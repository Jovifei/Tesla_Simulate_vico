"""Static contracts for v1.1 JSON-as-render-parameter truth."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
VEHICLES = (
    "hellcat_2022_stock",
    "gtr_r35_2007_stock",
    "c63_w204_facelift_stock",
    "supra_jza80_rz_stock",
    "rx7_fd_1991_stock",
    "lexus_lfa_stock",
    "ferrari_458_stock",
    "aventador_lp700_stock",
)
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
RENDER_SECTIONS = {
    "architecture",
    "rpm_load",
    "order_harmonics",
    "character",
    "transient",
    "afterfire",
    "ptr",
    "renderer",
    "dashboard_defaults",
    "vehicle_state",
}
REQUIRED_PARAMETERS = {
    "architecture": {
        "engine_kind",
        "cylinders",
        "rotor_count",
        "chambers_per_rotor",
        "shaft_turns_per_rotor_turn",
    },
    "rpm_load": {"idle_rpm", "redline_rpm", "minimum_load", "maximum_load"},
    "order_harmonics": {"order_gains", "firing_gain", "firing_harmonic_gain"},
    "character": {
        "pulse_sharpness",
        "intake_tone",
        "supercharger_tone",
        "source_gain",
        "output_gain",
        "stereo_offset",
        "order_load_tilt_gain",
        "intake_base_mix",
        "intake_throttle_mix",
        "supercharger_base_mix",
        "supercharger_throttle_mix",
        "source_base_mix",
        "source_load_mix",
        "rotary_apex_gain",
    },
    "transient": {"acceleration_gain", "throttle_delta_gain", "output_gain"},
    "afterfire": {
        "idle_rpm_ceiling",
        "minimum_event_rpm",
        "upshift_max_throttle",
        "downshift_min_throttle",
        "overrun_max_throttle",
        "overrun_max_acceleration",
        "minimum_shift_load",
        "steady_acceleration_limit",
        "cruise_min_throttle",
        "cruise_max_throttle",
        "base_energy",
        "onset_delay_s",
        "cluster_interval_s",
        "cluster_refractory_s",
        "refractory_jitter_fraction",
        "interval_jitter_fraction",
        "cluster_energy_decay",
        "upshift_max_throttle_rate_per_s",
        "downshift_min_throttle_rate_per_s",
        "downshift_min_rpm_rate_per_s",
        "overrun_max_throttle_rate_per_s",
        "overrun_max_rpm_rate_per_s",
        "minimum_thermal_eligibility",
        "lift_energy_decay_rate_per_s",
        "lift_refractory_growth_per_s",
    },
    "ptr": {"pipe_length_m", "area_m2", "reflection", "damping"},
    "renderer": {
        "sample_rate_hz",
        "frame_samples",
        "channels",
        "bits_per_sample",
        "hard_limiter",
    },
    "dashboard_defaults": {
        "rpm", "load", "acceleration", "throttle", "order_balance", "transient",
        "backfire_level", "ptr_pipe_length_m", "ptr_area_m2", "ptr_reflection",
        "ptr_damping", "gain",
    },
    "vehicle_state": {
        "speed_kph_per_rpm", "speed_acceleration_gain", "gear_rpm_step",
        "minimum_gear", "maximum_gear", "upshift_rpm_threshold",
        "downshift_rpm_threshold", "dfco_throttle_threshold",
        "dfco_acceleration_threshold", "shift_hold_s", "derivative_min_dt_s",
        "thermal_initial_eligibility", "thermal_heating_rate_per_s",
        "thermal_cooling_rate_per_s", "thermal_load_gain",
        "thermal_rpm_reference_rpm",
    },
}


class S12EngineSoundV11JsonTruthStaticTests(unittest.TestCase):
    def test_every_render_parameter_is_a_synthetic_provenance_record(self) -> None:
        for vehicle_id in VEHICLES:
            payload = load_profile(vehicle_id)
            self.assertEqual(set(payload["render_tuning"]), RENDER_SECTIONS)
            for section, expected_names in REQUIRED_PARAMETERS.items():
                parameters = payload["render_tuning"][section]
                self.assertEqual(set(parameters), expected_names, f"{vehicle_id}:{section}")
                for name, record in parameters.items():
                    self.assertEqual(set(record), RECORD_FIELDS, f"{vehicle_id}:{section}.{name}")
                    self.assertEqual(record["source_level"], "C")
                    self.assertEqual(record["source"], "synthetic")
                    self.assertEqual(record["source_url"], "")
                    self.assertEqual(record["verification_state"], "synthetic_assumption")
                    self.assertTrue(record["source_scope"])
                    self.assertIn("synthetic", record["source_scope"].lower())
                    self.assertIn("value", record)
                    self.assertIn("unit", record)
                    self.assertIn("range", record)

    def test_schema_binds_complete_render_tuning_and_rejects_unknown_bypass(self) -> None:
        schema = json.loads((V11 / "common" / "schemas" / "vehicle_package.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["documents"]["profile"]), {
            "schema_version", "vehicle_id", "vehicle_identity", "provenance", "scope", "engine", "render_tuning"
        })
        contract = schema["render_tuning"]
        self.assertEqual(set(contract["sections"]), RENDER_SECTIONS)
        self.assertEqual(set(contract["record_fields"]), RECORD_FIELDS)
        self.assertEqual(contract["allowed_source_levels"], ["C"])
        self.assertEqual(contract["allowed_sources"], ["synthetic"])
        self.assertEqual(contract["allowed_verification_states"], ["synthetic_assumption"])

    def test_loader_maps_json_records_without_an_identifier_tuning_switch(self) -> None:
        loader = (V11 / "s12_v11_load_profile.m").read_text(encoding="utf-8")
        self.assertIn('profile.render_tuning = metadata.render_tuning', loader)
        self.assertIn("mapRenderTuning(metadata.render_tuning)", loader)
        self.assertNotIn("switch identifier", loader)
        self.assertNotIn("function [character, afterfire, ptr] = vehicleCharacter", loader)
        self.assertNotIn("function value = makeCharacter", loader)
        self.assertNotIn("function value = makePtr", loader)

    def test_validator_has_a_render_tuning_rejection_path(self) -> None:
        validator = (V11 / "common" / "s12_v11_validate_vehicle_package.m").read_text(encoding="utf-8")
        self.assertIn("validateRenderTuning(profile.render_tuning, schema)", validator)
        self.assertIn('"S12:EngineSoundV11:RenderTuning"', validator)
        self.assertIn("requireExactFields(tuning", validator)
        self.assertIn("validateTuningRecord", validator)

    def test_offline_renderer_and_model_helpers_consume_loaded_render_tuning(self) -> None:
        renderer = (V11 / "s12_v11_render_profile.m").read_text(encoding="utf-8")
        excitation = (V11 / "s12_v11_model_excitation_afterfire_step.m").read_text(encoding="utf-8")
        ptr = (V11 / "s12_v11_model_ptr_radiation_step.m").read_text(encoding="utf-8")
        stereo = (V11 / "s12_v11_model_stereo_renderer_step.m").read_text(encoding="utf-8")
        builder = (V11 / "s12_v11_build_simulink_models.m").read_text(encoding="utf-8")
        for text in (renderer, excitation):
            for token in (
                "profile.renderer.sample_rate_hz",
                "profile.renderer.frame_samples",
                "character.firing_gain",
                "character.firing_harmonic_gain",
                "character.minimum_load",
                "character.maximum_load",
                "character.order_load_tilt_gain",
                "profile.transient.acceleration_gain",
                "profile.transient.throttle_delta_gain",
                "profile.transient.output_gain",
            ):
                self.assertIn(token, text)
        self.assertIn("s12_v11_load_profile", ptr)
        selector = (V11 / "s12_v11_model_ptr_controls_step.m").read_text(encoding="utf-8")
        self.assertIn("ptrControls(1)", ptr)
        self.assertIn("s12_v11_model_dashboard_controls(profile)", selector)
        self.assertIn("profile.renderer.frame_samples", ptr)
        self.assertIn("s12_v11_load_profile", stereo)
        self.assertIn("gain *", stereo)
        self.assertIn("profile.character.stereo_offset", stereo)
        self.assertIn("s12_v11_model_dashboard_controls(profile)", builder)

    def test_rotary_excitation_uses_mapped_character_gains_without_hidden_literals(self) -> None:
        loader = (V11 / "s12_v11_load_profile.m").read_text(encoding="utf-8")
        rotary = (V11 / "s12_v11_render_rotary_excitation_frame.m").read_text(encoding="utf-8")
        self.assertIn('"rotary_apex_gain", valueOf(characterParameters.rotary_apex_gain)', loader)
        expression = rotary.split("excitation =", 1)[1].split("nextPhaseRad", 1)[0]
        self.assertIn("character.firing_gain * sin(firingPhase)", expression)
        self.assertIn("character.firing_harmonic_gain * sharpness", expression)
        self.assertIn("character.rotary_apex_gain * sin(apexPhase + pi / 5)", expression)
        for hidden_gain in ("0.20", "0.09", "0.045"):
            self.assertNotIn(hidden_gain, expression)

    def test_validator_uses_schema_owned_bounds_and_integral_architecture_counts(self) -> None:
        schema = json.loads((V11 / "common" / "schemas" / "vehicle_package.schema.json").read_text(encoding="utf-8"))
        validator = (V11 / "common" / "s12_v11_validate_vehicle_package.m").read_text(encoding="utf-8")
        self.assertIn("numeric_bounds", schema["render_tuning"])
        self.assertEqual(
            schema["render_tuning"]["integer_parameter_paths"],
            [
                "architecture.cylinders",
                "architecture.rotor_count",
                "architecture.chambers_per_rotor",
                "architecture.shaft_turns_per_rotor_turn",
                "renderer.sample_rate_hz",
                "renderer.frame_samples",
                "renderer.channels",
                "renderer.bits_per_sample",
                "dashboard_defaults.backfire_level",
                "vehicle_state.minimum_gear",
                "vehicle_state.maximum_gear",
            ],
        )
        self.assertIn("schemaOwnedBounds", validator)
        self.assertIn("value ~= floor(value)", validator)
        self.assertIn("declaredRange(1) < schemaOwnedBounds(1)", validator)


def load_profile(vehicle_id: str) -> dict:
    return json.loads((V11 / "vehicles" / vehicle_id / "profile.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
