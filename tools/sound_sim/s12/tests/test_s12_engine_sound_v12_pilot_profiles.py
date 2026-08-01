"""Package contracts for the first three reference-guided v1.2 pilots."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
V12 = ROOT / "playground_v12"
VEHICLES = V12 / "vehicles"
SCHEMAS = V12 / "common" / "schemas"
SEMANTIC_CONTRACT_PATH = V12 / "common" / "s12_v12_source_profile_contract.py"
PILOTS = {
    "hellcat_2022_stock": ("piston", 8, 0, "V"),
    "ferrari_458_stock": ("piston", 8, 0, "V"),
    "rx7_fd_1991_stock": ("rotary", 0, 2, "rotary"),
}
REFERENCE_EXPECTATIONS = {
    "hellcat_2022_stock": ("R3", "rejected"),
    "ferrari_458_stock": ("R2", "listening_only"),
    "rx7_fd_1991_stock": ("R2", "listening_only"),
}


def value(record: dict):
    return record["value"]


def assert_synthetic_parameter_tree(test: unittest.TestCase, payload: object) -> None:
    if isinstance(payload, dict):
        if "value" in payload:
            test.assertEqual(payload["source_level"], "C")
            test.assertEqual(payload["source"], "synthetic")
            test.assertEqual(payload["verification_state"], "synthetic_assumption")
        for child in payload.values():
            assert_synthetic_parameter_tree(test, child)
    elif isinstance(payload, list):
        for child in payload:
            assert_synthetic_parameter_tree(test, child)


class S12V12PilotProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_schema = json.loads(
            (SCHEMAS / "source_profile_v12.schema.json").read_text(encoding="utf-8")
        )
        cls.reference_schema = json.loads(
            (SCHEMAS / "reference_manifest_v12.schema.json").read_text(encoding="utf-8")
        )
        spec = importlib.util.spec_from_file_location("s12_v12_source_profile_contract", SEMANTIC_CONTRACT_PATH)
        assert spec is not None and spec.loader is not None
        cls.contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.contract)

    def test_pilot_source_profiles_validate_and_are_topologically_distinct(self) -> None:
        profiles: dict[str, dict] = {}
        for vehicle_id, expected in PILOTS.items():
            with self.subTest(vehicle_id=vehicle_id):
                payload = json.loads((VEHICLES / vehicle_id / "source_profile.json").read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(self.source_schema).validate(payload)
                self.contract.validate_source_profile(payload)
                assert_synthetic_parameter_tree(self, payload)
                source = payload["source"]
                self.assertEqual(
                    (value(source["engine_kind"]), value(source["cylinders"]), value(source["rotor_count"]), value(source["layout"])),
                    expected,
                )
                phases = value(source["firing_phases_deg"])
                order = value(source["firing_order"])
                self.assertEqual(order, [index + 1 for index, _phase in sorted(enumerate(phases), key=lambda item: item[1])])
                profiles[vehicle_id] = payload

        self.assertGreater(
            value(profiles["hellcat_2022_stock"]["source"]["induction_gain"]),
            value(profiles["ferrari_458_stock"]["source"]["induction_gain"]),
        )
        self.assertGreater(
            value(profiles["ferrari_458_stock"]["source"]["flow_gain"]),
            value(profiles["hellcat_2022_stock"]["source"]["flow_gain"]),
        )
        self.assertEqual(value(profiles["rx7_fd_1991_stock"]["source"]["cylinders"]), 0)
        self.assertEqual(
            value(profiles["rx7_fd_1991_stock"]["source"]["shaft_turns_per_rotor_turn"]), 3
        )
        source = (V12 / "common" / "s12_v12_render_source_frame.m").read_text(encoding="utf-8")
        self.assertIn("eventOrder = source.chambers_per_rotor / source.shaft_turns_per_rotor_turn", source)

    def test_pilot_reference_manifests_never_mislabel_unqualified_or_wrong_vehicle_media(self) -> None:
        for vehicle_id in PILOTS:
            with self.subTest(vehicle_id=vehicle_id):
                manifest = json.loads((VEHICLES / vehicle_id / "reference_manifest.json").read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(self.reference_schema).validate(manifest)
                self.assertEqual(manifest["vehicle_id"], vehicle_id)
                expected_class, expected_use = REFERENCE_EXPECTATIONS[vehicle_id]
                self.assertEqual(manifest["quality_class"], expected_class)
                self.assertEqual(manifest["inventory_use"], expected_use)
                self.assertNotIn("rpm_evidence", manifest)
                self.assertNotIn("stock_evidence", manifest)
                if expected_class == "R3":
                    self.assertIn("rejection_reason", manifest)
                else:
                    self.assertNotIn("rejection_reason", manifest)
                self.assertEqual(
                    manifest["source"]["source_url_sha256"],
                    hashlib.sha256(manifest["source"]["url"].encode("utf-8")).hexdigest(),
                )
                self.assertFalse((VEHICLES / vehicle_id / "acoustic_target.json").exists())


if __name__ == "__main__":
    unittest.main()
