"""Hellcat-only torque interruption and load transient synthesis before PTR."""

from __future__ import annotations

from dataclasses import replace
import hashlib

import numpy as np

from ..acoustic_layers.shift_dynamics import detect_shift_events
from ..contracts import SourceRender, VehicleStateTrace
from .candidate_profiles import StageLCandidateProfile


_HEMI_STEMS = (
    "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
    "hemi_structure_shock", "hemi_mechanical_torque_ripple",
)
_SC_STEMS = ("sc_intake_radiated", "sc_casing_radiated")
_ADDITIVE_STEMS = (
    "hellcat_shift_reengagement", "hellcat_sc_drive_transient", "hellcat_tip_in_blowdown",
)


def apply_hellcat_transient_dynamics(
    render: SourceRender,
    trace: VehicleStateTrace,
    candidate: StageLCandidateProfile,
    sample_rate_hz: int = 48_000,
) -> SourceRender:
    """Apply separate HEMI torque-cut and inertia-retaining SC shift responses.

    Primitive source stems are modified in place. ``hellcat_shift_torque_cut``
    records their exact negative delta but is diagnostic-only, so pressure is
    never charged for the same interruption twice.
    """
    render.validate()
    trace.validate()
    if not isinstance(candidate, StageLCandidateProfile) or candidate.vehicle_id != "hellcat":
        raise ValueError("candidate must be a validated Stage-L Hellcat profile")
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8_000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    missing = sorted((set(_HEMI_STEMS) | set(_SC_STEMS)) - set(render.stems))
    if missing:
        raise ValueError(f"Hellcat transient source stems are missing: {missing}")
    if any(name in render.stems for name in ("hellcat_shift_torque_cut", *_ADDITIVE_STEMS)):
        raise ValueError("Hellcat transient dynamics may only be applied once")

    params = {
        name: float(record["value"])
        for name, record in candidate.payload["shift_and_load_transient"].items()
    }
    count = render.pressure.shape[0]
    audio_time = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    throttle = np.interp(audio_time, trace.time_s, trace.throttle)
    events = detect_shift_events(trace, sample_rate_hz)
    exhaust_gain = np.ones(count, dtype=np.float64)
    sc_gain = np.ones(count, dtype=np.float64)
    reengagement_env = np.zeros(count, dtype=np.float64)
    sc_drive_env = np.zeros(count, dtype=np.float64)

    duration = params["shift_interruption_s"]
    for event in events:
        center = int(round((event.time_s - trace.time_s[0]) * sample_rate_hz))
        half = max(2, int(round(0.5 * duration * sample_rate_hz)))
        start, stop = max(0, center - half), min(count, center + half + 1)
        if stop <= start:
            continue
        phase = np.linspace(-1.0, 1.0, stop - start)
        dip = 0.5 * (1.0 + np.cos(np.pi * phase))
        exhaust_gain[start:stop] = np.minimum(
            exhaust_gain[start:stop], 1.0 - (1.0 - params["shift_min_exhaust_gain"]) * dip,
        )
        sc_gain[start:stop] = np.minimum(
            sc_gain[start:stop], 1.0 - (1.0 - params["shift_min_sc_gain"]) * dip,
        )
        tail_start = min(count, center + half)
        tail_count = min(count - tail_start, max(1, int(round(5.0 * params["reengagement_decay_s"] * sample_rate_hz))))
        if tail_count:
            local = np.arange(tail_count, dtype=np.float64) / sample_rate_hz
            reengagement_env[tail_start:tail_start + tail_count] = np.maximum(
                reengagement_env[tail_start:tail_start + tail_count],
                0.25 * (1.0 - params["shift_min_exhaust_gain"]) * np.exp(-local / params["reengagement_decay_s"]),
            )
            sc_drive_env[tail_start:tail_start + tail_count] = np.maximum(
                sc_drive_env[tail_start:tail_start + tail_count],
                params["sc_drive_modulation_depth"] * np.exp(-local / params["reengagement_decay_s"]),
            )

    stems = {name: np.asarray(stem, dtype=np.float64).copy() for name, stem in render.stems.items()}
    old_pressure = np.asarray(render.pressure, dtype=np.float64)
    pressure = old_pressure.copy()
    torque_cut = np.zeros_like(old_pressure)
    for name in _HEMI_STEMS:
        old = stems[name]
        new = old * exhaust_gain[:, None]
        stems[name] = new
        delta = new - old
        torque_cut += delta
        pressure += delta
    for name in _SC_STEMS:
        old = stems[name]
        new = old * sc_gain[:, None]
        stems[name] = new
        pressure += new - old

    hemi_source = sum((np.asarray(render.stems[name]) for name in _HEMI_STEMS), np.zeros_like(old_pressure))
    sc_source = sum((np.asarray(render.stems[name]) for name in _SC_STEMS), np.zeros_like(old_pressure))
    reengagement = hemi_source * reengagement_env[:, None]
    sc_drive = sc_source * sc_drive_env[:, None]
    tip_in = _tip_in_blowdown(
        np.asarray(render.stems["hemi_blowdown_body"]), throttle,
        params["tip_in_blowdown_gain"], sample_rate_hz,
    )
    stems.update({
        "hellcat_shift_torque_cut": torque_cut,
        "hellcat_shift_reengagement": reengagement,
        "hellcat_sc_drive_transient": sc_drive,
        "hellcat_tip_in_blowdown": tip_in,
    })
    pressure += reengagement + sc_drive + tip_in
    stems["exhaust"] = stems["hemi_exhaust_left"] + stems["hemi_exhaust_right"]
    stems["hemi_exhaust"] = stems["exhaust"]
    stems["hemi_combustion_and_blowdown"] = sum(
        (stems[name] for name in _HEMI_STEMS), np.zeros_like(old_pressure)
    )
    stems["supercharger_intake"] = sum(
        (stems[name] for name in (*_SC_STEMS, "sc_bypass_release")), np.zeros_like(old_pressure)
    )
    stems["blower"] = stems["supercharger_intake"].copy()

    diagnostics = dict(render.diagnostics)
    contract = dict(diagnostics.get("pressure_stem_contract", {}))
    contributors = list(contract.get("contributors", ()))
    aggregates = list(contract.get("diagnostic_aggregates", ()))
    for name in _ADDITIVE_STEMS:
        if name not in contributors:
            contributors.append(name)
    if "hellcat_shift_torque_cut" not in aggregates:
        aggregates.append("hellcat_shift_torque_cut")
    for name in ("exhaust", "hemi_exhaust", "hemi_combustion_and_blowdown", "supercharger_intake", "blower"):
        if name not in aggregates:
            aggregates.append(name)
    contract.update({"contributors": contributors, "diagnostic_aggregates": aggregates})
    event_measurements = tuple(
        _measure_shift_event(old_pressure, pressure, event.sample_index, sample_rate_hz, duration)
        for event in events
    )
    measured_dips = tuple(row["dip_db"] for row in event_measurements)
    measured_settling = tuple(row["settling_s"] for row in event_measurements)
    measured_overshoot = tuple(row["overshoot_db"] for row in event_measurements)
    bypass_before_sha = _sha256_array(np.asarray(render.stems["sc_bypass_release"]))
    bypass_after_sha = _sha256_array(stems["sc_bypass_release"])
    diagnostics.update({
        "pressure_stem_contract": contract,
        "hellcat_shift_model": "separate_hemi_torque_cut_and_supercharger_inertia",
        "hellcat_shift_event_count": len(events),
        "hellcat_shift_event_times_s": tuple(event.time_s for event in events),
        "shift_min_exhaust_gain_measured": float(np.min(exhaust_gain)),
        "shift_min_sc_gain_measured": float(np.min(sc_gain)),
        "supercharger_inertia_retained": True,
        "sustained_throttle_shift_bypass_triggered": bypass_before_sha != bypass_after_sha,
        "sustained_throttle_bypass_before_sha256": bypass_before_sha,
        "sustained_throttle_bypass_after_sha256": bypass_after_sha,
        "generic_shift_dynamics_called": False,
        "fixed_70hz_recovery_used": False,
        "candidate_shift_parameters_read": tuple(sorted(params)),
        "shift_event_measurement_domain": "pre_common_lf_rumble_eq_actual_pressure_waveform",
        "shift_event_measurements": event_measurements,
        "shift_dip_db_measured": float(max(measured_dips, default=0.0)),
        "shift_settling_s_measured": float(max(measured_settling, default=0.0)),
        "shift_overshoot_db_measured": float(max(measured_overshoot, default=0.0)),
    })
    requested = sorted(candidate.requested_parameters())
    shift_names = sorted(f"shift_and_load_transient.{name}" for name in params)
    active_names = {
        "shift_interruption_s", "shift_min_exhaust_gain", "shift_min_sc_gain",
        "reengagement_decay_s", "sc_drive_modulation_depth",
    } if events else set()
    if np.any(tip_in):
        active_names.add("tip_in_blowdown_gain")
    previous_usage = render.diagnostics.get("candidate_parameter_usage", {})
    previous_read = set(previous_usage.get("read", ()))
    previous_configured = set(previous_usage.get("configured", ()))
    previous_active = set(previous_usage.get("active", ()))
    previous_inactive = set(previous_usage.get("inactive", ()))
    l4_active = {f"shift_and_load_transient.{name}" for name in active_names}
    l4_inactive = {f"shift_and_load_transient.{name}" for name in params if name not in active_names}
    diagnostics["candidate_parameter_usage"] = {
        "requested": requested,
        "read": sorted(previous_read | set(shift_names)),
        "configured": sorted(previous_configured | set(shift_names)),
        "active": sorted(previous_active | l4_active),
        "inactive": sorted((previous_inactive | l4_inactive) - previous_active - l4_active),
        "unused": sorted(set(requested) - previous_read - set(shift_names)),
    }
    return replace(render, pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _tip_in_blowdown(
    source: np.ndarray, throttle: np.ndarray, gain: float, sample_rate_hz: int,
) -> np.ndarray:
    result = np.zeros_like(source)
    derivative = np.gradient(throttle) * sample_rate_hz
    indices = np.flatnonzero((derivative > 0.75) & (throttle > 0.35))
    if not indices.size:
        return result
    starts = indices[np.r_[True, np.diff(indices) > 1]]
    length = max(1, int(round(0.060 * sample_rate_hz)))
    for index in starts:
        stop = min(result.shape[0], int(index) + length)
        envelope = np.exp(-np.arange(stop - int(index), dtype=np.float64) / max(0.018 * sample_rate_hz, 1.0))
        result[int(index):stop] += gain * source[int(index):stop] * envelope[:, None]
    return result


def _measure_shift_event(
    before: np.ndarray, after: np.ndarray, event_sample: int, sample_rate_hz: int,
    interruption_s: float,
) -> dict[str, object]:
    """Measure one real shift from fixed pre/dip/post waveform windows."""
    count = before.shape[0]
    pre_start = max(0, event_sample - int(round(0.090 * sample_rate_hz)))
    pre_stop = max(pre_start + 1, event_sample - int(round(0.065 * sample_rate_hz)))
    dip_start = max(0, event_sample - int(round(0.012 * sample_rate_hz)))
    dip_stop = min(count, event_sample + int(round(0.013 * sample_rate_hz)))
    after_start = min(count - 1, event_sample + int(round(0.070 * sample_rate_hz)))
    after_stop = min(count, event_sample + int(round(0.300 * sample_rate_hz)))
    pre_rms = _rms(before[pre_start:pre_stop])
    dip_rms = _rms(after[dip_start:dip_stop])
    dip_db = float(20.0 * np.log10(max(pre_rms, 1.0e-30) / max(dip_rms, 1.0e-30)))

    block = max(1, int(round(0.020 * sample_rate_hz)))
    hops = range(after_start, max(after_start + 1, after_stop - block + 1), block)
    levels = tuple((_rms(after[start:min(count, start + block)]), start) for start in hops)
    tolerance = 10.0 ** (0.50 / 20.0)
    settled = after_stop
    for position, (level, start) in enumerate(levels):
        remaining = levels[position:]
        if remaining and all(pre_rms / tolerance <= value <= pre_rms * tolerance for value, _ in remaining):
            settled = start
            break
    interruption_start = event_sample - int(round(0.5 * interruption_s * sample_rate_hz))
    settling_s = float((settled - interruption_start) / sample_rate_hz)
    post_peak_rms = max((value for value, _ in levels), default=pre_rms)
    overshoot_db = float(max(0.0, 20.0 * np.log10(max(post_peak_rms, 1.0e-30) / max(pre_rms, 1.0e-30))))
    evidence = np.concatenate((
        np.ascontiguousarray(before[pre_start:pre_stop]).ravel(),
        np.ascontiguousarray(after[dip_start:dip_stop]).ravel(),
        np.ascontiguousarray(after[after_start:after_stop]).ravel(),
    ))
    return {
        "event_sample": int(event_sample),
        "before_window": (int(pre_start), int(pre_stop)),
        "dip_window": (int(dip_start), int(dip_stop)),
        "after_window": (int(after_start), int(after_stop)),
        "before_rms": pre_rms,
        "dip_rms": dip_rms,
        "dip_db": dip_db,
        "settling_s": settling_s,
        "overshoot_db": overshoot_db,
        "measurement_sha256": _sha256_array(evidence),
    }


def _rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(np.asarray(value, dtype=np.float64)))))


def _sha256_array(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value, dtype="<f8").tobytes()).hexdigest()


__all__ = ("apply_hellcat_transient_dynamics",)
