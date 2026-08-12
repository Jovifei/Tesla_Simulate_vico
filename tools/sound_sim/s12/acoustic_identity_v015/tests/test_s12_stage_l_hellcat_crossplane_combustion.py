"""Stage-L L2 cross-plane HEMI combustion and blowdown contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import (
    _apply_frozen_ptr,
    _edge_fade,
    _pcm24_roundtrip,
)
from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_crossplane_combustion_v2 import (
    render_hellcat_crossplane_combustion_v2,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import (
    HELLCAT_BANK_PATTERN,
    HELLCAT_FIRING_ORDER,
    build_hellcat_crank_clock,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import (
    load_stage_l_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
    render_stage_l_candidate,
    render_stage_l_parent,
)


_SR = 12_000
_DEFAULTS = {
    "cylinder_strength_variation": 0.13,
    "bank_amplitude_asymmetry": 0.06,
    "blowdown_attack_ms": 0.45,
    "blowdown_fast_decay_ms": 2.0,
    "blowdown_slow_decay_ms": 7.0,
    "blowdown_slow_weight": 0.30,
    "low_frequency_blowdown_gain": 1.15,
    "structure_shock_mix": 0.10,
    "torque_ripple_modulation_depth": 0.12,
    "xpipe_cross_coupling": 0.14,
    "xpipe_delay_ms": 0.65,
}
_CONTRIBUTORS = (
    "hemi_exhaust_left",
    "hemi_exhaust_right",
    "hemi_blowdown_body",
    "hemi_structure_shock",
    "hemi_mechanical_torque_ripple",
)


def _trace(
    rpm_start: float = 1_200.0,
    rpm_end: float | None = None,
    duration_s: float = 0.75,
    load: float = 0.9,
    throttle: float = 0.92,
) -> VehicleStateTrace:
    count = int(round(duration_s * _SR)) + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    rpm = np.linspace(rpm_start, rpm_start if rpm_end is None else rpm_end, count)
    return VehicleStateTrace(
        time_s,
        rpm,
        np.full(count, load, dtype=np.float64),
        np.full(count, throttle, dtype=np.float64),
        np.gradient(rpm / 60.0, time_s),
    ).validate()


def _render(
    overrides: dict[str, float] | None = None,
    *,
    trace: VehicleStateTrace | None = None,
):
    trace = _trace() if trace is None else trace
    clock = build_hellcat_crank_clock(trace, _SR)
    values = dict(_DEFAULTS)
    if overrides:
        values.update(overrides)
    return render_hellcat_crossplane_combustion_v2(
        trace.rpm, trace.load, trace.throttle, clock, _SR, values
    ), clock


def _mono(value: np.ndarray) -> np.ndarray:
    return np.mean(np.asarray(value, dtype=np.float64), axis=1)


def _dominant_hz(value: np.ndarray) -> float:
    mono = _mono(value)
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / _SR)
    spectrum[frequencies < 20.0] = 0.0
    return float(frequencies[int(np.argmax(spectrum))])


def _sha(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _band_shares(value: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    mono = _mono(value)
    power = np.square(np.abs(np.fft.rfft(mono * np.hanning(mono.size))))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    bands = ((20.0, 250.0), (250.0, 1_000.0), (1_000.0, 4_000.0), (4_000.0, 12_000.0))
    energy = np.asarray([
        np.sum(power[(frequencies >= low) & (frequencies < high)]) for low, high in bands
    ])
    return energy / max(float(np.sum(energy)), 1.0e-30)


def _band_rms(value: np.ndarray, low_hz: float, high_hz: float, sample_rate_hz: int) -> float:
    mono = _mono(value)
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size))) ** 2
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    return float(np.sqrt(np.mean(spectrum[(frequencies >= low_hz) & (frequencies < high_hz)])))


def _crest(value: np.ndarray) -> float:
    mono = _mono(value)
    return float(np.max(np.abs(mono)) / np.sqrt(np.mean(np.square(mono))))


def _band_crest(value: np.ndarray, low_hz: float, high_hz: float, sample_rate_hz: int) -> float:
    mono = _mono(value)
    spectrum = np.fft.rfft(mono)
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    spectrum[(frequencies < low_hz) | (frequencies >= high_hz)] = 0.0
    band_limited = np.fft.irfft(spectrum, n=mono.size)
    trim = max(1, int(round(0.10 * sample_rate_hz)))
    band_limited = band_limited[trim:-trim]
    return float(np.max(np.abs(band_limited)) / np.sqrt(np.mean(np.square(band_limited))))


def test_l2_consumes_the_exact_shared_clock_and_preserves_crossplane_event_geometry() -> None:
    rendered, clock = _render()
    diagnostics = rendered.diagnostics
    assert diagnostics["clock_object_id"] == id(clock)
    assert tuple(diagnostics["event_sample_indices"]) == clock.event_sample_indices
    assert tuple(diagnostics["bank_labels"]) == clock.bank_labels
    assert tuple(diagnostics["firing_order"]) == HELLCAT_FIRING_ORDER
    assert tuple(clock.bank_labels[:8]) == HELLCAT_BANK_PATTERN
    assert diagnostics["event_phase_max_error_samples"] <= 1.0
    assert diagnostics["merged_firing_order"] == "uniform_4EO"
    assert diagnostics["bank_interval_ratio_multisets"] == {
        "left": (1, 2, 2, 3),
        "right": (1, 2, 2, 3),
    }
    expected_hz = 4.0 * 1_200.0 / 60.0
    assert _dominant_hz(rendered.stems["hemi_blowdown_body"]) == pytest.approx(expected_hz, abs=2.0)


def test_variable_rpm_moves_event_rate_without_losing_clock_events_or_firing_order() -> None:
    trace = _trace(900.0, 3_600.0, duration_s=0.8)
    rendered, clock = _render(trace=trace)
    assert tuple(rendered.diagnostics["event_sample_indices"]) == clock.event_sample_indices
    assert tuple(rendered.diagnostics["bank_labels"]) == clock.bank_labels
    assert rendered.diagnostics["event_count"] == len(clock.event_sample_indices)
    assert tuple(rendered.diagnostics["cylinder_sequence"][:8]) == HELLCAT_FIRING_ORDER
    intervals = np.diff(np.asarray(clock.event_sample_indices, dtype=np.int64))
    third = max(2, intervals.size // 3)
    assert np.median(intervals[:third]) > np.median(intervals[-third:])


def test_cylinder_strength_pattern_is_equal_at_zero_and_bounded_deterministic_when_enabled() -> None:
    equal, _ = _render({"cylinder_strength_variation": 0.0})
    first, _ = _render({"cylinder_strength_variation": 0.13})
    second, _ = _render({"cylinder_strength_variation": 0.13})
    equal_pattern = np.asarray(equal.diagnostics["cylinder_strength_pattern"])
    varied_pattern = np.asarray(first.diagnostics["cylinder_strength_pattern"])
    np.testing.assert_array_equal(equal_pattern, np.ones(8))
    assert np.ptp(varied_pattern) > 0.0
    assert np.min(varied_pattern) >= 0.87
    assert np.max(varied_pattern) <= 1.13
    assert _sha(first.pressure) == _sha(second.pressure)


def test_cylinder_strength_pattern_groups_strong_then_weak_events_with_unit_mean() -> None:
    rendered, _ = _render({"cylinder_strength_variation": 0.13})
    pattern = np.asarray(rendered.diagnostics["cylinder_strength_pattern"], dtype=np.float64)
    strengths = np.asarray(rendered.diagnostics["event_strengths"], dtype=np.float64)

    assert pattern.shape == (8,)
    assert np.mean(pattern) == pytest.approx(1.0, abs=1.0e-15)
    assert np.all(pattern[:4] > 1.0)
    assert np.all(pattern[4:] < 1.0)
    np.testing.assert_array_equal(strengths[:8], pattern)
    np.testing.assert_array_equal(strengths[8:16], pattern)
    assert rendered.diagnostics["cylinder_strength_grouping"] == "four_strong_four_weak"


def test_combustion_pressure_scale_is_named_c_level_source_structure_not_loudness_gain() -> None:
    rendered, _ = _render()
    evidence = rendered.diagnostics["combustion_pressure_structural_scale"]
    assert evidence == {
        "name": "combustion_pressure_structural_scale",
        "value": 0.75,
        "source_level": "C",
        "source": "synthetic",
        "verification_state": "fixed_source_structure",
        "whole_cycle_gain": False,
    }


@pytest.mark.parametrize(
    "parameter",
    ("low_frequency_blowdown_gain", "blowdown_attack_ms", "xpipe_delay_ms"),
)
def test_parameter_effect_energy_equals_explicit_reference_output_delta(parameter: str) -> None:
    baseline, _ = _render()
    references = baseline.diagnostics["parameter_effect_reference_values"]
    changed, _ = _render({parameter: references[parameter]})
    affected = baseline.diagnostics["parameter_affected_stems"][parameter]
    explicit_energy = sum(
        float(np.sum(np.square(baseline.stems[name] - changed.stems[name])))
        for name in affected
    )
    assert baseline.diagnostics["parameter_effect_energy"][parameter] == pytest.approx(
        explicit_energy, rel=1.0e-10, abs=1.0e-20
    )


def test_parameter_at_reference_is_inactive_even_when_its_stem_is_nonzero() -> None:
    rendered, _ = _render({"bank_amplitude_asymmetry": 0.0})
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert np.any(rendered.stems["hemi_exhaust_left"] != 0.0)
    assert rendered.diagnostics["parameter_effect_energy"]["bank_amplitude_asymmetry"] == 0.0
    assert "bank_amplitude_asymmetry" in usage["inactive"]
    assert "bank_amplitude_asymmetry" not in usage["active"]


def test_cylinder_strength_is_stable_across_python_hash_seeds() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    script = """
import hashlib
import numpy as np
from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import build_hellcat_crank_clock
from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_crossplane_combustion_v2 import render_hellcat_crossplane_combustion_v2
sr=12000; n=6001; t=np.arange(n,dtype=np.float64)/sr; rpm=np.full(n,1200.0)
trace=VehicleStateTrace(t,rpm,np.full(n,.9),np.full(n,.92),np.zeros(n)).validate()
clock=build_hellcat_crank_clock(trace,sr)
o=%r
r=render_hellcat_crossplane_combustion_v2(rpm,trace.load,trace.throttle,clock,sr,o)
print(hashlib.sha256(np.ascontiguousarray(r.pressure).tobytes()).hexdigest())
""" % _DEFAULTS
    hashes = []
    for seed in ("1", "777"):
        environment = dict(__import__("os").environ, PYTHONHASHSEED=seed)
        hashes.append(subprocess.check_output(
            [sys.executable, "-c", script], cwd=repo_root, env=environment, text=True
        ).strip())
    assert hashes[0] == hashes[1]


@pytest.mark.parametrize(
    ("parameter", "value", "diagnostic"),
    (
        ("blowdown_attack_ms", 0.75, "measured_attack_samples"),
        ("blowdown_fast_decay_ms", 2.8, "measured_fast_decay_samples"),
        ("blowdown_slow_decay_ms", 9.5, "measured_slow_decay_samples"),
        ("blowdown_slow_weight", 0.44, "slow_tail_energy_ratio"),
    ),
)
def test_each_blowdown_kernel_control_changes_its_measured_shape(
    parameter: str, value: float, diagnostic: str
) -> None:
    baseline, _ = _render()
    changed, _ = _render({parameter: value})
    assert changed.diagnostics[diagnostic] != baseline.diagnostics[diagnostic]
    assert not np.array_equal(
        changed.stems["hemi_blowdown_body"], baseline.stems["hemi_blowdown_body"]
    )
    assert changed.diagnostics["excitation_model"] == "event_driven_pressure_pulses"
    assert changed.diagnostics["static_low_shelf_used"] is False


@pytest.mark.parametrize(
    ("parameter", "value", "changed_stems"),
    (
        ("bank_amplitude_asymmetry", 0.11, {"hemi_exhaust_left", "hemi_exhaust_right"}),
        ("low_frequency_blowdown_gain", 1.34, {"hemi_blowdown_body"}),
        ("structure_shock_mix", 0.17, {"hemi_structure_shock"}),
        ("torque_ripple_modulation_depth", 0.19, {"hemi_mechanical_torque_ripple"}),
        ("xpipe_cross_coupling", 0.24, {"hemi_exhaust_left", "hemi_exhaust_right"}),
        ("xpipe_delay_ms", 1.45, {"hemi_exhaust_left", "hemi_exhaust_right"}),
    ),
)
def test_parameter_perturbations_are_reachable_without_changing_non_target_stems(
    parameter: str, value: float, changed_stems: set[str]
) -> None:
    baseline, _ = _render()
    changed, _ = _render({parameter: value})
    for name in _CONTRIBUTORS:
        if name in changed_stems:
            assert not np.array_equal(changed.stems[name], baseline.stems[name]), (parameter, name)
        else:
            np.testing.assert_array_equal(changed.stems[name], baseline.stems[name])
    usage = changed.diagnostics["candidate_parameter_usage"]
    assert parameter in usage["read"]
    assert parameter in usage["configured"]
    assert parameter in usage["active"]
    assert parameter not in usage["inactive"]
    assert parameter not in usage["unused"]


def test_named_primitives_sum_exactly_to_pressure_and_aggregates_are_diagnostic_only() -> None:
    rendered, _ = _render()
    contract = rendered.diagnostics["pressure_stem_contract"]
    assert tuple(contract["contributors"]) == _CONTRIBUTORS
    assert set(contract["contributors"]).isdisjoint(contract["diagnostic_aggregates"])
    expected = sum((rendered.stems[name] for name in _CONTRIBUTORS), np.zeros_like(rendered.pressure))
    np.testing.assert_allclose(rendered.pressure, expected, rtol=0.0, atol=1.0e-12)
    np.testing.assert_allclose(
        rendered.stems["hemi_exhaust"],
        rendered.stems["hemi_exhaust_left"] + rendered.stems["hemi_exhaust_right"],
        rtol=0.0,
        atol=1.0e-12,
    )


def test_stage_l_candidate_replaces_legacy_hemi_with_l2_and_keeps_one_shaping_pass() -> None:
    sample_rate_hz = 48_000
    count = sample_rate_hz + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    trace = VehicleStateTrace(
        time_s,
        np.linspace(1_500.0, 3_300.0, count),
        np.full(count, 0.92),
        np.full(count, 0.95),
        np.full(count, 2.0),
    ).validate()
    package_root = Path(__file__).resolve().parents[1]
    candidate = load_stage_l_candidate(
        package_root / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
    )
    rendered = render_stage_l_candidate(trace, candidate)
    contract = rendered.diagnostics["pressure_stem_contract"]
    assert set(_CONTRIBUTORS) <= set(contract["contributors"])
    assert "exhaust_left_bank" not in contract["contributors"]
    assert "exhaust_right_bank" not in contract["contributors"]
    assert rendered.diagnostics["stage_l_l2_event_consumption"] == "ACTIVE"
    evidence = rendered.diagnostics["shared_clock_consumers"]["cross_plane_combustion_l2"]
    assert evidence["event_gates_consumed"] is True
    assert evidence["event_sample_indices_consumed"] is True
    assert evidence["bank_labels_consumed"] is True
    assert evidence["internal_event_scheduling"] == "ACTIVE_L2_SHARED_CLOCK"
    usage = rendered.diagnostics["candidate_parameter_usage"]
    combustion_names = {
        f"combustion_and_blowdown.{name}" for name in _DEFAULTS
    }
    assert combustion_names <= set(usage["read"])
    assert combustion_names <= set(usage["configured"])
    assert combustion_names <= set(usage["active"])
    assert combustion_names.isdisjoint(usage["unused"])
    expected = sum(
        (rendered.stems[name] for name in contract["contributors"]),
        np.zeros_like(rendered.pressure),
    )
    np.testing.assert_allclose(rendered.pressure, expected, rtol=0.0, atol=1.0e-12)


def test_l2_low_frequency_body_does_not_create_a_high_frequency_repair() -> None:
    baseline, _ = _render({"low_frequency_blowdown_gain": 0.95})
    strengthened, _ = _render({"low_frequency_blowdown_gain": 1.35})
    before = _band_shares(baseline.pressure, _SR)
    after = _band_shares(strengthened.pressure, _SR)
    assert after[0] > before[0]
    assert after[3] <= before[3] + 0.005
    body_shares = _band_shares(strengthened.stems["hemi_blowdown_body"], _SR)
    assert body_shares[0] + body_shares[1] > 0.90
    assert strengthened.diagnostics["resonance_model"] == "broad_event_kernel_no_high_q_peak"


def test_high_load_l2_has_more_80_250_hz_pulse_rms_and_crest_than_stage_k_parent() -> None:
    sample_rate_hz = 48_000
    count = sample_rate_hz + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    trace = VehicleStateTrace(
        time_s,
        np.linspace(1_500.0, 3_300.0, count),
        np.full(count, 0.92),
        np.full(count, 0.95),
        np.full(count, 2.0),
    ).validate()
    package_root = Path(__file__).resolve().parents[1]
    candidate = load_stage_l_candidate(
        package_root / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
    )
    parent = render_stage_l_parent(trace)
    l2 = render_stage_l_candidate(trace, candidate)
    assert "hemi_blowdown_body" not in parent.stems
    pulse = l2.stems["hemi_blowdown_body"]
    assert _band_rms(pulse, 80.0, 250.0, sample_rate_hz) > 0.0
    assert _band_crest(pulse, 80.0, 250.0, sample_rate_hz) > 1.0
    parent_pcm = _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(parent.pressure)))
    l2_pcm = _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(l2.pressure)))
    parent_shares = _band_shares(parent_pcm, sample_rate_hz)
    l2_shares = _band_shares(l2_pcm, sample_rate_hz)
    target = np.asarray(json.loads(
        (package_root / "reference_database" / "hellcat_reference_targets.json").read_text()
    )["stock_median"]["acceleration_band_shares"])
    assert abs(l2_shares[0] - target[0]) <= abs(parent_shares[0] - target[0])
    assert l2_shares[3] <= parent_shares[3] + 0.005


def test_unknown_or_missing_override_is_rejected_instead_of_silently_unused() -> None:
    trace = _trace()
    clock = build_hellcat_crank_clock(trace, _SR)
    with pytest.raises(ValueError, match="override"):
        render_hellcat_crossplane_combustion_v2(
            trace.rpm, trace.load, trace.throttle, clock, _SR, {"unknown": 1.0}
        )
    missing = dict(_DEFAULTS)
    missing.pop("xpipe_delay_ms")
    with pytest.raises(ValueError, match="override"):
        render_hellcat_crossplane_combustion_v2(
            trace.rpm, trace.load, trace.throttle, clock, _SR, missing
        )


def test_bank_local_response_precedes_xpipe_and_has_bounded_distinct_group_delay() -> None:
    rendered, _ = _render()
    diagnostic = rendered.diagnostics["bank_local_response"]
    assert diagnostic["topology"] == "bank_local_response_then_coherent_xpipe_mix"
    assert diagnostic["source_level"] == "C/synthetic"
    assert 0 <= diagnostic["left_group_delay_samples"] < diagnostic["right_group_delay_samples"] <= int(0.50e-3 * _SR)
    assert diagnostic["local_paths_distinct"] is True
    assert diagnostic["xpipe_cross_energy"] > 0.0
    assert diagnostic["xpipe_mix_coherent"] is True


def test_decay_diagnostics_separate_requested_settings_from_measured_envelopes() -> None:
    rendered, _ = _render()
    diagnostic = rendered.diagnostics
    assert diagnostic["requested_fast_decay_ms"] == pytest.approx(_DEFAULTS["blowdown_fast_decay_ms"])
    assert diagnostic["requested_slow_decay_ms"] == pytest.approx(_DEFAULTS["blowdown_slow_decay_ms"])
    assert diagnostic["measured_fast_decay_ms"] > 0.0
    assert diagnostic["measured_slow_decay_ms"] > diagnostic["measured_fast_decay_ms"]
    assert diagnostic["measured_fast_decay_ms"] != diagnostic["requested_fast_decay_ms"]
    assert diagnostic["measured_slow_decay_ms"] != diagnostic["requested_slow_decay_ms"]


def test_usage_is_measured_and_zero_mix_is_inactive_not_declaratively_active() -> None:
    rendered, _ = _render({"structure_shock_mix": 0.0})
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert "structure_shock_mix" in usage["read"]
    assert "structure_shock_mix" in usage["configured"]
    assert "structure_shock_mix" in usage["inactive"]
    assert "structure_shock_mix" not in usage["active"]
    assert rendered.diagnostics["parameter_effect_energy"]["structure_shock_mix"] == 0.0


@pytest.mark.parametrize(
    ("parameter", "value", "affected"),
    (
        ("blowdown_attack_ms", 0.75, {"hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body"}),
        ("blowdown_fast_decay_ms", 2.8, {"hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body"}),
        ("blowdown_slow_decay_ms", 9.5, {"hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body"}),
        ("blowdown_slow_weight", 0.44, {"hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body"}),
    ),
)
def test_blowdown_controls_publish_exact_affected_stems_and_preserve_unrelated_paths(
    parameter: str, value: float, affected: set[str]
) -> None:
    baseline, _ = _render()
    changed, _ = _render({parameter: value})
    assert set(changed.diagnostics["parameter_affected_stems"][parameter]) == affected
    for name in _CONTRIBUTORS:
        if name in affected:
            assert not np.array_equal(changed.stems[name], baseline.stems[name])
        else:
            np.testing.assert_array_equal(changed.stems[name], baseline.stems[name])


def test_full_frozen_downstream_pcm_probe_improves_parent_low_and_mid_reference_errors() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module

    probe = getattr(module, "render_stage_l_final_pcm_probe", None)
    assert callable(probe)
    sample_rate_hz = 48_000
    count = sample_rate_hz + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    trace = VehicleStateTrace(
        time_s, np.linspace(1_500.0, 3_300.0, count), np.full(count, 0.92),
        np.full(count, 0.95), np.full(count, 2.0),
    ).validate()
    package_root = Path(__file__).resolve().parents[1]
    candidate = load_stage_l_candidate(package_root / "targets/stage_l_candidates/hellcat_candidate_v8.json")
    evidence = probe(trace, candidate)
    assert evidence["pipeline_order"] == (
        "source_operating_trim", "idle_dynamics", "deterministic_afterfire",
        "frozen_common_low_frequency_body", "frozen_exhaust_rumble",
        "l4_transient_pending_pass_through", "frozen_common_pre_ptr_equalization",
        "frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24",
    )
    assert evidence["l4_transient_status"] == "PENDING_PASS_THROUGH"
    assert evidence["candidate_pcm_sha256"] != evidence["parent_pcm_sha256"]
    assert evidence["candidate_80_250_rms"] > evidence["parent_80_250_rms"], evidence
    assert evidence["candidate_80_250_crest"] > evidence["parent_80_250_crest"], evidence
    assert evidence["candidate_band_abs_error"][0] <= evidence["parent_band_abs_error"][0], evidence
    assert evidence["candidate_band_abs_error"][1] < evidence["parent_band_abs_error"][1], evidence
    assert evidence["candidate_band_shares"][3] <= evidence["parent_band_shares"][3] + 0.005, evidence
