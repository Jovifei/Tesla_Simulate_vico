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
from typing import Any

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
from .engine import input_sha, spectrum_report
from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    GuardConfig,
    ceiling_run_metrics,
    linked_soft_ceiling,
)
from .source_policy import SourcePolicy, validate_events


_SAMPLE_RATE_HZ = 48_000
DEFAULT_SEED = 20260908
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
    vehicle: f"{vehicle}_real_reference_stem_scoped_v2" for vehicle in FOURCAR_VEHICLES
}
IR_NAMES = {
    "hellcat": "test_engine_16_eq_adjusted_16",
    "ferrari_458": "mild_exhaust_reverb",
    "lfa": "mild_exhaust_reverb",
    "gtr_r35": "test_engine_14_eq_adjusted_16",
}
SOURCE_SHELF_CUTOFF_HZ = 1_000.0

SOURCE_RECIPE = {
    "hellcat": {
        "parameter": "blower_gain_scale",
        "stem": "supercharger",
        "scope": "named_supercharger_stem_only",
        "unused_fields": (),
    },
    "ferrari_458": {
        "parameter": "high_rpm_growth_scale",
        "stem": "combustion_high_rpm",
        "scope": "combustion_order_envelope_above_65pct_redline",
        "unused_fields": (),
    },
    "lfa": {
        "parameter": "high_rpm_growth_scale",
        "stem": "combustion_high_rpm",
        "scope": "combustion_order_envelope_above_65pct_redline",
        "unused_fields": ("intake_resonance_scale",),
    },
    "gtr_r35": {
        "parameter": "turbo_whistle_mix",
        "stem": "turbo",
        "scope": "named_turbo_stem_only",
        "unused_fields": (),
    },
}


def source_adjustment_recipe(vehicle: str) -> dict[str, Any]:
    """Return the fixed, explicit source scope for one four-car candidate."""
    try:
        recipe = SOURCE_RECIPE[vehicle]
    except KeyError as exc:
        raise ValueError(f"unsupported four-car vehicle: {vehicle}") from exc
    return {**recipe, "vehicle": vehicle, "unused_fields": list(recipe["unused_fields"])}


def scene_trace_key(scene_id: str, trace_sha256: str) -> str:
    scene = str(scene_id).strip()
    trace = str(trace_sha256).strip().lower()
    if not scene or not trace:
        raise ValueError("scene_id and trace_sha256 are required")
    return f"{scene}|{trace}"


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
    full_field_diff = {
        name: {
            "base_value": float(base_payload["source"][name]["value"]),
            "candidate_value": float(profile.payload["source"][name]["value"]),
        }
        for name in sorted(set(base_payload.get("source", {})) & set(profile.payload.get("source", {})))
        if not np.isclose(
            float(base_payload["source"][name]["value"]),
            float(profile.payload["source"][name]["value"]),
        )
    }
    recipe = source_adjustment_recipe(vehicle)
    metadata = {
        "source_ids": [str(source["id"]) for source in record["sources"]],
        "tuning_basis": "primary_three_median",
        "changed_source_parameter": changed,
        "base_value": base_value,
        "candidate_value": candidate_value,
        "full_field_diff": full_field_diff,
        "active_source_parameter": recipe["parameter"],
        "active_source_stem": recipe["stem"],
        "unused_source_fields": list(recipe["unused_fields"]),
        "target_metrics": record["target_metrics"],
        "evidence_level": record["quality_gate"],
    }
    return profile, metadata


class RealReferenceSourcePolicy(SourcePolicy):
    """Apply the fixed profile ratio only at the named EngineAcoustics stem."""

    def __init__(self, vehicle: str, *, seed: int, ratio: float, collect: bool,
                 sample_rate: int, recipe: Mapping[str, Any]):
        super().__init__(
            vehicle,
            "r1_baseline",
            seed=seed,
            collect=collect,
            output_policy=LEGACY_CLIP_V1,
            sample_rate=sample_rate,
        )
        if not np.isfinite(ratio) or ratio <= 0.0:
            raise ValueError("source adjustment ratio must be finite and positive")
        self.source_ratio = float(ratio)
        self.recipe = dict(recipe)

    def combustion_input(self, engine, left, right, rpm, throttle):
        stem = self.recipe["stem"]
        if stem != "combustion_high_rpm":
            return super().combustion_input(engine, left, right, rpm, throttle)
        rpm_array = np.asarray(rpm, dtype=np.float64)
        envelope = np.clip(
            (rpm_array - 0.65 * float(engine.redline)) /
            (0.35 * float(engine.redline)),
            0.0,
            1.0,
        )
        gain = 1.0 + (self.source_ratio - 1.0) * envelope
        if np.isclose(self.source_ratio, 1.0):
            return left, right
        self.observe("combustion_high_rpm_before", np.column_stack([left, right]))
        adjusted_left = np.asarray(left, dtype=np.float64) * gain
        adjusted_right = np.asarray(right, dtype=np.float64) * gain
        self.observe("combustion_high_rpm_after", np.column_stack([adjusted_left, adjusted_right]))
        return adjusted_left, adjusted_right

    def source_family(self, name, stereo, rpm, throttle):
        if name != self.recipe["stem"]:
            return super().source_family(name, stereo, rpm, throttle)
        values = np.asarray(stereo, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise ValueError(f"non-finite {name} source stem")
        self.observe(f"{name}_before", values)
        if np.isclose(self.source_ratio, 1.0):
            return values
        adjusted = values * self.source_ratio
        self.observe(f"{name}_after", adjusted)
        return adjusted


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
    """Legacy mixed-signal diagnostic retained only for historical packages."""
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
    sos = signal.butter(2, SOURCE_SHELF_CUTOFF_HZ, btype="highpass", fs=sample_rate_hz, output="sos")
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
    numerical_fixes: tuple[str, ...] = (),
    policy: SourcePolicy | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    """Capture the current AH engine at its pre-tanh, pre-int16 boundary."""
    engine = EngineAcoustics(
        vehicle_type=vehicle,
        sr=_SAMPLE_RATE_HZ,
        numerical_fixes=tuple(numerical_fixes),
    )
    policy = policy or SourcePolicy(
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
        parent_peaks: Mapping[str, float] | None = None,
        seed: int = DEFAULT_SEED,
        numerical_fixes: tuple[str, ...] = (),
        source_adjustment_ratio: float | None = None,
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
        self.numerical_fixes = tuple(numerical_fixes)
        self.base = EngineAcoustics(
            vehicle_type=vehicle_type,
            sr=self.sr,
            numerical_fixes=self.numerical_fixes,
        )
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
        self.source_recipe = source_adjustment_recipe(vehicle_type)
        ratio = self.candidate_source_value / self.base_source_value
        self.source_adjustment_ratio = float(
            ratio if source_adjustment_ratio is None else source_adjustment_ratio
        )
        if not np.isfinite(self.source_adjustment_ratio) or self.source_adjustment_ratio <= 0.0:
            raise ValueError("source adjustment ratio must be finite and positive")
        self.parent_peaks = dict(parent_peaks or {})
        self.scene_id: str | None = None
        self.trace_sha256: str | None = None
        self.reports: list[dict[str, object]] = []
        self.last_report: dict[str, object] = {}

    def set_scene_context(self, scene_id: str, trace_sha256: str) -> None:
        self.scene_id = str(scene_id)
        self.trace_sha256 = str(trace_sha256).lower()

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

        trace_sha256 = input_sha(
            rpm,
            throttle,
            duration,
            [shift_events, afterfire_events, bov_events],
        )
        if self.trace_sha256 is not None and self.trace_sha256 != trace_sha256:
            raise ValueError("scene trace context does not match rendered curves")
        scene_id = self.scene_id or "UNBOUND_SCENE"
        parent_key = scene_trace_key(scene_id, trace_sha256)
        if parent_key not in self.parent_peaks:
            raise ValueError(f"parent denominator missing for scene trace {parent_key}")
        pre_saturation, source_stems, source_receipt = _render_pre_saturation(
            self.vehicle_type,
            rpm,
            throttle,
            duration,
            shift_events,
            afterfire_events,
            bov_events,
            seed=self.seed,
            numerical_fixes=self.numerical_fixes,
            policy=RealReferenceSourcePolicy(
                self.vehicle_type,
                seed=self.seed,
                ratio=self.source_adjustment_ratio,
                collect=True,
                sample_rate=self.sr,
                recipe=self.source_recipe,
            ),
        )
        adjusted = pre_saturation
        candidate_raw_peak = float(np.max(np.abs(adjusted)))
        if not np.isfinite(candidate_raw_peak) or candidate_raw_peak <= 0.0:
            raise ValueError("candidate source is silent before normalization")
        denominator = float(self.parent_peaks[parent_key])
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
        # Match the accepted C0 precision boundary: guard -> int16 -> identity.
        guarded_pcm = (guarded * 32767.0).astype(np.int16)
        guarded_quantized = guarded_pcm.astype(np.float64) / 32767.0
        combined = (1.0 - mix_curve[:, None]) * guarded_quantized + mix_curve[:, None] * identity
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
            "source_adjustment_domain": "named_source_stem_before_output_guard",
            "candidate_render_path": "current_ah_engine_named_source_recipe",
            "source_candidate_id": self.profile.candidate_id,
            "source_parameter_values": _json_safe(self.profile.payload.get("source", {})),
            "source_parameter_change": {
                "name": self.changed_source_parameter,
                "base_value": self.base_source_value,
                "candidate_value": self.candidate_source_value,
                "ratio": self.candidate_source_value / self.base_source_value,
                "applied_ratio": self.source_adjustment_ratio,
                "active_stem": self.source_recipe["stem"],
                "scope": self.source_recipe["scope"],
                "unused_fields": list(self.source_recipe["unused_fields"]),
            },
            "source_adjustment": {
                "method": "named_engine_source_stem_gain",
                "stem": self.source_recipe["stem"],
                "gain_ratio": self.source_adjustment_ratio,
                "low_band_policy": "not_global_filter; source_scope_controls_effect",
            },
            "scene_id": scene_id,
            "trace_sha256": trace_sha256,
            "sample_rate_hz": self.sr,
            "sample_count": count,
            "seed": self.seed,
            "flags": list(self.numerical_fixes),
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
            "ir_effective_sha256": _sha256_bytes(
                np.ascontiguousarray(self.base.ir, dtype="<f8").tobytes()
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
                "pre_identity_pcm_sha256": _sha256_bytes(
                    np.ascontiguousarray(guarded_pcm, dtype="<i2").tobytes()
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
            "candidate_pcm_sha256": _sha256_bytes(np.ascontiguousarray(pcm, dtype="<i2").tobytes()),
            "note": "R3 public recordings provide relative unsynchronised cues; source-only candidate, not OEM reproduction",
        }
        self.reports.append(report)
        self.last_report = report
        return pcm


__all__ = (
    "DEFAULT_SEED",
    "FOURCAR_TARGET_PATH",
    "FOURCAR_VEHICLES",
    "FourCarRealReferenceEngine",
    "RealReferenceSourcePolicy",
    "REAL_REFERENCE_BASE_PATHS",
    "REAL_REFERENCE_CHANGED_PARAMETERS",
    "REAL_REFERENCE_PROFILE_PATHS",
    "REAL_REFERENCE_SOURCE_VARIANTS",
    "load_real_reference_profile",
    "scene_trace_key",
    "source_adjustment_recipe",
)
