"""Hellcat-specific, synthetic perceptual diagnostics for Stage H.

These metrics are engineering gates for a candidate source.  They do not turn
the synthetic model into an OEM measurement or a human-realism claim.
"""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


def compute_hellcat_perceptual_metrics(
    render: SourceRender,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> dict[str, float | int | str]:
    """Return deterministic source-domain and state-coupled whine metrics."""
    render.validate()
    trace.validate()
    if sample_rate_hz != 48000:
        raise ValueError("Stage-H metrics require 48 kHz")
    pressure = np.asarray(render.pressure, dtype=np.float64)
    blower = _stem(render, "blower")
    exhaust = _stem(render, "exhaust")
    shaft = _stem(render, "blower_shaft")
    lobe = _stem(render, "blower_lobe_family")
    upper = _stem(render, "blower_upper_family")
    sidebands = _stem(render, "blower_sidebands")
    bypass = _stem(render, "blower_bypass_release")
    rpm, load, throttle = _audio_state(trace, pressure.shape[0], sample_rate_hz)
    ratio = _weighted_order(shaft, rpm, sample_rate_hz)
    lobe_ratio = _weighted_order(lobe, rpm, sample_rate_hz)
    upper_ratio = _weighted_order(upper, rpm, sample_rate_hz)
    return {
        "shaft_order_error": abs(ratio - 2.36) / 2.36 if np.isfinite(ratio) else float("inf"),
        "lobe_order_error": abs(lobe_ratio - 11.8) / 11.8 if np.isfinite(lobe_ratio) else float("inf"),
        "upper_order_error": abs(upper_ratio - 23.6) / 23.6 if np.isfinite(upper_ratio) else float("inf"),
        "shaft_order_measured": float(ratio),
        "lobe_order_measured": float(lobe_ratio),
        "upper_order_measured": float(upper_ratio),
        # Use the sum of named component energies rather than aggregate-wave
        # cross terms.  This is still measured from rendered stems, while
        # avoiding phase cancellation between the shaft and lobe carriers.
        "blower_load_correlation": _state_correlation(_component_energy((shaft, lobe, upper, sidebands, bypass)), load * throttle, sample_rate_hz),
        "blower_to_exhaust_ratio_db": _energy_db_ratio(blower, exhaust),
        "sideband_to_main_ratio": _energy(sidebands) / max(_energy(shaft) + _energy(lobe) + _energy(upper), 1e-18),
        "boost_attack_time_s": _rise_time(blower, load * throttle, sample_rate_hz),
        "boost_release_time_s": _fall_time(blower, throttle, sample_rate_hz),
        "bypass_event_count": _event_count(bypass, sample_rate_hz),
        "bypass_decay_time_s": _decay_time(bypass, throttle, sample_rate_hz),
        "upper_band_short_time_peak": _short_time_band_peak(pressure, sample_rate_hz, 4000.0, 12000.0),
        "blower_energy": _energy(blower),
        "exhaust_energy": _energy(exhaust),
        "rumble_energy": _energy(_stem(render, "exhaust_rumble")),
        "scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    }


def _audio_state(trace: VehicleStateTrace, count: int, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    return tuple(np.interp(time_s, trace.time_s, values) for values in (trace.rpm, trace.load, trace.throttle))  # type: ignore[return-value]


def _stem(render: SourceRender, name: str) -> np.ndarray:
    value = render.stems.get(name)
    if value is None:
        return np.zeros_like(render.pressure, dtype=np.float64)
    return np.asarray(value, dtype=np.float64)


def _component_energy(stems: tuple[np.ndarray, ...]) -> np.ndarray:
    if not stems:
        return np.zeros((0, 1), dtype=np.float64)
    energy = np.zeros(stems[0].shape[0], dtype=np.float64)
    for stem in stems:
        energy += np.mean(np.square(np.asarray(stem, dtype=np.float64)), axis=1)
    return np.sqrt(np.maximum(energy, 0.0))[:, None]


def _energy(audio: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(audio, dtype=np.float64))))


def _energy_db_ratio(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(10.0 * np.log10(max(_energy(numerator), 1e-18) / max(_energy(denominator), 1e-18)))


def _frame_values(audio: np.ndarray, state: np.ndarray, sample_rate_hz: int, frame_s: float = 0.10) -> tuple[np.ndarray, np.ndarray]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    size = max(int(round(frame_s * sample_rate_hz)), 1)
    count = mono.size // size
    if count < 2:
        return np.zeros(0), np.zeros(0)
    energy = np.asarray([np.mean(np.square(mono[i * size:(i + 1) * size])) for i in range(count)])
    values = np.asarray([np.mean(state[i * size:(i + 1) * size]) for i in range(count)])
    return energy, values


def _state_correlation(audio: np.ndarray, state: np.ndarray, sample_rate_hz: int) -> float:
    energy, values = _frame_values(audio, state, sample_rate_hz)
    # Identity is evaluated while the engine is actually loaded.  Idle and
    # closed-throttle coast are intentionally excluded: they test the bypass
    # and V8 body, not whether compressor energy follows load.  Log energy
    # keeps the correlation about the envelope rather than carrier amplitude.
    active = values >= 0.20
    energy = energy[active]
    values = values[active]
    if energy.size < 2 or np.std(energy) == 0.0 or np.std(values) == 0.0:
        return 0.0
    return float(np.corrcoef(np.log(np.maximum(energy, 1e-18)), values)[0, 1])


def _analytic_phase(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mono = np.mean(np.asarray(signal, dtype=np.float64), axis=1)
    n = mono.size
    spectrum = np.fft.fft(mono)
    mask = np.zeros(n)
    if n % 2 == 0:
        mask[0] = mask[n // 2] = 1.0
        mask[1:n // 2] = 2.0
    else:
        mask[0] = 1.0
        mask[1:(n + 1) // 2] = 2.0
    analytic = np.fft.ifft(spectrum * mask)
    return np.unwrap(np.angle(analytic)), np.abs(analytic)


def _weighted_order(signal: np.ndarray, rpm: np.ndarray, sample_rate_hz: int) -> float:
    phase, amplitude = _analytic_phase(signal)
    if phase.size < 3:
        return float("nan")
    frequency = np.diff(phase) * sample_rate_hz / (2.0 * np.pi)
    engine_hz = np.maximum(rpm[1:], 1.0) / 60.0
    valid = (amplitude[1:] > np.percentile(amplitude[1:], 40.0)) & (frequency > 0.0) & np.isfinite(frequency)
    if not np.any(valid):
        return float("nan")
    weights = amplitude[1:][valid]
    return float(np.sum((frequency[valid] / engine_hz[valid]) * weights) / np.sum(weights))


def _rise_time(audio: np.ndarray, target: np.ndarray, sample_rate_hz: int) -> float:
    energy, values = _frame_values(audio, target, sample_rate_hz, frame_s=0.01)
    if energy.size < 3:
        return 0.0
    transitions = np.flatnonzero((values[1:] >= 0.60) & (values[:-1] < 0.60))
    if transitions.size == 0:
        return 0.0
    index = int(transitions[0] + 1)
    start_index = max(index - 1, 0)
    peak = max(float(np.max(energy)), 1e-18)
    start = max(float(energy[start_index]), 1e-18)
    ten = start + 0.1 * (peak - start)
    ninety = start + 0.9 * (peak - start)
    ten_hits = np.flatnonzero(energy[start_index:] >= ten)
    if ten_hits.size == 0:
        return 0.0
    ninety_hits = np.flatnonzero(energy[start_index + int(ten_hits[0]):] >= ninety)
    return float((ninety_hits[0] if ninety_hits.size else 0) * 0.01)


def _fall_time(audio: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> float:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    envelope = np.convolve(np.abs(mono), np.ones(max(int(0.01 * sample_rate_hz), 1)) / max(int(0.01 * sample_rate_hz), 1), mode="same")
    transitions = np.flatnonzero((throttle[1:] < 0.15) & (throttle[:-1] >= 0.30))
    if transitions.size == 0:
        return 0.0
    start = int(transitions[0] + 1)
    initial = max(float(envelope[max(start - 1, 0)]), 1e-18)
    target = initial * 0.10
    reached = np.flatnonzero(envelope[start:] <= target)
    return float((reached[0] if reached.size else 0) / sample_rate_hz)


def _event_count(audio: np.ndarray, sample_rate_hz: int) -> int:
    envelope = np.mean(np.abs(np.asarray(audio, dtype=np.float64)), axis=1)
    threshold = max(float(np.percentile(envelope, 90.0)), 1e-12)
    active = envelope > threshold
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    refractory = max(int(0.08 * sample_rate_hz), 1)
    if starts.size == 0:
        return 0
    return int(1 + np.count_nonzero(np.diff(starts) > refractory))


def _decay_time(audio: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> float:
    transitions = np.flatnonzero((throttle[1:] < 0.15) & (throttle[:-1] >= 0.30))
    if transitions.size == 0:
        return 0.0
    start = int(transitions[0] + 1)
    envelope = np.mean(np.abs(np.asarray(audio, dtype=np.float64)), axis=1)
    peak = max(float(np.max(envelope[start:start + int(0.25 * sample_rate_hz)])), 1e-12)
    reached = np.flatnonzero(envelope[start:] <= peak * 0.10)
    return float((reached[0] if reached.size else 0) / sample_rate_hz)


def _short_time_band_peak(audio: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    size = min(4096, mono.size)
    if size < 64:
        return 0.0
    window = np.hanning(size)
    peaks = []
    for start in range(0, mono.size - size + 1, max(size // 2, 1)):
        spectrum = np.abs(np.fft.rfft(mono[start:start + size] * window))
        frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate_hz)
        mask = (frequencies >= low_hz) & (frequencies <= high_hz)
        peaks.append(float(np.sum(np.square(spectrum[mask]))) if np.any(mask) else 0.0)
    return float(max(peaks, default=0.0) / max(float(np.sum(np.square(mono))), 1e-18))


__all__ = ("compute_hellcat_perceptual_metrics",)
