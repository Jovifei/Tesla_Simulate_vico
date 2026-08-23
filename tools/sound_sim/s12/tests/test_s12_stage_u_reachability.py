from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.real_reference.stage_u_reachability import (
    build_stage_u_candidate,
    dashboard_values_to_source,
    probe_candidate_reachability,
)


ROOT = Path(__file__).resolve().parents[4]
CANDIDATES = ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "targets" / "stage_g_candidates"


def _trace() -> VehicleStateTrace:
    time_s = np.linspace(0.0, 1.0, 48_001)
    rpm = np.linspace(3_200.0, 5_800.0, time_s.size)
    load = np.linspace(0.55, 0.90, time_s.size)
    return VehicleStateTrace(time_s, rpm, load, load, np.gradient(rpm / 60.0, time_s)).validate()


def test_dashboard_abstract_values_map_to_real_source_controls() -> None:
    ferrari = dashboard_values_to_source("ferrari_458", {"metallic_envelope_db": 3.0, "mid_band_balance_db": -3.0, "texture_mix": 0.50})
    hellcat = dashboard_values_to_source("hellcat", {"blower_intake_balance": 0.25, "mid_band_pressure_db": 3.0, "pressure_attack_db": -3.0})
    rx7 = dashboard_values_to_source("rx7_fd", {"housing_peak_db": 3.0, "turbo_band_balance_db": -3.0, "broadband_mix": 0.50})
    assert set(ferrari) == {"metallic_gain_scale", "mid_carrier_gain_scale", "metallic_texture_mix"}
    assert set(hellcat) == {"blower_intake_balance", "intake_gain_scale", "pressure_attack_gain_scale"}
    assert {"housing_gain_scale", "turbo_gain_scale", "turbine_gain_scale", "rotary_amplitude_scale", "housing_order_weight_scale"} <= set(rx7)
    assert ferrari["metallic_gain_scale"] > 1.0
    assert hellcat["intake_gain_scale"] > 1.0
    assert rx7["housing_gain_scale"] > 1.0


def test_stage_u_rx7_candidate_replaces_legacy_pulse_name_with_reachable_controls() -> None:
    candidate, mapping = build_stage_u_candidate(
        CANDIDATES / "RX7_candidate_v4.json",
        "rx7_stage_u_test",
        {"housing_peak_db": 2.0, "turbo_band_balance_db": 1.0, "broadband_mix": 0.60},
    )
    assert "rotary_pulse_width_scale" not in candidate.payload["source"]
    assert "rotary_amplitude_scale" in candidate.payload["source"]
    assert mapping["parameter_group"] == "rotary_housing_turbo_distribution"


def test_reachability_probe_requires_consumption_target_change_and_bounded_non_target() -> None:
    candidate, _ = build_stage_u_candidate(
        CANDIDATES / "Hellcat_candidate_v4.json",
        "hellcat_stage_u_test",
        {"blower_intake_balance": 0.08, "mid_band_pressure_db": 1.0, "pressure_attack_db": 1.0},
    )
    receipt = probe_candidate_reachability(candidate, _trace())
    assert receipt["status"] == "PARAMETER_REACHABILITY_PASS"
    assert receipt["unused"] == []
    assert all(row["target_changed"] and row["direction_ok"] and row["non_target_bounded"] for row in receipt["parameters"])
