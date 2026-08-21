"""Validate SHA-bound webMUSHRA result exports without inventing human feedback."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Mapping


def import_webmushra_results(result_csv: Path, binding: Mapping[str, object]) -> dict[str, object]:
    """Import valid rows and classify their provenance conservatively."""

    required = list(binding.get("required_result_columns", []))
    expected_manifest = str(binding.get("package_manifest_sha256", ""))
    trials = binding.get("trials", {})
    if not isinstance(trials, Mapping) or not expected_manifest:
        raise ValueError("invalid webMUSHRA package binding")
    vehicle_ids = {str(trial.get("vehicle_id")) for trial in trials.values() if isinstance(trial, Mapping)}
    errors: list[dict[str, object]] = []
    accepted: list[dict[str, str]] = []
    with result_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        normalized = set(required).issubset(fields)
        raw = {"session_test_id", "listener_id", "trial_id", "rating_stimulus", "rating_score"}.issubset(fields)
        if not normalized and not raw:
            raise ValueError("result must be either SHA-bound normalized CSV or webMUSHRA mushra.csv")
        for number, row in enumerate(reader, start=2):
            if normalized:
                anonymous_id = row.get("anonymous_id", "")
                candidate_sha = row.get("candidate_sha256", "")
                if row.get("package_manifest_sha256") != expected_manifest:
                    errors.append({"line": number, "reason": "package_manifest_sha256_mismatch"})
                elif anonymous_id not in trials:
                    errors.append({"line": number, "reason": "unknown_anonymous_id"})
                elif candidate_sha != str(trials[anonymous_id].get("candidate_sha256", "")):
                    errors.append({"line": number, "reason": "candidate_sha256_mismatch"})
                elif "identity_guess" in required and row.get("identity_guess", "") not in vehicle_ids:
                    errors.append({"line": number, "reason": "identity_guess_not_in_study_vehicle_set"})
                elif any(not row.get(column, "").strip() for column in required):
                    errors.append({"line": number, "reason": "required_rating_or_binding_field_empty"})
                else:
                    accepted.append({column: row[column] for column in required})
                continue
            anonymous_id = row.get("trial_id", "")
            if row.get("session_test_id") != binding.get("test_id"):
                errors.append({"line": number, "reason": "webmushra_test_id_mismatch"})
            elif anonymous_id not in trials:
                errors.append({"line": number, "reason": "unknown_trial_id"})
            elif row.get("rating_stimulus") != "stage_m_candidate":
                errors.append({"line": number, "reason": "not_stage_m_candidate_rating"})
            elif not row.get("rating_score", "").strip():
                errors.append({"line": number, "reason": "rating_score_empty"})
            else:
                accepted.append({
                    "listener_id": row["listener_id"],
                    "anonymous_id": anonymous_id,
                    "package_manifest_sha256": expected_manifest,
                    "candidate_sha256": str(trials[anonymous_id].get("candidate_sha256", "")),
                    "mushra_basic_quality": row["rating_score"],
                })
    fixture_only = bool(accepted) and all("fixture" in row["listener_id"].lower() for row in accepted)
    jovi_submitted = bool(accepted) and all(row["listener_id"].strip().lower() == "jovi" for row in accepted)
    status = "FIXTURE_IMPORT_ONLY_NOT_HUMAN_FEEDBACK" if fixture_only else ("IMPORTED_JOVI_FEEDBACK_PENDING_REVIEW" if jovi_submitted else "IMPORTED_AWAITING_JOVI_CONFIRMATION")
    return {
        "schema_version": "s12-stage-n-webmushra-import-1",
        "status": status,
        "accepted_rows": len(accepted),
        "rejected_rows": len(errors),
        "errors": errors,
        "rows": accepted,
        "source_format": "sha_bound_normalized_csv" if normalized else "webmushra_raw_mushra_csv",
        "human_feedback_available": False,
        "promotion_block": "separate Jovi confirmation and a separate sound-fix branch are required",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a SHA-bound webMUSHRA result export.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    binding = json.loads(arguments.binding.read_text(encoding="utf-8"))
    receipt = import_webmushra_results(arguments.input, binding)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
