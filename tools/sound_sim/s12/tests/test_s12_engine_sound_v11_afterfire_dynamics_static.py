"""RED/GREEN static contracts for state-derived v1.1 afterfire dynamics."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
COMMON = V11 / "common"

AFTERFIRE_PARAMETERS = {
    "upshift_max_throttle_rate_per_s",
    "downshift_min_throttle_rate_per_s",
    "downshift_min_rpm_rate_per_s",
    "overrun_max_throttle_rate_per_s",
    "overrun_max_rpm_rate_per_s",
    "minimum_thermal_eligibility",
    "lift_energy_decay_rate_per_s",
    "lift_refractory_growth_per_s",
}

VEHICLE_STATE_PARAMETERS = {
    "derivative_min_dt_s",
    "thermal_initial_eligibility",
    "thermal_heating_rate_per_s",
    "thermal_cooling_rate_per_s",
    "thermal_load_gain",
    "thermal_rpm_reference_rpm",
}


class S12EngineSoundV11AfterfireDynamicsStaticTests(unittest.TestCase):
    def test_every_profile_owns_dynamic_afterfire_and_thermal_parameters(self) -> None:
        for profile_path in sorted((V11 / "vehicles").glob("*/profile.json")):
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            tuning = payload["render_tuning"]
            self.assertTrue(AFTERFIRE_PARAMETERS <= set(tuning["afterfire"]), profile_path)
            self.assertTrue(VEHICLE_STATE_PARAMETERS <= set(tuning["vehicle_state"]), profile_path)
            for section, fields in (("afterfire", AFTERFIRE_PARAMETERS), ("vehicle_state", VEHICLE_STATE_PARAMETERS)):
                for field in fields:
                    record = tuning[section][field]
                    self.assertEqual(record["source_level"], "C")
                    self.assertEqual(record["source"], "synthetic")
                    self.assertEqual(record["verification_state"], "synthetic_assumption")
                    self.assertEqual(record["source_url"], "")

    def test_scheduler_consumes_derivatives_thermal_and_lift_decay_without_hidden_defaults(self) -> None:
        scheduler = read(COMMON / "s12_v11_schedule_afterfire.m")
        for field in (
            "dthrottle_dt", "drpm_dt", "thermal_eligibility", "lift_start_s",
            "lift_energy_decay_rate_per_s", "lift_refractory_growth_per_s",
        ):
            self.assertIn(field, scheduler)
        self.assertIn("thermalEnergyScale", scheduler)
        self.assertIn("liftEnergyScale", scheduler)
        self.assertIn("liftAdjustedRefractory", scheduler)
        for field in AFTERFIRE_PARAMETERS:
            self.assertIn(f'"{field}"', scheduler)

    def test_cycle_derives_continuous_derivatives_and_thermal_eligibility_from_profile(self) -> None:
        cycle = read(V11 / "s12_v11_compile_vehicle_cycle.m")
        for token in (
            "dthrottle_dt", "drpm_dt", "thermal_eligibility",
            "deriveThermalEligibility", "thermal_initial_eligibility",
            "profile.vehicle_state.derivative_min_dt_s",
        ):
            self.assertIn(token, cycle)
        self.assertNotIn('thermalState = repmat("warm"', cycle)

    def test_cycle_creates_profile_driven_shift_edges_within_accepted_windows(self) -> None:
        cycle = read(V11 / "s12_v11_compile_vehicle_cycle.m")
        for token in (
            "applyProfileDrivenShiftTransients",
            "upshift_max_throttle",
            "downshift_min_throttle",
            "gear_rpm_step",
            "speed_kph_per_rpm",
            "profile.character.maximum_load",
            "upshiftWindowS",
            "downshiftWindowS",
        ):
            self.assertIn(token, cycle)
        self.assertNotIn("rpm = blendTransientTarget(rpm, upshiftPulse", cycle)

    def test_upshift_accepts_either_provenance_owned_negative_derivative_edge(self) -> None:
        scheduler = read(COMMON / "s12_v11_schedule_afterfire.m")
        self.assertIn("state.dthrottle_dt <= config.upshift_max_throttle_rate_per_s ||", scheduler)
        self.assertIn("state.drpm_dt <= config.overrun_max_rpm_rate_per_s", scheduler)

    def test_model_path_transports_clock_derived_state_to_pre_ptr_afterfire(self) -> None:
        contracts = read(V11 / "s12_v11_model_contracts.m")
        state = read(V11 / "s12_v11_model_vehicle_state_step.m")
        excitation = read(V11 / "s12_v11_model_excitation_afterfire_step.m")
        self.assertIn('"vehicle_state_output", "[21,1]"', contracts)
        self.assertIn("[21, 1]", state)
        self.assertIn("dthrottleDt", state)
        self.assertIn("drpmDt", state)
        self.assertIn("thermalEligibility", state)
        self.assertIn("[22, 1]", excitation)
        self.assertIn("values(19)", excitation)
        self.assertIn("values(20)", excitation)
        self.assertIn("values(21)", excitation)
        self.assertIn('"dthrottle_dt"', excitation)
        self.assertIn('"drpm_dt"', excitation)
        self.assertIn('"thermal_eligibility"', excitation)

    def test_authored_behavior_suite_proves_derivative_thermal_and_lift_decay_gates(self) -> None:
        behavior = read(ROOT / "tests" / "test_s12_engine_sound_v11_afterfire.m")
        for name in (
            "testDerivativeEligibilityChangesEventScheduling",
            "testThermalAndLiftDurationReduceRepeatedOverrunEnergyAndRate",
            "testWholeCycleAfterfireEventsStayInApprovedWindows",
            "testThermalEligibilitySeparatelyChangesOverrunEnergyAndRefractory",
            "testUpshiftHoldRetainsRedlineAndHighLoadWhileEmittingEvent",
            "testUpshiftAllowsEitherValidatedNegativeDerivativeEdge",
            "testIdleAndCruiseRemainEventFreeWithDynamicState",
            "testModelStateProvidesDerivativeAndThermalSlots",
        ):
            self.assertIn(name, behavior)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


if __name__ == "__main__":
    unittest.main(verbosity=2)
