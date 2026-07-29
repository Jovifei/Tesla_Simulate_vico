"""Static contracts for the v1.1 Simulink control/interface parity repair.

These tests deliberately inspect real JSON records and concrete builder/helper
dataflow.  They do not claim that MATLAB or Simulink has compiled the models.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
VEHICLES = tuple(sorted(path.name for path in (V11 / "vehicles").iterdir() if path.is_dir()))
CONTROLS = (
    "rpm", "load", "acceleration", "throttle", "order_balance", "transient",
    "backfire_level", "ptr_pipe_length_m", "ptr_area_m2", "ptr_reflection",
    "ptr_damping", "gain",
)
VEHICLE_STATE = (
    "speed_kph_per_rpm", "speed_acceleration_gain", "gear_rpm_step",
    "minimum_gear", "maximum_gear", "upshift_rpm_threshold",
    "downshift_rpm_threshold", "dfco_throttle_threshold",
    "dfco_acceleration_threshold", "shift_hold_s", "derivative_min_dt_s",
    "thermal_initial_eligibility", "thermal_heating_rate_per_s",
    "thermal_cooling_rate_per_s", "thermal_load_gain",
    "thermal_rpm_reference_rpm",
)


class S12EngineSoundV11ModelParityStaticTests(unittest.TestCase):
    def test_every_profile_has_provenance_complete_dashboard_and_vehicle_state_truth(self) -> None:
        self.assertEqual(len(VEHICLES), 8)
        for vehicle_id in VEHICLES:
            profile = json.loads((V11 / "vehicles" / vehicle_id / "profile.json").read_text(encoding="utf-8"))
            tuning = profile["render_tuning"]
            self.assertEqual(set(tuning["dashboard_defaults"]), set(CONTROLS))
            self.assertEqual(set(tuning["vehicle_state"]), set(VEHICLE_STATE))
            for section_name, expected in (("dashboard_defaults", CONTROLS), ("vehicle_state", VEHICLE_STATE)):
                for name in expected:
                    record = tuning[section_name][name]
                    self.assertEqual(record["source_level"], "C")
                    self.assertEqual(record["source"], "synthetic")
                    self.assertEqual(record["verification_state"], "synthetic_assumption")
                    self.assertEqual(record["source_url"], "")
                    self.assertEqual(len(record["range"]), 2)
                    self.assertLessEqual(record["range"][0], record["value"])
                    self.assertLessEqual(record["value"], record["range"][1])

    def test_schema_and_loader_make_the_new_json_values_runtime_visible(self) -> None:
        schema = json.loads((V11 / "common" / "schemas" / "vehicle_package.schema.json").read_text(encoding="utf-8"))
        sections = schema["render_tuning"]["sections"]
        self.assertEqual(tuple(sections["dashboard_defaults"]), CONTROLS)
        self.assertEqual(tuple(sections["vehicle_state"]), VEHICLE_STATE)
        loader = source("s12_v11_load_profile.m")
        mapping = function_body(loader, "mapRenderTuning")
        self.assertRegex(mapping, r"tuning\.vehicle_state\s*=\s*unwrapSection\(renderTuning\.vehicle_state\)")
        self.assertRegex(mapping, r"tuning\.dashboard_defaults\s*=\s*unwrapSection\(renderTuning\.dashboard_defaults\)")

    def test_builder_has_all_bound_controls_and_continuous_state_timeline(self) -> None:
        contracts = source("s12_v11_model_contracts.m")
        for display in (
            "Dashboard RPM", "Dashboard Load", "Dashboard Acceleration", "Dashboard Throttle",
            "Dashboard Order Balance", "Dashboard Transient", "Dashboard Backfire Level",
            "Dashboard PTR Pipe Length", "Dashboard PTR Area", "Dashboard PTR Reflection",
            "Dashboard PTR Damping", "Dashboard Gain",
        ):
            self.assertIn(display, contracts)
        builder = source("s12_v11_build_simulink_models.m")
        dashboard = function_body(builder, "addDashboardControls")
        self.assertRegex(dashboard, r"s12_v11_model_dashboard_controls\(profile\)")
        self.assertRegex(dashboard, r"set_param\(knobPath,\s*\"Binding\",\s*binding\)")
        self.assertRegex(dashboard, r"\"Inputs\",\s*num2str\(numel\(controls\)\s*\+\s*1\)")
        wrapper = function_body(builder, "buildVehicleWrapper")
        self.assertRegex(wrapper, r"add_block\(\"simulink/Sources/Clock\",\s*model\s*\+\s*\"/Timeline Clock\"")
        self.assertRegex(wrapper, r"add_line\(model,\s*\"Timeline Clock/1\",\s*stateMux\s*\+\s*\"/\"\s*\+\s*string\(numel\(controlNames\)\s*\+\s*1\)")

    def test_builder_routes_state_controls_to_excitation_ptr_and_renderer_consumers(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        wrapper = function_body(builder, "buildVehicleWrapper")
        for block_name, expression, dimensions in (
            ("PTR Control Selector", "s12_v11_model_ptr_controls_step", "[4 1]"),
            ("Renderer Gain Selector", "s12_v11_model_renderer_gain_step", "[1 1]"),
        ):
            self.assertIn(block_name, wrapper)
            self.assertIn(expression, wrapper)
            self.assertIn(dimensions, wrapper)
        self.assertRegex(wrapper, r'add_line\(model,\s*"Vehicle State/1",\s*"PTR Control Selector/1"')
        self.assertRegex(wrapper, r'add_line\(model,\s*"PTR Control Selector/1",\s*"PTR Radiation Model Reference/3"')
        self.assertRegex(wrapper, r'add_line\(model,\s*"Vehicle State/1",\s*"Renderer Gain Selector/1"')
        self.assertRegex(wrapper, r'add_line\(model,\s*"Renderer Gain Selector/1",\s*"Renderer Input Mux/2"')
        self.assertRegex(wrapper, r'add_line\(model,\s*"Renderer Input Mux/1",\s*"Stereo Renderer/1"')
        shared = function_body(builder, "buildSharedCore")
        self.assertIn('"/PTR Controls"', shared)
        self.assertRegex(shared, r"s12_v11_model_ptr_radiation_step\(u\)")

    def test_vehicle_state_and_excitation_are_controlled_not_fixed(self) -> None:
        state = source("s12_v11_model_vehicle_state_step.m")
        self.assertRegex(state, r"function\s+stateVector\s*=\s*s12_v11_model_vehicle_state_step\(controls,\s*profileIndex\)")
        for token in ("profile.vehicle_state", "timelineS", "determineGear", "determineShiftCode", "dfco_throttle_threshold"):
            self.assertIn(token, state)
        self.assertNotRegex(function_body(state, "s12_v11_model_vehicle_state_step"), r"shiftCode\s*=\s*0\s*;")
        excitation = source("s12_v11_model_excitation_afterfire_step.m")
        main = function_body(excitation, "s12_v11_model_excitation_afterfire_step")
        self.assertRegex(main, r"afterfireLevelFromControl\(state\.backfire_level\)")
        self.assertNotIn('"subtle"', main)
        render = function_body(excitation, "renderBaseExcitation")
        for token in ("character.intake_tone", "character.supercharger_tone", "state.order_balance", "state.transient_scale"):
            self.assertIn(token, render)

    def test_ptr_and_renderer_consume_dashboard_controls_without_post_ptr_design(self) -> None:
        ptr = source("s12_v11_model_ptr_radiation_step.m")
        renderer = source("s12_v11_model_stereo_renderer_step.m")
        self.assertRegex(ptr, r"function\s+pressure\s*=\s*s12_v11_model_ptr_radiation_step\(packedInput\)")
        self.assertRegex(ptr, r"s12_sound_playground_ptr_tuning_step\(excitation,[\s.]*ptrControls\(1\),\s*ptrControls\(2\),\s*ptrControls\(3\),\s*ptrControls\(4\)")
        self.assertRegex(renderer, r"function\s+pcm\s*=\s*s12_v11_model_stereo_renderer_step\(packedInput,\s*profileIndex\)")
        self.assertRegex(renderer, r"pcm\s*=\s*gain\s*\*\s*\[")
        combined = "\n".join((ptr, renderer, source("s12_v11_model_excitation_afterfire_step.m"))).lower()
        self.assertNotIn("audiowrite(", combined)
        self.assertNotIn("audioread(", combined)
        self.assertNotIn("hard limiter", combined)

    def test_authored_runtime_suite_covers_each_control_shift_type_and_port_dimension(self) -> None:
        suite = (ROOT / "tests" / "test_s12_engine_sound_v11_simulink_models.m").read_text(encoding="utf-8")
        for control in CONTROLS:
            self.assertIn(control, suite)
        for token in ("upshift", "downshift", "CompiledPortDimensions", "[960 2]", "AllowModelCreation", "SimulationCommand', 'update'"):
            self.assertIn(token, suite)


def source(name: str) -> str:
    return (V11 / name).read_text(encoding="utf-8")


def function_body(text: str, name: str) -> str:
    match = re.search(rf"(?m)^function\b[^\n]*\b{re.escape(name)}\b[^\n]*\n", text)
    if not match:
        return ""
    next_function = re.search(r"(?m)^function\b", text[match.end():])
    end = match.end() + next_function.start() if next_function else len(text)
    return text[match.start():end]


if __name__ == "__main__":
    unittest.main(verbosity=2)
