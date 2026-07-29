"""Offline contracts for v1.1 stateful afterfire scheduling."""

from __future__ import annotations

import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
COMMON = V11 / "common"


class S12EngineSoundV11AfterfireStatefulStaticTests(unittest.TestCase):
    def test_whole_cycle_scheduler_declares_refractory_state(self) -> None:
        scheduler = read(COMMON / "s12_v11_schedule_afterfire.m")
        compiler = COMMON / "s12_v11_compile_afterfire_schedule.m"
        self.assertTrue(compiler.is_file())
        self.assertIn("schedulerState", scheduler)
        self.assertIn("function [events, diagnostics, schedulerState]", scheduler)
        self.assertIn("cluster_refractory_s", scheduler)
        self.assertIn("refractory_jitter_fraction", scheduler)
        self.assertIn("requireProfileAfterfireFields", scheduler)
        self.assertIn("requiredAfterfireFields", scheduler)
        self.assertIn("config = struct();", scheduler)
        self.assertNotIn('"base_energy", 0.16', scheduler)
        self.assertNotIn('"idle_rpm_ceiling", 1200', scheduler)
        for field in (
            "idle_rpm_ceiling", "minimum_event_rpm", "upshift_max_throttle",
            "downshift_min_throttle", "overrun_max_throttle",
            "overrun_max_acceleration", "minimum_shift_load",
            "steady_acceleration_limit", "cruise_min_throttle",
            "cruise_max_throttle", "base_energy", "onset_delay_s",
            "cluster_interval_s", "cluster_refractory_s",
            "refractory_jitter_fraction", "interval_jitter_fraction",
            "cluster_energy_decay",
        ):
            self.assertIn(f'"{field}"', scheduler)
        self.assertIn("next_cluster_not_before_s", scheduler)
        self.assertIn("last_cluster_start_s", scheduler)
        self.assertIn("timestamp_s must be monotonic", scheduler)
        self.assertIn("s12_v11_schedule_afterfire", compiler.read_text(encoding="utf-8"))

    def test_renderer_compiles_schedule_once_not_per_frame(self) -> None:
        renderer = read(V11 / "s12_v11_render_profile.m")
        self.assertIn("s12_v11_compile_afterfire_schedule", renderer)
        self.assertNotIn("s12_v11_schedule_afterfire(state", renderer)
        self.assertNotIn('"|frame-" + string(frameIndex)', renderer)

    def test_model_helper_has_continuous_persistent_timeline(self) -> None:
        helper = read(V11 / "s12_v11_model_excitation_afterfire_step.m")
        self.assertIn("persistent context lastVehicleId schedulerState lastFrameTimeS activeEvents", helper)
        self.assertIn("activeEvents", helper)
        self.assertIn("selectEventsForPressureFrame", helper)
        self.assertIn("keepFutureTails", helper)
        self.assertIn('"timestamp_s", frameTimeS', helper)
        self.assertIn("frameTimeS < lastFrameTimeS", helper)
        self.assertIn("frameTimeS <= 0", helper)
        self.assertNotIn('"timestamp_s", 0', helper)

    def test_matlab_behavior_test_reconstructs_long_dfco_cycle(self) -> None:
        behavior = read(ROOT / "tests" / "test_s12_engine_sound_v11_afterfire.m")
        self.assertIn("testLongDfcoScheduleIsRefractoryAndDeterministic", behavior)
        self.assertIn("s12_v11_compile_afterfire_schedule", behavior)
        self.assertIn("63", behavior)
        self.assertIn("66", behavior)
        self.assertIn("cluster_refractory_s", behavior)
        self.assertIn("testEveryAfterfireProfileFieldIsRequiredAndFinite", behavior)

    def test_shift_kinds_require_transition_edges_while_overrun_can_recur(self) -> None:
        scheduler = read(COMMON / "s12_v11_schedule_afterfire.m")
        behavior = read(ROOT / "tests" / "test_s12_engine_sound_v11_afterfire.m")
        self.assertIn('kind == "overrun_crackle"', scheduler)
        self.assertIn("shouldStartCluster = eligible && transitioned", scheduler)
        self.assertIn("testShiftClustersRequireEdges", behavior)
        self.assertIn("testLongDfcoScheduleIsRefractoryAndDeterministic", behavior)
        self.assertIn("unique(string({longDfcoEvents.cluster_id}))", behavior)
        self.assertIn("max(intervals) - min(intervals)", behavior)

    def test_all_loaded_packages_supply_both_stateful_refractory_parameters(self) -> None:
        schema = read(COMMON / "schemas" / "vehicle_package.schema.json")
        validator = read(COMMON / "s12_v11_validate_vehicle_package.m")
        loader = read(V11 / "s12_v11_load_profile.m")
        self.assertIn("refractory_jitter_fraction", schema)
        self.assertIn("validateRenderTuning", validator)
        self.assertIn("tuning.afterfire = unwrapSection(renderTuning.afterfire)", loader)
        for profile_path in sorted((V11 / "vehicles").glob("*/profile.json")):
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            afterfire = payload["render_tuning"]["afterfire"]
            for field in ("cluster_refractory_s", "refractory_jitter_fraction"):
                record = afterfire[field]
                self.assertEqual(record["source_level"], "C")
                self.assertEqual(record["source"], "synthetic")
                self.assertEqual(record["verification_state"], "synthetic_assumption")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


if __name__ == "__main__":
    unittest.main(verbosity=2)
