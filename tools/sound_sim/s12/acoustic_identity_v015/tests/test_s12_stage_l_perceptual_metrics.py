from __future__ import annotations

from pathlib import Path
import wave

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _write_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.perceptual_metrics import (
    _bank_pattern_error,
    compute_stage_l_perceptual_metrics,
    evaluate_stage_l_metric_gates,
)


def _fixture(sample_rate_hz: int = 8_000) -> tuple[SourceRender, VehicleStateTrace]:
    count = sample_rate_hz * 2
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(1_200.0, 4_000.0, count)
    load = np.where(time_s < 1.0, 0.20, 0.90)
    throttle = load.copy()
    phase = np.cumsum(rpm / 60.0) / sample_rate_hz
    exhaust = np.column_stack((0.16 * np.sin(2.0 * np.pi * 4.0 * phase),) * 2)
    blowdown = np.column_stack((0.08 * np.sign(np.sin(2.0 * np.pi * 4.0 * phase)),) * 2)
    intake = np.column_stack((0.04 * load * np.sin(2.0 * np.pi * 11.8 * phase),) * 2)
    casing = np.column_stack((0.01 * load * np.sin(2.0 * np.pi * 23.6 * phase),) * 2)
    bypass = np.zeros_like(exhaust)
    pressure = exhaust + blowdown + intake + casing
    render = SourceRender(
        pressure,
        {
            "hemi_exhaust_left": 0.52 * exhaust,
            "hemi_exhaust_right": 0.48 * exhaust,
            "hemi_blowdown_body": blowdown,
            "hemi_structure_shock": 0.1 * blowdown,
            "hemi_mechanical_torque_ripple": 0.05 * blowdown,
            "sc_intake_radiated": intake,
            "sc_casing_radiated": casing,
            "sc_bypass_release": bypass,
            "hellcat_shift_reengagement": np.zeros_like(exhaust),
            "hellcat_sc_drive_transient": np.zeros_like(exhaust),
            "hellcat_tip_in_blowdown": np.zeros_like(exhaust),
        },
        {
            "event_sample_indices": tuple(range(0, count, 250)),
            "bank_labels": tuple("left" if index % 2 == 0 else "right" for index in range((count + 249) // 250)),
            "event_phase_max_error_samples": 0.0,
            "bank_interval_ratio_multisets": {"left": (1, 2, 2, 3), "right": (1, 2, 2, 3)},
            "bank_local_response": {"left_group_delay_samples": 1, "right_group_delay_samples": 3},
            "bypass_event_count": 0,
            "boost_attack_measured_10_90_s": 0.075,
            "boost_release_measured_90_10_s": 0.24,
            "bypass_decay_measured_90_10_s": 0.0,
            "shift_event_measurements": (),
            "candidate_parameter_usage": {
                "requested": ["combustion_and_blowdown.cylinder_strength_variation", "supercharger_intake.aero_family_order_ratio"],
                "read": ["combustion_and_blowdown.cylinder_strength_variation", "supercharger_intake.aero_family_order_ratio"],
                "configured": ["combustion_and_blowdown.cylinder_strength_variation", "supercharger_intake.aero_family_order_ratio"],
                "active": ["combustion_and_blowdown.cylinder_strength_variation", "supercharger_intake.aero_family_order_ratio"],
                "inactive": [],
                "unused": [],
            },
        },
    ).validate()
    trace = VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()
    return render, trace


def test_metrics_are_measured_in_explicit_source_pre_ptr_and_reopened_pcm_domains(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    metrics = compute_stage_l_perceptual_metrics(render, trace, wav, sample_rate_hz=8_000)

    assert set(metrics) == {"schema_version", "domains", "source_domain", "pre_ptr", "final_pcm24"}
    assert metrics["domains"] == {
        "source_domain": "actual SourceRender arrays and detected events",
        "pre_ptr": "actual named transient arrays before common Pre-PTR EQ",
        "final_pcm24": "reopened PCM24 WAV bytes",
    }
    source = metrics["source_domain"]
    for key in (
        "shaft_ratio_error", "shaft_max_rpm", "intake_whine_load_correlation",
        "intake_to_exhaust_ratio_db", "gear_to_aero_ratio", "intake_transfer_energy_ratio",
        "bypass_event_count", "boost_attack_10_90_s", "boost_release_90_10_s",
        "bypass_decay_90_10_s", "order_ridge_continuity", "tone_prominence_ratio",
        "firing_event_angle_error_samples", "bank_interval_pattern_error", "fourth_order_presence",
        "20_80_hz_share", "80_160_hz_share", "160_250_hz_share", "250_1000_hz_share",
        "low_band_pulse_crest_db", "low_band_envelope_cv", "fluctuation_below_20_hz",
        "roughness_20_300_hz", "modulation_peak_hz", "bank_to_bank_delay",
    ):
        assert key in source
        assert np.isfinite(float(source[key]))
    assert set(metrics["pre_ptr"]) >= {"shift_dip_db", "shift_settling_s", "shift_overshoot_db"}
    assert set(metrics["final_pcm24"]) >= {
        "wav_sha256", "sample_rate_hz", "channels", "pcm_bits", "finite",
        "final_pcm_lufs", "final_pcm_peak_dbfs", "clipping_count", "band_shares",
    }
    assert metrics["final_pcm24"]["pcm_bits"] == 24
    # The shared reference extractor uses full-spectrum normalization.  The
    # audited 20 Hz–12 kHz bands must not be renormalized to one here.
    assert 0.0 < sum(metrics["final_pcm24"]["band_shares"]) <= 1.0


def test_pre_ptr_propagates_and_derives_actual_parameter_reachability(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    metrics = compute_stage_l_perceptual_metrics(render, trace, wav, sample_rate_hz=8_000)
    usage = render.diagnostics["candidate_parameter_usage"]
    assert metrics["pre_ptr"]["candidate_parameter_usage"] == usage
    assert metrics["pre_ptr"]["all_requested_parameters_reachable"] is True


def test_pre_ptr_reachability_is_false_only_from_actual_unused_set(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    diagnostics = dict(render.diagnostics)
    diagnostics["candidate_parameter_usage"] = {
        "requested": ["a", "b"], "read": ["a"], "configured": ["a"],
        "active": ["a"], "inactive": [], "unused": ["b"],
    }
    changed = SourceRender(render.pressure, render.stems, diagnostics).validate()
    metrics = compute_stage_l_perceptual_metrics(changed, trace, wav, sample_rate_hz=8_000)
    assert metrics["pre_ptr"]["all_requested_parameters_reachable"] is False


def test_pre_ptr_rejects_declarative_or_inconsistent_parameter_usage(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    diagnostics = dict(render.diagnostics)
    diagnostics["candidate_parameter_usage"] = {
        "requested": ["a"], "read": ["a"], "configured": [],
        "active": ["a"], "inactive": [], "unused": [],
    }
    inconsistent = SourceRender(render.pressure, render.stems, diagnostics).validate()
    with pytest.raises(ValueError, match="configured must equal read"):
        compute_stage_l_perceptual_metrics(inconsistent, trace, wav, sample_rate_hz=8_000)


def test_actual_array_change_moves_metric_without_changing_declarations(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    first = compute_stage_l_perceptual_metrics(render, trace, wav, sample_rate_hz=8_000)
    stems = dict(render.stems)
    stems["sc_intake_radiated"] = 1.7 * stems["sc_intake_radiated"]
    changed = SourceRender(render.pressure + 0.7 * render.stems["sc_intake_radiated"], stems, render.diagnostics).validate()
    second = compute_stage_l_perceptual_metrics(changed, trace, wav, sample_rate_hz=8_000)
    assert second["source_domain"]["intake_to_exhaust_ratio_db"] > first["source_domain"]["intake_to_exhaust_ratio_db"]


def test_exhaust_aliases_cannot_double_count_the_exact_primitive_stems(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    first = compute_stage_l_perceptual_metrics(render, trace, wav, sample_rate_hz=8_000)
    stems = dict(render.stems)
    primitive = stems["hemi_exhaust_left"] + stems["hemi_exhaust_right"]
    stems["exhaust"] = primitive
    stems["hemi_exhaust"] = primitive
    aliased = SourceRender(render.pressure, stems, render.diagnostics).validate()
    second = compute_stage_l_perceptual_metrics(aliased, trace, wav, sample_rate_hz=8_000)
    assert second["source_domain"]["intake_to_exhaust_ratio_db"] == pytest.approx(
        first["source_domain"]["intake_to_exhaust_ratio_db"]
    )


def test_source_metrics_fail_closed_when_an_exact_primitive_stem_is_missing(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    stems = dict(render.stems)
    del stems["hemi_exhaust_left"]
    missing = SourceRender(render.pressure, stems, render.diagnostics).validate()
    with pytest.raises(ValueError, match="required Stage-L primitive stem"):
        compute_stage_l_perceptual_metrics(missing, trace, wav, sample_rate_hz=8_000)


def test_tone_prominence_uses_sc_source_not_unrelated_full_pressure(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    first = compute_stage_l_perceptual_metrics(render, trace, wav, sample_rate_hz=8_000)
    time = np.arange(render.pressure.shape[0]) / 8_000.0
    unrelated = np.column_stack((0.5 * np.sin(2.0 * np.pi * 3_500.0 * time),) * 2)
    changed = SourceRender(render.pressure + unrelated, render.stems, render.diagnostics).validate()
    second = compute_stage_l_perceptual_metrics(changed, trace, wav, sample_rate_hz=8_000)
    assert second["source_domain"]["tone_prominence_ratio"] == pytest.approx(
        first["source_domain"]["tone_prominence_ratio"]
    )


def test_tone_prominence_is_higher_for_known_sc_tone_than_deterministic_broadband(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    count = render.pressure.shape[0]
    time_s = np.arange(count, dtype=np.float64) / 8_000.0
    tone_mono = 0.04 * np.sin(2.0 * np.pi * 600.0 * time_s)
    rng = np.random.default_rng(20260813)
    broadband_mono = 0.04 * rng.standard_normal(count)

    def with_sc_intake(mono: np.ndarray) -> SourceRender:
        intake = np.column_stack((mono, mono))
        stems = dict(render.stems)
        previous = stems["sc_intake_radiated"] + stems["sc_casing_radiated"]
        stems["sc_intake_radiated"] = intake
        stems["sc_casing_radiated"] = np.zeros_like(intake)
        return SourceRender(render.pressure - previous + intake, stems, render.diagnostics).validate()

    tone = compute_stage_l_perceptual_metrics(
        with_sc_intake(tone_mono), trace, wav, sample_rate_hz=8_000,
    )
    broadband = compute_stage_l_perceptual_metrics(
        with_sc_intake(broadband_mono), trace, wav, sample_rate_hz=8_000,
    )
    assert tone["source_domain"]["tone_prominence_ratio"] > (
        10.0 * broadband["source_domain"]["tone_prominence_ratio"]
    )


def test_firing_and_bank_metrics_measure_arrays_against_clock_not_diagnostic_claims(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    first = compute_stage_l_perceptual_metrics(render, trace, wav, sample_rate_hz=8_000)
    diagnostics = dict(render.diagnostics)
    diagnostics.update({
        "event_phase_max_error_samples": 999.0,
        "bank_interval_ratio_multisets": {"left": (99,), "right": (99,)},
        "bank_local_response": {"left_group_delay_samples": 500, "right_group_delay_samples": 999},
        "bank_labels": tuple("left" for _ in diagnostics["event_sample_indices"]),
    })
    changed = SourceRender(render.pressure, render.stems, diagnostics).validate()
    second = compute_stage_l_perceptual_metrics(changed, trace, wav, sample_rate_hz=8_000)
    for name in (
        "firing_event_angle_error_samples", "bank_interval_pattern_error", "bank_to_bank_delay",
    ):
        assert second["source_domain"][name] == pytest.approx(first["source_domain"][name])


def test_source_metrics_require_clock_event_positions_for_array_alignment(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", render.pressure * 0.25)
    diagnostics = dict(render.diagnostics)
    diagnostics.pop("event_sample_indices")
    missing_clock = SourceRender(render.pressure, render.stems, diagnostics).validate()
    with pytest.raises(ValueError, match="clock event_sample_indices"):
        compute_stage_l_perceptual_metrics(missing_clock, trace, wav, sample_rate_hz=8_000)


def test_bank_pattern_rejects_identical_left_right_crosstalk_arrays() -> None:
    events = np.arange(100, 900, 100, dtype=np.int64)
    mono = np.zeros(1_000, dtype=np.float64)
    mono[events] = 1.0
    identical = np.column_stack((mono, mono))

    assert _bank_pattern_error(identical, identical.copy(), events) > 1.0


def test_named_transient_event_count_comes_from_named_arrays_not_clock_indices(tmp_path: Path) -> None:
    render, trace = _fixture()
    stems = dict(render.stems)
    transient = np.zeros_like(render.pressure)
    transient[2_000:2_020] = 0.5
    transient[10_000:10_020] = -0.5
    stems["hellcat_shift_reengagement"] = transient
    changed = SourceRender(render.pressure + transient, stems, render.diagnostics).validate()
    wav = _write_pcm24_wav(tmp_path / "candidate.wav", changed.pressure * 0.25)

    metrics = compute_stage_l_perceptual_metrics(changed, trace, wav, sample_rate_hz=8_000)

    assert metrics["pre_ptr"]["named_transient_event_count"] == 2


def test_existing_full_mix_low_crest_regression_is_a_hard_gate_failure() -> None:
    parent = {"source_domain": {"low_band_pulse_crest_db": 20.0 * np.log10(2.863099)}}
    candidate = {
        "source_domain": {
            "low_band_pulse_crest_db": 20.0 * np.log10(2.67696),
            "shaft_ratio_error": 0.0,
            "shaft_max_rpm": 14_396.0,
            "intake_whine_load_correlation": 0.90,
            "roughness_20_300_hz": 1.2,
            "bank_interval_pattern_error": 0.0,
        },
        "final_pcm24": {"finite": True, "clipping_count": 0, "band_shares": [0.4, 0.4, 0.15, 0.05]},
    }
    gates = evaluate_stage_l_metric_gates(candidate, parent)
    assert gates["low_band_pulse_crest_improves_parent"] is False
    assert gates["all_pass"] is False
    assert gates["automatic_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


def test_gate_requires_reopened_pcm24_format_peak_and_clipping_health() -> None:
    parent = {"source_domain": {"low_band_pulse_crest_db": 1.0}}
    candidate = {
        "source_domain": {
            "low_band_pulse_crest_db": 2.0,
            "shaft_ratio_error": 0.0,
            "shaft_max_rpm": 14_000.0,
            "intake_whine_load_correlation": 0.90,
            "bank_interval_pattern_error": 0.0,
        },
        "final_pcm24": {
            "finite": True,
            "clipping_count": 0,
            "sample_rate_hz": 8_000,
            "channels": 1,
            "pcm_bits": 16,
            "final_pcm_peak_dbfs": -1.0,
            "band_shares": [0.4, 0.4, 0.15, 0.05],
        },
    }
    gates = evaluate_stage_l_metric_gates(candidate, parent)
    assert gates["final_pcm_format"] is False
    assert gates["final_pcm_peak"] is False


def test_source_render_floats_cannot_be_substituted_for_a_pcm24_file(tmp_path: Path) -> None:
    render, trace = _fixture()
    with pytest.raises((FileNotFoundError, ValueError), match="PCM24|WAV|exist"):
        compute_stage_l_perceptual_metrics(render, trace, tmp_path / "missing.wav", sample_rate_hz=8_000)


def test_reopened_pcm24_fails_closed_on_wrong_sample_rate(tmp_path: Path) -> None:
    render, trace = _fixture()
    wav_path = tmp_path / "wrong-rate.wav"
    with wave.open(str(wav_path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(44_100)
        stream.writeframes(bytes(256 * 2 * 3))
    with pytest.raises(ValueError, match="48000|PCM24 WAV"):
        compute_stage_l_perceptual_metrics(render, trace, wav_path, sample_rate_hz=8_000)


def test_auxiliary_crest_and_roughness_gates_use_measured_parent_deltas() -> None:
    parent = {
        "source_domain": {"low_band_pulse_crest_db": 6.0, "roughness_20_300_hz": 1.0},
        "final_pcm24": {"band_shares": [0.3, 0.3, 0.2, 0.04]},
    }
    candidate = {
        "source_domain": {
            "low_band_pulse_crest_db": 7.5,
            "roughness_20_300_hz": 1.20,
            "shaft_ratio_error": 0.0,
            "shaft_anchor_max_rpm": 14_300.0,
            "intake_whine_load_correlation": 0.90,
            "bank_interval_pattern_error": 0.0,
        },
        "final_pcm24": {
            "finite": True,
            "clipping_count": 0,
            "sample_rate_hz": 48_000,
            "channels": 2,
            "pcm_bits": 24,
            "final_pcm_peak_dbfs": -2.0,
            "band_shares": [0.3, 0.3, 0.2, 0.05],
        },
        "reference_distance": {
            "mean_improvement_ratio": 0.30,
            "gates": {
                "all_required_states_available": True,
                "mean_improvement_at_least_30_percent": True,
                "no_state_worse_than_10_percent": True,
            },
        },
    }
    gates = evaluate_stage_l_metric_gates(candidate, parent)
    assert gates["low_band_pulse_crest_auxiliary_1_to_3_db"] is True
    assert gates["roughness_auxiliary_10_to_35_percent"] is True
    assert gates["reference_mean_improvement_at_least_30_percent"] is True

    candidate["source_domain"] = dict(candidate["source_domain"], low_band_pulse_crest_db=9.1)
    candidate["source_domain"]["roughness_20_300_hz"] = 1.36
    failed = evaluate_stage_l_metric_gates(candidate, parent)
    assert failed["low_band_pulse_crest_auxiliary_1_to_3_db"] is False
    assert failed["roughness_auxiliary_10_to_35_percent"] is False


def test_flat_legacy_reference_result_cannot_satisfy_reference_gate() -> None:
    candidate = {
        "source_domain": {
            "low_band_pulse_crest_db": 2.0,
            "roughness_20_300_hz": 1.2,
            "shaft_ratio_error": 0.0,
            "shaft_anchor_max_rpm": 14_300.0,
            "intake_whine_load_correlation": 0.90,
            "bank_interval_pattern_error": 0.0,
        },
        "final_pcm24": {
            "finite": True, "clipping_count": 0, "sample_rate_hz": 48_000,
            "channels": 2, "pcm_bits": 24, "final_pcm_peak_dbfs": -2.0,
            "band_shares": [0.3, 0.3, 0.2, 0.05],
        },
        "reference_distance": {"average_improvement_ratio": 0.99},
    }
    parent = {
        "source_domain": {"low_band_pulse_crest_db": 1.0, "roughness_20_300_hz": 1.0},
        "final_pcm24": {"band_shares": [0.3, 0.3, 0.2, 0.04]},
    }
    gates = evaluate_stage_l_metric_gates(candidate, parent)
    assert gates["reference_mean_improvement_at_least_30_percent"] is False
