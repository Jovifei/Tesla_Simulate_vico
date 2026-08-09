"""Static contracts for the v1.1 20 ms discrete Simulink frame pipeline."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"


class S12EngineSoundV11ModelTimingStaticTests(unittest.TestCase):
    def test_contract_declares_20ms_90s_4500_frame_timing(self) -> None:
        contracts = source("s12_v11_model_contracts.m")
        for token in ('"frame_period_s", 0.02', '"duration_s", 90', '"frame_count", 4500', '"frame_samples", 960'):
            self.assertIn(token, contracts)

    def test_builder_sets_fixed_discrete_model_timing_and_sampled_sources(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        timing = function_body(builder, "configureDiscreteFrameTiming")
        for token in ('"SolverType", "Fixed-step"', '"Solver", "FixedStepDiscrete"', '"FixedStep", "0.02"', '"StopTime", "90"'):
            self.assertIn(token, timing)
        wrapper = function_body(builder, "buildVehicleWrapper")
        self.assertGreaterEqual(builder.count("configureDiscreteFrameTiming("), 2)
        self.assertRegex(wrapper, r'"SampleTime",\s*"0\.02"')
        self.assertIn("Excitation Clock Mux", wrapper)
        self.assertRegex(wrapper, r'"Timeline Clock/1",\s*"Excitation Clock Mux/2"')
        self.assertRegex(wrapper, r'"Excitation Clock Mux/1",\s*"Vehicle Excitation Afterfire/1"')
        dashboard = function_body(builder, "addDashboardControls")
        self.assertRegex(dashboard, r'"SampleTime",\s*"0\.02"')

    def test_model_excitation_consumes_clock_time_and_resets_on_rewind(self) -> None:
        excitation = source("s12_v11_model_excitation_afterfire_step.m")
        self.assertRegex(excitation, r"s12_v11_model_excitation_afterfire_step\(packedInput,\s*vehicleId\)")
        self.assertIn("packedInput(22)", excitation)
        self.assertIn('"timestamp_s", frameTimeS', excitation)
        self.assertIn("frameTimeS < lastFrameTimeS", excitation)
        self.assertIn("frameTimeS <= 0", excitation)
        self.assertNotIn("timelineS = timelineS +", excitation)

    def test_vehicle_shift_state_resets_on_clock_rewind(self) -> None:
        state = source("s12_v11_model_vehicle_state_step.m")
        self.assertIn("timelineS < lastTimestampS", state)
        self.assertIn("timelineS <= 0", state)
        self.assertIn("lastTimestampS = timelineS", state)

    def test_authored_matlab_suite_covers_tick_count_dimensions_and_rewind(self) -> None:
        suite = (ROOT / "tests" / "test_s12_engine_sound_v11_simulink_models.m").read_text(encoding="utf-8")
        for token in ("4500", "0.02", "[960 2]", "testClockRewindResetsPersistentModelState", "SimulationCommand', 'update'"):
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
