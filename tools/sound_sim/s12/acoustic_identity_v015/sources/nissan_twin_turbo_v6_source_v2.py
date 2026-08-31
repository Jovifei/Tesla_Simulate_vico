"""Synthetic GT-R R35 inspired even-fire V6 twin-turbo source.

This module is intentionally independent of the legacy GT-R fixed-tone source.
It is an uncalibrated C/synthetic engineering voice, not an OEM recording or
OEM-calibrated reproduction.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_DEFAULTS = {
    "pulse_width_scale": 1.0,
    "bank_phase_offset_deg": 120.0,
    "primary_spool_tau_s": 0.12,
    "secondary_spool_tau_s": 0.25,
    "boost_attack_s": 0.09,
    "boost_release_s": 0.24,
    "wastegate_gain_scale": 1.0,
    "turbo_whistle_mix": 0.16,
}
_POSITIVE = {
    "pulse_width_scale",
    "primary_spool_tau_s",
    "secondary_spool_tau_s",
    "boost_attack_s",
    "boost_release_s",
    "wastegate_gain_scale",
    "turbo_whistle_mix",
}


def render_gtr_r35_v2(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render a finite pre-PTR C/synthetic GT-R R35 twin-turbo V6 source.

    The combustion source is an even-fire, three-events-per-revolution V6
    train. Turbo voices are generated from two independent spool histories and
    boost state; the wastegate stem is a throttle-lift BOV/wastegate transient.
    All order frequencies integrate instantaneous RPM, so no fixed-center tone
    is introduced by this source.
    """
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    parameters, requested = _parameters(overrides)
    count, time_s, rpm, load, throttle = _resample_trace(trace, sample_rate_hz)
    dt_s = 1.0 / sample_rate_hz
    engine_phase = np.cumsum(rpm) * dt_s / 60.0

    bank_a, bank_b, combined_envelope = _v6_event_envelopes(
        engine_phase, load, sample_rate_hz, parameters["pulse_width_scale"]
    )
    bank_offset_cycles = parameters["bank_phase_offset_deg"] / 360.0
    bank_b_phase = engine_phase + bank_offset_cycles

    # Tailpipe pressure follows the event train and moving engine orders. The
    # two banks remain separately phase-coupled rather than using a static tone.
    exhaust_mono = 0.105 * load * combined_envelope * (
        0.78 * np.sin(2.0 * np.pi * engine_phase * 3.0)
        + 0.34 * np.sin(2.0 * np.pi * engine_phase * 6.0)
        + 0.12 * np.sin(2.0 * np.pi * engine_phase * 9.0)
    )
    bank_a_orders = bank_a * (
        np.sin(2.0 * np.pi * engine_phase * 3.0)
        + 0.36 * np.sin(2.0 * np.pi * engine_phase * 6.0)
    )
    bank_b_orders = bank_b * (
        np.sin(2.0 * np.pi * bank_b_phase * 3.0)
        + 0.36 * np.sin(2.0 * np.pi * bank_b_phase * 6.0)
    )
    order_mono = 0.070 * load * (bank_a_orders + bank_b_orders)

    primary, secondary, boost, bov = _turbo_histories(
        rpm, load, throttle, sample_rate_hz, parameters
    )
    flow = _one_pole(0.08 + 0.92 * throttle, 0.035, sample_rate_hz)
    primary_cycles = np.cumsum((12.0 + 5.0 * boost) * rpm * dt_s / 60.0)
    secondary_cycles = np.cumsum((18.0 + 7.0 * boost) * rpm * dt_s / 60.0)
    whistle_mix = parameters["turbo_whistle_mix"]
    turbo_primary_mono = whistle_mix * flow * primary * (
        0.76 * np.sin(2.0 * np.pi * primary_cycles)
        + 0.24 * np.sin(2.0 * np.pi * primary_cycles * 2.0)
    )
    turbo_secondary_mono = 0.78 * whistle_mix * flow * secondary * (
        0.80 * np.sin(2.0 * np.pi * secondary_cycles + 0.31)
        + 0.20 * np.sin(2.0 * np.pi * secondary_cycles * 1.5)
    )
    bov_cycles = np.cumsum((520.0 + 1500.0 * boost + 900.0 * bov) * dt_s)
    wastegate_mono = parameters["wastegate_gain_scale"] * 0.22 * bov * (
        np.sin(2.0 * np.pi * bov_cycles)
        + 0.28 * np.sin(2.0 * np.pi * bov_cycles * 1.73)
    )
    mechanical_mono = 0.021 * (0.25 + 0.75 * load) * (
        0.70 * np.sin(2.0 * np.pi * engine_phase)
        + 0.22 * np.sin(2.0 * np.pi * engine_phase * 2.0)
        + 0.08 * np.sin(2.0 * np.pi * engine_phase * 4.0)
    )

    stems = {
        "exhaust": _stereo(exhaust_mono, 0.84),
        "order_family": _stereo(order_mono, 0.76),
        "turbo_primary": _stereo(turbo_primary_mono, 0.67),
        "turbo_secondary": _stereo(turbo_secondary_mono, 0.72),
        "wastegate": _stereo(wastegate_mono, 0.80),
        "mechanical": _stereo(mechanical_mono, 0.88),
    }
    pressure = sum(stems.values(), np.zeros((count, 2), dtype=np.float64))
    metrics = _response_metrics(
        time_s,
        stems,
        bank_a_orders,
        bank_b_orders,
        primary,
        secondary,
        boost,
    )
    lift_events = int(np.count_nonzero(np.diff(throttle) < -1e-9))
    render = SourceRender(
        pressure=pressure,
        stems=stems,
        diagnostics={
            "vehicle_id": "gtr_r35",
            "scope": "C/synthetic; uncalibrated; not OEM reproduction",
            "combustion_event_model": "even_fire_v6_3_events_per_revolution",
            "order_frequency_mode": "continuous_rpm_phase",
            "turbo_history_model": "primary_secondary_spool_load_boost",
            "transient_model": "throttle_lift_bov_wastegate_release",
            "primary_spool_peak": float(np.max(primary)),
            "secondary_spool_peak": float(np.max(secondary)),
            "boost_peak": float(np.max(boost)),
            "lift_event_count": lift_events,
            "response_metrics": metrics,
            "override_usage": {
                "requested": requested,
                "read": requested,
                "consumed": requested,
            },
            "candidate_source_overrides": dict(overrides or {}),
        },
    )
    return render.validate()


def _parameters(overrides: Mapping[str, float] | None) -> tuple[dict[str, float], list[str]]:
    if overrides is None:
        return dict(_DEFAULTS), []
    if not isinstance(overrides, Mapping):
        raise ValueError("overrides must be a mapping")
    requested = list(overrides)
    unknown = sorted(set(requested) - set(_DEFAULTS))
    if unknown:
        raise ValueError(f"unknown gtr v2 override: {unknown[0]}")
    result = dict(_DEFAULTS)
    for name in requested:
        value = float(overrides[name])
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
        if name in _POSITIVE and value <= 0.0:
            raise ValueError(f"{name} must be > 0")
        result[name] = value
    return result, requested


def _resample_trace(
    trace: VehicleStateTrace, sample_rate_hz: int
) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    duration_s = float(trace.time_s[-1] - trace.time_s[0])
    count = int(round(duration_s * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    return (
        count,
        time_s,
        np.interp(time_s, trace.time_s, trace.rpm),
        np.interp(time_s, trace.time_s, trace.load),
        np.interp(time_s, trace.time_s, trace.throttle),
    )


def _v6_event_envelopes(
    engine_phase: np.ndarray, load: np.ndarray, sample_rate_hz: int, pulse_width_scale: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    event_index = np.floor(engine_phase * 3.0).astype(np.int64)
    event_starts = np.flatnonzero(np.r_[True, np.diff(event_index) > 0])
    event_numbers = event_index[event_starts]
    combustion_drive = 0.28 + 0.72 * load
    bank_a_impulses = np.zeros(engine_phase.size, dtype=np.float64)
    bank_b_impulses = np.zeros(engine_phase.size, dtype=np.float64)
    bank_a_mask = event_numbers % 2 == 0
    bank_a_impulses[event_starts[bank_a_mask]] = combustion_drive[event_starts[bank_a_mask]]
    bank_b_impulses[event_starts[~bank_a_mask]] = combustion_drive[event_starts[~bank_a_mask]]
    decay_s = 0.006 * pulse_width_scale
    bank_a = _one_pole_impulse(bank_a_impulses, decay_s, sample_rate_hz)
    bank_b = _one_pole_impulse(bank_b_impulses, decay_s, sample_rate_hz)
    return bank_a, bank_b, bank_a + bank_b


def _turbo_histories(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    sample_rate_hz: int,
    parameters: Mapping[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    count = rpm.size
    primary = np.zeros(count, dtype=np.float64)
    secondary = np.zeros(count, dtype=np.float64)
    boost = np.zeros(count, dtype=np.float64)
    bov = np.zeros(count, dtype=np.float64)
    primary_target = load * throttle * np.clip((rpm - 1500.0) / 3000.0, 0.0, 1.0)
    secondary_gate = np.clip((rpm - 3800.0) / 1700.0, 0.0, 1.0)
    secondary_target = primary_target * secondary_gate
    dt_s = 1.0 / sample_rate_hz
    for index in range(1, count):
        primary[index] = primary[index - 1] + dt_s * (
            primary_target[index] - primary[index - 1]
        ) / parameters["primary_spool_tau_s"]
        secondary[index] = secondary[index - 1] + dt_s * (
            secondary_target[index] - secondary[index - 1]
        ) / parameters["secondary_spool_tau_s"]
        boost_target = 0.70 * primary[index] + 0.90 * secondary[index]
        boost_tau = (
            parameters["boost_attack_s"]
            if boost_target >= boost[index - 1]
            else parameters["boost_release_s"]
        )
        boost[index] = boost[index - 1] + dt_s * (boost_target - boost[index - 1]) / boost_tau
        lift = max(throttle[index - 1] - throttle[index], 0.0)
        bov[index] = bov[index - 1] * np.exp(-dt_s / 0.16) + lift * (
            0.25 + 0.75 * boost[index - 1]
        )
    return primary, secondary, boost, bov


def _one_pole_impulse(impulses: np.ndarray, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    result = np.zeros_like(impulses)
    pole = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    for index in range(1, result.size):
        result[index] = pole * result[index - 1] + impulses[index]
    return result


def _one_pole(target: np.ndarray, tau_s: float, sample_rate_hz: int) -> np.ndarray:
    result = np.empty_like(target)
    result[0] = target[0]
    coefficient = 1.0 / (tau_s * sample_rate_hz)
    for index in range(1, result.size):
        result[index] = result[index - 1] + coefficient * (target[index] - result[index - 1])
    return result


def _stereo(mono: np.ndarray, left_scale: float) -> np.ndarray:
    return np.column_stack((left_scale * mono, mono))


def _response_metrics(
    time_s: np.ndarray,
    stems: Mapping[str, np.ndarray],
    bank_a: np.ndarray,
    bank_b: np.ndarray,
    primary: np.ndarray,
    secondary: np.ndarray,
    boost: np.ndarray,
) -> dict[str, float]:
    return {
        "exhaust_event_energy": float(np.mean(np.square(stems["exhaust"]))),
        "bank_phase_correlation": _correlation(bank_a, bank_b),
        "primary_spool_50_time_s": _rise_time(time_s, primary, 0.50),
        "secondary_spool_50_time_s": _rise_time(time_s, secondary, 0.50),
        "boost_attack_63_time_s": _rise_time(time_s, boost, 0.63),
        "boost_release_37_time_s": _release_time(time_s, boost, 0.37),
        "wastegate_energy": float(np.mean(np.square(stems["wastegate"]))),
        "turbo_primary_rms": float(np.sqrt(np.mean(np.square(stems["turbo_primary"])))),
    }


def _correlation(a: np.ndarray, b: np.ndarray) -> float:
    a_centered = a - np.mean(a)
    b_centered = b - np.mean(b)
    denominator = np.sqrt(np.sum(a_centered * a_centered) * np.sum(b_centered * b_centered))
    return float(np.sum(a_centered * b_centered) / denominator) if denominator else 0.0


def _rise_time(time_s: np.ndarray, state: np.ndarray, fraction: float) -> float:
    peak = float(np.max(state))
    if peak <= 0.0:
        return 0.0
    return float(time_s[np.flatnonzero(state >= fraction * peak)[0]] - time_s[0])


def _release_time(time_s: np.ndarray, state: np.ndarray, fraction: float) -> float:
    peak_index = int(np.argmax(state))
    below = np.flatnonzero(state[peak_index:] <= fraction * state[peak_index])
    if below.size == 0:
        elapsed = float(time_s[-1] - time_s[peak_index])
        tail_fraction = float(state[-1] / state[peak_index])
        if 0.0 < tail_fraction < 1.0:
            return float(elapsed / -np.log(tail_fraction))
        return elapsed
    return float(time_s[peak_index + below[0]] - time_s[peak_index])
