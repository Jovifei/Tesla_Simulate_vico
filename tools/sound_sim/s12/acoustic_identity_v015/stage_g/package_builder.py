"""Deterministic anonymous Stage-G v4 listener and A/B package builder."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip, _write_pcm24_wav
from ..render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _render_stateful
from ..stage_d.scenarios import SCENES, build_stage_d_scenario_trace
from .candidate_profiles import ANCHOR_IDS, StageGCandidateProfile, load_stage_g_candidate
from .render_candidate import render_stage_g_candidate
from .response_contract import AB_FIELDS, BLIND_FIELDS, PACKAGE_ID

VEHICLES = ANCHOR_IDS
DEFAULT_SEED = 0x5331325F53544147455F475F56345F31


def build_stage_g_package(
    output_root: str | Path,
    candidate_paths: dict[str, str | Path] | None = None,
    seed: int = DEFAULT_SEED,
    duration_s: float = 60.0,
    automatic_status: str = "WAITING_FOR_JOVI_AUDITION",
) -> dict[str, object]:
    root = Path(output_root).resolve(); listener = root / "listener"; sealed = root / "sealed"; source_evidence = root / "source_evidence"; candidates_root = root / "candidates"; reference = root / "reference_distance"; results = root / "results"
    for path in (listener, sealed, source_evidence, candidates_root, reference, results): path.mkdir(parents=True, exist_ok=True)
    (listener / "round_1").mkdir(parents=True, exist_ok=True); (listener / "round_2").mkdir(parents=True, exist_ok=True); pairs_root = listener / "qualitative_full_cycle_pairs"; pairs_root.mkdir(parents=True, exist_ok=True)
    if candidate_paths is None:
        candidate_root = Path(__file__).resolve().parents[1] / "targets" / "stage_g_candidates"
        candidate_paths = {"ferrari_458": candidate_root / "Ferrari_candidate_v4.json", "hellcat": candidate_root / "Hellcat_candidate_v4.json", "rx7_fd": candidate_root / "RX7_candidate_v4.json"}
    candidates = {vehicle: load_stage_g_candidate(candidate_paths[vehicle]) for vehicle in VEHICLES}
    for vehicle, candidate in candidates.items():
        (candidates_root / f"{vehicle}_candidate_v4.json").write_text(json.dumps(candidate.payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    roles = ["baseline", "candidate"]
    if int(rng.integers(0, 2)): roles.reverse()
    # Keep the formal listener clips at eight seconds.  Test callers may use
    # a shorter cycle explicitly; honoring that bounded duration keeps the
    # contract tests fast without changing the published 60-second package.
    short_duration = 8.0 if float(duration_s) >= 8.0 else max(2.0, float(duration_s))
    short_audio: dict[tuple[str, str, str], np.ndarray] = {}
    short_traces: dict[tuple[str, str], object] = {}
    for vehicle in VEHICLES:
        for scene in SCENES:
            trace = build_stage_d_scenario_trace(vehicle, scene, duration_s=short_duration)
            short_traces[(vehicle, scene)] = trace
            for role in roles:
                short_audio[(role, vehicle, scene)] = _render_final(vehicle, trace, role, candidates)
    targets = {scene: min(-20.0, *(measure_loudness(short_audio[(role, vehicle, scene)]).integrated_lufs for role in roles for vehicle in VEHICLES)) for scene in SCENES}
    answer_trials: dict[str, dict[str, str]] = {}; public_trials: list[dict[str, object]] = []
    for round_index, role in enumerate(roles, 1):
        entries = [(vehicle, scene) for vehicle in VEHICLES for scene in SCENES]
        order = rng.permutation(len(entries))
        for trial_index, selected in enumerate(order, 1):
            vehicle, scene = entries[int(selected)]; trial_id = f"R{round_index}_T{trial_index:02d}"
            audio = _attenuate(short_audio[(role, vehicle, scene)], targets[scene])
            _write_pcm24_wav(listener / f"round_{round_index}" / f"{trial_id}.wav", audio)
            answer_trials[trial_id] = {"vehicle_id": vehicle, "scene_id": scene, "role": role}; public_trials.append({"round_id": round_index, "trial_id": trial_id, "scene_id": scene})
    pair_key: dict[str, dict[str, str]] = {}
    for index, vehicle in enumerate(VEHICLES, 1):
        trace = build_drive_cycle_trace(vehicle, duration_s=duration_s)
        # G2 already produced labelled, PCM24 final-domain evidence from this
        # exact canonical trace. Reuse those bytes for the anonymous A/B pair
        # when available; this keeps the pair bit-identical to the audited
        # evidence and avoids a second multi-minute long-cycle render.
        evidence_root = root / "source_evidence" / "reference_pcm" / vehicle
        baseline_path = evidence_root / "stage_c" / "full_cycle.wav"
        candidate_path = evidence_root / "stage_g" / "full_cycle.wav"
        if float(duration_s) == 60.0 and baseline_path.is_file() and candidate_path.is_file():
            from ..render_identity_v02 import _read_pcm24_wav
            baseline = _read_pcm24_wav(baseline_path); candidate = _read_pcm24_wav(candidate_path)
        else:
            baseline = _render_final(vehicle, trace, "baseline", candidates); candidate = _render_final(vehicle, trace, "candidate", candidates)
        target = min(-20.0, measure_loudness(baseline).integrated_lufs, measure_loudness(candidate).integrated_lufs)
        options: list[tuple[str, str, np.ndarray]] = [("A", "baseline", _attenuate(baseline, target)), ("B", "candidate", _attenuate(candidate, target))]
        if int(rng.integers(0, 2)): options.reverse()
        pair_id = f"P{index:02d}"; pair_key[pair_id] = {f"{option}_role": role for option, role, _ in options}
        for option, _, audio in options: _write_pcm24_wav(pairs_root / f"{pair_id}_{option}.wav", audio)
    # Keep the public listener manifest anonymous: the sealed answer key owns
    # the vehicle mapping.  The closed-set labels are supplied separately in
    # the scoring instructions, never as a trial-to-vehicle leak.
    manifest = {"package_id": PACKAGE_ID, "schema_version": "s12-stage-g-listener-manifest-1", "trial_count": 30, "rounds": 2, "trials_per_round": 15, "scenes": list(SCENES), "trials": public_trials, "audio_policy": {"attenuation_only": True, "shared_scene_target_lufs": targets, "peak_dbfs_max": -1.5, "edge_fade_ms": 20, "no_compressor_limiter_eq": True}, "provenance": "synthetic; uncalibrated; not OEM reproduction"}
    (listener / "listener_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    _write_blind_template(listener / "blind_responses.csv", public_trials); _write_ab_template(listener / "ab_responses.csv")
    (listener / "playback_context.json").write_text(json.dumps({"package_id": PACKAGE_ID, "listener_id": "jovi", "playback_device": "", "headphones_or_speakers": "", "windows_volume_percent": 40, "player": "", "eq_enabled": False, "spatial_audio_enabled": False, "environment": "", "start_time": "", "completion_time": ""}, indent=2) + "\n", encoding="utf-8", newline="\n")
    (listener / "README.md").write_text("匿名 Stage-G v4 双轮盲听包。请先填写 blind_responses.csv、ab_responses.csv 和 playback_context.json，再把三份文件交回。不要查看 sealed 目录。\n", encoding="utf-8", newline="\n")
    (listener / "README.md").write_text("Anonymous Stage-G v4 two-round listening package. Fill blind_responses.csv, ab_responses.csv, and playback_context.json after listening. Do not inspect the private answer files.\n", encoding="utf-8", newline="\n")
    (sealed / "answer_key.json").write_text(json.dumps({"package_id": PACKAGE_ID, "seed": hex(int(seed)), "round_role": {"round_1": roles[0], "round_2": roles[1]}, "trials": answer_trials}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (sealed / "pair_key.json").write_text(json.dumps({"package_id": PACKAGE_ID, "pairs": pair_key}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (sealed / "source_provenance.json").write_text(json.dumps({"package_id": PACKAGE_ID, "candidate_sha256": {v: _sha256(Path(candidate_paths[v])) for v in VEHICLES}, "base_commit": "e38fe62f423b1fb220e9daedf5f4ef291bcc5849", "provenance": "C/synthetic; B/R2 relative target context only; uncalibrated; not OEM reproduction"}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (sealed / "scoring_contract.json").write_text(json.dumps({"package_id": PACKAGE_ID, "labels_actual": list(VEHICLES), "labels_predicted": [*VEHICLES, "unsure"], "rounds": 2, "trials_per_round": 15, "trials_per_vehicle_per_round": 5, "candidate_gates": {"overall_min_correct": 12, "per_vehicle_min_correct": 4, "directed_confusion_max": 1, "confidence_median_min": 3, "realism_mean_min": 4, "artifact_freedom_min": 3, "ab": "candidate better/equal with no blocker"}}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (reference / "distance_contract.json").write_text(json.dumps({"domain": "final_pcm", "eligible_states": ["idle", "acceleration", "afterfire"], "bands_hz": [[20, 250], [250, 1000], [1000, 4000], [4000, 12000]], "formula": "sqrt(0.25 * sum((actual-target)^2))", "missing_reference_policy": "N/A; never zero-fill", "status": "measured separately by compute_stage_g_reference_evidence.py"}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (results / "status.json").write_text(json.dumps({"package_id": PACKAGE_ID, "status": automatic_status, "human_status": "WAITING_FOR_JOVI_AUDITION", "sealed_key_read": False, "provenance": "synthetic; uncalibrated; not OEM reproduction"}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    listener_zip = root / "S12_Stage_G_Listener_Package.zip"; answer_zip = root / "S12_Stage_G_Answer_Key.zip"; _zip_tree(listener_zip, listener, "listener"); _zip_tree(answer_zip, sealed, "sealed")
    sums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt": sums[path.relative_to(root).as_posix()] = _sha256(path)
    (root / "SHA256SUMS.txt").write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(sums.items())), encoding="utf-8", newline="\n")
    return {"package_id": PACKAGE_ID, "output_root": str(root), "trial_count": 30, "full_cycle_pair_count": 3, "status": automatic_status, "human_status": "WAITING_FOR_JOVI_AUDITION", "listener_zip": str(listener_zip), "answer_key_zip": str(answer_zip), "seed": hex(int(seed))}


def _render_final(vehicle: str, trace, role: str, candidates: Mapping[str, StageGCandidateProfile]) -> np.ndarray:
    source = _render_stateful(_RENDERERS[vehicle], vehicle, trace) if role == "baseline" else render_stage_g_candidate(vehicle, trace, candidates[vehicle])
    return _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(source.pressure)))


def _attenuate(audio: np.ndarray, target_lufs: float) -> np.ndarray:
    measured = measure_loudness(audio).integrated_lufs; gain_db = min(0.0, float(target_lufs) - float(measured)); return np.asarray(audio, dtype=np.float64) * (10.0 ** (gain_db / 20.0))


def _write_blind_template(path: Path, trials: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=BLIND_FIELDS); writer.writeheader()
        for trial in trials: writer.writerow({"package_id": PACKAGE_ID, "listener_id": "jovi", "round_id": trial["round_id"], "trial_id": trial["trial_id"], "guessed_vehicle_id": "", "confidence_1_5": "", "identity_strength_1_5": "", "realism_1_5": "", "artifact_freedom_1_5": "", "notes": ""})


def _write_ab_template(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=AB_FIELDS); writer.writeheader()
        for index in range(1, 4): writer.writerow({"package_id": PACKAGE_ID, "listener_id": "jovi", "pair_id": f"P{index:02d}", "preferred_option": "", "low_frequency_naturalness_1_5": "", "afterfire_naturalness_1_5": "", "artifact_blocker": "", "notes": ""})


def _zip_tree(output: Path, root: Path, prefix: str) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file(): continue
            info = zipfile.ZipInfo(f"{prefix}/{path.relative_to(root).as_posix()}"); info.date_time = (2020, 1, 1, 0, 0, 0); info.compress_type = zipfile.ZIP_DEFLATED; archive.writestr(info, path.read_bytes())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ("DEFAULT_SEED", "PACKAGE_ID", "VEHICLES", "build_stage_g_package")
