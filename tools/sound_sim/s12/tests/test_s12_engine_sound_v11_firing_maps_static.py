"""Static contracts for v1.1 synthetic firing/event and bank-map topology."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
VEHICLES = {
    "hellcat_2022_stock": (8, "V"),
    "gtr_r35_2007_stock": (6, "V"),
    "c63_w204_facelift_stock": (8, "V"),
    "supra_jza80_rz_stock": (6, "inline"),
    "rx7_fd_1991_stock": (2, "rotary"),
    "lexus_lfa_stock": (10, "V"),
    "ferrari_458_stock": (8, "V"),
    "aventador_lp700_stock": (12, "V"),
}
RECORD_FIELDS = {
    "value",
    "unit",
    "range",
    "source_level",
    "source",
    "source_url",
    "source_scope",
    "verification_state",
}
ENGINE_FIELDS = {
    "configuration",
    "layout",
    "firing_order",
    "firing_phases_deg",
    "bank_map",
    "redline_rpm",
    "ecu_logic",
}


class S12EngineSoundV11FiringMapStaticTests(unittest.TestCase):
    def test_every_vehicle_declares_provenance_complete_synthetic_event_maps(self) -> None:
        for vehicle_id, (event_count, expected_layout) in VEHICLES.items():
            profile = load_profile(vehicle_id)
            engine = profile["engine"]
            self.assertEqual(set(engine), ENGINE_FIELDS, vehicle_id)
            for field, record in engine.items():
                self.assertEqual(set(record), RECORD_FIELDS, f"{vehicle_id}:{field}")
                self.assertEqual(record["source_level"], "C")
                self.assertEqual(record["source"], "synthetic")
                self.assertEqual(record["source_url"], "")
                self.assertEqual(record["verification_state"], "synthetic_assumption")
                self.assertIn("synthetic", record["source_scope"].lower())

            self.assertEqual(engine["layout"]["value"], expected_layout)
            order = engine["firing_order"]["value"]
            phases = engine["firing_phases_deg"]["value"]
            banks = engine["bank_map"]["value"]
            self.assertEqual(len(order), event_count)
            self.assertEqual(len(phases), event_count)
            self.assertEqual(len(banks), event_count)
            self.assertEqual(sorted(order), list(range(1, event_count + 1)))
            self.assertEqual(len(set(phases)), event_count)
            self.assertTrue(all(isinstance(phase, (int, float)) and 0 <= phase < 720 for phase in phases))
            self.assertTrue(all(bank in (-1, 0, 1) for bank in banks))
            if expected_layout == "V":
                self.assertIn(-1, banks)
                self.assertIn(1, banks)
            elif expected_layout == "inline":
                self.assertEqual(set(banks), {0})
            else:
                self.assertEqual(sorted(banks), [-1, 1])

    def test_schema_validator_loader_and_both_excitation_paths_require_event_maps(self) -> None:
        schema = json.loads((V11 / "common" / "schemas" / "vehicle_package.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["engine_contract"]["fields"]), ENGINE_FIELDS)
        self.assertEqual(set(schema["engine_contract"]["record_fields"]), RECORD_FIELDS)
        self.assertEqual(schema["engine_contract"]["allowed_layouts"], ["inline", "V", "rotary"])

        validator = (V11 / "common" / "s12_v11_validate_vehicle_package.m").read_text(encoding="utf-8")
        loader = (V11 / "s12_v11_load_profile.m").read_text(encoding="utf-8")
        renderer = (V11 / "s12_v11_render_profile.m").read_text(encoding="utf-8")
        model = (V11 / "s12_v11_model_excitation_afterfire_step.m").read_text(encoding="utf-8")
        rotary = (V11 / "s12_v11_render_rotary_excitation_frame.m").read_text(encoding="utf-8")
        piston = (V11 / "s12_v11_render_piston_excitation_frame.m").read_text(encoding="utf-8")
        for token in ("validateEngineEventMap", "firing_phases_deg", "bank_map", "unique(firingOrder)"):
            self.assertIn(token, validator)
        for token in ("mapEngineEventMap(metadata.engine", '"engine", engine'):
            self.assertIn(token, loader)
        for text in (renderer, model):
            self.assertIn("s12_v11_render_piston_excitation_frame", text)
            self.assertIn("profile.engine", text)
        self.assertIn("engineEventMap", piston)
        self.assertIn("engineEventMap", rotary)

    def test_authored_matlab_sensitivity_test_mutates_order_and_bank_map(self) -> None:
        test_text = (ROOT / "tests" / "test_s12_engine_sound_v11_firing_maps.m").read_text(encoding="utf-8")
        hellcat = between(test_text, "function testFiringOrderMutation", "function testBankAndPhaseMutations")
        rx7 = between(test_text, "function testRotaryMapMutation", "function testMissingOrInvalidMapsAreRejected")
        self.assertIn("mutated.engine.firing_order([3, 4])", hellcat)
        self.assertIn("norm(baseline.base_excitation - changed.base_excitation)", hellcat)
        self.assertIn("mutated.engine.bank_map = fliplr(profile.engine.bank_map);", rx7)
        self.assertNotIn("mutated.engine.firing_phases_deg", rx7)
        self.assertIn("norm(baseline.base_excitation - changed.base_excitation)", rx7)
        self.assertIn("verifyNotEqual(testCase, baseline.pcm_sha256", test_text)


def load_profile(vehicle_id: str) -> dict:
    return json.loads((V11 / "vehicles" / vehicle_id / "profile.json").read_text(encoding="utf-8"))


def between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


if __name__ == "__main__":
    unittest.main(verbosity=2)
