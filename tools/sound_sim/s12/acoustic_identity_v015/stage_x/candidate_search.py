"""Deterministic Stage X/Y candidate search with evidence-backed rendering.

The search covers steady and dynamic scenarios, samples categorical controls
as discrete choices, ranks candidates with a bounded Jovi-feedback term, and
materializes the best candidate to PCM24 WAV before publication.
"""

from __future__ import annotations

import copy
import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import qmc

from ..event_domain.config_schema import load_config
from ..stage_v.io import read_pcm24_wav, write_json, write_pcm24_wav
from ..stage_w.click_contract import block_boundary_click_metrics
from .human_feedback_objective import combine_reference_and_feedback_objective
from .multi_reference_comparator import aggregate_dimensions, compare_case, compare_multi_reference
from .parameter_domains import refine_value, sample_value, sanitize_overrides, validate_parameter_set
from .search_parameters import apply_parameters, hellcat_search_parameters

SEARCH_SCHEMA = "s12.stage_y.candidate_search.v2"
PRESELECTION_SCHEMA = "s12.stage_y.engineering_preselection_result.v2"

SEARCH_SCENES = (
    ("hot_idle_20s", "hot_idle", 2.0),
    ("steady_1200rpm", "steady_low", 2.0),
    ("steady_2000rpm", "steady_mid", 2.0),
    ("steady_3000rpm", "steady_high", 2.0),
    ("throttle_tip_in", "tip_in", 2.0),
    ("full_load_acceleration", "full_pull", 2.5),
    ("gear_shift", "shift", 2.0),
    ("high_rpm_lift", "lift", 2.5),
    ("afterfire_eligible", "afterfire", 2.5),
    ("idle_return", "idle_return", 2.0),
)
OUTPUT_SCALE = 0.25
SOFT_IMPROVEMENT_TARGET = 0.15
DIMENSION_REGRESSION_LIMIT = 0.10
KEY_DIMENSIONS = ("low_frequency_body", "120_400_pressure_attack", "mid_band_congestion")


def _sha(audio: np.ndarray | None) -> str | None:
    if audio is None:
        return None
    return hashlib.sha256(np.ascontiguousarray(audio).tobytes()).hexdigest()


def _render_pcm(
    config: dict[str, Any] | None,
    architecture: str,
    scene: str,
    duration_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], float]:
    """Render one actual architecture/scene with an optional config override."""
    from ..stage_w.bakeoff import _render_architecture, build_hellcat_bakeoff_trace

    trace = build_hellcat_bakeoff_trace(scene, duration_s)
    start = time.perf_counter()

    class _ConfigPatcher:
        def __init__(self, target: dict[str, Any]) -> None:
            self.target = target

        def __enter__(self) -> "_ConfigPatcher":
            import tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff as bakeoff

            self._bakeoff = bakeoff
            self._orig_load = bakeoff.load_config
            bakeoff.load_config = lambda vehicle_id: copy.deepcopy(self.target)
            return self

        def __exit__(self, *exc: Any) -> None:
            self._bakeoff.load_config = self._orig_load

    if config is not None:
        with _ConfigPatcher(config):
            raw, post_ptr, monitor, diagnostics = _render_architecture(architecture, trace)
    else:
        raw, post_ptr, monitor, diagnostics = _render_architecture(architecture, trace)
    elapsed = time.perf_counter() - start
    return raw, post_ptr, monitor, diagnostics, elapsed


def _resample_mono(audio: np.ndarray, source_rate: int, target_rate: int = 48000) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim == 2:
        values = values.mean(axis=1)
    if source_rate == target_rate:
        return values
    if values.size < 2:
        return values.copy()
    target_count = max(1, int(round(values.size * target_rate / source_rate)))
    source_x = np.linspace(0.0, 1.0, values.size, endpoint=False)
    target_x = np.linspace(0.0, 1.0, target_count, endpoint=False)
    return np.interp(target_x, source_x, values).astype(np.float64)


def _unpack_reference(value: Any) -> tuple[np.ndarray, int, dict[str, Any]]:
    """Accept legacy tuples and metadata-bearing reference records."""
    if isinstance(value, dict):
        audio = np.asarray(value["audio"], dtype=np.float64)
        sample_rate = int(value["sample_rate"])
        metadata = dict(value.get("metadata") or {})
    elif isinstance(value, tuple) and len(value) >= 2:
        audio = np.asarray(value[0], dtype=np.float64)
        sample_rate = int(value[1])
        metadata = dict(value[2]) if len(value) >= 3 and isinstance(value[2], dict) else {}
    else:
        raise ValueError("reference_audio entries must be dicts or (audio, sample_rate)")
    return _resample_mono(audio, sample_rate, 48000), 48000, metadata


def _render_context(config: dict[str, Any] | None, architecture: str) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for scene, bound_scenario, duration_s in SEARCH_SCENES:
        raw, post_ptr, monitor, diagnostics, elapsed = _render_pcm(config, architecture, scene, duration_s)
        context[bound_scenario] = {
            "scene": scene,
            "raw": raw,
            "post_ptr": post_ptr,
            "monitor": monitor,
            "diagnostics": diagnostics,
            "elapsed": elapsed,
            "raw_sha256": _sha(raw),
            "post_ptr_sha256": _sha(post_ptr),
            "monitor_sha256": _sha(monitor),
        }
    return context


def _changed_override_count(overrides: dict[str, float], parameters: list[Any]) -> int:
    by_name = {item.name: item for item in parameters}
    count = 0
    for name, value in overrides.items():
        item = by_name[name]
        if not np.isclose(float(value), float(item.baseline), rtol=0.0, atol=1.0e-12):
            count += 1
    return count


def _evaluate_candidate(
    architecture: str,
    overrides: dict[str, float],
    base_config: dict[str, Any],
    parameters: list[Any],
    reference_audio: dict[str, Any],
    parent_context: dict[str, dict[str, Any]],
    architecture_baseline: dict[str, dict[str, Any]],
    *,
    human_feedback: dict[str, Any] | None = None,
    independent_reference_count: int = 0,
) -> dict[str, Any]:
    """Render one candidate and collect all hard-gate evidence."""
    safe_overrides = sanitize_overrides(overrides)
    config = apply_parameters(base_config, safe_overrides, parameters)
    scene_results: dict[str, Any] = {}
    scenario_comparisons: dict[str, list[dict[str, Any]]] = {}

    finite = True
    clipping = 0
    click_ok = True
    render_seconds = 0.0
    post_ptr_exists = True
    raw_monitor_separated = True
    scenario_compatible = True
    parent_sha_different = False
    override_audio_changed = False
    wrong_condition_afterfire_count = 0
    monitor_idle_rms: float | None = None
    reference_clean = True
    bound_reference_case_count = 0

    for scene, bound_scenario, duration_s in SEARCH_SCENES:
        raw, post_ptr, monitor, diagnostics, elapsed = _render_pcm(config, architecture, scene, duration_s)
        render_seconds += elapsed
        expected_frames = int(round(duration_s * 48000))
        arrays = (raw, post_ptr, monitor)
        finite = finite and all(value is not None and np.all(np.isfinite(value)) for value in arrays)
        post_ptr_exists = post_ptr_exists and post_ptr is not None
        scenario_compatible = scenario_compatible and all(
            value is not None and value.ndim == 2 and value.shape == (expected_frames, 2)
            for value in arrays
        )
        if post_ptr is not None:
            clipping += int(np.count_nonzero(np.abs(post_ptr) >= 1.0))
            click_metrics = block_boundary_click_metrics(post_ptr)
            click_ok = click_ok and bool(click_metrics["passed"])
        else:
            click_metrics = {"passed": False}
            click_ok = False

        raw_sha = _sha(raw)
        post_sha = _sha(post_ptr)
        monitor_sha = _sha(monitor)
        raw_monitor_separated = raw_monitor_separated and raw_sha != monitor_sha

        parent = parent_context[bound_scenario]
        baseline = architecture_baseline[bound_scenario]
        parent_sha_different = parent_sha_different or post_sha != parent["post_ptr_sha256"]
        override_audio_changed = override_audio_changed or post_sha != baseline["post_ptr_sha256"]

        afterfire_count = int(diagnostics.get("afterfire_event_count", 0))
        if bound_scenario not in {"lift", "afterfire"}:
            wrong_condition_afterfire_count += afterfire_count

        if bound_scenario == "hot_idle" and monitor is not None:
            monitor_idle_rms = float(np.sqrt(np.mean(np.square(monitor))))

        dimensions: dict[str, float] = {}
        reference_metadata: dict[str, Any] = {}
        if bound_scenario in reference_audio and post_ptr is not None:
            reference, sample_rate, reference_metadata = _unpack_reference(reference_audio[bound_scenario])
            clean = not bool(reference_metadata.get("speech_contaminated") or reference_metadata.get("rejected"))
            reference_clean = reference_clean and clean
            if clean:
                bound_reference_case_count += 1
                parent_pcm = parent["post_ptr"]
                minimum = min(reference.size, parent_pcm.shape[0], post_ptr.shape[0])
                comparison = compare_case(
                    reference[:minimum],
                    parent_pcm[:minimum],
                    post_ptr[:minimum],
                    sample_rate,
                    candidate_id=architecture,
                )
                dimensions = aggregate_dimensions(comparison, bound_scenario, render_seconds=elapsed)
                scenario_comparisons.setdefault(bound_scenario, []).append({
                    "dimensions": dimensions,
                    "reference_metadata": reference_metadata,
                })

        scene_results[scene] = {
            "bound_scenario": bound_scenario,
            "duration_s": duration_s,
            "dimensions": dimensions,
            "raw_sha256": raw_sha,
            "post_ptr_sha256": post_sha,
            "monitor_sha256": monitor_sha,
            "parent_post_ptr_sha256": parent["post_ptr_sha256"],
            "architecture_baseline_post_ptr_sha256": baseline["post_ptr_sha256"],
            "click_passed": bool(click_metrics["passed"]),
            "afterfire_event_count": afterfire_count,
            "reference_bound": bound_scenario in reference_audio,
            "reference_clean": not bool(
                reference_metadata.get("speech_contaminated") or reference_metadata.get("rejected")
            ) if reference_metadata else None,
        }

    multi = (
        compare_multi_reference(scenario_comparisons, candidate_id=architecture)
        if scenario_comparisons
        else {"improvement_fraction": None, "dimension_median_relative_error": {}, "scenario_case_counts": {}}
    )
    human = combine_reference_and_feedback_objective(
        multi.get("improvement_fraction"),
        multi.get("dimension_median_relative_error", {}),
        human_feedback,
    )
    changed_count = _changed_override_count(safe_overrides, parameters)
    parameter_consumed = bool(changed_count > 0 and override_audio_changed)

    return {
        "architecture": architecture,
        "overrides": safe_overrides,
        "scene_results": scene_results,
        "finite": finite,
        "clipping_samples": clipping,
        "click_ok": click_ok,
        "render_seconds": render_seconds,
        "comparison": multi,
        "human_feedback": human_feedback,
        "human_objective": human,
        "objective": human.get("combined_engineering_objective"),
        "reference_objective": multi.get("improvement_fraction"),
        "parent_sha_different": parent_sha_different,
        "post_ptr_exists": post_ptr_exists,
        "raw_monitor_separated": raw_monitor_separated,
        "parameter_consumed": parameter_consumed,
        "consumed_parameter_count": changed_count if parameter_consumed else 0,
        "scenario_compatible": scenario_compatible,
        "reference_clean": bool(reference_clean and bound_reference_case_count > 0),
        "bound_reference_case_count": bound_reference_case_count,
        "independent_reference_count": int(independent_reference_count),
        "wrong_condition_afterfire_count": wrong_condition_afterfire_count,
        "monitor_idle_rms": monitor_idle_rms,
        "evidence_contract": "s12.stage_y.rendered_candidate_evidence.v1",
    }


def sobol_overrides(parameters: list[Any], count: int, seed: int) -> list[dict[str, float]]:
    """Generate a deterministic domain-aware Sobol candidate set."""
    if count <= 0:
        return []
    validation = validate_parameter_set(parameters)
    if not validation["passed"]:
        raise ValueError(f"invalid parameter domains: {validation['errors']}")
    sampler = qmc.Sobol(d=len(parameters), scramble=True, seed=seed)
    unit = sampler.random(count)
    return [
        {item.name: sample_value(item, coordinate) for item, coordinate in zip(parameters, row)}
        for row in unit
    ]


def refine_overrides(
    parameters: list[Any],
    center: dict[str, float],
    count: int,
    seed: int,
    shrink: float = 0.45,
) -> list[dict[str, float]]:
    """Generate local continuous refinements while re-exploring categories."""
    if count <= 0:
        return []
    sampler = qmc.Sobol(d=len(parameters), scramble=True, seed=seed)
    unit = sampler.random(count)
    return [
        {
            item.name: refine_value(item, center[item.name], coordinate, shrink)
            for item, coordinate in zip(parameters, row)
        }
        for row in unit
    ]


def _materialize_best_candidate(
    output_root: Path,
    *,
    architecture: str,
    base_config: dict[str, Any],
    parameters: list[Any],
    overrides: dict[str, float],
) -> dict[str, Any]:
    """Write and reopen best-candidate raw/post/monitor WAVs for audit."""
    config = apply_parameters(base_config, sanitize_overrides(overrides), parameters)
    root = output_root / "best_candidate"
    files: dict[str, Any] = {}
    for scene, bound_scenario, duration_s in SEARCH_SCENES:
        raw, post_ptr, monitor, diagnostics, elapsed = _render_pcm(config, architecture, scene, duration_s)
        scene_receipt: dict[str, Any] = {
            "bound_scenario": bound_scenario,
            "duration_s": duration_s,
            "render_seconds": elapsed,
            "diagnostic_keys": sorted(diagnostics),
            "stems": {},
        }
        for stem, audio in (("raw_source", raw), ("post_ptr_raw", post_ptr), ("monitor", monitor)):
            receipt = write_pcm24_wav(root / scene / f"{stem}.wav", audio, 48000)
            reopened, metadata = read_pcm24_wav(receipt.path)
            if reopened.shape != audio.shape or metadata["clipping"] != 0:
                raise ValueError(f"best candidate reopen failed: {scene}/{stem}")
            scene_receipt["stems"][stem] = {
                "path": str(Path(receipt.path).relative_to(output_root).as_posix()),
                "sha256": receipt.sha256,
                "metadata": metadata,
            }
        files[scene] = scene_receipt
    payload = {
        "schema": "s12.stage_y.best_candidate_pcm_receipt.v1",
        "architecture": architecture,
        "overrides": sanitize_overrides(overrides),
        "scenes": files,
        "all_wavs_reopened": True,
        "scope": "engineering diagnostic only; no Profile Freeze",
    }
    write_json(root / "best_candidate_receipt.json", payload)
    return payload


def run_engineering_search(
    output_root: Path,
    reference_audio: dict[str, Any],
    *,
    architecture: str = "P3",
    coarse_count: int = 64,
    refine_count: int = 32,
    seed: int = 8675309,
    allowed_parameter_names: list[str] | None = None,
    base_config: dict[str, Any] | None = None,
    parameters_override: list[Any] | None = None,
    human_feedback: dict[str, Any] | None = None,
    independent_reference_count: int | None = None,
) -> dict[str, Any]:
    """Run two-stage rendered search and publish an auditable finalist."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    all_parameters = hellcat_search_parameters()
    if parameters_override is not None:
        parameters = list(parameters_override)
    elif allowed_parameter_names is None:
        parameters = list(all_parameters)
    else:
        allowed = set(allowed_parameter_names)
        parameters = [item for item in all_parameters if item.name in allowed]
    if not parameters:
        raise ValueError("engineering search has no parameters")
    domain_receipt = validate_parameter_set(parameters)
    if not domain_receipt["passed"]:
        raise ValueError(f"invalid parameter domains: {domain_receipt['errors']}")
    write_json(output_root / "parameter_domains.json", domain_receipt)

    if base_config is None:
        base_config = load_config("hellcat_v1")
    independent_count = int(independent_reference_count) if independent_reference_count is not None else len(reference_audio)

    parent_context = _render_context(load_config("hellcat_v1"), "P1")
    architecture_baseline = _render_context(base_config, architecture)

    records: list[dict[str, Any]] = []
    for index, overrides in enumerate(sobol_overrides(parameters, coarse_count, seed)):
        record = _evaluate_candidate(
            architecture,
            overrides,
            base_config,
            parameters,
            reference_audio,
            parent_context,
            architecture_baseline,
            human_feedback=human_feedback,
            independent_reference_count=independent_count,
        )
        record["stage"] = 1
        record["candidate_index"] = index
        records.append(record)
        write_json(output_root / f"stage1_{index:03d}.json", {
            key: record[key]
            for key in (
                "stage", "candidate_index", "overrides", "objective", "reference_objective",
                "finite", "clipping_samples", "click_ok", "render_seconds",
                "parent_sha_different", "post_ptr_exists", "raw_monitor_separated",
                "parameter_consumed", "consumed_parameter_count", "scenario_compatible",
                "reference_clean", "wrong_condition_afterfire_count", "monitor_idle_rms",
            )
        })

    eligible_stage1 = [
        record for record in records
        if record["finite"] and record["clipping_samples"] == 0 and record["click_ok"] and record["objective"] is not None
    ]
    ranked = sorted(eligible_stage1, key=lambda record: record["objective"], reverse=True)
    top = ranked[:3]
    stage2_seed = seed + 1
    per_center = refine_count // max(len(top), 1)
    for rank, center in enumerate(top):
        for index, overrides in enumerate(refine_overrides(parameters, center["overrides"], per_center, stage2_seed + rank)):
            record = _evaluate_candidate(
                architecture,
                overrides,
                base_config,
                parameters,
                reference_audio,
                parent_context,
                architecture_baseline,
                human_feedback=human_feedback,
                independent_reference_count=independent_count,
            )
            record["stage"] = 2
            record["candidate_index"] = f"r{rank}_{index}"
            records.append(record)

    evaluated = [
        record for record in records
        if record["objective"] is not None and record["finite"] and record["clipping_samples"] == 0 and record["click_ok"]
    ]
    best = max(evaluated, key=lambda record: record["objective"]) if evaluated else None
    materialization = None
    if best is not None:
        materialization = _materialize_best_candidate(
            output_root,
            architecture=architecture,
            base_config=base_config,
            parameters=parameters,
            overrides=best["overrides"],
        )
        best["best_candidate_pcm_receipt"] = "best_candidate/best_candidate_receipt.json"

    summary = {
        "schema": SEARCH_SCHEMA,
        "architecture": architecture,
        "coarse_count": coarse_count,
        "refine_count": refine_count,
        "seed": seed,
        "search_scenes": [scene for scene, _, _ in SEARCH_SCENES],
        "bound_scenarios": [bound for _, bound, _ in SEARCH_SCENES if bound in reference_audio],
        "dynamic_scenarios": ["tip_in", "full_pull", "shift", "lift", "afterfire", "idle_return"],
        "independent_reference_count": independent_count,
        "searched_parameters": [item.name for item in parameters],
        "excluded_parameters": [item.name for item in all_parameters if item not in parameters],
        "candidate_count": len(records),
        "best_objective": best["objective"] if best else None,
        "best_reference_objective": best["reference_objective"] if best else None,
        "best_overrides": best["overrides"] if best else None,
        "best_candidate_materialized": materialization is not None,
        "parent_reference_objective": 0.0,
        "records": [
            {key: record[key] for key in (
                "stage", "candidate_index", "objective", "reference_objective",
                "finite", "clipping_samples", "click_ok", "render_seconds", "parameter_consumed",
            )}
            for record in records
        ],
        "scope": "engineering diagnostic only; synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    write_json(output_root / f"search_summary_{architecture}.json", summary)
    return {
        "summary": summary,
        "best": best,
        "parent_audio": {scenario: context["post_ptr"] for scenario, context in parent_context.items()},
        "records": records,
    }


__all__ = [
    "PRESELECTION_SCHEMA",
    "SEARCH_SCENES",
    "SEARCH_SCHEMA",
    "SOFT_IMPROVEMENT_TARGET",
    "refine_overrides",
    "run_engineering_search",
    "sobol_overrides",
]
