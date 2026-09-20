"""Two-car AH diagnostic adapter with bounded, manual feedback control.

The adapter keeps the existing Stage-G RX-7 source and Stage-C Aventador source
in front of the shared IR/PTR boundary.  Feedback is an explicit, finite JSON
input that changes only named source stems; it never searches parameters or
changes the fixed output ceiling.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal

from ..contracts import SourceRender, VehicleStateTrace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..sources.lamborghini_v12_source import render_aventador_lp700
from ..stage_ad.engine_sim_acoustics import SOUND_LIB_DIR, load_impulse_response
from ..stage_g.candidate_profiles import load_stage_g_candidate
from ..stage_g.render_candidate import render_stage_g_candidate
from .engine import input_sha, spectrum_report
from .fourcar_pipeline import peak_estimate_4x, scene_trace_key
from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    GuardConfig,
    ceiling_run_metrics,
    linked_soft_ceiling,
)
from .rx7_boundary_repair import (
    RX7_BOUNDARY_POLICY_V1,
    apply_rx7_boundary_repair,
)
from .reconstruction_peak import reconstructed_peak_receipt


_SAMPLE_RATE_HZ = 48_000
REMAINING_VEHICLES = ("rx7_fd", "aventador_lp700")
RX7_CANDIDATE_PATH = (
    Path(__file__).resolve().parents[1] / "targets" / "stage_g_candidates" / "RX7_candidate_v4.json"
)
IR_NAMES = {vehicle: "mild_exhaust_reverb" for vehicle in REMAINING_VEHICLES}
IR_VOLUMES = {vehicle: 0.015 for vehicle in REMAINING_VEHICLES}
SOURCE_VARIANTS = {
    "rx7_fd": "rx7_stage_g_feedback_v1",
    "aventador_lp700": "aventador_stage_c_feedback_v1",
}
FEEDBACK_BOUNDS = {
    "rx7_fd": {
        "rotary_pulse_width_scale": (0.85, 1.15),
        "primary_spool_tau_s": (0.12, 0.22),
        "blow_off_gain_scale": (0.80, 1.40),
    },
    "aventador_lp700": {
        "v12_wail_mix": (0.75, 1.25),
        "v12_scream_mix": (0.75, 1.25),
        "v12_intake_mix": (0.75, 1.25),
    },
}
FEEDBACK_TAGS = {
    "rx7_fd": {
        "rotary_weak": ("rotary_pulse_width_scale", 1),
        "rotary_buzzy": ("rotary_pulse_width_scale", -1),
        "turbo_late": ("primary_spool_tau_s", -1),
        "turbo_early": ("primary_spool_tau_s", 1),
        "blowoff_weak": ("blow_off_gain_scale", 1),
        "blowoff_loud": ("blow_off_gain_scale", -1),
    },
    "aventador_lp700": {
        "wail_weak": ("v12_wail_mix", 1),
        "wail_bright": ("v12_wail_mix", -1),
        "scream_weak": ("v12_scream_mix", 1),
        "scream_harsh": ("v12_scream_mix", -1),
        "intake_weak": ("v12_intake_mix", 1),
        "intake_loud": ("v12_intake_mix", -1),
    },
}


def _profile_source_parameters() -> dict[str, float]:
    profile = load_stage_g_candidate(RX7_CANDIDATE_PATH)
    return {
        name: float(value["value"] if isinstance(value, Mapping) else value)
        for name, value in profile.payload["source"].items()
    }


def feedback_parameters(vehicle: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply explicit negative feedback to bounded source parameters."""
    if vehicle not in REMAINING_VEHICLES:
        raise ValueError(f"unsupported remaining vehicle: {vehicle}")
    baseline = (
        _profile_source_parameters()
        if vehicle == "rx7_fd"
        else {name: 1.0 for name in FEEDBACK_BOUNDS[vehicle]}
    )
    values = dict(baseline)
    adjustments: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("feedback row must be an object")
        if str(row.get("vehicle", "")) != vehicle:
            raise ValueError("feedback vehicle mismatch")
        if not str(row.get("scene", "")).strip():
            raise ValueError("feedback scene is required")
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not np.isfinite(float(score)):
            raise ValueError("feedback score must be finite")
        score = int(score)
        if score < 1 or score > 5:
            raise ValueError("feedback score must be in [1, 5]")
        tags = row.get("tags", [])
        if not isinstance(tags, list):
            raise ValueError("feedback tags must be a list")
        for tag in tags:
            if tag not in FEEDBACK_TAGS[vehicle]:
                raise ValueError(f"unknown feedback tag: {tag}")
            if score >= 3:
                continue
            parameter, direction = FEEDBACK_TAGS[vehicle][tag]
            before = float(values[parameter])
            step = 0.02 * float(3 - score) * direction
            lower, upper = FEEDBACK_BOUNDS[vehicle][parameter]
            after = float(np.clip(before + step, lower, upper))
            values[parameter] = after
            adjustments.append({
                "scene": str(row["scene"]),
                "score": score,
                "tag": str(tag),
                "parameter": parameter,
                "before": before,
                "after": after,
            })
    return {
        "vehicle": vehicle,
        "parameters": values,
        "bounds": {name: list(bounds) for name, bounds in FEEDBACK_BOUNDS[vehicle].items()},
        "adjustments": adjustments,
        "status": "APPLIED" if adjustments else "NO_FEEDBACK",
        "controller": "manual_negative_feedback_bounded_step_v1",
    }


def apply_negative_feedback(vehicle: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return feedback_parameters(vehicle, rows)


def apply_named_stem_scales(render: SourceRender, scales: Mapping[str, float]) -> SourceRender:
    """Scale named stems and preserve all non-target stems byte-for-byte."""
    render.validate()
    pressure = np.asarray(render.pressure, dtype=np.float64).copy()
    stems = {name: np.asarray(values, dtype=np.float64).copy() for name, values in render.stems.items()}
    for name, raw_scale in scales.items():
        if name not in stems:
            raise ValueError(f"unknown source stem: {name}")
        scale = float(raw_scale)
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError(f"invalid source stem scale: {name}")
        pressure += (scale - 1.0) * stems[name]
        stems[name] *= scale
    diagnostics = dict(render.diagnostics)
    diagnostics["feedback_stem_scales"] = {str(name): float(value) for name, value in scales.items()}
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def validate_source_pool(payload: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("vehicles"), Mapping):
        raise ValueError("source pool vehicles are required")
    counts: dict[str, int] = {}
    for vehicle in REMAINING_VEHICLES:
        entry = payload["vehicles"].get(vehicle)
        sources = entry.get("selected_sources") if isinstance(entry, Mapping) else None
        if not isinstance(sources, list) or len(sources) < 6:
            raise ValueError(f"{vehicle} requires at least six source recordings")
        ids = []
        for source in sources:
            if not isinstance(source, Mapping) or not str(source.get("video_id", "")).strip():
                raise ValueError(f"{vehicle} source video_id is required")
            ids.append(str(source["video_id"]))
        if len(set(ids)) != len(ids):
            raise ValueError(f"{vehicle} source video_ids must be unique")
        counts[vehicle] = len(ids)
    return counts


def _resolve_ir_path(name: str) -> Path | None:
    root = Path(os.environ.get("S12_ENGINE_SIM_IR_ROOT", SOUND_LIB_DIR))
    for candidate in (root / "new" / f"{name}.wav", root / "archive" / f"{name}.wav", root / "smooth" / f"{name}.wav", root / f"{name}.wav"):
        if candidate.is_file():
            return candidate.resolve()
    return None


def _feedback_source(vehicle: str, trace: VehicleStateTrace, feedback: Mapping[str, Any]) -> SourceRender:
    parameters = dict(feedback["parameters"])
    if vehicle == "rx7_fd":
        profile = load_stage_g_candidate(RX7_CANDIDATE_PATH)
        for name, value in parameters.items():
            if name in profile.payload["source"]:
                profile = profile.with_parameter("source", name, float(value))
        source = render_stage_g_candidate(vehicle, trace, profile)
    else:
        source = _render_stateful(_RENDERERS[vehicle], vehicle, trace)
        source = apply_named_stem_scales(
            source,
            {
                "wail": parameters["v12_wail_mix"],
                "scream": parameters["v12_scream_mix"],
                "intake": parameters["v12_intake_mix"],
            },
        )
    diagnostics = dict(source.diagnostics)
    diagnostics["feedback_control"] = feedback
    diagnostics["source_variant"] = SOURCE_VARIANTS[vehicle]
    return replace(source, diagnostics=diagnostics).validate()


class RemainingVehicleEngine:
    """Render RX-7 or Aventador with fixed parent peak and linked ceiling."""

    def __init__(
        self,
        vehicle_type: str,
        sr: int = _SAMPLE_RATE_HZ,
        *,
        output_policy: str = LEGACY_CLIP_V1,
        parent_peaks: Mapping[str, float] | None = None,
        ir: np.ndarray | None = None,
        seed: int = 20260908,
        scene_ids: tuple[str, ...] | None = None,
        feedback_rows: Sequence[Mapping[str, Any]] = (),
        boundary_policy: str | None = None,
    ) -> None:
        if vehicle_type not in REMAINING_VEHICLES:
            raise ValueError(f"unsupported remaining vehicle: {vehicle_type}")
        if int(sr) != _SAMPLE_RATE_HZ:
            raise ValueError("remaining AH qualification requires 48 kHz")
        if output_policy not in (LEGACY_CLIP_V1, LINKED_SOFT_CEILING_V1):
            raise ValueError(f"unsupported output policy: {output_policy}")
        if boundary_policy not in (None, RX7_BOUNDARY_POLICY_V1):
            raise ValueError(f"unsupported boundary policy: {boundary_policy}")
        if boundary_policy is not None and vehicle_type != "rx7_fd":
            raise ValueError("RX-7 boundary policy is scoped to rx7_fd")
        self.vehicle_type = vehicle_type
        self.sr = int(sr)
        self.output_policy = output_policy
        self.boundary_policy = boundary_policy
        self.seed = int(seed)
        self.feedback = feedback_parameters(vehicle_type, feedback_rows)
        self._parent_peaks_supplied = parent_peaks is not None
        self.parent_peaks = dict(parent_peaks or {})
        self.scene_ids = tuple(str(value) for value in (scene_ids or ()))
        self.scene_index = 0
        self.reports: list[dict[str, Any]] = []
        self.last_scene_id = "UNBOUND_SCENE"
        self.last_parent_peak_key = ""
        ir_name = IR_NAMES[vehicle_type]
        if ir is None:
            self.ir = load_impulse_response(ir_name, target_sr=self.sr, max_samples=12_000)
            self.ir_source_path = _resolve_ir_path(ir_name)
        else:
            self.ir = np.asarray(ir, dtype=np.float64).reshape(-1)
            if self.ir.size == 0 or not np.all(np.isfinite(self.ir)) or not np.any(self.ir):
                raise ValueError("injected IR must be finite and nonzero")
            self.ir_source_path = None

    @property
    def ir_source_sha256(self) -> str | None:
        return hashlib.sha256(self.ir_source_path.read_bytes()).hexdigest() if self.ir_source_path else None

    def _scene_id(self) -> str:
        if self.scene_ids:
            if self.scene_index >= len(self.scene_ids):
                raise ValueError(f"{self.vehicle_type} scene_ids exhausted")
            return self.scene_ids[self.scene_index]
        return "UNBOUND_SCENE"

    def render_track(
        self,
        rpm_curve: np.ndarray,
        throttle_curve: np.ndarray,
        duration: float,
        shift_events: list | None = None,
        afterfire_events: list | None = None,
        bov_events: list | None = None,
    ) -> np.ndarray:
        if not np.isfinite(duration) or duration <= 0.0:
            raise ValueError("duration must be finite and positive")
        count = int(round(self.sr * float(duration)))
        if count < 2:
            raise ValueError("track must contain at least two samples")
        rpm = np.asarray(rpm_curve, dtype=np.float64).reshape(-1)
        throttle = np.asarray(throttle_curve, dtype=np.float64).reshape(-1)
        if rpm.size == 0 or throttle.size == 0 or not np.all(np.isfinite(rpm)) or not np.all(np.isfinite(throttle)):
            raise ValueError("curves must be finite and nonempty")
        if rpm.size != count:
            rpm = np.interp(np.linspace(0.0, 1.0, count), np.linspace(0.0, 1.0, rpm.size), rpm)
        if throttle.size != count:
            throttle = np.interp(np.linspace(0.0, 1.0, count), np.linspace(0.0, 1.0, throttle.size), throttle)
        throttle = np.clip(throttle, 0.0, 1.0)
        time_s = np.arange(count, dtype=np.float64) / float(self.sr)
        trace = VehicleStateTrace(time_s, rpm, throttle, throttle, np.gradient(rpm / 60.0, time_s)).validate()
        trace_sha = input_sha(rpm, throttle, duration, [shift_events, afterfire_events, bov_events])
        scene_id = self._scene_id()
        parent_key = scene_trace_key(scene_id, trace_sha)
        source = _feedback_source(self.vehicle_type, trace, self.feedback)
        source_diagnostics = dict(source.diagnostics)
        afterfire_stem = np.asarray(source.stems.get("afterfire", np.zeros(len(trace.time_s))), dtype=np.float64)
        afterfire_times = tuple(
            float(event.get("time_s")) for event in (afterfire_events or [])
            if isinstance(event, Mapping) and np.isfinite(float(event.get("time_s", -1.0)))
        )
        if afterfire_times:
            start = max(0, min(len(afterfire_stem), int(round(min(afterfire_times) * self.sr))))
            source_diagnostics["afterfire_event_times_s"] = list(afterfire_times)
            source_diagnostics["afterfire_stem_energy_after_lift"] = float(
                np.sum(np.square(afterfire_stem[start:]))
            )
        else:
            source_diagnostics["afterfire_event_times_s"] = []
            source_diagnostics["afterfire_stem_energy_after_lift"] = 0.0
        pressure = np.asarray(source.pressure, dtype=np.float64)
        ir_scaled = self.ir * IR_VOLUMES[self.vehicle_type]
        convolved = np.column_stack([signal.fftconvolve(pressure[:, channel], ir_scaled, mode="same") for channel in range(2)])
        ptr_audio = _edge_fade(_apply_frozen_ptr(0.12 * pressure + 0.88 * convolved))
        candidate_raw_peak = float(np.max(np.abs(ptr_audio)))
        if not np.isfinite(candidate_raw_peak) or candidate_raw_peak <= 0.0:
            raise ValueError("candidate source is silent before normalization")
        if parent_key not in self.parent_peaks and self._parent_peaks_supplied:
            raise ValueError(f"{self.vehicle_type} parent denominator missing for scene trace {parent_key}")
        if parent_key not in self.parent_peaks:
            self.parent_peaks[parent_key] = candidate_raw_peak
        denominator = float(self.parent_peaks[parent_key])
        if not np.isfinite(denominator) or denominator <= 0.0:
            raise ValueError("parent denominator must be finite and positive")
        normalized = ptr_audio / denominator
        pre_guard = np.tanh(normalized * 1.5) / np.tanh(1.5) * 0.94
        metrics = ceiling_run_metrics(pre_guard, sample_rate=self.sr)
        if self.output_policy == LINKED_SOFT_CEILING_V1:
            final_float, guard = linked_soft_ceiling(pre_guard, GuardConfig(), sample_rate=self.sr)
        else:
            final_float = np.clip(pre_guard, -0.94, 0.94)
            guard = {
                "receipt_schema": "s12.stage_ah.output_guard_receipt.v1",
                "output_policy": LEGACY_CLIP_V1,
                "knee_linear": None,
                "ceiling_linear": 0.94,
                "stereo_link": "legacy_renderer_path",
                "parent_denominator_policy": "fixed_parent_peak",
                "frame_count": int(len(pre_guard)),
                "legacy_ceiling_input_exceedance_samples": int(metrics["ceiling_input_exceedance_samples"]),
                "legacy_transfer_pre_guard_peak": float(np.max(np.abs(pre_guard))),
                "pre_guard_exceedance_longest_run": metrics["exceedance_longest_run"],
                "pre_guard_peak": float(np.max(np.abs(pre_guard))),
                "soft_guard_active_frames": 0,
                "soft_guard_active_frame_ratio": 0.0,
                "soft_guard_min_gain": 1.0,
                "soft_guard_max_attenuation_db": 0.0,
                "soft_guard_delta_peak": 0.0,
                "soft_guard_delta_rms": 0.0,
                "post_guard_peak": float(np.max(np.abs(final_float))),
                "post_guard_ceiling_exceedance_samples": 0,
                "emergency_clip_count": 0,
                "emergency_clip_error": 0.0,
                "emergency_clip_error_rms": 0.0,
            }
        final_float, boundary_receipt = apply_rx7_boundary_repair(
            final_float, policy=self.boundary_policy
        )
        pcm = (np.asarray(final_float, dtype=np.float64) * 32767.0).astype(np.int16)
        artifact_float = pcm.astype(np.float64) / 32767.0
        reconstruction_peak = reconstructed_peak_receipt(
            artifact_float, sample_rate=self.sr
        )
        source_stems = {name: spectrum_report(np.asarray(values, dtype=np.float64), self.sr) for name, values in source.stems.items()}
        self.last_scene_id = scene_id
        self.last_parent_peak_key = parent_key
        record = {
            "vehicle": self.vehicle_type,
            "scene_id": scene_id,
            "parent_peak_key": parent_key,
            "source_variant": SOURCE_VARIANTS[self.vehicle_type],
            "output_policy": self.output_policy,
            "boundary_policy": self.boundary_policy,
            "feedback_control": self.feedback,
            "reference_pool_source_count": 6,
            "reference_evidence_level": "R3_PUBLIC_RECORDING_UNVERIFIED",
            "identity_mode": "stage_c_source_only_no_ag_r1_identity",
            "trace_sha256": trace_sha,
            "sample_rate_hz": self.sr,
            "sample_count": count,
            "seed": self.seed,
            "flags": [],
            "parent_peak": denominator,
            "candidate_raw_peak": candidate_raw_peak,
            "normalization_denominator": denominator,
            "parent_denominator_policy": "fixed_parent_peak_scene_trace",
            "ir_name": IR_NAMES[self.vehicle_type],
            "ir_volume": IR_VOLUMES[self.vehicle_type],
            "ir_source_path": str(self.ir_source_path) if self.ir_source_path else "INJECTED_TEST_IR",
            "ir_source_sha256": self.ir_source_sha256,
            "candidate_source_diagnostics": source_diagnostics,
            "candidate_stems": source_stems,
            "normalization": {
                **guard,
                "source_variant": SOURCE_VARIANTS[self.vehicle_type],
                "output_policy": self.output_policy,
                "normalization_denominator": denominator,
                "parent_denominator_policy": "fixed_parent_peak_scene_trace",
                "pre_guard_pcm_sha256": hashlib.sha256(np.ascontiguousarray((pre_guard * 32767.0).astype("<i2")).tobytes()).hexdigest(),
                "boundary_repair": boundary_receipt,
            },
            "identity_layer_clip_count": 0,
            "identity_layer_clip_error": 0.0,
            "post_identity_clip_count": 0,
            "post_identity_clip_error": 0.0,
            "final_peak": float(np.max(np.abs(final_float))),
            "final_rms": float(np.sqrt(np.mean(final_float * final_float))),
            "final_pcm_sha256": hashlib.sha256(np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest(),
            "peak_estimate_4x": peak_estimate_4x(final_float),
            "reconstruction_peak": reconstruction_peak,
            "boundary_repair": boundary_receipt,
            "note": "R3 real recordings provide relative cues only; source-local feedback candidate, not OEM reproduction",
        }
        self.reports.append(record)
        self.scene_index += 1
        return pcm


__all__ = (
    "FEEDBACK_BOUNDS",
    "FEEDBACK_TAGS",
    "REMAINING_VEHICLES",
    "RemainingVehicleEngine",
    "SOURCE_VARIANTS",
    "apply_named_stem_scales",
    "apply_negative_feedback",
    "feedback_parameters",
    "validate_source_pool",
)
