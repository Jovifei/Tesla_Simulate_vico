import csv
import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_f.package_builder import build_stage_f_package


def test_stage_f_package_contains_real_ab_audio_and_prefilled_forms(tmp_path):
    result = build_stage_f_package(tmp_path / "package", seed=20260810, duration_s=1.0)
    root = Path(result["output_root"])
    pairs = sorted((root / "listener" / "qualitative_full_cycle_pairs").glob("*.wav"))
    assert len(pairs) == 6
    with (root / "listener" / "blind_responses.csv").open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 30
    with (root / "listener" / "ab_responses.csv").open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 3
    assert (root / "S12_Stage_F_Listener_Package.zip").is_file()
    assert (root / "S12_Stage_F_Answer_Key.zip").is_file()
    assert result["status"] == "WAITING_FOR_JOVI_AUDITION"
