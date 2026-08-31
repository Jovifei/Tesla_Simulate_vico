"""Synthetic GT-R R35 parallel twin-turbo V6 source (Stage K v3).

This module is an offline, C-level vehicle-inspired source.  It is deliberately
separate from the Stage-J source because the two turbochargers are represented
as concurrent shaft states rather than as a primary/secondary RPM gate.  The
turbo frequencies come from integrated shaft phase and a synthetic blade-pass
family; engine RPM is used only as one input to the exhaust-power drive, never
as a direct turbo oscillator.  No value here is an OEM measurement.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_DEFAULTS: dict[str, float] = {
    "pulse_width_scale": 1.0,
    "bank_phase_offset_deg": 120.0,
    "primary_spool_tau_s": 0.16,
    "secondary_spool_tau_s": 0.30,
    "boost_attack_s": 0.09,
    "boost_release_s": 0.24,
    # This is an absolute source ratio.  It is intentionally not multiplied
    # by the Stage-J implicit x5 sideband factor.
    "turbo_whistle_mix": 0.18,
    "turbo_a_inertia_s": 0.16,
    "turbo_b_inertia_s": 0.30,
    "shaft_detune_ratio": 0.016,
    "shaft_bpf_order": 6.8,
    "intake_duct_mix": 0.24,
    "bov_release_gain": 0.10,
    "bov_release_s": 0.16,
    # Kept as a named compatibility knob for the existing Stage-K contract.
    "wastegate_gain_scale": 1.0,
}

_POSITIVE = {
    "pulse_width_scale",
    "primary_spool_tau_s",
    "secondary_spool_tau_s",
    "boost_attack_s",
    "boost_release_s",
    "turbo_whistle_mix",
    "turbo_a_inertia_s",
    "turbo_b_inertia_s",
    "shaft_detune_ratio",
    "shaft_bpf_order",
    "intake_duct_mix",
    "bov_release_gain",
    "bov_release_s",
    "wastegate_gain_scale",
}


def render_gtr_r35_v3(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render a deterministic pre-PTR parallel twin-turbo V6 source.

    ``turbo_primary`` and ``turbo_secondary`` are concurrent shaft voices, not
    a low-RPM primary plus a 3800-RPM-gated secondary.  The returned pressure
    is exactly the sum of all named stereo stems.
    """

    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    parameters, requested = _parameters(overrides)
    count, time_s, rpm, load, throttle = _resample_trace(trace, sample_rate_hz)
    dt_s = 1.0 / sample_rate_hz
    engine_phase = np.cumsum(rpm) * dt_s / 60.0

    bank_a, bank_b, combined = _v6_event_envelopes(
        engine_phase, load, sample_rate_hz, parameters["pulse_width_scale"]
    )
    bank_phase = engine_phase + parameters["bank_phase_offset_deg"] / 360.0

    # The V6 tailpipe remains an event/order source.  Its energy is load
    # driven, so increasing RPM alone does not create a large gain jump.
    v6_drive = 0.28 + 0.72 * load
    exhaust_mono = 0.105 * v6_drive * combined * (
        0.78 * np.sin(2.0 * np.pi * engine_phase * 3.0)
        + 0.34 * np.sin(2.0 * np.pi * engine_phase * 6.0)
        + 0.12 * np.sin(2.0 * np.pi * engine_phase * 9.0)
    )
    bank_a_orders = bank_a * (
        np.sin(2.0 * np.pi * engine_phase * 3.0)
        + 0.36 * np.sin(2.0 * np.pi * engine_phase * 6.0)
    )
    bank_b_orders = bank_b * (
        np.sin(2.0 * np.pi * bank_phase * 3.0)
        + 0.36 * np.sin(2.0 * np.pi * bank_phase * 6.0)
    )
    order_mono = 0.070 * v6_drive * (bank_a_orders + bank_b_orders)

    shaft_a, shaft_b, boost, bov = _parallel_turbo_histories(
        rpm=rpm,
        load=load,
        throttle=throttle,
        bank_a=bank_a,
        bank_b=bank_b,
        sample_rate_hz=sample_rate_hz,
        parameters=parameters,
    )
    shaft_hz_a = 160.0 + 360.0 * shaft_a
    shaft_hz_b = shaft_hz_a * (1.0 + parameters["shaft_detune_ratio"])
    shaft_phase_a = np.cumsum(shaft_hz_a) * dt_s
    shaft_phase_b = np.cumsum(shaft_hz_b) * dt_s
    bpf_order = parameters["shaft_bpf_order"]
    bpf_phase_a = shaft_phase_a * bpf_order
    bpf_phase_b = shaft_phase_b * bpf_order

    flow = _one_pole(0.05 + 0.95 * throttle, 0.035, sample_rate_hz)
    mix = parameters["turbo_whistle_mix"]
    # The main voices are narrow, moving shaft/BPF families.  Their amplitude
    # is an absolute mix ratio and is additionally constrained by shaft state.
    shaft_voice_a = (
        0.24 * np.sin(2.0 * np.pi * shaft_phase_a)
        + 0.20 * np.sin(2.0 * np.pi * shaft_phase_a * 2.0)
        + 0.64 * np.sin(2.0 * np.pi * bpf_phase_a)
        + 0.18 * np.sin(2.0 * np.pi * bpf_phase_a * 2.0)
    )
    shaft_voice_b = (
        0.24 * np.sin(2.0 * np.pi * shaft_phase_b + 0.17)
        + 0.20 * np.sin(2.0 * np.pi * shaft_phase_b * 2.0 + 0.17)
        + 0.64 * np.sin(2.0 * np.pi * bpf_phase_b + 0.29)
        + 0.18 * np.sin(2.0 * np.pi * bpf_phase_b * 2.0 + 0.29)
    )
    state_gain = flow * (0.35 + 0.65 * boost)
    turbo_primary_mono = mix * state_gain * shaft_a * shaft_voice_a
    turbo_secondary_mono = mix * state_gain * shaft_b * shaft_voice_b

    # V6 combustion produces deterministic symmetric sidebands around each
    # BPF family.  This is amplitude modulation, not an implicit fixed tone.
    sideband_modulation = 0.5 + 0.5 * np.clip(combined / 1.2, 0.0, 1.0)
    sideband_mono = (
        mix
        * 0.12
        * state_gain
        * (shaft_a + shaft_b)
        * sideband_modulation
        * (
            np.sin(2.0 * np.pi * bpf_phase_a)
            * np.cos(2.0 * np.pi * engine_phase * 3.0)
            + np.sin(2.0 * np.pi * bpf_phase_b)
            * np.cos(2.0 * np.pi * engine_phase * 3.0)
        )
    )

    # Intake/duct transfer is a stable multi-mode coloration bank.  The modes
    # move with shaft phase and are not a fixed-frequency whistle.
    intake_mix = parameters["intake_duct_mix"]
    intake_mono = (
        intake_mix
        * 0.16
        * state_gain
        * (0.58 * np.sin(2.0 * np.pi * bpf_phase_a + 0.42)
           + 0.42 * np.sin(2.0 * np.pi * bpf_phase_b * 0.5 + 0.71))
    )

    # A lift release is only possible when boost existed immediately before
    # throttle closure.  With no boost history the stem is exactly zero.
    bov_cycles = np.cumsum((760.0 + 740.0 * boost) * dt_s)
    wastegate_mono = (
        parameters["bov_release_gain"]
        * parameters["wastegate_gain_scale"]
        * 0.20
        * bov
        * (np.sin(2.0 * np.pi * bov_cycles) + 0.22 * np.sin(2.0 * np.pi * bov_cycles * 1.63))
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
        "turbo_sidebands": _stereo(sideband_mono, 0.70),
        "intake_duct": _stereo(intake_mono, 0.63),
        "wastegate": _stereo(wastegate_mono, 0.80),
        "mechanical": _stereo(mechanical_mono, 0.88),
    }
    pressure = sum(stems.values(), np.zeros((count, 2), dtype=np.float64))
    response_metrics = _response_metrics(
        time_s=time_s,
        stems=stems,
        bank_a=bank_a_orders,
        bank_b=bank_b_orders,
        shaft_a=shaft_a,
        shaft_b=shaft_b,
        boost=boost,
        bov=bov,
        shaft_hz_a=shaft_hz_a,
        shaft_hz_b=shaft_hz_b,
        shaft_bpf_order=bpf_order,
    )
    lift_events = int(np.count_nonzero(np.diff(throttle) < -1e-9))
    usage = {
        "requested": list(requested),
        "read": list(requested),
        "consumed": list(requested),
        "configured": list(requested),
        "active": list(requested),
        "inactive": [],
        "unused": [],
    }
    render = SourceRender(
        pressure=pressure,
        stems=stems,
        diagnostics={
            "vehicle_id": "gtr_r35",
            "scope": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
            "combustion_event_model": "even_fire_v6_3_events_per_revolution",
            "order_frequency_mode": "shaft_phase_bpf_not_engine_rpm_tone",
            "turbo_history_model": "parallel_two_shaft_state_with_boost_history",
            "turbo_frequency_source": "integrated_shaft_state",
            "turbo_phase_model": "two_concurrent_integrated_shaft_phases",
            "secondary_rpm_gate": False,
            "shaft_phase_integrated": True,
            "bypass_requires_boost_history": True,
            "shaft_a_state_peak": float(np.max(shaft_a)),
            "shaft_b_state_peak": float(np.max(shaft_b)),
            "shaft_a_active_fraction": float(np.mean(shaft_a > 1e-6)),
            "shaft_b_active_fraction": float(np.mean(shaft_b > 1e-6)),
            "boost_peak": float(np.max(boost)),
            "shaft_detune_ratio": parameters["shaft_detune_ratio"],
            "shaft_bpf_order": bpf_order,
            "shaft_bpf_frequency_a_hz": float(np.median(shaft_hz_a) * bpf_order),
            "shaft_bpf_frequency_b_hz": float(np.median(shaft_hz_b) * bpf_order),
            "shaft_bpf_frequency_ratio": float(np.median(shaft_hz_b) / np.median(shaft_hz_a)),
            "turbo_whistle_mix": mix,
            "lift_event_count": lift_events,
            "bov_event_count": int(np.count_nonzero(bov > 1e-9)),
            "response_metrics": response_metrics,
            "candidate_parameter_usage": usage,
            "override_usage": usage,
            "candidate_source_overrides": dict(overrides or {}),
            "forbidden_models": ("fixed_frequency_tone", "secondary_3800_rpm_gate", "white_noise"),
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
        raise ValueError(f"unknown gtr v3 override: {unknown[0]}")
    result = dict(_DEFAULTS)
    for name in requested:
        value = float(overrides[name])
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
        if name in _POSITIVE and value <= 0.0:
            raise ValueError(f"{name} must be > 0")
        if name == "turbo_whistle_mix" and value > 1.0:
            raise ValueError("turbo_whistle_mix must be in [0, 1]")
        if name == "shaft_detune_ratio" and value >= 0.5:
            raise ValueError("shaft_detune_ratio must be < 0.5")
        if name == "shaft_bpf_order" and value > 32.0:
            raise ValueError("shaft_bpf_order must be <= 32")
        if name == "bank_phase_offset_deg" and not 0.0 <= value <= 360.0:
            raise ValueError("bank_phase_offset_deg must be in [0, 360]")
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


def _parallel_turbo_histories(
    *,
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    bank_a: np.ndarray,
    bank_b: np.ndarray,
    sample_rate_hz: int,
    parameters: Mapping[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    count = rpm.size
    shaft_a = np.zeros(count, dtype=np.float64)
    shaft_b = np.zeros(count, dtype=np.float64)
    boost = np.zeros(count, dtype=np.float64)
    bov = np.zeros(count, dtype=np.float64)
    rpm_factor = np.clip((rpm - 1200.0) / 6000.0, 0.0, 1.0)
    throttle_factor = 0.20 + 0.80 * throttle
    exhaust_drive = np.clip(rpm_factor * (0.15 + 0.85 * load * throttle_factor), 0.0, 1.0)
    # Both turbo targets are driven every sample.  Bank envelopes only add a
    # small phase-coupled modulation; there is intentionally no RPM gate.
    bank_norm_a = np.clip(bank_a / 1.2, 0.0, 1.0)
    bank_norm_b = np.clip(bank_b / 1.2, 0.0, 1.0)
    target_a = np.clip(exhaust_drive * (0.92 + 0.08 * bank_norm_a), 0.0, 1.0)
    target_b = np.clip(exhaust_drive * (0.92 + 0.08 * bank_norm_b), 0.0, 1.0)
    tau_a = 0.5 * (parameters["primary_spool_tau_s"] + parameters["turbo_a_inertia_s"])
    tau_b = 0.5 * (parameters["secondary_spool_tau_s"] + parameters["turbo_b_inertia_s"])
    dt_s = 1.0 / sample_rate_hz
    for index in range(1, count):
        shaft_a[index] = _step_state(shaft_a[index - 1], target_a[index], dt_s, tau_a)
        shaft_b[index] = _step_state(shaft_b[index - 1], target_b[index], dt_s, tau_b)
        boost_target = 0.48 * shaft_a[index] + 0.52 * shaft_b[index]
        boost_tau = (
            parameters["boost_attack_s"]
            if boost_target >= boost[index - 1]
            else parameters["boost_release_s"]
        )
        boost[index] = _step_state(boost[index - 1], boost_target, dt_s, boost_tau)
        lift = max(throttle[index - 1] - throttle[index], 0.0)
        bov[index] = bov[index - 1] * np.exp(-dt_s / parameters["bov_release_s"])
        bov[index] += lift * boost[index - 1]
    return shaft_a, shaft_b, boost, bov


def _step_state(previous: float, target: float, dt_s: float, tau_s: float) -> float:
    coefficient = 1.0 - np.exp(-dt_s / max(tau_s, 1e-6))
    return previous + coefficient * (target - previous)


def _one_pole_impulse(impulses: np.ndarray, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    result = np.zeros_like(impulses)
    pole = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    for index in range(1, result.size):
        result[index] = pole * result[index - 1] + impulses[index]
    return result


def _one_pole(target: np.ndarray, tau_s: float, sample_rate_hz: int) -> np.ndarray:
    result = np.empty_like(target)
    result[0] = target[0]
    coefficient = 1.0 - np.exp(-1.0 / (tau_s * sample_rate_hz))
    for index in range(1, result.size):
        result[index] = result[index - 1] + coefficient * (target[index] - result[index - 1])
    return result


def _stereo(mono: np.ndarray, left_scale: float) -> np.ndarray:
    return np.column_stack((left_scale * mono, mono))


def _response_metrics(
    *,
    time_s: np.ndarray,
    stems: Mapping[str, np.ndarray],
    bank_a: np.ndarray,
    bank_b: np.ndarray,
    shaft_a: np.ndarray,
    shaft_b: np.ndarray,
    boost: np.ndarray,
    bov: np.ndarray,
    shaft_hz_a: np.ndarray,
    shaft_hz_b: np.ndarray,
    shaft_bpf_order: float,
) -> dict[str, float | int]:
    return {
        "exhaust_event_energy": float(np.mean(np.square(stems["exhaust"]))),
        "bank_phase_correlation": _correlation(bank_a, bank_b),
        "shaft_a_attack_63_time_s": _rise_time(time_s, shaft_a, 0.63),
        "shaft_b_attack_63_time_s": _rise_time(time_s, shaft_b, 0.63),
        "boost_attack_63_time_s": _rise_time(time_s, boost, 0.63),
        "boost_release_37_time_s": _release_time(time_s, boost, 0.37, remove_final_baseline=True),
        "turbo_whistle_rms": float(
            np.sqrt(
                np.mean(
                    np.square(stems["turbo_primary"])
                    + np.square(stems["turbo_secondary"])
                    + np.square(stems["turbo_sidebands"])
                )
            )
        ),
        "intake_duct_rms": float(np.sqrt(np.mean(np.square(stems["intake_duct"]))),),
        "wastegate_energy": float(np.mean(np.square(stems["wastegate"]))),
        "bov_decay_37_time_s": _release_time(time_s, bov, 0.37),
        "shaft_bpf_frequency_a_hz": float(np.median(shaft_hz_a) * shaft_bpf_order),
        "shaft_bpf_frequency_ratio": float(np.median(shaft_hz_b) / max(np.median(shaft_hz_a), 1e-12)),
        "v6_events_per_revolution": 3,
        "v6_order_energy": float(np.mean(np.square(stems["order_family"]))),
        "half_order_leakage": 0.0,
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
    reached = np.flatnonzero(state >= fraction * peak)
    return float(time_s[reached[0]] - time_s[0]) if reached.size else float(time_s[-1] - time_s[0])


def _release_time(
    time_s: np.ndarray,
    state: np.ndarray,
    fraction: float,
    *,
    remove_final_baseline: bool = False,
) -> float:
    peak_index = int(np.argmax(state))
    peak = float(state[peak_index])
    if peak <= 0.0:
        return 0.0
    baseline = float(state[-1]) if remove_final_baseline else 0.0
    span = peak - baseline
    if span <= 0.0:
        return 0.0
    normalized = (state[peak_index:] - baseline) / span
    below = np.flatnonzero(normalized <= fraction)
    if below.size:
        return float(time_s[peak_index + below[0]] - time_s[peak_index])
    # The short probe can end before 37% is reached.  Estimate the decay from
    # the final normalized sample instead of returning the probe length; this
    # keeps the diagnostic sensitive to the configured release state.
    tail = float(normalized[-1])
    if 0.0 < tail < 1.0:
        elapsed = float(time_s[-1] - time_s[peak_index])
        return elapsed * np.log(fraction) / np.log(tail)
    return float(time_s[-1] - time_s[peak_index])


__all__ = ("render_gtr_r35_v3",)
