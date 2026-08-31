"""Fail-closed Stage-F response validation and role-aware scoring."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Mapping

from .package_builder import AB_FIELDS, BLIND_FIELDS, PACKAGE_ID, VEHICLES

GUESSES = (*VEHICLES, "unsure")


@dataclass(frozen=True)
class PlaybackContext:
    payload: Mapping[str, object]


@dataclass(frozen=True)
class BlindResponse:
    payload: Mapping[str, str]


@dataclass(frozen=True)
class PairResponse:
    payload: Mapping[str, str]


@dataclass(frozen=True)
class StageFSubmission:
    blind_rows: tuple[BlindResponse, ...]
    pair_rows: tuple[PairResponse, ...]
    playback_context: PlaybackContext


@dataclass(frozen=True)
class StageFScore:
    baseline: Mapping[str, object]
    candidate: Mapping[str, object]
    delta: Mapping[str, float]
    pair_results: tuple[Mapping[str, object], ...]
    gates: Mapping[str, bool]
    status: str


def validate_stage_f_submission(listener_manifest_path, blind_csv_path, pair_csv_path, playback_context_path) -> StageFSubmission:
    manifest = json.loads(Path(listener_manifest_path).read_text(encoding="utf-8"))
    context = json.loads(Path(playback_context_path).read_text(encoding="utf-8"))
    _validate_context(context, manifest)
    blind = _read_rows(Path(blind_csv_path), BLIND_FIELDS)
    if len(blind) != 30:
        raise ValueError("blind responses must contain exactly 30 trials")
    expected = {str(t["trial_id"]): int(t["round_id"]) for t in manifest.get("trials", [])}
    if len(expected) != 30:
        raise ValueError("listener manifest must contain 30 trials")
    seen = set()
    for row in blind:
        if row["package_id"] != PACKAGE_ID or row["listener_id"] != context["listener_id"] or row["trial_id"] in seen or row["trial_id"] not in expected:
            raise ValueError("blind response identity or trial set is invalid")
        seen.add(row["trial_id"])
        if int(row["round_id"]) != expected[row["trial_id"]] or row["guessed_vehicle_id"] not in GUESSES:
            raise ValueError("blind response round or vehicle guess is invalid")
        for field in ("confidence_1_5", "identity_strength_1_5", "realism_1_5", "artifact_freedom_1_5"):
            _score(row[field], field)
    if seen != set(expected):
        raise ValueError("blind responses do not match manifest")
    pair_rows = _read_rows(Path(pair_csv_path), AB_FIELDS)
    if len(pair_rows) != 3:
        raise ValueError("A/B responses must contain exactly 3 pairs")
    pair_ids = {f"P{i:02d}" for i in range(1, 4)}
    if {row["pair_id"] for row in pair_rows} != pair_ids:
        raise ValueError("A/B pair IDs are incomplete or duplicated")
    for row in pair_rows:
        if row["package_id"] != PACKAGE_ID or row["listener_id"] != context["listener_id"] or row["preferred_option"] not in {"A", "B", "equal", "unsure"}:
            raise ValueError("invalid A/B response")
        _score(row["low_frequency_naturalness_1_5"], "low_frequency_naturalness_1_5")
        _score(row["afterfire_naturalness_1_5"], "afterfire_naturalness_1_5")
        if row["artifact_blocker"].lower() not in {"true", "false"}:
            raise ValueError("artifact_blocker must be boolean")
        if row["artifact_blocker"].lower() == "true" and not row["notes"].strip():
            raise ValueError("artifact blocker requires notes")
    return StageFSubmission(tuple(BlindResponse(row) for row in blind), tuple(PairResponse(row) for row in pair_rows), PlaybackContext(context))


def score_stage_f_submission(answer_key_path, pair_key_path, submission: StageFSubmission, output_root=None) -> StageFScore:
    key = json.loads(Path(answer_key_path).read_text(encoding="utf-8")); pair_key = json.loads(Path(pair_key_path).read_text(encoding="utf-8"))["pairs"]
    expected = key["trials"]
    role_rows = {"baseline": [], "candidate": []}
    for response in submission.blind_rows:
        trial = expected[response.payload["trial_id"]]; role_rows[trial["role"]].append((response.payload, trial))
    summaries = {role: _summarize(rows) for role, rows in role_rows.items()}
    pairs = []
    for response in submission.pair_rows:
        mapping = pair_key[response.payload["pair_id"]]
        preferred = response.payload["preferred_option"]
        selected_role = mapping.get(f"{preferred}_role") if preferred in {"A", "B"} else None
        pairs.append({"pair_id": response.payload["pair_id"], "preferred": preferred, "candidate_better_or_equal": selected_role in {"candidate", None} and preferred == "equal" or selected_role == "candidate", "artifact_blocker": response.payload["artifact_blocker"].lower() == "true"})
    baseline = summaries["baseline"]; candidate = summaries["candidate"]
    gates = {
        "candidate_overall_12_of_15": candidate["correct"] >= 12,
        "candidate_per_vehicle_4_of_5": all(value >= 4 for value in candidate["per_vehicle_correct"].values()),
        "candidate_confidence_median_3": candidate["confidence_median_correct"] >= 3,
        "candidate_realism_4_each_vehicle": all(value >= 4.0 for value in candidate["realism_mean"].values()),
        "candidate_artifact_freedom_3": candidate["min_artifact_freedom"] >= 3,
        "candidate_recognition_not_below_baseline": candidate["accuracy"] >= baseline["accuracy"],
        "ab_candidate_better_or_equal": all(pair["candidate_better_or_equal"] and not pair["artifact_blocker"] for pair in pairs),
    }
    status = "JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS" if all(gates.values()) else "ITERATION_REQUIRED"
    score = StageFScore(baseline, candidate, {"accuracy_delta": candidate["accuracy"] - baseline["accuracy"]}, tuple(pairs), gates, status)
    if output_root is not None:
        path = Path(output_root); path.mkdir(parents=True, exist_ok=True); (path / "stage_f_audition_summary.json").write_text(json.dumps({"baseline": baseline, "candidate": candidate, "delta": dict(score.delta), "pair_results": list(pairs), "gates": dict(gates), "status": status}, indent=2), encoding="utf-8")
    return score


def _summarize(rows):
    counts = {vehicle: {guess: 0 for guess in GUESSES} for vehicle in VEHICLES}
    correct_confidence = []; realism = {vehicle: [] for vehicle in VEHICLES}; artifacts = []
    for response, trial in rows:
        guess = response["guessed_vehicle_id"]; actual = trial["vehicle_id"]; counts[actual][guess] += 1
        if guess == actual: correct_confidence.append(int(response["confidence_1_5"]))
        realism[actual].append(int(response["realism_1_5"])); artifacts.append(int(response["artifact_freedom_1_5"]))
    per_vehicle_correct = {vehicle: counts[vehicle][vehicle] for vehicle in VEHICLES}
    correct = sum(per_vehicle_correct.values())
    return {"counts": counts, "correct": correct, "accuracy": correct / 15.0, "per_vehicle_correct": per_vehicle_correct, "per_vehicle_recall": {v: per_vehicle_correct[v] / 5.0 for v in VEHICLES}, "confidence_median_correct": _median(correct_confidence), "realism_mean": {v: sum(values) / len(values) if values else 0.0 for v, values in realism.items()}, "min_artifact_freedom": min(artifacts) if artifacts else 0}


def _validate_context(context, manifest):
    required = ("package_id", "listener_id", "playback_device", "headphones_or_speakers", "windows_volume_percent", "player", "eq_enabled", "spatial_audio_enabled", "environment", "start_time", "completion_time")
    if any(key not in context or context[key] in ("", None) for key in required):
        raise ValueError("playback context is incomplete")
    if context["package_id"] != manifest["package_id"] or not isinstance(context["eq_enabled"], bool) or not isinstance(context["spatial_audio_enabled"], bool):
        raise ValueError("playback context identity or booleans are invalid")
    if not isinstance(context["windows_volume_percent"], (int, float)) or not 1 <= context["windows_volume_percent"] <= 100:
        raise ValueError("windows volume must be 1..100")
    try:
        start = datetime.fromisoformat(str(context["start_time"])); end = datetime.fromisoformat(str(context["completion_time"]))
    except ValueError as error:
        raise ValueError("playback timestamps must be ISO-8601") from error
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("playback timestamps must be timezone-aware and ordered")


def _read_rows(path, fields):
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError("response fields do not match Stage-F contract")
        return list(reader)


def _score(value, field):
    try: number = int(value)
    except (TypeError, ValueError) as error: raise ValueError(f"invalid {field}") from error
    if not 1 <= number <= 5: raise ValueError(f"invalid {field}")


def _median(values):
    if not values: return 0.0
    values = sorted(values); middle = len(values) // 2
    return float(values[middle]) if len(values) % 2 else float(values[middle - 1] + values[middle]) / 2.0
