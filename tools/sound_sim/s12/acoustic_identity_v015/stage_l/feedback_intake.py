"""Inspect Stage-K review inputs without promoting diagnostic text to a score."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class StageLFeedbackReceipt:
    stage_k_package_sha256: str
    formal_template_sha256: str
    formal_template_status: str
    nested_copy_sha256: str
    nested_copy_status: str
    named_text_feedback_sha256: str
    feedback_scope: str
    human_pass: bool


def inspect_stage_l_feedback_inputs(package_root: str | Path, named_text_feedback_path: str | Path) -> StageLFeedbackReceipt:
    root = Path(package_root).resolve()
    archive = root / "S12_Stage_K_Named_Review.zip"
    formal = root / "06_Feedback" / "Jovi_Stage_K_Named_Feedback.csv"
    nested = root / "S12_Stage_K_Named_Review" / "06_Feedback" / "Jovi_Stage_K_Named_Feedback.csv"
    sums = root / "SHA256SUMS.txt"
    if not all(path.is_file() for path in (archive, formal, nested, sums)):
        raise ValueError("canonical Stage-K package root must contain ZIP, SHA256SUMS, formal template and nested diagnostic copy")
    binding = sums.read_text(encoding="utf-8")
    formal_sha = _sha256(formal)
    if formal_sha not in binding.lower() or "06_feedback/jovi_stage_k_named_feedback.csv" not in binding.replace("\\", "/").lower():
        raise ValueError("formal Stage-K feedback template is not SHA256SUMS-bound")
    formal_rows = _rows(formal)
    score_fields = tuple(name for name in formal_rows[0] if name.endswith("_1_5")) if formal_rows else ()
    if not score_fields or any(row.get(name, "").strip() for row in formal_rows for name in score_fields):
        raise ValueError("formal Stage-K feedback is not an unsubmitted blank template")
    nested_rows = _rows(nested)
    nested_values = [row.get(name, "").strip() for row in nested_rows for name in score_fields]
    if not any(value == "0" for value in nested_values):
        raise ValueError("nested diagnostic copy does not exhibit the recorded out-of-range zero-score boundary")
    nested_sha = _sha256(nested)
    nested_relative = "s12_stage_k_named_review/06_feedback/jovi_stage_k_named_feedback.csv"
    if nested_sha in binding.lower() or nested_relative in binding.replace("\\", "/").lower():
        raise ValueError("nested diagnostic copy unexpectedly appears in canonical SHA256SUMS")
    text_path = Path(named_text_feedback_path).resolve()
    try:
        feedback = json.loads(text_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read named Stage-L text feedback") from exc
    if feedback.get("human_pass") is not False:
        raise ValueError("named text feedback human_pass must remain false")
    if feedback.get("feedback_scope") != "named_engineering_direction":
        raise ValueError("named text feedback feedback_scope must remain named_engineering_direction")
    return StageLFeedbackReceipt(
        _sha256(archive), formal_sha, "UNSUBMITTED_TEMPLATE", nested_sha,
        "INVALID_UNBOUND_DIAGNOSTIC_COPY", _sha256(text_path),
        "named_engineering_direction", False,
    )


def _rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError as exc:
        raise ValueError(f"cannot read feedback CSV: {path}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ("StageLFeedbackReceipt", "inspect_stage_l_feedback_inputs")
