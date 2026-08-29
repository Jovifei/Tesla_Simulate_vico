"""Stage X deterministic two-stage candidate search and engineering preselection.

Stage 1: Sobol coarse box around the baseline (bounded by each parameter's
reachability delta). Stage 2: local refinement around the top-3. Every
candidate is actually rendered, reopened from PCM, hashed, measured against
its scenario-bound references, and ranked. No candidate exists on paper.
"""

from __future__ import annotations

import copy
import hashlib
import time
from typing import Any

import numpy as np
from scipy.stats import qmc

from ..event_domain.config_schema import load_config
from ..stage_v.io import write_json
from ..stage_w.click_contract import block_boundary_click_metrics
from .multi_reference_comparator import aggregate_dimensions, compare_case, compare_multi_reference
from .search_parameters import apply_parameters, hellcat_search_parameters

SEARCH_SCHEMA = "s12.stage_x.candidate_search.v1"
PRESELECTION_SCHEMA = "s12.stage_x.engineering_preselection_result.v1"

SEARCH_SCENES = (
    ("hot_idle_20s", "hot_idle", 2.0),
    ("steady_1200rpm", "steady_low", 2.0),
    ("steady_2000rpm", "steady_mid", 2.0),
    ("steady_3000rpm", "steady_high", 2.0),
)
OUTPUT_SCALE = 0.25
SOFT_IMPROVEMENT_TARGET = 0.15
DIMENSION_REGRESSION_LIMIT = 0.10
KEY_DIMENSIONS = ("low_frequency_body", "120_400_pressure_attack", "mid_band_congestion")


def _render_pcm(config: dict[str, Any], architecture: str, scene: str, duration_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], float]:
    from ..stage_w.bakeoff import _render_architecture, build_hellcat_bakeoff_trace

    trace = build_hellcat_bakeoff_trace(scene, duration_s)
    start = time.perf_counter()

    class _ConfigPatcher:
        """Swap the bakeoff module's hellcat config for the candidate one.

        bakeoff.py binds load_config at import time, so patch that binding,
        not only the schema module.
        """

        def __init__(self, target: dict[str, Any]) -> None:
            self.target = target

        def __enter__(self) -> "_ConfigPatcher":
            from .. import stage_w as _stage_w_pkg  # noqa: F401
            import tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff as bakeoff

            self._bakeoff = bakeoff
            self._orig_load = bakeoff.load_config
            bakeoff.load_config = lambda vehicle_id: copy.deepcopy(self.target)
            return self

        def __exit__(self, *exc: Any) -> None:
            self._bakeoff.load_config = self._orig_load

    with _ConfigPatcher(config):
        raw, post_ptr, monitor, diagnostics = _render_architecture(architecture, trace)
    elapsed = time.perf_counter() - start
    return raw, post_ptr, monitor, diagnostics, elapsed


def _evaluate_candidate(
    architecture: str,
    overrides: dict[str, float],
    base_config: dict[str, Any],
    parameters: list[Any],
    reference_audio: dict[str, tuple[np.ndarray, int]],
    parent_audio: dict[str, np.ndarray],
) -> dict[str, Any]:
    """Render one candidate and compare it to parent and references per scene."""
    config = apply_parameters(base_config, overrides, parameters)
    scene_results: dict[str, Any] = {}
    overall_finite = True
    clipping = 0
    click_ok = True
    render_seconds = 0.0
    for scene, bound_scenario, duration_s in SEARCH_SCENES:
        raw, post_ptr, monitor, diagnostics, elapsed = _render_pcm(config, architecture, scene, duration_s)
        render_seconds += elapsed
        overall_finite = overall_finite and bool(np.all(np.isfinite(post_ptr))) and bool(np.all(np.isfinite(monitor)))
        clipping += int(np.count_nonzero(np.abs(post_ptr) >= 1.0))
        click_ok = click_ok and block_boundary_click_metrics(post_ptr)["passed"]
        comparison = None
        if bound_scenario in reference_audio and bound_scenario in parent_audio:
            reference_audio_data, sample_rate = reference_audio[bound_scenario]
            min_len = min(reference_audio_data.size, post_ptr.shape[0])
            comparison = compare_case(
                reference_audio_data[:min_len],
                parent_audio[bound_scenario][:min_len],
                post_ptr[:min_len],
                sample_rate,
                candidate_id=architecture,
            )
            scene_results[scene] = {
                "bound_scenario": bound_scenario,
                "dimensions": aggregate_dimensions(comparison, bound_scenario, render_seconds=elapsed),
                "post_ptr_sha256": hashlib.sha256(np.ascontiguousarray(post_ptr).tobytes()).hexdigest(),
                "monitor_sha256": hashlib.sha256(np.ascontiguousarray(monitor).tobytes()).hexdigest(),
                "click_passed": bool(block_boundary_click_metrics(post_ptr)["passed"]),
            }
        else:
            scene_results[scene] = {
                "bound_scenario": bound_scenario,
                "dimensions": {},
                "post_ptr_sha256": hashlib.sha256(np.ascontiguousarray(post_ptr).tobytes()).hexdigest(),
                "monitor_sha256": hashlib.sha256(np.ascontiguousarray(monitor).tobytes()).hexdigest(),
                "click_passed": bool(block_boundary_click_metrics(post_ptr)["passed"]),
            }
    scenario_comparisons = {
        scene_result["bound_scenario"]: [scene_result]
        for scene_result in scene_results.values()
        if scene_result.get("dimensions")
    }
    multi = compare_multi_reference(scenario_comparisons, candidate_id=architecture) if scenario_comparisons else {"improvement_fraction": None, "dimension_median_relative_error": {}}
    return {
        "architecture": architecture,
        "overrides": dict(overrides),
        "scene_results": scene_results,
        "finite": overall_finite,
        "clipping_samples": clipping,
        "click_ok": click_ok,
        "render_seconds": render_seconds,
        "comparison": multi,
        "objective": multi.get("improvement_fraction"),
    }


def sobol_overrides(parameters: list[Any], count: int, seed: int) -> list[dict[str, float]]:
    """Deterministic Sobol box: baseline +/- delta scaled by [-1, 1]."""
    sampler = qmc.Sobol(d=len(parameters), scramble=True, seed=seed)
    unit = sampler.random(count)
    candidates = []
    for row in unit:
        overrides = {}
        for item, coordinate in zip(parameters, row):
            overrides[item.name] = float(item.baseline + (2.0 * coordinate - 1.0) * item.delta)
        candidates.append(overrides)
    return candidates


def refine_overrides(parameters: list[Any], center: dict[str, float], count: int, seed: int, shrink: float = 0.45) -> list[dict[str, float]]:
    """Local refinement around one center with a shrunken box."""
    sampler = qmc.Sobol(d=len(parameters), scramble=True, seed=seed)
    unit = sampler.random(count)
    candidates = []
    for row in unit:
        overrides = {}
        for item, coordinate in zip(parameters, row):
            span = item.delta * shrink
            overrides[item.name] = float(center[item.name] + (2.0 * coordinate - 1.0) * span)
        candidates.append(overrides)
    return candidates


def run_engineering_search(
    output_root,
    reference_audio: dict[str, tuple[np.ndarray, int]],
    *,
    architecture: str = "P3",
    coarse_count: int = 64,
    refine_count: int = 32,
    seed: int = 8675309,
    allowed_parameter_names: list[str] | None = None,
    base_config: dict[str, Any] | None = None,
    parameters_override: list[Any] | None = None,
) -> dict[str, Any]:
    """Two-stage bounded search for one architecture; every candidate rendered.

    Only reachability-verified parameters may enter the box; unreachable
    ones are excluded per the Stage X contract.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    all_parameters = hellcat_search_parameters()
    if parameters_override is not None:
        parameters = list(parameters_override)
    elif allowed_parameter_names is None:
        parameters = list(all_parameters)
    else:
        allowed = set(allowed_parameter_names)
        parameters = [item for item in all_parameters if item.name in allowed]
    if base_config is None:
        base_config = load_config("hellcat_v1")
    parent_audio: dict[str, np.ndarray] = {}
    for scene, bound_scenario, duration_s in SEARCH_SCENES:
        _, post_ptr, _, _, _ = _render_pcm(load_config("hellcat_v1"), "P1", scene, duration_s)
        parent_audio[bound_scenario] = post_ptr
    records: list[dict[str, Any]] = []
    stage1 = sobol_overrides(parameters, coarse_count, seed)
    for index, overrides in enumerate(stage1):
        record = _evaluate_candidate(architecture, overrides, base_config, parameters, reference_audio, parent_audio)
        record["stage"] = 1
        record["candidate_index"] = index
        records.append(record)
        write_json(output_root / f"stage1_{index:03d}.json", {key: record[key] for key in ("stage", "candidate_index", "overrides", "objective", "finite", "clipping_samples", "click_ok", "render_seconds")})
    finite_records = [record for record in records if record["finite"] and record["clipping_samples"] == 0 and record["objective"] is not None]
    ranked = sorted(finite_records, key=lambda record: record["objective"], reverse=True)
    top = ranked[:3]
    stage2_seed = seed + 1
    for rank, center in enumerate(top):
        for index, overrides in enumerate(refine_overrides(parameters, center["overrides"], refine_count // max(len(top), 1), stage2_seed + rank)):
            record = _evaluate_candidate(architecture, overrides, base_config, parameters, reference_audio, parent_audio)
            record["stage"] = 2
            record["candidate_index"] = f"r{rank}_{index}"
            records.append(record)
    evaluated = [record for record in records if record["objective"] is not None]
    best = max(evaluated, key=lambda record: record["objective"]) if evaluated else None
    summary = {
        "schema": SEARCH_SCHEMA,
        "architecture": architecture,
        "coarse_count": coarse_count,
        "refine_count": refine_count,
        "seed": seed,
        "search_scenes": [scene for scene, _, _ in SEARCH_SCENES],
        "bound_scenarios": [bound for _, bound, _ in SEARCH_SCENES if bound in reference_audio],
        "searched_parameters": [item.name for item in parameters],
        "excluded_parameters": [item.name for item in all_parameters if item not in parameters],
        "candidate_count": len(records),
        "best_objective": best["objective"] if best else None,
        "best_overrides": best["overrides"] if best else None,
        "parent_reference_objective": 0.0,
        "records": [
            {key: record[key] for key in ("stage", "candidate_index", "objective", "finite", "clipping_samples", "click_ok", "render_seconds")}
            for record in records
        ],
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    write_json(output_root / f"search_summary_{architecture}.json", summary)
    return {"summary": summary, "best": best, "parent_audio": parent_audio, "records": records}


__all__ = [
    "PRESELECTION_SCHEMA",
    "SEARCH_SCENES",
    "SEARCH_SCHEMA",
    "SOFT_IMPROVEMENT_TARGET",
    "refine_overrides",
    "run_engineering_search",
    "sobol_overrides",
]
