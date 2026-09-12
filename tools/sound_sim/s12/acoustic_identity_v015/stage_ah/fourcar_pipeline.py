"""Four-car AH source-local real-reference audition adapter.

The adapter keeps the accepted AH/R1 control path available for comparison and
renders the new candidate from the existing Stage-G/Stage-K source profiles.
The public recordings only supply relative, unsynchronised cues; they never
change the output ceiling, IR, frozen PTR or identity contract.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from scipy import signal

from ..contracts import SourceRender, VehicleStateTrace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade
from ..stage_ad.engine_sim_acoustics import EngineAcoustics, SOUND_LIB_DIR
from ..stage_ag.vehicle_identity_r1 import (
    _state_envelope,
    synthesize_vehicle_identity_layer_r1,
)
from ..stage_ag.vehicle_identity import VEHICLE_IDENTITY_PROFILES
from ..stage_g.candidate_profiles import load_stage_g_candidate
from ..stage_k.candidate_profiles import load_stage_k_candidate
from .engine import spectrum_report
from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    GuardConfig,
    ceiling_run_metrics,
    linked_soft_ceiling,
)
from .source_policy import SourcePolicy, validate_events


_SAMPLE_RATE_HZ = 48_000
_V015_ROOT = Path(__file__).resolve().parents[1]
FOURCAR_VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
FOURCAR_TARGET_PATH = _V015_ROOT / "reference_database" / "fourcar_real_reference_targets_v1.json"
REAL_REFERENCE_PROFILE_PATHS = {
    "hellcat": _V015_ROOT / "targets" / "fourcar_real_reference" / "hellcat_real_reference_v7.json",
    "ferrari_458": _V015_ROOT / "targets" / "fourcar_real_reference" / "Ferrari_real_reference_v4.json",
    "lfa": _V015_ROOT / "targets" / "fourcar_real_reference" / "lfa_real_reference_v2.json",
    "gtr_r35": _V015_ROOT / "targets" / "fourcar_real_reference" / "gtr_r35_real_reference_v2.json",
}
REAL_REFERENCE_BASE_PATHS = {
    "hellcat": _V015_ROOT / "targets" / "stage_k_candidates" / "hellcat_candidate_v7.json",
    "ferrari_458": _V015_ROOT / "targets" / "stage_g_candidates" / "Ferrari_candidate_v4.json",
    "lfa": _V015_ROOT / "targets" / "stage_k_candidates" / "lfa_candidate_v2.json",
    "gtr_r35": _V015_ROOT / "targets" / "stage_k_candidates" / "gtr_r35_candidate_v2.json",
}
REAL_REFERENCE_CHANGED_PARAMETERS = {
    "hellcat": "blower_gain_scale",
    "ferrari_458": "high_rpm_growth_scale",
    "lfa": "high_rpm_growth_scale",
    "gtr_r35": "turbo_whistle_mix",
}
REAL_REFERENCE_SOURCE_VARIANTS = {
    vehicle: f"{vehicle}_real_reference_v1" for vehicle in FOURCAR_VEHICLES
}
IR_NAMES = {
    "hellcat": "test_engine_16_eq_adjusted_16",
    "ferrari_458": "mild_exhaust_reverb",
    "lfa": "mild_exhaust_reverb",
    "gtr_r35": "test_engine_14_eq_adjusted_16",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _json_safe(value: object) -> object:
    if isinstance(value, np.ndarray):
        array = np.asarray(value, dtype=np.float64)
        return {
            "shape": list(array.shape),
            "min": float(np.min(array)) if array.size else 0.0,
            "max": float(np.max(array)) if array.size else 0.0,
            "rms": float(np.sqrt(np.mean(array * array))) if array.size else 0.0,
        }
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def load_real_reference_profile(vehicle: str):
    """Load one immutable profile and its five-source evidence summary."""
    if vehicle not in FOURCAR_VEHICLES:
        raise ValueError(f"unsupported four-car vehicle: {vehicle}")
    path = REAL_REFERENCE_PROFILE_PATHS[vehicle]
    profile = (
        load_stage_g_candidate(path)
        if vehicle == "ferrari_458"
        else load_stage_k_candidate(path)
    )
    payload = json.loads(FOURCAR_TARGET_PATH.read_text(encoding="utf-8"))
    record = payload["vehicles"][vehicle]
    if int(record["source_count"]) != 5 or len(record["sources"]) != 5:
        raise ValueError(f"four-car reference inventory must contain five sources: {vehicle}")
    changed = REAL_REFERENCE_CHANGED_PARAMETERS[vehicle]
    base_payload = json.loads(REAL_REFERENCE_BASE_PATHS[vehicle].read_text(encoding="utf-8"))
    base_value = float(base_payload["source"][changed]["value"])
    candidate_value = float(profile.payload["source"][changed]["value"])
    if np.isclose(base_value, candidate_value):
        raise ValueError(f"real-reference profile did not change {vehicle}/{changed}")
    metadata = {
        "source_ids": [str(source["id"]) for source in record["sources"]],
        "tuning_basis": "primary_three_median",
        "changed_source_parameter": changed,
        "base_value": base_value,
        "candidate_value": candidate_value,
        "target_metrics": record["target_metrics"],
        "evidence_level": record["quality_gate"],
    }
    return profile, metadata


def _curve(values: np.ndarray, count: int, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size < 2 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite samples")
    if array.size != count:
        array = np.interp(
            np.linspace(0.0, 1.0, count),
            np.linspace(0.0, 1.0, array.size),
            array,
        )
    return array


def _apply_profile_shelf(
    values: np.ndarray,
    *,
    vehicle: str,
    profile,
    base_value: float,
    candidate_value: float,
    sample_rate_hz: int,
) -> np.ndarray:
    """Apply one fixed source-profile ratio to the upper source band."""
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2 or not np.all(np.isfinite(x)):
        raise ValueError("pre-saturation source must be finite stereo")
    ratio = float(candidate_value) / float(base_value)
    if not np.isfinite(ratio) or ratio <= 0.0:
        raise ValueError("source profile ratio must be finite and positive")
    if np.isclose(ratio, 1.0):
        return x.copy()
    # A causal shelf keeps the adjustment before the existing tanh/int16
    # boundary while leaving the parent denominator and low band untouched.
    cutoff_hz = {"hellcat": 1_000.0, "ferrari_458": 1_000.0, "lfa": 1_000.0, "gtr_r35": 1_000.0}[vehicle]
    sos = signal.butter(2, cutoff_hz, btype="highpass", fs=sample_rate_hz, output="sos")
    high = np.column_stack(
        [signal.sosfilt(sos, x[:, channel]) for channel in range(x.shape[1])]
    )
    return x + (ratio - 1.0) * high


def _render_pre_saturation(
    vehicle: str,
    rpm: np.ndarray,
    throttle: np.ndarray,
    duration: float,
    shift_events: list | None,
    afterfire_events: list | None,
    bov_events: list | None,
    *,
    seed: int,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    """Capture the current AH engine at its pre-tanh, pre-int16 boundary."""
    engine = EngineAcoustics(vehicle_type=vehicle, sr=_SAMPLE_RATE_HZ)
    policy = SourcePolicy(
        vehicle,
        "r1_baseline",
        seed=seed,
        collect=True,
        output_policy=LEGACY_CLIP_V1,
        sample_rate=_SAMPLE_RATE_HZ,
    )
    saved_state = np.random.get_state()
    np.random.seed(seed)
    engine._source_policy = policy
    try:
        engine.render_track(
            rpm,
            throttle,
            duration,
            shift_events=shift_events,
            afterfire_events=afterfire_events,
            bov_events=bov_events,
        )
    finally:
        engine._source_policy = None
        np.random.set_state(saved_state)
    pre_saturation = policy.stems.get("pre_saturation")
    if pre_saturation is None:
        raise RuntimeError("AH engine did not expose pre-saturation stereo")
    return (
        np.asarray(pre_saturation, dtype=np.float64),
        {name: np.asarray(value, dtype=np.float64) for name, value in policy.stems.items()},
        dict(policy.receipt),
    )


class FourCarRealReferenceEngine:
    """Render one source-local four-car candidate through the AH final domain."""

    def __init__(
        self,
        vehicle_type: str,
        profile,
        *,
        sr: int = _SAMPLE_RATE_HZ,
        output_policy: str = LINKED_SOFT_CEILING_V1,
        parent_peaks: Mapping[int, float] | None = None,
        seed: int = 20260912,
    ) -> None:
        if vehicle_type not in FOURCAR_VEHICLES:
            raise ValueError(f"unsupported four-car vehicle: {vehicle_type}")
        if int(sr) != _SAMPLE_RATE_HZ:
            raise ValueError("four-car AH qualification requires 48 kHz")
        if output_policy not in (LEGACY_CLIP_V1, LINKED_SOFT_CEILING_V1):
            raise ValueError(f"unsupported output policy: {output_policy}")
        if profile.vehicle_id != vehicle_type:
            raise ValueError("profile vehicle_id does not match engine vehicle")
        self.vehicle_type = vehicle_type
        self.profile = profile
        self.sr = int(sr)
        self.output_policy = output_policy
        self.seed = int(seed)
        self.base = EngineAcoustics(vehicle_type=vehicle_type, sr=self.sr)
        self.ir_name = IR_NAMES[vehicle_type]
        self.ir_source_path = _resolve_ir_path(self.ir_name)
        self.base_source_payload = json.loads(
            REAL_REFERENCE_BASE_PATHS[vehicle_type].read_text(encoding="utf-8")
        )
        self.changed_source_parameter = REAL_REFERENCE_CHANGED_PARAMETERS[vehicle_type]
        self.base_source_value = float(
            self.base_source_payload["source"][self.changed_source_parameter]["value"]
        )
        self.candidate_source_value = float(
            self.profile.payload["source"][self.changed_source_parameter]["value"]
        )
        self.parent_peaks = dict(parent_peaks or {})
        self.scene_index = 0
        self.reports: list[dict[str, object]] = []

    def _guard(self, pre_guard: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
        metrics = ceiling_run_metrics(pre_guard, sample_rate=self.sr)
        if self.output_policy == LINKED_SOFT_CEILING_V1:
            output, receipt = linked_soft_ceiling(
                pre_guard, GuardConfig(), sample_rate=self.sr
            )
            return output, receipt
        output = np.clip(pre_guard, -0.94, 0.94)
        receipt = {
            "receipt_schema": "s12.stage_ah.output_guard_receipt.v1",
            "output_policy": LEGACY_CLIP_V1,
            "knee_linear": None,
            "ceiling_linear": 0.94,
            "stereo_link": "legacy_renderer_path",
            "parent_denominator_policy": "caller_supplied_fixed_parent_peak",
            "frame_count": int(len(pre_guard)),
            "legacy_ceiling_input_exceedance_samples": int(
                metrics["ceiling_input_exceedance_samples"]
            ),
            "legacy_transfer_pre_guard_peak": float(np.max(np.abs(pre_guard))),
            "pre_guard_exceedance_longest_run": metrics["exceedance_longest_run"],
            "pre_guard_peak": float(np.max(np.abs(pre_guard))),
            "soft_guard_active_frames": 0,
            "soft_guard_active_frame_ratio": 0.0,
            "soft_guard_min_gain": 1.0,
            "soft_guard_max_attenuation_db": 0.0,
            "soft_guard_delta_peak": 0.0,
            "soft_guard_delta_rms": 0.0,
            "post_guard_peak": float(np.max(np.abs(output))),
            "post_guard_ceiling_exceedance_samples": 0,
            "emergency_clip_count": 0,
            "emergency_clip_error": 0.0,
            "emergency_clip_error_rms": 0.0,
        }
        return output, receipt

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
        validate_events(afterfire_events, float(duration))
        count = int(round(self.sr * float(duration)))
        if count < 2:
            raise ValueError("track must contain at least two samples")
        rpm = _curve(rpm_curve, count, "rpm_curve")
        throttle = np.clip(_curve(throttle_curve, count, "throttle_curve"), 0.0, 1.0)
        time_s = np.arange(count, dtype=np.float64) / float(self.sr)
        trace = VehicleStateTrace(
            time_s=time_s,
            rpm=rpm,
            load=throttle,
            throttle=throttle,
            acceleration_mps2=np.gradient(rpm / 60.0, time_s),
        ).validate()

        pre_saturation, source_stems, source_receipt = _render_pre_saturation(
            self.vehicle_type,
            rpm,
            throttle,
            duration,
            shift_events,
            afterfire_events,
            bov_events,
            seed=self.seed,
        )
        adjusted = _apply_profile_shelf(
            pre_saturation,
            vehicle=self.vehicle_type,
            profile=self.profile,
            base_value=self.base_source_value,
            candidate_value=self.candidate_source_value,
            sample_rate_hz=self.sr,
        )
        candidate_raw_peak = float(np.max(np.abs(adjusted)))
        if not np.isfinite(candidate_raw_peak) or candidate_raw_peak <= 0.0:
            raise ValueError("candidate source is silent before normalization")
        denominator = float(self.parent_peaks.get(self.scene_index, candidate_raw_peak))
        if not np.isfinite(denominator) or denominator <= 0.0:
            raise ValueError("parent denominator must be finite and positive")
        normalized = adjusted / denominator
        pre_guard = np.tanh(normalized * 1.5) / np.tanh(1.5) * 0.94
        guarded, guard = self._guard(pre_guard)

        state = np.random.get_state()
        np.random.seed(self.seed)
        try:
            identity, identity_receipt = synthesize_vehicle_identity_layer_r1(
                self.vehicle_type,
                rpm,
                throttle,
                sr=self.sr,
                seed=self.seed,
                return_receipt=True,
            )
        finally:
            np.random.set_state(state)
        _, blend_scale = _state_envelope(self.vehicle_type, rpm, throttle)
        mix_curve = np.clip(
            float(VEHICLE_IDENTITY_PROFILES[self.vehicle_type].identity_mix)
            * blend_scale,
            0.0,
            0.25,
        )
        combined = (1.0 - mix_curve[:, None]) * guarded + mix_curve[:, None] * identity
        post_identity_mask = np.abs(combined) > 0.94 + 1e-12
        final_float = np.clip(combined, -0.94, 0.94)
        identity_error = combined - final_float
        pcm = (final_float * 32767.0).astype(np.int16)
        stem_reports = {
            name: spectrum_report(np.asarray(values, dtype=np.float64), self.sr)
            for name, values in source_stems.items()
        }
        stem_reports["pre_saturation_adjusted"] = spectrum_report(adjusted, self.sr)
        report = {
            "vehicle": self.vehicle_type,
            "source_variant": REAL_REFERENCE_SOURCE_VARIANTS[self.vehicle_type],
            "output_policy": self.output_policy,
            "source_adjustment_domain": "ah_r1_pre_saturation_before_output_guard",
            "candidate_render_path": "current_ah_engine_pre_saturation_overlay",
            "source_candidate_id": self.profile.candidate_id,
            "source_parameter_values": _json_safe(self.profile.payload.get("source", {})),
            "source_parameter_change": {
                "name": self.changed_source_parameter,
                "base_value": self.base_source_value,
                "candidate_value": self.candidate_source_value,
                "ratio": self.candidate_source_value / self.base_source_value,
            },
            "trace_sha256": _sha256_bytes(
                np.ascontiguousarray(np.column_stack([rpm, throttle]), dtype="<f8").tobytes()
            ),
            "parent_peak": denominator,
            "candidate_raw_peak": candidate_raw_peak,
            "normalization_denominator": denominator,
            "parent_denominator_policy": "fixed_parent_peak_from_ah_r1_control",
            "ir_name": self.ir_name,
            "ir_source_path": str(self.ir_source_path) if self.ir_source_path else "UNRESOLVED_IR_PATH",
            "ir_source_sha256": (
                _sha256_bytes(self.ir_source_path.read_bytes())
                if self.ir_source_path
                else _sha256_bytes(np.ascontiguousarray(self.base.ir, dtype="<f8").tobytes())
            ),
            "candidate_source_diagnostics": _json_safe({"source_policy_receipt": source_receipt}),
            "candidate_stems": stem_reports,
            "normalization": {
                **guard,
                "source_variant": REAL_REFERENCE_SOURCE_VARIANTS[self.vehicle_type],
                "output_policy": self.output_policy,
                "normalization_denominator": denominator,
                "parent_denominator_policy": "fixed_parent_peak_from_ah_r1_control",
                "pre_guard_pcm_sha256": _sha256_bytes(
                    np.ascontiguousarray((pre_guard * 32767.0).astype("<i2")).tobytes()
                ),
            },
            "identity_layer_preclip_peak": float(identity_receipt["identity_layer_preclip_peak"]),
            "identity_layer_clip_count": int(identity_receipt["identity_layer_clip_count"]),
            "identity_layer_clip_error": float(identity_receipt["identity_layer_clip_error"]),
            "post_identity_mix_peak": float(np.max(np.abs(combined))),
            "post_identity_clip_count": int(np.count_nonzero(post_identity_mask)),
            "post_identity_clip_error": float(np.max(np.abs(identity_error))),
            "post_identity_clip_error_rms": float(np.sqrt(np.mean(identity_error * identity_error))),
            "final_peak": float(np.max(np.abs(final_float))),
            "final_rms": float(np.sqrt(np.mean(final_float * final_float))),
            "final_pcm_sha256": _sha256_bytes(np.ascontiguousarray(pcm, dtype="<i2").tobytes()),
            "note": "R3 public recordings provide relative unsynchronised cues; source-only candidate, not OEM reproduction",
        }
        self.reports.append(report)
        self.scene_index += 1
        return pcm


__all__ = (
    "FOURCAR_TARGET_PATH",
    "FOURCAR_VEHICLES",
    "FourCarRealReferenceEngine",
    "REAL_REFERENCE_BASE_PATHS",
    "REAL_REFERENCE_CHANGED_PARAMETERS",
    "REAL_REFERENCE_PROFILE_PATHS",
    "REAL_REFERENCE_SOURCE_VARIANTS",
    "load_real_reference_profile",
)
