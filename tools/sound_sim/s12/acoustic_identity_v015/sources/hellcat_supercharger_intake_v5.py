"""Stage-L Hellcat-inspired twin-screw intake and casing radiation source.

The published 2.36:1 drive ratio is the only frequency anchor treated as a
hardware fact.  Aero feature counts, gear feature counts, transfers and
amplitudes are deterministic C-level synthetic design variables.  This module
does not put supercharger orders into the exhaust path.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender
from ..stage_l.crank_clock import HellcatCrankClock


_SHAFT_RATIO = 2.36
_PUBLISHED_ROUNDED_MAX_SHAFT_RPM = 14_600.0
_LN9 = float(np.log(9.0))
_PARAMETERS = {
    "aero_family_order_ratio", "aero_harmonic_mix", "aero_cluster_spread_ratio",
    "gear_family_order_ratio", "gear_to_aero_ratio", "torque_ripple_to_gear_depth",
    "intake_transfer_mix", "casing_transfer_mix", "boost_attack_10_90_s",
    "boost_release_90_10_s", "bypass_release_gain", "bypass_decay_90_10_s",
}
_CONTRIBUTORS = ("sc_intake_radiated", "sc_casing_radiated", "sc_bypass_release")
_DIAGNOSTIC_ONLY = ("sc_aero_raw", "sc_gear_raw", "supercharger_intake")


def render_hellcat_supercharger_intake_v5(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: HellcatCrankClock,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    """Render named intake, casing and bypass stems before common Pre-PTR EQ."""
    params = _validated_inputs(rpm, load, throttle, clock, sample_rate_hz, overrides)
    rpm = np.asarray(rpm, dtype=np.float64)
    load = np.clip(np.asarray(load, dtype=np.float64), 0.0, 1.0)
    throttle = np.clip(np.asarray(throttle, dtype=np.float64), 0.0, 1.0)
    count = rpm.size

    shaft_phase = _SHAFT_RATIO * np.asarray(clock.engine_phase_cycles, dtype=np.float64)
    shaft_rpm = _SHAFT_RATIO * rpm

    boost_target = np.power(load, 1.08) * np.power(throttle, 1.04)
    boost_state = _asymmetric_smoother(
        boost_target,
        params["boost_attack_10_90_s"],
        params["boost_release_90_10_s"],
        sample_rate_hz,
    )
    # Shaft speed changes acoustic order position.  Its amplitude contribution
    # is deliberately shallow; load/throttle/boost remain the principal energy state.
    shaft_speed_weight = 0.72 + 0.28 * np.clip((shaft_rpm - 1_800.0) / 12_000.0, 0.0, 1.0)
    source_envelope = boost_state * shaft_speed_weight

    aero_order = params["aero_family_order_ratio"]
    aero_phase = aero_order * shaft_phase
    harmonic_mix = params["aero_harmonic_mix"]
    spread = params["aero_cluster_spread_ratio"]
    aero_family = (
        (1.0 - harmonic_mix) * _moving_cluster(aero_phase, spread)
        + harmonic_mix * _moving_cluster(2.0 * aero_phase + 0.19, 0.67 * spread)
    )
    aero_raw_mono = source_envelope * aero_family

    gear_order = params["gear_family_order_ratio"]
    gear_phase = gear_order * shaft_phase + 0.17
    torque_depth = params["torque_ripple_to_gear_depth"]
    torque_modulation = 1.0 + torque_depth * (
        2.0 * np.asarray(clock.torque_ripple_envelope, dtype=np.float64) - 1.0
    )
    gear_shape = source_envelope * torque_modulation * (
        0.78 * np.sin(2.0 * np.pi * gear_phase)
        + 0.22 * np.sin(2.0 * np.pi * (1.5 * gear_phase + 0.31))
    )
    gear_raw_mono = _scale_to_rms(
        gear_shape, params["gear_to_aero_ratio"] * _rms(aero_raw_mono)
    )

    aero_raw = _stereo(aero_raw_mono, 0.91)
    gear_raw = _stereo(gear_raw_mono, 0.84)
    intake = params["intake_transfer_mix"] * _intake_plenum_transfer(aero_raw)
    casing = params["casing_transfer_mix"] * _casing_transfer(gear_raw)
    bypass_mono, bypass_events, bypass_decay_measured = _render_bypass_release(
        load, throttle, boost_state, shaft_phase, sample_rate_hz,
        params["bypass_release_gain"], params["bypass_decay_90_10_s"],
    )
    bypass = _stereo(bypass_mono, 0.95)

    contributors = {
        "sc_intake_radiated": intake,
        "sc_casing_radiated": casing,
        "sc_bypass_release": bypass,
    }
    aggregate = sum(contributors.values(), np.zeros((count, 2), dtype=np.float64))
    stems = {
        "sc_aero_raw": aero_raw,
        "sc_gear_raw": gear_raw,
        **contributors,
        "supercharger_intake": aggregate,
    }

    rising = _transition_used(boost_target, boost_state, rising=True)
    falling = _transition_used(boost_target, boost_state, rising=False)
    intake_active = _has_energy(intake)
    casing_active = _has_energy(casing)
    bypass_active = bypass_events > 0 and _has_energy(bypass)
    active_conditions = {
        "aero_family_order_ratio": intake_active,
        "aero_harmonic_mix": intake_active and harmonic_mix != 0.0,
        "aero_cluster_spread_ratio": intake_active and spread != 0.0,
        "gear_family_order_ratio": casing_active,
        "gear_to_aero_ratio": casing_active and params["gear_to_aero_ratio"] != 0.0,
        "torque_ripple_to_gear_depth": casing_active and torque_depth != 0.0,
        "intake_transfer_mix": intake_active,
        "casing_transfer_mix": casing_active,
        "boost_attack_10_90_s": rising and _has_energy(aggregate),
        "boost_release_90_10_s": falling and _has_energy(aggregate),
        "bypass_release_gain": bypass_active,
        "bypass_decay_90_10_s": bypass_active,
    }
    active = sorted(name for name, used in active_conditions.items() if used)
    inactive = sorted(_PARAMETERS - set(active))
    peak_shaft = float(np.max(shaft_rpm)) if count else 0.0
    published_status = (
        "INFORMATIONAL_ROUNDED_FIGURE_PLUS_0.22_PERCENT"
        if peak_shaft > _PUBLISHED_ROUNDED_MAX_SHAFT_RPM else "WITHIN_ROUNDED_PUBLIC_FIGURE"
    )
    diagnostics = {
        "vehicle_id": "hellcat",
        "scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        "shaft_ratio": _SHAFT_RATIO,
        "shaft_phase_max_cycles": float(shaft_phase[-1]) if count else 0.0,
        "shaft_rpm_peak": peak_shaft,
        "published_max_shaft_rpm_rounded": _PUBLISHED_ROUNDED_MAX_SHAFT_RPM,
        "published_limit_status": published_status,
        "frequency_model": "shaft_phase_integrated_orders_no_fixed_hz_tones",
        "random_source": False,
        "aero_family_order_ratio": aero_order,
        "gear_family_order_ratio": gear_order,
        "aero_ridge_hz_mean": float(np.mean(rpm * _SHAFT_RATIO * aero_order / 60.0)),
        "gear_ridge_hz_mean": float(np.mean(rpm * _SHAFT_RATIO * gear_order / 60.0)),
        "boost_state_peak": float(np.max(boost_state)) if count else 0.0,
        "boost_attack_requested_10_90_s": params["boost_attack_10_90_s"],
        "boost_release_requested_90_10_s": params["boost_release_90_10_s"],
        "boost_attack_measured_10_90_s": _measure_smoother_time(
            params["boost_attack_10_90_s"], sample_rate_hz, rising=True
        ),
        "boost_release_measured_90_10_s": _measure_smoother_time(
            params["boost_release_90_10_s"], sample_rate_hz, rising=False
        ),
        "bypass_decay_requested_90_10_s": params["bypass_decay_90_10_s"],
        "bypass_decay_measured_90_10_s": bypass_decay_measured,
        "bypass_event_count": int(bypass_events),
        "bypass_gate": "boost_history_and_throttle_below_0.25_and_load_below_0.25",
        "pressure_stem_contract": {
            "contributors": list(_CONTRIBUTORS),
            "diagnostic_only": list(_DIAGNOSTIC_ONLY),
        },
        "pipeline_position": "source_before_state_shaping_and_common_pre_ptr_equalization",
        "parameter_effect_energy": {
            name: float(_rms(stems[target])) if active_conditions[name] else 0.0
            for name, target in {
                "aero_family_order_ratio": "sc_intake_radiated",
                "aero_harmonic_mix": "sc_intake_radiated",
                "aero_cluster_spread_ratio": "sc_intake_radiated",
                "gear_family_order_ratio": "sc_casing_radiated",
                "gear_to_aero_ratio": "sc_casing_radiated",
                "torque_ripple_to_gear_depth": "sc_casing_radiated",
                "intake_transfer_mix": "sc_intake_radiated",
                "casing_transfer_mix": "sc_casing_radiated",
                "boost_attack_10_90_s": "supercharger_intake",
                "boost_release_90_10_s": "supercharger_intake",
                "bypass_release_gain": "sc_bypass_release",
                "bypass_decay_90_10_s": "sc_bypass_release",
            }.items()
        },
        "candidate_source_overrides": dict(params),
        "candidate_parameter_usage": {
            "requested": sorted(_PARAMETERS),
            "read": sorted(_PARAMETERS),
            "configured": sorted(_PARAMETERS),
            "active": active,
            "inactive": inactive,
            "unused": [],
        },
    }
    return SourceRender(pressure=aggregate, stems=stems, diagnostics=diagnostics).validate()


def _validated_inputs(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: HellcatCrankClock,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> dict[str, float]:
    if not isinstance(clock, HellcatCrankClock):
        raise TypeError("clock must be a HellcatCrankClock")
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8_000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    if not isinstance(overrides, Mapping):
        raise TypeError("overrides must be a mapping")
    names = {str(name) for name in overrides}
    if names != _PARAMETERS:
        raise ValueError(f"supercharger intake override keys mismatch: {sorted(names ^ _PARAMETERS)}")
    params = {str(name): float(value) for name, value in overrides.items()}
    arrays = tuple(np.asarray(value, dtype=np.float64) for value in (rpm, load, throttle))
    if any(value.ndim != 1 for value in arrays) or len({value.size for value in arrays}) != 1:
        raise ValueError("rpm/load/throttle must be equal-length one-dimensional arrays")
    if arrays[0].size != clock.engine_phase_cycles.size:
        raise ValueError("input arrays must match the shared crank clock")
    if any(not np.all(np.isfinite(value)) for value in arrays) or any(not np.isfinite(v) for v in params.values()):
        raise ValueError("supercharger intake inputs and overrides must be finite")
    for name in ("boost_attack_10_90_s", "boost_release_90_10_s", "bypass_decay_90_10_s"):
        if params[name] <= 0.0:
            raise ValueError(f"{name} must be positive")
    return params


def _moving_cluster(phase: np.ndarray, spread: float) -> np.ndarray:
    return (
        0.72 * np.sin(2.0 * np.pi * phase)
        + 0.14 * np.sin(2.0 * np.pi * (1.0 - spread) * phase - 0.29)
        + 0.14 * np.sin(2.0 * np.pi * (1.0 + spread) * phase + 0.37)
    )


def _intake_plenum_transfer(stereo: np.ndarray) -> np.ndarray:
    signal = np.asarray(stereo, dtype=np.float64)
    # Short deterministic duct/plenum reflections: source-domain propagation,
    # not an EQ or a fixed-Hz oscillator.
    return 0.82 * signal + 0.23 * _delay(signal, 3) - 0.11 * _delay(signal, 7)


def _casing_transfer(stereo: np.ndarray) -> np.ndarray:
    signal = np.asarray(stereo, dtype=np.float64)
    return 0.74 * signal - 0.18 * _delay(signal, 2) + 0.09 * _delay(signal, 5)


def _delay(signal: np.ndarray, samples: int) -> np.ndarray:
    result = np.zeros_like(signal)
    if samples < signal.shape[0]:
        result[samples:] = signal[:-samples]
    return result


def _asymmetric_smoother(
    target: np.ndarray, attack_10_90_s: float, release_90_10_s: float, sample_rate_hz: int,
) -> np.ndarray:
    state = np.zeros_like(target, dtype=np.float64)
    attack_tau = attack_10_90_s / _LN9
    release_tau = release_90_10_s / _LN9
    for index in range(1, target.size):
        tau = attack_tau if target[index] >= state[index - 1] else release_tau
        alpha = 1.0 - np.exp(-1.0 / max(tau * sample_rate_hz, 1.0))
        state[index] = state[index - 1] + alpha * (target[index] - state[index - 1])
    return state


def _render_bypass_release(
    load: np.ndarray,
    throttle: np.ndarray,
    boost_state: np.ndarray,
    shaft_phase: np.ndarray,
    sample_rate_hz: int,
    gain: float,
    decay_90_10_s: float,
) -> tuple[np.ndarray, int, float]:
    result = np.zeros_like(load, dtype=np.float64)
    true_close = (throttle < 0.25) & (load < 0.25)
    onsets = np.flatnonzero(np.diff(true_close.astype(np.int8), prepend=0) > 0)
    tau = decay_90_10_s / _LN9
    events = 0
    measured = 0.0
    for onset in onsets:
        history = float(boost_state[onset - 1]) if onset > 0 else 0.0
        if history <= 1.0e-5 or gain <= 0.0:
            continue
        events += 1
        length = min(load.size - int(onset), max(2, int(5.0 * tau * sample_rate_hz)))
        local_s = np.arange(length, dtype=np.float64) / sample_rate_hz
        envelope = float(gain) * history * np.exp(-local_s / tau)
        phase = shaft_phase[onset : onset + length]
        result[onset : onset + length] += envelope * (
            0.76 * np.sin(2.0 * np.pi * 0.72 * phase + 0.41)
            + 0.24 * np.sin(2.0 * np.pi * 1.44 * phase + 0.93)
        )
        measured = _measure_decay_envelope(envelope, sample_rate_hz)
    return result, events, measured


def _measure_smoother_time(configured_s: float, sample_rate_hz: int, *, rising: bool) -> float:
    lead = max(4, int(0.04 * sample_rate_hz))
    tail = max(8, int(2.5 * configured_s * sample_rate_hz))
    target = np.zeros(lead + tail, dtype=np.float64)
    if rising:
        target[lead:] = 1.0
        state = _asymmetric_smoother(target, configured_s, configured_s, sample_rate_hz)
        local = state[lead:]
        first = np.flatnonzero(local >= 0.10)
        second = np.flatnonzero(local >= 0.90)
    else:
        target[:lead] = 1.0
        state = np.ones_like(target)
        tau = configured_s / _LN9
        alpha = 1.0 - np.exp(-1.0 / max(tau * sample_rate_hz, 1.0))
        for index in range(lead, target.size):
            state[index] = state[index - 1] + alpha * (target[index] - state[index - 1])
        local = state[lead:]
        first = np.flatnonzero(local <= 0.90)
        second = np.flatnonzero(local <= 0.10)
    if not first.size or not second.size:
        return 0.0
    return float((second[0] - first[0]) / sample_rate_hz)


def _measure_decay_envelope(envelope: np.ndarray, sample_rate_hz: int) -> float:
    if envelope.size < 2 or envelope[0] <= 0.0:
        return 0.0
    normalized = envelope / envelope[0]
    at_90 = np.flatnonzero(normalized <= 0.90)
    at_10 = np.flatnonzero(normalized <= 0.10)
    if not at_90.size or not at_10.size:
        return 0.0
    return float((at_10[0] - at_90[0]) / sample_rate_hz)


def _transition_used(target: np.ndarray, state: np.ndarray, *, rising: bool) -> bool:
    if target.size < 2:
        return False
    delta = target[1:] - state[:-1]
    return bool(np.any(delta > 1.0e-8) if rising else np.any(delta < -1.0e-8))


def _scale_to_rms(signal: np.ndarray, target_rms: float) -> np.ndarray:
    current = _rms(signal)
    if current <= 1.0e-15 or target_rms <= 0.0:
        return np.zeros_like(signal)
    return np.asarray(signal, dtype=np.float64) * (float(target_rms) / current)


def _rms(value: np.ndarray) -> float:
    array = np.asarray(value, dtype=np.float64)
    return float(np.sqrt(np.mean(np.square(array)))) if array.size else 0.0


def _has_energy(value: np.ndarray) -> bool:
    return bool(np.any(np.abs(np.asarray(value, dtype=np.float64)) > 1.0e-12))


def _stereo(mono: np.ndarray, left_scale: float) -> np.ndarray:
    return np.column_stack((float(left_scale) * mono, mono))


__all__ = ("render_hellcat_supercharger_intake_v5",)
