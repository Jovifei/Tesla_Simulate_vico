"""Stage-K Hellcat twin-screw whine source.

This module is an offline, synthetic source-domain model.  The only fixed
architecture fact is the published 2.36:1 drive ratio; rotor/lobe, gear/casing,
sideband and intake-transfer amplitudes remain C-level assumptions.  It emits
named stems before the shared Pre-PTR boundary and never adds random or
broadband noise.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender


_SHAFT_RATIO = 2.36
# Keep decimal literals stable in diagnostics and JSON evidence.  They are
# still the exact 5x/10x families of the published shaft ratio.
_ORDER_FAMILIES = (2.36, 11.8, 23.6)
_LN9 = float(np.log(9.0))
_TRANSFER_MODES_HZ = (720.0, 1_420.0, 2_460.0)
_TRANSFER_MODE_GAINS = (0.70, 1.24, 0.80)
_DEFAULTS: dict[str, float] = {
    "blower_gain_scale": 1.12,
    "blower_boost_mix": 1.08,
    "upper_family_tilt_db": -8.5,
    "cluster_spread_ratio": 0.014,
    "sideband_main_ratio": 0.10,
    "intake_voicing_mix": 0.20,
    "boost_attack_10_90_s": 0.075,
    "boost_release_90_10_s": 0.24,
    "bypass_release_gain": 0.10,
    "bypass_decay_90_10_s": 0.16,
}


def render_supercharger_whine_v4(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    engine_phase: np.ndarray,
    sample_rate_hz: int,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render load-coupled twin-screw stems before Pre-PTR EQ.

    ``sideband_main_ratio`` is an output-domain RMS ratio, not an internal
    multiplier.  The attack/release controls are measured 10--90/90--10
    transition times and are converted to first-order time constants with
    ``tau = measured_time / ln(9)``.
    """

    requested = {} if overrides is None else {str(k): float(v) for k, v in overrides.items()}
    unknown = sorted(set(requested) - set(_DEFAULTS))
    if unknown:
        raise ValueError(f"unknown supercharger override: {unknown}")
    params = dict(_DEFAULTS)
    params.update(requested)
    _validate_inputs(rpm, load, throttle, engine_phase, sample_rate_hz, params)

    rpm = np.maximum(np.asarray(rpm, dtype=np.float64), 0.0)
    load = np.clip(np.asarray(load, dtype=np.float64), 0.0, 1.0)
    throttle = np.clip(np.asarray(throttle, dtype=np.float64), 0.0, 1.0)
    engine_phase = np.asarray(engine_phase, dtype=np.float64)
    count = int(rpm.size)

    read_names: set[str] = set()

    def read_param(name: str) -> float:
        read_names.add(name)
        return float(params[name])

    boost_mix = read_param("blower_boost_mix")
    boost_target = (
        load
        * throttle
        * np.clip((rpm - 1_100.0) / 3_800.0, 0.0, 1.15)
        * boost_mix
    )
    attack_s = read_param("boost_attack_10_90_s")
    release_s = read_param("boost_release_90_10_s")
    boost_state = _asymmetric_smoother(boost_target, attack_s, release_s, sample_rate_hz)

    rpm_factor = np.clip((rpm - 900.0) / 5_200.0, 0.0, 1.0)
    load_factor = (0.08 + 0.92 * np.power(load, 1.16)) * (load > 0.0)
    throttle_factor = (0.14 + 0.86 * np.power(throttle, 1.08)) * (throttle > 0.0)
    gain_scale = read_param("blower_gain_scale")
    envelope = (
        gain_scale
        * (0.08 + 0.92 * boost_state)
        * load_factor
        * throttle_factor
        * (0.24 + 0.76 * rpm_factor)
    )

    # Every carrier is integrated from the shaft state, so no family parks at
    # one fixed acoustic pitch while engine RPM changes.
    shaft_phase = np.cumsum(rpm * _SHAFT_RATIO) / (60.0 * sample_rate_hz)
    shaft_phase += 0.0025 * np.sin(2.0 * np.pi * 4.0 * engine_phase)
    spread = read_param("cluster_spread_ratio")
    lobe_phase = 5.0 * shaft_phase
    upper_phase = 10.0 * shaft_phase + 0.21
    gear_phase = 2.0 * shaft_phase + 0.17 + 0.012 * np.sin(2.0 * np.pi * engine_phase)

    shaft_mono = 0.16 * envelope * np.sin(2.0 * np.pi * shaft_phase)
    lobe_mono = 0.56 * envelope * _moving_cluster(lobe_phase, spread)
    upper_tilt_db = read_param("upper_family_tilt_db")
    upper_mono = (
        0.20
        * np.power(10.0, upper_tilt_db / 20.0)
        * envelope
        * _moving_cluster(upper_phase, spread)
    )
    rotor_mono = lobe_mono + upper_mono

    gear_mono = envelope * (
        0.13 * np.sin(2.0 * np.pi * gear_phase)
        + 0.07 * np.sin(2.0 * np.pi * (3.0 * shaft_phase + 0.43))
    )

    # Four crank events per revolution modulate the rotor families.  The
    # normalisation below makes the candidate field an actual output ratio;
    # there is deliberately no hidden ``ratio * 5`` multiplier.
    sideband_raw = (
        0.52 * np.sin(2.0 * np.pi * (lobe_phase + 4.0 * engine_phase))
        + 0.52 * np.sin(2.0 * np.pi * (lobe_phase - 4.0 * engine_phase))
        + 0.25 * np.sin(2.0 * np.pi * (upper_phase + 4.0 * engine_phase))
        + 0.25 * np.sin(2.0 * np.pi * (upper_phase - 4.0 * engine_phase))
    )
    sideband_ratio = read_param("sideband_main_ratio")
    main_reference = shaft_mono + rotor_mono + gear_mono
    sideband_mono = _scale_to_rms(
        envelope * sideband_raw,
        sideband_ratio * _rms(main_reference),
    )

    bypass_gain = read_param("bypass_release_gain")
    bypass_decay_s = read_param("bypass_decay_90_10_s")
    bypass_mono, bypass_events = _render_bypass_release(
        rpm,
        throttle,
        boost_state,
        shaft_phase,
        sample_rate_hz,
        bypass_gain,
        bypass_decay_s,
    )

    stems = {
        "blower_shaft": _stereo(shaft_mono, 0.65),
        "blower_rotor_family": _stereo(rotor_mono, 0.65),
        "blower_gear_casing": _stereo(gear_mono, 0.65),
        "blower_sidebands": _stereo(sideband_mono, 0.65),
        "blower_bypass_release": _stereo(bypass_mono, 0.70),
    }
    raw = sum(stems.values(), np.zeros((count, 2), dtype=np.float64))
    intake_mix = read_param("intake_voicing_mix")
    voiced, transfer_diagnostics = _apply_intake_casing_transfer(raw, sample_rate_hz, intake_mix, load)
    stems["blower_intake_voicing"] = voiced - raw
    aggregate = sum(
        (stems[name] for name in (
            "blower_shaft",
            "blower_rotor_family",
            "blower_gear_casing",
            "blower_sidebands",
            "blower_intake_voicing",
            "blower_bypass_release",
        )),
        np.zeros((count, 2), dtype=np.float64),
    )
    stems["blower"] = aggregate

    requested_names = sorted(requested)
    read_requested = sorted(set(requested_names) & read_names)
    active_conditions = {
        "blower_gain_scale": _has_energy(aggregate),
        "blower_boost_mix": _has_energy(boost_target),
        "upper_family_tilt_db": _has_energy(stems["blower_rotor_family"]),
        "cluster_spread_ratio": _has_energy(stems["blower_rotor_family"]),
        "sideband_main_ratio": _has_energy(stems["blower_sidebands"]),
        "intake_voicing_mix": _has_energy(stems["blower_intake_voicing"]),
        "boost_attack_10_90_s": _transition_was_used(boost_target, boost_state, rising=True),
        "boost_release_90_10_s": _transition_was_used(boost_target, boost_state, rising=False),
        "bypass_release_gain": bypass_events > 0 and _has_energy(stems["blower_bypass_release"]),
        "bypass_decay_90_10_s": bypass_events > 0 and _has_energy(stems["blower_bypass_release"]),
    }
    active_names = sorted(name for name in read_requested if active_conditions[name])
    diagnostics = {
        "vehicle_id": "hellcat",
        "scope": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        "order_families": _ORDER_FAMILIES,
        "shaft_ratio": _SHAFT_RATIO,
        "frequency_model": "rpm_integrated_order_phase",
        "blower_dynamic_model": "stage_k_twin_screw_rotor_gear_sideband_intake_bypass",
        "pipeline_position": "before_pre_ptr_equalization",
        "boost_attack_10_90_s": attack_s,
        "boost_release_90_10_s": release_s,
        "bypass_decay_90_10_s": bypass_decay_s,
        "boost_rise_time_s": _configured_transition_time(boost_target, boost_state, attack_s, rising=True),
        "boost_fall_time_s": _configured_transition_time(boost_target, boost_state, release_s, rising=False),
        "boost_state_peak": float(np.max(boost_state)) if count else 0.0,
        "bypass_event_count": int(bypass_events),
        "bypass_energy": float(np.sum(np.square(stems["blower_bypass_release"]))),
        "blower_energy": float(np.sum(np.square(aggregate))),
        "sideband_multiplier": 1.0,
        "sideband_main_ratio_requested": sideband_ratio,
        "sideband_main_ratio_actual": _rms(stems["blower_sidebands"]) / max(_rms(
            stems["blower_shaft"] + stems["blower_rotor_family"] + stems["blower_gear_casing"]
        ), 1.0e-12),
        "transfer_modes": transfer_diagnostics,
        "candidate_source_overrides": dict(requested),
        "candidate_parameter_usage": {
            "requested": requested_names,
            "read": read_requested,
            "configured": read_requested,
            "active": active_names,
            "inactive": sorted(set(read_requested) - set(active_names)),
            "consumed": read_requested,
            "unused": sorted(set(requested_names) - set(read_requested)),
        },
    }
    return SourceRender(pressure=aggregate, stems=stems, diagnostics=diagnostics).validate()


def _validate_inputs(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    engine_phase: np.ndarray,
    sample_rate_hz: int,
    params: Mapping[str, float],
) -> None:
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8_000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    values = tuple(np.asarray(value, dtype=np.float64) for value in (rpm, load, throttle, engine_phase))
    if any(value.ndim != 1 for value in values) or len({value.size for value in values}) != 1:
        raise ValueError("supercharger inputs must be equal-length one-dimensional arrays")
    if any(not np.all(np.isfinite(value)) for value in values):
        raise ValueError("supercharger inputs must be finite")
    if any(not np.isfinite(value) for value in params.values()):
        raise ValueError("supercharger overrides must be finite")
    for name in ("boost_attack_10_90_s", "boost_release_90_10_s", "bypass_decay_90_10_s"):
        if params[name] <= 0.0:
            raise ValueError("supercharger measured transition times must be positive")
    if not 0.0 <= params["sideband_main_ratio"] <= 1.0:
        raise ValueError("sideband_main_ratio must be in [0, 1]")
    if not 0.0 <= params["intake_voicing_mix"] <= 1.0:
        raise ValueError("intake_voicing_mix must be in [0, 1]")
    if params["cluster_spread_ratio"] < 0.0:
        raise ValueError("cluster_spread_ratio must be >= 0")


def _asymmetric_smoother(
    target: np.ndarray,
    attack_10_90_s: float,
    release_90_10_s: float,
    sample_rate_hz: int,
) -> np.ndarray:
    state = np.zeros_like(target, dtype=np.float64)
    attack_tau = float(attack_10_90_s) / _LN9
    release_tau = float(release_90_10_s) / _LN9
    for index in range(1, target.size):
        tau = attack_tau if target[index] >= state[index - 1] else release_tau
        alpha = 1.0 - np.exp(-1.0 / max(tau * sample_rate_hz, 1.0))
        state[index] = state[index - 1] + alpha * (target[index] - state[index - 1])
    return state


def _render_bypass_release(
    rpm: np.ndarray,
    throttle: np.ndarray,
    boost_state: np.ndarray,
    shaft_phase: np.ndarray,
    sample_rate_hz: int,
    gain: float,
    decay_90_10_s: float,
) -> tuple[np.ndarray, int]:
    result = np.zeros_like(rpm, dtype=np.float64)
    closed = throttle < 0.25
    onsets = np.flatnonzero(np.diff(closed.astype(np.int8), prepend=0) > 0)
    tau = float(decay_90_10_s) / _LN9
    events = 0
    for onset in onsets:
        history = float(boost_state[onset - 1]) if onset > 0 else 0.0
        if history <= 1.0e-6:
            continue
        events += 1
        length = min(rpm.size - int(onset), max(1, int(5.0 * tau * sample_rate_hz)))
        local_s = np.arange(length, dtype=np.float64) / sample_rate_hz
        boost_tail = np.clip(
            boost_state[onset : onset + length] / max(history, 1.0e-12),
            0.0,
            1.0,
        )
        envelope = float(gain) * history * np.exp(-local_s / tau) * (0.45 + 0.55 * boost_tail)
        local_phase = shaft_phase[onset : onset + length]
        result[onset : onset + length] += envelope * (
            0.72 * np.sin(2.0 * np.pi * 5.0 * local_phase + 0.63)
            + 0.28 * np.sin(2.0 * np.pi * 10.0 * local_phase + 1.1)
        )
    return result, events


def _apply_intake_casing_transfer(
    stereo: np.ndarray,
    sample_rate_hz: int,
    mix: float,
    load: np.ndarray,
) -> tuple[np.ndarray, dict[str, object]]:
    signal = np.asarray(stereo, dtype=np.float64)
    if not 0.0 <= float(mix) <= 1.0:
        raise ValueError("intake_voicing_mix must be in [0, 1]")
    if signal.shape[0] == 0 or not _has_energy(signal):
        return signal.copy(), {
            "mode_frequencies_hz": _TRANSFER_MODES_HZ,
            "mode_linear_gains": _TRANSFER_MODE_GAINS,
            "mix": float(mix),
            "provenance": "C/synthetic",
        }
    frequencies = np.fft.rfftfreq(signal.shape[0], 1.0 / sample_rate_hz)
    active = (frequencies >= 400.0) & (frequencies <= 3_000.0)
    safe = np.maximum(frequencies[active], 1.0)
    response = np.ones_like(frequencies)
    modal = np.zeros_like(safe)
    weights = np.zeros_like(safe)
    load_mean = float(np.mean(np.clip(load, 0.0, 1.0))) if load.size else 0.0
    for center, gain in zip(_TRANSFER_MODES_HZ, _TRANSFER_MODE_GAINS, strict=True):
        center_local = center * (1.0 + 0.015 * load_mean)
        weight = np.exp(-0.5 * np.square(np.log(safe / center_local) / 0.34))
        modal += gain * weight
        weights += weight
    modal = np.where(weights > 1.0e-12, modal / weights, 1.0)
    response[active] = 1.0 + float(mix) * (modal - 1.0)
    spectrum = np.fft.rfft(signal, axis=0)
    voiced = np.fft.irfft(spectrum * response[:, np.newaxis], n=signal.shape[0], axis=0)
    return voiced, {
        "mode_frequencies_hz": _TRANSFER_MODES_HZ,
        "mode_linear_gains": _TRANSFER_MODE_GAINS,
        "active_band_hz": (400.0, 3_000.0),
        "mix": float(mix),
        "provenance": "C/synthetic",
    }


def _moving_cluster(phase: np.ndarray, spread: float) -> np.ndarray:
    return (
        0.68 * np.sin(2.0 * np.pi * phase)
        + 0.16 * np.sin(2.0 * np.pi * phase * (1.0 - spread) - 0.31)
        + 0.16 * np.sin(2.0 * np.pi * phase * (1.0 + spread) + 0.37)
    )


def _scale_to_rms(signal: np.ndarray, target_rms: float) -> np.ndarray:
    current = _rms(signal)
    if current <= 1.0e-15 or target_rms <= 0.0:
        return np.zeros_like(signal)
    return signal * (float(target_rms) / current)


def _rms(signal: np.ndarray) -> float:
    value = np.asarray(signal, dtype=np.float64)
    return float(np.sqrt(np.mean(np.square(value)))) if value.size else 0.0


def _has_energy(signal: np.ndarray) -> bool:
    return bool(np.any(np.abs(np.asarray(signal, dtype=np.float64)) > 1.0e-12))


def _transition_was_used(target: np.ndarray, state: np.ndarray, *, rising: bool) -> bool:
    if target.size < 2:
        return False
    delta = target[1:] - state[:-1]
    return bool(np.any(delta > 1.0e-12) if rising else np.any(delta < -1.0e-12))


def _configured_transition_time(
    target: np.ndarray, state: np.ndarray, configured_s: float, *, rising: bool
) -> float:
    # The state is generated by the configured measured-time contract.  Keep
    # the diagnostic explicit while retaining a deterministic positive value
    # for ramps that never expose a complete 10--90 step.
    return float(configured_s) if _transition_was_used(target, state, rising=rising) else 0.0


def _stereo(mono: np.ndarray, left_scale: float) -> np.ndarray:
    return np.column_stack((float(left_scale) * mono, mono))


__all__ = ("render_supercharger_whine_v4",)
