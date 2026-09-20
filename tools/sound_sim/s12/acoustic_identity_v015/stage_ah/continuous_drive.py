"""Governed continuous-drive A/B rendering for Stage AI-6.

The module renders one complete stateful track per role. It does not concatenate
scene WAVs, search parameters, or change the accepted source algorithms.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from ..render_drive_cycle_v10 import build_drive_cycle_trace
from .feedback_evidence import SCENES, canonical
from .qualification import numeric_ok
from .reconstruction_peak import reconstructed_peak_receipt
from .remaining_vehicle_pipeline import (
    FEEDBACK_BOUNDS,
    LINKED_SOFT_CEILING_V1,
    REMAINING_VEHICLES,
    RX7_BOUNDARY_POLICY_V1,
    RemainingVehicleEngine,
    feedback_parameters,
)

SAMPLE_RATE_HZ = 48_000
DURATION_S = 30.0
CONTINUOUS_SCENE_ID = "continuous_drive"
CONTINUOUS_SCHEMA = "s12.stage_ai6.continuous_drive_pair.v1"


def continuous_events() -> dict[str, list[dict[str, Any]]]:
    """Return the fixed event schedule used by both roles."""
    return {
        "shift_events": [
            {"time_s": 6.16, "kind": "gear_shift", "index": 1},
            {"time_s": 8.68, "kind": "gear_shift", "index": 2},
            {"time_s": 11.20, "kind": "gear_shift", "index": 3},
        ],
        "afterfire_events": [{"time_s": 18.0, "kind": "closed_throttle_lift"}],
        "bov_events": [{"time_s": 18.0, "kind": "lift_bov"}],
    }


def build_continuous_trace(vehicle: str):
    trace = build_drive_cycle_trace(vehicle, DURATION_S)
    if len(trace.time_s) != int(SAMPLE_RATE_HZ * DURATION_S) + 1:
        raise ValueError("continuous trace must contain 30 seconds plus endpoint")
    return trace


def _selected_parameters(vehicle: str, selected: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(selected, Mapping):
        raise ValueError("selected parameters must be an object")
    baseline = feedback_parameters(vehicle, ())['parameters']
    values = dict(baseline)
    for name, raw in selected.items():
        if name not in FEEDBACK_BOUNDS[vehicle]:
            raise ValueError(f"unsupported continuous parameter: {name}")
        value = float(raw)
        low, high = FEEDBACK_BOUNDS[vehicle][name]
        if not np.isfinite(value) or value < low or value > high:
            raise ValueError(f"continuous parameter out of bounds: {name}")
        values[name] = value
    return values


def _pcm_sha(pcm: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest()


def _ir_sha(ir: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(ir, dtype="<f8").tobytes()).hexdigest()


def _validate_report(report: Mapping[str, Any], pcm: np.ndarray) -> dict[str, Any]:
    if not numeric_ok(report):
        raise ValueError("continuous report failed numeric gate")
    if report.get("scene_id") != CONTINUOUS_SCENE_ID:
        raise ValueError("continuous scene identity mismatch")
    if int(report.get("sample_rate_hz", 0)) != SAMPLE_RATE_HZ:
        raise ValueError("continuous sample rate mismatch")
    if int(report.get("sample_count", -1)) != len(pcm):
        raise ValueError("continuous frame count mismatch")
    if report.get("final_pcm_sha256") != _pcm_sha(pcm):
        raise ValueError("continuous PCM identity mismatch")
    recomputed = reconstructed_peak_receipt(
        pcm.astype(np.float64) / 32767.0,
        sample_rate=SAMPLE_RATE_HZ,
    )
    if canonical(recomputed) != canonical(report.get("reconstruction_peak")):
        raise ValueError("continuous reconstructed-peak receipt mismatch")
    return recomputed


def _validate_event_diagnostics(report: Mapping[str, Any], events: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics=report.get('candidate_source_diagnostics', {})
    shifts=int(diagnostics.get('shift_event_count', -1))
    afterfire=int(diagnostics.get('afterfire_event_count', -1))
    energy=float(diagnostics.get('afterfire_stem_energy',
                                diagnostics.get('afterfire_thermal_peak', 0.0)))
    if shifts != len(events['shift_events']):
        raise ValueError('continuous renderer shift diagnostics mismatch')
    if afterfire <= 0 or not np.isfinite(energy) or energy <= 0.0:
        raise ValueError('continuous renderer afterfire diagnostics missing')
    return {'shift_count': shifts, 'afterfire_event_count': afterfire,
            'afterfire_stem_energy': energy}


def render_continuous_pair(
    vehicle: str,
    selected_parameters: Mapping[str, float],
    *,
    duration_s: float = DURATION_S,
    ir: np.ndarray | None = None,
    boundary_policy: str | None = None,
) -> dict[str, Any]:
    """Render A/B once each with identical state, IR, and parent denominator."""
    if vehicle not in REMAINING_VEHICLES:
        raise ValueError(f"continuous feedback is unavailable for {vehicle}")
    if float(duration_s) != DURATION_S:
        raise ValueError("continuous drive is fixed at 30 seconds")
    expected_boundary = RX7_BOUNDARY_POLICY_V1 if vehicle == "rx7_fd" else None
    if boundary_policy != expected_boundary:
        raise ValueError("continuous boundary policy does not match vehicle scope")
    selected = _selected_parameters(vehicle, selected_parameters)
    trace = build_continuous_trace(vehicle)
    events = continuous_events()
    rpm, throttle = trace.rpm[:-1], trace.throttle[:-1]
    engine_a = RemainingVehicleEngine(
        vehicle, SAMPLE_RATE_HZ, output_policy=LINKED_SOFT_CEILING_V1,
        ir=ir, seed=20260908, scene_ids=(CONTINUOUS_SCENE_ID,),
        boundary_policy=boundary_policy,
    )
    pcm_a = engine_a.render_track(rpm, throttle, DURATION_S, **events)
    report_a = copy.deepcopy(engine_a.reports[-1])
    diagnostic_a = _validate_event_diagnostics(report_a, events)
    parent_peaks = copy.deepcopy(engine_a.parent_peaks)
    shared_ir = np.asarray(engine_a.ir, dtype=np.float64).copy()

    engine_b = RemainingVehicleEngine(
        vehicle, SAMPLE_RATE_HZ, output_policy=LINKED_SOFT_CEILING_V1,
        parent_peaks=parent_peaks, ir=shared_ir, seed=20260908,
        scene_ids=(CONTINUOUS_SCENE_ID,), boundary_policy=boundary_policy,
    )
    engine_b.feedback["parameters"].update(selected)
    pcm_b = engine_b.render_track(rpm, throttle, DURATION_S, **events)
    report_b = copy.deepcopy(engine_b.reports[-1])
    diagnostic_b = _validate_event_diagnostics(report_b, events)

    engine_off = RemainingVehicleEngine(
        vehicle, SAMPLE_RATE_HZ, output_policy=LINKED_SOFT_CEILING_V1,
        parent_peaks=parent_peaks, ir=shared_ir, seed=20260908,
        scene_ids=(CONTINUOUS_SCENE_ID,), boundary_policy=boundary_policy,
    )
    pcm_off = engine_off.render_track(rpm, throttle, DURATION_S, **events)
    report_off = copy.deepcopy(engine_off.reports[-1])
    _validate_event_diagnostics(report_off, events)
    _validate_report(report_a, pcm_a)
    _validate_report(report_b, pcm_b)
    _validate_report(report_off, pcm_off)
    for field in ("trace_sha256", "seed", "flags", "parent_peak_key",
                  "normalization_denominator", "output_policy", "sample_rate_hz"):
        if report_a.get(field) != report_b.get(field):
            raise ValueError(f"continuous A/B {field} mismatch")
    if not np.array_equal(pcm_a, pcm_off):
        raise ValueError("continuous feedback-off rerender changed A")
    if diagnostic_a != diagnostic_b:
        raise ValueError("continuous A/B event diagnostics mismatch")
    boundary = report_a.get("boundary_repair", {})
    if vehicle == "rx7_fd" and (boundary.get("policy_id") != RX7_BOUNDARY_POLICY_V1
                                 or boundary.get("fade_frames") != 24):
        raise ValueError("RX-7 continuous boundary receipt is not start-only 24 frames")
    if vehicle == "aventador_lp700" and boundary.get("policy_id") is not None:
        raise ValueError("Aventador continuous path has an RX-7 boundary policy")
    receipt = {
        "schema": CONTINUOUS_SCHEMA,
        "vehicle": vehicle,
        "duration_s": DURATION_S,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "scene_id": CONTINUOUS_SCENE_ID,
        "shared": {
            "seed": 20260908,
            "trace_sha256": report_a["trace_sha256"],
            "parent_peak_key": report_a["parent_peak_key"],
            "normalization_denominator": report_a["normalization_denominator"],
            "output_policy": LINKED_SOFT_CEILING_V1,
            "ir_array_sha256": _ir_sha(shared_ir),
            "ir_source_path": report_a.get("ir_source_path"),
            "ir_source_sha256": report_a.get("ir_source_sha256"),
        },
        "events": {
            "shift_count": diagnostic_a["shift_count"],
            "shift_events": events["shift_events"],
            "afterfire_event_count": diagnostic_a["afterfire_event_count"],
            "afterfire_stem_energy": diagnostic_a["afterfire_stem_energy"],
            "afterfire_events": events["afterfire_events"],
            "bov_events": events["bov_events"],
            "stateful_single_render_per_role": True,
        },
        "parameters": {
            "baseline": feedback_parameters(vehicle, ())['parameters'],
            "selected": selected,
        },
        "boundary": boundary,
        "wav": {
            "A": {"decoded_pcm_sha256": _pcm_sha(pcm_a), "frame_count": len(pcm_a)},
            "B": {"decoded_pcm_sha256": _pcm_sha(pcm_b), "frame_count": len(pcm_b)},
        },
        "reports": {"A": report_a, "B": report_b, "off_switch": report_off},
        "feedback_off_pcm_equal": True,
        "human_status": "NOT_EVALUATED",
        "promotable": False,
    }
    return {
        "receipt": receipt,
        "trace": trace,
        "events": events,
        "pcm_a": pcm_a,
        "pcm_b": pcm_b,
        "pcm_off_switch": pcm_off,
        "report_a": report_a,
        "report_b": report_b,
        "report_off": report_off,
    }


def write_continuous_pair(root: Path, pair: Mapping[str, Any]) -> dict[str, Any]:
    """Write governed A/B WAVs and receipt under an existing package staging root."""
    root = Path(root)
    receipt = copy.deepcopy(pair.get("receipt", {}))
    if receipt.get("schema") != CONTINUOUS_SCHEMA or not receipt.get("vehicle"):
        raise ValueError("continuous receipt identity is required")
    pcm_a=np.asarray(pair.get("pcm_a"));pcm_b=np.asarray(pair.get("pcm_b"))
    if (pcm_a.dtype!=np.int16 or pcm_b.dtype!=np.int16
            or pcm_a.shape!=(1_440_000,2) or pcm_b.shape!=(1_440_000,2)):
        raise ValueError("continuous pair must be 30-second stereo int16")
    reports=receipt.get('reports')
    if not isinstance(reports, Mapping) or not all(role in reports for role in ('A','B','off_switch')):
        raise ValueError("continuous report evidence is required")
    for role,pcm in (('A',pcm_a),('B',pcm_b)):
        report=reports[role]
        if (report.get('vehicle')!=receipt.get('vehicle')
                or report.get('scene_id')!=CONTINUOUS_SCENE_ID
                or int(report.get('sample_count',-1))!=len(pcm)
                or report.get('final_pcm_sha256')!=_pcm_sha(pcm)):
            raise ValueError("continuous report/audio identity mismatch")
    audio = root / "web_audio"
    audio.mkdir(parents=True, exist_ok=True)
    wavfile.write(audio / "A_continuous_drive.wav", SAMPLE_RATE_HZ, pair["pcm_a"])
    wavfile.write(audio / "B_continuous_drive.wav", SAMPLE_RATE_HZ, pair["pcm_b"])
    receipt.setdefault("wav", {})
    receipt["wav"].setdefault("A", {})["decoded_pcm_sha256"] = _pcm_sha(pcm_a)
    receipt["wav"].setdefault("B", {})["decoded_pcm_sha256"] = _pcm_sha(pcm_b)
    receipt["wav"]["A"]["wav_file_sha256"] = hashlib.sha256(
        (audio / "A_continuous_drive.wav").read_bytes()).hexdigest()
    receipt["wav"]["B"]["wav_file_sha256"] = hashlib.sha256(
        (audio / "B_continuous_drive.wav").read_bytes()).hexdigest()
    (root / "continuous_drive_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt


__all__ = (
    "CONTINUOUS_SCENE_ID", "CONTINUOUS_SCHEMA", "DURATION_S", "SAMPLE_RATE_HZ",
    "build_continuous_trace", "continuous_events", "render_continuous_pair",
    "write_continuous_pair",
)
