"""AA-C3-aware Stage AD reference search.

The search preserves the frozen AA-C3 pressure/event-body/carrier processing and
Track-P boundary while perturbing upstream S12 parameters. Results are new
Stage-AD diagnostic candidates; the official v3 package is never overwritten.

Cross-iteration convergence uses an *absolute reference-distance* whose scale is
anchored only to the real reference metric (plus fixed metric floors). It does
not compare changing per-iteration improvement fractions as if they shared one
origin.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from ..stage_aa.candidates import render_candidate
from ..stage_v.io import write_json, write_pcm24_wav
from ..stage_w.click_contract import block_boundary_click_metrics
from ..stage_x.candidate_search import SEARCH_SCENES, refine_overrides, sobol_overrides
from ..stage_x.human_feedback_objective import combine_reference_and_feedback_objective
from ..stage_x.multi_reference_comparator import aggregate_dimensions, compare_case, compare_multi_reference
from ..stage_x.parameter_domains import sanitize_overrides, validate_parameter_set
from ..stage_x.search_parameters import apply_parameters, hellcat_search_parameters
from ..stage_y.package import _fitted_config

AA_C3_SEARCH_SCHEMA = "s12.stage_ad.aa_c3_reference_search.v2"

AA_C3_SOURCE_CAUSAL_PARAMETERS = (
    "combustion_event_energy",
    "combustion_rise_time",
    "combustion_decay_time",
    "cycle_variation",
    "crank_inertia",
    "idle_governor",
    "primary_length_spread",
    "primary_attenuation_spread",
    "waveguide_reflection",
    "waveguide_loss",
    "collector_loss",
    "blower_sideband_mix",
    "blower_broadband_mix",
    "blower_casing_mix",
    "intake_mix",
    "boost_attack",
    "boost_release",
    "bypass_threshold",
    "afterfire_reservoir_rate",
    "afterfire_ignition_delay",
    "afterfire_location_mix",
    "afterfire_energy",
)

_AA_SCENE = {
    "hot_idle": "hot_idle",
    "steady_low": "steady_1200",
    "steady_mid": "steady_2000",
    "steady_high": "steady_3000",
    "tip_in": "tip_in",
    "full_pull": "full_load",
    "shift": "gear_shift",
    "lift": "lift",
    "afterfire": "afterfire",
    "idle_return": "idle_return",
}

_METRIC_FLOORS: dict[str, float] = {
    "rms_dbfs": 1.0,
    "peak_dbfs": 1.0,
    "crest_db": 1.0,
    "dynamic_range_db": 1.0,
    "transient_event_density_per_s": 0.5,
    "spectral_centroid_hz": 100.0,
    "spectral_flux": 0.01,
    "roughness_proxy": 0.05,
    "sharpness_proxy": 0.05,
    "tonality_proxy": 0.05,
    "persistent_tone_ratio": 0.05,
    "narrowband_whine_proxy": 0.02,
}


def _sha(audio: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(audio).tobytes()).hexdigest()


def _reference_entry(value: Any) -> tuple[np.ndarray, int, dict[str, Any]]:
    if isinstance(value, dict):
        audio = np.asarray(value["audio"], dtype=np.float64)
        sample_rate = int(value["sample_rate"])
        metadata = dict(value.get("metadata") or {})
    else:
        audio = np.asarray(value[0], dtype=np.float64)
        sample_rate = int(value[1])
        metadata = dict(value[2]) if len(value) >= 3 else {}
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if sample_rate != 48000:
        count = max(1, int(round(audio.size * 48000 / sample_rate)))
        audio = np.interp(
            np.linspace(0.0, 1.0, count, endpoint=False),
            np.linspace(0.0, 1.0, audio.size, endpoint=False),
            audio,
        )
        sample_rate = 48000
    return audio, sample_rate, metadata


def _metric_floor(name: str) -> float:
    if name.startswith("band_share_"):
        return 0.02
    return _METRIC_FLOORS.get(name, 0.01)


def _absolute_reference_distance(case_comparison: dict[str, Any]) -> float:
    """Stable distance independent of the changing parent candidate.

    Each metric is normalized by ``max(abs(reference), fixed_floor)``. Floors
    are fixed by metric semantics so a later iteration cannot change the ruler.
    The median is robust to one pathological proxy; individual terms are capped
    to keep near-zero reference metrics from dominating the whole objective.
    """
    values: list[float] = []
    for name, row in dict(case_comparison.get("metrics") or {}).items():
        reference = float(row["reference"])
        candidate = float(row["candidate"])
        if not np.isfinite(reference) or not np.isfinite(candidate):
            continue
        scale = max(abs(reference), _metric_floor(name))
        values.append(float(np.clip(abs(candidate - reference) / scale, 0.0, 10.0)))
    return float(np.median(values)) if values else float("nan")


def _render_context(config: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for _, scenario, duration_s in SEARCH_SCENES:
        context[scenario] = render_candidate(
            "AA-C3", _AA_SCENE[scenario], duration_s, config_override=config
        )
    return context


def _evaluate(
    config: dict[str, Any],
    reference_audio: dict[str, Any],
    baseline_context: dict[str, Any],
    *,
    human_feedback: dict[str, Any] | None,
    independent_reference_count: int,
) -> dict[str, Any]:
    candidate_context = _render_context(config)
    finite = True
    clipping_samples = 0
    click_ok = True
    audio_changed = False
    scene_results: dict[str, Any] = {}
    comparisons: dict[str, list[dict[str, Any]]] = {}
    absolute_distances: list[float] = []

    for _, scenario, _ in SEARCH_SCENES:
        candidate = candidate_context[scenario]
        baseline = baseline_context[scenario]
        audio = np.asarray(candidate.raw_pcm, dtype=np.float64)
        finite = finite and bool(np.all(np.isfinite(audio)))
        clipping_samples += int(np.count_nonzero(np.abs(audio) >= 1.0))
        click = block_boundary_click_metrics(audio)
        click_ok = click_ok and bool(click["passed"])
        audio_changed = audio_changed or _sha(audio) != _sha(baseline.raw_pcm)

        dimensions: dict[str, float] = {}
        absolute_distance: float | None = None
        if scenario in reference_audio:
            reference, sample_rate, metadata = _reference_entry(reference_audio[scenario])
            clean = not bool(metadata.get("speech_contaminated") or metadata.get("rejected"))
            if clean:
                minimum = min(reference.shape[0], baseline.raw_pcm.shape[0], audio.shape[0])
                comparison = compare_case(
                    reference[:minimum],
                    baseline.raw_pcm[:minimum],
                    audio[:minimum],
                    sample_rate,
                    candidate_id="AA-C3-StageAD",
                )
                dimensions = aggregate_dimensions(comparison, scenario, render_seconds=0.0)
                absolute_distance = _absolute_reference_distance(comparison)
                if np.isfinite(absolute_distance):
                    absolute_distances.append(float(absolute_distance))
                comparisons.setdefault(scenario, []).append({
                    "dimensions": dimensions,
                    "reference_metadata": metadata,
                })
        scene_results[scenario] = {
            "aa_scene": _AA_SCENE[scenario],
            "raw_sha256": _sha(audio),
            "baseline_raw_sha256": _sha(baseline.raw_pcm),
            "dimensions": dimensions,
            "absolute_reference_distance": absolute_distance,
            "click_passed": bool(click["passed"]),
        }

    wrong_condition = render_candidate(
        "AA-C3", "afterfire_ineligible", 0.5, config_override=config
    ).diagnostics["engine"].get("afterfire_event_count", 0)

    multi = (
        compare_multi_reference(comparisons, candidate_id="AA-C3-StageAD")
        if comparisons
        else {"improvement_fraction": None, "dimension_median_relative_error": {}}
    )
    absolute_reference_distance = (
        float(np.median(absolute_distances)) if absolute_distances else None
    )
    human = combine_reference_and_feedback_objective(
        multi.get("improvement_fraction"),
        multi.get("dimension_median_relative_error", {}),
        human_feedback,
    )
    feedback_adjustment = float(human.get("feedback_adjustment") or 0.0)
    fixed_scale_objective = (
        -float(absolute_reference_distance) + feedback_adjustment
        if absolute_reference_distance is not None
        else None
    )
    return {
        "scene_results": scene_results,
        "finite": finite,
        "clipping_samples": clipping_samples,
        "click_ok": click_ok,
        "wrong_condition_afterfire_count": int(wrong_condition),
        "parameter_consumed": audio_changed,
        "comparison": multi,
        "reference_objective": multi.get("improvement_fraction"),
        "absolute_reference_distance": absolute_reference_distance,
        "human_objective": human,
        "objective": fixed_scale_objective,
        "independent_reference_count": int(independent_reference_count),
    }


def _materialize(
    output_root: Path,
    config: dict[str, Any],
    overrides: dict[str, float],
) -> dict[str, Any]:
    root = output_root / "best_candidate"
    scenes: dict[str, Any] = {}
    for _, scenario, duration_s in SEARCH_SCENES:
        rendered = render_candidate("AA-C3", _AA_SCENE[scenario], duration_s, config_override=config)
        stem_receipts: dict[str, Any] = {}
        for stem, audio in (
            ("raw_source", rendered.pre_ptr_pcm),
            ("post_ptr_raw", rendered.raw_pcm),
            ("monitor", rendered.monitor_pcm),
        ):
            receipt = write_pcm24_wav(root / _AA_SCENE[scenario] / f"{stem}.wav", audio, 48000)
            stem_receipts[stem] = {
                "path": str(Path(receipt.path).relative_to(output_root).as_posix()),
                "sha256": receipt.sha256,
            }
        scenes[scenario] = {"aa_scene": _AA_SCENE[scenario], "stems": stem_receipts}
    payload = {
        "schema": "s12.stage_ad.aa_c3_best_candidate_receipt.v1",
        "baseline": "AA-C3 fixed processing + source-causal config overrides",
        "overrides": sanitize_overrides(overrides),
        "scenes": scenes,
        "official_v3_modified": False,
        "qualification": "diagnostic audition only; Jovi human decision required",
    }
    write_json(root / "best_candidate_receipt.json", payload)
    return payload


def run_aa_c3_search(
    output_root: Path,
    reference_audio: dict[str, Any],
    *,
    architecture: str = "AA-C3",
    coarse_count: int = 48,
    refine_count: int = 24,
    seed: int = 20260904,
    allowed_parameter_names: list[str] | None = None,
    base_config: dict[str, Any] | None = None,
    parameters_override: list[Any] | None = None,
    human_feedback: dict[str, Any] | None = None,
    independent_reference_count: int | None = None,
) -> dict[str, Any]:
    """Run a bounded source-parameter search around AA-C3."""
    del architecture
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    all_parameters = list(hellcat_search_parameters())
    if parameters_override is not None:
        parameters = list(parameters_override)
    else:
        allowed = set(allowed_parameter_names or AA_C3_SOURCE_CAUSAL_PARAMETERS)
        parameters = [item for item in all_parameters if item.name in allowed]
    if not parameters:
        raise ValueError("AA-C3 Stage AD search has no parameters")
    validation = validate_parameter_set(parameters)
    if not validation["passed"]:
        raise ValueError(f"invalid AA-C3 parameter domains: {validation['errors']}")
    write_json(output_root / "parameter_domains.json", validation)

    base_config = copy.deepcopy(base_config if base_config is not None else _fitted_config())
    baseline_context = _render_context(base_config)
    independent_count = int(independent_reference_count) if independent_reference_count is not None else len(reference_audio)

    records: list[dict[str, Any]] = []
    for index, overrides in enumerate(sobol_overrides(parameters, coarse_count, seed)):
        safe = sanitize_overrides(overrides)
        config = apply_parameters(base_config, safe, parameters)
        record = _evaluate(
            config,
            reference_audio,
            baseline_context,
            human_feedback=human_feedback,
            independent_reference_count=independent_count,
        )
        record.update({"stage": 1, "candidate_index": index, "overrides": safe})
        records.append(record)

    def eligible(item: dict[str, Any]) -> bool:
        return bool(
            item["finite"]
            and item["clipping_samples"] == 0
            and item["click_ok"]
            and item["wrong_condition_afterfire_count"] == 0
            and item["parameter_consumed"]
            and item["objective"] is not None
            and item["absolute_reference_distance"] is not None
        )

    top = sorted(
        [item for item in records if eligible(item)],
        key=lambda item: item["objective"],
        reverse=True,
    )[:3]
    per_center = refine_count // max(len(top), 1)
    for rank, center in enumerate(top):
        for index, overrides in enumerate(
            refine_overrides(parameters, center["overrides"], per_center, seed + 1 + rank)
        ):
            safe = sanitize_overrides(overrides)
            config = apply_parameters(base_config, safe, parameters)
            record = _evaluate(
                config,
                reference_audio,
                baseline_context,
                human_feedback=human_feedback,
                independent_reference_count=independent_count,
            )
            record.update({"stage": 2, "candidate_index": f"r{rank}_{index}", "overrides": safe})
            records.append(record)

    evaluated = [item for item in records if eligible(item)]
    best = max(evaluated, key=lambda item: item["objective"]) if evaluated else None
    materialized = None
    if best is not None:
        best_config = apply_parameters(base_config, best["overrides"], parameters)
        materialized = _materialize(output_root, best_config, best["overrides"])
        best["best_candidate_pcm_receipt"] = "best_candidate/best_candidate_receipt.json"

    summary = {
        "schema": AA_C3_SEARCH_SCHEMA,
        "baseline": "AA-C3",
        "fixed_candidate_processing_preserved": True,
        "track_p_frozen": True,
        "official_v3_modified": False,
        "candidate_count": len(records),
        "searched_parameters": [item.name for item in parameters],
        "best_objective": best.get("objective") if best else None,
        "best_absolute_reference_distance": best.get("absolute_reference_distance") if best else None,
        "best_reference_objective": best.get("reference_objective") if best else None,
        "best_overrides": best.get("overrides") if best else None,
        "best_candidate_materialized": materialized is not None,
        "objective_interpretation": "maximize -absolute_reference_distance + bounded human adjustment",
        "scope": "Stage-AD diagnostic audition only; no automatic profile promotion",
    }
    write_json(output_root / "aa_c3_search_summary.json", summary)
    return {"summary": summary, "best": best, "records": records}


__all__ = [
    "AA_C3_SEARCH_SCHEMA",
    "AA_C3_SOURCE_CAUSAL_PARAMETERS",
    "run_aa_c3_search",
]
