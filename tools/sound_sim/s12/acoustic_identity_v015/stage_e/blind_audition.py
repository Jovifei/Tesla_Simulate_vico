"""Stage-E two-round blind package and fail-closed response scorer."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import secrets
import zipfile

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _read_pcm24_wav, _write_pcm24_wav

VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
SCENES = ("idle", "cruise", "acceleration", "shift", "lift")
GUESSES = (*VEHICLES, "unsure")
RESPONSE_FIELDS = ("package_id", "listener_id", "round_id", "trial_id", "guessed_vehicle_id", "confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5", "notes")
PACKAGE_ID = "S12_Blind_Audition_Package_v2"


def build_stage_e_blind_package(source_root: str | Path, source_manifest: str | Path, output_root: str | Path, seed: int | None = None, loudness_ceiling_lufs: float = -20.0) -> dict[str, object]:
    root, source_root, manifest_path = Path(output_root).resolve(), Path(source_root).resolve(), Path(source_manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    trials = manifest.get("trials", [])
    _validate_trials(trials, source_root)
    root.mkdir(parents=True, exist_ok=True)
    listener, sealed, results = root / "listener", root / "sealed", root / "results"
    for path in (listener, sealed, results): path.mkdir(exist_ok=True)
    audio = {str(t["wav"]): _read_pcm24_wav(source_root / str(t["wav"])) for t in trials}
    targets = {scene: min(float(loudness_ceiling_lufs), min(float(measure_loudness(audio[str(t["wav"])]).integrated_lufs) for t in trials if t["scene_id"] == scene)) for scene in SCENES}
    generator = np.random.Generator(np.random.PCG64(seed if seed is not None else secrets.randbits(128)))
    roles = ["baseline", "candidate"]
    if int(generator.integers(0, 2)): roles.reverse()
    answer_trials, public_trials = {}, []
    for round_index, role in enumerate(roles, 1):
        round_root = listener / f"round_{round_index}"
        round_root.mkdir(exist_ok=True)
        selected = sorted((t for t in trials if t["role"] == role), key=lambda t: (str(t["scene_id"]), str(t["vehicle_id"])))
        for trial_index in generator.permutation(len(selected)):
            trial = selected[int(trial_index)]
            trial_id = f"R{round_index}_T{len(public_trials) % 15 + 1:02d}"
            clip = audio[str(trial["wav"])].copy()
            gain_db = min(0.0, targets[str(trial["scene_id"])] - float(measure_loudness(clip).integrated_lufs))
            clip *= 10.0 ** (gain_db / 20.0)
            _write_pcm24_wav(round_root / f"{trial_id}.wav", clip)
            answer_trials[trial_id] = {"vehicle_id": trial["vehicle_id"], "scene_id": trial["scene_id"], "role": role}
            public_trials.append({"trial_id": trial_id, "round_id": round_index, "scene_id": trial["scene_id"]})
    key = {"package_id": PACKAGE_ID, "seed": seed, "round_role": {"round_1": roles[0], "round_2": roles[1]}, "trials": answer_trials}
    key_path = sealed / "answer_key.json"; key_path.write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    (listener / "listener_manifest.json").write_text(json.dumps({"package_id": PACKAGE_ID, "trial_count": 30, "trials": public_trials}, indent=2), encoding="utf-8")
    _write_template(listener / "responses_template.csv")
    (listener / "playback_context_template.json").write_text(json.dumps({"package_id": PACKAGE_ID, "listener_id": "jovi", "playback_device": "", "headphones_or_speakers": "", "windows_volume_percent": 40, "player": "", "eq_enabled": False, "spatial_audio_enabled": False, "environment": "", "start_time": "", "completion_time": ""}, indent=2), encoding="utf-8")
    (sealed / "source_provenance.json").write_text(json.dumps({"manifest_sha256": _sha256(manifest_path), "provenance": "C/synthetic; B/R2 relative only; uncalibrated; not OEM reproduction"}, indent=2), encoding="utf-8")
    (sealed / "scoring_contract.json").write_text(json.dumps({"labels_actual": list(VEHICLES), "labels_predicted": list(GUESSES), "round_denominator": 5, "combined_denominator": 10}, indent=2), encoding="utf-8")
    (results / "README.md").write_text("Provide complete responses.csv and playback_context.json. Scoring is blocked until both validate.\n", encoding="utf-8")
    listener_zip, answer_zip = root / "S12_Stage_E_Listener_Package.zip", root / "S12_Stage_E_Answer_Key.zip"
    _zip_tree(listener_zip, listener, "listener"); _zip_tree(answer_zip, sealed, "sealed")
    return {"package_id": PACKAGE_ID, "trial_count": 30, "listener_zip": str(listener_zip), "answer_key_sha256": _sha256(key_path), "status": "WAITING_FOR_JOVI_AUDITION"}


def validate_stage_e_responses(responses_csv: str | Path, playback_context_path: str | Path) -> list[dict[str, str]]:
    context = json.loads(Path(playback_context_path).read_text(encoding="utf-8"))
    required_context = ("playback_device", "headphones_or_speakers", "windows_volume_percent", "player", "eq_enabled", "spatial_audio_enabled", "environment", "start_time", "completion_time")
    if any(context.get(k, "") in ("", None) for k in required_context): raise ValueError("playback context is incomplete")
    try:
        if not 0 <= float(context["windows_volume_percent"]) <= 100:
            raise ValueError("windows volume must be 0..100")
    except (TypeError, ValueError) as error:
        raise ValueError("windows volume must be numeric") from error
    with Path(responses_csv).open(encoding="utf-8", newline="") as stream: rows = list(csv.DictReader(stream))
    if len(rows) != 30: raise ValueError("responses must contain 30 trials")
    seen = set()
    for row in rows:
        if row.get("package_id") != PACKAGE_ID or not row.get("listener_id"):
            raise ValueError("invalid package_id or listener_id")
        if row.get("round_id") not in ("1", "2"):
            raise ValueError("round_id must be 1 or 2")
        if row.get("trial_id") in seen: raise ValueError("duplicate trial")
        seen.add(row.get("trial_id"))
        if row.get("guessed_vehicle_id") not in GUESSES: raise ValueError("invalid vehicle guess")
        for field in ("confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5"):
            try: value = int(row.get(field, ""))
            except ValueError as error: raise ValueError(f"invalid {field}") from error
            if not 1 <= value <= 5: raise ValueError(f"invalid {field}")
    return rows


def score_stage_e_blind_responses(answer_key_path: str | Path, responses_csv: str | Path, playback_context_path: str | Path, output_root: str | Path) -> dict[str, object]:
    rows = validate_stage_e_responses(responses_csv, playback_context_path)
    key = json.loads(Path(answer_key_path).read_text(encoding="utf-8"))
    expected = key["trials"]
    if {r["trial_id"] for r in rows} != set(expected): raise ValueError("responses do not match sealed trial set")
    summaries = {}
    for round_id in (1, 2):
        subset = [r for r in rows if int(r["round_id"]) == round_id]
        if len(subset) != 15:
            raise ValueError("each round must contain 15 responses")
        matrix = {actual: {guess: 0 for guess in GUESSES} for actual in VEHICLES}
        for row in subset:
            actual = expected[row["trial_id"]]["vehicle_id"]; matrix[actual][row["guessed_vehicle_id"]] += 1
        if any(sum(matrix[actual].values()) != 5 for actual in VEHICLES):
            raise ValueError("each round must contain five trials per vehicle")
        correct = sum(matrix[v][v] for v in VEHICLES)
        summaries[f"round_{round_id}"] = {"counts": matrix, "accuracy": correct / 15.0, "per_vehicle_recall": {v: matrix[v][v] / 5.0 for v in VEHICLES}, "confidence_median_correct": _median_correct(rows, expected, round_id)}
    combined = {actual: {guess: 0 for guess in GUESSES} for actual in VEHICLES}
    for summary in summaries.values():
        for actual in VEHICLES:
            for guess in GUESSES: combined[actual][guess] += summary["counts"][actual][guess]
    accuracy = sum(combined[v][v] for v in VEHICLES) / 30.0
    result = {"package_id": PACKAGE_ID, "rounds": summaries, "combined": {"counts": combined, "accuracy": accuracy, "per_vehicle_recall": {v: combined[v][v] / 10.0 for v in VEHICLES}}, "status": "JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS" if accuracy >= .8 else "HUMAN_AUDITION_FAIL"}
    Path(output_root).mkdir(parents=True, exist_ok=True); (Path(output_root) / "stage_e_audition_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _median_correct(rows, expected, round_id):
    values = [int(r["confidence_1_5"]) for r in rows if int(r["round_id"]) == round_id and r["guessed_vehicle_id"] == expected[r["trial_id"]]["vehicle_id"]]
    return float(np.median(values)) if values else 0.0


def _validate_trials(trials, root):
    if len(trials) != 30: raise ValueError("Stage-E source manifest must contain 30 trials")
    for t in trials:
        if t.get("role") not in ("baseline", "candidate") or t.get("vehicle_id") not in VEHICLES or t.get("scene_id") not in SCENES: raise ValueError("invalid source trial")
        path = (root / str(t["wav"])).resolve()
        if root not in path.parents or not path.is_file(): raise ValueError("source wav outside root")


def _write_template(path):
    with path.open("w", newline="", encoding="utf-8") as stream: csv.DictWriter(stream, fieldnames=RESPONSE_FIELDS).writeheader()


def _zip_tree(output, root, prefix):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file(): archive.writestr(f"{prefix}/{path.relative_to(root).as_posix()}", path.read_bytes())


def _sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
