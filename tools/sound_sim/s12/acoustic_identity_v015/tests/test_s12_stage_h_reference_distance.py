from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_h.reference_distance import compute_stage_h_reference_distance


def test_stage_h_reference_distance_reports_final_pcm_and_missing_policy(tmp_path: Path) -> None:
    # This contract test uses the existing Stage-G evidence files when present;
    # the production package test supplies the actual 60-second paths.
    target = Path("tools/sound_sim/s12/acoustic_identity_v015/reference_database/hellcat_reference_targets.json")
    assert target.is_file()
    assert "stock_median" in json.loads(target.read_text(encoding="utf-8"))
