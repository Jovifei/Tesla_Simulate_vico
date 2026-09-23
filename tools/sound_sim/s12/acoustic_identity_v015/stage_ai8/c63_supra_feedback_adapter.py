"""Bounded measured-search adapter for the existing C63 and Supra sources.

This module only exposes one source-local parameter per vehicle.  It reuses
the Stage-AH optimizer and numeric qualification without changing either.
"""
from __future__ import annotations

import hashlib
import math
import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal
from scipy.io import wavfile

from ..stage_ah.c63_pipeline import C63Engine, C63_IR_NAME, _resolve_ir_path
from ..stage_ah.feedback_evidence import SCENES
from ..stage_ah.qualification import numeric_ok
from ..stage_ah.reference_feedback import (
    ReferenceCase,
    Rendered,
    SearchConfig,
    _validate_cases,
    optimize_reference_feedback,
    validate_parameters,
)
from ..stage_ah.supra_pipeline import SupraEngine
from ..stage_k.candidate_profiles import load_stage_k_candidate
from ..stage_ah.c63_pipeline import C63_CANDIDATE_PATH
from ..sources import toyota_i6_turbo_source_v2 as supra_source


C63_PARAMETER = "bark_upper_partial_mix"
SUPRA_PARAMETER = "edge_scale"
SUPRA_EDGE_BOUNDS = (0.9, 1.8)
SUPRA_SOURCE_PATH = Path(supra_source.__file__).resolve()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound_ir(path: Path) -> np.ndarray:
    sample_rate, raw = wavfile.read(path)
    data = raw[:, 0] if raw.ndim > 1 else raw
    if data.dtype == np.uint8:
        data = (data.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(data.dtype, np.signedinteger):
        data = data.astype(np.float64) / float(-np.iinfo(data.dtype).min)
    else:
        data = data.astype(np.float64)
    if data.size == 0 or not np.all(np.isfinite(data)) or not np.any(data):
        raise ValueError("bound IR must contain finite nonzero samples")
    if int(sample_rate) != 48_000:
        data = signal.resample(data, int(len(data) * 48_000 / int(sample_rate)))
    return np.asarray(data[: min(len(data), 12_000)], dtype=np.float64)


def feedback_parameter_contract(
    vehicle: str,
) -> tuple[dict[str, float], dict[str, tuple[float, float]]]:
    """Return the one-parameter baseline and bounded experiment box."""
    if vehicle == "c63_w204":
        profile = load_stage_k_candidate(C63_CANDIDATE_PATH)
        entry = profile.payload["source"][C63_PARAMETER]
        baseline = float(entry["value"])
        bounds = tuple(float(value) for value in entry["range"])
        return {C63_PARAMETER: baseline}, {C63_PARAMETER: bounds}
    if vehicle == "supra_jza80":
        return {SUPRA_PARAMETER: float(supra_source.SUPRA_V2_EDGE_SCALE)}, {
            SUPRA_PARAMETER: SUPRA_EDGE_BOUNDS
        }
    raise ValueError(f"unsupported AI-8 vehicle: {vehicle}")


def _validate_contract(
    baseline: Mapping[str, float], bounds: Mapping[str, Sequence[float]]
) -> None:
    if len(baseline) != 1 or set(baseline) != set(bounds):
        raise ValueError("AI-8 requires exactly one whitelisted source parameter")
    validate_parameters(baseline, bounds)


class C63SupraFeedbackRenderer:
    """Render bounded trials with frozen traces, parent peaks, IR and guards."""

    def __init__(
        self,
        vehicle: str,
        contexts: Mapping[str, Mapping[str, Any]],
        parent_peaks: Mapping[str, float],
        *,
        ir: np.ndarray | None = None,
        ir_path: str | Path | None = None,
    ) -> None:
        if ir is not None and ir_path is not None:
            raise ValueError("provide either injected IR or an actual IR path, not both")
        self.vehicle = str(vehicle)
        self.contexts = copy.deepcopy({str(key): dict(value) for key, value in contexts.items()})
        raw_parent_peaks = dict(parent_peaks)
        if not raw_parent_peaks or any(
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.integer, np.floating))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
            for value in raw_parent_peaks.values()
        ):
            raise ValueError("parent peaks must be finite and positive")
        self.parent_peaks = {str(key): float(value) for key, value in raw_parent_peaks.items()}
        self._c63_candidate_path: Path | None = None
        self._c63_candidate_sha256: str | None = None
        self._c63_candidate = None
        self._supra_source_path: Path | None = None
        self._supra_source_sha256: str | None = None
        if self.vehicle == "c63_w204":
            self._c63_candidate_path = Path(C63_CANDIDATE_PATH).resolve()
            self._c63_candidate_sha256 = _sha256(self._c63_candidate_path)
            self._c63_candidate = load_stage_k_candidate(self._c63_candidate_path)
            entry = self._c63_candidate.payload["source"][C63_PARAMETER]
            self.baseline = {C63_PARAMETER: float(entry["value"])}
            self.bounds = {
                C63_PARAMETER: tuple(float(value) for value in entry["range"])
            }
        elif self.vehicle == "supra_jza80":
            self.baseline, self.bounds = feedback_parameter_contract(self.vehicle)
            self._supra_source_path = Path(SUPRA_SOURCE_PATH).resolve()
            if not self._supra_source_path.is_file():
                raise FileNotFoundError(self._supra_source_path)
            self._supra_source_sha256 = _sha256(self._supra_source_path)
        else:
            self.baseline, self.bounds = feedback_parameter_contract(self.vehicle)
        _validate_contract(self.baseline, self.bounds)
        if not self.contexts:
            raise ValueError("at least one frozen scene context is required")
        self._trace_sha256 = {
            scene: str(context.get("trace_sha256", ""))
            for scene, context in self.contexts.items()
        }
        if any(len(value) != 64 for value in self._trace_sha256.values()):
            raise ValueError("each frozen scene requires a trace SHA-256")
        self.ir_path = Path(ir_path).resolve() if ir_path is not None else None
        if self.ir_path is not None and not self.ir_path.is_file():
            raise FileNotFoundError(self.ir_path)
        self.ir_path_sha256 = _sha256(self.ir_path) if self.ir_path is not None else None
        if self.ir_path is not None:
            ir = _load_bound_ir(self.ir_path)
        self._default_ir_path = None
        if ir is None and self.ir_path is None:
            self._default_ir_path = _resolve_ir_path(C63_IR_NAME)
            if self._default_ir_path is None:
                raise FileNotFoundError("required default IR path is unavailable")
        self._bound_ir_path = self.ir_path or self._default_ir_path
        self._bound_ir_sha256 = (
            _sha256(self._bound_ir_path) if self._bound_ir_path is not None else None
        )
        self.ir = None if ir is None else np.asarray(ir, dtype=np.float64).reshape(-1).copy()
        if self.ir is not None and (
            self.ir.size == 0 or not np.all(np.isfinite(self.ir)) or not np.any(self.ir)
        ):
            raise ValueError("IR must be finite and nonzero")
        self.last_records: dict[str, Mapping[str, Any]] = {}

    def _check_source_bindings(self) -> None:
        if (
            self._c63_candidate_path is not None
            and _sha256(self._c63_candidate_path) != self._c63_candidate_sha256
        ):
            raise ValueError("C63 candidate profile file changed during bounded search")
        if (self._supra_source_path is not None
                and (not self._supra_source_path.is_file()
                     or _sha256(self._supra_source_path) != self._supra_source_sha256)):
            raise ValueError("Supra source file changed during bounded search")
        if (
            self._bound_ir_path is not None
            and _sha256(self._bound_ir_path) != self._bound_ir_sha256
        ):
            raise ValueError("IR path changed during bounded search")

    def _engine(self, parameters: Mapping[str, float], scene: str):
        common = {
            "output_policy": "linked_soft_ceiling_v1",
            "parent_peaks": self.parent_peaks,
            "ir": self.ir,
            "scene_ids": (scene,),
            "seed": 20260908,
        }
        if self.vehicle == "c63_w204":
            profile = self._c63_candidate.with_parameter(
                "source", C63_PARAMETER, parameters[C63_PARAMETER]
            )
            return C63Engine(candidate=profile, **common)
        return SupraEngine(edge_scale=parameters[SUPRA_PARAMETER], **common)

    def _default_engine(self, scene: str):
        common = {
            "output_policy": "linked_soft_ceiling_v1",
            "parent_peaks": self.parent_peaks,
            "ir": self.ir,
            "scene_ids": (scene,),
            "seed": 20260908,
        }
        return (
            C63Engine(candidate=self._c63_candidate, **common)
            if self.vehicle == "c63_w204"
            else SupraEngine(**common)
        )

    def __call__(self, parameters: Mapping[str, float], scene: str) -> Rendered:
        params = validate_parameters(parameters, self.bounds)
        if scene not in self.contexts:
            raise ValueError(f"unknown frozen scene: {scene}")
        self._check_source_bindings()
        context = self.contexts[scene]
        engine = self._engine(params, scene)
        if self._default_ir_path is not None:
            actual = engine.ir_source_path.resolve() if engine.ir_source_path is not None else None
            if actual != self._default_ir_path:
                raise ValueError("runtime default IR differs from the bound IR path")
        audio = engine.render_track(
            context["rpm"],
            context["throttle"],
            context["duration"],
            shift_events=context.get("shift_events"),
            afterfire_events=context.get("afterfire_events"),
            bov_events=context.get("bov_events"),
        )
        record = engine.reports[-1]
        if record["trace_sha256"] != self._trace_sha256[scene]:
            raise ValueError("trial trace differs from frozen baseline")
        key = record["parent_peak_key"]
        if key not in self.parent_peaks:
            raise ValueError("trial denominator is not bound to the frozen scene trace")
        if record["normalization_denominator"] != self.parent_peaks[key]:
            raise ValueError("trial changed the frozen parent denominator")
        self._check_source_bindings()
        self.last_records[scene] = record
        return Rendered(audio, numeric_ok(record), record)


def fit_reference_cases(
    vehicle: str,
    contexts: Mapping[str, Mapping[str, Any]],
    parent_peaks: Mapping[str, float],
    cases: Sequence[ReferenceCase],
    *,
    ir: np.ndarray | None = None,
    ir_path: str | Path | None = None,
    config: SearchConfig = SearchConfig(),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate off-switch equivalence, then run the existing bounded optimizer."""
    frozen_cases = tuple(cases)
    case_scenes = sorted({case.scene for case in frozen_cases})
    missing = [scene for scene in case_scenes if scene not in contexts]
    if missing:
        raise ValueError(f"reference case has no frozen scene context: {missing}")
    _validate_cases(frozen_cases)
    renderer = C63SupraFeedbackRenderer(
        vehicle, contexts, parent_peaks, ir=ir, ir_path=ir_path
    )
    renderer._check_source_bindings()
    provided_scenes = sorted(renderer.contexts)
    denominator_keys: dict[str, str] = {}
    for scene in provided_scenes:
        feedback_off = renderer(renderer.baseline, scene)
        context = renderer.contexts[scene]
        default_engine = renderer._default_engine(scene)
        default_audio = default_engine.render_track(
            context["rpm"],
            context["throttle"],
            context["duration"],
            shift_events=context.get("shift_events"),
            afterfire_events=context.get("afterfire_events"),
            bov_events=context.get("bov_events"),
        )
        default_record = default_engine.reports[-1]
        if not feedback_off.numeric_ok or not numeric_ok(default_record):
            raise ValueError(f"baseline numeric gate failed: {scene}")
        if not np.array_equal(feedback_off.audio, default_audio):
            raise ValueError(f"feedback-off PCM differs from default source: {scene}")
        if default_record["trace_sha256"] != renderer._trace_sha256[scene]:
            raise ValueError(f"default source trace differs from frozen context: {scene}")
        denominator_keys[scene] = default_record["parent_peak_key"]
    result = optimize_reference_feedback(
        dict(renderer.baseline),
        dict(renderer.bounds),
        frozen_cases,
        renderer,
        config=config,
    )
    renderer._check_source_bindings()
    optimizer_status = result["status"]
    result.update(
        optimizer_status=optimizer_status,
        reference_provenance="UNVERIFIED_IN_MEMORY",
        production_qualification=False,
    )
    selected_diagnostics: dict[str, Mapping[str, Any]] = {}
    failed_scenes: list[str] = []
    for scene in provided_scenes:
        selected = renderer(result["selected_parameters"], scene)
        selected_diagnostics[scene] = copy.deepcopy(selected.diagnostics)
        if selected.numeric_ok is not True:
            failed_scenes.append(scene)
    if failed_scenes:
        rejected_parameters = dict(result["selected_parameters"])
        rejected_status = result["status"]
        for scene in provided_scenes:
            rollback = renderer(renderer.baseline, scene)
            if rollback.numeric_ok is not True:
                raise ValueError(f"baseline rollback failed numeric verification: {scene}")
        result.update(
            status="ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK",
            selected_parameters=dict(renderer.baseline),
            parameter_delta={name: 0.0 for name in renderer.baseline},
            selected_train_loss=result["baseline_train_loss"],
            rejected_parameters=rejected_parameters,
            rejected_optimizer_status=rejected_status,
            rejected_scenes=failed_scenes,
            rejected_diagnostics=selected_diagnostics,
        )
    else:
        result["status"] = "ADAPTER_DIAGNOSTIC_ONLY"
    renderer._check_source_bindings()
    tested_scope = {
        "vehicle": vehicle,
        "parameter_count": 1,
        "parameters": dict(renderer.baseline),
        "bounds": {name: list(bounds) for name, bounds in renderer.bounds.items()},
        "scenes": provided_scenes,
        "provided_scenes": provided_scenes,
        "reference_scenes": case_scenes,
        "canonical_ten_scene_coverage": (
            len(provided_scenes) == len(SCENES) and set(provided_scenes) == set(SCENES)
        ),
        "trace_sha256": {
            scene: renderer._trace_sha256[scene] for scene in provided_scenes
        },
        "parent_peak_keys": denominator_keys,
        "parameter_source_binding": {
            "kind": "stage_k_candidate_profile" if vehicle == "c63_w204" else "supra_source_module",
            "sha256": renderer._c63_candidate_sha256 or renderer._supra_source_sha256,
        },
        "feedback_off_pcm_equal": True,
        "numeric_gate": "stage_ah.qualification.numeric_ok",
        "file_output": False,
    }
    return result, tested_scope


__all__ = (
    "C63_PARAMETER",
    "C63SupraFeedbackRenderer",
    "SUPRA_EDGE_BOUNDS",
    "SUPRA_PARAMETER",
    "feedback_parameter_contract",
    "fit_reference_cases",
)
