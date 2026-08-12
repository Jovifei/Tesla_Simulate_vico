"""Inspect Stage-K review inputs without promoting diagnostic text to a score."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .candidate_profiles import _load_l0_feedback_bindings


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
    expected = _load_l0_feedback_bindings()
    root = Path(package_root).resolve()
    archive = root / "S12_Stage_K_Named_Review.zip"
    formal = root / "06_Feedback" / "Jovi_Stage_K_Named_Feedback.csv"
    nested = root / "S12_Stage_K_Named_Review" / "06_Feedback" / "Jovi_Stage_K_Named_Feedback.csv"
    sums = root / "SHA256SUMS.txt"
    if not all(path.is_file() for path in (archive, formal, nested, sums)):
        raise ValueError("canonical Stage-K package root must contain ZIP, SHA256SUMS, formal template and nested diagnostic copy")
    bindings = _parse_sha256sums(sums)
    archive_sha = _sha256(archive)
    if archive_sha != expected["stage_k_package_sha256"]:
        raise ValueError("Stage-K package archive SHA-256 does not match frozen L0 receipt")
    formal_sha = _sha256(formal)
    if formal_sha != expected["formal_template_sha256"]:
        raise ValueError("formal Stage-K feedback SHA-256 does not match frozen L0 receipt")
    formal_relative = "06_feedback/jovi_stage_k_named_feedback.csv"
    if bindings.get(formal_relative) != formal_sha:
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
    if nested_sha != expected["nested_copy_sha256"]:
        raise ValueError("nested diagnostic feedback SHA-256 does not match frozen L0 receipt")
    nested_relative = "s12_stage_k_named_review/06_feedback/jovi_stage_k_named_feedback.csv"
    if nested_relative in bindings or nested_sha in bindings.values():
        raise ValueError("nested diagnostic copy unexpectedly appears in canonical SHA256SUMS")
    text_path = Path(named_text_feedback_path).resolve()
    if not text_path.is_file():
        raise ValueError("cannot read named Stage-L text feedback: missing file")
    text_sha = _sha256(text_path)
    try:
        feedback = json.loads(text_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read named Stage-L text feedback") from exc
    if feedback.get("human_pass") is not False:
        raise ValueError("named text feedback human_pass must remain false")
    if feedback.get("feedback_scope") != "named_engineering_direction":
        raise ValueError("named text feedback feedback_scope must remain named_engineering_direction")
    if text_sha != expected["named_text_feedback_sha256"]:
        raise ValueError("named Stage-L text feedback SHA-256 does not match frozen L0 receipt")
    formal_status = "UNSUBMITTED_TEMPLATE"
    nested_status = "INVALID_UNBOUND_DIAGNOSTIC_COPY"
    if formal_status != expected["formal_template_status"] or nested_status != expected["nested_copy_status"]:
        raise ValueError("computed feedback statuses do not match frozen L0 receipt")
    if feedback.get("feedback_scope") != expected["feedback_scope"] or feedback.get("human_pass") is not expected["human_pass"]:
        raise ValueError("named text feedback status does not match frozen L0 receipt")
    return StageLFeedbackReceipt(
        archive_sha, formal_sha, formal_status, nested_sha,
        nested_status, text_sha,
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


def _parse_sha256sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError("cannot read canonical SHA256SUMS") from exc
    entries: dict[str, str] = {}
    pattern = re.compile(r"^([0-9A-Fa-f]{64})  ([^\r\n]+)$")
    for line_number, line in enumerate(lines, 1):
        match = pattern.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid SHA256SUMS entry at line {line_number}")
        digest, raw_relative = match.groups()
        relative = raw_relative.replace("\\", "/").lower()
        parts = relative.split("/")
        if not relative or relative.startswith("/") or ":" in parts[0] or any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"unsafe SHA256SUMS path at line {line_number}")
        if relative in entries:
            raise ValueError(f"duplicate SHA256SUMS path at line {line_number}")
        entries[relative] = digest.lower()
    return entries


__all__ = ("StageLFeedbackReceipt", "inspect_stage_l_feedback_inputs")
