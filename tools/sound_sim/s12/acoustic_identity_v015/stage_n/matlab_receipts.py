"""Fail-closed validation for real Stage-N MATLAB Desktop execution receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ORDER_FUNCTIONS = ("rpmordermap", "ordertrack", "orderspectrum", "rpmfreqmap")
PSYCHOACOUSTIC_FUNCTIONS = (
    "acousticLoudness",
    "acousticSharpness",
    "acousticRoughness",
    "acousticFluctuation",
    "acousticToneToNoiseRatio",
    "acousticProminenceRatio",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _child(root: Path, candidate: object) -> Path:
    path = Path(str(candidate)).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"MATLAB artifact is outside its declared Stage-N root: {path}") from exc
    return path


def _input_manifest(input_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    manifest_path = input_root / "input_manifest.json"
    manifest = _read_json(manifest_path)
    records = manifest.get("records")
    if manifest.get("status") != "PREPARED_NOT_EXECUTED_IN_MATLAB" or not isinstance(records, list) or len(records) != 8:
        raise ValueError("MATLAB receipt requires exactly eight prepared hash-bound inputs")
    by_vehicle = {str(record.get("vehicle_id")): record for record in records if isinstance(record, dict)}
    if len(by_vehicle) != 8 or "None" in by_vehicle:
        raise ValueError("MATLAB input manifest vehicle identities are invalid")
    for vehicle_id, record in by_vehicle.items():
        mat_path = input_root / str(record.get("mat_file"))
        if not mat_path.is_file() or _sha256(mat_path) != record.get("mat_sha256"):
            raise ValueError(f"MATLAB input SHA mismatch during receipt validation: {vehicle_id}")
    return manifest, by_vehicle, _sha256(manifest_path)


def _project_entries(
    receipt: Mapping[str, Any],
    *,
    input_root: Path,
    output_root: Path,
    input_records: Mapping[str, Mapping[str, Any]],
    metric_filename: str,
    expected_functions: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    raw_entries = receipt.get("project")
    if not isinstance(raw_entries, list) or len(raw_entries) != 8:
        raise ValueError("MATLAB session receipt must contain eight project entries")
    entries: dict[str, dict[str, Any]] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("MATLAB project entry must be an object")
        vehicle_id = str(raw_entry.get("vehicle_id"))
        if vehicle_id not in input_records or vehicle_id in entries:
            raise ValueError(f"unexpected MATLAB project vehicle: {vehicle_id}")
        input_path = _child(input_root, raw_entry.get("input_file"))
        expected = input_root / str(input_records[vehicle_id]["mat_file"])
        if input_path != expected.resolve():
            raise ValueError(f"MATLAB project input does not match the immutable manifest: {vehicle_id}")
        if raw_entry.get("status") != "EXECUTED_ON_PROJECT_DATA":
            raise ValueError(f"MATLAB project execution did not succeed: {vehicle_id}")
        vehicle_root = _child(output_root, raw_entry.get("output_directory"))
        metric_path = vehicle_root / metric_filename
        metrics = _read_json(metric_path)
        availability = metrics.get("function_availability")
        if metrics.get("status") != "EXECUTED_ON_PROJECT_DATA" or not isinstance(availability, dict):
            raise ValueError(f"MATLAB project metric receipt is invalid: {vehicle_id}")
        if any(availability.get(function) is not True for function in expected_functions):
            raise ValueError(f"MATLAB project function availability is incomplete: {vehicle_id}")
        entries[vehicle_id] = {
            "input_file": input_path.name,
            "input_sha256": _sha256(input_path),
            "metric_path": str(metric_path),
            "metric_sha256": _sha256(metric_path),
            "metrics": metrics.get("metrics"),
            "candidate_sha256": input_records[vehicle_id]["candidate_sha256"],
            "trace_sha256": input_records[vehicle_id]["trace_sha256"],
            "reference_comparison": "REFERENCE_RPM_UNAVAILABLE / ORDER_COMPARISON_NOT_QUALIFIED",
        }
    if set(entries) != set(input_records):
        raise ValueError("MATLAB session receipt does not cover every hash-bound input")
    return dict(sorted(entries.items()))


def validate_order_session(receipt_path: Path, *, input_root: Path, output_root: Path) -> dict[str, Any]:
    """Validate fixture and eight-candidate order execution from a Desktop session."""

    receipt = _read_json(receipt_path)
    _, input_records, manifest_sha = _input_manifest(input_root)
    if receipt.get("schema_version") != "s12-stage-n-matlab-order-session-1":
        raise ValueError("unexpected MATLAB order session schema")
    if receipt.get("reference_status") != "REFERENCE_RPM_UNAVAILABLE":
        raise ValueError("MATLAB order receipt must not claim an external RPM reference")
    if receipt.get("comparison_status") != "ORDER_COMPARISON_NOT_QUALIFIED":
        raise ValueError("MATLAB order receipt must retain the reference-comparison boundary")
    fixture = receipt.get("fixture")
    if not isinstance(fixture, dict) or fixture.get("status") != "VALIDATED":
        raise ValueError("MATLAB order fixture was not validated")
    availability = fixture.get("function_availability")
    validation = fixture.get("fixture_validation")
    if not isinstance(availability, dict) or any(availability.get(function) is not True for function in ORDER_FUNCTIONS):
        raise ValueError("MATLAB order fixture did not invoke every required function")
    if not isinstance(validation, dict) or validation.get("passed") is not True:
        raise ValueError("MATLAB order fixture validation failed")
    fixture_root = _child(output_root, Path(str(fixture.get("order_rpm_map"))).parent)
    fixture_artifacts = {
        name: str(_child(fixture_root, fixture.get(field)))
        for name, field in {
            "map_mat": "order_rpm_map",
            "map_png": "order_rpm_map_png",
            "ridges": "order_ridges",
        }.items()
    }
    if not all(Path(path).is_file() for path in fixture_artifacts.values()):
        raise ValueError("MATLAB order fixture output artifact is missing")
    project = _project_entries(
        receipt,
        input_root=input_root,
        output_root=output_root,
        input_records=input_records,
        metric_filename="order_metrics.json",
        expected_functions=ORDER_FUNCTIONS,
    )
    return {
        "schema_version": "s12-stage-n-matlab-order-validation-1",
        "status": "VALIDATED",
        "matlab_release": fixture.get("matlab_release"),
        "fixture_validated": True,
        "vehicle_data_executed": True,
        "vehicle_count": len(project),
        "input_manifest_sha256": manifest_sha,
        "session_receipt_path": str(receipt_path),
        "session_receipt_sha256": _sha256(receipt_path),
        "fixture": {
            "validation": validation,
            "artifacts": fixture_artifacts,
        },
        "vehicles": project,
        "reference_status": "REFERENCE_RPM_UNAVAILABLE",
        "order_comparison_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "limitation": "Order maps use the current candidate PCM with its hash-bound synthetic RPM/state trace; no external reference waveform supplies matching RPM/state metadata.",
    }


def validate_psychoacoustic_session(receipt_path: Path, *, input_root: Path, output_root: Path) -> dict[str, Any]:
    """Validate fixture and eight-candidate Audio Toolbox execution from a Desktop session."""

    receipt = _read_json(receipt_path)
    _, input_records, manifest_sha = _input_manifest(input_root)
    if receipt.get("schema_version") != "s12-stage-n-matlab-psychoacoustic-session-1":
        raise ValueError("unexpected MATLAB psychoacoustic session schema")
    fixture = receipt.get("fixture")
    if not isinstance(fixture, dict) or fixture.get("status") != "VALIDATED":
        raise ValueError("MATLAB psychoacoustic fixture was not validated")
    availability = fixture.get("function_availability")
    validation = fixture.get("validation")
    if not isinstance(availability, dict) or any(availability.get(function) is not True for function in PSYCHOACOUSTIC_FUNCTIONS):
        raise ValueError("MATLAB psychoacoustic fixture did not invoke every required function")
    if not isinstance(validation, dict) or validation.get("passed") is not True:
        raise ValueError("MATLAB psychoacoustic fixture validation failed")
    fixture_metric = _child(output_root, fixture.get("output_artifact"))
    if not fixture_metric.is_file():
        raise ValueError("MATLAB psychoacoustic fixture output artifact is missing")
    project = _project_entries(
        receipt,
        input_root=input_root,
        output_root=output_root,
        input_records=input_records,
        metric_filename="matlab_psychoacoustic_metrics.json",
        expected_functions=PSYCHOACOUSTIC_FUNCTIONS,
    )
    return {
        "schema_version": "s12-stage-n-matlab-psychoacoustic-validation-1",
        "status": "VALIDATED",
        "matlab_release": fixture.get("matlab_release"),
        "fixture_validated": True,
        "vehicle_data_executed": True,
        "vehicle_count": len(project),
        "input_manifest_sha256": manifest_sha,
        "session_receipt_path": str(receipt_path),
        "session_receipt_sha256": _sha256(receipt_path),
        "fixture": {
            "validation": validation,
            "metrics": fixture.get("metrics"),
            "metric_path": str(fixture_metric),
            "metric_sha256": _sha256(fixture_metric),
        },
        "vehicles": project,
        "input_calibration": fixture.get("calibration"),
        "limitation": "Digital-domain relative candidate metrics only; no full-scale-to-Pascal calibration, absolute SPL, or real-reference residual is claimed.",
    }


def validate_shared_psychoacoustic_fixture(receipt_path: Path, *, fixture_root: Path, output_root: Path) -> dict[str, Any]:
    """Validate a MATLAB fixture that consumed the exact cross-tool MAT payload."""

    manifest_path = fixture_root / "fixture_manifest.json"
    manifest = _read_json(manifest_path)
    mat_path = fixture_root / str(manifest.get("fixture_mat", ""))
    if manifest.get("fixture_id") != "s12-stage-n-shared-psychoacoustic-fixture-v1" or not mat_path.is_file() or _sha256(mat_path) != manifest.get("fixture_mat_sha256"):
        raise ValueError("shared psychoacoustic fixture manifest/MAT binding is invalid")
    receipt = _read_json(receipt_path)
    if receipt.get("schema_version") != "s12-stage-n-matlab-shared-psychoacoustic-fixture-1" or receipt.get("status") != "VALIDATED":
        raise ValueError("MATLAB shared psychoacoustic fixture was not validated")
    fixture = receipt.get("fixture")
    if not isinstance(fixture, Mapping) or fixture.get("status") != "VALIDATED":
        raise ValueError("MATLAB shared psychoacoustic fixture result is invalid")
    availability = fixture.get("function_availability")
    validation = fixture.get("validation")
    if not isinstance(availability, Mapping) or any(availability.get(function) is not True for function in PSYCHOACOUSTIC_FUNCTIONS):
        raise ValueError("MATLAB shared fixture did not invoke every required Audio Toolbox function")
    if not isinstance(validation, Mapping) or validation.get("passed") is not True:
        raise ValueError("MATLAB shared psychoacoustic fixture direction validation failed")
    output_artifact = _child(output_root, fixture.get("output_artifact"))
    if not output_artifact.is_file():
        raise ValueError("MATLAB shared psychoacoustic fixture output artifact is missing")
    provenance = {
        "fixture_id": manifest["fixture_id"],
        "fixture_manifest_sha256": _sha256(manifest_path),
        "fixture_mat_sha256": _sha256(mat_path),
    }
    raw_provenance = fixture.get("fixture_provenance")
    if not isinstance(raw_provenance, Mapping) or raw_provenance.get("fixture_id") != provenance["fixture_id"] or raw_provenance.get("fixture_mat_sha256") != provenance["fixture_mat_sha256"]:
        raise ValueError("MATLAB shared fixture receipt does not identify the declared MAT payload")
    return {
        "schema_version": "s12-stage-n-matlab-shared-psychoacoustic-validation-1",
        "status": "VALIDATED",
        "fixture": {
            "provenance": provenance,
            "validation": dict(validation),
            "metrics": fixture.get("metrics"),
            "metric_path": str(output_artifact),
            "metric_sha256": _sha256(output_artifact),
        },
        "matlab_release": fixture.get("matlab_release"),
        "fixture_validated": True,
        "vehicle_data_executed": False,
        "vehicle_count": 0,
        "session_receipt_path": str(receipt_path),
        "session_receipt_sha256": _sha256(receipt_path),
        "limitation": "Shared fixture validates cross-tool trends only; it is digital-domain relative and is not an external-reference comparison.",
    }


def attach_shared_fixture_to_project_receipt(project_receipt: Mapping[str, Any], shared_fixture_receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve eight-candidate execution while replacing the legacy fixture with the shared one."""

    if not _project_receipt_valid(project_receipt) or shared_fixture_receipt.get("status") != "VALIDATED":
        raise ValueError("cannot attach an unvalidated shared fixture to the MATLAB project receipt")
    fixture = shared_fixture_receipt.get("fixture")
    if not isinstance(fixture, Mapping):
        raise ValueError("shared fixture payload is invalid")
    merged = dict(project_receipt)
    merged["fixture"] = dict(fixture)
    merged["shared_fixture_receipt_path"] = shared_fixture_receipt.get("session_receipt_path")
    merged["shared_fixture_receipt_sha256"] = shared_fixture_receipt.get("session_receipt_sha256")
    return merged


def _project_receipt_valid(receipt: Mapping[str, Any]) -> bool:
    return bool(
        receipt.get("status") == "VALIDATED"
        and receipt.get("fixture_validated") is True
        and receipt.get("vehicle_data_executed") is True
        and receipt.get("vehicle_count") == 8
        and isinstance(receipt.get("vehicles"), Mapping)
        and len(receipt["vehicles"]) == 8
    )
