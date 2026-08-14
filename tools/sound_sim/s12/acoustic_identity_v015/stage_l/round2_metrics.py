"""Actual-array Round-2 measurements for the Hellcat diagnostic search."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path
import wave

import numpy as np

from .crank_clock import HellcatCrankClock, build_hellcat_crank_clock


ROUND2_WINDOWS_S = {
    "baseline_0_8": (0.0, 8.0),
    "high_load_24_26": (24.0, 26.0),
    "sustained_26_36": (26.0, 36.0),
    "afterfire_36_46": (36.0, 46.0),
}
ROUND2_BANDS_HZ = {
    "80_250": (80.0, 250.0),
    "250_1000": (250.0, 1_000.0),
    "1000_4000": (1_000.0, 4_000.0),
}


def compute_round2_metrics(
    render: object,
    trace: object,
    clock: HellcatCrankClock,
    candidate_pcm24_path: str | Path,
    reference_pcm24_path: str | Path,
    *,
    afterfire_config: Mapping[str, float] | None = None,
    sample_rate_hz: int = 48000,
) -> dict[str, object]:
    """Measure actual source arrays and two independently reopened PCM24 WAVs."""

    pressure = _stereo(getattr(render, "pressure", None), "render.pressure")
    raw_stems = getattr(render, "stems", None)
    if not isinstance(raw_stems, Mapping):
        raise ValueError("render.stems must be a mapping")
    stems = {str(name): _stereo(value, f"stem {name}") for name, value in raw_stems.items()}
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    expected_count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    if pressure.shape[0] != expected_count or len(clock.firing_event_gate) != pressure.shape[0]:
        raise ValueError("render, trace, and shared crank clock lengths must match")
    expected_clock = build_hellcat_crank_clock(trace, sample_rate_hz)
    if not np.allclose(clock.engine_phase_cycles, expected_clock.engine_phase_cycles, atol=1e-12, rtol=0.0):
        raise ValueError("shared crank clock does not match trace")
    duration_s = float(trace.time_s[-1] - trace.time_s[0])
    if duration_s < 46.0:
        raise ValueError("fixed Round-2 window 36-46 s is unavailable")

    candidate = _read_pcm24(candidate_pcm24_path)
    reference = _read_pcm24(reference_pcm24_path)
    windows = {
        name: _measure_window(pressure, stems, bounds, sample_rate_hz)
        for name, bounds in ROUND2_WINDOWS_S.items()
    }
    sc = _sum_stems(stems, ("sc_intake_radiated", "sc_casing_radiated"), pressure)
    hemi = _sum_stems(
        stems,
        ("hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body", "hemi_structure_shock", "hemi_mechanical_torque_ripple"),
        pressure,
    )
    # The carrier is a moving source, not a fixed tone.  A short RMS-like
    # envelope preserves the crank-ripple modulation instead of averaging
    # several ripple events into an unrelated slow trend.
    sc_envelope = _smooth_abs(np.mean(sc, axis=1), max(1, int(round(0.001 * sample_rate_hz))))
    high_start = int(round(24.0 * sample_rate_hz))
    high_stop = min(sc_envelope.size, int(round(26.0 * sample_rate_hz)))
    coherence = _coherence(
        sc_envelope[high_start:high_stop],
        clock.torque_ripple_envelope[high_start:high_stop],
    )
    high_load = windows["high_load_24_26"]
    afterfire = _measure_afterfire(
        stems.get("afterfire", np.zeros_like(pressure)),
        clock,
        sample_rate_hz,
        afterfire_config,
    )
    return {
        "schema_version": "s12-stage-l-round2-metrics-1",
        "domains": {
            "source": "actual SourceRender arrays",
            "clock": "actual shared HellcatCrankClock arrays",
            "final_pcm24": "reopened candidate and Stage-K PCM24 bytes",
        },
        "window_contract_s": dict(ROUND2_WINDOWS_S),
        "band_contract_hz": dict(ROUND2_BANDS_HZ),
        "windows": windows,
        "high_load": {
            "sc_to_hemi_ratio_db": _db_ratio(sc, hemi),
            "sc_torque_ripple_clock_coherence": coherence,
            "spectral_distance_800_3000": _normalized_distance(candidate, reference),
        },
        "source": {
            "sc_energy": _energy(sc),
            "hemi_energy": _energy(hemi),
            "diagnostics_claims_used": False,
            "sc_envelope_sha256": hashlib.sha256(sc_envelope.tobytes()).hexdigest(),
        },
        "afterfire": afterfire,
        "final_pcm24": {
            "candidate": _pcm_receipt(candidate_pcm24_path, candidate),
            "reference": _pcm_receipt(reference_pcm24_path, reference),
        },
    }


def _measure_window(
    pressure: np.ndarray,
    stems: Mapping[str, np.ndarray],
    bounds: tuple[float, float],
    sample_rate_hz: int,
) -> dict[str, object]:
    start = int(round(bounds[0] * sample_rate_hz))
    stop = min(pressure.shape[0], int(round(bounds[1] * sample_rate_hz)))
    if stop <= start + 4:
        return {"available": False, "band_energy": {name: None for name in ROUND2_BANDS_HZ}, "sc_to_hemi_ratio_db": None}
    values = np.mean(pressure[start:stop], axis=1)
    frequencies, power = _spectrum(values, sample_rate_hz)
    sc = _sum_stems({name: value[start:stop] for name, value in stems.items()}, ("sc_intake_radiated", "sc_casing_radiated"), pressure[start:stop])
    hemi = _sum_stems({name: value[start:stop] for name, value in stems.items()}, ("hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body"), pressure[start:stop])
    return {
        "available": True,
        "sample_count": int(stop - start),
        "band_energy": {name: _band_energy(frequencies, power, bounds) for name, bounds in ROUND2_BANDS_HZ.items()},
        "sc_to_hemi_ratio_db": _db_ratio(sc, hemi),
    }


def _measure_afterfire(
    stem: np.ndarray,
    clock: HellcatCrankClock,
    sample_rate_hz: int,
    config: Mapping[str, float] | None,
) -> dict[str, object]:
    mono = np.mean(_stereo(stem, "afterfire"), axis=1)
    magnitude = np.abs(mono)
    if magnitude.size == 0 or float(np.max(magnitude)) <= 1.0e-12:
        return {
            "event_count": 0, "onset_times_s": (), "all_onsets_on_shared_clock": False,
            "amplitude_cv": 0.0, "interval_cv": 0.0, "spectral_centroid_hz": 0.0,
            "qualification_status": "INELIGIBLE", "decay_config_consistency": _decay_consistency(0.0, config),
            "external_decay_target": {"availability": "NOT_AVAILABLE", "target_s": None},
        }
    peak = float(np.max(magnitude))
    active = magnitude >= peak * 0.18
    starts = np.flatnonzero(active & np.r_[True, ~active[:-1]])
    spacing = max(2, int(round(0.008 * sample_rate_hz)))
    starts = starts[np.r_[True, np.diff(starts) > spacing]]
    # Each detected onset must be close to a real shared crank event; no
    # diagnostics/event list is consulted.
    matched: list[int] = []
    for start in starts:
        nearest = min(clock.event_sample_indices, key=lambda index: abs(index - int(start)))
        if abs(nearest - int(start)) <= max(3, int(round(0.004 * sample_rate_hz))):
            matched.append(int(nearest))
    amplitudes = np.asarray([float(np.max(magnitude[index:min(magnitude.size, index + int(0.12 * sample_rate_hz))])) for index in matched])
    intervals = np.diff(matched) / sample_rate_hz if len(matched) > 1 else np.asarray([], dtype=np.float64)
    decay_values = [_measure_decay(magnitude, index, sample_rate_hz) for index in matched]
    measured_decay = float(np.mean(decay_values)) if decay_values else 0.0
    return {
        "event_count": len(matched),
        "onset_times_s": tuple(index / sample_rate_hz for index in matched),
        "all_onsets_on_shared_clock": len(matched) == len(starts) and bool(matched),
        "amplitude_cv": _cv(amplitudes),
        "interval_cv": _cv(intervals),
        "spectral_centroid_hz": _centroid(mono, sample_rate_hz),
        "qualification_status": "QUALIFIED_FROM_ACTUAL_ARRAYS_AND_CLOCK" if matched else "INELIGIBLE",
        "decay_config_consistency": _decay_consistency(measured_decay, config),
        "external_decay_target": {"availability": "NOT_AVAILABLE", "target_s": None},
    }


def _decay_consistency(measured: float, config: Mapping[str, float] | None) -> dict[str, object]:
    configured = float(config.get("decay_90_10_s", 0.045)) if config else 0.045
    relative = abs(measured - configured) / configured if configured > 0.0 else float("inf")
    return {"configured_s": configured, "measured_s": measured, "relative_error": relative, "passes": relative <= 0.10}


def _read_pcm24(path_like: str | Path) -> np.ndarray:
    path = Path(path_like)
    try:
        with wave.open(str(path), "rb") as stream:
            if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getcomptype()) != (48000, 2, 3, "NONE"):
                raise ValueError("PCM24 WAV must be uncompressed 48 kHz stereo 24-bit")
            raw = np.frombuffer(stream.readframes(stream.getnframes()), dtype=np.uint8)
    except wave.Error as exc:
        raise ValueError("PCM24 WAV could not be reopened") from exc
    if raw.size % 6:
        raise ValueError("PCM24 WAV payload is not stereo aligned")
    bytes3 = raw.reshape(-1, 3)
    signed = bytes3[:, 0].astype(np.int32) | (bytes3[:, 1].astype(np.int32) << 8) | (bytes3[:, 2].astype(np.int32) << 16)
    signed[signed & 0x800000 != 0] -= 0x1000000
    values = signed.reshape(-1, 2).astype(np.float64) / 8388607.0
    if not np.all(np.isfinite(values)):
        raise ValueError("PCM24 WAV is not finite")
    return values


def _pcm_receipt(path_like: str | Path, values: np.ndarray) -> dict[str, object]:
    return {
        "wav_sha256": _sha256_path(path_like), "sample_rate_hz": 48000,
        "channels": 2, "pcm_bits": 24, "frames": int(values.shape[0]),
        "finite": bool(np.all(np.isfinite(values))),
        "clipping_count": int(np.count_nonzero(np.abs(values) > 1.0)),
        "peak_dbfs": float(20.0 * np.log10(max(float(np.max(np.abs(values))), 1.0e-12))),
    }


def _normalized_distance(first: np.ndarray, second: np.ndarray) -> float:
    a_f, a_p = _spectrum(np.mean(first, axis=1), 48000)
    b_f, b_p = _spectrum(np.mean(second, axis=1), 48000)
    a_mask = (a_f >= 800.0) & (a_f <= 3000.0)
    b_mask = (b_f >= 800.0) & (b_f <= 3000.0)
    n = min(int(np.count_nonzero(a_mask)), int(np.count_nonzero(b_mask)))
    if n < 2:
        return 0.0
    a = a_p[a_mask][:n]; b = b_p[b_mask][:n]
    a /= max(float(a.sum()), 1.0e-18); b /= max(float(b.sum()), 1.0e-18)
    return float(np.sqrt(np.mean(np.square(a - b))))


def _stereo(value: object, label: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2 or array.shape[0] == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{label} must be finite stereo data")
    return array


def _sum_stems(stems: Mapping[str, np.ndarray], names: tuple[str, ...], fallback: np.ndarray) -> np.ndarray:
    found = [stems[name] for name in names if name in stems]
    return sum(found, np.zeros_like(fallback)) if found else np.zeros_like(fallback)


def _spectrum(values: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(values.size)
    spectrum = np.fft.rfft(np.asarray(values, dtype=np.float64) * window)
    return np.fft.rfftfreq(values.size, 1.0 / sample_rate_hz), np.square(np.abs(spectrum))


def _band_energy(frequencies: np.ndarray, power: np.ndarray, bounds: tuple[float, float]) -> float:
    return float(np.sum(power[(frequencies >= bounds[0]) & (frequencies < bounds[1])]))


def _energy(value: np.ndarray) -> float:
    return float(np.mean(np.square(value)))


def _db_ratio(first: np.ndarray, second: np.ndarray) -> float:
    return float(10.0 * np.log10(max(_energy(first), 1.0e-18) / max(_energy(second), 1.0e-18)))


def _smooth_abs(values: np.ndarray, width: int) -> np.ndarray:
    kernel = np.ones(max(1, width), dtype=np.float64) / max(1, width)
    return np.convolve(np.abs(values), kernel, mode="same")


def _coherence(first: np.ndarray, second: np.ndarray) -> float:
    size = min(first.size, second.size)
    a = first[:size] - float(np.mean(first[:size])); b = second[:size] - float(np.mean(second[:size]))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.clip(np.dot(a, b) / denominator, -1.0, 1.0)) if denominator > 1e-18 else 0.0


def _cv(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(values)) if values.size else 0.0
    return float(np.std(values) / mean) if values.size and mean > 1e-12 else 0.0


def _centroid(values: np.ndarray, sample_rate_hz: int) -> float:
    frequencies, power = _spectrum(values, sample_rate_hz)
    total = float(np.sum(power))
    return float(np.sum(frequencies * power) / total) if total > 1e-18 else 0.0


def _measure_decay(magnitude: np.ndarray, start: int, sample_rate_hz: int) -> float:
    tail = magnitude[start:min(magnitude.size, start + int(0.4 * sample_rate_hz))]
    if tail.size == 0 or float(np.max(tail)) <= 1e-12:
        return 0.0
    width = max(3, int(round(0.006 * sample_rate_hz)))
    envelope = np.convolve(np.abs(tail), np.ones(width, dtype=np.float64) / width, mode="same")
    peak_index = int(np.argmax(envelope))
    peak = float(envelope[peak_index])
    below = np.flatnonzero(envelope[peak_index:] <= 0.10 * peak)
    return float((below[0] + peak_index) / sample_rate_hz) if below.size else float(tail.size / sample_rate_hz)


def _sha256_path(path_like: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path_like).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ("ROUND2_BANDS_HZ", "ROUND2_WINDOWS_S", "compute_round2_metrics")
