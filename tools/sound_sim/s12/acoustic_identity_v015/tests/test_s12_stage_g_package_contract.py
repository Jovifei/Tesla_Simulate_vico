from __future__ import annotations

import csv
from pathlib import Path
import zipfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_g.package_builder import build_stage_g_package


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "targets" / "stage_g_candidates"


def test_stage_g_package_has_anonymous_trials_and_real_ab_files(tmp_path: Path) -> None:
    result = build_stage_g_package(
        tmp_path / "package",
        candidate_paths={"ferrari_458": CANDIDATES / "Ferrari_candidate_v4.json", "hellcat": CANDIDATES / "Hellcat_candidate_v4.json", "rx7_fd": CANDIDATES / "RX7_candidate_v4.json"},
        seed=0x5331325F53544147455F475F56345F31,
        duration_s=1.0,
    )
    root = Path(result["output_root"])
    with (root / "listener" / "blind_responses.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 30
    assert all(not row["guessed_vehicle_id"] for row in rows)
    assert len(list((root / "listener" / "qualitative_full_cycle_pairs").glob("P*_*.wav"))) == 6
    with zipfile.ZipFile(root / "S12_Stage_G_Listener_Package.zip") as archive:
        names = archive.namelist()
        assert len(names) > 30
        assert not any("sealed" in name.lower() for name in names)
        assert not any(token in item.lower() for item in names for token in ("ferrari", "hellcat", "rx7", "candidate", "baseline"))
        payload = b"\n".join(archive.read(name) for name in names).lower()
        assert not any(token in payload for token in (b"ferrari_458", b"hellcat", b"rx7_fd", b"baseline", b"candidate", b"answer_key", b"0x5331325f"))


def test_stage_g_seed_is_recorded_as_hex_without_listener_leak(tmp_path: Path) -> None:
    result = build_stage_g_package(tmp_path / "package", candidate_paths={"ferrari_458": CANDIDATES / "Ferrari_candidate_v4.json", "hellcat": CANDIDATES / "Hellcat_candidate_v4.json", "rx7_fd": CANDIDATES / "RX7_candidate_v4.json"}, seed=7, duration_s=1.0)
    root = Path(result["output_root"])
    assert result["seed"] == "0x7"
    assert "0x7" not in (root / "listener" / "listener_manifest.json").read_text(encoding="utf-8")
