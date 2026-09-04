"""Stage AD reference-driven closed-loop calibration orchestration.

reference -> render -> compare -> update parameter center/domain -> render...

The controller is engineering-only. It never promotes a profile, never turns
R2/R3 material into R1, and never bypasses the human-audition gate.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..event_domain.config_schema import load_config
from ..stage_v.io import write_json
from ..stage_x.candidate_search import SOFT_IMPROVEMENT_TARGET, run_engineering_search
from ..stage_x.reference_caseset import load_case_segment_audio
from ..stage_x.search_parameters import apply_parameters, hellcat_search_parameters

CLOSED_LOOP_SCHEMA = "s12.stage_ad.closed_loop.v2"
ITERATION_SCHEMA = "s12.stage_ad.closed_loop_iteration.v2"


@dataclass(frozen=True)
class ClosedLoopPolicy:
    max_iterations: int = 3
    coarse_count: int = 48
    refine_count: int = 24
    seed: int = 20260904
    domain_shrink: float = 0.55
    minimum_delta_fraction: float = 0.20
    minimum_reference_distance_gain: float = 0.005
    plateau_patience: int = 1
    target_reference_distance: float | None = None
    generic_iteration_target: float = SOFT_IMPROVEMENT_TARGET

    def validate(self) -> None:
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.coarse_count <= 0:
            raise ValueError("coarse_count must be positive")
        if self.refine_count < 0:
            raise ValueError("refine_count must be non-negative")
        if not 0.0 < self.domain_shrink <= 1.0:
            raise ValueError("domain_shrink must be in (0, 1]")
        if not 0.0 < self.minimum_delta_fraction <= 1.0:
            raise ValueError("minimum_delta_fraction must be in (0, 1]")
        if self.minimum_reference_distance_gain < 0.0:
            raise ValueError("minimum_reference_distance_gain must be non-negative")
        if self.plateau_patience < 0:
            raise ValueError("plateau_patience must be non-negative")
        if self.target_reference_distance is not None and self.target_reference_distance < 0.0:
            raise ValueError("target_reference_distance must be non-negative")


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _evidence_rank(level: str) -> int:
    normalized = str(level or "").upper()
    if normalized == "R1":
        return 3
    if normalized.startswith("R2"):
        return 2
    if normalized.startswith("R3"):
        return 1
    return 0


def reference_audio_from_caseset(caseset: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Convert a governed ReferenceCaseSet into candidate-search inputs."""
    cases = [dict(case) for case in caseset.get("cases", []) if case.get("status") == "BOUND"]
    if not cases:
        raise ValueError("closed loop requires at least one BOUND reference case")

    selected: dict[str, dict[str, Any]] = {}
    for case in sorted(
        cases,
        key=lambda item: (
            str(item.get("scenario") or ""),
            -_evidence_rank(str(item.get("evidence_level") or "")),
            str(item.get("reference_id") or ""),
        ),
    ):
        scenario = str(case.get("scenario") or "")
        if scenario and scenario not in selected:
            selected[scenario] = case

    reference_audio: dict[str, Any] = {}
    for scenario, case in sorted(selected.items()):
        audio, sample_rate = load_case_segment_audio(case, target_sample_rate=48000)
        contamination = dict(case.get("speech_music_contamination") or {})
        reference_audio[scenario] = {
            "audio": np.asarray(audio, dtype=np.float64),
            "sample_rate": int(sample_rate),
            "metadata": {
                "reference_id": case.get("reference_id"),
                "evidence_level": case.get("evidence_level"),
                "rights_status": case.get("rights_status"),
                "speech_contaminated": bool(contamination.get("speech_contaminated")),
                "rejected": False,
                "segment_sha256": case.get("segment_sha256"),
            },
        }

    independent_count = int(
        caseset.get("selection_reference_count")
        or caseset.get("valid_reference_count")
        or len({str(case.get("recording_session_id") or case.get("source_id")) for case in cases})
    )
    return reference_audio, independent_count


def _select_parameters(allowed_parameter_names: list[str] | None) -> list[Any]:
    parameters = list(hellcat_search_parameters())
    if allowed_parameter_names is None:
        return parameters
    allowed = set(allowed_parameter_names)
    selected = [item for item in parameters if item.name in allowed]
    missing = sorted(allowed - {item.name for item in selected})
    if missing:
        raise ValueError(f"unknown closed-loop parameters: {missing}")
    if not selected:
        raise ValueError("closed loop has no selected parameters")
    return selected


def _shrink_parameters(
    parameters: list[Any],
    best_overrides: dict[str, float],
    original_deltas: dict[str, float],
    policy: ClosedLoopPolicy,
) -> list[Any]:
    narrowed: list[Any] = []
    for item in parameters:
        center = float(best_overrides.get(item.name, item.baseline))
        floor = float(original_deltas[item.name]) * float(policy.minimum_delta_fraction)
        delta = max(float(item.delta) * float(policy.domain_shrink), floor)
        narrowed.append(replace(item, baseline=center, delta=delta))
    return narrowed


def _audition_manifest(iteration_root: Path, best: dict[str, Any]) -> dict[str, Any]:
    scenes = []
    for scene, result in sorted((best.get("scene_results") or {}).items()):
        output_scene = str(result.get("aa_scene") or scene)
        scenes.append({
            "scene": scene,
            "output_scene": output_scene,
            "bound_scenario": result.get("bound_scenario") or scene,
            "monitor_wav": f"best_candidate/{output_scene}/monitor.wav",
            "post_ptr_wav": f"best_candidate/{output_scene}/post_ptr_raw.wav",
            "raw_source_wav": f"best_candidate/{output_scene}/raw_source.wav",
        })
    payload = {
        "schema": "s12.stage_ad.audition_manifest.v2",
        "iteration_root": str(iteration_root),
        "objective": best.get("objective"),
        "absolute_reference_distance": best.get("absolute_reference_distance"),
        "reference_objective": best.get("reference_objective"),
        "overrides": best.get("overrides"),
        "scenes": scenes,
        "qualification": "engineering audition only; human decision required",
    }
    write_json(iteration_root / "audition_manifest.json", payload)
    return payload


def run_closed_loop(
    output_root: str | Path,
    caseset: dict[str, Any],
    *,
    vehicle_id: str = "hellcat_v1",
    architecture: str = "P3",
    policy: ClosedLoopPolicy | None = None,
    allowed_parameter_names: list[str] | None = None,
    human_feedback: dict[str, Any] | None = None,
    base_config: dict[str, Any] | None = None,
    search_fn: Callable[..., dict[str, Any]] = run_engineering_search,
) -> dict[str, Any]:
    """Run an explicit multi-iteration reference-driven engineering loop.

    If the search provides ``absolute_reference_distance`` (AA-C3 Stage AD),
    convergence/plateau decisions use that fixed ruler. Generic Stage-X search
    remains supported, but changing-parent objectives are not compared across
    iterations for plateau detection.
    """
    policy = policy or ClosedLoopPolicy()
    policy.validate()
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    reference_audio, independent_count = reference_audio_from_caseset(caseset)
    parameters = _select_parameters(allowed_parameter_names)
    original_deltas = {item.name: float(item.delta) for item in parameters}
    current_config = copy.deepcopy(base_config if base_config is not None else load_config(vehicle_id))

    iterations: list[dict[str, Any]] = []
    previous_distance: float | None = None
    plateau_count = 0
    stop_reason = "MAX_ITERATIONS"
    final_best: dict[str, Any] | None = None

    for index in range(policy.max_iterations):
        iteration_root = output_root / f"iteration_{index:02d}"
        result = search_fn(
            iteration_root,
            reference_audio,
            architecture=architecture,
            coarse_count=policy.coarse_count,
            refine_count=policy.refine_count,
            seed=policy.seed + index * 1009,
            base_config=current_config,
            parameters_override=parameters,
            human_feedback=human_feedback,
            independent_reference_count=independent_count,
        )
        best = result.get("best")
        if not best:
            stop_reason = "NO_ELIGIBLE_CANDIDATE"
            break
        if not bool(best.get("parameter_consumed")):
            stop_reason = "BEST_PARAMETER_NOT_CONSUMED"
            break
        objective = best.get("objective")
        if objective is None or not np.isfinite(float(objective)):
            stop_reason = "OBJECTIVE_NOT_AVAILABLE"
            break

        objective = float(objective)
        distance_value = best.get("absolute_reference_distance")
        absolute_distance = (
            float(distance_value)
            if distance_value is not None and np.isfinite(float(distance_value))
            else None
        )
        distance_gain = (
            previous_distance - absolute_distance
            if previous_distance is not None and absolute_distance is not None
            else None
        )
        best_overrides = {
            name: float(value) for name, value in dict(best.get("overrides") or {}).items()
        }
        audition = _audition_manifest(iteration_root, best)
        iteration_receipt = {
            "schema": ITERATION_SCHEMA,
            "iteration": index,
            "objective": objective,
            "absolute_reference_distance": absolute_distance,
            "reference_distance_gain_from_previous": distance_gain,
            "reference_objective": best.get("reference_objective"),
            "best_overrides": best_overrides,
            "parameter_count": len(parameters),
            "parameter_centers": {item.name: float(item.baseline) for item in parameters},
            "parameter_deltas": {item.name: float(item.delta) for item in parameters},
            "input_config_sha256": _canonical_sha(current_config),
            "audition_manifest": str(
                (iteration_root / "audition_manifest.json").relative_to(output_root)
            ),
            "audition_scene_count": len(audition["scenes"]),
        }
        iterations.append(iteration_receipt)
        write_json(iteration_root / "closed_loop_iteration.json", iteration_receipt)
        final_best = best
        current_config = apply_parameters(current_config, best_overrides, parameters)

        if (
            absolute_distance is not None
            and policy.target_reference_distance is not None
            and absolute_distance <= float(policy.target_reference_distance)
        ):
            stop_reason = "TARGET_REFERENCE_DISTANCE_REACHED"
            break

        if distance_gain is not None:
            if distance_gain < float(policy.minimum_reference_distance_gain):
                plateau_count += 1
            else:
                plateau_count = 0
            if plateau_count > int(policy.plateau_patience):
                stop_reason = "REFERENCE_DISTANCE_PLATEAU"
                break
        elif absolute_distance is None and objective >= float(policy.generic_iteration_target):
            stop_reason = "GENERIC_ITERATION_TARGET_REACHED"
            break

        parameters = _shrink_parameters(parameters, best_overrides, original_deltas, policy)
        if absolute_distance is not None:
            previous_distance = absolute_distance

    summary = {
        "schema": CLOSED_LOOP_SCHEMA,
        "vehicle_id": vehicle_id,
        "architecture": architecture,
        "policy": asdict(policy),
        "reference_evidence_level": caseset.get("reference_evidence_level"),
        "independent_reference_count": independent_count,
        "bound_scenarios": sorted(reference_audio),
        "iteration_count": len(iterations),
        "iterations": iterations,
        "stop_reason": stop_reason,
        "final_objective": final_best.get("objective") if final_best else None,
        "final_absolute_reference_distance": (
            final_best.get("absolute_reference_distance") if final_best else None
        ),
        "final_reference_objective": final_best.get("reference_objective") if final_best else None,
        "final_overrides": final_best.get("overrides") if final_best else None,
        "final_config_sha256": _canonical_sha(current_config),
        "automatic_profile_promotion": False,
        "human_audition_required": True,
        "r1_promotion_forbidden": True,
        "scope": (
            "engineering closed-loop calibration infrastructure; no Profile Freeze, "
            "OEM likeness claim, or blind-audition bypass"
        ),
    }
    write_json(output_root / "closed_loop_summary.json", summary)
    write_json(output_root / "final_config.json", current_config)
    return summary


__all__ = [
    "CLOSED_LOOP_SCHEMA",
    "ITERATION_SCHEMA",
    "ClosedLoopPolicy",
    "reference_audio_from_caseset",
    "run_closed_loop",
]
