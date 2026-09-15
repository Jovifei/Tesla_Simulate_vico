"""AI-1: measured-feedback receipts, append-only journals and strict B eligibility.

No audio processing. A fixed recipe, a human tag, different WAV bytes, or a
status string alone must never qualify a slot labelled 'automatic feedback'.
Hashes detect drift; they are not authentication/signatures of human approval.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

AUTO = "AUTOMATIC_REFERENCE_CLOSED_LOOP"
FIXED = "FIXED_SOURCE_RECIPE_NOT_AUTOMATIC"
SCENES = ("01_afterfire", "02_full_pull", "03_hot_idle", "04_idle_return", "05_lift",
          "06_shift", "07_steady_high", "08_steady_low", "09_steady_mid", "10_tip_in")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


class Journal:
    """Flush one hash-linked event at a time; never overwrite an earlier run."""
    def __init__(self, path: Path):
        self.path, self.sequence, self.previous = path, 0, "0" * 64
        self.stream = path.open("x", encoding="utf-8", newline="\n")

    def append(self, event: str, payload: Mapping[str, Any]) -> dict:
        row = {"sequence": self.sequence, "previous_sha256": self.previous,
               "event": event, "payload": copy.deepcopy(dict(payload))}
        row["sha256"] = hashlib.sha256(canonical(row)).hexdigest()
        self.stream.write(canonical(row).decode("utf-8") + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.previous, self.sequence = row["sha256"], self.sequence + 1
        return row

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def read_journal(path: Path, *, expected_sha256: str | None = None) -> list[dict]:
    if expected_sha256 is not None and sha_file(path) != expected_sha256:
        raise ValueError("journal file digest mismatch")
    previous, rows = "0" * 64, []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        digest = row.pop("sha256")
        if row["sequence"] != len(rows) or row["previous_sha256"] != previous:
            raise ValueError("journal chain/sequence mismatch")
        if hashlib.sha256(canonical(row)).hexdigest() != digest:
            raise ValueError("journal event digest mismatch")
        row["sha256"] = previous = digest
        rows.append(row)
    if not rows:
        raise ValueError("empty journal")
    return rows


def finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def fit_eligibility(result: Mapping[str, Any]) -> dict:
    """Conservative qualification using the existing v1 optimizer receipt.

    This checks measured-history evidence; caller must separately bind all audio
    files, references, numeric/trace receipts and source identity before serving.
    """
    reasons = []
    if result.get("schema") != "s12.stage_ah.reference_feedback.v1":
        reasons.append("NO_MEASURED_FIT_SCHEMA")
    if result.get("status") != "RELATIVE_IMPROVEMENT_VALIDATED":
        reasons.append("NO_VALIDATED_IMPROVEMENT")
    initial, final = result.get("baseline_train_loss"), result.get("selected_train_loss")
    if not finite_number(initial) or not finite_number(final) or not 0 <= final < initial:
        reasons.append("NO_FINITE_TRAIN_IMPROVEMENT")
    history = result.get("history", [])
    if not isinstance(history, list) or len(history) < 2:
        reasons.append("NO_TRIAL_HISTORY")
        history = []
    elif result.get("trial_count") != len(history):
        reasons.append("TRIAL_COUNT_MISMATCH")
    elif [row.get("trial") for row in history] != list(range(len(history))):
        reasons.append("TRIAL_SEQUENCE_MISMATCH")
    accepted = [r for r in history if r.get("decision") == "TRAIN_ACCEPTED"]
    selected = result.get("selected_parameters", {})
    baseline = result.get("baseline_parameters", {})
    if (not selected or set(selected) != set(baseline) or selected == baseline
            or not all(finite_number(x) for x in (*selected.values(), *baseline.values()))):
        reasons.append("NO_VALID_PARAMETER_CHANGE")
    if not accepted or selected not in [r.get("parameters") for r in accepted]:
        reasons.append("SELECTED_PARAMETERS_NOT_ACCEPTED_TRIAL")
    if result.get("validation_used_for_search") is not False:
        reasons.append("VALIDATION_USED_FOR_SEARCH_OR_UNKNOWN")
    a, b = result.get("validation_baseline", {}), result.get("validation_proposed", {})
    if not a or a.keys() != b.keys() or any(not finite_number(x) or x < 0 for x in (*a.values(), *b.values())):
        reasons.append("VALIDATION_MISSING_OR_INVALID")
    elif any(b[k] > a[k] * 1.03 + 1e-10 for k in a):
        reasons.append("VALIDATION_CASE_REGRESSION")
    else:
        groups: dict[str, list[str]] = {}
        records = result.get("reference_cases", [])
        source_sets = {split: {r.get("source_sha256") for r in records if r.get("split") == split}
                       for split in ("train", "validation")}
        if (not all(source_sets.values()) or source_sets["train"] & source_sets["validation"]):
            reasons.append("SOURCE_SPLIT_NOT_INDEPENDENT")
        for r in records:
            if r.get("split") == "validation":
                groups.setdefault(str(r.get("source_sha256")), []).append(r.get("case_id"))
        keys = [k for group in groups.values() for k in group]
        if set(keys) != set(a) or len(keys) != len(a):
            reasons.append("VALIDATION_CASE_BINDING_MISMATCH")
        elif groups:
            before = sum(sum(a[k] for k in ids)/len(ids) for ids in groups.values())/len(groups)
            after = sum(sum(b[k] for k in ids)/len(ids) for ids in groups.values())/len(groups)
            if after > before + 1e-10:
                reasons.append("VALIDATION_MEAN_REGRESSION")
    return {"kind": AUTO if not reasons else "NO_QUALIFIED_AUTOMATIC_B",
            "available": not reasons, "reasons": reasons,
            "trial_count": len(history), "accepted_count": len(accepted),
            "human_status": "NOT_EVALUATED", "promotable": False}
