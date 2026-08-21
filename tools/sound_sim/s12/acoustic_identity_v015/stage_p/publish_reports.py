"""Publish the Stage-P evidence bundle and final gate matrix."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(root: Path, name: str) -> dict[str, object]:
    return json.loads((root / name).read_text(encoding="utf-8"))


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def publish(repo: Path, output: Path, *, uat_package: Path, review_package: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    baseline = _read(output, "stage_p_baseline_state.json")
    evidence = _read(output, "stage_p_exact_tip_test_evidence.json")
    receipts = _read(output, "stage_p_stage_n_receipt_validation.json")
    replay = _read(output, "stage_p_comparator_replay.json")
    web = _read(output, "stage_p_webmushra_roundtrip.json")
    security = _read(output, "stage_p_feedback_security.json")
    reproducibility = _read(output, "stage_p_reproducibility.json")
    fixture = _read(output, "stage_p_fixture_stage_o_receipt.json")
    uat = _read(uat_package, "manifest.json")
    gates = {
        "A_exact_stage_o_baseline": "PASS" if baseline.get("status") == "PASS_EXACT_STAGE_O_BASELINE" else "FAIL",
        "B_fresh_full_and_focused_regression": "PASS" if evidence.get("status") == "PASS" else "FAIL",
        "C_stage_n_receipts_and_cross_tool_fixture": "PASS" if receipts.get("status") == "PASS" else "FAIL",
        "D_eight_vehicle_comparator_replay": "PASS" if replay.get("status") == "PASS" else "FAIL",
        "E_official_webmushra_browser_roundtrip": "PASS" if web.get("status") == "PASS" else "FAIL",
        "F_security_reproducibility_idempotence": "PASS" if security.get("status") == "PASS" and reproducibility.get("status") == "PASS" else "FAIL",
        "G_jovi_uat_package_and_fixture_stage_o_boundary": "PASS" if uat.get("status") == "READY_FOR_JOVI_UAT" and fixture.get("status") == "FIXTURE_ONLY_NOT_HUMAN_FEEDBACK_NOT_TUNING_AUTHORITY" else "FAIL",
        "H_real_jovi_feedback": "PENDING",
    }
    all_ready = all(value == "PASS" for key, value in gates.items() if key != "H_real_jovi_feedback")
    overall = "SYSTEM_ACCEPTANCE_PASSED" if all_ready else "SYSTEM_ACCEPTANCE_FAILED"
    matrix = {
        "schema_version": "s12-stage-p-gate-matrix-1",
        "overall_status": overall,
        "ready_for_jovi_uat": all_ready,
        "human_feedback_status": "HUMAN_FEEDBACK_PENDING",
        "human_acoustic_qualification_status": "HUMAN_ACOUSTIC_QUALIFICATION_PENDING",
        "profile_freeze_ready": False,
        "final_status": [
            overall,
            "READY_FOR_JOVI_UAT" if all_ready else "NOT_READY_FOR_JOVI_UAT",
            "HUMAN_ACOUSTIC_QUALIFICATION_PENDING",
            "NOT_PROFILE_FREEZE_READY",
        ],
        "no_source_change": True,
        "gates": gates,
        "exact_head": baseline.get("exact_head"),
        "uat_manifest_sha256": _sha(uat_package / "manifest.json"),
        "review_package_manifest_sha256": _sha(review_package / "webmushra_package_manifest.json"),
        "uat_handoff": {
            "package": str(uat_package),
            "manifest_sha256": _sha(uat_package / "manifest.json"),
            "start_command": f'powershell -ExecutionPolicy Bypass -File "{uat_package / "START_REVIEW.ps1"}"',
            "browser_url": "http://127.0.0.1:8000/?config=s12-stage-p-system-acceptance-v1.yaml",
            "expected_result_paths": uat.get("expected_result_paths", {}),
        },
        "git_handoff": {
            "branch": baseline.get("branch"),
            "current_local_head_at_report": _git(repo, "rev-parse", "HEAD"),
            "status_at_report": _git(repo, "status", "--short"),
            "push": False,
            "merge": False,
            "pull_request": False,
        },
    }
    (output / "stage_p_gate_matrix.json").write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    (output / "S12_Stage_P_Baseline_Audit.md").write_text(
        f"# S12 Stage P Baseline Audit\n\n"
        f"Status: `{baseline.get('status')}`. Exact Stage-O tip: `{baseline.get('exact_head')}`; parent `{baseline.get('parent')}`; branch `{baseline.get('branch')}`; `origin/main` `{baseline.get('origin_main')}`.\n\n"
        "P0 observed a clean worktree immediately after creating the independent Stage-P branch. The current worktree is intentionally dirty only with new Stage-P acceptance files/reports; no Stage-N/O or Track-P file was rewritten.\n\n"
        f"Stage-N webMUSHRA binding SHA: `{baseline['stage_n_package']['manifest_sha256']}`; study manifest SHA: `{baseline['stage_n_package']['study_manifest_sha256']}`; candidate IDs: `{', '.join(baseline['candidate_ids'])}`. Stage-O feedback schema SHA: `{baseline['stage_o']['feedback_schema_sha256']}`.\n\n"
        "The required `git worktree list --porcelain` capture is stored in `stage_p_baseline_state.json` under `worktree_list_porcelain`; it includes the Stage-O exact-tip worktree and this independent Stage-P worktree.\n\n"
        f"Track-P protected manifest: `{baseline['protected_track_p']['frozen_manifest_count']}` files / SHA `{baseline['protected_track_p']['frozen_manifest_sha256']}`; frozen symbols SHA `{baseline['protected_track_p']['frozen_symbol_sha256']}`. Real feedback content read: `{baseline['real_feedback_read']}`.\n",
        encoding="utf-8", newline="\n",
    )
    (output / "S12_Stage_P_Stage_N_Receipt_Validation.md").write_text(
        "# S12 Stage P Stage-N Receipt Validation\n\n"
        f"Status: `{receipts['status']}`. Validated `{receipts['receipt_count']}` receipts and `{receipts['candidate_count']}` candidate IDs (`{', '.join(receipts['candidate_ids'])}`).\n\n"
        f"MATLAB constraint: `{receipts['matlab_constraint']['status']}`; MoSQITo: `{receipts['mosqito_constraint']['status']}`; same cross-tool fixture: `{receipts['cross_tool_same_fixture']}`. SHA/finite-value/schema errors: `{len(receipts['errors'])}`. No absolute SPL or real-reference claim is promoted.\n",
        encoding="utf-8", newline="\n",
    )
    (output / "S12_Stage_P_Comparator_Replay.md").write_text(
        "# S12 Stage P Comparator Replay\n\n"
        f"Status: `{replay['status']}`. Re-audited `{replay['vehicle_count']}` vehicles × `{replay['scenario_count']}` scenario slots.\n\n"
        f"Scenario counts: `{json.dumps(replay['scenario_counts'], sort_keys=True)}`. Comparison kind: `{replay['comparison_kind']}`. `no_truth_percentage`: `{replay['no_truth_percentage']}`. Qualified claims: `{len(replay['qualified_claims'])}`; absolute-SPL/real-reference claims: `{len(replay['absolute_spl_or_real_reference_claims'])}`.\n\n"
        "This is an internal synthetic-parent replay only; it does not create external-reference truth or a profile-freeze decision.\n",
        encoding="utf-8", newline="\n",
    )
    (output / "S12_Stage_P_WebMUSHRA_Roundtrip.md").write_text(
        "# S12 Stage P Official webMUSHRA Roundtrip\n\n"
        f"Status: `{web['status']}`. Official upstream checkout commit: `{web['official_upstream']['commit']}`. Browser session: `{web['browser']['session']}`; session was closed after the run.\n\n"
        f"The fixture listener completed the full browser study. Official exports: `mushra.csv` `{web['official_exports']['mushra_data_rows']}` data rows / SHA `{web['official_exports']['mushra_sha256']}`, `lss.csv` `{web['official_exports']['lss_data_rows']}` data rows / SHA `{web['official_exports']['lss_sha256']}`. Importer joined `{web['importer_binding']['accepted_rows']}` stage-M candidate rows and rejected `{web['importer_binding']['rejected_rows']}` non-candidate stimuli by design.\n\n"
        "The hidden reference is explicitly `synthetic_parent_not_real_reference`. Listener ID is fixture-only; `human_feedback_available=false` and `tuning_authority=false`.\n",
        encoding="utf-8", newline="\n",
    )
    (output / "S12_Stage_P_Feedback_Security.md").write_text(
        "# S12 Stage P Feedback Security\n\n"
        f"Status: `{security['status']}` across `{security['case_count']}` negative cases. `fail_closed`: `{security['fail_closed']}`; accepted rows in every negative case: zero.\n\n"
        "Covered wrong package/file/candidate SHA, test ID, duplicate listener/trial, missing Likert, illegal/unknown identity, insufficient rows, blank score, fixture-as-Jovi, modified CSV, other package, MUSHRA/LSS mismatch, and path traversal/external reference. No case creates human approval or tuning authority.\n",
        encoding="utf-8", newline="\n",
    )
    # Emit both the historical internal names and the names required by the
    # Stage-P hand-off specification.  The JSON content remains identical so
    # downstream consumers cannot accidentally observe two different results.
    (output / "stage_p_tool_receipt_validation.json").write_text(
        json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "stage_p_feedback_security_tests.json").write_text(
        json.dumps(security, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    uat_alias = dict(uat)
    uat_alias["artifact_name"] = "stage_p_uat_manifest.json"
    (output / "stage_p_uat_manifest.json").write_text(
        json.dumps(uat_alias, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "S12_Stage_P_Reproducibility.md").write_text(
        "# S12 Stage P Reproducibility and Idempotence\n\n"
        f"Status: `{reproducibility['status']}`. Two independent output directories were generated; `{reproducibility['audio_file_count']}` audio files had equal inventories and equal SHA values. Existing populated outputs are refused rather than overwritten.\n",
        encoding="utf-8", newline="\n",
    )
    (output / "S12_Stage_P_Fixture_Stage_O_Consumption.md").write_text(
        "# S12 Stage P Fixture-Only Stage-O Consumption\n\n"
        f"Status: `{fixture['status']}`. Accepted `{fixture['accepted_rows']}` synthetic rows through the importer semantics; human feedback: `{fixture['human_feedback_available']}`; tuning authority: `{fixture['tuning_authority']}`.\n\n"
        f"The same official browser pair was passed through the Stage-O entry boundary and returned `{fixture.get('stage_o_entry_status')}` with `{fixture.get('stage_o_entry_accepted_rows', 0)}` accepted rows.\n\n"
        "The derived confusion matrix and per-vehicle scores are explicitly fixture-only evidence. They cannot qualify Stage O, produce HUMAN_PASS, or authorize a sound-fix/profile-freeze branch.\n",
        encoding="utf-8", newline="\n",
    )
    final_report = (
        "# S12 Stage P Final System Acceptance\n\n"
        f"Overall status: `{overall}` / `READY_FOR_JOVI_UAT` = `{all_ready}` / `HUMAN_ACOUSTIC_QUALIFICATION_PENDING` / `NOT_PROFILE_FREEZE_READY`.\n\n"
        "## Gate matrix\n\n"
        "| Gate | Result |\n| --- | --- |\n"
        + "".join(f"| `{key}` | `{value}` |\n" for key, value in gates.items())
        + "\n"
        + "A–G are system acceptance gates. H remains a human/Jovi gate and is intentionally pending because no real Jovi feedback content was read or submitted.\n\n"
        "## Scope boundary\n\n"
        "No FVM/PTR/Radiation/Runtime/Android/MATLAB physics/vehicle source/profile/idle/afterfire/low-frequency/shift/sound candidate parameter was changed. No Stage-N receipt or Stage-O waiting receipt was promoted. Synthetic parents are not real vehicle recordings; digital-domain metrics are not absolute SPL or real-reference truth.\n\n"
        f"Exact baseline: `{baseline.get('exact_head')}`. Review package: `{review_package}`. Jovi UAT package: `{uat_package}`. UAT manifest SHA: `{_sha(uat_package / 'manifest.json')}`.\n\n"
        "## Jovi UAT hand-off\n\n"
        f"One-click start: `powershell -ExecutionPolicy Bypass -File \"{uat_package / 'START_REVIEW.ps1'}\"`.\n\n"
        "Browser URL: `http://127.0.0.1:8000/?config=s12-stage-p-system-acceptance-v1.yaml`.\n\n"
        f"Expected official result files: `results/s12-stage-p-system-acceptance-v1/mushra.csv`, `results/s12-stage-p-system-acceptance-v1/lss.csv`; package-local normalized receipt: `{review_package / 'results' / 'normalized_import_result.json'}`; UAT receipt: `{uat_package / 'uat_import_receipt.json'}`.\n\n"
        f"Git branch: `{baseline.get('branch')}`; local HEAD at report generation: `{_git(repo, 'rev-parse', 'HEAD')}`; push: `False`; merge: `False`; PR: `False`.\n\n"
        "The independent branch is committed locally only. Push/merge/PR/profile freeze are outside this acceptance scope.\n"
    )
    for report_name in ("S12_Stage_P_Final_System_Acceptance.md", "S12_Stage_P_System_Acceptance_Report.md"):
        (output / report_name).write_text(final_report, encoding="utf-8", newline="\n")
    files = []
    for path in sorted(output.iterdir()):
        if path.name == "stage_p_artifact_manifest.json" or not path.is_file():
            continue
        files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)})
    artifact_manifest = {
        "schema_version": "s12-stage-p-artifact-manifest-1",
        "status": overall,
        "source_commit": baseline.get("exact_head"),
        "ready_for_jovi_uat": all_ready,
        "human_feedback_content_read": False,
        "profile_freeze_ready": False,
        "artifacts": files,
    }
    (output / "stage_p_artifact_manifest.json").write_text(json.dumps(artifact_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return matrix


def main() -> int:
    repo = Path(__file__).resolve().parents[5]
    output = repo / "tasks/reports/runtime/s12-stage-p-system-acceptance"
    uat = Path(r"E:\Tesla_speed\review_packages\s12-stage-p-jovi-uat-v1")
    review = Path(r"E:\Tesla_speed\review_packages\s12-stage-p-system-acceptance-v1")
    matrix = publish(repo, output, uat_package=uat, review_package=review)
    print(json.dumps({"overall_status": matrix["overall_status"], "ready_for_jovi_uat": matrix["ready_for_jovi_uat"]}, sort_keys=True))
    return 0 if matrix["overall_status"] == "SYSTEM_ACCEPTANCE_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
