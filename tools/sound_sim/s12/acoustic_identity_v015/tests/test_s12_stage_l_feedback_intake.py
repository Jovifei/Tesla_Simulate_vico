"""Hash-bound Stage-L feedback intake and human-status boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_l.feedback_intake import inspect_stage_l_feedback_inputs


REPO_ROOT = Path(__file__).resolve().parents[5]
PACKAGE_ROOT = Path(r"E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1")
TEXT_FEEDBACK = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-l-hellcat-calibration-v1" / "stage_l_jovi_feedback_intake.json"


def test_blank_formal_template_and_invalid_nested_copy_are_classified_without_human_promotion() -> None:
    receipt = inspect_stage_l_feedback_inputs(PACKAGE_ROOT, TEXT_FEEDBACK)
    assert receipt.stage_k_package_sha256 == "d81bc9e77276bf6066c73bf3444239800067f1a1545f43460061c37bd88fdeef"
    assert receipt.formal_template_sha256 == "de55eb154e05530f2905aa0cfc5c247ee7d6f81158119cb2a8fe2535e60f374e"
    assert receipt.formal_template_status == "UNSUBMITTED_TEMPLATE"
    assert receipt.nested_copy_sha256 == "88f9636511233c04014b848bdc4a9c2cb49b188d23f964bbf3c337c1783faf95"
    assert receipt.nested_copy_status == "INVALID_UNBOUND_DIAGNOSTIC_COPY"
    assert receipt.named_text_feedback_sha256 == "0f8e55cd4020d43e23b773d3844057444fda8fab5efa4b0b779e892fc976ca70"
    assert receipt.feedback_scope == "named_engineering_direction"
    assert receipt.human_pass is False


def test_nested_diagnostic_tree_cannot_be_supplied_as_the_formal_package_root() -> None:
    nested_root = PACKAGE_ROOT / "S12_Stage_K_Named_Review"
    with pytest.raises(ValueError, match="canonical|package|ZIP"):
        inspect_stage_l_feedback_inputs(nested_root, TEXT_FEEDBACK)


def test_named_text_feedback_cannot_claim_human_pass(tmp_path: Path) -> None:
    payload = json.loads(TEXT_FEEDBACK.read_text(encoding="utf-8"))
    payload["human_pass"] = True
    bad = tmp_path / "feedback.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="human_pass"):
        inspect_stage_l_feedback_inputs(PACKAGE_ROOT, bad)

def test_named_text_feedback_scope_is_exact(tmp_path: Path) -> None:
    payload = json.loads(TEXT_FEEDBACK.read_text(encoding="utf-8"))
    payload["feedback_scope"] = "formal_human_score"
    bad = tmp_path / "feedback.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="feedback_scope"):
        inspect_stage_l_feedback_inputs(PACKAGE_ROOT, bad)
