"""Explicit Stage-N publisher; it writes a new runtime root and study package only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping

from tools.sound_sim.s12.acoustic_comparator.listening.webmushra_export import export_webmushra_study
from tools.sound_sim.s12.acoustic_identity_v015.stage_n.toolchain import (
    build_cross_tool_validation,
    build_unified_results,
    default_capability_matrix,
    verify_artifact_manifest,
    withheld_recommendations,
    write_artifact_manifest,
    write_stage_n_report,
    write_toolchain_matrix,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_n.matlab_receipts import (
    attach_shared_fixture_to_project_receipt,
    validate_order_session,
    validate_psychoacoustic_session,
    validate_shared_psychoacoustic_fixture,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_n.feedback_closure import prepare_feedback_closure


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _study_trials(stage_m_review_package: Path) -> list[dict[str, object]]:
    manifest = json.loads((stage_m_review_package / "artifact_manifest.json").read_text(encoding="utf-8"))
    trials = []
    for anonymous_id, record in sorted(manifest["vehicles"].items()):
        audition = stage_m_review_package / "vehicles" / anonymous_id / "audition"
        parent = audition / "A_stage_k_parent_audition.wav"
        candidate = audition / "B_stage_m_r1_upstream_candidate_audition.wav"
        if not parent.is_file() or not candidate.is_file():
            raise FileNotFoundError(f"Stage-M audition pair missing for {anonymous_id}")
        trials.append({"anonymous_id": anonymous_id, "vehicle_id": record["vehicle_id"], "scenario": "full_cycle", "parent": parent, "candidate": candidate})
    return trials


def _validated_fixture_import_matches_binding(receipt: object, binding: object) -> bool:
    """Accept fixture evidence only when every accepted row binds this exact study."""

    if not isinstance(receipt, dict) or not isinstance(binding, dict):
        return False
    trials = binding.get("trials")
    expected_manifest = binding.get("package_manifest_sha256")
    rows = receipt.get("rows")
    if (
        receipt.get("status") != "FIXTURE_IMPORT_ONLY_NOT_HUMAN_FEEDBACK"
        or receipt.get("accepted_rows") != 1
        or receipt.get("rejected_rows") != 0
        or not isinstance(trials, dict)
        or not isinstance(expected_manifest, str)
        or not isinstance(rows, list)
        or len(rows) != 1
    ):
        return False
    row = rows[0]
    if not isinstance(row, dict):
        return False
    anonymous_id = row.get("anonymous_id")
    trial = trials.get(anonymous_id) if isinstance(anonymous_id, str) else None
    return bool(
        isinstance(trial, dict)
        and row.get("package_manifest_sha256") == expected_manifest
        and row.get("candidate_sha256") == trial.get("candidate_sha256")
    )


def _prepare_feedback_closure(
    feedback_receipt_path: Path | None,
    package_binding: Mapping[str, object],
    comparator_results: Mapping[str, object],
    *,
    confirmed_by_jovi: bool,
) -> dict[str, object]:
    """Only promote a supplied Jovi receipt through an explicit CLI confirmation."""

    import_receipt: Mapping[str, object] = {}
    if feedback_receipt_path is not None:
        loaded = json.loads(feedback_receipt_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("webMUSHRA feedback receipt must be a JSON object")
        import_receipt = loaded
    return prepare_feedback_closure(
        import_receipt,
        package_binding,
        comparator_results,
        confirmed_by_jovi=confirmed_by_jovi,
    )


def publish(
    output: Path,
    stage_m_runtime: Path,
    stage_m_review_package: Path,
    review_package_root: Path,
    mosqito_receipt_path: Path | None,
    mosqito_project_receipt_path: Path | None,
    matlab_input_root: Path | None,
    matlab_order_receipt_path: Path | None,
    matlab_order_output_root: Path | None,
    matlab_psychoacoustic_receipt_path: Path | None,
    matlab_psychoacoustic_output_root: Path | None,
    shared_fixture_root: Path | None,
    matlab_shared_psychoacoustic_receipt_path: Path | None,
    matlab_shared_psychoacoustic_output_root: Path | None,
    mosqito_shared_fixture_receipt_path: Path | None,
    webmushra_feedback_receipt_path: Path | None,
    confirmed_by_jovi: bool,
    webmushra_upstream_receipt: dict[str, object],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    stage_m = json.loads((stage_m_runtime / "stage_m_comparator_results.json").read_text(encoding="utf-8"))
    if mosqito_receipt_path and mosqito_receipt_path.is_file():
        mosqito = json.loads(mosqito_receipt_path.read_text(encoding="utf-8"))
    else:
        mosqito = None
    if mosqito_project_receipt_path and mosqito_project_receipt_path.is_file():
        mosqito_project = json.loads(mosqito_project_receipt_path.read_text(encoding="utf-8"))
    else:
        mosqito_project = None
    matlab_paths = (
        matlab_input_root,
        matlab_order_receipt_path,
        matlab_order_output_root,
        matlab_psychoacoustic_receipt_path,
        matlab_psychoacoustic_output_root,
    )
    if any(path is not None for path in matlab_paths) and not all(path is not None for path in matlab_paths):
        raise ValueError("MATLAB integration requires the input root plus both receipt/output-root pairs")
    if all(path is not None for path in matlab_paths):
        assert matlab_input_root is not None
        assert matlab_order_receipt_path is not None and matlab_order_output_root is not None
        assert matlab_psychoacoustic_receipt_path is not None and matlab_psychoacoustic_output_root is not None
        matlab_order = validate_order_session(
            matlab_order_receipt_path,
            input_root=matlab_input_root,
            output_root=matlab_order_output_root,
        )
        matlab_psychoacoustic = validate_psychoacoustic_session(
            matlab_psychoacoustic_receipt_path,
            input_root=matlab_input_root,
            output_root=matlab_psychoacoustic_output_root,
        )
    else:
        matlab_order = None
        matlab_psychoacoustic = None
    shared_paths = (
        shared_fixture_root,
        matlab_shared_psychoacoustic_receipt_path,
        matlab_shared_psychoacoustic_output_root,
        mosqito_shared_fixture_receipt_path,
    )
    if any(path is not None for path in shared_paths) and not all(path is not None for path in shared_paths):
        raise ValueError("shared cross-tool validation requires the fixture root, MATLAB receipt/output root, and MoSQITo receipt")
    if all(path is not None for path in shared_paths):
        assert shared_fixture_root is not None
        assert matlab_shared_psychoacoustic_receipt_path is not None and matlab_shared_psychoacoustic_output_root is not None
        assert mosqito_shared_fixture_receipt_path is not None
        matlab_shared = validate_shared_psychoacoustic_fixture(
            matlab_shared_psychoacoustic_receipt_path,
            fixture_root=shared_fixture_root,
            output_root=matlab_shared_psychoacoustic_output_root,
        )
        mosqito_shared = json.loads(mosqito_shared_fixture_receipt_path.read_text(encoding="utf-8"))
        provenance = matlab_shared["fixture"]["provenance"]
        if (
            mosqito_shared.get("status") != "VALIDATED"
            or mosqito_shared.get("shared_fixture_provenance") != provenance
        ):
            raise ValueError("MoSQITo shared fixture receipt does not bind the same validated MAT payload")
        if matlab_psychoacoustic is None:
            raise ValueError("shared cross-tool fixture cannot replace the required eight-candidate MATLAB project receipt")
        matlab_psychoacoustic = attach_shared_fixture_to_project_receipt(matlab_psychoacoustic, matlab_shared)
    else:
        matlab_shared = None
        mosqito_shared = None
    study_manifest = review_package_root / "study_manifest.json"
    package_binding = review_package_root / "webmushra_package_manifest.json"
    if study_manifest.is_file() and package_binding.is_file():
        study = json.loads(study_manifest.read_text(encoding="utf-8"))
    elif review_package_root.exists() and any(review_package_root.iterdir()):
        raise FileExistsError(f"existing webMUSHRA study is incomplete and will not be overwritten: {review_package_root}")
    else:
        study = export_webmushra_study(
            review_package_root,
            _study_trials(stage_m_review_package),
            upstream_receipt=webmushra_upstream_receipt,
            study_id=review_package_root.name,
        )
    binding = json.loads(package_binding.read_text(encoding="utf-8"))
    webmushra_fixture_receipt = output / "webmushra_import_validation.json"
    webmushra_fixture_validated = False
    if webmushra_fixture_receipt.is_file():
        imported = json.loads(webmushra_fixture_receipt.read_text(encoding="utf-8"))
        webmushra_fixture_validated = _validated_fixture_import_matches_binding(imported, binding)
    _write_json(output / "webmushra_package_manifest.json", binding)
    if mosqito is not None:
        _write_json(output / "mosqito_validation.json", mosqito)
    else:
        _write_json(output / "mosqito_validation.json", {"status": "BLOCKED", "reason": "no successful isolated MoSQITo fixture receipt supplied"})
    if mosqito_project is not None:
        _write_json(output / "mosqito_project_analysis.json", mosqito_project)
    if matlab_shared is not None:
        _write_json(output / "matlab_shared_psychoacoustic_validation.json", matlab_shared)
    if mosqito_shared is not None:
        _write_json(output / "mosqito_shared_fixture_validation.json", mosqito_shared)
    _write_json(output / "matlab_order_validation.json", matlab_order or {"status": "BLOCKED", "reason": "no validated MATLAB order session receipt was supplied"})
    _write_json(output / "matlab_psychoacoustic_validation.json", matlab_psychoacoustic or {"status": "BLOCKED", "reason": "no validated MATLAB psychoacoustic session receipt was supplied; proxy metrics are excluded"})
    _write_json(output / "cross_tool_validation.json", build_cross_tool_validation(matlab_psychoacoustic, mosqito_shared))
    matrix = write_toolchain_matrix(
        output,
        default_capability_matrix(
            mosqito,
            mosqito_project_receipt=mosqito_project,
            matlab_order_receipt=matlab_order,
            matlab_psychoacoustic_receipt=matlab_psychoacoustic,
            webmushra_output=str(package_binding),
            webmushra_fixture_validated=webmushra_fixture_validated,
        ),
    )
    base_unified = build_unified_results(
        stage_m,
        human_feedback=None,
        mosqito_project=mosqito_project,
        matlab_order=matlab_order,
        matlab_psychoacoustic=matlab_psychoacoustic,
    )
    feedback_closure = _prepare_feedback_closure(
        webmushra_feedback_receipt_path,
        binding,
        base_unified,
        confirmed_by_jovi=confirmed_by_jovi,
    )
    unified = build_unified_results(
        stage_m,
        human_feedback=feedback_closure,
        mosqito_project=mosqito_project,
        matlab_order=matlab_order,
        matlab_psychoacoustic=matlab_psychoacoustic,
    )
    _write_json(output / "feedback_closure.json", feedback_closure)
    _write_json(output / "comparator_results.json", unified)
    recommendations = withheld_recommendations(unified)
    _write_json(output / "parameter_recommendations.json", recommendations)
    _write_json(output / "stage_n_parameter_recommendations.json", recommendations)
    write_stage_n_report(output, matrix, unified, webmushra_package=review_package_root)
    _write_json(output / "publish_receipt.json", {
        "status": "PUBLISHED_WITH_LIMITATIONS",
        "stage_m_comparator_sha256": _sha(stage_m_runtime / "stage_m_comparator_results.json"),
        "study_manifest_sha256": _sha(review_package_root / "study_manifest.json"),
        "artifact_manifest_verified": True,
        "webmushra_hidden_reference": study["hidden_reference_policy"],
    })
    write_artifact_manifest(output)
    errors = verify_artifact_manifest(output)
    if errors:
        raise RuntimeError(f"Stage-N artifact manifest verification failed: {errors}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish Stage-N professional-comparator evidence.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage-m-runtime", type=Path, required=True)
    parser.add_argument("--stage-m-review-package", type=Path, required=True)
    parser.add_argument("--review-package-root", type=Path, required=True)
    parser.add_argument("--mosqito-receipt", type=Path)
    parser.add_argument("--mosqito-project-receipt", type=Path)
    parser.add_argument("--matlab-input-root", type=Path)
    parser.add_argument("--matlab-order-receipt", type=Path)
    parser.add_argument("--matlab-order-output-root", type=Path)
    parser.add_argument("--matlab-psychoacoustic-receipt", type=Path)
    parser.add_argument("--matlab-psychoacoustic-output-root", type=Path)
    parser.add_argument("--shared-fixture-root", type=Path)
    parser.add_argument("--matlab-shared-psychoacoustic-receipt", type=Path)
    parser.add_argument("--matlab-shared-psychoacoustic-output-root", type=Path)
    parser.add_argument("--mosqito-shared-fixture-receipt", type=Path)
    parser.add_argument("--webmushra-feedback-receipt", type=Path)
    parser.add_argument("--confirm-jovi-feedback", action="store_true")
    parser.add_argument("--webmushra-commit", required=True)
    parser.add_argument("--webmushra-source", type=Path, required=True)
    arguments = parser.parse_args(argv)
    source = arguments.webmushra_source
    publish(
        arguments.output,
        arguments.stage_m_runtime,
        arguments.stage_m_review_package,
        arguments.review_package_root,
        arguments.mosqito_receipt,
        arguments.mosqito_project_receipt,
        arguments.matlab_input_root,
        arguments.matlab_order_receipt,
        arguments.matlab_order_output_root,
        arguments.matlab_psychoacoustic_receipt,
        arguments.matlab_psychoacoustic_output_root,
        arguments.shared_fixture_root,
        arguments.matlab_shared_psychoacoustic_receipt,
        arguments.matlab_shared_psychoacoustic_output_root,
        arguments.mosqito_shared_fixture_receipt,
        arguments.webmushra_feedback_receipt,
        arguments.confirm_jovi_feedback,
        {
            "tool": "webMUSHRA",
            "upstream_repository": "https://github.com/audiolabs/webMUSHRA",
            "commit": arguments.webmushra_commit,
            "source_path": str(source),
            "license_file_sha256": _sha(source / "LICENSE.txt"),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
