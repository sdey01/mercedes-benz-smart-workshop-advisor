import json
import operator
from pathlib import Path
from typing import Annotated, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph


DATA_DIR = Path(__file__).resolve().parent


def load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    with path.open(encoding="utf-8") as file:
        return json.load(file)


MANUALS_DB = load_json("2_xentry_manuals_db.json")
PARTS_DB = load_json("3_parts_inventory_db.json")
WARRANTY_RULES = PARTS_DB["warranty_rules"]


class WorkshopState(TypedDict):
    event_id: str
    vehicle_model: str
    chassis_code: str
    vin: str
    vehicle_age_months: int
    mileage_km: int
    dtc_code: str
    subsystem: str
    telemetry_alert: str
    warranty_eligible: NotRequired[bool]
    warranty_type: NotRequired[str]
    fault_category: NotRequired[Literal["Info", "Software_Update", "Hardware_Repair"]]
    manual_bulletin: NotRequired[dict]
    parts_quote: NotRequired[dict]
    final_advisory: NotRequired[str]
    nodes_visited: Annotated[list[str], operator.add]


def parse_telemetry_node(state: WorkshopState) -> dict:
    if state["subsystem"] == "High-Voltage Powertrain":
        warranty_type = "HV Powertrain Warranty"
        rule = WARRANTY_RULES["hv_powertrain_warranty"]
    else:
        warranty_type = "Standard Vehicle Warranty"
        rule = WARRANTY_RULES["standard_vehicle_warranty"]

    covered = (
        state["vehicle_age_months"] <= rule["max_age_months"]
        and state["mileage_km"] <= rule["max_mileage_km"]
        and state["subsystem"] in rule["applicable_subsystems"]
    )
    return {
        "warranty_eligible": covered,
        "warranty_type": warranty_type,
        "nodes_visited": ["parse_telemetry_node"],
    }


def triage_classifier_node(state: WorkshopState) -> dict:
    alert = state["telemetry_alert"].strip().upper()
    if alert.startswith("INFO ONLY:"):
        category = "Info"
    elif alert.startswith("SOFTWARE BUG:"):
        category = "Software_Update"
    elif alert.startswith("HARDWARE FAULT:"):
        category = "Hardware_Repair"
    else:
        raise ValueError(f"Unable to classify telemetry alert for {state['event_id']}")

    return {
        "fault_category": category,
        "nodes_visited": ["triage_classifier_node"],
    }


def xentry_manual_node(state: WorkshopState) -> dict:
    return {
        "manual_bulletin": MANUALS_DB.get(state["dtc_code"], {}),
        "nodes_visited": ["xentry_manual_node"],
    }


def parts_inventory_node(state: WorkshopState) -> dict:
    return {
        "parts_quote": PARTS_DB["parts_bundles_by_dtc"].get(state["dtc_code"], {}),
        "nodes_visited": ["parts_inventory_node"],
    }


def advisory_synthesizer_node(state: WorkshopState) -> dict:
    category = state["fault_category"]
    alert = state["telemetry_alert"]

    if category == "Info":
        reason = alert.partition(":")[2].strip() or alert
        advisory = (
            "NO WORKSHOP ACTION REQUIRED [INFO]: No parts or manual lookup are needed. "
            f"The telemetry reports normal behavior: {reason}"
        )
    else:
        bulletin = state.get("manual_bulletin", {})
        if not bulletin:
            raise ValueError(f"No XENTRY bulletin found for DTC {state['dtc_code']}")

        warranty_status = (
            f"Covered under {state['warranty_type']}."
            if state["warranty_eligible"]
            else (
                f"Out of warranty ({state['vehicle_age_months']} months / "
                f"{state['mileage_km']:,} km); customer-billable."
            )
        )
        prefix = (
            "SOFTWARE UPDATE ONLY"
            if category == "Software_Update"
            else "HARDWARE REPAIR"
        )
        advisory_parts = [
            f"{prefix} [{bulletin['bulletin_id']}]: {bulletin['repair_steps']}",
            f"Labor: {bulletin['labor_hours']:.1f} hours.",
        ]

        if category == "Software_Update":
            advisory_parts.extend(
                [
                    "Do not replace physical hardware.",
                    "Parts cost: EUR 0.00.",
                    warranty_status,
                ]
            )
        else:
            quote = state.get("parts_quote", {})
            if not quote:
                raise ValueError(f"No parts quote found for DTC {state['dtc_code']}")
            parts = []
            for part in quote.get("parts", []):
                stock = part["stock_status"]
                if stock == "Backordered":
                    stock += f", {part['lead_time_days']}-day lead time"
                parts.append(f"{part['part_number']} ({stock})")
            advisory_parts.extend(
                [
                    f"Required parts: {', '.join(parts) or 'None listed'}.",
                    f"Total parts cost: EUR {quote['total_parts_cost_eur']:,.2f}.",
                    warranty_status,
                ]
            )
        advisory = " ".join(advisory_parts)

    return {
        "final_advisory": advisory,
        "nodes_visited": ["advisory_synthesizer_node"],
    }


def route_by_fault_category(
    state: WorkshopState,
) -> str | list[str]:
    category = state["fault_category"]
    if category == "Info":
        return "advisory_synthesizer_node"
    if category == "Software_Update":
        return "xentry_manual_node"
    if category == "Hardware_Repair":
        return ["xentry_manual_node", "parts_inventory_node"]
    raise ValueError(f"Unsupported fault category: {category}")


def build_workflow():
    workflow = StateGraph(WorkshopState)
    workflow.add_node("parse_telemetry_node", parse_telemetry_node)
    workflow.add_node("triage_classifier_node", triage_classifier_node)
    workflow.add_node("xentry_manual_node", xentry_manual_node)
    workflow.add_node("parts_inventory_node", parts_inventory_node)
    workflow.add_node("advisory_synthesizer_node", advisory_synthesizer_node)

    workflow.add_edge(START, "parse_telemetry_node")
    workflow.add_edge("parse_telemetry_node", "triage_classifier_node")
    workflow.add_conditional_edges(
        "triage_classifier_node",
        route_by_fault_category,
        [
            "advisory_synthesizer_node",
            "xentry_manual_node",
            "parts_inventory_node",
        ],
    )
    workflow.add_edge("xentry_manual_node", "advisory_synthesizer_node")
    workflow.add_edge("parts_inventory_node", "advisory_synthesizer_node")
    workflow.add_edge("advisory_synthesizer_node", END)
    return workflow.compile()


app = build_workflow()


def diagnose(event: dict) -> WorkshopState:
    return app.invoke({**event, "nodes_visited": []})
