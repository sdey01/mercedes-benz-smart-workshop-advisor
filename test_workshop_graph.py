import unittest

from workshop_graph import diagnose


def sample_event(event_id, dtc_code, subsystem, age, mileage, alert):
    return {
        "event_id": event_id,
        "vehicle_model": "Example Mercedes-Benz",
        "chassis_code": "TEST",
        "vin": "TEST-VIN",
        "vehicle_age_months": age,
        "mileage_km": mileage,
        "dtc_code": dtc_code,
        "subsystem": subsystem,
        "telemetry_alert": alert,
    }


class WorkshopGraphTests(unittest.TestCase):
    def test_hardware_fault_runs_both_lookups_and_checks_warranty(self):
        result = diagnose(
            sample_event(
                "TEST_HW",
                "P33E200",
                "High-Voltage Powertrain",
                18,
                28450,
                "HARDWARE FAULT: HV coolant pump pressure drop.",
            )
        )
        self.assertEqual(result["fault_category"], "Hardware_Repair")
        self.assertTrue(result["warranty_eligible"])
        self.assertEqual(result["parts_quote"]["total_parts_cost_eur"], 527.5)
        self.assertIn("parts_inventory_node", result["nodes_visited"])
        self.assertIn("xentry_manual_node", result["nodes_visited"])

    def test_software_update_skips_parts_lookup(self):
        result = diagnose(
            sample_event(
                "TEST_SW",
                "U111300",
                "MBUX Infotainment",
                11,
                14200,
                "SOFTWARE BUG: MBUX connectivity requires a firmware update.",
            )
        )
        self.assertEqual(result["fault_category"], "Software_Update")
        self.assertNotIn("parts_quote", result)
        self.assertIn("Do not replace physical hardware", result["final_advisory"])

    def test_info_alert_skips_both_lookups(self):
        result = diagnose(
            sample_event(
                "TEST_INFO",
                "B220664",
                "ADAS & Sensors",
                30,
                42100,
                "INFO ONLY: Radar recovered after heavy rain.",
            )
        )
        self.assertEqual(result["fault_category"], "Info")
        self.assertNotIn("manual_bulletin", result)
        self.assertNotIn("parts_quote", result)
        self.assertIn("NO WORKSHOP ACTION REQUIRED", result["final_advisory"])


if __name__ == "__main__":
    unittest.main()
