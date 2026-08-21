"""Fail-closed capability records and unified Stage-N comparator results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


TOOL_STATUSES = {
    "RESEARCHED_ONLY",
    "ADAPTER_IMPLEMENTED",
    "EXECUTED_ON_FIXTURE",
    "EXECUTED_ON_PROJECT_DATA",
    "VALIDATED",
    "BLOCKED",
    "OPTIONAL_NOT_INSTALLED",
}

_REQUIRED_FIELDS = {
    "tool", "version", "license", "installation_mode", "adapter_path", "actually_invoked",
    "fixture_validated", "vehicle_data_executed", "output_artifact", "status", "limitation",
}


def tool_record(tool: str, **overrides: object) -> dict[str, object]:
    """Create a complete conservative capability record for one tool/function."""

    record: dict[str, object] = {
        "tool": tool,
        "version": "not_detected",
        "license": "not_recorded",
        "installation_mode": "not_installed",
        "adapter_path": "not_implemented",
        "actually_invoked": False,
        "fixture_validated": False,
        "vehicle_data_executed": False,
        "output_artifact": None,
        "status": "RESEARCHED_ONLY",
        "limitation": "no real invocation receipt",
    }
    record.update(overrides)
    return record


def validate_tool_record(record: Mapping[str, object]) -> None:
    missing = _REQUIRED_FIELDS.difference(record)
    if missing:
        raise ValueError(f"missing tool record fields: {sorted(missing)}")
    status = record["status"]
    if status not in TOOL_STATUSES:
        raise ValueError(f"unsupported tool status: {status}")
    for field in ("actually_invoked", "fixture_validated", "vehicle_data_executed"):
        if not isinstance(record[field], bool):
            raise ValueError(f"{field} must be bool")
    if status == "VALIDATED" and (not record["actually_invoked"] or not record["fixture_validated"]):
        raise ValueError("VALIDATED requires a real invocation and a validated fixture")
    if record["actually_invoked"] and not record["output_artifact"]:
        raise ValueError("an invoked tool requires an output artifact")


def build_unified_results(stage_m: Mapping[str, object], *, human_feedback: Mapping[str, object] | None) -> dict[str, object]:
    """Translate Stage-M internal regression evidence without upgrading it."""

    vehicle_results: dict[str, dict[str, dict[str, object]]] = {}
    vehicles = stage_m.get("vehicles", {})
    if not isinstance(vehicles, Mapping):
        raise ValueError("Stage-M comparator payload must expose vehicles")
    for vehicle_id, prior in sorted(vehicles.items()):
        if not isinstance(prior, Mapping):
            raise ValueError(f"invalid Stage-M record: {vehicle_id}")
        uncertainty = prior.get("uncertainty", {})
        external_missing = bool(uncertainty.get("external_reference_missing", True)) if isinstance(uncertainty, Mapping) else True
        vehicle_results[str(vehicle_id)] = {
            "full_cycle": {
                "reference_availability": "EXTERNAL_REFERENCE_UNAVAILABLE" if external_missing else "EXTERNAL_REFERENCE_PRESENT",
                "rpm_state_alignment": {"status": "REFERENCE_RPM_UNAVAILABLE" if external_missing else "NOT_REEVALUATED"},
                "spectral_residual": prior.get("spectral", {}).get("log_distance") if isinstance(prior.get("spectral"), Mapping) else None,
                "order_identity": {"status": "ORDER_COMPARISON_NOT_QUALIFIED" if external_missing else "NOT_REEVALUATED", "residual": None},
                "idle_residual": {"status": "NOT_QUALIFIED_NO_STATE_WINDOW"},
                "transient_residual": {"status": "NOT_QUALIFIED_NO_STATE_WINDOW"},
                "psychoacoustic_residual": {"status": "BLOCKED_PENDING_PROFESSIONAL_TOOL_RECEIPT"},
                "human_score": None,
                "uncertainty": {"digital_domain_relative_only": True, "external_reference_missing": external_missing},
                "reference_limitation": "Stage-M is synthetic-parent internal regression evidence; external RPM/state metadata is unavailable",
                "radar_axes": {
                    "order_identity": "NOT_QUALIFIED",
                    "spectral_envelope": "INTERNAL_REGRESSION_ONLY",
                    "low_frequency_body": "NOT_QUALIFIED",
                    "high_order_character": "NOT_QUALIFIED",
                    "idle_texture": "NOT_QUALIFIED",
                    "transient_behavior": "NOT_QUALIFIED",
                    "psychoacoustic_match": "BLOCKED",
                    "human_realism": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
                },
            }
        }
    return {
        "schema_version": "s12-stage-n-unified-comparator-1",
        "comparison_kind": "internal_synthetic_parent_regression_only",
        "no_truth_percentage": True,
        "human_feedback_import": human_feedback,
        "vehicles": vehicle_results,
    }


def default_capability_matrix(
    mosqito_receipt: Mapping[str, object] | None,
    *,
    webmushra_output: str | None = None,
    webmushra_fixture_validated: bool = False,
) -> list[dict[str, object]]:
    """Build the N0 matrix using execution receipts rather than assertions."""

    order_functions = ("rpmordermap", "ordertrack", "orderspectrum", "rpmfreqmap")
    psychoacoustic_functions = (
        "acousticLoudness", "acousticSharpness", "acousticRoughness", "acousticFluctuation",
        "acousticToneToNoiseRatio", "acousticProminenceRatio",
    )
    records = [
        *[
            tool_record(
                f"MATLAB Signal Processing Toolbox: {function}",
                version="R2026a executable detected; no safe user-started Desktop session",
                license="MathWorks commercial",
                installation_mode="locally installed, existing-session-only policy",
                adapter_path="tools/sound_sim/s12/acoustic_comparator/matlab/s12_order_analysis.m",
                status="BLOCKED",
                limitation="MATLAB.exe is absent while pre-existing MATLAB-MCP servers are active; Stage N did not start, stop, or reconnect MATLAB.",
            )
            for function in order_functions
        ],
        *[
            tool_record(
                f"MATLAB Audio Toolbox: {function}",
                version="R2026a executable detected; toolbox availability unqueried without safe Desktop session",
                license="MathWorks commercial",
                installation_mode="locally installed, existing-session-only policy",
                adapter_path="tools/sound_sim/s12/acoustic_comparator/matlab/s12_psychoacoustic_analysis.m",
                status="BLOCKED",
                limitation="No safe manually opened MATLAB Desktop session is available; proxy metrics are not substituted.",
            )
            for function in psychoacoustic_functions
        ],
        tool_record(
            "MATLAB Audio Test Bench",
            version="unqueried",
            license="MathWorks commercial",
            installation_mode="not integrated",
            adapter_path="tools/sound_sim/s12/acoustic_comparator/matlab/S12ComparatorPreviewPlugin.m (not created)",
            status="BLOCKED",
            limitation="AUDIO_TEST_BENCH_NOT_INTEGRATED; no audioPlugin bridge exists.",
        ),
        tool_record(
            "Essentia",
            version="not detected",
            license="AGPL-3.0-only",
            installation_mode="optional isolated subprocess only",
            adapter_path="tools/sound_sim/s12/acoustic_comparator/psychoacoustics/essentia_adapter.py",
            status="OPTIONAL_NOT_INSTALLED",
            limitation="Windows Python binding was not installed; it is not a core dependency.",
        ),
        tool_record(
            "ViSQOL",
            version="not detected",
            license="Apache-2.0",
            installation_mode="official google/visqol local-build only",
            adapter_path="tools/sound_sim/s12/acoustic_comparator/perceptual/visqol_adapter.py",
            status="OPTIONAL_NOT_INSTALLED",
            limitation="No official source checkout/build with commit and SHA is available; PyPI installation is prohibited.",
        ),
        tool_record(
            "webMUSHRA",
            version="upstream commit recorded in external tool receipt",
            license="webMUSHRA.js Software License (external upstream)",
            installation_mode="external checkout under approved download directory",
            adapter_path="tools/sound_sim/s12/acoustic_comparator/listening/webmushra_export.py",
            actually_invoked=webmushra_output is not None,
            fixture_validated=webmushra_fixture_validated,
            output_artifact=webmushra_output,
            status="VALIDATED" if webmushra_fixture_validated else "ADAPTER_IMPLEMENTED",
            limitation=(
                "External Docker server served the config/audio and a PHP fixture export was SHA/file-ID imported; it is not human feedback or a real-reference study."
                if webmushra_fixture_validated
                else "Package/config exported; only a confirmed external server/browser smoke can advance its execution status."
            ),
        ),
    ]
    if mosqito_receipt and mosqito_receipt.get("status") == "VALIDATED":
        version = str(mosqito_receipt.get("fixtures", {}).get("base", {}).get("mosqito_version", "receipt version unavailable"))
        records.insert(3, tool_record(
            "MoSQITo",
            version=version,
            license="Apache-2.0 (distribution metadata)",
            installation_mode="isolated Python 3.12 venv at E:/AI_Tools/Other/S12StageN/mosqito-venv",
            adapter_path="tools/sound_sim/s12/acoustic_comparator/psychoacoustics/mosqito_adapter.py",
            actually_invoked=True,
            fixture_validated=True,
            output_artifact="mosqito_validation.json",
            status="VALIDATED",
            limitation="Fixture input is digital-domain relative; it is not calibrated SPL or a real-reference comparison.",
        ))
    else:
        records.insert(3, tool_record(
            "MoSQITo",
            version="not invoked",
            license="Apache-2.0 (distribution metadata)",
            installation_mode="isolated Python venv required",
            adapter_path="tools/sound_sim/s12/acoustic_comparator/psychoacoustics/mosqito_adapter.py",
            status="BLOCKED",
            limitation="No successful versioned MoSQITo fixture receipt was supplied.",
        ))
    for record in records:
        validate_tool_record(record)
    return records


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def write_toolchain_matrix(output_root: Path, records: list[dict[str, object]]) -> dict[str, object]:
    """Write N0 JSON/Markdown evidence and retain commercial tools as references."""

    for record in records:
        validate_tool_record(record)
    payload = {
        "schema_version": "s12-stage-n-toolchain-capability-matrix-1",
        "overall_status": "PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL",
        "real_reference_status": "REAL_REFERENCE_CALIBRATION_BLOCKED",
        "records": records,
        "industry_references": [
            {"tool": name, "status": "INDUSTRY_REFERENCE_NOT_INSTALLED"}
            for name in ("HEAD ArtemiS", "Simcenter Testlab", "BK Connect")
        ],
    }
    _write_json(output_root / "toolchain_capability_matrix.json", payload)
    lines = [
        "# S12 Professional Acoustic Toolchain Matrix", "",
        "`PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL` / `REAL_REFERENCE_CALIBRATION_BLOCKED`.", "",
        "| Tool | Version | Invoked | Fixture validated | Project data | Status | Limitation |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append("| {tool} | {version} | {actually_invoked} | {fixture_validated} | {vehicle_data_executed} | {status} | {limitation} |".format(**record))
    lines.extend(["", "## Industry references", ""])
    lines.extend(f"- `{record['tool']}`: `{record['status']}`." for record in payload["industry_references"])
    _write_text(output_root / "S12_Professional_Acoustic_Toolchain_Matrix.md", "\n".join(lines) + "\n")
    return payload


def withheld_recommendations(unified: Mapping[str, object]) -> dict[str, object]:
    vehicles = unified.get("vehicles", {})
    return {
        "schema_version": "s12-stage-n-parameter-recommendations-1",
        "no_source_change": True,
        "recommendations": [
            {
                "vehicle_id": vehicle_id,
                "state": "WITHHELD",
                "metric_residual": None,
                "parameter_group": None,
                "direction": None,
                "evidence": "no RPM/state-bound external reference and no imported Jovi feedback",
                "confidence": "NONE",
                "side_effect_risk": "unknown without target",
                "no_source_change": True,
            }
            for vehicle_id in sorted(vehicles) if isinstance(vehicles, Mapping)
        ],
    }


def write_artifact_manifest(output_root: Path) -> dict[str, object]:
    """Hash all prior Stage-N outputs; manifest itself is intentionally excluded."""

    artifacts = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            artifacts.append({
                "path": path.relative_to(output_root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            })
    payload = {"schema_version": "s12-stage-n-artifact-manifest-1", "artifacts": artifacts}
    _write_json(output_root / "artifact_manifest.json", payload)
    return payload


def verify_artifact_manifest(output_root: Path) -> list[str]:
    """Return all manifest mismatches; an empty list is the only pass condition."""

    manifest = json.loads((output_root / "artifact_manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for artifact in manifest.get("artifacts", []):
        path = output_root / str(artifact["path"])
        if not path.is_file():
            errors.append(f"missing: {artifact['path']}")
        elif path.stat().st_size != artifact["bytes"]:
            errors.append(f"size: {artifact['path']}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            errors.append(f"sha256: {artifact['path']}")
    return errors


def write_stage_n_report(output_root: Path, matrix: Mapping[str, object], unified: Mapping[str, object], *, webmushra_package: Path) -> None:
    mosqito = next((record for record in matrix["records"] if record["tool"] == "MoSQITo"), None)
    webmushra = next((record for record in matrix["records"] if record["tool"] == "webMUSHRA"), None)
    validated = [record["tool"] for record in matrix["records"] if record["status"] == "VALIDATED"]
    lines = [
        "# S12 Stage N Professional Toolchain Report", "",
        "## Status", "",
        "- `PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL`: MATLAB remains blocked and optional tools are not installed.",
        f"- `PROFESSIONAL_TOOLCHAIN_VALIDATED_ON_FIXTURES`: limited to `{', '.join(validated) or 'none'}`; it is not a claim that every professional tool is validated.",
        "- `PROJECT_CANDIDATES_ANALYZED`: eight Stage-M synthetic-parent candidate records were carried into the unified comparator without upgrading their evidence class.",
        "- `REAL_REFERENCE_ORDER_COMPARISON_BLOCKED`: no lawful external reference contains matching RPM/state metadata.",
        "- `WAITING_FOR_JOVI_HUMAN_FEEDBACK`: no human result content was imported.",
        "- `NOT_PROFILE_FREEZE_READY`.", "",
        "## Tool receipts", "",
        f"- MoSQITo receipt: `{mosqito['output_artifact'] if mosqito else 'unavailable'}`; status `{mosqito['status'] if mosqito else 'BLOCKED'}`.",
        "- MATLAB order and psychoacoustic source adapters are present but were not run because Stage N found no safe user-started Desktop session.",
        "- Audio Test Bench: `AUDIO_TEST_BENCH_NOT_INTEGRATED`; no audioPlugin bridge exists.",
        f"- webMUSHRA package: `{webmushra_package}`; status `{webmushra['status'] if webmushra else 'BLOCKED'}`. Its hidden reference is explicitly a synthetic parent, not a real vehicle reference.",
        "", "## Unified boundary", "",
        f"- Vehicle count: `{len(unified.get('vehicles', {}))}`.",
        "- No aggregate realism/truth percentage is emitted; all absent order comparisons are `ORDER_COMPARISON_NOT_QUALIFIED`.",
        "- Parameter recommendations are withheld and no vehicle source path was changed.",
    ]
    _write_text(output_root / "S12_Stage_N_Professional_Toolchain_Report.md", "\n".join(lines) + "\n")
