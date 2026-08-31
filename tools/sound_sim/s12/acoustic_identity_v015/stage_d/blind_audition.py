"""Deterministic, sealed two-round blind audition package and scorer."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import zipfile

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _read_pcm24_wav, _write_pcm24_wav

_VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
_GUESSES = set(_VEHICLES) | {"unsure"}
_SCENES = ("idle", "cruise", "acceleration", "shift", "lift")
_RESPONSE_FIELDS = ("trial_id", "guessed_vehicle_id", "confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5", "notes")


def build_blind_package(
    source_root: str | Path,
    source_manifest: str | Path,
    output_root: str | Path,
    seed: int | None = None,
    loudness_ceiling_lufs: float = -20.0,
) -> dict[str, object]:
    source_root = Path(source_root).resolve()
    manifest_path = Path(source_manifest).resolve()
    output_root = Path(output_root).resolve()
    if output_root.exists():
        unexpected = [item.name for item in output_root.iterdir() if item.name != "source_evidence"]
        if unexpected:
            raise ValueError("blind package output_root must be empty except for source_evidence")
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        raise ValueError("source manifest must contain non-empty trials")
    _validate_source_trials(trials, source_root)
    scene_lufs: dict[str, list[float]] = {scene: [] for scene in _SCENES}
    source_audio: dict[str, np.ndarray] = {}
    for trial in trials:
        trial_key = str(trial["wav"])
        audio = _read_pcm24_wav((source_root / trial_key).resolve())
        source_audio[trial_key] = audio
        scene_lufs[str(trial["scene_id"])].append(float(measure_loudness(audio).integrated_lufs))
    scene_targets = {scene: min(float(loudness_ceiling_lufs), min(values)) for scene, values in scene_lufs.items() if values}
    output_root.mkdir(parents=True, exist_ok=True)
    listener_root = output_root / "listener"
    sealed_root = output_root / "sealed"
    results_root = output_root / "results"
    for path in (listener_root, sealed_root, results_root):
        path.mkdir(parents=True)
    generator = np.random.Generator(np.random.PCG64(seed if seed is not None else secrets.randbits(128)))
    role_order = ["baseline", "candidate"]
    if bool(generator.integers(0, 2)):
        role_order.reverse()
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for trial in trials:
        grouped.setdefault((str(trial["role"]), str(trial["scene_id"])), []).append(trial)
    answer_trials: dict[str, dict[str, object]] = {}
    public_trials: list[dict[str, object]] = []
    trial_number = 1
    for round_id, role in enumerate(role_order, start=1):
        round_root = listener_root / f"round_{round_id}"
        round_root.mkdir()
        selected = [item for item in trials if item["role"] == role]
        selected.sort(key=lambda item: (str(item["scene_id"]), str(item["vehicle_id"])))
        permutation = generator.permutation(len(selected))
        for index in permutation:
            trial = selected[int(index)]
            trial_id = f"R{round_id}_T{trial_number:02d}"
            trial_number += 1
            source_path = (source_root / str(trial["wav"])).resolve()
            audio = source_audio[str(trial["wav"])].copy()
            input_lufs = float(measure_loudness(audio).integrated_lufs)
            target_lufs = scene_targets[str(trial["scene_id"])]
            gain_db = min(0.0, target_lufs - input_lufs)
            audio *= 10.0 ** (gain_db / 20.0)
            output_path = round_root / f"{trial_id}.wav"
            _write_pcm24_wav(output_path, audio)
            answer_trials[trial_id] = {"vehicle_id": trial["vehicle_id"], "scene_id": trial["scene_id"], "role": role}
            public_trials.append({"trial_id": trial_id, "round_id": round_id, "scene_id": trial["scene_id"]})
    answer_key = {"package_id": "S12_Blind_Audition_Package_v1", "seed": int(seed) if seed is not None else None, "round_role": {"round_1": role_order[0], "round_2": role_order[1]}, "trials": answer_trials}
    key_path = sealed_root / "answer_key.json"
    key_path.write_text(json.dumps(answer_key, ensure_ascii=False, indent=2), encoding="utf-8")
    listener_manifest = {"package_id": "S12_Blind_Audition_Package_v1", "trial_count": len(public_trials), "trials": public_trials, "answer_key_sha256": _sha256(key_path)}
    (listener_root / "listener_manifest.json").write_text(json.dumps(listener_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_response_template(listener_root / "responses_template.csv")
    (listener_root / "playback_context_template.json").write_text(json.dumps({"package_id": listener_manifest["package_id"], "listener_id": "jovi", "output_type": "headphones|speakers", "windows_volume_percent": 40, "eq_enabled": False, "spatial_audio_enabled": False, "environment": "quiet"}, indent=2), encoding="utf-8")
    (sealed_root / "source_provenance.json").write_text(json.dumps({"source_root": str(source_root), "source_manifest_sha256": _sha256(manifest_path), "provenance": "C/synthetic; B/R2 relative reference only; uncalibrated; not OEM reproduction"}, indent=2), encoding="utf-8")
    (sealed_root / "scoring_contract.json").write_text(json.dumps({"labels_actual": list(_VEHICLES), "labels_predicted": [*_VEHICLES, "unsure"], "minimum_accuracy": 0.80, "minimum_recall": 0.80}, indent=2), encoding="utf-8")
    (results_root / "README.md").write_text("Submit the completed response CSV and playback context here. The sealed key is intentionally separate.\n", encoding="utf-8")
    listener_zip = output_root / "S12_Stage_D_Listener_Package.zip"
    answer_zip = output_root / "S12_Stage_D_Answer_Key.zip"
    _zip_tree(listener_zip, listener_root, "listener")
    _zip_tree(answer_zip, sealed_root, "sealed")
    return {"package_id": listener_manifest["package_id"], "trial_count": len(public_trials), "listener_zip": str(listener_zip), "answer_key_sha256": _sha256(key_path), "loudness_ceiling_lufs": loudness_ceiling_lufs}


def score_blind_responses(answer_key_path: str | Path, responses_csv: str | Path, playback_context_path: str | Path, output_root: str | Path) -> dict[str, object]:
    with Path(answer_key_path).open(encoding="utf-8") as stream:
        answer_key = json.load(stream)
    rows = list(csv.DictReader(Path(responses_csv).open(encoding="utf-8", newline="")))
    expected = answer_key.get("trials", {})
    seen: set[str] = set()
    for row in rows:
        trial_id = row.get("trial_id", "")
        if trial_id in seen:
            raise ValueError(f"duplicate trial response: {trial_id}")
        seen.add(trial_id)
        if trial_id not in expected:
            raise ValueError(f"unknown trial response: {trial_id}")
        if row.get("guessed_vehicle_id") not in _GUESSES:
            raise ValueError(f"invalid guessed_vehicle_id: {row.get('guessed_vehicle_id')}")
        for field in ("confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5"):
            try:
                value = int(row.get(field, ""))
            except ValueError as error:
                raise ValueError(f"invalid {field}") from error
            if not 1 <= value <= 5:
                raise ValueError(f"invalid {field}")
    if set(expected) != seen:
        raise ValueError("responses must contain every trial exactly once")
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    matrix = {actual: {guess: 0 for guess in (*_VEHICLES, "unsure")} for actual in _VEHICLES}
    for row in rows:
        actual = expected[row["trial_id"]]["vehicle_id"]
        matrix[actual][row["guessed_vehicle_id"]] += 1
    correct = sum(matrix[vehicle][vehicle] for vehicle in _VEHICLES)
    summary = {"labels_actual": list(_VEHICLES), "labels_predicted": [*_VEHICLES, "unsure"], "counts": matrix, "accuracy": correct / len(rows), "per_vehicle_recall": {vehicle: matrix[vehicle][vehicle] / 5.0 for vehicle in _VEHICLES}, "status": "JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS" if correct / len(rows) >= 0.80 else "HUMAN_AUDITION_FAIL"}
    (output_root / "blind_scoring_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _validate_source_trials(trials: list[object], source_root: Path) -> None:
    for trial in trials:
        if not isinstance(trial, dict) or set(("role", "vehicle_id", "scene_id", "wav")) - set(trial):
            raise ValueError("each source trial must contain role, vehicle_id, scene_id, wav")
        if trial["role"] not in ("baseline", "candidate") or trial["vehicle_id"] not in _VEHICLES or trial["scene_id"] not in _SCENES:
            raise ValueError("source trial has invalid role, vehicle, or scene")
        path = (source_root / str(trial["wav"])).resolve()
        if source_root not in path.parents or not path.is_file():
            raise ValueError("source trial wav must be inside source_root")


def _write_response_template(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=_RESPONSE_FIELDS)
        writer.writeheader()


def _zip_tree(output: Path, root: Path, prefix: str) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
