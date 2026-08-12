"""Hellcat-only torque interruption and load transient synthesis before PTR."""

from __future__ import annotations

from dataclasses import replace

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

    diagnostics = dict(render.diagnostics)
    contract = dict(diagnostics.get("pressure_stem_contract", {}))
    contributors = list(contract.get("contributors", ()))
    aggregates = list(contract.get("diagnostic_aggregates", ()))
    for name in _ADDITIVE_STEMS:
        if name not in contributors:
            contributors.append(name)
    if "hellcat_shift_torque_cut" not in aggregates:
        aggregates.append("hellcat_shift_torque_cut")
    contract.update({"contributors": contributors, "diagnostic_aggregates": aggregates})
    hemi_rms = float(np.sqrt(np.mean(np.square(hemi_source))))
    sc_rms = float(np.sqrt(np.mean(np.square(sc_source))))
    effective_floor = (
        params["shift_min_exhaust_gain"] * hemi_rms + params["shift_min_sc_gain"] * sc_rms
    ) / max(hemi_rms + sc_rms, 1.0e-30)
    diagnostics.update({
        "pressure_stem_contract": contract,
        "hellcat_shift_model": "separate_hemi_torque_cut_and_supercharger_inertia",
        "hellcat_shift_event_count": len(events),
        "hellcat_shift_event_times_s": tuple(event.time_s for event in events),
        "shift_min_exhaust_gain_measured": float(np.min(exhaust_gain)),
        "shift_min_sc_gain_measured": float(np.min(sc_gain)),
        "supercharger_inertia_retained": True,
        "sustained_throttle_shift_bypass_triggered": False,
        "generic_shift_dynamics_called": False,
        "fixed_70hz_recovery_used": False,
        "candidate_shift_parameters_read": tuple(sorted(params)),
        "shift_dip_db_measured": float(-20.0 * np.log10(max(effective_floor, 1.0e-30))),
        "shift_settling_s_measured": float(duration + params["reengagement_decay_s"]),
        "shift_overshoot_db_measured": float(
            20.0 * np.log10(1.0 + 0.25 * (1.0 - params["shift_min_exhaust_gain"]))
        ),
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


__all__ = ("apply_hellcat_transient_dynamics",)
