"""Fail-closed importer for the Chinese Stage-S human-feedback JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .build_r2_ab_package import DIMENSIONS, DIMENSION_LABELS_ZH


class FeedbackValidationError(ValueError):
    """Raised when a feedback file is not bound to one immutable R2 package."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackValidationError(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise FeedbackValidationError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeedbackValidationError(f"missing required feedback field: {field}")
    return value.strip()


def _score(value: object, field: str) -> int | float | str:
    if isinstance(value, bool):
        raise FeedbackValidationError(f"invalid score: {field}")
    if isinstance(value, str) and value.strip().lower() == "uncertain":
        return "uncertain"
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FeedbackValidationError(f"invalid score: {field}") from exc
    if not 1.0 <= number <= 5.0:
        raise FeedbackValidationError(f"score outside 1..5: {field}")
    return int(number) if number.is_integer() else number


def _canonical_scores(raw: object) -> dict[str, int | float | str]:
    if not isinstance(raw, Mapping):
        raise FeedbackValidationError("feedback case scores must be an object")
    result: dict[str, int | float | str] = {}
    for dimension in DIMENSIONS:
        label = DIMENSION_LABELS_ZH[dimension]
        value = raw.get(dimension, raw.get(label))
        if value is None or (isinstance(value, str) and not value.strip()):
            raise FeedbackValidationError(f"missing score: {dimension}")
        result[dimension] = _score(value, dimension)
    return result


def _study_cases(study: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_cases = study.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise FeedbackValidationError("study manifest has no cases")
    result: dict[str, Mapping[str, Any]] = {}
    for case in raw_cases:
        if not isinstance(case, Mapping):
            raise FeedbackValidationError("study case is malformed")
        case_id = _text(case.get("case_id"), "study.case_id")
        if case_id in result:
            raise FeedbackValidationError(f"duplicate study case: {case_id}")
        result[case_id] = case
    return result


def _source_sha(case: Mapping[str, Any], side: str) -> str:
    source = case.get(side)
    if not isinstance(source, Mapping):
        raise FeedbackValidationError(f"study case missing {side} source")
    value = source.get("source_sha256") or source.get("candidate_sha256")
    return _text(value, f"study.{side}.source_sha256").lower()


def validate_human_feedback(feedback_path: Path, study_path: Path, binding_path: Path) -> dict[str, Any]:
    """Validate one complete R2 feedback JSON and return a canonical receipt.

    Validation is deliberately limited to evidence binding.  A successful
    receipt never grants automatic tuning or Profile authority.
    """

    feedback_path = Path(feedback_path)
    study_path = Path(study_path)
    binding_path = Path(binding_path)
    feedback = _read_json(feedback_path)
    study = _read_json(study_path)
    binding = _read_json(binding_path)
    if feedback.get("schema_version") != "s12-stage-s-human-feedback-zh.v1":
        raise FeedbackValidationError("unexpected feedback schema")
    if study.get("status") != "WAITING_FOR_JOVI_HUMAN_FEEDBACK":
        raise FeedbackValidationError("study manifest is not a waiting package")
    if binding.get("schema_version") != study.get("schema_version") or binding.get("status") != study.get("status"):
        raise FeedbackValidationError("feedback binding schema/status does not match study manifest")
    study_sha = _sha256(study_path)
    supplied_sha = feedback.get("package_manifest_sha256") or feedback.get("study_manifest_sha256")
    if not isinstance(supplied_sha, str) or supplied_sha.lower() != study_sha.lower():
        raise FeedbackValidationError("feedback package SHA does not match study manifest")
    binding_study_sha = binding.get("study_manifest_sha256")
    if not isinstance(binding_study_sha, str) or binding_study_sha.lower() != study_sha.lower():
        raise FeedbackValidationError("feedback binding SHA does not match study manifest")
    test_id = _text(feedback.get("test_id"), "test_id")
    if test_id != _text(study.get("test_id"), "study.test_id") or test_id != _text(binding.get("test_id"), "binding.test_id"):
        raise FeedbackValidationError("test_id mismatch")
    if feedback.get("evidence_level") != "R2":
        raise FeedbackValidationError("only R2 human feedback is accepted by this importer")
    if feedback.get("package_status") != "READY_FOR_REVIEW":
        raise FeedbackValidationError("feedback package is incomplete")
    if feedback.get("automatic_tuning_eligible") is not False:
        raise FeedbackValidationError("feedback cannot grant automatic tuning authority")
    if feedback.get("profile_update") != "FORBIDDEN":
        raise FeedbackValidationError("feedback cannot grant Profile authority")
    metadata = {field: _text(feedback.get(field), field) for field in (
        "listener_id", "playback_device", "windows_volume", "playback_endpoint", "system_audio_effects"
    )}
    study_cases = _study_cases(study)
    binding_cases = binding.get("cases")
    if not isinstance(binding_cases, Mapping):
        raise FeedbackValidationError("feedback binding has no case map")
    if set(binding_cases) != set(study_cases):
        raise FeedbackValidationError("feedback binding case map does not match study package")
    raw_cases = feedback.get("cases")
    if not isinstance(raw_cases, list):
        raw_cases = [feedback]
    if not raw_cases:
        raise FeedbackValidationError("feedback contains no cases")
    canonical_cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            raise FeedbackValidationError("feedback case is malformed")
        case_id = _text(raw_case.get("case_id"), "case_id")
        if case_id in seen_case_ids:
            raise FeedbackValidationError(f"duplicate feedback case: {case_id}")
        seen_case_ids.add(case_id)
        study_case = study_cases.get(case_id)
        binding_case = binding_cases.get(case_id)
        if not isinstance(study_case, Mapping) or not isinstance(binding_case, Mapping):
            raise FeedbackValidationError(f"unknown feedback case: {case_id}")
        vehicle_id = _text(raw_case.get("vehicle_id"), "vehicle_id")
        scenario = _text(raw_case.get("scenario"), "scenario")
        if vehicle_id != _text(study_case.get("vehicle_id"), "study.vehicle_id") or scenario != _text(study_case.get("scenario"), "study.scenario"):
            raise FeedbackValidationError(f"vehicle/scenario mismatch: {case_id}")
        if vehicle_id != _text(binding_case.get("vehicle_id"), "binding.vehicle_id") or scenario != _text(binding_case.get("scenario"), "binding.scenario"):
            raise FeedbackValidationError(f"feedback binding vehicle/scenario mismatch: {case_id}")
        reference_sha = _text(raw_case.get("reference_sha256"), "reference_sha256").lower()
        candidate_sha = _text(raw_case.get("candidate_sha256"), "candidate_sha256").lower()
        if reference_sha != _source_sha(study_case, "reference") or reference_sha != _text(binding_case.get("reference_sha256"), "binding.reference_sha256").lower():
            raise FeedbackValidationError(f"reference SHA mismatch: {case_id}")
        if candidate_sha != _source_sha(study_case, "candidate") or candidate_sha != _text(binding_case.get("candidate_sha256"), "binding.candidate_sha256").lower():
            raise FeedbackValidationError(f"candidate SHA mismatch: {case_id}")
        canonical_cases.append({
            "case_id": case_id,
            "vehicle_id": vehicle_id,
            "scenario": scenario,
            "reference_sha256": reference_sha,
            "candidate_sha256": candidate_sha,
            "scores": _canonical_scores(raw_case.get("scores")),
            "preference": _text(raw_case.get("preference"), "preference"),
            "notes_zh": raw_case.get("notes_zh") if isinstance(raw_case.get("notes_zh"), str) else None,
        })
    expected_case_ids = set(study_cases)
    if seen_case_ids != expected_case_ids:
        missing = sorted(expected_case_ids - seen_case_ids)
        extra = sorted(seen_case_ids - expected_case_ids)
        detail = []
        if missing:
            detail.append(f"missing={','.join(missing)}")
        if extra:
            detail.append(f"extra={','.join(extra)}")
        raise FeedbackValidationError("feedback cases do not cover study package: " + "; ".join(detail))
    return {
        "schema_version": "s12-stage-s-r2-human-feedback-receipt-v1",
        "status": "VALIDATED_R2_HUMAN_FEEDBACK",
        "evidence_level": "R2",
        "feedback_rows": len(canonical_cases),
        "feedback_sha256": _sha256(feedback_path),
        "study_manifest_sha256": study_sha,
        "feedback_binding_sha256": _sha256(binding_path),
        "test_id": test_id,
        **metadata,
        "cases": canonical_cases,
        "case_id": canonical_cases[0]["case_id"] if len(canonical_cases) == 1 else None,
        "scores": canonical_cases[0]["scores"] if len(canonical_cases) == 1 else None,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "parameter_changes": 0,
        "profile_candidate_ready": False,
    }



def main() -> int:
    parser = argparse.ArgumentParser(description="导入并校验绑定 SHA 的中文 R2 人耳反馈")
    parser.add_argument("--feedback", type=Path, required=True, help="页面导出的反馈 JSON")
    parser.add_argument("--study", type=Path, required=True, help="study_manifest.json")
    parser.add_argument("--binding", type=Path, required=True, help="feedback_binding.json")
    parser.add_argument("--output", type=Path, required=True, help="规范化收据输出路径")
    args = parser.parse_args()
    receipt = validate_human_feedback(args.feedback, args.study, args.binding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


__all__ = ["FeedbackValidationError", "validate_human_feedback", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
