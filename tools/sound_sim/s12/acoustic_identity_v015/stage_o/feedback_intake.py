"""Strict Stage-O human-feedback entry gate.

This module only validates provenance and listener metadata.  It never turns
automatic metrics into a human pass and never edits a vehicle source.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from ...acoustic_comparator.listening.webmushra_import import import_webmushra_results

SCHEMA_VERSION = "s12-stage-o-human-feedback-receipt-1"
PLAYBACK_METADATA_FIELDS = (
    "playback_device",
    "windows_volume",
    "playback_endpoint",
    "listening_environment",
    "system_eq_enhancement",
)
NAMED_REQUIRED_FIELDS = frozenset(
    {
        "listener_id",
        "playback_device",
        "windows_volume",
        "playback_endpoint",
        "vehicle_id",
        "scenario",
        "baseline_file",
        "candidate_file",
        "candidate_sha256",
        "package_manifest_sha256",
        "identity_score",
        "realism_score",
        "low_frequency_score",
        "mechanical_score",
        "shift_score",
        "afterfire_score",
        "artifact_score",
        "preference",
        "notes",
    }
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata_missing(metadata: Mapping[str, object] | None) -> list[str]:
    if not isinstance(metadata, Mapping):
        return list(PLAYBACK_METADATA_FIELDS)
    return [field for field in PLAYBACK_METADATA_FIELDS if not str(metadata.get(field, "")).strip()]


def _base_receipt(binding: Mapping[str, object] | None) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "WAITING_FOR_JOVI_FEEDBACK",
        "human_feedback_available": False,
        "human_pass": False,
        "content_read": False,
        "no_source_change": True,
        "binding_manifest_sha256": str(binding.get("package_manifest_sha256", "")) if isinstance(binding, Mapping) else "",
        "required_playback_metadata": list(PLAYBACK_METADATA_FIELDS),
        "promotion_block": "real Jovi submission and separate sound-fix branch are required; automatic metrics cannot produce HUMAN_PASS",
    }


def _source_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path): _sha256(path) for path in paths}


def _known_file_ids(binding: Mapping[str, object]) -> dict[str, str]:
    explicit = binding.get("known_file_ids")
    if isinstance(explicit, Mapping):
        return {str(key): str(value) for key, value in explicit.items()}
    trials = binding.get("trials")
    known: dict[str, str] = {}
    if isinstance(trials, Mapping):
        for trial in trials.values():
            if isinstance(trial, Mapping) and trial.get("candidate_file") and trial.get("candidate_sha256"):
                known[str(trial["candidate_file"])] = str(trial["candidate_sha256"])
    return known


def _validate_named_csv(path: Path, known_file_ids: Mapping[str, str], package_manifest_sha256: str) -> tuple[bool, str, list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return False, "WAITING_FOR_JOVI_NAMED_REVIEW", []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        missing = NAMED_REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"feedback missing required fields: {sorted(missing)}")
        vehicle = str(row["vehicle_id"])
        candidate = str(row["candidate_file"])
        if not vehicle or not candidate or candidate not in known_file_ids:
            raise ValueError("unknown vehicle or candidate file")
        if str(row["candidate_sha256"]) != str(known_file_ids[candidate]):
            raise ValueError("candidate SHA mismatch")
        if str(row["package_manifest_sha256"]) != package_manifest_sha256:
            raise ValueError("package manifest SHA mismatch")
        key = (str(row["listener_id"]), candidate)
        if key in seen:
            raise ValueError("duplicate feedback response")
        seen.add(key)
        for field in NAMED_REQUIRED_FIELDS - {"listener_id", "playback_device", "windows_volume", "playback_endpoint", "vehicle_id", "scenario", "baseline_file", "candidate_file", "candidate_sha256", "package_manifest_sha256", "notes"}:
            if not str(row[field]).strip():
                raise ValueError(f"blank feedback field: {field}")
    return True, "VALID_NAMED_FEEDBACK_REQUIRES_REVIEW", rows


def validate_feedback_entry(
    *,
    binding: Mapping[str, object] | None = None,
    named_csv: Path | None = None,
    mushra_csv: Path | None = None,
    lss_csv: Path | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate a real submission without interpreting it as a human pass.

    With no input paths this deliberately returns a waiting receipt and does
    not read any result file.  Official raw webMUSHRA exports must be supplied
    as a pair; named CSV submissions use the Stage-M schema and binding.
    """

    receipt = _base_receipt(binding)
    supplied = [path for path in (named_csv, mushra_csv, lss_csv) if path is not None]
    if not supplied:
        return receipt
    if named_csv is not None and (mushra_csv is not None or lss_csv is not None):
        raise ValueError("submit either Jovi_Stage_M_Named_Feedback.csv or mushra.csv+lss.csv, not both")
    if mushra_csv is not None and lss_csv is None or lss_csv is not None and mushra_csv is None:
        raise ValueError("official webMUSHRA feedback requires both mushra.csv and lss.csv")
    missing_metadata = _metadata_missing(metadata)
    if missing_metadata:
        return {
            **receipt,
            "status": "REJECTED_MISSING_PLAYBACK_METADATA",
            "rejection_reason": "playback device, Windows volume, endpoint, listening environment, and system EQ/enhancement are required",
            "missing_playback_metadata": missing_metadata,
            "content_read": False,
        }
    if not isinstance(binding, Mapping):
        raise ValueError("feedback validation requires the package binding")

    if named_csv is not None:
        known_file_ids = _known_file_ids(binding)
        accepted, reason, rows = _validate_named_csv(
            named_csv,
            known_file_ids,
            str(binding.get("package_manifest_sha256", "")),
        )
        if not accepted:
            return {
                **receipt,
                "status": "REJECTED_EMPTY_OR_INVALID_NAMED_FEEDBACK",
                "content_read": True,
                "source_format": "Jovi_Stage_M_Named_Feedback.csv",
                "source_sha256": _source_hashes([named_csv]),
                "rejection_reason": reason,
            }
        if any(str(row.get("listener_id", "")).strip().lower() != "jovi" for row in rows):
            return {
                **receipt,
                "status": "REJECTED_LISTENER_ID_NOT_JOVI",
                "content_read": True,
                "source_format": "Jovi_Stage_M_Named_Feedback.csv",
                "source_sha256": _source_hashes([named_csv]),
                "rejection_reason": "every accepted row must explicitly identify Jovi",
            }
        return {
            **receipt,
            "status": "IMPORTED_JOVI_FEEDBACK_PENDING_REVIEW",
            "human_feedback_available": True,
            "content_read": True,
            "source_format": "Jovi_Stage_M_Named_Feedback.csv",
            "source_sha256": _source_hashes([named_csv]),
            "accepted_rows": len(rows),
            "rejected_rows": 0,
            "playback_metadata": dict(metadata),
            "rejection_reason": None,
        }

    raw_receipt = import_webmushra_results(mushra_csv, binding, lss_csv=lss_csv)
    source_paths = [mushra_csv, lss_csv]
    if str(raw_receipt.get("status", "")).startswith("FIXTURE_") or any("fixture" in str(row.get("listener_id", "")).lower() for row in raw_receipt.get("rows", []) if isinstance(row, Mapping)):
        return {
            **receipt,
            "status": "REJECTED_FIXTURE_OR_SYNTHETIC_INPUT",
            "content_read": True,
            "source_format": raw_receipt.get("source_format"),
            "source_sha256": _source_hashes(source_paths),
            "accepted_rows": 0,
            "rejected_rows": int(raw_receipt.get("rejected_rows", 0)),
            "rejection_reason": "fixture or synthetic result cannot be promoted to Jovi human feedback",
        }
    if raw_receipt.get("accepted_rows") != 0 and any(str(row.get("listener_id", "")).strip().lower() != "jovi" for row in raw_receipt.get("rows", []) if isinstance(row, Mapping)):
        return {
            **receipt,
            "status": "REJECTED_LISTENER_ID_NOT_JOVI",
            "content_read": True,
            "source_format": raw_receipt.get("source_format"),
            "source_sha256": _source_hashes(source_paths),
            "accepted_rows": 0,
            "rejected_rows": int(raw_receipt.get("rejected_rows", 0)),
            "rejection_reason": "every accepted row must explicitly identify Jovi",
        }
    return {
        **receipt,
        "status": "IMPORTED_JOVI_FEEDBACK_PENDING_REVIEW",
        "human_feedback_available": True,
        "content_read": True,
        "source_format": raw_receipt.get("source_format"),
        "source_sha256": _source_hashes(source_paths),
        "accepted_rows": int(raw_receipt.get("accepted_rows", 0)),
        "rejected_rows": int(raw_receipt.get("rejected_rows", 0)),
        "playback_metadata": dict(metadata),
        "rejection_reason": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Stage-O Jovi feedback entry boundary.")
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--named-input", type=Path)
    parser.add_argument("--mushra-input", type=Path)
    parser.add_argument("--lss-input", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    binding = json.loads(args.binding.read_text(encoding="utf-8"))
    metadata = json.loads(args.metadata.read_text(encoding="utf-8")) if args.metadata else None
    receipt = validate_feedback_entry(
        binding=binding,
        named_csv=args.named_input,
        mushra_csv=args.mushra_input,
        lss_csv=args.lss_input,
        metadata=metadata,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
