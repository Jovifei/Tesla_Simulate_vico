"""Independent Stage-P acceptance, provenance, and fixture-only evidence.

The functions in this module are intentionally read-only with respect to the
vehicle/sound implementation.  They validate existing Stage-N/O artifacts,
exercise the comparator/import boundaries, and write new Stage-P evidence.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from ...acoustic_comparator.listening.webmushra_import import import_webmushra_results
from ..stage_o.feedback_intake import validate_feedback_entry
from .build_package import write_sha256sums

EXPECTED_VEHICLE_IDS = {
    "aventador_lp700",
    "c63_w204",
    "ferrari_458",
    "gtr_r35",
    "hellcat",
    "lfa",
    "rx7_fd",
    "supra_jza80",
}
SCENARIOS = ("full_cycle", "idle", "acceleration", "lift_afterfire", "shift")
EXPECTED_RECEIPTS = (
    "matlab_order_validation.json",
    "matlab_psychoacoustic_validation.json",
    "matlab_shared_psychoacoustic_validation.json",
    "mosqito_validation.json",
    "mosqito_shared_fixture_validation-v2.json",
    "cross_tool_validation.json",
    "toolchain_capability_matrix.json",
    "webmushra_package_manifest.json",
    "webmushra_import_validation.json",
)
HEX64 = set("0123456789abcdef")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        errors.append(path)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            errors.extend(_finite(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_finite(item, f"{path}[{index}]"))
    return errors


def _git(repo: Path, *args: str) -> tuple[int, str, str]:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def baseline_audit(repo: Path, stage_n_package: Path, stage_o_output: Path, output: Path) -> dict[str, Any]:
    """Capture the exact Stage-P baseline and all binding hashes."""

    rc, head, err = _git(repo, "rev-parse", "HEAD")
    if rc:
        raise RuntimeError(f"cannot resolve HEAD: {err}")
    _, parent, _ = _git(repo, "rev-parse", "HEAD^")
    _, branch, _ = _git(repo, "branch", "--show-current")
    _, origin_main, origin_err = _git(repo, "rev-parse", "origin/main")
    _, status, _ = _git(repo, "status", "--porcelain")
    _, remote, _ = _git(repo, "remote", "get-url", "origin")
    binding = _json(stage_n_package / "webmushra_package_manifest.json")
    stage_o_schema = repo / "tools/sound_sim/s12/acoustic_comparator/schemas/human_feedback.schema.json"
    guard = repo / "tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py"
    from ..scripts import assert_track_p_unchanged as guard_module

    protected = {
        "guard_script_sha256": sha256(guard),
        "frozen_manifest_sha256": guard_module.FROZEN_MANIFEST_SHA256,
        "frozen_manifest_count": guard_module.FROZEN_MANIFEST_COUNT,
        "frozen_symbol_sha256": guard_module.FROZEN_SYMBOL_SHA256,
        "frozen_substrings": list(guard_module.FROZEN_SUBSTRINGS),
        "track_s_allowlist_sha256": hashlib.sha256(
            "\n".join(sorted(guard_module.TRACK_S_ALLOWLIST)).encode("utf-8")
        ).hexdigest(),
    }
    audit = {
        "schema_version": "s12-stage-p-baseline-audit-1",
        "status": "PASS" if not status else "FAIL_DIRTY_BASELINE",
        "exact_head": head,
        "parent": parent,
        "branch": branch,
        "origin_main": origin_main,
        "origin_main_resolution_error": origin_err or None,
        "remote_origin": remote,
        "worktree_status_porcelain": status,
        "clean": not bool(status),
        "protected_track_p": protected,
        "stage_n_package": {
            "root": str(stage_n_package),
            "manifest_sha256": sha256(stage_n_package / "webmushra_package_manifest.json"),
            "study_manifest_sha256": sha256(stage_n_package / "study_manifest.json"),
            "test_id": binding.get("test_id"),
            "candidate_ids": sorted(binding.get("trials", {})),
            "candidate_shas": {
                key: value.get("candidate_sha256")
                for key, value in sorted(binding.get("trials", {}).items())
                if isinstance(value, Mapping)
            },
        },
        "stage_o": {
            "output": str(stage_o_output),
            "feedback_receipt_sha256": sha256(stage_o_output / "stage_o_human_feedback_receipt.json"),
            "feedback_schema_sha256": sha256(stage_o_schema),
            "status": _json(stage_o_output / "stage_o_human_feedback_receipt.json").get("status"),
            "human_feedback_available": _json(stage_o_output / "stage_o_human_feedback_receipt.json").get("human_feedback_available"),
        },
        "candidate_ids": sorted(binding.get("trials", {})),
        "candidate_sha_count": len(binding.get("trials", {})),
        "source_change_authorized": False,
        "real_feedback_read": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return audit


def validate_stage_n_receipts(stage_n: Path, stage_m_manifest: Path, package: Path) -> dict[str, Any]:
    """Validate receipt structure, finite values, candidate bindings, and tools."""

    errors: list[str] = []
    receipts: dict[str, Any] = {}
    for name in EXPECTED_RECEIPTS:
        path = stage_n / name
        if not path.is_file():
            errors.append(f"missing:{name}")
            continue
        try:
            value = _json(path)
        except Exception as exc:  # pragma: no cover - evidence diagnostic
            errors.append(f"invalid_json:{name}:{exc}")
            continue
        receipts[name] = value
        if not isinstance(value, Mapping):
            errors.append(f"not_object:{name}")
        if not str(value.get("schema_version", "")).startswith("s12-stage-"):
            errors.append(f"schema_version:{name}")
        errors.extend(f"nonfinite:{name}:{item}" for item in _finite(value))
        for key, item in value.items():
            if key.endswith("sha256") and item is not None:
                text = str(item)
                if len(text) != 64 or any(char not in HEX64 for char in text.lower()):
                    errors.append(f"sha256:{name}:{key}")
    stage_m = _json(stage_m_manifest)
    stage_m_ids = set(stage_m.get("vehicles", {}))
    binding = receipts.get("webmushra_package_manifest.json", {})
    binding_ids = set(binding.get("trials", {})) if isinstance(binding, Mapping) else set()
    if binding_ids != {f"V{i:02d}" for i in range(1, 9)}:
        errors.append(f"candidate_ids:{sorted(binding_ids)}")
    if stage_m_ids != binding_ids:
        errors.append(f"stage_m_binding_ids:{sorted(stage_m_ids)}")
    candidate_sha_matches = []
    if isinstance(binding, Mapping):
        for anonymous_id, trial in sorted(binding.get("trials", {}).items()):
            candidate_sha = str(trial.get("candidate_sha256", "")) if isinstance(trial, Mapping) else ""
            candidate_sha_matches.append(bool(len(candidate_sha) == 64 and set(candidate_sha.lower()) <= HEX64))
    if not all(candidate_sha_matches):
        errors.append("candidate_sha_format")
    comparator = receipts.get("comparator_results.json") or _json(stage_n / "comparator_results.json")
    comparator_ids = set(comparator.get("vehicles", {})) if isinstance(comparator, Mapping) else set()
    if comparator_ids != EXPECTED_VEHICLE_IDS:
        errors.append(f"comparator_vehicle_ids:{sorted(comparator_ids)}")
    tool_matrix = receipts.get("toolchain_capability_matrix.json", {})
    allowed_statuses = {"RESEARCHED_ONLY", "ADAPTER_IMPLEMENTED", "EXECUTED_ON_FIXTURE", "EXECUTED_ON_PROJECT_DATA", "VALIDATED", "BLOCKED", "OPTIONAL_NOT_INSTALLED"}
    tool_records = tool_matrix.get("records", []) if isinstance(tool_matrix, Mapping) else []
    invalid_tool_records = [record.get("tool") for record in tool_records if record.get("status") not in allowed_statuses or not str(record.get("version", ""))]
    if invalid_tool_records:
        errors.append(f"tool_records:{invalid_tool_records}")
    matlab = [receipts.get("matlab_order_validation.json", {}), receipts.get("matlab_psychoacoustic_validation.json", {})]
    if any(item.get("status") != "VALIDATED" or item.get("vehicle_count") != 8 or item.get("fixture_validated") is not True for item in matlab):
        errors.append("matlab_constraints")
    mosqito = receipts.get("mosqito_validation.json", {})
    if mosqito.get("status") != "VALIDATED":
        errors.append("mosqito_status")
    limitation_text = " ".join(
        str(receipts.get(name, {}).get("limitation", ""))
        for name in ("matlab_order_validation.json", "matlab_psychoacoustic_validation.json", "mosqito_validation.json", "cross_tool_validation.json")
    ).lower()
    for required_phrase in ("external reference", "absolute spl", "digital-domain relative"):
        if required_phrase not in limitation_text:
            errors.append(f"limitation_disclosure:{required_phrase}")
    cross = receipts.get("cross_tool_validation.json", {})
    if cross.get("status") != "VALIDATED" or cross.get("passed") is not True or not cross.get("same_fixture_intent"):
        errors.append("cross_tool_status")
    cross_provenance = cross.get("shared_fixture_provenance")
    mos_provenance = receipts.get("mosqito_shared_fixture_validation-v2.json", {}).get("shared_fixture_provenance")
    if cross_provenance != mos_provenance:
        errors.append("cross_tool_fixture_provenance")
    result = {
        "schema_version": "s12-stage-p-stage-n-receipt-validation-1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "receipt_count": len(receipts),
        "candidate_count": len(binding_ids),
        "candidate_ids": sorted(binding_ids),
        "candidate_sha_format_valid": all(candidate_sha_matches) if candidate_sha_matches else False,
        "matlab_constraint": {"status": "PASS" if not any("matlab_constraints" == error for error in errors) else "FAIL", "vehicle_count": 8},
        "mosqito_constraint": {"status": "PASS" if "mosqito_status" not in errors else "FAIL", "status_value": mosqito.get("status")},
        "cross_tool_same_fixture": cross_provenance == mos_provenance and cross.get("passed") is True,
        "real_reference_or_absolute_spl_claim": False,
        "receipts": {name: {"schema_version": value.get("schema_version"), "status": value.get("status")} for name, value in receipts.items()},
        "package_manifest_sha256": sha256(package / "webmushra_package_manifest.json"),
    }
    return result


def comparator_replay(comparator_path: Path, output: Path) -> dict[str, Any]:
    """Re-audit all eight vehicles and five scenario slots from Stage-N output."""

    comparator = _json(comparator_path)
    errors: list[str] = []
    vehicles = comparator.get("vehicles", {}) if isinstance(comparator, Mapping) else {}
    if set(vehicles) != EXPECTED_VEHICLE_IDS:
        errors.append("vehicle_set")
    scenario_counts: Counter[str] = Counter()
    qualified_claims: list[str] = []
    absolute_claims: list[str] = []
    for vehicle_id, record in vehicles.items():
        if not isinstance(record, Mapping):
            errors.append(f"vehicle_record:{vehicle_id}")
            continue
        for scenario in SCENARIOS:
            if scenario not in record:
                errors.append(f"missing_scenario:{vehicle_id}:{scenario}")
                continue
            scenario_counts[scenario] += 1
            payload = record[scenario]
            text = json.dumps(payload, sort_keys=True).lower()
            if "qualified" in text and "not_qualified" not in text and "waiting" not in text and "blocked" not in text:
                qualified_claims.append(f"{vehicle_id}:{scenario}")
            if "absolute spl" in text or "real reference" in text and "unavailable" not in text:
                absolute_claims.append(f"{vehicle_id}:{scenario}")
    result = {
        "schema_version": "s12-stage-p-comparator-replay-1",
        "status": "PASS" if not errors and not qualified_claims and not absolute_claims else "FAIL",
        "errors": errors,
        "vehicle_count": len(vehicles),
        "scenario_count": sum(scenario_counts.values()),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "vehicle_ids": sorted(vehicles),
        "no_truth_percentage": comparator.get("no_truth_percentage") is True,
        "comparison_kind": comparator.get("comparison_kind"),
        "qualified_claims": qualified_claims,
        "absolute_spl_or_real_reference_claims": absolute_claims,
        "human_feedback_available": comparator.get("human_feedback_import", {}).get("human_feedback_available") is True,
        "replay_source_sha256": sha256(comparator_path),
    }
    if result["no_truth_percentage"] is not True:
        result["errors"].append("no_truth_percentage_false")
        result["status"] = "FAIL"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def _normalized_row(binding: Mapping[str, Any], anonymous_id: str, listener: str = "fixture-stage-p") -> dict[str, str]:
    trial = binding["trials"][anonymous_id]
    row = {
        "listener_id": listener,
        "anonymous_id": anonymous_id,
        "package_manifest_sha256": str(binding["package_manifest_sha256"]),
        "candidate_sha256": str(trial["candidate_sha256"]),
        "identity_guess": str(trial["vehicle_id"]),
    }
    for column in binding["required_result_columns"]:
        row.setdefault(column, "50")
    return row


def write_fixture_csv(package: Path, *, name: str = "fixture_stage_p_normalized.csv") -> Path:
    path = package / "results" / name
    if path.exists():
        return path
    binding = _json(package / "webmushra_package_manifest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=binding["required_result_columns"])
        writer.writeheader()
        for anonymous_id in sorted(binding["trials"]):
            writer.writerow(_normalized_row(binding, anonymous_id))
    return path


def fixture_stage_o_consumption(package: Path, output_dir: Path) -> dict[str, Any]:
    """Consume only a synthetic fixture through importer semantics and label every output."""

    binding = _json(package / "webmushra_package_manifest.json")
    fixture_csv = write_fixture_csv(package)
    imported = import_webmushra_results(fixture_csv, binding)
    # Also exercise the real Stage-O entry function with the official browser
    # pair when it is available.  The fixture listener must be rejected there,
    # even though the lower-level importer can retain fixture rows for audit.
    official_mushra = package / "results" / "mushra.csv"
    official_lss = package / "results" / "lss.csv"
    stage_o_entry: dict[str, Any] | None = None
    if official_mushra.is_file() and official_lss.is_file():
        metadata = {field: "fixture" for field in ("playback_device", "windows_volume", "playback_endpoint", "listening_environment", "system_eq_enhancement")}
        stage_o_entry = validate_feedback_entry(binding=binding, mushra_csv=official_mushra, lss_csv=official_lss, metadata=metadata)
    rows = imported.get("rows", [])
    confusion: Counter[tuple[str, str]] = Counter()
    per_vehicle: dict[str, dict[str, float]] = {}
    for row in rows:
        trial = binding["trials"][row["anonymous_id"]]
        actual = str(trial["vehicle_id"])
        guess = str(row["identity_guess"])
        confusion[(actual, guess)] += 1
        per_vehicle[actual] = {
            "vehicle_identity": float(row["vehicle_identity"]),
            "realism": float(row["realism"]),
            "low_frequency_weight": float(row["low_frequency_weight"]),
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "s12-stage-p-fixture-stage-o-consumption-1",
        "status": "FIXTURE_ONLY_NOT_HUMAN_FEEDBACK_NOT_TUNING_AUTHORITY" if imported.get("accepted_rows") == 8 else "FAIL",
        "source_format": imported.get("source_format"),
        "source_path": str(fixture_csv),
        "source_sha256": sha256(fixture_csv),
        "package_manifest_sha256": binding["package_manifest_sha256"],
        "accepted_rows": imported.get("accepted_rows"),
        "rejected_rows": imported.get("rejected_rows"),
        "human_feedback_available": False,
        "human_pass": False,
        "tuning_authority": False,
        "content_read": True,
        "provenance": "synthetic Stage-P fixture; not Jovi and not a real external recording",
        "promotion_block": "explicit Jovi metadata-bound submission and separate sound-fix branch are required",
        "stage_o_entry_status": stage_o_entry.get("status") if stage_o_entry else "NOT_RUN_NO_OFFICIAL_PAIR",
        "stage_o_entry_accepted_rows": stage_o_entry.get("accepted_rows", 0) if stage_o_entry else 0,
    }
    confusion_out = {
        "schema_version": "s12-stage-p-fixture-confusion-matrix-1",
        "status": receipt["status"],
        "human_feedback_available": False,
        "matrix": {f"{actual}->{guess}": count for (actual, guess), count in sorted(confusion.items())},
        "human_pass": False,
    }
    metrics = {
        "schema_version": "s12-stage-p-fixture-metric-binding-1",
        "status": receipt["status"],
        "human_feedback_available": False,
        "tuning_authority": False,
        "per_vehicle_fixture_scores": per_vehicle,
        "metric_source": "synthetic fixture only",
    }
    for name, value in (("stage_p_fixture_stage_o_receipt.json", receipt), ("stage_p_fixture_confusion_matrix.json", confusion_out), ("stage_p_fixture_metric_human_binding.json", metrics)):
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if stage_o_entry is not None:
        (output_dir / "stage_p_fixture_stage_o_entry_receipt.json").write_text(json.dumps(stage_o_entry, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    # Keep a package-local normalized-import receipt alongside the raw CSV pair.
    # It is deliberately labelled fixture-only and never becomes a Stage-O
    # human receipt.  Refresh the package checksum ledger after adding it.
    official_receipt = package / "results" / "browser_import_receipt.json"
    normalized_result = {
        "schema_version": "s12-stage-p-normalized-import-result-1",
        "status": imported.get("status"),
        "source_format": imported.get("source_format"),
        "accepted_rows": imported.get("accepted_rows", 0),
        "rejected_rows": imported.get("rejected_rows", 0),
        "source_receipt": str(official_receipt) if official_receipt.is_file() else None,
        "source_receipt_sha256": sha256(official_receipt) if official_receipt.is_file() else None,
        "human_feedback_available": False,
        "tuning_authority": False,
        "provenance": "Stage-P fixture/import evidence only; not Jovi human feedback",
    }
    (package / "results" / "normalized_import_result.json").write_text(
        json.dumps(normalized_result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    write_sha256sums(package)
    return receipt


def _write_normalized(path: Path, binding: Mapping[str, Any], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=binding["required_result_columns"])
        writer.writeheader()
        writer.writerows(rows)


def secure_normalized_import(path: Path, binding_path: Path, *, allowed_root: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    """P-specific fail-closed wrapper around the Stage-N normalized importer."""

    try:
        resolved_root = allowed_root.resolve()
        resolved_path = path.resolve()
        resolved_binding = binding_path.resolve()
        if resolved_root not in resolved_path.parents:
            return {"accepted_rows": 0, "rejected_rows": 1, "errors": [{"reason": "path_outside_package"}]}
        if resolved_root not in resolved_binding.parents:
            return {"accepted_rows": 0, "rejected_rows": 1, "errors": [{"reason": "binding_outside_package"}]}
        if expected_sha256 is not None and sha256(path) != expected_sha256:
            return {"accepted_rows": 0, "rejected_rows": 1, "errors": [{"reason": "input_sha256_mismatch"}]}
        binding = _json(binding_path)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        seen: set[tuple[str, str]] = set()
        errors: list[dict[str, Any]] = []
        for row in rows:
            key = (str(row.get("listener_id", "")), str(row.get("anonymous_id", "")))
            if key in seen:
                errors.append({"reason": "duplicate_listener_trial"})
            seen.add(key)
        if len(rows) != len(binding.get("trials", {})):
            errors.append({"reason": "insufficient_or_excessive_rows", "expected": len(binding.get("trials", {})), "actual": len(rows)})
        if errors:
            return {"accepted_rows": 0, "rejected_rows": len(errors), "errors": errors}
        receipt = import_webmushra_results(path, binding)
        if receipt.get("accepted_rows") != len(binding.get("trials", {})):
            receipt = {**receipt, "accepted_rows": 0, "status": "REJECTED_FAIL_CLOSED"}
        return receipt
    except Exception as exc:
        return {"accepted_rows": 0, "rejected_rows": 1, "errors": [{"reason": "exception_fail_closed", "detail": str(exc)}]}


def security_matrix(package: Path, output: Path) -> dict[str, Any]:
    """Run fifteen independent negative provenance/security cases."""

    binding_path = package / "webmushra_package_manifest.json"
    binding = _json(binding_path)
    with tempfile.TemporaryDirectory(prefix="s12-stage-p-security-") as temp_name:
        temp = Path(temp_name)
        # Keep each negative fixture inside one isolated package-shaped root so
        # the test reaches the intended SHA/ID checks instead of failing only
        # at the path boundary.
        test_binding_path = temp / "webmushra_package_manifest.json"
        test_binding_path.write_text(binding_path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        base = [_normalized_row(binding, anonymous_id) for anonymous_id in sorted(binding["trials"])]
        expected_input_sha = None
        cases: list[tuple[str, Any]] = []

        def normalized(name: str, rows: list[dict[str, str]], *, expected: str | None = None, root: Path = temp) -> None:
            path = temp / f"{name}.csv"
            _write_normalized(path, binding, rows)
            cases.append((name, lambda path=path, expected=expected, root=root: secure_normalized_import(path, test_binding_path, allowed_root=root, expected_sha256=expected)))

        wrong_sha = [dict(row) for row in base]
        wrong_sha[0]["package_manifest_sha256"] = "0" * 64
        normalized("wrong_package_sha", wrong_sha)
        unknown_file = [dict(row) for row in base]
        unknown_file[0]["anonymous_id"] = "V99"
        normalized("unknown_file_id", unknown_file)
        candidate_sha = [dict(row) for row in base]
        candidate_sha[0]["candidate_sha256"] = "1" * 64
        normalized("candidate_sha", candidate_sha)

        raw_mushra = temp / "mushra.csv"
        raw_lss = temp / "lss.csv"
        raw_mushra.write_text("session_test_id,listener_id,session_uuid,trial_id,rating_stimulus,rating_score\nwrong,fixture,V,V01,stage_m_candidate,50\n", encoding="utf-8")
        raw_lss.write_text("session_test_id,listener_id,trial_id,stimuli_rating,stimuli\nwrong,fixture,V01_vehicle_identity,50,stage_m_candidate\n", encoding="utf-8")
        cases.append(("test_id", lambda: import_webmushra_results(raw_mushra, binding, lss_csv=raw_lss)))

        duplicate = base + [dict(base[0])]
        normalized("duplicate_listener_trial", duplicate)
        missing_likert_mushra = temp / "missing_mushra.csv"
        missing_likert_lss = temp / "missing_lss.csv"
        missing_likert_mushra.write_text("session_test_id,listener_id,session_uuid,trial_id,rating_stimulus,rating_score\n" + f"{binding['test_id']},fixture,V,V01,stage_m_candidate,50\n", encoding="utf-8")
        missing_likert_lss.write_text("session_test_id,listener_id,trial_id,stimuli_rating,stimuli\n" + f"{binding['test_id']},fixture,V01_vehicle_identity,50,stage_m_candidate\n", encoding="utf-8")
        cases.append(("missing_likert", lambda: import_webmushra_results(missing_likert_mushra, binding, lss_csv=missing_likert_lss)))

        illegal_identity = [dict(row) for row in base]
        illegal_identity[0]["identity_guess"] = "not-a-vehicle"
        normalized("illegal_identity", illegal_identity)
        normalized("insufficient_rows", base[:1])
        blank_score = [dict(row) for row in base]
        blank_score[0]["realism"] = ""
        normalized("blank_score", blank_score)

        # A complete named-schema fixture with a non-Jovi listener must be
        # rejected explicitly, rather than being mistaken for a Jovi result.
        fixture_jovi = temp / "fixture_jovi.csv"
        named_fields = [
            "listener_id", "playback_device", "windows_volume", "playback_endpoint",
            "vehicle_id", "scenario", "baseline_file", "candidate_file",
            "candidate_sha256", "package_manifest_sha256", "identity_score",
            "realism_score", "low_frequency_score", "mechanical_score", "shift_score",
            "afterfire_score", "artifact_score", "preference", "notes",
        ]
        named_binding = dict(binding)
        named_binding["known_file_ids"] = {
            f"candidate-{anonymous_id}.wav": str(trial["candidate_sha256"])
            for anonymous_id, trial in binding["trials"].items()
        }
        with fixture_jovi.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=named_fields)
            writer.writeheader()
            for anonymous_id, trial in sorted(binding["trials"].items()):
                writer.writerow({
                    "listener_id": "fixture",
                    "playback_device": "fixture-device",
                    "windows_volume": "fixture-volume",
                    "playback_endpoint": "fixture-endpoint",
                    "vehicle_id": trial["vehicle_id"],
                    "scenario": trial["scenario"],
                    "baseline_file": f"parent-{anonymous_id}.wav",
                    "candidate_file": f"candidate-{anonymous_id}.wav",
                    "candidate_sha256": trial["candidate_sha256"],
                    "package_manifest_sha256": binding["package_manifest_sha256"],
                    "identity_score": "50", "realism_score": "50", "low_frequency_score": "50",
                    "mechanical_score": "50", "shift_score": "50", "afterfire_score": "50",
                    "artifact_score": "50", "preference": "candidate", "notes": "fixture",
                })
        cases.append(("fixture_as_jovi", lambda: validate_feedback_entry(binding=named_binding, named_csv=fixture_jovi, metadata={field: "fixture" for field in ("playback_device", "windows_volume", "playback_endpoint", "listening_environment", "system_eq_enhancement")})))

        original = temp / "modified_original.csv"
        _write_normalized(original, binding, base)
        original_sha = sha256(original)
        modified = temp / "modified_csv.csv"
        modified.write_text(original.read_text(encoding="utf-8").replace(",50,", ",51,", 1), encoding="utf-8")
        cases.append(("modified_csv", lambda: secure_normalized_import(modified, test_binding_path, allowed_root=temp, expected_sha256=original_sha)))

        other_binding = temp / "other_package_binding.json"
        other_binding.write_text(json.dumps({**binding, "package_manifest_sha256": "2" * 64}) + "\n", encoding="utf-8")
        cases.append(("other_package", lambda: secure_normalized_import(temp / "wrong_package_sha.csv", other_binding, allowed_root=temp)))

        mismatch_mushra = temp / "mismatch_mushra.csv"
        mismatch_lss = temp / "mismatch_lss.csv"
        mismatch_mushra.write_text(f"session_test_id,{ 'listener_id'},session_uuid,trial_id,rating_stimulus,rating_score\n{binding['test_id']},fixture,V,V01,stage_m_candidate,50\n", encoding="utf-8")
        mismatch_lss.write_text("session_test_id,listener_id,trial_id,stimuli_rating,stimuli\nother,fixture,V01_vehicle_identity,50,stage_m_candidate\n", encoding="utf-8")
        cases.append(("mushra_lss_mismatch", lambda: import_webmushra_results(mismatch_mushra, binding, lss_csv=mismatch_lss)))

        unknown_vehicle = [dict(row) for row in base]
        unknown_vehicle[0]["identity_guess"] = "unknown_vehicle"
        normalized("unknown_vehicle", unknown_vehicle)

        outside = Path(tempfile.gettempdir()) / "s12-stage-p-external.csv"
        _write_normalized(outside, binding, base)
        cases.append(("path_traversal_external_ref", lambda: secure_normalized_import(outside, binding_path, allowed_root=temp)))

        results: list[dict[str, Any]] = []
        for name, operation in cases:
            try:
                value = operation()
                accepted = int(value.get("accepted_rows", 0)) if isinstance(value, Mapping) else 0
                passed = accepted == 0
                detail = {"accepted_rows": accepted, "status": value.get("status") if isinstance(value, Mapping) else None, "errors": value.get("errors", []) if isinstance(value, Mapping) else []}
            except Exception as exc:  # fail-closed exception is a pass for negative tests
                passed = True
                detail = {"exception": str(exc), "accepted_rows": 0}
            results.append({"case": name, "status": "PASS" if passed else "FAIL", "detail": detail})
    evidence = {
        "schema_version": "s12-stage-p-feedback-security-1",
        "status": "PASS" if all(item["status"] == "PASS" for item in results) and len(results) == 15 else "FAIL",
        "case_count": len(results),
        "cases": results,
        "fail_closed": all(item["status"] == "PASS" for item in results),
        "human_pass": False,
        "tuning_authority": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return evidence


def package_tree_manifest(root: Path) -> list[dict[str, Any]]:
    return [{"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sorted(root.rglob("*")) if path.is_file()]
