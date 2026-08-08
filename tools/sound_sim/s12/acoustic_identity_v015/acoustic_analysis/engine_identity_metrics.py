"""Measured, synthetic-scope identity metrics for v0.15 stereo renders."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace

# Vehicles supported by the identity metric pipeline (8 cars total).
_SUPPORTED = {
    "ferrari_458", "hellcat", "rx7_fd",
    "aventador_lp700", "c63_w204", "gtr_r35", "lfa", "supra_jza80",
}


@dataclass(frozen=True)
class OrderMap:
    """Dynamic STFT energy sampled onto engine-order bins."""

    time_s: np.ndarray
    orders: np.ndarray
    power: np.ndarray
    engine_hz: np.ndarray

    @property
    def order_energy(self) -> np.ndarray:
        return np.mean(self.power, axis=0) if self.power.size else np.zeros_like(self.orders)

    def to_dict(self) -> dict[str, object]:
        return {
            "time_s": self.time_s.tolist(),
            "orders": self.orders.tolist(),
            "power": self.power.tolist(),
            "engine_hz": self.engine_hz.tolist(),
            "order_energy": self.order_energy.tolist(),
        }


def compute_order_map(
    audio: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int = 48000, frame_size: int = 2048, hop_size: int = 512
) -> OrderMap:
    """Map real STFT energy to dynamic engine orders using the supplied trace."""
    signal = _audio(audio)
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    if frame_size < 64 or hop_size < 1:
        raise ValueError("frame_size must be >= 64 and hop_size must be positive")
    size = min(frame_size, signal.shape[0])
    starts = _frame_starts(signal.shape[0], size, hop_size)
    orders = np.arange(0.25, 24.25, 0.25, dtype=np.float64)
    frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate_hz)
    window = np.hanning(size)
    duration_s = (signal.shape[0] - 1) / sample_rate_hz
    time_s = trace.time_s[0] + (starts + (size - 1) / 2.0) / sample_rate_hz
    time_s = np.clip(time_s, trace.time_s[0], trace.time_s[0] + duration_s)
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    engine_hz = rpm / 60.0
    power = np.zeros((starts.size, orders.size), dtype=np.float64)
    for index, start in enumerate(starts):
        spectrum = _frame_spectrum(signal[start : start + size], window)
        if engine_hz[index] > 0.0:
            power[index] = np.interp(orders * engine_hz[index], frequencies, spectrum, left=0.0, right=0.0)
    return OrderMap(time_s=time_s, orders=orders, power=power, engine_hz=engine_hz)


def compute_engine_identity_metrics(
    vehicle_id: str, render: SourceRender, trace: VehicleStateTrace, sample_rate_hz: int = 48000
) -> dict[str, object]:
    """Compute finite audio/stem metrics without using renderer diagnostics as data."""
    if vehicle_id not in _SUPPORTED:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    render.validate()
    trace.validate()
    signal = _audio(render.pressure)
    frequencies, energy = _spectrum(signal, sample_rate_hz)
    total = float(energy.sum())
    low = _band_fraction(energy, frequencies, 40.0, 400.0)
    high = _band_fraction(energy, frequencies, 1200.0, None)
    order_map = compute_order_map(render.pressure, trace, sample_rate_hz)
    vector = _normalised(order_map.order_energy)
    peak = float(vector.max()) if vector.size else 0.0
    metrics: dict[str, object] = {
        "vehicle_id": vehicle_id,
        "spectral_centroid_hz": float(np.sum(frequencies * energy) / total) if total else 0.0,
        "low_energy_fraction_40_400hz": low,
        "high_energy_fraction_gt_1200hz": high,
        "order_energy_vector": vector.tolist(),
        "harmonic_density": float(np.count_nonzero(vector >= 0.10 * peak) / vector.size) if peak else 0.0,
        "harmonic_ratio": float(peak / np.median(vector[vector > 0.0])) if np.any(vector > 0.0) else 0.0,
        "order_map": order_map.to_dict(),
    }
    if vehicle_id == "ferrari_458":
        sweep_correlation, sweep_error = _order_sweep_tracking(signal, trace, sample_rate_hz, 2.0)
        metrics["ferrari"] = {
            "high_frequency_ratio": high,
            "high_frequency_growth": _end_to_start_fraction(signal, sample_rate_hz, 1200.0),
            "order_sweep_correlation": sweep_correlation,
            "order_sweep_relative_error": sweep_error,
        }
    elif vehicle_id == "hellcat":
        blower = _stem(render, "blower")
        metrics["hellcat"] = {
            "low_frequency_energy_40_400hz": float(energy[(frequencies >= 40.0) & (frequencies <= 400.0)].sum()),
            "blower_stem_energy": float(np.sum(np.square(np.asarray(render.stems.get("blower", 0.0), dtype=np.float64)))),
            "blower_load_correlation": _frame_energy_state_correlation(blower, trace, sample_rate_hz, "load"),
        }
    else:
        integer, half = _integer_half_order_fractions(order_map)
        turbo = _stem(render, "turbo")
        turbine = _stem(render, "turbine")
        lift = _stem(render, "lift")
        metrics["rx7"] = {
            "integer_order_concentration": integer,
            "half_order_leakage": half,
            "turbo_primary_rise": _frame_end_start_ratio(turbo, sample_rate_hz),
            "turbo_secondary_rise": _frame_end_start_ratio(turbine, sample_rate_hz),
            "turbo_transition_s": _turbo_transition_time(turbo, turbine, trace, sample_rate_hz),
            "lift_decay_ratio": _lift_decay_ratio(lift, trace, sample_rate_hz),
        }
    return metrics


def compare_identity_renders(
    renders: Mapping[str, SourceRender | np.ndarray], trace: VehicleStateTrace, sample_rate_hz: int = 48000
) -> dict[str, object]:
    """Apply same-trace, unit-RMS A/B gates without altering any demo render."""
    trace.validate()
    items = [(name, _audio(render.pressure if isinstance(render, SourceRender) else render)) for name, render in renders.items()]
    pairs: dict[str, dict[str, object]] = {}
    for (left_name, left), (right_name, right) in combinations(items, 2):
        if left.shape != right.shape:
            raise ValueError("all comparison renders must have identical sample counts")
        correlation = _absolute_correlation(_unit_rms(left), _unit_rms(right))
        distance = _log_order_distance(left, right, trace, sample_rate_hz)
        pairs[f"{left_name}__{right_name}"] = {
            "absolute_waveform_correlation": correlation,
            "log_order_cosine_distance": distance,
            "passes": bool(correlation < 0.85 and distance > 0.20),
        }
    return {"comparison_scope": "same_trace_unit_rms_analysis_only", "pairs": pairs, "passes": bool(pairs) and all(pair["passes"] for pair in pairs.values())}


def _audio(audio: np.ndarray) -> np.ndarray:
    signal = np.asarray(audio, dtype=np.float64)
    if signal.ndim == 1:
        signal = signal[:, np.newaxis]
    elif signal.ndim == 2 and signal.shape[1] == 2:
        pass
    else:
        raise ValueError("audio must be mono or stereo [N, 2]")
    if signal.shape[0] == 0 or not np.all(np.isfinite(signal)):
        raise ValueError("audio must be nonempty and finite")
    return signal


def _stem(render: SourceRender, name: str) -> np.ndarray:
    return _audio(render.stems[name]) if name in render.stems else np.zeros_like(render.pressure, dtype=np.float64)


def _spectrum(signal: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(signal.shape[0])[:, np.newaxis]
    return np.fft.rfftfreq(signal.shape[0], 1.0 / sample_rate_hz), _frame_spectrum(signal, window)


def _band_fraction(energy: np.ndarray, frequencies: np.ndarray, low_hz: float, high_hz: float | None) -> float:
    mask = frequencies >= low_hz
    if high_hz is not None:
        mask &= frequencies <= high_hz
    total = float(energy.sum())
    return float(energy[mask].sum() / total) if total else 0.0


def _normalised(values: np.ndarray) -> np.ndarray:
    total = float(np.sum(values))
    return values / total if total else np.zeros_like(values)


def _end_to_start_fraction(signal: np.ndarray, sample_rate_hz: int, low_hz: float) -> float:
    size = max(signal.shape[0] // 3, 1)
    _, start = _spectrum(signal[:size], sample_rate_hz)
    frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate_hz)
    _, end = _spectrum(signal[-size:], sample_rate_hz)
    first = _band_fraction(start, frequencies, low_hz, None)
    last = _band_fraction(end, frequencies, low_hz, None)
    return float(last / first) if first > 1e-15 else 0.0


def _order_sweep_tracking(
    audio: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int, order: float
) -> tuple[float, float]:
    signal = _audio(audio)
    order_map = compute_order_map(signal, trace, sample_rate_hz)
    if np.count_nonzero(order_map.engine_hz) < 2:
        return 0.0, 0.0
    detected = []
    expected = []
    frame_size = min(2048, signal.shape[0])
    frequencies = np.fft.rfftfreq(frame_size, 1.0 / sample_rate_hz)
    window = np.hanning(frame_size)
    starts = _frame_starts(signal.shape[0], frame_size, 512)
    for start, engine_hz in zip(starts, order_map.engine_hz):
        if engine_hz <= 0.0:
            continue
        energy = _frame_spectrum(signal[start : start + frame_size], window)
        mask = (frequencies >= 1.5 * engine_hz) & (frequencies <= 2.5 * engine_hz)
        if np.any(mask):
            detected.append(float(frequencies[mask][np.argmax(energy[mask])]))
            expected.append(order * engine_hz)
    if len(detected) < 2 or np.std(detected) == 0.0 or np.std(expected) == 0.0:
        return 0.0, 0.0
    detected_array = np.asarray(detected)
    expected_array = np.asarray(expected)
    return (
        float(np.clip(np.corrcoef(detected_array, expected_array)[0, 1], -1.0, 1.0)),
        float(np.mean(np.abs(detected_array - expected_array) / expected_array)),
    )


def _frame_energy_state_correlation(stem: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int, state_name: str) -> float:
    frame = min(2048, stem.shape[0])
    starts = _frame_starts(stem.shape[0], frame, frame)
    values = np.array([np.mean(np.square(stem[start : start + frame])) for start in starts])
    time_s = trace.time_s[0] + (starts + frame / 2.0) / sample_rate_hz
    state = np.interp(np.clip(time_s, trace.time_s[0], trace.time_s[-1]), trace.time_s, getattr(trace, state_name))
    if values.size < 2 or np.std(values) == 0.0 or np.std(state) == 0.0:
        return 0.0
    return float(np.clip(np.corrcoef(values, state)[0, 1], -1.0, 1.0))


def _integer_half_order_fractions(order_map: OrderMap) -> tuple[float, float]:
    energy = order_map.order_energy
    integer = float(energy[np.isclose(order_map.orders, np.round(order_map.orders))].sum())
    half = float(energy[np.isclose(order_map.orders % 1.0, 0.5)].sum())
    total = float(energy.sum())
    return (integer / total, half / total) if total else (0.0, 0.0)


def _frame_end_start_ratio(stem: np.ndarray, sample_rate_hz: int) -> float:
    frame = max(min(sample_rate_hz // 4, stem.shape[0] // 3), 1)
    start = float(np.mean(np.square(stem[:frame])))
    end = float(np.mean(np.square(stem[-frame:])))
    return float(end / start) if start > 1e-15 else (0.0 if end == 0.0 else float(end / 1e-15))


def _turbo_transition_time(turbo: np.ndarray, turbine: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int) -> float:
    combined = np.square(turbo) + np.square(turbine)
    frame = min(2048, combined.shape[0])
    starts = _frame_starts(combined.shape[0], frame, frame)
    energy = np.array([np.mean(combined[start : start + frame]) for start in starts])
    if not np.any(energy > 1e-15):
        return 0.0
    time_s = trace.time_s[0] + (starts + frame / 2.0) / sample_rate_hz
    time_s = np.clip(time_s, trace.time_s[0], trace.time_s[-1])
    eligible = (np.interp(time_s, trace.time_s, trace.rpm) >= 4300.0) & (
        np.interp(time_s, trace.time_s, trace.load) >= 0.35
    )
    active = np.flatnonzero(eligible & (energy >= 0.10 * float(energy.max())))
    return float(time_s[active[0]] - trace.time_s[0]) if active.size else 0.0


def _lift_decay_ratio(stem: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int) -> float:
    drops = np.flatnonzero(np.diff(trace.throttle) < -0.05)
    if not drops.size:
        return 0.0
    sample = int(round((trace.time_s[drops[0] + 1] - trace.time_s[0]) * sample_rate_hz))
    available = stem.shape[0] - sample
    if available < 2:
        return 0.0
    length = min(sample_rate_hz // 8, available // 2)
    if length < 1:
        return 0.0
    initial = float(np.mean(np.square(stem[sample : sample + length])))
    later = float(np.mean(np.square(stem[sample + length : sample + 2 * length])))
    return float(later / initial) if initial > 1e-15 else 0.0


def _unit_rms(signal: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(np.square(signal))))
    return signal / rms if rms > 1e-15 else signal.copy()


def _absolute_correlation(left: np.ndarray, right: np.ndarray) -> float:
    left_flat = left.ravel()
    right_flat = right.ravel()
    left_norm = float(np.linalg.norm(left_flat))
    right_norm = float(np.linalg.norm(right_flat))
    if left_norm <= 1e-15 or right_norm <= 1e-15:
        return 1.0 if left_norm <= 1e-15 and right_norm <= 1e-15 else 0.0
    return float(abs(np.dot(left_flat, right_flat) / (left_norm * right_norm)))


def _log_order_distance(left: np.ndarray, right: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int) -> float:
    left_energy = compute_order_map(left, trace, sample_rate_hz).order_energy
    right_energy = compute_order_map(right, trace, sample_rate_hz).order_energy
    return _log_order_cosine_distance(left_energy, right_energy)


def _log_order_cosine_distance(left_energy: np.ndarray, right_energy: np.ndarray) -> float:
    left_shape = _relative_db_shape(left_energy)
    right_shape = _relative_db_shape(right_energy)
    denominator = float(np.linalg.norm(left_shape) * np.linalg.norm(right_shape))
    cosine = float(np.dot(left_shape, right_shape) / denominator) if denominator else 1.0
    return float(np.clip(1.0 - cosine, 0.0, 2.0))


def _relative_db_shape(energy: np.ndarray) -> np.ndarray:
    peak = float(np.max(energy)) if energy.size else 0.0
    if peak <= 0.0:
        return np.zeros_like(energy)
    decibels = np.maximum(10.0 * np.log10(np.maximum(energy / peak, 1e-6)), -60.0)
    return decibels - float(np.mean(decibels))


def _frame_starts(sample_count: int, frame_size: int, hop_size: int) -> np.ndarray:
    starts = np.arange(0, max(sample_count - frame_size + 1, 1), hop_size, dtype=int)
    last = max(sample_count - frame_size, 0)
    return np.append(starts, last) if starts[-1] != last else starts


def _frame_spectrum(frame: np.ndarray, window: np.ndarray) -> np.ndarray:
    windowed = frame * np.asarray(window, dtype=np.float64).reshape(-1, 1)
    return np.square(np.abs(np.fft.rfft(windowed, axis=0))).sum(axis=1)
