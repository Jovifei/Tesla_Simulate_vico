"""Deterministic Stage-I Hellcat-inspired supercharger whine source."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender
from ..stage_i.whine_voicing import apply_intake_casing_voicing


_ORDER_FAMILIES = (2.36, 11.8, 23.6)
_DEFAULTS = {
    "blower_gain_scale": 1.18,
    "blower_boost_mix": 1.18,
    "lobe_family_mix": 1.12,
    "upper_family_tilt_db": -5.0,
    "sideband_depth": 0.14,
    "phase_ripple_depth": 0.004,
    "order_cluster_spread_ratio": 0.012,
    "intake_voicing_mix": 0.18,
    "boost_attack_s": 0.075,
    "boost_release_s": 0.24,
    "bypass_release_gain": 0.12,
    "bypass_pitch_fall_ratio": 0.80,
    "bypass_decay_s": 0.16,
}


def render_supercharger_whine_v3(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    engine_phase: np.ndarray,
    sample_rate_hz: int,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render moving order clusters, state envelope, and bypass release.

    All values remain C-level synthetic assumptions. No random or broadband
    excitation is used, and the result is intended for the shared Pre-PTR
    pipeline only.
    """
    requested = {} if overrides is None else dict(overrides)
    unknown = set(requested) - set(_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown supercharger override: {sorted(unknown)}")
    params = dict(_DEFAULTS)
    params.update({name: float(value) for name, value in requested.items()})
    _validate_inputs(rpm, load, throttle, engine_phase, sample_rate_hz, params)
    read_names: set[str] = set()

    def read_param(name: str) -> float:
        read_names.add(name)
        return float(params[name])

    rpm = np.maximum(np.asarray(rpm, dtype=np.float64), 0.0)
    load = np.clip(np.asarray(load, dtype=np.float64), 0.0, 1.0)
    throttle = np.clip(np.asarray(throttle, dtype=np.float64), 0.0, 1.0)
    engine_phase = np.asarray(engine_phase, dtype=np.float64)
    count = rpm.size

    boost_target = (
        load
        * throttle
        * np.clip((rpm - 1100.0) / 3800.0, 0.0, 1.15)
        * read_param("blower_boost_mix")
    )
    boost_state = _asymmetric_smoother(
        boost_target,
        read_param("boost_attack_s"),
        read_param("boost_release_s"),
        sample_rate_hz,
    )
    shift_gain = _shift_dip_and_rebuild(rpm, throttle, sample_rate_hz)
    rpm_factor = np.clip((rpm - 900.0) / 5200.0, 0.0, 1.0)
    load_factor = (0.10 + 0.90 * np.power(load, 1.12)) * (load > 0.0)
    throttle_factor = (0.14 + 0.86 * np.power(throttle, 1.08)) * (throttle > 0.0)
    envelope = (
        read_param("blower_gain_scale")
        * (0.08 + 0.92 * boost_state)
        * load_factor
        * throttle_factor
        * (0.20 + 0.80 * rpm_factor)
        * shift_gain
    )

    shaft_phase = np.cumsum(rpm * _ORDER_FAMILIES[0]) / (60.0 * sample_rate_hz)
    phase_ripple = read_param("phase_ripple_depth") * np.sin(2.0 * np.pi * 4.0 * engine_phase)
    shaft_phase = shaft_phase + phase_ripple
    spread = read_param("order_cluster_spread_ratio")
    shaft_mono = 0.20 * envelope * _moving_cluster(shaft_phase, spread)
    lobe_phase = 5.0 * shaft_phase
    lobe_mono = (
        0.58
        * read_param("lobe_family_mix")
        * envelope
        * _moving_cluster(lobe_phase, spread)
    )
    upper_phase = 10.0 * shaft_phase + 0.21
    upper_mono = (
        0.20
        * np.power(10.0, read_param("upper_family_tilt_db") / 20.0)
        * envelope
        * _moving_cluster(upper_phase, spread)
    )
    sideband_mono = envelope * (5.0 * read_param("sideband_depth")) * (
        0.30 * np.sin(2.0 * np.pi * (lobe_phase + 4.0 * engine_phase))
        + 0.30 * np.sin(2.0 * np.pi * (lobe_phase - 4.0 * engine_phase))
        + 0.12 * np.sin(2.0 * np.pi * (upper_phase + 4.0 * engine_phase))
        + 0.12 * np.sin(2.0 * np.pi * (upper_phase - 4.0 * engine_phase))
    )

    bypass_mono, bypass_events = _render_bypass_release(
        rpm,
        throttle,
        boost_state,
        sample_rate_hz,
        read_param("bypass_release_gain"),
        read_param("bypass_pitch_fall_ratio"),
        read_param("bypass_decay_s"),
    )
    stems = {
        "blower_shaft": _stereo(shaft_mono, 0.65),
        "blower_lobe_family": _stereo(lobe_mono, 0.65),
        "blower_upper_family": _stereo(upper_mono, 0.65),
        "blower_sidebands": _stereo(sideband_mono, 0.65),
        "blower_bypass_release": _stereo(bypass_mono, 0.70),
    }
    raw = sum(stems.values(), np.zeros((count, 2), dtype=np.float64))
    voiced, transfer_diagnostics = apply_intake_casing_voicing(
        raw, sample_rate_hz, read_param("intake_voicing_mix")
    )
    stems["blower_intake_voicing"] = voiced - raw
    aggregate = sum(stems.values(), np.zeros((count, 2), dtype=np.float64))
    stems["blower"] = aggregate

    requested_names = sorted(requested)
    read_requested = sorted(set(requested_names) & read_names)
    active_conditions = {
        "blower_gain_scale": _has_energy(aggregate),
        "blower_boost_mix": bool(np.any(np.abs(boost_target) > 1.0e-12)),
        "lobe_family_mix": _has_energy(stems["blower_lobe_family"]),
        "upper_family_tilt_db": _has_energy(stems["blower_upper_family"]),
        "sideband_depth": _has_energy(stems["blower_sidebands"]),
        "phase_ripple_depth": _has_energy(stems["blower_shaft"]),
        "order_cluster_spread_ratio": _has_energy(raw),
        "intake_voicing_mix": _has_energy(stems["blower_intake_voicing"]),
        "boost_attack_s": _attack_was_used(boost_target, boost_state),
        "boost_release_s": _release_was_used(boost_target, boost_state),
        "bypass_release_gain": bypass_events > 0 and _has_energy(stems["blower_bypass_release"]),
        "bypass_pitch_fall_ratio": bypass_events > 0 and _has_energy(stems["blower_bypass_release"]),
        "bypass_decay_s": bypass_events > 0 and _has_energy(stems["blower_bypass_release"]),
    }
    active_names = sorted(name for name in read_requested if active_conditions[name])
    inactive_names = sorted(set(read_requested) - set(active_names))
    diagnostics = {
        "vehicle_id": "hellcat",
        "scope": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        "order_families": _ORDER_FAMILIES,
        "blower_dynamic_model": "stage_i_moving_clusters_state_envelope_transfer_and_bypass",
        "boost_attack_s": params["boost_attack_s"],
        "boost_release_s": params["boost_release_s"],
        "boost_state_peak": float(np.max(boost_state)) if count else 0.0,
        "bypass_event_count": int(bypass_events),
        "bypass_energy": float(np.sum(np.square(stems["blower_bypass_release"]))),
        "blower_energy": float(np.sum(np.square(aggregate))),
        "shift_gain_min": float(np.min(shift_gain)) if count else 1.0,
        "transfer_modes": transfer_diagnostics,
        "pipeline_position": "before_pre_ptr_equalization",
        "candidate_source_overrides": dict(requested),
        "candidate_parameter_usage": {
            "requested": requested_names,
            "read": read_requested,
            "configured": read_requested,
            "active": active_names,
            "inactive": inactive_names,
            "consumed": read_requested,
            "unused": sorted(set(requested_names) - set(read_requested)),
        },
    }
    return SourceRender(pressure=aggregate, stems=stems, diagnostics=diagnostics).validate()


def _has_energy(signal: np.ndarray) -> bool:
    return bool(np.any(np.abs(np.asarray(signal, dtype=np.float64)) > 1.0e-12))


def _attack_was_used(target: np.ndarray, state: np.ndarray) -> bool:
    return bool(target.size > 1 and np.any(target[1:] >= state[:-1] + 1.0e-12))


def _release_was_used(target: np.ndarray, state: np.ndarray) -> bool:
    return bool(target.size > 1 and np.any(target[1:] < state[:-1] - 1.0e-12))


def _validate_inputs(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    engine_phase: np.ndarray,
    sample_rate_hz: int,
    params: Mapping[str, float],
) -> None:
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    arrays = tuple(np.asarray(value, dtype=np.float64) for value in (rpm, load, throttle, engine_phase))
    if any(value.ndim != 1 for value in arrays) or len({value.size for value in arrays}) != 1:
        raise ValueError("supercharger inputs must be equal-length one-dimensional arrays")
    if any(not np.all(np.isfinite(value)) for value in arrays):
        raise ValueError("supercharger inputs must be finite")
    if any(not np.isfinite(value) for value in params.values()):
        raise ValueError("supercharger overrides must be finite")
    if params["boost_attack_s"] <= 0.0 or params["boost_release_s"] <= 0.0 or params["bypass_decay_s"] <= 0.0:
        raise ValueError("supercharger time constants must be positive")
    if not 0.0 < params["bypass_pitch_fall_ratio"] <= 1.0:
        raise ValueError("bypass_pitch_fall_ratio must be in (0, 1]")
    if not 0.0 <= params["intake_voicing_mix"] <= 1.0:
        raise ValueError("intake_voicing_mix must be in [0, 1]")


def _asymmetric_smoother(
    target: np.ndarray, attack_s: float, release_s: float, sample_rate_hz: int
) -> np.ndarray:
    state = np.zeros_like(target)
    for index in range(1, target.size):
        tau = attack_s if target[index] >= state[index - 1] else release_s
        state[index] = state[index - 1] + (target[index] - state[index - 1]) / max(tau * sample_rate_hz, 1.0)
    return state


def _moving_cluster(phase: np.ndarray, spread: float) -> np.ndarray:
    return (
        0.68 * np.sin(2.0 * np.pi * phase)
        + 0.16 * np.sin(2.0 * np.pi * phase * (1.0 - spread) - 0.31)
        + 0.16 * np.sin(2.0 * np.pi * phase * (1.0 + spread) + 0.37)
    )


def _shift_dip_and_rebuild(
    rpm: np.ndarray, throttle: np.ndarray, sample_rate_hz: int
) -> np.ndarray:
    gain = np.ones_like(rpm)
    if rpm.size < 2:
        return gain
    derivative = np.gradient(rpm) * sample_rate_hz
    events = np.flatnonzero((derivative < -1500.0) & (throttle > 0.30))
    refractory = int(0.35 * sample_rate_hz)
    last = -refractory
    for event in events:
        if event - last < refractory:
            continue
        last = int(event)
        end = min(rpm.size, event + int(0.18 * sample_rate_hz))
        local = np.arange(end - event, dtype=np.float64) / sample_rate_hz
        gain[event:end] *= 1.0 - 0.58 * np.exp(-local / 0.055)
    return gain


def _render_bypass_release(
    rpm: np.ndarray,
    throttle: np.ndarray,
    boost_state: np.ndarray,
    sample_rate_hz: int,
    gain: float,
    pitch_fall_ratio: float,
    decay_s: float,
) -> tuple[np.ndarray, int]:
    result = np.zeros_like(rpm)
    closed = throttle < 0.25
    onsets = np.flatnonzero(np.diff(closed.astype(np.int8), prepend=0) > 0)
    events = 0
    for onset in onsets:
        history = float(boost_state[onset - 1]) if onset > 0 else 0.0
        if history <= 1.0e-4:
            continue
        events += 1
        length = min(rpm.size - onset, max(1, int(5.0 * decay_s * sample_rate_hz)))
        local_s = np.arange(length, dtype=np.float64) / sample_rate_hz
        # The bypass tail carries both its own valve decay and the compressor's
        # release state. This makes ``boost_release_s`` a real time-domain
        # control instead of a reported-but-inaudible field.
        boost_tail = np.clip(
            boost_state[onset : onset + length] / max(history, 1.0e-12),
            0.0,
            1.0,
        )
        envelope = gain * history * np.exp(-local_s / decay_s) * (0.45 + 0.55 * boost_tail)
        fall = pitch_fall_ratio + (1.0 - pitch_fall_ratio) * np.exp(-local_s / decay_s)
        frequency_hz = rpm[onset : onset + length] / 60.0 * _ORDER_FAMILIES[1] * fall
        phase = np.cumsum(frequency_hz) / sample_rate_hz
        result[onset : onset + length] += envelope * np.sin(2.0 * np.pi * phase + 0.63)
    return result, events


def _stereo(mono: np.ndarray, left_scale: float) -> np.ndarray:
    return np.column_stack((float(left_scale) * mono, mono))


__all__ = ("render_supercharger_whine_v3",)
