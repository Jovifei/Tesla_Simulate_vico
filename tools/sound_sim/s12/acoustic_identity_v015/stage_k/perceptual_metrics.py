"""Deterministic Stage-K perceptual and health metrics.

The functions in this module intentionally accept duck-typed ``SourceRender``
and ``VehicleStateTrace`` objects.  That keeps the analysis usable for offline
probes and for the formal contracts without coupling it to a renderer.  All
values are synthetic engineering diagnostics: they are not OEM measurements,
calibration, or a human-realism verdict.
"""

from __future__ import annotations

from collections.abc import Mapping
import math

import numpy as np


BANDS_HZ = (
    ("20_250", 20.0, 250.0),
    ("250_1000", 250.0, 1000.0),
    ("1000_4000", 1000.0, 4000.0),
    ("4000_12000", 4000.0, 12000.0),
)

_VEHICLE_ORDERS: dict[str, tuple[float, ...]] = {
    "hellcat": (2.36, 11.8, 23.6),
    "c63_w204": (7.6,),
    "gtr_r35": (3.0, 8.0, 12.0),
    "lfa": (5.0, 10.0, 15.0),
}


def compute_stage_k_perceptual_metrics(
    render: object,
    trace: object,
    sample_rate_hz: int = 48000,
    *,
    vehicle_id: str | None = None,
    state_masks: Mapping[str, np.ndarray] | None = None,
) -> dict[str, object]:
    """Return common and vehicle-specific final/source-domain diagnostics.

    Sparse state traces are interpolated onto the rendered audio grid.  Empty
    inferred state windows are represented by zero metrics rather than being
    silently filled with a different state.  This makes missing reference
    windows visible to callers while keeping probe analysis deterministic.
    """

    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    pressure = _stereo_array(getattr(render, "pressure", None), "pressure")
    stems = getattr(render, "stems", None)
    if not isinstance(stems, Mapping):
        raise ValueError("render.stems must be a mapping")
    normalized_stems = {str(name): _stereo_array(value, f"stem {name}") for name, value in stems.items()}
    for name, value in normalized_stems.items():
        if value.shape != pressure.shape:
            raise ValueError(f"stem {name!r} must match pressure shape")
    if not np.all(np.isfinite(pressure)) or any(not np.all(np.isfinite(value)) for value in normalized_stems.values()):
        raise ValueError("render arrays must be finite")

    rpm, load, throttle = _audio_state(trace, pressure.shape[0], sample_rate_hz)
    masks = _state_masks(state_masks, rpm, load, throttle, sample_rate_hz)
    mono = np.mean(pressure, axis=1)
    rms_by_state = {name: _rms(mono[mask]) for name, mask in masks.items()}
    lufs_by_state = {name: _synthetic_lufs(value) for name, value in rms_by_state.items()}
    low = lufs_by_state.get("low_load", 0.0)
    high = lufs_by_state.get("high_load", 0.0)
    frequencies, power = _spectrum(mono, sample_rate_hz)
    shares = {name: _band_share(frequencies, power, low_hz, high_hz) for name, low_hz, high_hz in BANDS_HZ}
    resolved_vehicle = vehicle_id or _vehicle_id(getattr(render, "diagnostics", {}))
    expected_orders = _VEHICLE_ORDERS.get(resolved_vehicle, ())
    order_error, order_measured = _order_ridge_error(mono, rpm, expected_orders, sample_rate_hz)
    pcm_health = _pcm_health(pressure, getattr(render, "diagnostics", {}), sample_rate_hz)
    transition = _transition_metrics(mono, rpm, throttle, sample_rate_hz)
    common: dict[str, object] = {
        "vehicle_id": resolved_vehicle,
        "state_rms": rms_by_state,
        "state_lufs": lufs_by_state,
        "low_load_high_load_delta_db": float(high - low),
        "band_shares": shares,
        "spectral_centroid_hz": _spectral_centroid(frequencies, power),
        "order_ridge_error": order_error,
        "order_ridge_measured": order_measured,
        "tonal_prominence": _tonal_prominence(power, frequencies),
        "spectral_roughness": _spectral_roughness(mono, sample_rate_hz),
        "event_inter_onset_interval_s": _event_inter_onset(mono, sample_rate_hz)[0],
        "event_inter_onset_cv": _event_inter_onset(mono, sample_rate_hz)[1],
        "event_count": _event_inter_onset(mono, sample_rate_hz)[2],
        "transition_dip_db": transition["dip_db"],
        "transition_overshoot_db": transition["overshoot_db"],
        "transition_settling_s": transition["settling_s"],
        "pcm_health": pcm_health,
        "final_pcm_health": pcm_health,
        "sample_rate_hz": sample_rate_hz,
        "scope": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    diagnostics = getattr(render, "diagnostics", {})
    vehicle_metrics = _vehicle_metrics(resolved_vehicle, normalized_stems, pressure, rpm, load, throttle, masks, sample_rate_hz, diagnostics)
    common["vehicle_metrics"] = vehicle_metrics
    # Flat aliases make report JSON easy to consume and retain the nested
    # structure for callers that need to distinguish common metrics.
    common.update({f"{resolved_vehicle}.{key}": value for key, value in vehicle_metrics.items()})
    return common


def evaluate_stage_k_hard_gates(
    metrics: Mapping[str, object],
    vehicle_id: str | None = None,
    parent_metrics: Mapping[str, object] | None = None,
) -> dict[str, bool]:
    """Evaluate fixed Stage-K health/identity gates fail-closed.

    Missing or malformed evidence produces a false gate, never an inferred
    pass.  Reference-distance's 30% target is intentionally not calculated or
    altered here; the caller supplies that independent evidence.
    """

    health = metrics.get("pcm_health")
    gates: dict[str, bool] = {
        "pcm_finite": isinstance(health, Mapping) and health.get("finite") is True,
        "pcm_clipping": isinstance(health, Mapping) and _number(health.get("clipping_count"), default=1.0) == 0.0,
        "pcm_peak": isinstance(health, Mapping) and _number(health.get("peak_dbfs"), default=0.0) <= -1.5,
        "pcm_format": isinstance(health, Mapping)
        and _number(health.get("sample_rate_hz"), default=-1.0) == 48000.0
        and _number(health.get("channels"), default=-1.0) == 2.0
        and _number(health.get("pcm_bits"), default=-1.0) == 24.0,
    }
    band = metrics.get("band_shares")
    if isinstance(band, Mapping):
        gates["upper_band_share"] = _number(band.get("4000_12000"), default=1.0) <= 0.06
    else:
        gates["upper_band_share"] = False
    gates["finite_metrics"] = _all_numeric_finite(metrics)
    if vehicle_id is not None:
        vehicle = metrics.get("vehicle_metrics")
        gates.update(_vehicle_gate_values(vehicle_id, vehicle, metrics, parent_metrics))
    supplied = metrics.get("hard_gates")
    if isinstance(supplied, Mapping):
        for name, value in supplied.items():
            gates[f"supplied_{name}"] = value is True
    gates["all_pass"] = bool(gates) and all(gates.values())
    return gates


def _vehicle_metrics(
    vehicle_id: str,
    stems: Mapping[str, np.ndarray],
    pressure: np.ndarray,
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    masks: Mapping[str, np.ndarray],
    sample_rate_hz: int,
    diagnostics: object,
) -> dict[str, float | int]:
    stem = lambda name: stems.get(name, np.zeros_like(pressure))
    if vehicle_id == "hellcat":
        main = _energy(stem("blower_shaft")) + _energy(stem("blower_rotor_family")) + _energy(stem("blower_upper_family"))
        sideband = stem("blower_sidebands")
        # Stage-K v4 defines the field in the output domain as an RMS ratio.
        # Keep the energy-domain diagnostics elsewhere, but do not square this
        # contract a second time when evaluating the hard gate.
        sideband_rms = _rms(sideband)
        main_rms = _rms(stem("blower_shaft") + stem("blower_rotor_family") + stem("blower_gear_casing"))
        return {
            "blower_exhaust_ratio_db": _energy_db_ratio(stem("blower"), stem("exhaust")),
            "blower_exhaust_ratio_acceleration_db": _masked_energy_db_ratio(stem("blower"), stem("exhaust"), masks.get("acceleration")),
            "blower_load_correlation": _state_correlation(stem("blower"), load * throttle, sample_rate_hz),
            "sideband_main_ratio": sideband_rms / max(main_rms, 1.0e-18),
            "shaft_order_error": _order_ridge_error(np.mean(stem("blower_shaft"), axis=1), rpm, (2.36,), sample_rate_hz)[0],
            "lobe_order_error": _order_ridge_error(np.mean(stem("blower_rotor_family"), axis=1), rpm, (11.8,), sample_rate_hz)[0],
            "rumble_energy": _energy(stem("exhaust_rumble")),
        }
    if vehicle_id == "c63_w204":
        bark = stem("bark")
        upper = stems.get("bark_upper_partial")
        if upper is None:
            # v3 exposes bark_primary and the total bark event.  The residual
            # is the named upper-partial energy and keeps the metric tied to
            # the actual Stage-K source contract without adding an alias stem.
            upper = bark - stem("bark_primary")
        return {
            "bark_upper_partial_ratio": _energy(upper) / max(_energy(bark), 1.0e-18),
            "roughness": _spectral_roughness(np.mean(pressure, axis=1), sample_rate_hz),
            "upper_band_short_time_peak": _short_time_band_peak(pressure, sample_rate_hz, 4000.0, 12000.0),
            "low_frequency_share_40_200hz": _band_share(*_spectrum(np.mean(pressure, axis=1), sample_rate_hz), 40.0, 200.0),
        }
    if vehicle_id == "gtr_r35":
        shaft_a = stems.get("turbo_a_shaft", stem("turbo_primary"))
        shaft_b = stems.get("turbo_b_shaft", stem("turbo_secondary"))
        turbo = stems.get("turbo")
        if turbo is None:
            turbo = shaft_a + shaft_b + stem("turbo_sidebands") + stem("intake_duct")
        return {
            "bank_phase_offset_deg": _diagnostic_number(diagnostics, "bank_phase_offset_deg", 120.0),
            "turbo_a_activity": _rms(np.mean(shaft_a, axis=1)),
            "turbo_b_activity": _rms(np.mean(shaft_b, axis=1)),
            "shaft_bpf_ridge_error": _order_ridge_error(np.mean(turbo, axis=1), rpm, (8.0,), sample_rate_hz)[0],
            "boost_history_release_energy": _energy(stem("bov")) + _energy(stem("wastegate")),
            "turbo_exhaust_ratio_db": _energy_db_ratio(turbo, stem("exhaust")),
        }
    if vehicle_id == "lfa":
        return {
            "shift_dip_db": _transition_metrics(np.mean(stem("lfa_shift_torque_cut"), axis=1), rpm, throttle, sample_rate_hz)["dip_db"],
            "shift_settling_s": _transition_metrics(np.mean(stem("lfa_shift_exhaust_reengagement"), axis=1), rpm, throttle, sample_rate_hz)["settling_s"],
            "lift_decay_s": _decay_time(np.mean(stem("lfa_intake_lift_decay"), axis=1), throttle, sample_rate_hz),
            "overrun_energy": _energy(stem("lfa_overrun")),
            "order_5_10_15_preservation": _order_family_presence(pressure, rpm, (5.0, 10.0, 15.0), sample_rate_hz),
        }
    return {}


def _vehicle_gate_values(vehicle_id: str, vehicle: object, metrics: Mapping[str, object], parent: Mapping[str, object] | None) -> dict[str, bool]:
    if not isinstance(vehicle, Mapping):
        return {"vehicle_metrics_present": False}
    result: dict[str, bool] = {"vehicle_metrics_present": True}
    if vehicle_id == "hellcat":
        result.update({
            "hellcat_load_correlation": _number(vehicle.get("blower_load_correlation"), default=0.0) >= 0.82,
            "hellcat_sideband_ratio": 0.08 <= _number(vehicle.get("sideband_main_ratio"), default=-1.0) <= 0.18,
            "hellcat_order": _number(vehicle.get("shaft_order_error"), default=1.0) <= 0.01 and _number(vehicle.get("lobe_order_error"), default=1.0) <= 0.01,
        })
    elif vehicle_id == "c63_w204":
        result["c63_roughness_present"] = math.isfinite(_number(vehicle.get("roughness"), default=float("nan")))
    elif vehicle_id == "gtr_r35":
        result["gtr_two_shafts_active"] = _number(vehicle.get("turbo_a_activity"), default=0.0) > 0.0 and _number(vehicle.get("turbo_b_activity"), default=0.0) > 0.0
    elif vehicle_id == "lfa":
        result["lfa_order_preserved"] = _number(vehicle.get("order_5_10_15_preservation"), default=0.0) > 0.0
    if parent is not None:
        regression = metrics.get("state_regression", {})
        if isinstance(regression, Mapping):
            result["state_regression"] = all(abs(_number(value, default=100.0)) <= 0.10 for value in regression.values())
        else:
            result["state_regression"] = False
    return result


def _audio_state(trace: object, count: int, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_s = _array(getattr(trace, "time_s", None), "trace.time_s")
    if time_s.size == 0 or np.any(np.diff(time_s) <= 0.0):
        raise ValueError("trace.time_s must be strictly increasing")
    values = []
    target_time = float(time_s[0]) + np.arange(count, dtype=np.float64) / float(sample_rate_hz)
    for name in ("rpm", "load", "throttle"):
        value = _array(getattr(trace, name, None), f"trace.{name}")
        if value.size != time_s.size:
            raise ValueError("trace arrays must have equal length")
        values.append(np.interp(target_time, time_s, value))
    return values[0], np.clip(values[1], 0.0, 1.0), np.clip(values[2], 0.0, 1.0)


def _state_masks(
    provided: Mapping[str, np.ndarray] | None,
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    sample_rate_hz: int,
) -> dict[str, np.ndarray]:
    if provided is not None:
        result = {}
        for name, value in provided.items():
            mask = np.asarray(value, dtype=bool)
            if mask.ndim != 1 or mask.size != rpm.size:
                raise ValueError(f"state mask {name!r} must match rendered sample count")
            result[str(name)] = mask
        return result
    derivative = np.gradient(rpm) * float(sample_rate_hz) if rpm.size > 1 else np.zeros_like(rpm)
    redline = max(float(np.max(rpm)), 1.0)
    return {
        "idle": (rpm <= 1400.0) & (load <= 0.30) & (throttle <= 0.30),
        "low_load": load <= 0.30,
        "high_load": load >= 0.70,
        "acceleration": (derivative > 0.0) & (load >= 0.30),
        "full_pull": (rpm >= 0.70 * redline) & (load >= 0.70),
        "lift": throttle <= 0.20,
    }


def _stereo_array(value: object, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim == 1:
        array = np.column_stack((array, array))
    if array.ndim != 2 or array.shape[1] != 2 or array.shape[0] == 0:
        raise ValueError(f"{name} must be a non-empty [N, 2] array")
    return array


def _array(value: object, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    return result


def _vehicle_id(diagnostics: object) -> str:
    return str(diagnostics.get("vehicle_id", "unknown")) if isinstance(diagnostics, Mapping) else "unknown"


def _spectrum(audio: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    mono = np.asarray(audio, dtype=np.float64)
    window = np.hanning(mono.size) if mono.size > 1 else np.ones_like(mono)
    spectrum = np.fft.rfft(mono * window)
    return np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz), np.square(np.abs(spectrum))


def _band_share(frequencies: np.ndarray, power: np.ndarray, low_hz: float, high_hz: float) -> float:
    selected = (frequencies >= low_hz) & (frequencies < high_hz)
    total = float(np.sum(power))
    return float(np.sum(power[selected]) / total) if total > 0.0 else 0.0


def _spectral_centroid(frequencies: np.ndarray, power: np.ndarray) -> float:
    total = float(np.sum(power))
    return float(np.sum(frequencies * power) / total) if total > 0.0 else 0.0


def _tonal_prominence(power: np.ndarray, frequencies: np.ndarray) -> float:
    selected = power[(frequencies >= 100.0) & (frequencies <= 8_000.0)]
    if selected.size == 0:
        return 0.0
    return float(np.max(selected) / max(float(np.median(selected)), 1.0e-18))


def _spectral_roughness(audio: np.ndarray, sample_rate_hz: int) -> float:
    if audio.size < 128:
        return 0.0
    frame = min(2048, audio.size)
    hop = max(frame // 2, 1)
    values: list[float] = []
    for start in range(0, audio.size - frame + 1, hop):
        power = np.square(np.abs(np.fft.rfft(audio[start:start + frame] * np.hanning(frame))))
        log_power = np.log1p(power)
        scale = max(float(np.mean(log_power)), 1.0e-18)
        values.append(float(np.mean(np.abs(np.diff(log_power))) / scale))
    return float(np.mean(values)) if values else 0.0


def _order_ridge_error(audio: np.ndarray, rpm: np.ndarray, expected: tuple[float, ...], sample_rate_hz: int) -> tuple[float, float]:
    if not expected or audio.size < 128:
        return float("inf"), float("nan")
    frame = min(4096, audio.size)
    hop = max(frame // 2, 1)
    errors: list[float] = []
    measured: list[float] = []
    for start in range(0, audio.size - frame + 1, hop):
        center = min(start + frame // 2, rpm.size - 1)
        frequencies, power = _spectrum(audio[start:start + frame], sample_rate_hz)
        engine_hz = max(float(rpm[center]) / 60.0, 1.0)
        candidates = []
        for order in expected:
            target = order * engine_hz
            band = (frequencies >= 0.90 * target) & (frequencies <= 1.10 * target)
            if np.any(band):
                index = np.flatnonzero(band)[int(np.argmax(power[band]))]
                candidates.append((abs(frequencies[index] - target) / target, frequencies[index] / engine_hz))
        if candidates:
            error, order = min(candidates, key=lambda item: item[0])
            errors.append(float(error))
            measured.append(float(order))
    return (float(np.mean(errors)), float(np.mean(measured))) if errors else (float("inf"), float("nan"))


def _order_family_presence(audio: np.ndarray, rpm: np.ndarray, orders: tuple[float, ...], sample_rate_hz: int) -> float:
    error, _ = _order_ridge_error(np.mean(audio, axis=1) if audio.ndim == 2 else audio, rpm, orders, sample_rate_hz)
    return float(max(0.0, 1.0 - error)) if np.isfinite(error) else 0.0


def _event_inter_onset(audio: np.ndarray, sample_rate_hz: int) -> tuple[float, float, int]:
    envelope = np.convolve(np.abs(audio), np.ones(max(int(0.005 * sample_rate_hz), 1)) / max(int(0.005 * sample_rate_hz), 1), mode="same")
    threshold = max(float(np.percentile(envelope, 90.0)), 1.0e-12)
    active = envelope >= threshold
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    if starts.size < 2:
        return 0.0, 0.0, int(starts.size)
    intervals = np.diff(starts).astype(np.float64) / sample_rate_hz
    mean = float(np.mean(intervals))
    return mean, float(np.std(intervals) / mean) if mean > 0.0 else 0.0, int(starts.size)


def _transition_metrics(audio: np.ndarray, rpm: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    if rpm.size < 3:
        return {"dip_db": 0.0, "overshoot_db": 0.0, "settling_s": 0.0}
    derivative = np.gradient(rpm) * sample_rate_hz
    events = np.flatnonzero((derivative < -1500.0) & (throttle > 0.30))
    if events.size == 0:
        return {"dip_db": 0.0, "overshoot_db": 0.0, "settling_s": 0.0}
    center = int(events[0])
    envelope = np.convolve(np.abs(audio), np.ones(max(int(0.01 * sample_rate_hz), 1)) / max(int(0.01 * sample_rate_hz), 1), mode="same")
    before = max(float(np.mean(envelope[max(center - int(0.08 * sample_rate_hz), 0):center])), 1.0e-12)
    after = envelope[center:min(center + int(0.35 * sample_rate_hz), envelope.size)]
    if after.size == 0:
        return {"dip_db": 0.0, "overshoot_db": 0.0, "settling_s": 0.0}
    dip = float(20.0 * np.log10(max(float(np.min(after)), 1.0e-12) / before))
    overshoot = float(max(0.0, 20.0 * np.log10(max(float(np.max(after)), 1.0e-12) / before)))
    hits = np.flatnonzero(after >= 0.90 * before)
    settling = float(hits[0] / sample_rate_hz) if hits.size else 0.35
    return {"dip_db": dip, "overshoot_db": overshoot, "settling_s": settling}


def _short_time_band_peak(audio: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    frame = min(4096, audio.shape[0])
    if frame < 64:
        return 0.0
    mono = np.mean(audio, axis=1) if audio.ndim == 2 else audio
    total = max(float(np.sum(np.square(mono))), 1.0e-18)
    frequencies = np.fft.rfftfreq(frame, 1.0 / sample_rate_hz)
    mask = (frequencies >= low_hz) & (frequencies <= high_hz)
    peaks = []
    for start in range(0, mono.size - frame + 1, max(frame // 2, 1)):
        power = np.square(np.abs(np.fft.rfft(mono[start:start + frame] * np.hanning(frame))))
        peaks.append(float(np.sum(power[mask])))
    return float(max(peaks, default=0.0) / total)


def _decay_time(audio: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> float:
    transitions = np.flatnonzero((throttle[1:] < 0.15) & (throttle[:-1] >= 0.30))
    if transitions.size == 0:
        return 0.0
    start = int(transitions[0] + 1)
    envelope = np.abs(audio)
    peak = max(float(np.max(envelope[start:])), 1.0e-12)
    hits = np.flatnonzero(envelope[start:] <= 0.10 * peak)
    return float(hits[0] / sample_rate_hz) if hits.size else 0.0


def _state_correlation(audio: np.ndarray, state: np.ndarray, sample_rate_hz: int) -> float:
    mono = np.mean(audio, axis=1) if audio.ndim == 2 else audio
    frame = max(int(0.02 * sample_rate_hz), 1)
    count = mono.size // frame
    if count < 2:
        return 0.0
    energy = np.asarray([np.mean(np.square(mono[i * frame:(i + 1) * frame])) for i in range(count)])
    values = np.asarray([np.mean(state[i * frame:(i + 1) * frame]) for i in range(count)])
    active = values >= 0.20
    if np.count_nonzero(active) < 2 or np.std(energy[active]) <= 0.0 or np.std(values[active]) <= 0.0:
        return 0.0
    return float(np.corrcoef(np.log(np.maximum(energy[active], 1.0e-18)), values[active])[0, 1])


def _masked_energy_db_ratio(numerator: np.ndarray, denominator: np.ndarray, mask: np.ndarray | None) -> float:
    if mask is None or mask.size != numerator.shape[0] or not np.any(mask):
        return 0.0
    return _energy_db_ratio(numerator[mask], denominator[mask])


def _energy_db_ratio(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(10.0 * np.log10(max(_energy(numerator), 1.0e-18) / max(_energy(denominator), 1.0e-18)))


def _energy(value: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(value, dtype=np.float64))))


def _rms(value: np.ndarray) -> float:
    array = np.asarray(value, dtype=np.float64)
    return float(np.sqrt(np.mean(np.square(array)))) if array.size else 0.0


def _synthetic_lufs(rms: float) -> float:
    return float(20.0 * np.log10(max(float(rms), 1.0e-12)))


def _pcm_health(pressure: np.ndarray, diagnostics: object, sample_rate_hz: int) -> dict[str, object]:
    peak = float(np.max(np.abs(pressure))) if pressure.size else 0.0
    metadata = diagnostics if isinstance(diagnostics, Mapping) else {}
    bits = _number(metadata.get("pcm_bits"), default=24.0)
    return {
        "finite": bool(np.all(np.isfinite(pressure))),
        "clipping_count": int(np.count_nonzero(np.abs(pressure) >= 1.0)),
        "peak_dbfs": float(20.0 * np.log10(max(peak, 1.0e-12))),
        "sample_rate_hz": float(sample_rate_hz),
        "channels": 2.0,
        "pcm_bits": bits,
    }


def _number(value: object, *, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return float(default)


def _diagnostic_number(diagnostics: object, key: str, default: float) -> float:
    value = diagnostics.get(key) if isinstance(diagnostics, Mapping) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) else float(default)


def _all_numeric_finite(value: object) -> bool:
    if isinstance(value, Mapping):
        return all(_all_numeric_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_all_numeric_finite(item) for item in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    return True


__all__ = (
    "BANDS_HZ",
    "compute_stage_k_metrics",
    "compute_stage_k_perceptual_metrics",
    "evaluate_stage_k_gates",
    "evaluate_stage_k_hard_gates",
)

# Short aliases used by offline qualification scripts.  Keeping these as
# direct aliases avoids divergent metric implementations across reports.
compute_stage_k_metrics = compute_stage_k_perceptual_metrics
evaluate_stage_k_gates = evaluate_stage_k_hard_gates
