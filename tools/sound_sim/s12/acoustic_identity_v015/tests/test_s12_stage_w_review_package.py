"""RED tests for the local Stage-W architecture review package."""

from __future__ import annotations

import json
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import run_hellcat_bakeoff
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.review_package import (
    build_stage_w_review_package,
    validate_stage_w_review_package,
)


def test_review_package_keeps_reference_and_unavailable_paths_fail_closed(tmp_path) -> None:
    bakeoff = tmp_path / "bakeoff"
    package = tmp_path / "package"
    run_hellcat_bakeoff(bakeoff, duration_s=0.25)

    with pytest.raises(ValueError, match="prohibited until candidate selection and R1 qualification"):
        build_stage_w_review_package(bakeoff, package)


def test_review_package_validator_rejects_historical_waiting_audition(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "package_manifest.json").write_text(json.dumps({"status": "WAITING_FOR_JOVI_ARCHITECTURE_REVIEW", "selected_architecture": None, "reference_status": "REFERENCE_POINTER_ONLY"}), encoding="utf-8")
    assert "stale_waiting_audition" in validate_stage_w_review_package(package)
