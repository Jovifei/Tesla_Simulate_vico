from __future__ import annotations

import json
from pathlib import Path
import zipfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_h.named_review import build_stage_h_named_review


def test_named_stage_h_package_has_core_files_and_waiting_status(tmp_path: Path) -> None:
    result = build_stage_h_named_review(tmp_path / "named", duration_s=2.0)
    root = Path(result["output_root"])
    assert result["status"] == "WAITING_FOR_JOVI_NAMED_CALIBRATION"
    assert (root / "01_Hellcat" / "01_Hellcat_StageG_Baseline_60s.wav").is_file()
    assert (root / "01_Hellcat" / "02_Hellcat_StageH_Candidate_60s.wav").is_file()
    assert (root / "01_Hellcat" / "03_Hellcat_StageG_BlowerOnly_Acceleration.wav").is_file()
    assert (root / "01_Hellcat" / "04_Hellcat_StageH_BlowerOnly_Acceleration.wav").is_file()
    assert (root / "01_Hellcat" / "05_Hellcat_StageH_ExhaustOnly_Acceleration.wav").is_file()
    assert (root / "02_Anchor_Mapping" / "Ferrari_458_StageG_Unchanged_60s.wav").is_file()
    assert (root / "02_Anchor_Mapping" / "RX7_FD_StageG_Unchanged_60s.wav").is_file()
    assert (root / "04_Feedback" / "Jovi_Stage_H_Named_Feedback.csv").read_text(encoding="utf-8").splitlines().__len__() == 8
    artifact = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert artifact["sealed_key_read"] is False
    with zipfile.ZipFile(root / "S12_Stage_H_Named_Review.zip") as archive:
        names = archive.namelist()
        assert not any("sealed" in name.lower() for name in names)
        assert any(name.endswith("01_Hellcat_StageG_Baseline_60s.wav") for name in names)
