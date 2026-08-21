"""Named human-feedback validation without interpreting the listener's answer."""
from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

from .audit import REQUIRED_FEEDBACK_FIELDS, VEHICLES


def validate_named_feedback(rows: Sequence[Mapping[str, object]], known_file_ids: Mapping[str, str] | set[str]) -> dict[str, object]:
    if not rows:
        return {"accepted": False, "reason": "WAITING_FOR_JOVI_NAMED_REVIEW", "content_read": False, "human_pass": False}
    known = set(known_file_ids)
    sha_by_file = known_file_ids if isinstance(known_file_ids, Mapping) else {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        missing = REQUIRED_FEEDBACK_FIELDS - set(row)
        if missing:
            raise ValueError(f"feedback missing required fields: {sorted(missing)}")
        vehicle = row["vehicle_id"]
        candidate = row["candidate_file"]
        if not isinstance(vehicle, str) or vehicle not in VEHICLES:
            raise ValueError("unknown vehicle")
        if not isinstance(candidate, str) or candidate not in known:
            raise ValueError("unknown candidate file")
        if "candidate_sha256" in row and sha_by_file and row["candidate_sha256"] != sha_by_file[candidate]:
            raise ValueError("candidate SHA mismatch")
        key = (str(row["listener_id"]), candidate)
        if key in seen:
            raise ValueError("duplicate feedback response")
        seen.add(key)
        for field in REQUIRED_FEEDBACK_FIELDS - {"listener_id", "playback_device", "windows_volume", "playback_endpoint", "vehicle_id", "scenario", "baseline_file", "candidate_file", "notes"}:
            if row[field] in ("", None):
                raise ValueError(f"blank feedback field: {field}")
    return {"accepted": True, "content_read": True, "human_pass": False, "reason": "VALID_NAMED_FEEDBACK_REQUIRES_REVIEW"}


def validate_named_feedback_csv(path: Path | None, known_file_ids: Mapping[str, str]) -> dict[str, object]:
    if path is None or not path.exists():
        return validate_named_feedback([], known_file_ids)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return validate_named_feedback(list(csv.DictReader(handle)), known_file_ids)
