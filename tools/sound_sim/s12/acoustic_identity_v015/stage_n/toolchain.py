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


def build_unified_results(
    stage_m: Mapping[str, object],
    *,
    human_feedback: Mapping[str, object] | None,
    mosqito_project: Mapping[str, object] | None = None,
    matlab_order: Mapping[str, object] | None = None,
    matlab_psychoacoustic: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Translate Stage-M internal regression evidence without upgrading it."""

    vehicle_results: dict[str, dict[str, dict[str, object]]] = {}
    vehicles = stage_m.get("vehicles", {})
    if not isinstance(vehicles, Mapping):
        raise ValueError("Stage-M comparator payload must expose vehicles")
    project_vehicles = mosqito_project.get("vehicles", {}) if isinstance(mosqito_project, Mapping) else {}
    if not isinstance(project_vehicles, Mapping):
        project_vehicles = {}
    matlab_order_vehicles = matlab_order.get("vehicles", {}) if isinstance(matlab_order, Mapping) else {}
    if not isinstance(matlab_order_vehicles, Mapping):
        matlab_order_vehicles = {}
    matlab_psychoacoustic_vehicles = matlab_psychoacoustic.get("vehicles", {}) if isinstance(matlab_psychoacoustic, Mapping) else {}
    if not isinstance(matlab_psychoacoustic_vehicles, Mapping):
        matlab_psychoacoustic_vehicles = {}
    for vehicle_id, prior in sorted(vehicles.items()):
        if not isinstance(prior, Mapping):
            raise ValueError(f"invalid Stage-M record: {vehicle_id}")
        uncertainty = prior.get("uncertainty", {})
        external_missing = bool(uncertainty.get("external_reference_missing", True)) if isinstance(uncertainty, Mapping) else True
        project_record = project_vehicles.get(str(vehicle_id))
        project_metrics = project_record.get("metrics", {}).get("results") if isinstance(project_record, Mapping) and isinstance(project_record.get("metrics"), Mapping) else None
        matlab_psycho_record = matlab_psychoacoustic_vehicles.get(str(vehicle_id))
        matlab_psycho_metrics = matlab_psycho_record.get("metrics") if isinstance(matlab_psycho_record, Mapping) else None
        matlab_order_record = matlab_order_vehicles.get(str(vehicle_id))
        order_identity = {
            "status": "ORDER_COMPARISON_NOT_QUALIFIED" if external_missing else "NOT_REEVALUATED",
            "residual": None,
        }
        if isinstance(matlab_order_record, Mapping):
            order_identity.update({
                "candidate_order_analysis": "EXECUTED_ON_PROJECT_DATA",
                "candidate_metric_path": matlab_order_record.get("metric_path"),
                "limitation": "Candidate order map uses its hash-bound synthetic RPM/state trace; external reference RPM/state remains unavailable.",
            })
        psychoacoustic = (
            {
                "status": "CANDIDATE_METRICS_AVAILABLE_REFERENCE_COMPARISON_BLOCKED",
                "tools": [
                    name
                    for name, metrics in (
                        ("MoSQITo", project_metrics),
                        ("MATLAB Audio Toolbox", matlab_psycho_metrics),
                    )
                    if isinstance(metrics, Mapping)
                ],
                "candidate_metrics": {
                    name: metrics
                    for name, metrics in (
                        ("mosqito", project_metrics),
                        ("matlab_audio_toolbox", matlab_psycho_metrics),
                    )
                    if isinstance(metrics, Mapping)
                },
                "residual": None,
                "limitation": "no RPM/state-bound external reference is available",
            }
            if isinstance(project_metrics, Mapping) or isinstance(matlab_psycho_metrics, Mapping)
            else {"status": "BLOCKED_PENDING_PROFESSIONAL_TOOL_RECEIPT"}
        )
        vehicle_results[str(vehicle_id)] = {
            "full_cycle": {
                "reference_availability": "EXTERNAL_REFERENCE_UNAVAILABLE" if external_missing else "EXTERNAL_REFERENCE_PRESENT",
                "rpm_state_alignment": {"status": "REFERENCE_RPM_UNAVAILABLE" if external_missing else "NOT_REEVALUATED"},
                "spectral_residual": prior.get("spectral", {}).get("log_distance") if isinstance(prior.get("spectral"), Mapping) else None,
                "order_identity": order_identity,
                "idle_residual": {"status": "NOT_QUALIFIED_NO_STATE_WINDOW"},
                "transient_residual": {"status": "NOT_QUALIFIED_NO_STATE_WINDOW"},
                "psychoacoustic_residual": psychoacoustic,
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
                    "psychoacoustic_match": "REFERENCE_COMPARISON_BLOCKED" if isinstance(project_metrics, Mapping) or isinstance(matlab_psycho_metrics, Mapping) else "BLOCKED",
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


def _matlab_receipt_valid(receipt: Mapping[str, object] | None) -> bool:
    """Only a validated fixture plus all eight project records unlocks MATLAB status."""

    return bool(
        isinstance(receipt, Mapping)
        and receipt.get("status") == "VALIDATED"
        and receipt.get("fixture_validated") is True
        and receipt.get("vehicle_data_executed") is True
        and receipt.get("vehicle_count") == 8
        and isinstance(receipt.get("vehicles"), Mapping)
        and len(receipt["vehicles"]) == 8
    )


def build_cross_tool_validation(
    matlab_psychoacoustic: Mapping[str, object] | None,
    mosqito_fixture: Mapping[str, object] | None,
) -> dict[str, object]:
    """Compare common fixture trends without claiming cross-standard equality."""

    if not _matlab_receipt_valid(matlab_psychoacoustic):
        return {
            "status": "CROSS_TOOL_COMPARISON_BLOCKED",
            "reason": "validated MATLAB psychoacoustic fixture receipt is absent",
        }
    if not isinstance(mosqito_fixture, Mapping) or mosqito_fixture.get("status") != "VALIDATED":
        return {
            "status": "CROSS_TOOL_COMPARISON_BLOCKED",
            "reason": "validated MoSQITo fixture receipt is absent",
        }
    matlab_fixture = matlab_psychoacoustic.get("fixture", {})
    matlab_validation = matlab_fixture.get("validation", {}) if isinstance(matlab_fixture, Mapping) else {}
    mosqito_validation = mosqito_fixture.get("validation", {})
    common_trends = {
        "gain_increases_loudness": {
            "matlab": matlab_validation.get("gain_increases_loudness"),
            "mosqito": mosqito_validation.get("gain_increases_loudness"),
        },
        "high_frequency_increases_sharpness": {
            "matlab": matlab_validation.get("high_frequency_increases_sharpness"),
            "mosqito": mosqito_validation.get("high_frequency_increases_sharpness"),
        },
        "fast_am_increases_roughness": {
            "matlab": matlab_validation.get("fast_am_increases_roughness"),
            "mosqito": mosqito_validation.get("fast_am_increases_roughness"),
        },
        "prominent_tone_reports_tonality": {
            "matlab": matlab_validation.get("prominent_tone_increases_tonality"),
            "mosqito": mosqito_validation.get("prominent_tone_reports_tonality"),
        },
    }
    for trend in common_trends.values():
        trend["agreement"] = trend["matlab"] is True and trend["mosqito"] is True
    matlab_metrics = matlab_fixture.get("metrics", {}) if isinstance(matlab_fixture, Mapping) else {}
    mosqito_metrics = mosqito_fixture.get("fixtures", {})
    metric_differences: dict[str, dict[str, object]] = {}
    for fixture_name, metric_name in (
        ("base", "loudness_sone"),
        ("base", "sharpness_acum"),
        ("base", "roughness_asper"),
        ("prominent_tone", "tone_to_noise_ratio_db"),
    ):
        matlab_value = _nested_metric(matlab_metrics, fixture_name, metric_name)
        mosqito_value = _nested_metric(mosqito_metrics, fixture_name, metric_name)
        metric_differences[f"{fixture_name}.{metric_name}"] = {
            "matlab": matlab_value,
            "mosqito": mosqito_value,
            "difference_matlab_minus_mosqito": (
                matlab_value - mosqito_value
                if isinstance(matlab_value, (int, float)) and isinstance(mosqito_value, (int, float))
                else None
            ),
        }
    passed = all(trend["agreement"] for trend in common_trends.values())
    return {
        "schema_version": "s12-stage-n-cross-tool-validation-1",
        "status": "VALIDATED" if passed else "EXECUTED_ON_FIXTURE",
        "same_fixture_intent": "digital-domain direction fixtures; durations and implementation standards may differ",
        "common_trends": common_trends,
        "metric_differences": metric_differences,
        "passed": passed,
        "limitation": "MATLAB Audio Toolbox and MoSQITo are not expected to be sample-for-sample identical; units and trend agreement are recorded explicitly.",
    }


def _nested_metric(container: object, fixture_name: str, metric_name: str) -> object:
    if not isinstance(container, Mapping):
        return None
    fixture = container.get(fixture_name)
    if not isinstance(fixture, Mapping):
        return None
    results = fixture.get("results") if isinstance(fixture.get("results"), Mapping) else fixture
    return results.get(metric_name) if isinstance(results, Mapping) else None


def default_capability_matrix(
    mosqito_receipt: Mapping[str, object] | None,
    *,
    mosqito_project_receipt: Mapping[str, object] | None = None,
    matlab_order_receipt: Mapping[str, object] | None = None,
    matlab_psychoacoustic_receipt: Mapping[str, object] | None = None,
    webmushra_output: str | None = None,
    webmushra_fixture_validated: bool = False,
) -> list[dict[str, object]]:
    """Build the N0 matrix using execution receipts rather than assertions."""

    order_functions = ("rpmordermap", "ordertrack", "orderspectrum", "rpmfreqmap")
    psychoacoustic_functions = (
        "acousticLoudness", "acousticSharpness", "acousticRoughness", "acousticFluctuation",
        "acousticToneToNoiseRatio", "acousticProminenceRatio",
    )
    order_validated = _matlab_receipt_valid(matlab_order_receipt)
    psychoacoustic_validated = _matlab_receipt_valid(matlab_psychoacoustic_receipt)
    records = [
        *[
            tool_record(
                f"MATLAB Signal Processing Toolbox: {function}",
                version=str(matlab_order_receipt.get("matlab_release")) if order_validated else "R2026a executable detected; no execution receipt",
                license="MathWorks commercial",
                installation_mode="locally installed, existing-session-only policy",
                adapter_path="tools/sound_sim/s12/acoustic_comparator/matlab/s12_order_analysis.m",
                actually_invoked=order_validated,
                fixture_validated=order_validated,
                vehicle_data_executed=order_validated,
                output_artifact="matlab_order_validation.json" if order_validated else None,
                status="VALIDATED" if order_validated else "BLOCKED",
                limitation=(
                    "Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; no external reference RPM/state metadata is available."
                    if order_validated
                    else "No receipt from a user-opened MATLAB Desktop session was supplied; proxy order metrics are not substituted."
                ),
            )
            for function in order_functions
        ],
        *[
            tool_record(
                f"MATLAB Audio Toolbox: {function}",
                version=str(matlab_psychoacoustic_receipt.get("matlab_release")) if psychoacoustic_validated else "R2026a executable detected; no execution receipt",
                license="MathWorks commercial",
                installation_mode="locally installed, existing-session-only policy",
                adapter_path="tools/sound_sim/s12/acoustic_comparator/matlab/s12_psychoacoustic_analysis.m",
                actually_invoked=psychoacoustic_validated,
                fixture_validated=psychoacoustic_validated,
                vehicle_data_executed=psychoacoustic_validated,
                output_artifact="matlab_psychoacoustic_validation.json" if psychoacoustic_validated else None,
                status="VALIDATED" if psychoacoustic_validated else "BLOCKED",
                limitation=(
                    "Fixture plus eight hash-bound synthetic candidates executed in the user-opened Desktop session; metrics are digital-domain relative only."
                    if psychoacoustic_validated
                    else "No receipt from a user-opened MATLAB Desktop session was supplied; proxy psychoacoustic metrics are not substituted."
                ),
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
    project_data_executed = bool(
        isinstance(mosqito_project_receipt, Mapping)
        and mosqito_project_receipt.get("status") == "EXECUTED_ON_PROJECT_DATA"
        and mosqito_project_receipt.get("vehicle_count") == 8
        and isinstance(mosqito_project_receipt.get("vehicles"), Mapping)
        and len(mosqito_project_receipt["vehicles"]) == 8
    )
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
            vehicle_data_executed=project_data_executed,
            output_artifact="mosqito_validation.json; mosqito_project_analysis.json" if project_data_executed else "mosqito_validation.json",
            status="VALIDATED",
            limitation=(
                "Fixture and eight hash-bound synthetic candidates were processed in the digital domain; no absolute SPL or real-reference residual is claimed."
                if project_data_executed
                else "Fixture input is digital-domain relative; it is not calibrated SPL or a real-reference comparison."
            ),
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
    matlab_order = next((record for record in matrix["records"] if record["tool"] == "MATLAB Signal Processing Toolbox: rpmordermap"), None)
    matlab_psychoacoustic = next((record for record in matrix["records"] if record["tool"] == "MATLAB Audio Toolbox: acousticLoudness"), None)
    validated = [record["tool"] for record in matrix["records"] if record["status"] == "VALIDATED"]
    lines = [
        "# S12 Stage N Professional Toolchain Report", "",
        "## Status", "",
        "- `PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL`: professional execution evidence exists only for the recorded tools; optional tools and real-reference calibration remain unavailable.",
        f"- `PROFESSIONAL_TOOLCHAIN_VALIDATED_ON_FIXTURES`: limited to `{', '.join(validated) or 'none'}`; it is not a claim that every professional tool is validated.",
        "- `PROJECT_CANDIDATES_ANALYZED`: eight Stage-M synthetic-parent candidate records were carried into the unified comparator without upgrading their evidence class.",
        "- `REAL_REFERENCE_ORDER_COMPARISON_BLOCKED`: no lawful external reference contains matching RPM/state metadata.",
        "- `WAITING_FOR_JOVI_HUMAN_FEEDBACK`: no human result content was imported.",
        "- `NOT_PROFILE_FREEZE_READY`.", "",
        "## Tool receipts", "",
        f"- MoSQITo receipt: `{mosqito['output_artifact'] if mosqito else 'unavailable'}`; status `{mosqito['status'] if mosqito else 'BLOCKED'}`; project data `{mosqito['vehicle_data_executed'] if mosqito else False}`.",
        f"- MATLAB order receipt: `{matlab_order['output_artifact'] if matlab_order else 'unavailable'}`; status `{matlab_order['status'] if matlab_order else 'BLOCKED'}`; project data `{matlab_order['vehicle_data_executed'] if matlab_order else False}`.",
        f"- MATLAB psychoacoustic receipt: `{matlab_psychoacoustic['output_artifact'] if matlab_psychoacoustic else 'unavailable'}`; status `{matlab_psychoacoustic['status'] if matlab_psychoacoustic else 'BLOCKED'}`; project data `{matlab_psychoacoustic['vehicle_data_executed'] if matlab_psychoacoustic else False}`.",
        "- Audio Test Bench: `AUDIO_TEST_BENCH_NOT_INTEGRATED`; no audioPlugin bridge exists.",
        f"- webMUSHRA package: `{webmushra_package}`; status `{webmushra['status'] if webmushra else 'BLOCKED'}`. Its hidden reference is explicitly a synthetic parent, not a real vehicle reference.",
        "", "## Unified boundary", "",
        f"- Vehicle count: `{len(unified.get('vehicles', {}))}`.",
        "- No aggregate realism/truth percentage is emitted; all absent order comparisons are `ORDER_COMPARISON_NOT_QUALIFIED`.",
        "- Parameter recommendations are withheld and no vehicle source path was changed.",
    ]
    _write_text(output_root / "S12_Stage_N_Professional_Toolchain_Report.md", "\n".join(lines) + "\n")
