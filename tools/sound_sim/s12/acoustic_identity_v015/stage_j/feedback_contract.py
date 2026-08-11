"""Fail-closed validation for Jovi's named Stage-J review feedback."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

_VEHICLES = {"c63_w204", "gtr_r35", "lfa"}
_REQUIRED = {"file_id", "vehicle_id", "identity_1_5", "low_frequency_weight_1_5", "high_frequency_harshness_1_5", "artifact_freedom_1_5", "keep_or_change", "notes"}
_SCORES = ("identity_1_5", "low_frequency_weight_1_5", "high_frequency_harshness_1_5", "artifact_freedom_1_5")


def validate_stage_j_feedback(path: str | Path) -> dict[str, Any]:
    feedback_path = Path(path)
    with feedback_path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Stage-J feedback must contain at least one row")
    for row in rows:
        if set(row) != _REQUIRED:
            raise ValueError("Stage-J feedback columns mismatch")
        if row["vehicle_id"] not in _VEHICLES:
            raise ValueError("unknown Stage-J feedback vehicle")
        if not row["file_id"] or row["keep_or_change"] not in ("", "keep", "change"):
            raise ValueError("invalid Stage-J feedback identity fields")
        for name in _SCORES:
            value = row[name].strip()
            if value == "":
                continue
            try:
                score = int(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be 1-5") from exc
            if score < 1 or score > 5:
                raise ValueError(f"{name} must be 1-5")
    complete = all(all(row[name].strip() for name in _SCORES) and row["keep_or_change"].strip() for row in rows)
    return {"status": "REVIEWED" if complete else "WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW", "rows": len(rows), "complete": complete, "path": str(feedback_path.resolve())}


__all__ = ("validate_stage_j_feedback",)
