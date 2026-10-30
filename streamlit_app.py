import streamlit as st

from workshop_graph import app, diagnose


st.set_page_config(
    page_title="Mercedes-Benz Workshop Advisor",
    page_icon="🚘",
    layout="wide",
)
st.title("Mercedes-Benz Smart Workshop Advisor")
st.caption(
    "Enter a vehicle telemetry event to run LangGraph triage, warranty checks, "
    "XENTRY guidance, and parts lookup."
)

with st.form("telemetry_event"):
    st.subheader("Vehicle and diagnostic details")
    event_id = st.text_input("Event ID", placeholder="For example: MB_HW_01")
    vehicle_model = st.text_input("Vehicle model", placeholder="Mercedes-Benz EQS 580 4MATIC")
    chassis_code = st.text_input("Chassis code", placeholder="V297")
    vin = st.text_input("VIN", placeholder="Enter the 17-character VIN")
    dtc_code = st.text_input("DTC code", placeholder="For example: P33E200")
    subsystem = st.text_input(
        "Subsystem",
        placeholder="For example: High-Voltage Powertrain",
    )

    age_column, mileage_column = st.columns(2)
    vehicle_age_months = age_column.number_input(
        "Vehicle age (months)",
        min_value=0,
        step=1,
        value=None,
        placeholder="Enter age",
    )
    mileage_km = mileage_column.number_input(
        "Mileage (km)",
        min_value=0,
        step=1,
        value=None,
        placeholder="Enter mileage",
    )
    telemetry_alert = st.text_area(
        "Telemetry alert",
        placeholder=(
            "Describe the warning or behavior. Prefix with INFO ONLY:, "
            "SOFTWARE BUG:, or HARDWARE FAULT: for unambiguous triage."
        ),
        height=140,
    )
    submitted = st.form_submit_button("Run workshop triage", type="primary")

if submitted:
    st.session_state.pop("diagnosis", None)
    st.session_state.pop("diagnosis_event_id", None)
    required_fields = {
        "Event ID": event_id,
        "Vehicle model": vehicle_model,
        "Chassis code": chassis_code,
        "VIN": vin,
        "DTC code": dtc_code,
        "Subsystem": subsystem,
        "Telemetry alert": telemetry_alert,
    }
    missing_fields = [name for name, value in required_fields.items() if not value.strip()]
    if vehicle_age_months is None:
        missing_fields.append("Vehicle age")
    if mileage_km is None:
        missing_fields.append("Mileage")
    if missing_fields:
        st.error(f"Please provide: {', '.join(missing_fields)}.")
    else:
        event = {
            "event_id": event_id.strip(),
            "vehicle_model": vehicle_model.strip(),
            "chassis_code": chassis_code.strip(),
            "vin": vin.strip(),
            "vehicle_age_months": int(vehicle_age_months),
            "mileage_km": int(mileage_km),
            "dtc_code": dtc_code.strip().upper(),
            "subsystem": subsystem.strip(),
            "telemetry_alert": telemetry_alert.strip(),
        }
        try:
            st.session_state["diagnosis"] = diagnose(event)
            st.session_state["diagnosis_event_id"] = event["event_id"]
        except ValueError as error:
            st.error(str(error))

result = st.session_state.get("diagnosis")
if result and result["event_id"] == st.session_state.get("diagnosis_event_id"):
    st.subheader("Workshop advisory")
    st.info(result["final_advisory"])

    first, second, third = st.columns(3)
    first.metric("Fault category", result["fault_category"])
    second.metric(
        "Warranty",
        "Eligible" if result["warranty_eligible"] else "Not eligible",
    )
    second.caption(result["warranty_type"])
    quote = result.get("parts_quote", {})
    third.metric(
        "Parts cost",
        f"EUR {quote.get('total_parts_cost_eur', 0):,.2f}",
    )

    st.subheader("Execution trace")
    st.write(" → ".join(result["nodes_visited"]))

    if result.get("manual_bulletin"):
        with st.expander("XENTRY manual bulletin"):
            st.write(f"**{result['manual_bulletin']['bulletin_id']}**")
            st.write(result["manual_bulletin"]["title"])
            st.write(result["manual_bulletin"]["repair_steps"])
            st.write(f"Labor: {result['manual_bulletin']['labor_hours']:.1f} hours")

    if quote:
        with st.expander("Parts quote"):
            st.dataframe(quote.get("parts", []), width="stretch", hide_index=True)

with st.expander("Workflow graph"):
    st.graphviz_chart(
        """
        digraph {
          rankdir=TB;
          start [label="START"];
          parse [label="parse_telemetry_node"];
          triage [label="triage_classifier_node"];
          manual [label="xentry_manual_node"];
          parts [label="parts_inventory_node"];
          report [label="advisory_synthesizer_node"];
          end [label="END"];
          start -> parse -> triage;
          triage -> report [label="Info"];
          triage -> manual [label="Software_Update"];
          triage -> manual [label="Hardware_Repair"];
          triage -> parts [label="Hardware_Repair"];
          manual -> report;
          parts -> report;
          report -> end;
        }
        """
    )
    st.code(app.get_graph().draw_mermaid(), language="mermaid")
