"""
Stage AD Closed-Loop Calibration for Ferrari 458 Italia.
Multi-iteration reference-driven optimization against authentic AutoTopNL clips.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import qmc

import sys
sys.path.insert(0, r"E:\Tesla_speed\worktrees\s12-stage-ad-closed-loop-calibration")
sys.path.insert(0, r"C:\Users\Admin\.gemini\antigravity\brain\8bc761b6-1605-4302-b371-adbbacb9e18d\scratch")

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.multi_reference_comparator import compare_case, aggregate_dimensions
from ferrari_search_harness import (
    FERRARI_SEARCH_PARAMETERS,
    SCENE_DEFS,
    apply_ferrari_parameters,
    load_config,
    render_ferrari_scene,
    SAMPLE_RATE_HZ,
    BLOCK_SIZE,
)

OUTPUT_ROOT = Path(r"E:\Tesla_speed\stage_ad_runs\ferrari_458_closed_loop_v1")
CASESET_PATH = OUTPUT_ROOT / "reference_caseset.json"
PACKAGE_DIR = Path(r"E:\Tesla_speed\review_packages\s12-stage-ad-ferrari-458-closed-loop-v1")
WEB_AUDIO_DIR = PACKAGE_DIR / "web_audio"

_METRIC_FLOORS = {
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

def metric_floor(name: str) -> float:
    if name.startswith("band_share_"):
        return 0.02
    return _METRIC_FLOORS.get(name, 0.01)

def compute_case_distance(case_comparison: dict[str, Any]) -> float:
    values = []
    for name, row in dict(case_comparison.get("metrics") or {}).items():
        ref_val = float(row["reference"])
        cand_val = float(row["candidate"])
        if not np.isfinite(ref_val) or not np.isfinite(cand_val):
            continue
        scale = max(abs(ref_val), metric_floor(name))
        values.append(float(np.clip(abs(cand_val - ref_val) / scale, 0.0, 10.0)))
    return float(np.median(values)) if values else float("nan")

def load_references(caseset: dict[str, Any]) -> dict[str, np.ndarray]:
    refs = {}
    for c in caseset.get("cases", []):
        scen = c["scenario"]
        p = Path(c["audio_path"])
        with wave.open(str(p), "rb") as wf:
            data = wf.readframes(wf.getnframes())
            # Convert 16-bit to float
            audio = np.frombuffer(data, dtype=np.int16).reshape(-1, wf.getnchannels()) / 32768.0
            refs[scen] = audio
    return refs

def evaluate_candidate(
    cfg: dict[str, Any],
    references: dict[str, np.ndarray],
    eval_duration_s: float = 2.0,
    eval_scenes: list[str] | None = None,
) -> dict[str, Any]:
    if eval_scenes is None:
        eval_scenes = ["hot_idle", "steady_low", "steady_mid", "steady_high", "full_pull", "afterfire"]
    
    scene_results = {}
    distances = []
    all_finite = True
    all_clicks_pass = True
    max_peak = 0.0
    
    for scen in eval_scenes:
        pcm, diags = render_ferrari_scene(cfg, scen, eval_duration_s)
        peak = float(np.max(np.abs(pcm)))
        max_peak = max(max_peak, peak)
        finite = bool(np.all(np.isfinite(pcm)))
        all_finite = all_finite and finite
        click = block_boundary_click_metrics(pcm, BLOCK_SIZE)
        all_clicks_pass = all_clicks_pass and bool(click["passed"])
        
        dist = None
        if scen in references:
            ref_pcm = references[scen]
            min_len = min(ref_pcm.shape[0], pcm.shape[0])
            comp = compare_case(
                ref_pcm[:min_len],
                pcm[:min_len], # baseline placeholder
                pcm[:min_len],
                SAMPLE_RATE_HZ,
                candidate_id="ferrari_458_candidate",
            )
            dist = compute_case_distance(comp)
            if np.isfinite(dist):
                distances.append(dist)
        
        scene_results[scen] = {
            "peak": peak,
            "finite": finite,
            "click_passed": click["passed"],
            "distance": dist
        }
    
    median_dist = float(np.median(distances)) if distances else float("nan")
    
    return {
        "median_distance": median_dist,
        "distances": distances,
        "scene_results": scene_results,
        "all_finite": all_finite,
        "all_clicks_pass": all_clicks_pass,
        "max_peak": max_peak,
        "passed_gates": bool(all_finite and all_clicks_pass and max_peak <= 0.985),
    }

def run_ferrari_closed_loop():
    print("=================================================================")
    print(" Stage AD Closed-Loop Calibration: Ferrari 458 Italia (F136 V8) ")
    print("=================================================================")
    
    caseset = json.loads(CASESET_PATH.read_text(encoding="utf-8"))
    references = load_references(caseset)
    print(f"Loaded {len(references)} reference scenarios: {list(references.keys())}")
    
    base_cfg = load_config("ferrari_458_v1")
    current_cfg = copy.deepcopy(base_cfg)
    
    # -------------------------------------------------------------
    # Iteration 00: Baseline Evaluation
    # -------------------------------------------------------------
    print("\n--- [Iteration 00: Initial Baseline Evaluation] ---")
    base_eval = evaluate_candidate(current_cfg, references, eval_duration_s=2.0)
    print(f"Baseline Median Reference Distance: {base_eval['median_distance']:.4f}")
    for scen, res in base_eval["scene_results"].items():
        print(f"  {scen:14s} -> distance: {res['distance']:.4f}, peak: {res['peak']:.4f}, click: {res['click_passed']}")
    
    iter0_dir = OUTPUT_ROOT / "iteration_00"
    iter0_dir.mkdir(parents=True, exist_ok=True)
    with open(iter0_dir / "closed_loop_iteration.json", "w", encoding="utf-8") as f:
        json.dump({
            "iteration": 0,
            "stage": "baseline",
            "median_distance": base_eval["median_distance"],
            "scene_results": base_eval["scene_results"],
        }, f, indent=2)
    
    # -------------------------------------------------------------
    # Iteration 01: Body & Combustion Optimization
    # -------------------------------------------------------------
    iter1_dir = OUTPUT_ROOT / "iteration_01"
    iter1_file = iter1_dir / "closed_loop_iteration.json"
    if iter1_file.exists():
        print("\n--- [Iteration 01: Loading existing completed results] ---")
        iter1_data = json.loads(iter1_file.read_text(encoding="utf-8"))
        best_body_overrides = iter1_data["overrides"]
        current_cfg = apply_ferrari_parameters(current_cfg, best_body_overrides)
        iter1_eval = evaluate_candidate(current_cfg, references, eval_duration_s=2.0)
        print(f"Iteration 01 Loaded! Median Distance: {iter1_eval['median_distance']:.4f}")
    else:
        print("\n--- [Iteration 01: Body & Combustion Parameter Tuning] ---")
        body_params = [p for p in FERRARI_SEARCH_PARAMETERS if p.family == "body"]
        print(f"Tuning {len(body_params)} body parameters: {[p.name for p in body_params]}")
        
        # Sobol sampling
        sobol = qmc.Sobol(d=len(body_params), seed=20260905)
        sample_points = sobol.random(n=32)
        
        best_body_overrides = {}
        best_body_dist = base_eval["median_distance"]
        best_body_cfg = copy.deepcopy(current_cfg)
        
        for idx, pt in enumerate(sample_points):
            overrides = {}
            for p, unit_val in zip(body_params, pt):
                val = p.min_val + unit_val * (p.max_val - p.min_val)
                overrides[p.name] = float(val)
            
            test_cfg = apply_ferrari_parameters(current_cfg, overrides)
            res = evaluate_candidate(test_cfg, references, eval_duration_s=1.5, eval_scenes=["hot_idle", "steady_mid", "full_pull"])
            
            if res["passed_gates"] and res["median_distance"] < best_body_dist:
                gain = best_body_dist - res["median_distance"]
                best_body_dist = res["median_distance"]
                best_body_overrides = overrides
                best_body_cfg = copy.deepcopy(test_cfg)
                print(f"  [Sample {idx+1:02d}/32] New best distance: {best_body_dist:.4f} (gain: +{gain:.4f})")
        
        # Local refinement around best
        print("Refining around best body parameters...")
        for step in range(12):
            overrides = {}
            for p in body_params:
                center = best_body_overrides.get(p.name, p.baseline)
                delta = (p.max_val - p.min_val) * 0.15
                val = np.clip(center + np.random.uniform(-delta, delta), p.min_val, p.max_val)
                overrides[p.name] = float(val)
                
            test_cfg = apply_ferrari_parameters(current_cfg, overrides)
            res = evaluate_candidate(test_cfg, references, eval_duration_s=1.5, eval_scenes=["hot_idle", "steady_mid", "full_pull"])
            if res["passed_gates"] and res["median_distance"] < best_body_dist:
                gain = best_body_dist - res["median_distance"]
                best_body_dist = res["median_distance"]
                best_body_overrides = overrides
                best_body_cfg = copy.deepcopy(test_cfg)
                print(f"  [Refine {step+1:02d}/12] Improved distance: {best_body_dist:.4f} (gain: +{gain:.4f})")
        
        current_cfg = copy.deepcopy(best_body_cfg)
        iter1_eval = evaluate_candidate(current_cfg, references, eval_duration_s=2.0)
        print(f"Iteration 01 Complete! Full Median Distance: {iter1_eval['median_distance']:.4f}")
        
        iter1_dir.mkdir(parents=True, exist_ok=True)
        with open(iter1_dir / "closed_loop_iteration.json", "w", encoding="utf-8") as f:
            json.dump({
                "iteration": 1,
                "stage": "body_combustion",
                "median_distance": iter1_eval["median_distance"],
                "distance_gain": base_eval["median_distance"] - iter1_eval["median_distance"],
                "overrides": best_body_overrides,
                "scene_results": iter1_eval["scene_results"],
            }, f, indent=2)

    # -------------------------------------------------------------
    # Iteration 02: Resonator & Exhaust Tuning
    # -------------------------------------------------------------
    print("\n--- [Iteration 02: Exhaust & Resonator Parameter Tuning] ---")
    exhaust_params = [p for p in FERRARI_SEARCH_PARAMETERS if p.family in ("exhaust", "afterfire")]
    print(f"Tuning {len(exhaust_params)} exhaust/resonator parameters: {[p.name for p in exhaust_params]}")
    
    sobol_ex = qmc.Sobol(d=len(exhaust_params), seed=20260906)
    sample_points_ex = sobol_ex.random(n=32)
    
    best_ex_overrides = {}
    best_ex_dist = iter1_eval["median_distance"]
    best_ex_cfg = copy.deepcopy(current_cfg)
    
    for idx, pt in enumerate(sample_points_ex):
        overrides = {}
        for p, unit_val in zip(exhaust_params, pt):
            val = p.min_val + unit_val * (p.max_val - p.min_val)
            overrides[p.name] = float(val)
        
        test_cfg = apply_ferrari_parameters(current_cfg, overrides)
        res = evaluate_candidate(test_cfg, references, eval_duration_s=1.5, eval_scenes=["steady_high", "full_pull", "afterfire"])
        
        if res["passed_gates"] and res["median_distance"] < best_ex_dist:
            gain = best_ex_dist - res["median_distance"]
            best_ex_dist = res["median_distance"]
            best_ex_overrides = overrides
            best_ex_cfg = copy.deepcopy(test_cfg)
            print(f"  [Sample {idx+1:02d}/32] New best distance: {best_ex_dist:.4f} (gain: +{gain:.4f})")
    
    current_cfg = copy.deepcopy(best_ex_cfg)
    final_eval = evaluate_candidate(current_cfg, references, eval_duration_s=2.0)
    print(f"\nIteration 02 Complete! Final Median Distance: {final_eval['median_distance']:.4f}")
    
    total_gain = base_eval["median_distance"] - final_eval["median_distance"]
    print(f"Total Closed-Loop Distance Improvement: {base_eval['median_distance']:.4f} -> {final_eval['median_distance']:.4f} (Gain: +{total_gain:.4f})")
    
    all_overrides = {**best_body_overrides, **best_ex_overrides}
    
    # Save final summary
    summary = {
        "schema": "s12.stage_ad.closed_loop_summary.v2",
        "vehicle_id": "ferrari_458_v1",
        "iteration_count": 2,
        "initial_distance": base_eval["median_distance"],
        "final_absolute_reference_distance": final_eval["median_distance"],
        "total_distance_gain": total_gain,
        "final_overrides": all_overrides,
        "final_config_sha256": hashlib.sha256(json.dumps(current_cfg, sort_keys=True).encode()).hexdigest(),
        "final_scene_results": final_eval["scene_results"],
        "passed_all_gates": final_eval["passed_gates"],
    }
    
    summary_path = OUTPUT_ROOT / "closed_loop_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten summary: {summary_path}")
    
    final_cfg_path = OUTPUT_ROOT / "final_calibrated_config.json"
    final_cfg_path.write_text(json.dumps(current_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written final calibrated config: {final_cfg_path}")
    
    # -------------------------------------------------------------
    # Render all 10 candidate WAVs for Audition Package
    # -------------------------------------------------------------
    print("\n--- [Rendering 10 Full Candidate WAVs for Ferrari 458 Package] ---")
    manifest_files = []
    
    scene_file_map = [
        ("01_afterfire.wav", "afterfire", 3.5),
        ("02_full_pull.wav", "full_pull", 3.5),
        ("03_hot_idle.wav", "hot_idle", 3.0),
        ("04_idle_return.wav", "idle_return", 3.0),
        ("05_lift.wav", "lift", 3.5),
        ("06_shift.wav", "shift", 3.0),
        ("07_steady_high.wav", "steady_high", 3.0),
        ("08_steady_low.wav", "steady_low", 3.0),
        ("09_steady_mid.wav", "steady_mid", 3.0),
        ("10_tip_in.wav", "tip_in", 3.0),
    ]
    
    for idx, (fname, scen, dur) in enumerate(scene_file_map, 1):
        print(f"Rendering [{idx:02d}/10] {fname} ({scen}, {dur}s)...")
        pcm, _ = render_ferrari_scene(current_cfg, scen, dur)
        pcm16 = np.clip(np.round(pcm * 32767.0), -32768, 32767).astype(np.int16)
        
        # Write to web_audio
        dst_web = WEB_AUDIO_DIR / fname
        with wave.open(str(dst_web), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE_HZ)
            wf.writeframes(pcm16.tobytes())
            
        # Also copy to package root
        shutil.copy2(dst_web, PACKAGE_DIR / fname)
        
        sha = hashlib.sha256(dst_web.read_bytes()).hexdigest()
        rms = np.sqrt(np.mean(np.square(pcm)))
        peak = np.max(np.abs(pcm))
        print(f"  ✓ {fname}: size={dst_web.stat().st_size // 1024} KB, rms={rms:.4f} (-{20*np.log10(1/rms):.1f} dBFS), peak={peak:.4f}, sha={sha[:12]}")
        
        manifest_files.append({
            "index": idx,
            "scene": scen,
            "file": fname,
            "sha256": sha,
            "rms": float(rms),
            "peak": float(peak)
        })
        
    audition_manifest = {
        "schema": "s12.stage_ad.audition_package.v2",
        "vehicle": "Ferrari 458 Italia (4.5L Flat-Plane V8, 570 HP @ 9000 RPM)",
        "calibration_target": "authentic_autotopnl_youtube_ferrari_458",
        "source_loop_root": str(OUTPUT_ROOT),
        "source_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "final_iteration": 2,
        "final_objective": -final_eval["median_distance"],
        "final_absolute_reference_distance": final_eval["median_distance"],
        "final_config_sha256": summary["final_config_sha256"],
        "files": manifest_files,
        "blind": False,
        "official_v3_modified": False,
        "instruction": "Listen to monitor WAVs calibrated directly on authentic Ferrari 458 Italia video.",
    }
    
    audition_manifest_path = PACKAGE_DIR / "audition_manifest.json"
    audition_manifest_path.write_text(json.dumps(audition_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten audition manifest: {audition_manifest_path}")
    print("Ferrari 458 Stage AD Closed-Loop Calibration Complete!")

if __name__ == "__main__":
    run_ferrari_closed_loop()
