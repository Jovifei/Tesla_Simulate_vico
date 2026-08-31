"""Deterministic per-field perturbation evidence for Stage-G candidates."""

from __future__ import annotations

from collections.abc import Mapping
import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from .candidate_profiles import StageGCandidateProfile
from .render_candidate import render_stage_g_candidate


def audit_candidate_parameter_reachability(
    candidate: StageGCandidateProfile,
    trace: VehicleStateTrace,
) -> dict[str, object]:
    """Show that each public field changes its intended pre-PTR calculation.

    The audit is intentionally an execution test rather than a schema test. A
    field is only considered consumed when the renderer reports it and an
    isolated in-range perturbation changes the mapped stem (or, for a transient
    whose stem is silent in the selected trace, the complete pressure).
    """
    trace.validate()
    baseline = render_stage_g_candidate(candidate.vehicle_id, trace, candidate)
    usage = baseline.diagnostics.get("candidate_parameter_usage", {})
    requested = sorted(candidate.requested_parameters())
    consumed = sorted(set(usage.get("consumed", ())))
    evidence: list[dict[str, object]] = []
    unused = sorted(set(requested) - set(consumed))
    for qualified in requested:
        if qualified.startswith("loudness.transient_peak_shaper."):
            section, name = "loudness", qualified.rsplit(".", 1)[1]
        else:
            section, name = qualified.rsplit(".", 1)
        if section == "loudness":
            entry = candidate.payload["loudness"]["transient_peak_shaper"][name]
        else:
            entry = candidate.payload[section][name]
        value = float(entry["value"])
        low, high = (float(entry["range"][0]), float(entry["range"][1]))
        delta = max((high - low) * 0.20, 1e-6)
        modified_value = min(high, value + delta)
        if modified_value == value:
            modified_value = max(low, value - delta)
        modified = candidate.with_parameter(section, name, modified_value)
        changed = render_stage_g_candidate(candidate.vehicle_id, trace, modified)
        target_names = _target_stems(candidate.vehicle_id, section, name)
        target_l2 = 0.0
        for stem_name in target_names:
            if stem_name in baseline.stems and stem_name in changed.stems:
                before = np.asarray(baseline.stems[stem_name], dtype=np.float64)
                after = np.asarray(changed.stems[stem_name], dtype=np.float64)
                target_l2 += float(np.linalg.norm(after - before) / max(np.linalg.norm(before), 1.0))
        if target_l2 == 0.0 and section == "shift":
            probe_trace = _shift_probe_trace(trace)
            probe_before = render_stage_g_candidate(candidate.vehicle_id, probe_trace, candidate)
            probe_after = render_stage_g_candidate(candidate.vehicle_id, probe_trace, modified)
            for stem_name in target_names:
                if stem_name in probe_before.stems and stem_name in probe_after.stems:
                    before = np.asarray(probe_before.stems[stem_name], dtype=np.float64)
                    after = np.asarray(probe_after.stems[stem_name], dtype=np.float64)
                    target_l2 += float(np.linalg.norm(after - before) / max(np.linalg.norm(before), 1.0))
        if target_l2 == 0.0:
            target_l2 = float(np.linalg.norm(changed.pressure - baseline.pressure) / max(np.linalg.norm(baseline.pressure), 1.0))
        evidence.append({
            "name": qualified,
            "value": value,
            "perturbed_value": modified_value,
            "target_stems": list(target_names),
            "target_l2_delta": target_l2,
            "consumed": qualified in consumed,
        })
    return {
        "vehicle_id": candidate.vehicle_id,
        "candidate_id": candidate.candidate_id,
        "requested": requested,
        "consumed": consumed,
        "unused": unused,
        "parameters": evidence,
        "deterministic": True,
        "provenance": "C/synthetic; candidate perturbation evidence; uncalibrated; not OEM reproduction",
    }


def _shift_probe_trace(trace: VehicleStateTrace) -> VehicleStateTrace:
    """Create a deterministic local shift probe when the supplied trace has none."""
    time_s = np.asarray(trace.time_s, dtype=np.float64)
    duration = float(time_s[-1] - time_s[0])
    if duration < 1.0:
        return trace
    base = np.interp(time_s, (time_s[0], time_s[-1]), (3200.0, 5600.0))
    center = time_s[0] + 0.42 * duration
    fall = np.clip((time_s - (center - 0.06)) / 0.12, 0.0, 1.0)
    shape = np.where(fall <= 0.5, 2.0 * fall, 2.0 * (1.0 - fall))
    rpm = base - 1500.0 * np.clip(shape, 0.0, 1.0)
    load = np.full_like(time_s, 0.82)
    throttle = np.full_like(time_s, 0.86)
    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _target_stems(vehicle_id: str, section: str, name: str) -> tuple[str, ...]:
    if section == "source":
        if vehicle_id == "ferrari_458":
            return ("left_bank", "right_bank", "metallic")
        if vehicle_id == "hellcat":
            return ("blower",)
        if name.startswith("blow_off"):
            return ("blow_off", "lift")
        if name.startswith("rotary"):
            return ("rotary",)
        return ("turbo", "turbine")
    if section == "idle":
        return ("idle_combustion_variation", "idle_accessory", "idle_valvetrain", "idle_crank")
    if section == "afterfire":
        return ("afterfire",)
    if section == "shift":
        return ("shift_impact", "shift_recovery_boom")
    return ("shift_impact", "shift_recovery_boom", "afterfire", "blower_attack")


__all__ = ("audit_candidate_parameter_reachability",)
