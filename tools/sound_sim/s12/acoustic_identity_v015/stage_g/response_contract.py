"""Fail-closed Stage-G submission validation and sealed-role scoring."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping

PACKAGE_ID = "S12_Blind_Audition_Package_v4"
VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
GUESSES = (*VEHICLES, "unsure")
BLIND_FIELDS = ("package_id", "listener_id", "round_id", "trial_id", "guessed_vehicle_id", "confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5", "notes")
AB_FIELDS = ("package_id", "listener_id", "pair_id", "preferred_option", "low_frequency_naturalness_1_5", "afterfire_naturalness_1_5", "artifact_blocker", "notes")


@dataclass(frozen=True)
class PlaybackContext:
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class BlindResponse:
    payload: Mapping[str, str]


@dataclass(frozen=True)
class PairResponse:
    payload: Mapping[str, str]


@dataclass(frozen=True)
class StageGSubmission:
    blind_rows: tuple[BlindResponse, ...]
    pair_rows: tuple[PairResponse, ...]
    playback_context: PlaybackContext


@dataclass(frozen=True)
class StageGScore:
    baseline: Mapping[str, object]
    candidate: Mapping[str, object]
    delta: Mapping[str, float]
    pair_results: tuple[Mapping[str, object], ...]
    gates: Mapping[str, bool]
    status: str


def validate_stage_g_submission(listener_manifest_path: str | Path, blind_csv_path: str | Path, pair_csv_path: str | Path, playback_context_path: str | Path) -> StageGSubmission:
    manifest = json.loads(Path(listener_manifest_path).read_text(encoding="utf-8"))
    context = json.loads(Path(playback_context_path).read_text(encoding="utf-8"))
    _validate_context(context, manifest)
    blind = _read_rows(Path(blind_csv_path), BLIND_FIELDS)
    if len(blind) != 30:
        raise ValueError("Stage-G blind responses must contain exactly 30 trials")
    expected = {str(item["trial_id"]): int(item["round_id"]) for item in manifest.get("trials", [])}
    if len(expected) != 30:
        raise ValueError("Stage-G listener manifest must contain exactly 30 trials")
    seen: set[str] = set()
    per_round = {1: 0, 2: 0}
    for row in blind:
        if row["package_id"] != PACKAGE_ID or row["listener_id"] != context["listener_id"] or row["trial_id"] in seen or row["trial_id"] not in expected:
            raise ValueError("Stage-G blind response identity or trial set is invalid")
        round_id = int(row["round_id"])
        if round_id != expected[row["trial_id"]] or round_id not in per_round or row["guessed_vehicle_id"] not in GUESSES:
            raise ValueError("Stage-G blind response round or vehicle guess is invalid")
        seen.add(row["trial_id"]); per_round[round_id] += 1
        for field in ("confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5"):
            _score(row[field], field)
    if seen != set(expected) or per_round != {1: 15, 2: 15}:
        raise ValueError("Stage-G blind responses must have 15 complete trials per round")
    pairs = _read_rows(Path(pair_csv_path), AB_FIELDS)
    if len(pairs) != 3 or {row["pair_id"] for row in pairs} != {"P01", "P02", "P03"}:
        raise ValueError("Stage-G A/B responses must contain exactly P01/P02/P03")
    for row in pairs:
        if row["package_id"] != PACKAGE_ID or row["listener_id"] != context["listener_id"] or row["preferred_option"] not in {"A", "B", "equal", "unsure"}:
            raise ValueError("invalid Stage-G A/B response")
        _score(row["low_frequency_naturalness_1_5"], "low_frequency_naturalness_1_5")
        _score(row["afterfire_naturalness_1_5"], "afterfire_naturalness_1_5")
        blocker = row["artifact_blocker"].strip().lower()
        if blocker not in {"true", "false"}:
            raise ValueError("artifact_blocker must be boolean")
        if blocker == "true" and not row["notes"].strip():
            raise ValueError("artifact blocker requires notes")
    return StageGSubmission(tuple(BlindResponse(row) for row in blind), tuple(PairResponse(row) for row in pairs), PlaybackContext(context))


def score_stage_g_submission(answer_key_path: str | Path, pair_key_path: str | Path, submission: StageGSubmission) -> StageGScore:
    key = json.loads(Path(answer_key_path).read_text(encoding="utf-8"))
    pair_key = json.loads(Path(pair_key_path).read_text(encoding="utf-8"))["pairs"]
    expected = key["trials"]
    role_rows: dict[str, list[tuple[Mapping[str, str], Mapping[str, str]]]] = {"baseline": [], "candidate": []}
    round_rows: dict[str, dict[int, list[tuple[Mapping[str, str], Mapping[str, str]]]]] = {"baseline": {1: [], 2: []}, "candidate": {1: [], 2: []}}
    for response in submission.blind_rows:
        trial = expected[response.payload["trial_id"]]
        role = trial["role"]
        role_rows[role].append((response.payload, trial)); round_rows[role][int(response.payload["round_id"])].append((response.payload, trial))
    baseline = _summarize(role_rows["baseline"])
    candidate = _summarize(role_rows["candidate"])
    round_scores = {role: {str(round_id): _summarize(rows) for round_id, rows in rounds.items()} for role, rounds in round_rows.items()}
    pair_results = []
    for response in submission.pair_rows:
        pair_id = response.payload["pair_id"]; mapping = pair_key[pair_id]; preferred = response.payload["preferred_option"]
        selected_role = mapping.get(f"{preferred}_role") if preferred in {"A", "B"} else None
        blocker = response.payload["artifact_blocker"].lower() == "true"
        pair_results.append({"pair_id": pair_id, "preferred": preferred, "selected_role": selected_role, "candidate_better_or_equal": bool(selected_role == "candidate" or preferred == "equal"), "artifact_blocker": blocker, "notes": response.payload["notes"]})
    gates = {
        "candidate_overall_12_of_15": candidate["correct"] >= 12,
        "candidate_per_vehicle_4_of_5": all(value >= 4 for value in candidate["per_vehicle_correct"].values()),
        "candidate_directed_confusion_at_most_1": candidate["max_directed_confusion"] <= 1,
        "candidate_confidence_median_3": candidate["confidence_median_correct"] >= 3,
        "candidate_realism_4_each_vehicle": all(value >= 4.0 for value in candidate["realism_mean"].values()),
        "candidate_artifact_freedom_3": candidate["min_artifact_freedom"] >= 3,
        "candidate_recognition_not_below_baseline": candidate["accuracy"] >= baseline["accuracy"],
        "candidate_gain_if_baseline_below_80": baseline["correct"] >= 12 or candidate["correct"] >= baseline["correct"] + 2,
        "ab_candidate_better_or_equal_without_blocker": all(item["candidate_better_or_equal"] and not item["artifact_blocker"] and item["preferred"] != "unsure" for item in pair_results),
    }
    status = "JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS" if all(gates.values()) else "ITERATION_REQUIRED"
    delta = {"accuracy_delta": float(candidate["accuracy"] - baseline["accuracy"]), "correct_delta": float(candidate["correct"] - baseline["correct"])}
    return StageGScore({**baseline, "rounds": round_scores["baseline"]}, {**candidate, "rounds": round_scores["candidate"]}, delta, tuple(pair_results), gates, status)


def _summarize(rows: list[tuple[Mapping[str, str], Mapping[str, str]]]) -> dict[str, object]:
    counts = {vehicle: {guess: 0 for guess in GUESSES} for vehicle in VEHICLES}
    correct_confidence: list[int] = []; realism = {vehicle: [] for vehicle in VEHICLES}; artifacts: list[int] = []
    for response, trial in rows:
        actual = str(trial["vehicle_id"]); guess = response["guessed_vehicle_id"]; counts[actual][guess] += 1
        if guess == actual: correct_confidence.append(int(response["confidence_1_5"]))
        realism[actual].append(int(response["realism_1_5"])); artifacts.append(int(response["artifact_freedom_1_5"]))
    per_vehicle_correct = {vehicle: counts[vehicle][vehicle] for vehicle in VEHICLES}
    directed = {(actual, guess): counts[actual][guess] for actual in VEHICLES for guess in VEHICLES if actual != guess}
    return {"confusion_matrix": counts, "correct": sum(per_vehicle_correct.values()), "accuracy": sum(per_vehicle_correct.values()) / 15.0, "per_vehicle_correct": per_vehicle_correct, "per_vehicle_recall": {v: per_vehicle_correct[v] / 5.0 for v in VEHICLES}, "per_scene_accuracy": _scene_accuracy(rows), "confidence_median_correct": float(median(correct_confidence)) if correct_confidence else 0.0, "identity_strength_mean": _mean_score(rows, "identity_strength_1_5"), "realism_mean": {v: (sum(values) / len(values) if values else 0.0) for v, values in realism.items()}, "min_artifact_freedom": min(artifacts) if artifacts else 0, "directed_confusion": {f"{a}->{g}": n for (a, g), n in directed.items()}, "max_directed_confusion": max(directed.values(), default=0)}


def _scene_accuracy(rows):
    values = {scene: [0, 0] for scene in ("idle", "cruise", "acceleration", "shift", "lift")}
    for response, trial in rows:
        scene = str(trial["scene_id"]); values[scene][1] += 1; values[scene][0] += int(response["guessed_vehicle_id"] == trial["vehicle_id"])
    return {scene: (correct / total if total else 0.0) for scene, (correct, total) in values.items()}


def _mean_score(rows, field):
    return float(sum(int(response[field]) for response, _ in rows) / len(rows)) if rows else 0.0


def _validate_context(context, manifest):
    required = ("package_id", "listener_id", "playback_device", "headphones_or_speakers", "windows_volume_percent", "player", "eq_enabled", "spatial_audio_enabled", "environment", "start_time", "completion_time")
    if any(key not in context or context[key] in ("", None) for key in required):
        raise ValueError("playback context is incomplete")
    if context["package_id"] != PACKAGE_ID or context["package_id"] != manifest.get("package_id") or not isinstance(context["eq_enabled"], bool) or not isinstance(context["spatial_audio_enabled"], bool):
        raise ValueError("playback context identity or booleans are invalid")
    if not isinstance(context["windows_volume_percent"], (int, float)) or isinstance(context["windows_volume_percent"], bool) or not 1 <= context["windows_volume_percent"] <= 100:
        raise ValueError("windows volume must be 1..100")
    try:
        start = datetime.fromisoformat(str(context["start_time"])); end = datetime.fromisoformat(str(context["completion_time"]))
    except ValueError as exc:
        raise ValueError("playback timestamps must be ISO-8601") from exc
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("playback timestamps must be timezone-aware and ordered")


def _read_rows(path: Path, fields):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError("response fields do not match Stage-G contract")
        return list(reader)


def _score(value, field):
    try: number = int(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"invalid {field}") from exc
    if not 1 <= number <= 5: raise ValueError(f"invalid {field}")


__all__ = ("AB_FIELDS", "BLIND_FIELDS", "BlindResponse", "PairResponse", "PACKAGE_ID", "PlaybackContext", "StageGScore", "StageGSubmission", "validate_stage_g_submission", "score_stage_g_submission")
