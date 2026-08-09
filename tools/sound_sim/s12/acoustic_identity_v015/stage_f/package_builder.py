"""Deterministic Stage-F listener-package builder."""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _write_pcm24_wav
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _render_stateful
from ..stage_d.scenarios import SCENES, build_stage_d_scenario_trace
from .candidate_profiles import load_stage_f_candidate
from .render_candidate import render_stage_f_candidate

VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
PACKAGE_ID = "S12_Blind_Audition_Package_v3"
SHORT_SCENES = SCENES
BLIND_FIELDS = ("package_id", "listener_id", "round_id", "trial_id", "guessed_vehicle_id", "confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5", "notes")
AB_FIELDS = ("package_id", "listener_id", "pair_id", "preferred_option", "low_frequency_naturalness_1_5", "afterfire_naturalness_1_5", "artifact_blocker", "notes")


def build_stage_f_package(output_root: str | Path, candidate_paths: dict[str, str | Path] | None = None, seed: int = 20260810, duration_s: float = 60.0) -> dict[str, object]:
    root = Path(output_root).resolve()
    # The package root is dedicated to this package ID. Re-running after a
    # killed build is allowed and deterministically overwrites the generated
    # members, so a partial local build cannot block recovery.
    root.mkdir(parents=True, exist_ok=True)
    listener = root / "listener"; sealed = root / "sealed"; evidence = root / "source_evidence"; candidates_root = root / "candidates"; reference = root / "reference_distance"; results = root / "results"
    for path in (listener, sealed, evidence, candidates_root, reference, results): path.mkdir(parents=True, exist_ok=True)
    (listener / "round_1").mkdir(exist_ok=True); (listener / "round_2").mkdir(exist_ok=True); pairs_root = listener / "qualitative_full_cycle_pairs"; pairs_root.mkdir(exist_ok=True)
    if candidate_paths is None:
        repo_root = Path(__file__).resolve().parents[1]
        candidate_paths = {v: repo_root / "targets" / "stage_f_candidates" / filename for v, filename in (("ferrari_458", "Ferrari_candidate_v3.json"), ("hellcat", "Hellcat_candidate_v3.json"), ("rx7_fd", "RX7_candidate_v3.json"))}
    candidates = {vehicle: load_stage_f_candidate(path) for vehicle, path in candidate_paths.items()}
    for vehicle, candidate in candidates.items():
        (candidates_root / f"{vehicle}_candidate_v3.json").write_text(json.dumps(candidate.payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    roles = ["baseline", "candidate"]
    if int(rng.integers(0, 2)): roles.reverse()
    audio_cache: dict[tuple[str, str, str], np.ndarray] = {}
    render_cache: dict[tuple[str, str, str, float], np.ndarray] = {}
    full_cycle_mode = float(duration_s) >= 60.0
    # The normal v3 package uses explicit 8-second scene traces and one
    # continuous canonical 60-second trace for each A/B pair. Short durations
    # remain available for fast contract tests and use the compact sweep.
    short_duration_s = 8.0 if full_cycle_mode else max(float(duration_s), 0.10)
    for role in roles:
        for vehicle in VEHICLES:
            for scene in SHORT_SCENES:
                trace = _build_trace(vehicle, scene, short_duration_s)
                cache_key = (role, vehicle, scene, float(short_duration_s))
                if cache_key not in render_cache:
                    render_cache[cache_key] = _render_final(vehicle, trace, role, candidates)
                audio_cache[(role, vehicle, scene)] = render_cache[cache_key]
    targets = {}
    for scene in SHORT_SCENES:
        levels = [measure_loudness(audio_cache[(role, vehicle, scene)]).integrated_lufs for role in roles for vehicle in VEHICLES]
        targets[scene] = min(-20.0, min(levels))
    answer_trials: dict[str, dict[str, str]] = {}; public_trials = []
    for round_index, role in enumerate(roles, 1):
        entries = [(vehicle, scene) for vehicle in VEHICLES for scene in SHORT_SCENES]
        order = rng.permutation(len(entries))
        for trial_index, selected in enumerate(order, 1):
            vehicle, scene = entries[int(selected)]
            trial_id = f"R{round_index}_T{trial_index:02d}"
            audio = _fit_audio(_attenuate(audio_cache[(role, vehicle, scene)], targets[scene]), int(round(8.0 * _SAMPLE_RATE_HZ)))
            _write_pcm24_wav(listener / f"round_{round_index}" / f"{trial_id}.wav", audio)
            answer_trials[trial_id] = {"vehicle_id": vehicle, "scene_id": scene, "role": role}
            public_trials.append({"round_id": round_index, "trial_id": trial_id, "scene_id": scene})
    pair_key: dict[str, dict[str, str]] = {}
    for index, vehicle in enumerate(VEHICLES, 1):
        if full_cycle_mode:
            cycle_trace = build_drive_cycle_trace(vehicle, duration_s)
            baseline = _render_final(vehicle, cycle_trace, "baseline", candidates)
            candidate = _render_final(vehicle, cycle_trace, "candidate", candidates)
        else:
            baseline_parts = []; candidate_parts = []
            for scene, seconds in _cycle_lengths(duration_s):
                for role, parts in (("baseline", baseline_parts), ("candidate", candidate_parts)):
                    base_audio = audio_cache[(role, vehicle, "acceleration" if scene == "full_pull" else scene)]
                    parts.append(_fit_audio(base_audio, int(round(seconds * _SAMPLE_RATE_HZ))))
            baseline = np.concatenate(baseline_parts, axis=0); candidate = np.concatenate(candidate_parts, axis=0)
        target = min(-20.0, measure_loudness(baseline).integrated_lufs, measure_loudness(candidate).integrated_lufs)
        baseline = _attenuate(baseline, target); candidate = _attenuate(candidate, target)
        options = [("A", baseline), ("B", candidate)]
        if int(rng.integers(0, 2)): options.reverse()
        pair_id = f"P{index:02d}"
        pair_key[pair_id] = {"vehicle_id": vehicle, "A_role": "baseline" if options[0][1] is baseline else "candidate", "B_role": "baseline" if options[1][1] is baseline else "candidate"}
        for option, audio in options:
            _write_pcm24_wav(pairs_root / f"{pair_id}_{option}.wav", audio)
    manifest = {"package_id": PACKAGE_ID, "trial_count": 30, "scenes": list(SCENES), "trials": public_trials, "render_base_duration_s": short_duration_s, "full_cycle_trace": "build_drive_cycle_trace v10" if full_cycle_mode else "compact contract sweep", "audio_policy": {"attenuation_only": True, "scene_lufs_spread_max": 0.10, "peak_dbfs_max": -1.5}}
    (listener / "listener_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_blind_template(listener / "blind_responses.csv", public_trials)
    _write_ab_template(listener / "ab_responses.csv", pair_key)
    (listener / "playback_context.json").write_text(json.dumps({"package_id": PACKAGE_ID, "listener_id": "jovi", "playback_device": "", "headphones_or_speakers": "", "windows_volume_percent": 40, "player": "", "eq_enabled": False, "spatial_audio_enabled": False, "environment": "", "start_time": "", "completion_time": ""}, indent=2), encoding="utf-8")
    (listener / "README.md").write_text("匿名 Stage-F 双轮盲听包。先填写 blind_responses.csv、ab_responses.csv 和 playback_context.json，再交回评分。不要查看 sealed 目录。\n", encoding="utf-8")
    (sealed / "answer_key.json").write_text(json.dumps({"package_id": PACKAGE_ID, "seed": int(seed), "round_role": {"round_1": roles[0], "round_2": roles[1]}, "trials": answer_trials}, indent=2), encoding="utf-8")
    (sealed / "pair_key.json").write_text(json.dumps({"package_id": PACKAGE_ID, "pairs": pair_key}, indent=2), encoding="utf-8")
    (sealed / "source_provenance.json").write_text(json.dumps({"provenance": "C/synthetic; B/R2 relative feature context only; uncalibrated; not OEM reproduction", "candidate_sha256": {v: _sha256(Path(p)) for v, p in candidate_paths.items()}}, indent=2), encoding="utf-8")
    (sealed / "scoring_contract.json").write_text(json.dumps({"labels_actual": list(VEHICLES), "labels_predicted": [*VEHICLES, "unsure"], "rounds": 2, "trials_per_round": 15, "trials_per_vehicle_per_round": 5, "candidate_gates": {"overall_min_correct": 12, "per_vehicle_min_correct": 4, "confidence_median_min": 3, "realism_mean_min": 4, "artifact_freedom_min": 3}}, indent=2), encoding="utf-8")
    (reference / "README.md").write_text("Reference-distance is measured in the final PCM domain. Missing or below-threshold comparisons remain PARTIAL.\n", encoding="utf-8")
    (results / "README.md").write_text("No listener result exists until Jovi returns completed forms.\n", encoding="utf-8")
    listener_zip = root / "S12_Stage_F_Listener_Package.zip"; answer_zip = root / "S12_Stage_F_Answer_Key.zip"
    _zip_tree(listener_zip, listener, "listener"); _zip_tree(answer_zip, sealed, "sealed")
    sums = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt": sums[str(path.relative_to(root)).replace("\\", "/")] = _sha256(path)
    (root / "SHA256SUMS.txt").write_text("\n".join(f"{digest}  {path}" for path, digest in sorted(sums.items())) + "\n", encoding="utf-8")
    return {"package_id": PACKAGE_ID, "output_root": str(root), "trial_count": 30, "full_cycle_pair_count": 3, "status": "WAITING_FOR_JOVI_AUDITION", "listener_zip": str(listener_zip), "answer_key_zip": str(answer_zip)}


def _render_final(vehicle: str, trace, role: str, candidates):
    rendered = _render_stateful(_RENDERERS[vehicle], vehicle, trace) if role == "baseline" else render_stage_f_candidate(vehicle, trace, candidates[vehicle])
    return _edge_fade(_apply_frozen_ptr(rendered.pressure))


def _build_trace(vehicle: str, scene: str, duration_s: float):
    scenario_scene = "acceleration" if scene == "full_pull" else scene
    if duration_s >= 2.0:
        return build_stage_d_scenario_trace(vehicle, scenario_scene, duration_s=duration_s)
    base = build_stage_d_scenario_trace(vehicle, scenario_scene, duration_s=2.0)
    count = max(int(round(duration_s * _SAMPLE_RATE_HZ)) + 1, 2)
    from ..contracts import VehicleStateTrace
    return VehicleStateTrace(*(getattr(base, name)[:count] for name in ("time_s", "rpm", "load", "throttle", "acceleration_mps2"))).validate()


def _attenuate(audio: np.ndarray, target_lufs: float) -> np.ndarray:
    measured = measure_loudness(audio).integrated_lufs
    gain_db = min(0.0, float(target_lufs) - float(measured))
    return np.asarray(audio, dtype=np.float64) * (10.0 ** (gain_db / 20.0))


def _fit_audio(audio: np.ndarray, samples: int) -> np.ndarray:
    if samples <= 0:
        raise ValueError("audio segment length must be positive")
    if audio.shape[0] == samples:
        return np.array(audio, dtype=np.float64, copy=True)
    repeats = int(np.ceil(samples / audio.shape[0]))
    return np.tile(audio, (repeats, 1))[:samples].copy()


def _cycle_lengths(duration_s: float):
    if abs(float(duration_s) - 60.0) < 1e-9:
        return (("idle", 8.0), ("acceleration", 18.0), ("full_pull", 10.0), ("lift", 10.0), ("cruise", 6.0), ("idle", 8.0))
    each = max(float(duration_s) / 6.0, 0.10)
    return tuple((scene, each) for scene in ("idle", "acceleration", "full_pull", "lift", "cruise", "idle"))


def _write_blind_template(path: Path, trials):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=BLIND_FIELDS); writer.writeheader()
        for trial in trials:
            writer.writerow({"package_id": PACKAGE_ID, "listener_id": "jovi", "round_id": trial["round_id"], "trial_id": trial["trial_id"], "guessed_vehicle_id": "", "confidence_1_5": "", "identity_strength_1_5": "", "realism_1_5": "", "artifact_freedom_1_5": "", "notes": ""})


def _write_ab_template(path: Path, pair_key):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=AB_FIELDS); writer.writeheader()
        for pair_id in sorted(pair_key):
            writer.writerow({"package_id": PACKAGE_ID, "listener_id": "jovi", "pair_id": pair_id, "preferred_option": "", "low_frequency_naturalness_1_5": "", "afterfire_naturalness_1_5": "", "artifact_blocker": "", "notes": ""})


def _zip_tree(output: Path, root: Path, prefix: str):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file(): continue
            info = zipfile.ZipInfo(f"{prefix}/{path.relative_to(root).as_posix()}"); info.date_time = (2020, 1, 1, 0, 0, 0); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
