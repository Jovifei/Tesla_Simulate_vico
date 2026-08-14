"""Round-2 v9 candidate and source-domain contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import (
    load_stage_l_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import (
    build_hellcat_crank_clock,
)
from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_crossplane_combustion_v2 import (
    render_hellcat_crossplane_combustion_v2,
)
from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_supercharger_intake_v5 import (
    render_hellcat_supercharger_intake_v5,
)


ROOT = Path(__file__).resolve().parents[1]
V8_PATH = ROOT / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
V9_PATH = ROOT / "targets" / "stage_l_candidates" / "hellcat_candidate_v9.json"
SC_V9_PARAMETERS = {
    "combustion_ripple_to_aero_depth",
    "high_load_whine_knee",
    "high_load_whine_post_knee_slope",
}
HEMI_V9_PARAMETERS = {
    "acceleration_blowdown_body_gain",
    "low_frequency_blowdown_gain",
    "structure_shock_mix",
    "torque_ripple_modulation_depth",
}
AFTERFIRE_V9_PARAMETERS = {
    "minimum_rpm",
    "residual_energy_gain",
    "event_energy_threshold",
    "body_mix",
    "bright_mix",
    "decay_90_10_s",
}
SC_V8 = {
    "aero_family_order_ratio": 5.0,
    "aero_harmonic_mix": 0.24,
    "aero_cluster_spread_ratio": 0.018,
    "gear_family_order_ratio": 10.0,
    "gear_to_aero_ratio": 0.10,
    "torque_ripple_to_gear_depth": 0.10,
    "intake_transfer_mix": 0.36,
    "casing_transfer_mix": 0.14,
    "boost_attack_10_90_s": 0.075,
    "boost_release_90_10_s": 0.24,
    "bypass_release_gain": 0.10,
    "bypass_decay_90_10_s": 0.16,
}
HEMI_V8 = {
    "cylinder_strength_variation": 0.16,
    "bank_amplitude_asymmetry": 0.05,
    "blowdown_attack_ms": 0.45,
    "blowdown_fast_decay_ms": 2.0,
    "blowdown_slow_decay_ms": 6.5,
    "blowdown_slow_weight": 0.28,
    "low_frequency_blowdown_gain": 1.12,
    "structure_shock_mix": 0.10,
    "torque_ripple_modulation_depth": 0.11,
    "xpipe_cross_coupling": 0.14,
    "xpipe_delay_ms": 0.65,
}


def _trace(load: np.ndarray, throttle: np.ndarray, *, sample_rate_hz: int = 8_000) -> VehicleStateTrace:
    count = load.size
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    return VehicleStateTrace(
        time_s=time_s,
        rpm=np.full(count, 2_400.0),
        load=load,
        throttle=throttle,
        acceleration_mps2=np.zeros(count),
    ).validate()


def test_v9_schema_is_separate_and_exposes_exact_round2_public_parameters() -> None:
    v8_bytes = V8_PATH.read_bytes()
    candidate = load_stage_l_candidate(V9_PATH)

    assert V8_PATH.read_bytes() == v8_bytes
    assert candidate.payload["schema_version"] == "s12-stage-l-hellcat-candidate-profile-2"
    assert candidate.candidate_id == "hellcat_stage_l_v9"
    assert set(candidate.payload["supercharger_intake"]) == SC_V9_PARAMETERS
    assert set(candidate.payload["combustion_and_blowdown"]) == HEMI_V9_PARAMETERS
    assert set(candidate.payload["afterfire"]) == AFTERFIRE_V9_PARAMETERS
    receipt = candidate.payload["round2_feedback_receipt"]
    assert receipt["human_pass"] is False
    assert receipt["csv_content_read"] is False


def test_sc_v6_is_v5_below_knee_and_modulates_then_attenuates_whine_above_knee() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_supercharger_intake_v6 import (
        render_hellcat_supercharger_intake_v6,
    )

    candidate = load_stage_l_candidate(V9_PATH)
    count = 8_001
    load = np.r_[np.full(count // 2, 0.15), np.full(count - count // 2, 0.92)]
    throttle = load.copy()
    trace = _trace(load, throttle)
    clock = build_hellcat_crank_clock(trace, 8_000)
    rendered = render_hellcat_supercharger_intake_v6(
        trace.rpm, trace.load, trace.throttle, clock, 8_000,
        {name: candidate.parameter("supercharger_intake", name) for name in SC_V9_PARAMETERS},
    )
    baseline = render_hellcat_supercharger_intake_v5(
        trace.rpm, trace.load, trace.throttle, clock, 8_000, SC_V8
    )

    assert rendered.diagnostics["below_knee_v5_byte_identical"] is True
    assert rendered.diagnostics["shared_clock_torque_ripple_modulation"] is True
    assert rendered.diagnostics["monotonic_high_load_whine_attenuation"] is True
    assert abs(rendered.diagnostics["torque_ripple_zero_mean"]) < 1.0e-12
    assert np.isclose(rendered.diagnostics["torque_ripple_unit_rms"], 1.0)
    assert rendered.diagnostics["random_source"] is False
    assert rendered.diagnostics["fixed_hz_oscillator"] is False
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert set(usage["requested"]) == SC_V9_PARAMETERS
    assert set(usage["read"]) == SC_V9_PARAMETERS
    assert set(usage["configured"]) == SC_V9_PARAMETERS
    assert not usage["unused"]
    split = count // 2
    for name in baseline.stems:
        np.testing.assert_array_equal(rendered.stems[name][:split], baseline.stems[name][:split])
    for name in ("sc_gear_raw", "sc_casing_radiated", "sc_bypass_release"):
        np.testing.assert_array_equal(rendered.stems[name], baseline.stems[name])
    assert np.sqrt(np.mean(rendered.stems["sc_intake_radiated"][split:] ** 2)) < np.sqrt(
        np.mean(baseline.stems["sc_intake_radiated"][split:] ** 2)
    )
    assert not any("exhaust" in name for name in rendered.stems)


def test_crossplane_v3_preserves_low_load_v8_bytes_and_rebuilds_accounting() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_crossplane_combustion_v3 import (
        render_hellcat_crossplane_combustion_v3,
    )

    candidate = load_stage_l_candidate(V9_PATH)
    count = 8_001
    trace = _trace(np.full(count, 0.10), np.full(count, 0.12))
    clock = build_hellcat_crank_clock(trace, 8_000)
    rendered = render_hellcat_crossplane_combustion_v3(
        trace.rpm, trace.load, trace.throttle, clock, 8_000,
        {name: candidate.parameter("combustion_and_blowdown", name) for name in HEMI_V9_PARAMETERS},
    )
    baseline = render_hellcat_crossplane_combustion_v2(
        trace.rpm, trace.load, trace.throttle, clock, 8_000, HEMI_V8
    )

    assert rendered.diagnostics["v8_baseline_byte_identical"] is True
    np.testing.assert_array_equal(rendered.pressure, baseline.pressure)
    assert set(rendered.stems) == set(baseline.stems)
    for name in baseline.stems:
        np.testing.assert_array_equal(rendered.stems[name], baseline.stems[name])
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert set(usage["requested"]) == HEMI_V9_PARAMETERS
    assert set(usage["read"]) == HEMI_V9_PARAMETERS
    assert set(usage["configured"]) == HEMI_V9_PARAMETERS
    assert not usage["active"]
    assert set(usage["inactive"]) == HEMI_V9_PARAMETERS
    assert not usage["unused"]
    contract = rendered.diagnostics["pressure_stem_contract"]
    expected = sum(
        (rendered.stems[name] for name in contract["contributors"]),
        np.zeros_like(rendered.pressure),
    )
    np.testing.assert_array_equal(rendered.pressure, expected)
    np.testing.assert_array_equal(
        rendered.stems["hemi_combustion_and_blowdown"], rendered.pressure
    )
    np.testing.assert_array_equal(
        rendered.stems["hemi_exhaust"],
        rendered.stems["hemi_exhaust_left"] + rendered.stems["hemi_exhaust_right"],
    )

    high_trace = _trace(np.full(count, 0.95), np.full(count, 0.96))
    high_clock = build_hellcat_crank_clock(high_trace, 8_000)
    high = render_hellcat_crossplane_combustion_v3(
        high_trace.rpm, high_trace.load, high_trace.throttle, high_clock, 8_000,
        {name: candidate.parameter("combustion_and_blowdown", name) for name in HEMI_V9_PARAMETERS},
    )
    high_baseline = render_hellcat_crossplane_combustion_v2(
        high_trace.rpm, high_trace.load, high_trace.throttle, high_clock, 8_000, HEMI_V8
    )
    for name in ("hemi_exhaust_left", "hemi_exhaust_right", "hemi_exhaust"):
        np.testing.assert_array_equal(high.stems[name], high_baseline.stems[name])
    for name in (
        "hemi_blowdown_body",
        "hemi_structure_shock",
        "hemi_mechanical_torque_ripple",
    ):
        assert not np.array_equal(high.stems[name], high_baseline.stems[name])
    high_usage = high.diagnostics["candidate_parameter_usage"]
    assert set(high_usage["active"]) == HEMI_V9_PARAMETERS
    assert not high_usage["inactive"]
