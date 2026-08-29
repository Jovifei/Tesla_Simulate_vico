"""Drive X6 Ferrari/RX-7 diagnostic migration with bounded candidate search.

Ferrari 458: R2 references are bound (speech-clean scenarios only) and the
search is reference-supported. RX-7: every R2 reference is speech-contaminated
(Jovi-confirmed), so the search is diagnostic-only — it ranks candidates by
Parent/Candidate separation without reference objectives and can never emit a
reference-supported preselection for RX-7.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import (  # noqa: E402
    MIGRATION_SCENES,
    build_vehicle_migration_trace,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_x import reference_caseset as rc  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.engineering_gate import evaluate_engineering_preselection  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import apply_parameters, hellcat_search_parameters  # noqa: E402
from scipy.stats import qmc  # noqa: E402
import numpy as np  # noqa: E402

MANIFEST = REPO_ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "reference_database" / "realism_reference_manifest.json"
R2_AUDIO_DIR = Path("E:/Claude_allow/Download/s12-acoustic-realism-v10")
RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x"
VEHICLE_CONFIG = {"ferrari_458": "ferrari_458_v1", "rx7_fd": "rx7_fd_v1"}
SEARCH_SCENES = ("hot_idle", "steady_mid", "full_pull", "lift")
COARSE_COUNT = 64
REFINE_COUNT = 24
OUTPUT_SCALE = 0.25

# scenario -> migration scene map for reference binding
_SCENE_MAP = {"hot_idle": "hot_idle", "steady_mid": "steady_mid", "full_pull": "full_pull", "lift": "lift"}


def _render(vehicle_id: str, architecture: str, config: dict[str, Any] | None, scene: str, duration_s: float = 2.0):
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import _render_architecture, _state_arrays  # type: ignore[attr-defined]
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine

    trace = build_vehicle_migration_trace(vehicle_id, scene, duration_s)
    if config is None:
        return _render_architecture(vehicle_id, architecture, trace)
    settings = {"P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"}, "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"}}[architecture]
    engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **settings)
    rendered = engine.process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    post = rendered.post_ptr_raw if rendered.post_ptr_raw is not None else rendered.raw_pcm
    return rendered.raw_pcm * OUTPUT_SCALE, post * OUTPUT_SCALE, rendered.monitor_pcm * OUTPUT_SCALE, rendered.diagnostics


def _vehicle_parameters(vehicle_id: str) -> list[Any]:
    """Reuse the Hellcat 27-parameter definitions; they mutate shared config paths."""
    return [item for item in hellcat_search_parameters()]


def _search(vehicle_id: str, architecture: str, reference_audio: dict[str, tuple[np.ndarray, int]], allowed: list[str], output_root: Path) -> dict[str, Any]:
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_x.multi_reference_comparator import aggregate_dimensions, compare_case, compare_multi_reference

    parameters = [item for item in _vehicle_parameters(vehicle_id) if item.name in set(allowed)]
    base_config = load_config(VEHICLE_CONFIG[vehicle_id])
    parent_audio: dict[str, np.ndarray] = {}
    for scene in SEARCH_SCENES:
        _, post, _, _ = _render(vehicle_id, "P1", None, scene)
        parent_audio[scene] = post

    def evaluate(overrides: dict[str, float], stage: int, index: Any) -> dict[str, Any]:
        config = apply_parameters(base_config, overrides, parameters) if overrides else None
        config = config if config is not None else copy.deepcopy(base_config)
        scene_results: dict[str, Any] = {}
        finite, clipping, click_ok = True, 0, True
        for scene in SEARCH_SCENES:
            raw, post, monitor, _ = _render(vehicle_id, architecture, config, scene)
            finite = finite and bool(np.all(np.isfinite(post)))
            clipping += int(np.count_nonzero(np.abs(post) >= 1.0))
            sha = hashlib.sha256(np.ascontiguousarray(post).tobytes()).hexdigest()
            if scene in reference_audio and scene in parent_audio:
                ref_audio, sample_rate = reference_audio[scene]
                min_len = min(ref_audio.size, post.shape[0])
                comparison = compare_case(ref_audio[:min_len], parent_audio[scene][:min_len], post[:min_len], sample_rate, candidate_id=architecture)
                dimensions = aggregate_dimensions(comparison, scene)
            else:
                dimensions = {}
            scene_results[scene] = {"sha": sha, "dimensions": dimensions}
        scenario_comparisons = {}
        for scene, payload in scene_results.items():
            if payload["dimensions"]:
                scenario_comparisons[scene] = [{"dimensions": payload["dimensions"]}]
        multi = compare_multi_reference(scenario_comparisons, candidate_id=architecture) if scenario_comparisons else None
        if multi is None:
            # diagnostic-only objective: parent-candidate spectral separation
            from tools.sound_sim.s12.acoustic_identity_v015.stage_x.multi_reference_comparator import timbre_metrics

            separations = []
            for scene in SEARCH_SCENES:
                _, post, _, _ = _render(vehicle_id, architecture, config, scene)
                parent_centroid = timbre_metrics(parent_audio[scene], 48000)["spectral_centroid_hz"]
                candidate_centroid = timbre_metrics(post, 48000)["spectral_centroid_hz"]
                parent_sha = hashlib.sha256(np.ascontiguousarray(parent_audio[scene]).tobytes()).hexdigest()
                candidate_sha = hashlib.sha256(np.ascontiguousarray(post).tobytes()).hexdigest()
                if candidate_sha == parent_sha:
                    continue
                separations.append(abs(candidate_centroid - parent_centroid) / max(parent_centroid, 1.0))
            objective = float(np.median(separations)) if separations else None
        else:
            objective = multi["improvement_fraction"]
        return {"stage": stage, "index": index, "overrides": overrides, "objective": objective, "finite": finite, "clipping_samples": clipping, "click_ok": click_ok, "comparison": multi or {}}

    records: list[dict[str, Any]] = []
    sampler = qmc.Sobol(d=len(parameters), scramble=True, seed=424242)
    for index, row in enumerate(sampler.random(COARSE_COUNT)):
        overrides = {item.name: float(item.baseline + (2.0 * coordinate - 1.0) * item.delta) for item, coordinate in zip(parameters, row)}
        records.append(evaluate(overrides, 1, index))
    ranked = sorted([r for r in records if r["objective"] is not None], key=lambda r: r["objective"], reverse=True)
    for rank, center in enumerate(ranked[:2]):
        sampler2 = qmc.Sobol(d=len(parameters), scramble=True, seed=424242 + rank + 1)
        for index, row in enumerate(sampler2.random(REFINE_COUNT // 2)):
            overrides = {item.name: float(center["overrides"][item.name] + (2.0 * coordinate - 1.0) * item.delta * 0.45) for item, coordinate in zip(parameters, row)}
            records.append(evaluate(overrides, 2, f"r{rank}_{index}"))
    evaluated = [r for r in records if r["objective"] is not None]
    best = max(evaluated, key=lambda r: r["objective"]) if evaluated else None
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": "s12.stage_x.migration_search.v1",
        "vehicle_id": vehicle_id,
        "architecture": architecture,
        "candidate_count": len(records),
        "reference_supported": bool(reference_audio),
        "best_objective": best["objective"] if best else None,
        "best_overrides": best["overrides"] if best else None,
        "records": [{k: r[k] for k in ("stage", "index", "objective", "finite", "clipping_samples")} for r in records],
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction; diagnostic migration only",
    }
    (output_root / f"search_{architecture}.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"best": best, "records": records, "summary": summary}


def main() -> int:
    started = time.perf_counter()
    reachability = json.loads((RUNTIME / "x4_reachability" / "parameter_reachability.json").read_text(encoding="utf-8"))
    allowed = [item["parameter"] for item in reachability["results"] if item["status"] == "PARAMETER_REACHABLE"]
    results: dict[str, Any] = {}
    for vehicle_id, speech_note in (("ferrari_458", None), ("rx7_fd", "Jovi: extracted audio contains speech, not engine sound")):
        caseset = rc.build_reference_caseset(vehicle_id, MANIFEST, R2_AUDIO_DIR, human_speech_confirmations={vehicle_id: speech_note} if speech_note else None)
        reference_audio: dict[str, tuple[np.ndarray, int]] = {}
        for case in caseset["cases"]:
            if case["status"] == "BOUND":
                audio, sample_rate = rc.load_case_segment_audio(case)
                reference_audio[case["scenario"]] = (audio, sample_rate)
        vehicle_started = time.perf_counter()
        vehicle_result: dict[str, Any] = {"valid_reference_count": caseset["valid_reference_count"], "reference_scenarios": sorted(reference_audio), "architectures": {}}
        for architecture in ("P2H", "P3"):
            search = _search(vehicle_id, architecture, reference_audio, allowed, RUNTIME / "x6_migration" / vehicle_id)
            best = search["best"]
            if reference_audio:
                gate = evaluate_engineering_preselection(best if best is not None else {}, architecture=architecture, valid_reference_count=caseset["valid_reference_count"], reference_evidence_level=caseset["reference_evidence_level"])
                gate["best_objective"] = best["objective"] if best else None
            else:
                gate = {
                    "status": "NO_DIAGNOSTIC_IMPROVEMENT" if best is None else "DIAGNOSTIC_ONLY_NO_REFERENCE",
                    "note": "all R2 references speech-contaminated; reference-supported preselection prohibited",
                    "best_objective": best["objective"] if best else None,
                }
            vehicle_result["architectures"][architecture] = gate
        ranking = sorted(vehicle_result["architectures"].items(), key=lambda kv: (kv[1].get("best_objective") or -1.0), reverse=True)
        vehicle_result["best_architecture"] = ranking[0][0] if ranking else None
        vehicle_result["wall_seconds"] = round(time.perf_counter() - vehicle_started, 1)
        results[vehicle_id] = vehicle_result
        print(f"{vehicle_id}: refs={vehicle_result['valid_reference_count']} best={vehicle_result['best_architecture']} ({vehicle_result['wall_seconds']}s)", flush=True)
    summary = {
        "schema": "s12.stage_x.x6_migration_summary.v1",
        "vehicles": results,
        "searched_parameter_count": len(allowed),
        "wall_seconds": round(time.perf_counter() - started, 1),
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction; no formal migration or OEM likeness claim",
    }
    (RUNTIME / "x6_migration" / "x6_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({vid: {"best": v["best_architecture"], "refs": v["valid_reference_count"]} for vid, v in results.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
