"""C63 W204 adapter for the current Stage-K source and AH output guard.

The C63 source is already a current, deterministic Stage-K source. This small
adapter gives it the same final-domain contract used by AH-C1 without changing
the four-vehicle AH/R1 registry.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from scipy import signal

from ..contracts import SourceRender, VehicleStateTrace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade
from ..stage_ad.engine_sim_acoustics import SOUND_LIB_DIR, load_impulse_response
from ..stage_k.candidate_profiles import load_stage_k_candidate
from ..stage_k.render_candidate import render_stage_k_candidate
from .engine import spectrum_report
from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    OUTPUT_GUARD_RECEIPT_SCHEMA,
    GuardConfig,
    ceiling_run_metrics,
    linked_soft_ceiling,
)


C63_VEHICLE = "c63_w204"
C63_SOURCE_VARIANT = "c63_stage_k_v2"
C63_CANDIDATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "targets"
    / "stage_k_candidates"
    / "c63_w204_candidate_v2.json"
)
C63_IR_NAME = "mild_exhaust_reverb"
C63_IR_VOLUME = 0.015


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _trace_sha256(
    rpm: np.ndarray,
    throttle: np.ndarray,
    duration: float,
    shift_events: object,
    afterfire_events: object,
    bov_events: object,
) -> str:
    digest = hashlib.sha256()
    for curve in (rpm, throttle):
        array = np.ascontiguousarray(curve, dtype="<f8")
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes())
    digest.update(repr((float(duration), shift_events, afterfire_events, bov_events)).encode("utf-8"))
    return digest.hexdigest()


def _curve(values: np.ndarray, count: int, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be nonempty and finite")
    if array.size != count:
        array = np.interp(
            np.linspace(0.0, 1.0, count),
            np.linspace(0.0, 1.0, array.size),
            array,
        )
    return array


def _resolve_ir_path(name: str) -> Path | None:
    root = Path(os.environ.get("S12_ENGINE_SIM_IR_ROOT", SOUND_LIB_DIR))
    for candidate in (
        root / "new" / f"{name}.wav",
        root / "archive" / f"{name}.wav",
        root / "smooth" / f"{name}.wav",
        root / f"{name}.wav",
    ):
        if candidate.is_file():
            return candidate.resolve()
    return None


def _spectrum(values: np.ndarray, sample_rate: int) -> dict[str, object]:
    """Return an uncalibrated digital spectrum for one source stem."""
    return spectrum_report(values, sample_rate)


class C63Engine:
    """Render C63 Stage-K source through the AH-C1 final-domain contract."""

    def __init__(
        self,
        vehicle_type: str = C63_VEHICLE,
        sr: int = 48_000,
        *,
        output_policy: str = LEGACY_CLIP_V1,
        parent_peaks: Mapping[int, float] | None = None,
        ir: np.ndarray | None = None,
        candidate_path: str | Path = C63_CANDIDATE_PATH,
        seed: int = 20260908,
    ) -> None:
        if vehicle_type != C63_VEHICLE:
            raise ValueError("C63Engine only supports c63_w204")
        if int(sr) != 48_000:
            raise ValueError("C63 AH qualification requires 48 kHz")
        if output_policy not in (LEGACY_CLIP_V1, LINKED_SOFT_CEILING_V1):
            raise ValueError(f"unsupported C63 output policy: {output_policy}")
        self.vehicle_type = vehicle_type
        self.sr = int(sr)
        self.output_policy = output_policy
        self.seed = int(seed)
        self.candidate = load_stage_k_candidate(candidate_path)
        if ir is None:
            self.ir = load_impulse_response(C63_IR_NAME, target_sr=self.sr, max_samples=12_000)
            self.ir_source_path = _resolve_ir_path(C63_IR_NAME)
        else:
            self.ir = np.asarray(ir, dtype=np.float64).reshape(-1)
            if self.ir.size == 0 or not np.all(np.isfinite(self.ir)) or not np.any(self.ir):
                raise ValueError("injected C63 IR must be finite and nonzero")
            self.ir_source_path = None
        self.parent_peaks = dict(parent_peaks or {})
        self.reports: list[dict[str, object]] = []
        self.scene_index = 0

    @property
    def ir_source_sha256(self) -> str | None:
        if self.ir_source_path is None:
            return None
        return _sha256_bytes(self.ir_source_path.read_bytes())

    def _pre_guard(
        self,
        rpm_curve: np.ndarray,
        throttle_curve: np.ndarray,
        duration: float,
        shift_events: object,
        afterfire_events: object,
        bov_events: object,
    ) -> tuple[np.ndarray, SourceRender, float, float, str]:
        if not np.isfinite(duration) or duration <= 0.0:
            raise ValueError("duration must be finite and positive")
        count = int(round(self.sr * float(duration)))
        if count < 2:
            raise ValueError("C63 track must contain at least two samples")
        rpm = _curve(rpm_curve, count, name="rpm_curve")
        throttle = np.clip(_curve(throttle_curve, count, name="throttle_curve"), 0.0, 1.0)
        time_s = np.arange(count, dtype=np.float64) / float(self.sr)
        trace = VehicleStateTrace(
            time_s=time_s,
            rpm=rpm,
            load=throttle,
            throttle=throttle,
            acceleration_mps2=np.gradient(rpm / 60.0, time_s),
        ).validate()
        source = render_stage_k_candidate(C63_VEHICLE, trace, self.candidate)
        pressure = np.asarray(source.pressure, dtype=np.float64)
        ir_scaled = self.ir * C63_IR_VOLUME
        convolved = np.column_stack(
            [signal.fftconvolve(pressure[:, channel], ir_scaled, mode="same") for channel in range(2)]
        )
        post_ir = 0.12 * pressure + 0.88 * convolved
        ptr_audio = _edge_fade(_apply_frozen_ptr(post_ir))
        actual_peak = float(np.max(np.abs(ptr_audio)))
        if actual_peak <= 0.0:
            raise ValueError("C63 pre-saturation output is silent")
        if self.scene_index not in self.parent_peaks:
            self.parent_peaks[self.scene_index] = actual_peak
        denominator = float(self.parent_peaks[self.scene_index])
        if not np.isfinite(denominator) or denominator <= 0.0:
            raise ValueError("C63 parent denominator must be finite and positive")
        normalized = ptr_audio / denominator
        pre_guard = np.tanh(normalized * 1.5) / np.tanh(1.5) * 0.94
        return (
            pre_guard,
            source,
            actual_peak,
            denominator,
            _trace_sha256(rpm, throttle, duration, shift_events, afterfire_events, bov_events),
        )

    def render_track(
        self,
        rpm_curve: np.ndarray,
        throttle_curve: np.ndarray,
        duration: float,
        shift_events: list | None = None,
        afterfire_events: list | None = None,
        bov_events: list | None = None,
    ) -> np.ndarray:
        pre_guard, source, actual_peak, denominator, trace_sha = self._pre_guard(
            rpm_curve,
            throttle_curve,
            duration,
            shift_events,
            afterfire_events,
            bov_events,
        )
        pre_guard_metrics = ceiling_run_metrics(pre_guard, sample_rate=self.sr)
        if self.output_policy == LINKED_SOFT_CEILING_V1:
            final_float, guard = linked_soft_ceiling(
                pre_guard, GuardConfig(), sample_rate=self.sr
            )
        else:
            final_float = np.clip(pre_guard, -0.94, 0.94)
            guard = {
                "receipt_schema": "s12.stage_ah.output_guard_receipt.v1",
                "output_policy": LEGACY_CLIP_V1,
                "knee_linear": None,
                "ceiling_linear": 0.94,
                "stereo_link": "legacy_renderer_path",
                "parent_denominator_policy": "caller_supplied_fixed_parent_peak",
                "frame_count": int(len(pre_guard)),
                "legacy_ceiling_input_exceedance_samples": int(
                    pre_guard_metrics["ceiling_input_exceedance_samples"]
                ),
                "legacy_transfer_pre_guard_peak": float(np.max(np.abs(pre_guard))),
                "pre_guard_exceedance_longest_run": pre_guard_metrics["exceedance_longest_run"],
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
        pcm = (np.asarray(final_float, dtype=np.float64) * 32767.0).astype(np.int16)
        source_stems = {
            name: _spectrum(np.asarray(values, dtype=np.float64), self.sr)
            for name, values in source.stems.items()
        }
        report = {
            "vehicle": C63_VEHICLE,
            "source_variant": C63_SOURCE_VARIANT,
            "output_policy": self.output_policy,
            "trace_sha256": trace_sha,
            "parent_peak": denominator,
            "candidate_raw_peak": actual_peak,
            "normalization_denominator": denominator,
            "parent_denominator_policy": "fixed_parent_peak",
            "ir_name": C63_IR_NAME,
            "ir_volume": C63_IR_VOLUME,
            "ir_source_path": str(self.ir_source_path) if self.ir_source_path else "INJECTED_TEST_IR",
            "ir_source_sha256": self.ir_source_sha256,
            "candidate_source_diagnostics": dict(source.diagnostics),
            "candidate_stems": source_stems,
            "normalization": {
                **guard,
                "source_variant": C63_SOURCE_VARIANT,
                "output_policy": self.output_policy,
                "normalization_denominator": denominator,
                "parent_denominator_policy": "caller_supplied_fixed_parent_peak",
                "pre_guard_pcm_sha256": _sha256_bytes(
                    np.ascontiguousarray((pre_guard * 32767.0).astype("<i2")).tobytes()
                ),
            },
            "identity_layer_clip_count": 0,
            "identity_layer_clip_error": 0.0,
            "post_identity_clip_count": 0,
            "post_identity_clip_error": 0.0,
            "final_pcm_sha256": _sha256_bytes(np.ascontiguousarray(pcm, dtype="<i2").tobytes()),
            "note": "C63 Stage-K source; reference audio is local unverified R2 material",
        }
        self.reports.append(report)
        self.scene_index += 1
        return pcm


__all__ = (
    "C63_CANDIDATE_PATH",
    "C63Engine",
    "C63_IR_NAME",
    "C63_IR_VOLUME",
    "C63_SOURCE_VARIANT",
    "C63_VEHICLE",
)
