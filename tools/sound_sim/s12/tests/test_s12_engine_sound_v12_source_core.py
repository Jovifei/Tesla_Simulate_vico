"""Static contracts for the v1.2 pre-PTR differential source core."""

from __future__ import annotations

import json
import importlib.util
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
V12 = ROOT / "playground_v12"
COMMON = V12 / "common"
SCHEMA_PATH = COMMON / "schemas" / "source_profile_v12.schema.json"
SEMANTIC_CONTRACT_PATH = COMMON / "s12_v12_source_profile_contract.py"
BANK_MIXER_PATH = COMMON / "s12_v12_mix_bank_excitation.m"
PRE_PTR_ROUTER_PATH = COMMON / "s12_v12_render_pre_ptr_frame.m"


def parameter(value: object, unit: str, value_range: list[object]) -> dict:
    return {
        "value": value,
        "unit": unit,
        "range": value_range,
        "source_level": "C",
        "source": "synthetic",
        "source_url": "",
        "source_scope": "Synthetic S12 v1.2 source parameter; not OEM calibration.",
        "verification_state": "synthetic_assumption",
    }


def piston_source_profile() -> dict:
    return {
        "schema_version": "s12-engine-sound-v12-source-profile-1",
        "source": {
            "engine_kind": parameter("piston", "enum", ["piston", "rotary"]),
            "cylinders": parameter(8, "count", [1, 12]),
            "rotor_count": parameter(0, "count", [0, 2]),
            "chambers_per_rotor": parameter(0, "count", [0, 3]),
            "shaft_turns_per_rotor_turn": parameter(1, "ratio", [1, 3]),
            "layout": parameter("V", "enum", ["inline", "V", "rotary"]),
            "firing_order": parameter([1, 8, 4, 3, 6, 5, 7, 2], "event_id", [1, 8]),
            "firing_phases_deg": parameter(
                [0, 630, 270, 180, 450, 360, 540, 90], "deg", [0, 720]
            ),
            "bank_map": parameter([-1, 1, 1, -1, -1, 1, 1, -1], "bank", [-1, 1]),
            "pulse_sharpness": parameter(0.6, "ratio", [0, 1]),
            "combustion_gain": parameter(0.5, "ratio", [0, 1]),
            "intake_gain": parameter(0.1, "ratio", [0, 1]),
            "induction_gain": parameter(0.2, "ratio", [0, 1]),
            "mechanical_gain": parameter(0.1, "ratio", [0, 1]),
            "flow_gain": parameter(0.1, "ratio", [0, 1]),
            "order_surface": [
                {
                    "order": parameter(2.0, "order", [0.5, 18.0]),
                    "rpm_nodes": parameter([800, 4500, 9000], "rpm", [0, 12000]),
                    "low_load_gains": parameter([0.4, 0.5, 0.6], "ratio", [0, 1]),
                    "high_load_gains": parameter([0.8, 0.9, 1.0], "ratio", [0, 1]),
                    "phase_rad": parameter([0.0, 0.1, 0.2], "rad", [-3.141593, 3.141593]),
                }
            ],
        },
        "transient": {
            "acceleration_attack_gain": parameter(0.2, "ratio", [0, 1]),
            "lift_decay_gain": parameter(0.2, "ratio", [0, 1]),
        },
        "gearbox": {
            "torque_cut_gain": parameter(0.3, "ratio", [0, 1]),
            "shift_bark_gain": parameter(0.3, "ratio", [0, 1]),
        },
        "afterfire": {
            "upshift_bark_gain": parameter(0.2, "ratio", [0, 1]),
            "downshift_blip_pop_gain": parameter(0.2, "ratio", [0, 1]),
            "overrun_crackle_gain": parameter(0.2, "ratio", [0, 1]),
        },
    }


class S12V12SourceCoreContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_source_schema_requires_provenance_per_render_parameter(self) -> None:
        profile = piston_source_profile()
        jsonschema.Draft202012Validator(self.schema).validate(profile)
        profile["source"]["flow_gain"].pop("source_level")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(profile)

    def test_source_schema_rejects_unknown_or_invalid_piston_event_maps(self) -> None:
        profile = piston_source_profile()
        profile["source"]["unexpected"] = parameter(1, "ratio", [0, 1])
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(profile)

        profile = piston_source_profile()
        profile["source"]["flow_gain"]["range"] = ["minimum", "maximum"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(profile)

        profile = piston_source_profile()
        profile["source"]["firing_order"]["value"] = [1, 1, 2, 3, 4, 5, 6, 7]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(profile)

    def test_pre_ptr_source_core_has_all_causal_layers_and_no_v11_dependency(self) -> None:
        source = (COMMON / "s12_v12_render_source_frame.m").read_text(encoding="utf-8")
        validator = (COMMON / "s12_v12_validate_source_profile.m").read_text(encoding="utf-8")
        for symbol in (
            "renderPistonCombustion",
            "renderRotaryCombustion",
            "renderOrderSurface",
            "renderIntakeLayer",
            "renderInductionLayer",
            "renderMechanicalLayer",
            "renderFlowLayer",
            "renderGearboxTransient",
            "renderAfterfire",
            "bankExcitation",
            "applyDcBlocker",
            "smoothEnvelope",
        ):
            self.assertIn(symbol, source)
        self.assertIn("source_profile_v12", validator)
        self.assertNotIn("s12_v11", source)
        self.assertNotIn("s12_v11", validator)

    def test_source_core_uses_720_degree_timing_and_rpm_load_order_surfaces(self) -> None:
        source = (COMMON / "s12_v12_render_source_frame.m").read_text(encoding="utf-8")
        validator = (COMMON / "s12_v12_validate_source_profile.m").read_text(encoding="utf-8")
        self.assertIn("cycleIncrement = pi * rpm", source)
        self.assertIn("firing_phases_deg(eventId)", source)
        self.assertNotIn("sequencePhase", source)
        self.assertIn("rpm_nodes", source)
        self.assertIn("low_load_gains", source)
        self.assertIn("high_load_gains", source)
        self.assertIn("interp1", source)
        self.assertIn("smoothControl", source)
        self.assertIn("eventOrder = source.chambers_per_rotor / source.shaft_turns_per_rotor_turn", source)
        self.assertNotIn("rotor_count * source.chambers_per_rotor", source)
        self.assertIn("hasExactFields", validator)
        self.assertIn("sortIndexByPhase", validator)
        self.assertIn("source.shaft_turns_per_rotor_turn ~= 3", validator)
        self.assertNotIn("frame = frame - mean(frame)", source)
        self.assertNotIn("prePtrExcitation = prePtrExcitation - mean", source)

    def test_source_core_declares_fixed_frame_and_before_ptr_only_contract(self) -> None:
        source = (COMMON / "s12_v12_render_source_frame.m").read_text(encoding="utf-8")
        self.assertTrue(BANK_MIXER_PATH.exists(), "pre-PTR bank mixer is missing")
        mixer = BANK_MIXER_PATH.read_text(encoding="utf-8")
        self.assertTrue(PRE_PTR_ROUTER_PATH.exists(), "pre-PTR routing helper is missing")
        router = PRE_PTR_ROUTER_PATH.read_text(encoding="utf-8")
        self.assertIn("[frameSamples, 2]", source)
        self.assertIn("s12_v12_mix_bank_excitation", mixer)
        self.assertIn("[frameSamples, 1]", mixer)
        self.assertIn("s12_v12_render_source_frame", router)
        self.assertIn("s12_v12_mix_bank_excitation", router)
        self.assertIn("[frameSamples, 1]", router)
        self.assertIn("before_ptr_radiation", source)
        self.assertNotIn("audiowrite", source.lower())
        self.assertNotIn("sound(", source.lower())

    def test_source_contract_rejects_orders_above_eighteen_and_declares_real_bank_maps(self) -> None:
        profile = piston_source_profile()
        profile["source"]["order_surface"][0]["order"]["value"] = 18.5
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(profile)

        validator = (COMMON / "s12_v12_validate_source_profile.m").read_text(encoding="utf-8")
        self.assertIn("source.layout == \"V\"", validator)
        self.assertIn("any(source.bank_map == -1)", validator)
        self.assertIn("any(source.bank_map == 1)", validator)
        self.assertIn("all(source.bank_map == 0)", validator)

    def test_static_contract_enforces_numeric_ranges_and_dynamic_event_topology(self) -> None:
        self.assertTrue(SEMANTIC_CONTRACT_PATH.exists(), "semantic profile validator is missing")
        spec = importlib.util.spec_from_file_location("s12_v12_source_profile_contract", SEMANTIC_CONTRACT_PATH)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        module.validate_source_profile(piston_source_profile())

        out_of_range = piston_source_profile()
        out_of_range["source"]["flow_gain"]["value"] = 99
        with self.assertRaises(module.SourceProfileContractError):
            module.validate_source_profile(out_of_range)

        nonscalar_gain = piston_source_profile()
        nonscalar_gain["source"]["flow_gain"]["value"] = [0.1, 0.2]
        with self.assertRaises(module.SourceProfileContractError):
            module.validate_source_profile(nonscalar_gain)

        empty_gain = piston_source_profile()
        empty_gain["source"]["flow_gain"]["value"] = []
        with self.assertRaises(module.SourceProfileContractError):
            module.validate_source_profile(empty_gain)

        wrong_event_count = piston_source_profile()
        wrong_event_count["source"]["firing_order"]["value"] = [1, 2]
        wrong_event_count["source"]["firing_phases_deg"]["value"] = [0, 90]
        wrong_event_count["source"]["bank_map"]["value"] = [-1, 1]
        with self.assertRaises(module.SourceProfileContractError):
            module.validate_source_profile(wrong_event_count)

    def test_source_contract_rejects_non_scalar_char_text_and_unsafe_discrete_switches(self) -> None:
        source = (COMMON / "s12_v12_render_source_frame.m").read_text(encoding="utf-8")
        validator = (COMMON / "s12_v12_validate_source_profile.m").read_text(encoding="utf-8")
        self.assertIn("ischar(value) && isrow(value)", validator)
        self.assertIn("ischar(state.afterfire_kind) && isrow(state.afterfire_kind)", source)
        self.assertIn("validateDiscreteTransitions", source)
        self.assertIn("shift_event_state", source)
        self.assertIn("afterfire_kind_state", source)
        self.assertNotIn("nextEnvelope = target;", source)
        self.assertIn(
            "value = boundedScalar(container.(field), field, lower, upper);\nend\nend\n\n"
            "function value = optionalRowVector",
            source,
        )


if __name__ == "__main__":
    unittest.main()
