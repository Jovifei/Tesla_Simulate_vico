"""Measured Round-2 metrics from arrays, shared clock, and reopened PCM24."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import wave

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import build_hellcat_crank_clock
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.round2_metrics import (
    ROUND2_BANDS_HZ,
    ROUND2_WINDOWS_S,
    compute_round2_metrics,
)


SAMPLE_RATE_HZ = 8_000
DECAY_90_10_S = 0.045


def _write_pcm24(path: Path, audio: np.ndarray, *, sample_rate_hz: int = 48_000) -> Path:
    pcm = np.clip(np.rint(np.asarray(audio) * 8_388_607.0), -8_388_608, 8_388_607).astype("<i4")
    packed = pcm.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(sample_rate_hz)
        stream.writeframes(packed)
    return path


def _fixture() -> tuple[SourceRender, VehicleStateTrace, object, np.ndarray]:
    count = 48 * SAMPLE_RATE_HZ + 1
    time_s = np.arange(count, dtype=np.float64) / SAMPLE_RATE_HZ
    rpm = np.full(count, 3_600.0)
    load = np.where(time_s < 8.0, 0.15, np.where(time_s < 36.0, 0.92, 0.12))
    throttle = load.copy()
    trace = VehicleStateTrace(time_s, rpm, load, throttle, np.zeros(count)).validate()
    clock = build_hellcat_crank_clock(trace, SAMPLE_RATE_HZ)

    body = 0.18 * np.sin(2.0 * np.pi * 173.0 * time_s)
    mid = 0.09 * np.sin(2.0 * np.pi * 611.0 * time_s + 0.2)
    ripple = np.asarray(clock.torque_ripple_envelope)
    sc = 0.045 * (1.0 + 0.65 * ripple) * np.sin(2.0 * np.pi * 1_487.0 * time_s)
    stereo_body = np.column_stack((1.03 * body, 0.97 * body))
    stereo_mid = np.column_stack((0.97 * mid, 1.03 * mid))
    stereo_sc = np.column_stack((sc, 0.94 * sc))
    afterfire = np.zeros_like(stereo_body)
    tau_s = DECAY_90_10_S / np.log(9.0)
    event_indices = tuple(
        clock.event_sample_indices[int(np.searchsorted(clock.event_sample_indices, int(t * SAMPLE_RATE_HZ)))]
        for t in (36.5, 39.1, 42.8)
    )
    amplitudes = (0.18, 0.22, 0.20)
    length = int(0.15 * SAMPLE_RATE_HZ)
    local_t = np.arange(length, dtype=np.float64) / SAMPLE_RATE_HZ
    carrier = (
        0.70 * np.sin(2.0 * np.pi * 233.0 * local_t + 0.4)
        + 0.30 * np.sin(2.0 * np.pi * 911.0 * local_t + 0.9)
    )
    envelope = np.exp(-local_t / tau_s)
    for index, amplitude in zip(event_indices, amplitudes, strict=True):
        stop = min(count, index + length)
        mono = amplitude * carrier[: stop - index] * envelope[: stop - index]
        afterfire[index:stop] += np.column_stack((mono, 0.82 * mono))

    stems = {
        "hemi_exhaust_left": 0.28 * stereo_body,
        "hemi_exhaust_right": 0.24 * stereo_body,
        "hemi_blowdown_body": 0.48 * stereo_body,
        "hemi_structure_shock": stereo_mid,
        "hemi_mechanical_torque_ripple": 0.18 * stereo_mid,
        "sc_intake_radiated": stereo_sc,
        "sc_casing_radiated": 0.12 * stereo_sc,
        "afterfire": afterfire,
    }
    pressure = sum((stems[name] for name in stems), np.zeros_like(stereo_body))
    render = SourceRender(
        pressure,
        stems,
        diagnostics={
            "round2_window_metrics": "DECLARATIVE_VALUES_MUST_NOT_BE_USED",
            "afterfire_event_sample_indices": (1, 2, 3),
            "clock_coherence": -999.0,
        },
    ).validate()
    return render, trace, clock, np.asarray(event_indices, dtype=np.int64)


def test_round2_metrics_use_fixed_windows_bands_actual_arrays_clock_and_reopened_pcm24(
    tmp_path: Path,
) -> None:
    render, trace, clock, _ = _fixture()
    candidate_path = _write_pcm24(tmp_path / "candidate.wav", 0.20 * render.pressure)
    reference = np.column_stack((
        0.12 * np.sin(2.0 * np.pi * 2_350.0 * trace.time_s),
        0.11 * np.sin(2.0 * np.pi * 2_350.0 * trace.time_s),
    ))
    reference_path = _write_pcm24(tmp_path / "stage-k.wav", reference)

    metrics = compute_round2_metrics(
        render,
        trace,
        clock,
        candidate_path,
        reference_path,
        afterfire_config={"decay_90_10_s": DECAY_90_10_S},
        sample_rate_hz=SAMPLE_RATE_HZ,
    )

    assert metrics["domains"] == {
        "source": "actual SourceRender arrays",
        "clock": "actual shared HellcatCrankClock arrays",
        "final_pcm24": "reopened candidate and Stage-K PCM24 bytes",
    }
    assert metrics["window_contract_s"] == ROUND2_WINDOWS_S == {
        "baseline_0_8": (0.0, 8.0),
        "high_load_24_26": (24.0, 26.0),
        "sustained_26_36": (26.0, 36.0),
        "afterfire_36_46": (36.0, 46.0),
    }
    assert metrics["band_contract_hz"] == ROUND2_BANDS_HZ == {
        "80_250": (80.0, 250.0),
        "250_1000": (250.0, 1_000.0),
        "1000_4000": (1_000.0, 4_000.0),
    }
    assert set(metrics["windows"]) == set(ROUND2_WINDOWS_S)
    assert all(set(row["band_energy"]) == set(ROUND2_BANDS_HZ) for row in metrics["windows"].values())
    assert np.isfinite(metrics["high_load"]["sc_to_hemi_ratio_db"])
    assert metrics["high_load"]["sc_torque_ripple_clock_coherence"] > 0.45
    assert metrics["high_load"]["spectral_distance_800_3000"] > 0.0
    assert metrics["final_pcm24"]["candidate"]["pcm_bits"] == 24
    assert metrics["final_pcm24"]["candidate"]["frames"] == render.pressure.shape[0]
    assert metrics["final_pcm24"]["candidate"]["wav_sha256"] != metrics["final_pcm24"]["reference"]["wav_sha256"]

    lied = replace(render, diagnostics={"clock_coherence": 1.0, "afterfire_event_sample_indices": ()})
    repeated = compute_round2_metrics(
        lied,
        trace,
        clock,
        candidate_path,
        reference_path,
        afterfire_config={"decay_90_10_s": DECAY_90_10_S},
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    assert repeated == metrics


def test_afterfire_metrics_measure_clock_onsets_cv_centroid_and_decay_consistency(
    tmp_path: Path,
) -> None:
    render, trace, clock, expected_events = _fixture()
    candidate_path = _write_pcm24(tmp_path / "candidate.wav", 0.20 * render.pressure)
    reference_path = _write_pcm24(tmp_path / "stage-k.wav", 0.18 * render.pressure)

    metrics = compute_round2_metrics(
        render,
        trace,
        clock,
        candidate_path,
        reference_path,
        afterfire_config={"decay_90_10_s": DECAY_90_10_S},
        sample_rate_hz=SAMPLE_RATE_HZ,
    )["afterfire"]

    np.testing.assert_allclose(metrics["onset_times_s"], expected_events / SAMPLE_RATE_HZ, atol=2.0 / SAMPLE_RATE_HZ)
    assert metrics["event_count"] == 3
    assert metrics["all_onsets_on_shared_clock"] is True
    assert 0.0 < metrics["amplitude_cv"] < 0.20
    assert 0.0 < metrics["interval_cv"] < 0.20
    assert 200.0 < metrics["spectral_centroid_hz"] < 1_000.0
    assert metrics["qualification_status"] == "QUALIFIED_FROM_ACTUAL_ARRAYS_AND_CLOCK"
    consistency = metrics["decay_config_consistency"]
    assert consistency["configured_s"] == DECAY_90_10_S
    assert consistency["relative_error"] <= 0.10
    assert consistency["passes"] is True
    assert metrics["external_decay_target"] == {
        "availability": "NOT_AVAILABLE",
        "target_s": None,
    }


def test_round2_metrics_fail_closed_on_missing_fixed_window_or_non_pcm24(tmp_path: Path) -> None:
    render, trace, clock, _ = _fixture()
    short_count = 40 * SAMPLE_RATE_HZ
    short_trace = VehicleStateTrace(
        trace.time_s[:short_count], trace.rpm[:short_count], trace.load[:short_count],
        trace.throttle[:short_count], trace.acceleration_mps2[:short_count],
    ).validate()
    short_stems = {name: value[:short_count] for name, value in render.stems.items()}
    short_render = SourceRender(render.pressure[:short_count], short_stems, {}).validate()
    short_clock = build_hellcat_crank_clock(short_trace, SAMPLE_RATE_HZ)
    candidate_path = _write_pcm24(tmp_path / "candidate.wav", 0.20 * render.pressure)
    reference_path = _write_pcm24(tmp_path / "stage-k.wav", 0.18 * render.pressure)
    with pytest.raises(ValueError, match="36.*46|fixed Round-2 window"):
        compute_round2_metrics(
            short_render,
            short_trace,
            short_clock,
            candidate_path,
            reference_path,
            afterfire_config={"decay_90_10_s": DECAY_90_10_S},
            sample_rate_hz=SAMPLE_RATE_HZ,
        )

    bad_path = tmp_path / "candidate-16-bit.wav"
    with wave.open(str(bad_path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE_HZ)
        stream.writeframes(bytes(render.pressure.shape[0] * 4))
    with pytest.raises(ValueError, match="PCM24"):
        compute_round2_metrics(
            render,
            trace,
            clock,
            bad_path,
            reference_path,
            afterfire_config={"decay_90_10_s": DECAY_90_10_S},
            sample_rate_hz=SAMPLE_RATE_HZ,
        )
