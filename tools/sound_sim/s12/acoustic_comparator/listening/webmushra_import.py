"""Validate SHA-bound webMUSHRA result exports without inventing human feedback."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Mapping


def _normalize_raw_webmushra_results(
    mushra_csv: Path,
    lss_csv: Path,
    *,
    binding: Mapping[str, object],
    required: list[str],
    expected_manifest: str,
    trials: Mapping[str, object],
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Join official mushra.csv and lss.csv rows into the SHA-bound import schema."""

    dimensions = [column for column in required if column not in {"listener_id", "anonymous_id", "package_manifest_sha256", "candidate_sha256"}]
    mushra_rows: dict[tuple[str, str], dict[str, str]] = {}
    lss_rows: dict[tuple[str, str], dict[str, str]] = {}
    errors: list[dict[str, object]] = []
    with mushra_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        expected = {"session_test_id", "listener_id", "trial_id", "rating_stimulus", "rating_score"}
        if not expected.issubset(fields):
            raise ValueError("mushra.csv is not an official webMUSHRA MUSHRA export")
        for number, row in enumerate(reader, start=2):
            listener_id = row.get("listener_id", "").strip()
            anonymous_id = row.get("trial_id", "")
            key = (listener_id, anonymous_id)
            if row.get("session_test_id") != binding.get("test_id"):
                errors.append({"source": "mushra.csv", "line": number, "reason": "webmushra_test_id_mismatch"})
            elif not listener_id:
                errors.append({"source": "mushra.csv", "line": number, "reason": "listener_id_empty"})
            elif anonymous_id not in trials:
                errors.append({"source": "mushra.csv", "line": number, "reason": "unknown_trial_id"})
            elif row.get("rating_stimulus") != "stage_m_candidate":
                errors.append({"source": "mushra.csv", "line": number, "reason": "not_stage_m_candidate_rating"})
            elif not row.get("rating_score", "").strip():
                errors.append({"source": "mushra.csv", "line": number, "reason": "rating_score_empty"})
            elif key in mushra_rows:
                errors.append({"source": "mushra.csv", "line": number, "reason": "duplicate_candidate_rating"})
            else:
                mushra_rows[key] = row
    with lss_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        rating_column = "stimuli_rating" if "stimuli_rating" in fields else "stimuli_rating1"
        expected = {"session_test_id", "listener_id", "trial_id", "stimuli", rating_column}
        if not expected.issubset(fields):
            raise ValueError("lss.csv is not an official webMUSHRA single-stimulus Likert export")
        for number, row in enumerate(reader, start=2):
            listener_id = row.get("listener_id", "").strip()
            page_id = row.get("trial_id", "")
            matches = [(anonymous_id, page_id.removeprefix(f"{anonymous_id}_")) for anonymous_id in trials if page_id.startswith(f"{anonymous_id}_")]
            if row.get("session_test_id") != binding.get("test_id"):
                errors.append({"source": "lss.csv", "line": number, "reason": "webmushra_test_id_mismatch"})
            elif not listener_id:
                errors.append({"source": "lss.csv", "line": number, "reason": "listener_id_empty"})
            elif row.get("stimuli") != "stage_m_candidate":
                errors.append({"source": "lss.csv", "line": number, "reason": "not_stage_m_candidate_rating"})
            elif len(matches) != 1 or matches[0][1] not in dimensions:
                errors.append({"source": "lss.csv", "line": number, "reason": "unknown_likert_trial_id"})
            elif not row.get(rating_column, "").strip():
                errors.append({"source": "lss.csv", "line": number, "reason": "likert_rating_empty"})
            else:
                anonymous_id, dimension = matches[0]
                key = (listener_id, anonymous_id)
                if dimension in lss_rows.setdefault(key, {}):
                    errors.append({"source": "lss.csv", "line": number, "reason": "duplicate_likert_dimension"})
                else:
                    lss_rows[key][dimension] = row[rating_column]
    accepted: list[dict[str, str]] = []
    for key, mushra_row in mushra_rows.items():
        ratings = lss_rows.get(key, {})
        missing = [dimension for dimension in dimensions if dimension not in ratings]
        if missing:
            errors.append({"source": "lss.csv", "listener_id": key[0], "anonymous_id": key[1], "reason": "required_likert_dimensions_missing", "dimensions": missing})
            continue
        trial = trials[key[1]]
        if not isinstance(trial, Mapping):
            raise ValueError("invalid webMUSHRA trial binding")
        accepted.append({
            "listener_id": key[0],
            "anonymous_id": key[1],
            "package_manifest_sha256": expected_manifest,
            "candidate_sha256": str(trial.get("candidate_sha256", "")),
            **ratings,
        })
    return accepted, errors


def import_webmushra_results(
    result_csv: Path,
    binding: Mapping[str, object],
    *,
    lss_csv: Path | None = None,
) -> dict[str, object]:
    """Import valid rows and classify their provenance conservatively."""

    required = list(binding.get("required_result_columns", []))
    expected_manifest = str(binding.get("package_manifest_sha256", ""))
    trials = binding.get("trials", {})
    if not isinstance(trials, Mapping) or not expected_manifest:
        raise ValueError("invalid webMUSHRA package binding")
    vehicle_ids = {str(trial.get("vehicle_id")) for trial in trials.values() if isinstance(trial, Mapping)}
    errors: list[dict[str, object]] = []
    accepted: list[dict[str, str]] = []
    if lss_csv is not None:
        accepted, errors = _normalize_raw_webmushra_results(
            result_csv,
            lss_csv,
            binding=binding,
            required=required,
            expected_manifest=expected_manifest,
            trials=trials,
        )
        normalized_rows = accepted
        accepted = []
        for row in normalized_rows:
            if "identity_guess" in required and row.get("identity_guess", "") not in vehicle_ids:
                errors.append({"source": "lss.csv", "listener_id": row.get("listener_id", ""), "anonymous_id": row.get("anonymous_id", ""), "reason": "identity_guess_not_in_study_vehicle_set"})
            elif any(not row.get(column, "").strip() for column in required):
                errors.append({"source": "lss.csv", "listener_id": row.get("listener_id", ""), "anonymous_id": row.get("anonymous_id", ""), "reason": "required_rating_or_binding_field_empty"})
            else:
                accepted.append(row)
        source_format = "webmushra_raw_mushra_and_lss_csv"
    else:
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
        source_format = "sha_bound_normalized_csv" if normalized else "webmushra_raw_mushra_csv"
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
        "source_format": source_format,
        "human_feedback_available": False,
        "promotion_block": "separate Jovi confirmation and a separate sound-fix branch are required",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a SHA-bound webMUSHRA result export.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--lss-input", type=Path, help="official webMUSHRA lss.csv to join with a raw mushra.csv")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    binding = json.loads(arguments.binding.read_text(encoding="utf-8"))
    receipt = import_webmushra_results(arguments.input, binding, lss_csv=arguments.lss_input)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
