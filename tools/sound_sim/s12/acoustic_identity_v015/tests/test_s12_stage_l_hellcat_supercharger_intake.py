"""Stage-L L3 Hellcat intake/casing supercharger source contracts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import build_hellcat_crank_clock
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
    render_stage_l_candidate,
    render_stage_l_l3_final_pcm_probe,
)
from tools.sound_sim.s12.acoustic_identity_v015.sources.hellcat_supercharger_intake_v5 import (
    render_hellcat_supercharger_intake_v5,
)


_SR = 8_000
_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = load_stage_l_candidate(
    _ROOT / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
)
_DEFAULTS = {
    name: float(record["value"])
    for name, record in _CANDIDATE.payload["supercharger_intake"].items()
}
_CONTRIBUTORS = ("sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release")

_PERTURBATIONS = {
    "aero_family_order_ratio": 6.2,
    "aero_harmonic_mix": 0.36,
    "aero_cluster_spread_ratio": 0.028,
    "gear_family_order_ratio": 15.0,
    "gear_to_aero_ratio": 0.18,
    "torque_ripple_to_gear_depth": 0.17,
    "intake_transfer_mix": 0.50,
    "casing_transfer_mix": 0.22,
    "boost_attack_10_90_s": 0.13,
    "boost_release_90_10_s": 0.38,
    "bypass_release_gain": 0.17,
    "bypass_decay_90_10_s": 0.28,
}


def _trace(*, seconds: float = 1.1, lifting: bool = True) -> VehicleStateTrace:
    count = int(seconds * _SR) + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    split = int(0.62 * count)
    rpm = np.linspace(1_200.0, 4_800.0, count)
    load = np.full(count, 0.88)
    throttle = np.full(count, 0.92)
    if lifting:
        load[split:] = 0.08
        throttle[split:] = 0.04
    return VehicleStateTrace(
        time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s),
    ).validate()


def _render(overrides: dict[str, float] | None = None, *, trace: VehicleStateTrace | None = None):
    trace = _trace() if trace is None else trace
    clock = build_hellcat_crank_clock(trace, _SR)
    params = dict(_DEFAULTS)
    if overrides:
        params.update(overrides)
    return render_hellcat_supercharger_intake_v5(
        trace.rpm, trace.load, trace.throttle, clock, _SR, params,
    ), clock


def _rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(np.asarray(value, dtype=np.float64)))))


def _sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(value, dtype="<f8").tobytes(order="C")).hexdigest()


def _expected_boost_state(trace: VehicleStateTrace, attack_s: float, release_s: float) -> np.ndarray:
    target = np.power(trace.load, 1.08) * np.power(trace.throttle, 1.04)
    state = np.zeros_like(target)
    for index in range(1, target.size):
        configured = attack_s if target[index] >= state[index - 1] else release_s
        tau = configured / np.log(9.0)
        alpha = 1.0 - np.exp(-1.0 / max(tau * _SR, 1.0))
        state[index] = state[index - 1] + alpha * (target[index] - state[index - 1])
    return state


def _steady_trace(rpm: float, load: float, *, seconds: float = 2.5) -> VehicleStateTrace:
    count = int(seconds * _SR) + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    return VehicleStateTrace(
        time_s,
        np.full(count, rpm),
        np.full(count, load),
        np.full(count, load),
        np.zeros(count),
    ).validate()


def _fft_ridge_hz(value: np.ndarray, expected_hz: float, *, span: float = 0.18) -> float:
    mono = np.mean(np.asarray(value, dtype=np.float64), axis=1)
    mono = mono[len(mono) // 2 :]
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size)))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / _SR)
    mask = (frequencies >= expected_hz * (1.0 - span)) & (frequencies <= expected_hz * (1.0 + span))
    assert np.any(mask)
    candidates = np.flatnonzero(mask)
    return float(frequencies[candidates[int(np.argmax(spectrum[candidates]))]])


def test_shaft_phase_is_exact_236_engine_phase_without_6200_clamp() -> None:
    rendered, clock = _render(trace=_trace(lifting=False))
    diagnostics = rendered.diagnostics
    assert diagnostics["shaft_ratio"] == pytest.approx(2.36, rel=0.0, abs=0.0)
    assert diagnostics["shaft_phase_max_cycles"] == pytest.approx(
        2.36 * float(clock.engine_phase_cycles[-1]), rel=1e-12,
    )
    assert diagnostics["shaft_rpm_peak"] == pytest.approx(2.36 * 4_800.0)
    count = _SR // 2 + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    trace = VehicleStateTrace(
        time_s, np.full(count, 6_200.0), np.ones(count), np.ones(count), np.zeros(count),
    ).validate()
    high, _ = _render(trace=trace)
    assert high.diagnostics["shaft_rpm_peak"] == pytest.approx(14_632.0)
    assert high.diagnostics["published_limit_status"] == "INFORMATIONAL_ROUNDED_FIGURE_PLUS_0.22_PERCENT"


def test_hardware_anchor_sweep_stays_within_rounded_public_speed() -> None:
    count = _SR + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    trace = VehicleStateTrace(
        time_s, np.linspace(800.0, 6_100.0, count), np.ones(count), np.ones(count), np.zeros(count),
    ).validate()
    rendered, _ = _render(trace=trace)
    assert rendered.diagnostics["shaft_rpm_peak"] <= 14_600.0


def test_named_intake_and_casing_paths_are_separate_pressure_contributors() -> None:
    rendered, _ = _render()
    assert set(_CONTRIBUTORS) <= set(rendered.stems)
    assert set(("sc_aero_raw", "sc_gear_raw", "supercharger_intake")) <= set(rendered.stems)
    total = sum((rendered.stems[name] for name in _CONTRIBUTORS), np.zeros_like(rendered.pressure))
    np.testing.assert_allclose(rendered.pressure, total, atol=1e-12, rtol=0.0)
    np.testing.assert_allclose(rendered.stems["supercharger_intake"], total, atol=1e-12, rtol=0.0)
    assert rendered.diagnostics["pressure_stem_contract"] == {
        "contributors": list(_CONTRIBUTORS),
        "diagnostic_only": ["sc_aero_raw", "sc_gear_raw", "supercharger_intake"],
    }
    assert not any("exhaust" in name for name in rendered.stems)
    assert _rms(rendered.stems["sc_intake_radiated"]) > _rms(rendered.stems["sc_casing_radiated"])


def test_aero_and_casing_can_be_silenced_without_changing_other_source_path() -> None:
    baseline, _ = _render()
    no_intake, _ = _render({"intake_transfer_mix": 0.0})
    assert _rms(no_intake.stems["sc_intake_radiated"]) == 0.0
    np.testing.assert_array_equal(no_intake.stems["sc_casing_radiated"], baseline.stems["sc_casing_radiated"])
    no_case, _ = _render({"casing_transfer_mix": 0.0})
    assert _rms(no_case.stems["sc_casing_radiated"]) == 0.0
    np.testing.assert_array_equal(no_case.stems["sc_intake_radiated"], baseline.stems["sc_intake_radiated"])


def test_rpm_moves_ridges_while_load_changes_amplitude_not_family_ratio() -> None:
    count = _SR // 2 + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    def fixed(rpm: float, load: float) -> VehicleStateTrace:
        return VehicleStateTrace(
            time_s, np.full(count, rpm), np.full(count, load), np.full(count, load), np.zeros(count),
        ).validate()
    low_rpm, _ = _render(trace=fixed(1_800.0, 0.85))
    high_rpm, _ = _render(trace=fixed(3_600.0, 0.85))
    low_load, _ = _render(trace=fixed(3_600.0, 0.30))
    assert high_rpm.diagnostics["aero_ridge_hz_mean"] > 1.8 * low_rpm.diagnostics["aero_ridge_hz_mean"]
    assert high_rpm.diagnostics["aero_ridge_hz_mean"] == pytest.approx(low_load.diagnostics["aero_ridge_hz_mean"])
    assert _rms(high_rpm.stems["sc_intake_radiated"]) > _rms(low_load.stems["sc_intake_radiated"])


def test_actual_source_waveforms_move_with_orders_and_not_with_load() -> None:
    rpm = 2_400.0
    baseline, _ = _render(trace=_steady_trace(rpm, 0.88))
    low_load, _ = _render(trace=_steady_trace(rpm, 0.32))
    moved_aero, _ = _render({"aero_family_order_ratio": 6.2}, trace=_steady_trace(rpm, 0.88))
    moved_gear, _ = _render({"gear_family_order_ratio": 15.0}, trace=_steady_trace(rpm, 0.88))

    shaft_hz = rpm * 2.36 / 60.0
    aero_expected = shaft_hz * _DEFAULTS["aero_family_order_ratio"]
    gear_expected = shaft_hz * _DEFAULTS["gear_family_order_ratio"]
    aero_ridge = _fft_ridge_hz(baseline.stems["sc_aero_raw"], aero_expected)
    aero_low_load_ridge = _fft_ridge_hz(low_load.stems["sc_aero_raw"], aero_expected)
    aero_moved_ridge = _fft_ridge_hz(moved_aero.stems["sc_aero_raw"], shaft_hz * 6.2)
    gear_ridge = _fft_ridge_hz(baseline.stems["sc_gear_raw"], gear_expected)
    gear_moved_ridge = _fft_ridge_hz(moved_gear.stems["sc_gear_raw"], shaft_hz * 15.0)

    bin_hz = _SR / (baseline.stems["sc_aero_raw"].shape[0] // 2)
    assert aero_ridge == pytest.approx(aero_expected, abs=2.0 * bin_hz)
    assert gear_ridge == pytest.approx(gear_expected, abs=2.0 * bin_hz)
    assert aero_low_load_ridge == pytest.approx(aero_ridge, abs=bin_hz)
    assert aero_moved_ridge / aero_ridge == pytest.approx(6.2 / 5.0, rel=0.01)
    assert gear_moved_ridge / gear_ridge == pytest.approx(15.0 / 10.0, rel=0.01)
    assert _rms(baseline.stems["sc_aero_raw"]) > 2.0 * _rms(low_load.stems["sc_aero_raw"])


def test_bypass_requires_boost_history_and_true_throttle_close() -> None:
    no_history = _trace(seconds=0.6, lifting=False)
    no_history = VehicleStateTrace(
        no_history.time_s, no_history.rpm, np.zeros_like(no_history.load),
        np.zeros_like(no_history.throttle), no_history.acceleration_mps2,
    ).validate()
    silent, _ = _render(trace=no_history)
    assert silent.diagnostics["bypass_event_count"] == 0
    assert not np.any(silent.stems["sc_bypass_release"])
    lifted, _ = _render()
    assert lifted.diagnostics["bypass_event_count"] == 1
    assert _rms(lifted.stems["sc_bypass_release"]) > 0.0
    shift_like = _trace(seconds=0.8, lifting=False)
    throttle = shift_like.throttle.copy()
    load = shift_like.load.copy()
    load[len(load) // 2 :] = 0.20
    throttle[len(throttle) // 2 :] = 0.55
    shift_like = VehicleStateTrace(
        shift_like.time_s, shift_like.rpm, load, throttle, shift_like.acceleration_mps2,
    ).validate()
    shifted, _ = _render(trace=shift_like)
    assert shifted.diagnostics["bypass_event_count"] == 0


def test_attack_release_and_bypass_diagnostics_are_measured_time_contracts() -> None:
    baseline, _ = _render()
    diagnostics = baseline.diagnostics
    sample_tolerance = 3.0 / _SR
    assert diagnostics["boost_attack_measured_10_90_s"] == pytest.approx(
        _DEFAULTS["boost_attack_10_90_s"], abs=sample_tolerance,
    )
    assert diagnostics["boost_release_measured_90_10_s"] == pytest.approx(
        _DEFAULTS["boost_release_90_10_s"], abs=sample_tolerance,
    )
    assert diagnostics["bypass_decay_measured_90_10_s"] == pytest.approx(
        _DEFAULTS["bypass_decay_90_10_s"], abs=sample_tolerance,
    )
    changed, _ = _render({
        "boost_attack_10_90_s": 0.13,
        "boost_release_90_10_s": 0.38,
        "bypass_decay_90_10_s": 0.28,
    })
    assert changed.diagnostics["boost_attack_measured_10_90_s"] > diagnostics["boost_attack_measured_10_90_s"]
    assert changed.diagnostics["boost_release_measured_90_10_s"] > diagnostics["boost_release_measured_90_10_s"]
    assert changed.diagnostics["bypass_decay_measured_90_10_s"] > diagnostics["bypass_decay_measured_90_10_s"]


def test_attack_release_measurements_and_hashes_come_from_current_trace_state() -> None:
    trace = _trace()
    baseline, _ = _render(trace=trace)
    diagnostics = baseline.diagnostics
    expected_state = _expected_boost_state(
        trace, _DEFAULTS["boost_attack_10_90_s"], _DEFAULTS["boost_release_90_10_s"],
    )
    shaft_speed = 2.36 * trace.rpm
    expected_envelope = expected_state * (
        0.72 + 0.28 * np.clip((shaft_speed - 1_800.0) / 12_000.0, 0.0, 1.0)
    )
    assert diagnostics["boost_timing_measurement_source"] == "current_trace_boost_state"
    assert diagnostics["boost_state_sha256"] == _sha256(expected_state)
    assert diagnostics["source_envelope_sha256"] == _sha256(expected_envelope)
    assert diagnostics["boost_attack_measured_10_90_s"] == pytest.approx(
        _DEFAULTS["boost_attack_10_90_s"], abs=4.0 / _SR,
    )
    assert diagnostics["boost_release_measured_90_10_s"] == pytest.approx(
        _DEFAULTS["boost_release_90_10_s"], abs=4.0 / _SR,
    )
    changed, _ = _render({"boost_attack_10_90_s": 0.13, "boost_release_90_10_s": 0.38})
    assert changed.diagnostics["boost_state_sha256"] != diagnostics["boost_state_sha256"]
    assert changed.diagnostics["source_envelope_sha256"] != diagnostics["source_envelope_sha256"]


@pytest.mark.parametrize(
    ("name", "changed"),
    (
        ("aero_family_order_ratio", 6.2), ("aero_harmonic_mix", 0.36),
        ("aero_cluster_spread_ratio", 0.028), ("gear_family_order_ratio", 15.0),
        ("gear_to_aero_ratio", 0.18), ("torque_ripple_to_gear_depth", 0.17),
        ("intake_transfer_mix", 0.50), ("casing_transfer_mix", 0.22),
        ("boost_attack_10_90_s", 0.13), ("boost_release_90_10_s", 0.38),
        ("bypass_release_gain", 0.17), ("bypass_decay_90_10_s", 0.28),
    ),
)
def test_each_public_parameter_is_reachable_and_usage_is_measured(name: str, changed: float) -> None:
    baseline, _ = _render()
    perturbed, _ = _render({name: changed})
    assert not np.array_equal(perturbed.pressure, baseline.pressure)
    usage = perturbed.diagnostics["candidate_parameter_usage"]
    assert set(usage["requested"]) == set(_DEFAULTS)
    assert set(usage["read"]) == set(_DEFAULTS)
    assert set(usage["configured"]) == set(_DEFAULTS)
    assert set(usage["active"]) | set(usage["inactive"]) == set(_DEFAULTS)
    assert set(usage["active"]).isdisjoint(usage["inactive"])
    assert usage["unused"] == []
    assert name in usage["active"]


@pytest.mark.parametrize(
    ("name", "target_stems", "unchanged_stems"),
    (
        ("aero_family_order_ratio", ("sc_aero_raw", "sc_intake_radiated"), ("sc_gear_raw", "sc_casing_radiated", "sc_bypass_release")),
        ("aero_harmonic_mix", ("sc_aero_raw", "sc_intake_radiated"), ("sc_gear_raw", "sc_casing_radiated", "sc_bypass_release")),
        ("aero_cluster_spread_ratio", ("sc_aero_raw", "sc_intake_radiated"), ("sc_gear_raw", "sc_casing_radiated", "sc_bypass_release")),
        ("intake_transfer_mix", ("sc_intake_radiated",), ("sc_aero_raw", "sc_gear_raw", "sc_casing_radiated", "sc_bypass_release")),
        ("gear_family_order_ratio", ("sc_gear_raw", "sc_casing_radiated"), ("sc_aero_raw", "sc_intake_radiated", "sc_bypass_release")),
        ("gear_to_aero_ratio", ("sc_gear_raw", "sc_casing_radiated"), ("sc_aero_raw", "sc_intake_radiated", "sc_bypass_release")),
        ("torque_ripple_to_gear_depth", ("sc_gear_raw", "sc_casing_radiated"), ("sc_aero_raw", "sc_intake_radiated", "sc_bypass_release")),
        ("casing_transfer_mix", ("sc_casing_radiated",), ("sc_aero_raw", "sc_intake_radiated", "sc_gear_raw", "sc_bypass_release")),
        ("bypass_release_gain", ("sc_bypass_release",), ("sc_aero_raw", "sc_intake_radiated", "sc_gear_raw", "sc_casing_radiated")),
        ("bypass_decay_90_10_s", ("sc_bypass_release",), ("sc_aero_raw", "sc_intake_radiated", "sc_gear_raw", "sc_casing_radiated")),
    ),
)
def test_source_family_parameters_change_only_their_target_path(
    name: str, target_stems: tuple[str, ...], unchanged_stems: tuple[str, ...],
) -> None:
    baseline, _ = _render()
    perturbed, _ = _render({name: _PERTURBATIONS[name]})
    for stem in target_stems:
        assert not np.array_equal(perturbed.stems[stem], baseline.stems[stem]), (name, stem)
    for stem in unchanged_stems:
        np.testing.assert_array_equal(perturbed.stems[stem], baseline.stems[stem], err_msg=f"{name} leaked into {stem}")


@pytest.mark.parametrize("name", ("boost_attack_10_90_s", "boost_release_90_10_s"))
def test_boost_time_parameter_reaches_actual_state_and_only_continuous_sc_paths(name: str) -> None:
    baseline, _ = _render()
    perturbed, _ = _render({name: _PERTURBATIONS[name]})
    assert perturbed.diagnostics["boost_state_sha256"] != baseline.diagnostics["boost_state_sha256"]
    for stem in ("sc_aero_raw", "sc_intake_radiated", "sc_gear_raw", "sc_casing_radiated"):
        assert not np.array_equal(perturbed.stems[stem], baseline.stems[stem]), (name, stem)


@pytest.mark.parametrize("name,changed", tuple(_PERTURBATIONS.items()))
def test_stage_l_supercharger_perturbations_leave_l2_hemi_and_exhaust_bytes_unchanged(
    name: str, changed: float, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module

    trace = _trace(seconds=0.35, lifting=False)
    observed = []
    original = module.render_crossplane_combustion_l2_with_clock

    def observe(*args, **kwargs):
        rendered = original(*args, **kwargs)
        observed.append(rendered)
        return rendered

    monkeypatch.setattr(module, "render_crossplane_combustion_l2_with_clock", observe)
    render_stage_l_candidate(trace, _CANDIDATE)
    render_stage_l_candidate(
        trace, _CANDIDATE.with_parameter("supercharger_intake", name, changed),
    )
    assert len(observed) == 2
    baseline, repeated = observed
    for stem in (
        "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
        "hemi_structure_shock", "hemi_mechanical_torque_ripple",
    ):
        np.testing.assert_array_equal(repeated.stems[stem], baseline.stems[stem], err_msg=f"{name} altered L2 {stem}")


def test_zero_transfer_and_untriggered_bypass_are_reported_inactive() -> None:
    trace = _trace(lifting=False)
    rendered, _ = _render(
        {"intake_transfer_mix": 0.0, "casing_transfer_mix": 0.0, "bypass_release_gain": 0.0},
        trace=trace,
    )
    inactive = set(rendered.diagnostics["candidate_parameter_usage"]["inactive"])
    assert {"intake_transfer_mix", "casing_transfer_mix", "bypass_release_gain", "bypass_decay_90_10_s"} <= inactive


def test_unknown_or_missing_override_fails_closed() -> None:
    trace = _trace()
    clock = build_hellcat_crank_clock(trace, _SR)
    with pytest.raises(ValueError, match="override"):
        render_hellcat_supercharger_intake_v5(
            trace.rpm, trace.load, trace.throttle, clock, _SR, {**_DEFAULTS, "unknown": 1.0},
        )
    missing = dict(_DEFAULTS)
    missing.pop("gear_family_order_ratio")
    with pytest.raises(ValueError, match="override"):
        render_hellcat_supercharger_intake_v5(
            trace.rpm, trace.load, trace.throttle, clock, _SR, missing,
        )


def test_source_is_deterministic_and_contains_no_random_contract() -> None:
    first, _ = _render()
    second, _ = _render()
    np.testing.assert_array_equal(first.pressure, second.pressure)
    assert first.diagnostics["random_source"] is False
    assert first.diagnostics["frequency_model"] == "shaft_phase_integrated_orders_no_fixed_hz_tones"


def test_stage_l_renderer_consumes_l3_with_the_shared_clock_and_true_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module

    adapter = getattr(module, "render_supercharger_intake_l3_with_clock", None)
    assert callable(adapter)
    observed: list[object] = []
    original = adapter

    def observe(trace, clock, overrides, sample_rate_hz=48_000):
        observed.append(clock)
        return original(trace, clock, overrides, sample_rate_hz)

    monkeypatch.setattr(module, "render_supercharger_intake_l3_with_clock", observe)
    rendered = render_stage_l_candidate(_trace(), _CANDIDATE)
    assert len(observed) == 1
    evidence = rendered.diagnostics["shared_clock_consumers"]["supercharger_intake_l3"]
    assert evidence["clock_object_shared"] is True
    assert evidence["shaft_phase_exact_2_36"] is True
    assert rendered.diagnostics["stage_l_phase"] == "L3_SUPERCHARGER_INTAKE_AND_CASING"
    usage = rendered.diagnostics["candidate_parameter_usage"]
    intake_names = {f"supercharger_intake.{name}" for name in _DEFAULTS}
    assert intake_names <= set(usage["read"])
    assert intake_names <= set(usage["active"])
    assert intake_names.isdisjoint(usage["unused"])
    assert "supercharger_intake" in rendered.stems
    np.testing.assert_allclose(
        rendered.stems["supercharger_intake"],
        sum((rendered.stems[name] for name in _CONTRIBUTORS), np.zeros_like(rendered.pressure)),
        atol=1e-12,
        rtol=0.0,
    )
    assert not any(name.startswith("blower_") for name in rendered.stems)


def test_final_pcm_upper_band_share_stays_below_stage_l_gate() -> None:
    sample_rate_hz = 48_000
    count = sample_rate_hz + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    trace = VehicleStateTrace(
        time_s, np.linspace(1_500.0, 3_300.0, count), np.full(count, 0.92),
        np.full(count, 0.95), np.full(count, 2.0),
    ).validate()
    evidence = render_stage_l_l3_final_pcm_probe(trace, _CANDIDATE)
    assert evidence["candidate_band_shares"][3] <= 0.06
    assert evidence["upper_4_12khz_gate"] is True
    assert evidence["l2_low_frequency_gate"] == "PASS"
    assert evidence["l3_full_mix_low_frequency_status"] == "DIAGNOSTIC_REGRESSION_PENDING_L5"
    assert evidence["finite"] is True
    assert evidence["clipping_count"] == 0
    assert evidence["peak_dbfs"] <= -1.5 + 1e-3
    assert "twin_screw_intake_case_source_l3" in evidence["pipeline_order"]
