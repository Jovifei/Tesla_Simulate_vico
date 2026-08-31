"""Publish Stage-O acceptance and waiting-state evidence without sound edits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .feedback_intake import validate_feedback_entry

OUTPUT_FILES = (
    "S12_Stage_N_Final_Acceptance_Receipt.md",
    "S12_Stage_O_Human_Feedback_Analysis.md",
    "S12_Stage_O_Calibration_Report.md",
    "stage_n_exact_tip_test_evidence.json",
    "stage_o_human_feedback_receipt.json",
    "stage_o_confusion_matrix.json",
    "stage_o_metric_human_binding.json",
    "stage_o_parameter_plan.json",
    "stage_o_round1_results.json",
    "stage_o_round2_results.json",
    "stage_o_round3_results.json",
    "stage_o_gate_matrix.json",
)


def _write_json(root: Path, name: str, value: Any) -> None:
    (root / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_waiting_state(output: Path, binding_path: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    feedback = validate_feedback_entry(binding=binding)
    evidence: dict[str, object] = {
        "schema_version": "s12-stage-n-exact-tip-test-evidence-1",
        "status": "STAGE_N_ACCEPTED",
        "baseline_commit": "e0cf90dc7d10f5bb36d8953ae93eb068ab4382c6",
        "acceptance_commit": "fef513e",
        "acceptance_scope": "governance-only Track-S classification repair; no Track-P file, symbol, or frozen content changed",
        "pre_repair_exact_tip_observation": {
            "status": "INHERITED_GUARD_FALSE_POSITIVE",
            "result": "814 passed, 2 failed, 232 subtests",
            "reason": "Stage-N comparator MATLAB paths and three receipts matched the conservative Track-P matlab substring rule",
        },
        "full_regression": {
            "command": "python -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q",
            "result": "827 passed, 232 subtests passed in 1710.50s",
            "status": "PASS",
        },
        "final_tree_regression": {
            "command": "python -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q",
            "result": "830 passed, 232 subtests passed in 1746.77s",
            "status": "PASS",
            "note": "includes the three Stage-O feedback-entry tests added after the O0 acceptance run",
        },
        "stage_n_focused": {
            "command": "python -m pytest tools/sound_sim/s12/tests/test_s12_stage_n_professional_comparator.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_n_toolchain.py -q",
            "result": "19 passed in 11.20s",
            "status": "PASS",
        },
        "track_p_pytest": {
            "command": "python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_track_p_guard.py -q",
            "result": "32 passed in 2.53s",
            "status": "PASS",
        },
        "track_p_guard": {
            "command": "python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py",
            "result": "180 frozen files / 2 symbols; original manifest SHA matched",
            "status": "PASS",
        },
        "diff_check": {"command": "git diff --check", "status": "PASS"},
        "stage_n_artifact_manifest": {"errors": [], "status": "PASS"},
        "package_validation": {
            "stage_m_wav_reopen": {"wav_count": 24, "finite": True, "clipping": False, "status": "PASS"},
            "stage_n_wav_reopen": {"wav_count": 32, "finite": True, "clipping": False, "status": "PASS"},
            "stage_n_binding_sha": {"missing": [], "mismatches": [], "status": "PASS"},
            "zip_crc_sha": {"status": "NOT_APPLICABLE_NO_ZIP_PRESENT", "note": "no ZIP artifact exists in the preserved Stage-M or Stage-N review packages"},
        },
        "source_change": False,
        "human_feedback_content_read": False,
        "human_pass": False,
        "profile_freeze_ready": False,
    }
    _write_json(output, "stage_n_exact_tip_test_evidence.json", evidence)
    _write_json(output, "stage_o_human_feedback_receipt.json", feedback)
    _write_json(output, "stage_o_confusion_matrix.json", {
        "schema_version": "s12-stage-o-confusion-matrix-1",
        "status": "WAITING_FOR_JOVI_FEEDBACK",
        "human_feedback_available": False,
        "matrix": None,
        "human_pass": False,
    })
    _write_json(output, "stage_o_metric_human_binding.json", {
        "schema_version": "s12-stage-o-metric-human-binding-1",
        "status": "WAITING_FOR_JOVI_FEEDBACK",
        "bindings": [],
        "human_feedback_available": False,
        "no_source_change": True,
    })
    _write_json(output, "stage_o_parameter_plan.json", {
        "schema_version": "s12-stage-o-parameter-plan-1",
        "status": "WITHHELD_WAITING_FOR_JOVI_FEEDBACK",
        "plans": [],
        "no_source_change": True,
    })
    for round_name in ("stage_o_round1_results.json", "stage_o_round2_results.json", "stage_o_round3_results.json"):
        _write_json(output, round_name, {
            "schema_version": "s12-stage-o-round-results-1",
            "status": "NOT_STARTED_WAITING_FOR_JOVI_FEEDBACK",
            "results": [],
            "no_source_change": True,
        })
    _write_json(output, "stage_o_gate_matrix.json", {
        "schema_version": "s12-stage-o-gate-matrix-1",
        "overall_status": "WAITING_FOR_JOVI_FEEDBACK",
        "profile_freeze_ready": False,
        "gates": {
            "O0_exact_tip_acceptance": "PASS",
            "O1_real_feedback_import": "WAITING_FOR_JOVI_FEEDBACK",
            "O2_metric_human_binding": "NOT_STARTED_WAITING_FOR_JOVI_FEEDBACK",
            "O3_repair_scope": "NOT_STARTED_WAITING_FOR_JOVI_FEEDBACK",
            "O4_bounded_tuning": "NOT_STARTED_WAITING_FOR_JOVI_FEEDBACK",
            "O5_listening_package": "NOT_STARTED_WAITING_FOR_JOVI_FEEDBACK",
            "O6_second_feedback": "NOT_STARTED_WAITING_FOR_JOVI_FEEDBACK",
            "O7_approved_profile_candidate": "BLOCKED_NO_HUMAN_PASS",
        },
    })
    (output / "S12_Stage_N_Final_Acceptance_Receipt.md").write_text(
        "# S12 Stage N Final Acceptance Receipt\n\n"
        "Status: `STAGE_N_ACCEPTED` for the exact Stage-N baseline `e0cf90d`.\n\n"
        "The first exact-tip run exposed an inherited Track-P false positive: 11 Stage-N comparator MATLAB/receipt paths were classified by a conservative `matlab` substring rule. The O0 governance repair is limited to an explicit Track-S allowlist and its regression tests/docs (`fef513e`); it preserves the original 180-file/2-symbol frozen manifest and SHA. No Track-P content, Stage-N comparator algorithm, MATLAB receipt, or vehicle source was edited.\n\n"
        "After that classification repair, the O0 S12 suite passed `827 passed / 232 subtests` in `1710.50 s`; Stage-N focused tests passed `19`; Track-P guard tests passed `32`; the independent Track-P guard reported `180 frozen files / 2 symbols` and the Stage-N artifact manifest had zero errors. The final current tree, including the three Stage-O entry tests, passed `830 / 232 subtests` in `1746.77 s`.\n\n"
        "O1 is not started: no real Jovi `mushra.csv`/`lss.csv` or named feedback submission is present. Fixture outputs remain non-human evidence.\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "S12_Stage_O_Human_Feedback_Analysis.md").write_text(
        "# S12 Stage O Human Feedback Analysis\n\n"
        "Status: `WAITING_FOR_JOVI_FEEDBACK`. The entry gate was exercised with no submission paths, so no feedback content was read. The receipt requires package-manifest SHA, candidate SHA, anonymous file ID, test ID, all score dimensions, identity guess, complete non-duplicate rows, listener ID, and playback metadata (device, Windows volume, endpoint, environment, system EQ/enhancement).\n\n"
        "No confusion matrix, human complaint, metric-human binding, or `HUMAN_PASS` is generated. Stage-N fixture rows are explicitly rejected as synthetic evidence.\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "S12_Stage_O_Calibration_Report.md").write_text(
        "# S12 Stage O Calibration Report\n\n"
        "Status: `STAGE_N_ACCEPTED` / `WAITING_FOR_JOVI_FEEDBACK` / `NOT_PROFILE_FREEZE_READY`. O0 is complete after the governance-only Track-S classification repair. O2–O7 are intentionally not started because no real Jovi submission exists.\n\n"
        "No Ferrari, Hellcat, RX-7, or other vehicle source/profile/idle/afterfire/shift/body parameter was changed. No automatic metric is promoted to human approval.\n",
        encoding="utf-8",
        newline="\n",
    )
    files = []
    for path in sorted(output.iterdir()):
        if path.name == "stage_o_artifact_manifest.json" or not path.is_file():
            continue
        files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    manifest = {
        "schema_version": "s12-stage-o-artifact-manifest-1",
        "status": "STAGE_N_ACCEPTED_WAITING_FOR_JOVI_FEEDBACK",
        "source_commit": "e0cf90dc7d10f5bb36d8953ae93eb068ab4382c6",
        "acceptance_commit": "fef513e",
        "human_feedback_content_read": False,
        "source_change": False,
        "artifacts": files,
    }
    _write_json(output, "stage_o_artifact_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish Stage-O waiting-state evidence.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    args = parser.parse_args(argv)
    publish_waiting_state(args.output, args.binding)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
