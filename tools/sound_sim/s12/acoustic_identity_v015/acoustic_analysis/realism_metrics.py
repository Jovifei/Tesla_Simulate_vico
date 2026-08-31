"""State, body, and transient measurements for synthetic realism review."""

from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


def compute_realism_metrics(
    vehicle_id: str, render: SourceRender, trace: VehicleStateTrace, sample_rate_hz: int = 48000
) -> dict[str, object]:
    """Measure pre-PTR realism cues without presenting them as vehicle calibration."""
    _SUPPORTED = {
        "ferrari_458", "hellcat", "rx7_fd",
        "aventador_lp700", "c63_w204", "gtr_r35", "lfa", "supra_jza80",
    }
    if vehicle_id not in _SUPPORTED:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    render.validate()
    trace.validate()
    signal = np.asarray(render.pressure, dtype=np.float64).mean(axis=1)
    frequencies, energy = _spectrum(signal, sample_rate_hz)
    total = float(energy.sum())
    afterfire = _stem(render, "afterfire")
    idle_variation = _stem(render, "idle_combustion_variation")
    low_frequency = {
        "energy_fraction_40_200hz": _band_fraction(energy, frequencies, 40.0, 200.0),
        "energy_fraction_200_500hz": _band_fraction(energy, frequencies, 200.0, 500.0),
        "radiation_stem_energy": _energy(_stem(render, "radiation")),
    }
    band_shares = {
        "20_250hz": _band_fraction(energy, frequencies, 20.0, 250.0),
        "250_1000hz": _band_fraction(energy, frequencies, 250.0, 1000.0),
        "1_4khz": _band_fraction(energy, frequencies, 1000.0, 4000.0),
        "4_12khz": _band_fraction(energy, frequencies, 4000.0, 12000.0),
    }
    transients = {
        "afterfire_event_count": int(render.diagnostics.get("afterfire_event_count", 0)),
        "afterfire_stem_energy": _energy(afterfire),
        "afterfire_peak_to_rms": _peak_to_rms(afterfire),
        "afterfire_centroid_hz": float(render.diagnostics.get("afterfire_centroid_hz", 0.0) or 0.0),
        "afterfire_onset_s": render.diagnostics.get("afterfire_onset_s"),
        "afterfire_decay_ratio": float(render.diagnostics.get("afterfire_decay_ratio", 0.0) or 0.0),
        "rumble_energy_30_90hz": _band_energy(_stem(render, "exhaust_rumble"), sample_rate_hz, 30.0, 90.0),
        "shift_event_count": int(render.diagnostics.get("shift_event_count", 0)),
        "shift_impact_energy": float(render.diagnostics.get("shift_impact_energy", 0.0) or 0.0),
        "shift_recovery_boom_energy": float(render.diagnostics.get("shift_recovery_boom_energy", 0.0) or 0.0),
        "closed_throttle_fraction": float(np.mean(trace.throttle < 0.12)),
    }
    idle = {
        "combustion_variation_energy": _energy(idle_variation),
        "cycle_amplitude_std": float(render.diagnostics.get("idle_cycle_amplitude_std", 0.0)),
        "phase_jitter_samples_peak": float(render.diagnostics.get("idle_phase_jitter_samples_peak", 0.0)),
    }
    feature = {
        "spectral_centroid_hz": float(np.sum(frequencies * energy) / total) if total else 0.0,
        "crest_factor_db": _crest_factor_db(signal),
        "idle": idle,
        "low_frequency": low_frequency,
        "band_shares": band_shares,
        "transients": transients,
    }
    if vehicle_id == "ferrari_458":
        feature.update({"high_frequency_fraction_gt_1200hz": _band_fraction(energy, frequencies, 1200.0, None), "metallic_energy": _energy(_stem(render, "metallic"))})
    elif vehicle_id == "hellcat":
        feature.update({"blower_energy": _energy(_stem(render, "blower")), "blower_boost_state_peak": float(render.diagnostics.get("blower_boost_state_peak", 0.0)), "blower_bypass_state_peak": float(render.diagnostics.get("blower_bypass_state_peak", 0.0))})
    elif vehicle_id == "aventador_lp700":
        feature.update({"wail_energy": _energy(_stem(render, "wail"))})
    elif vehicle_id == "c63_w204":
        feature.update({"bark_energy": _energy(_stem(render, "bark")), "exhaust_bank_energy": _energy(_stem(render, "exhaust_left_bank")) + _energy(_stem(render, "exhaust_right_bank"))})
    elif vehicle_id == "gtr_r35":
        feature.update({"turbo_energy": _energy(_stem(render, "whistle")), "racy_energy": _energy(_stem(render, "racy"))})
    elif vehicle_id == "lfa":
        feature.update({"scream_energy": _energy(_stem(render, "scream"))})
    elif vehicle_id == "supra_jza80":
        feature.update({"turbo_energy": _energy(_stem(render, "whistle")), "edge_energy": _energy(_stem(render, "edge"))})
    else:
        feature.update({"rotary_energy": _energy(_stem(render, "rotary")), "turbo_energy": _energy(_stem(render, "turbo")), "blow_off_energy": _energy(_stem(render, "blow_off")), "boost_state_peak": float(render.diagnostics.get("boost_state_peak", 0.0))})
    return {
        "scope": "synthetic; uncalibrated; not OEM reproduction",
        "analysis_domain": "pre_ptr_source_with_stateful_realism_layers",
        "finite": bool(np.all(np.isfinite(signal)) and all(np.isfinite(value) for value in _numbers(feature))),
        "idle": idle,
        "low_frequency": low_frequency,
        "band_shares": band_shares,
        "transients": transients,
        "vehicle_features": {vehicle_id: feature},
    }


def _stem(render: SourceRender, name: str) -> np.ndarray:
    return np.asarray(render.stems.get(name, np.zeros_like(render.pressure)), dtype=np.float64)


def _energy(stereo: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(stereo, dtype=np.float64))))


def _band_energy(stereo: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    values = np.asarray(stereo, dtype=np.float64)
    if values.size == 0:
        return 0.0
    signal = values.mean(axis=1)
    energy = np.square(np.abs(np.fft.rfft(signal * np.hanning(signal.size))))
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    return float(energy[(frequencies >= low_hz) & (frequencies <= high_hz)].sum())


def _spectrum(signal: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    windowed = signal * np.hanning(signal.size)
    return np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz), np.square(np.abs(np.fft.rfft(windowed)))


def _band_fraction(energy: np.ndarray, frequencies: np.ndarray, low_hz: float, high_hz: float | None) -> float:
    mask = frequencies >= low_hz
    if high_hz is not None:
        mask &= frequencies <= high_hz
    total = float(energy.sum())
    return float(energy[mask].sum() / total) if total else 0.0


def _peak_to_rms(stereo: np.ndarray) -> float:
    values = np.asarray(stereo, dtype=np.float64)
    rms = float(np.sqrt(np.mean(np.square(values))))
    return float(np.max(np.abs(values)) / rms) if rms else 0.0


def _crest_factor_db(signal: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(signal))))
    return float(20.0 * np.log10(np.max(np.abs(signal)) / rms)) if rms else 0.0


def _numbers(value: object) -> list[float]:
    if isinstance(value, dict):
        return [number for item in value.values() for number in _numbers(item)]
    if isinstance(value, (float, int, np.floating, np.integer)):
        return [float(value)]
    return []
