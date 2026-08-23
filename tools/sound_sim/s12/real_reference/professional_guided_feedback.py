"""Fail-closed importer for the simplified Chinese Jovi Dashboard feedback."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


class GuidedFeedbackError(ValueError):
    """Raised when simplified feedback is incomplete or unbound."""


_AGREEMENT = {"符合", "部分符合", "不符合", "无法判断"}
_PREFERENCE = {"参考", "候选", "无明显偏好"}
_PROBLEMS = {"太闷", "太薄", "太刺", "机械感不足", "机械感过强", "低频无冲击", "固定电子哨声", "转速变化不自然", "换挡不自然", "回火不自然", "循环/合成器伪影", "当前片段不包含", "无法判断", "其它"}


def _read(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuidedFeedbackError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise GuidedFeedbackError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuidedFeedbackError(f"missing {label}")
    return value.strip()


def _score(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or not 0 <= int(value) <= 100:
        raise GuidedFeedbackError(f"{label} must be an integer from 0 to 100")
    return int(value)


def validate_guided_feedback(feedback_path: Path, metrics_path: Path) -> dict[str, Any]:
    feedback = _read(Path(feedback_path), "Jovi guided feedback")
    metrics = _read(Path(metrics_path), "professional pair metrics")
    if feedback.get("schema_version") != "s12-professional-jovi-guided-feedback-v1":
        raise GuidedFeedbackError("unexpected guided feedback schema")
    if feedback.get("status") != "READY_FOR_REVIEW":
        raise GuidedFeedbackError("guided feedback must be READY_FOR_REVIEW")
    if feedback.get("automatic_tuning_eligible") is not False:
        raise GuidedFeedbackError("feedback cannot grant automatic tuning")
    if feedback.get("profile_update") != "FORBIDDEN":
        raise GuidedFeedbackError("feedback cannot grant profile update")
    gate = feedback.get("audio_submit_gate")
    if not isinstance(gate, Mapping) or gate.get("status") != "PASS":
        raise GuidedFeedbackError("audio gate must be PASS before feedback import")
    if feedback.get("package_manifest_sha256") != metrics.get("manifest_sha256"):
        raise GuidedFeedbackError("package manifest SHA mismatch")
    pairs = metrics.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 9:
        raise GuidedFeedbackError("professional metrics must contain 9 pairs")
    expected = {str(pair["pair_id"]): pair for pair in pairs}
    rows = feedback.get("rows")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise GuidedFeedbackError(f"guided feedback must cover all {len(expected)} pairs")
    seen: set[str] = set()
    vehicle_summary: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": 0, "identity_sum": 0, "realism_sum": 0, "preferences": Counter(), "agreements": Counter()})
    problem_summary: Counter[str] = Counter()
    canonical: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise GuidedFeedbackError("feedback row is malformed")
        pair_id = _text(row.get("pair_id"), "pair_id")
        if pair_id in seen or pair_id not in expected:
            raise GuidedFeedbackError(f"unknown or duplicate pair_id: {pair_id}")
        seen.add(pair_id)
        pair = expected[pair_id]
        if _text(row.get("file_id"), f"{pair_id}.file_id") != pair["file_id"]:
            raise GuidedFeedbackError(f"file_id mismatch: {pair_id}")
        if _text(row.get("vehicle_id"), f"{pair_id}.vehicle_id") != pair["vehicle_id"]:
            raise GuidedFeedbackError(f"vehicle mismatch: {pair_id}")
        if _text(row.get("reference_sha256"), f"{pair_id}.reference_sha256").lower() != str(pair["reference_sha256"]).lower() or _text(row.get("candidate_sha256"), f"{pair_id}.candidate_sha256").lower() != str(pair["candidate_sha256"]).lower():
            raise GuidedFeedbackError(f"SHA mismatch: {pair_id}")
        agreement = _text(row.get("software_agreement"), f"{pair_id}.software_agreement")
        preference = _text(row.get("preference"), f"{pair_id}.preference")
        if agreement not in _AGREEMENT:
            raise GuidedFeedbackError(f"invalid software agreement: {pair_id}")
        if preference not in _PREFERENCE:
            raise GuidedFeedbackError(f"invalid preference: {pair_id}")
        problems = row.get("problems")
        if not isinstance(problems, list) or any(problem not in _PROBLEMS for problem in problems):
            raise GuidedFeedbackError(f"invalid problem list: {pair_id}")
        identity = _score(row.get("identity"), f"{pair_id}.identity")
        realism = _score(row.get("realism"), f"{pair_id}.realism")
        notes = row.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise GuidedFeedbackError(f"notes must be text or null: {pair_id}")
        vehicle = vehicle_summary[str(pair["vehicle_id"])]
        vehicle["rows"] += 1
        vehicle["identity_sum"] += identity
        vehicle["realism_sum"] += realism
        vehicle["preferences"][preference] += 1
        vehicle["agreements"][agreement] += 1
        problem_summary.update(problems)
        canonical.append({
            "pair_id": pair_id,
            "file_id": pair["file_id"],
            "vehicle_id": pair["vehicle_id"],
            "reference_sha256": pair["reference_sha256"],
            "candidate_sha256": pair["candidate_sha256"],
            "software_agreement": agreement,
            "identity": identity,
            "realism": realism,
            "problems": list(problems),
            "preference": preference,
            "notes": notes.strip() if isinstance(notes, str) and notes.strip() else None,
        })
    if seen != set(expected):
        raise GuidedFeedbackError("guided feedback pair set does not match professional metrics")
    normalized_summary = {}
    for vehicle, summary in vehicle_summary.items():
        normalized_summary[vehicle] = {
            "rows": summary["rows"],
            "identity_mean": summary["identity_sum"] / summary["rows"],
            "realism_mean": summary["realism_sum"] / summary["rows"],
            "preferences": dict(summary["preferences"]),
            "agreements": dict(summary["agreements"]),
        }
    return {
        "schema_version": "s12-professional-jovi-guided-feedback-receipt-v1",
        "status": "VALIDATED_R2_R3_GUIDED_FEEDBACK",
        "evidence_level": feedback.get("evidence_level"),
        "package_manifest_sha256": metrics["manifest_sha256"],
        "feedback_rows": len(canonical),
        "rows": canonical,
        "vehicle_summary": normalized_summary,
        "problem_summary": dict(problem_summary),
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "parameter_changes": 0,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "profile_candidate_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入 S12 Dashboard 的 Jovi 简化反馈")
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = validate_guided_feedback(args.feedback, args.metrics)
    except GuidedFeedbackError as exc:
        print(f"ERROR: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


__all__ = ["GuidedFeedbackError", "validate_guided_feedback", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
