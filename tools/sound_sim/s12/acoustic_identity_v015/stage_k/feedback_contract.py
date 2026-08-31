"""Fail-closed contract for the human Stage-K named review form.

The form is deliberately separate from the anonymous qualification scorer.  It
is an engineering feedback sheet: blank score cells are valid before Jovi's
review, while submitted values can be validated without opening any sealed
package.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping


FEEDBACK_FIELDS = (
    "file_id",
    "vehicle_id",
    "identity_likeness_1_5",
    "low_frequency_weight_1_5",
    "high_frequency_harshness_1_5",
    "shift_naturalness_1_5",
    "deceleration_naturalness_1_5",
    "loudness_balance_1_5",
    "artifact_freedom_1_5",
    "keep_or_change",
    "notes",
)

STAGE_K_REVIEW_VEHICLES = ("hellcat", "c63_w204", "gtr_r35", "lfa")


def write_feedback_template(path: str | Path, rows: Iterable[Mapping[str, object]]) -> Path:
    """Write a deterministic, blank-score feedback form."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FEEDBACK_FIELDS, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            values = {field: str(row.get(field, "")) for field in FEEDBACK_FIELDS}
            # Templates must not smuggle an answer into the package.
            for field in FEEDBACK_FIELDS[2:]:
                values[field] = ""
            writer.writerow(values)
    return destination


def read_feedback_rows(path: str | Path, *, allow_blank: bool = True) -> tuple[dict[str, str], ...]:
    """Read and validate feedback rows; blank templates remain acceptable."""

    source = Path(path)
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FEEDBACK_FIELDS:
            raise ValueError("Stage-K feedback CSV fields do not match the contract")
        rows = tuple({field: str(row.get(field, "")) for field in FEEDBACK_FIELDS} for row in reader)
    if not rows:
        raise ValueError("Stage-K feedback CSV must contain at least one row")
    for row in rows:
        if row["vehicle_id"] not in STAGE_K_REVIEW_VEHICLES:
            raise ValueError(f"unsupported Stage-K feedback vehicle: {row['vehicle_id']!r}")
        if not row["file_id"]:
            raise ValueError("Stage-K feedback file_id must not be blank")
        for field in FEEDBACK_FIELDS[2:9]:
            if not row[field] and allow_blank:
                continue
            try:
                value = int(row[field])
            except ValueError as exc:
                raise ValueError(f"{field} must be an integer from 1 to 5") from exc
            if value < 1 or value > 5:
                raise ValueError(f"{field} must be an integer from 1 to 5")
    return rows


__all__ = ("FEEDBACK_FIELDS", "STAGE_K_REVIEW_VEHICLES", "read_feedback_rows", "write_feedback_template")
