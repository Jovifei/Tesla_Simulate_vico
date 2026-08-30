from pathlib import Path
import json
import wave

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.package import build_hellcat_layer_package, validate_layer_package

SCENES = (
    "hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm",
    "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift",
    "afterfire_eligible", "afterfire_ineligible", "idle_return",
)
STEMS = ("parent", "y1_event", "y2_map", "y3_p4", "y4_transients", "y5_dp", "monitor")


def test_package_writes_required_wavs_and_distinct_parent_candidate(tmp_path) -> None:
    root = tmp_path / "pkg"
    manifest = build_hellcat_layer_package(root, long_window=False, duration_s=0.8)
    errors = validate_layer_package(root)
    assert errors == []
    for scene in SCENES:
        for stem in STEMS:
            wav = root / scene / f"{stem}.wav"
            assert wav.is_file(), wav
            with wave.open(str(wav), "rb") as handle:
                assert handle.getnframes() > 0
    assert manifest["parent_sha256"] != manifest["candidate_sha256"]
    assert "OEM" not in json.dumps(manifest)
    assert manifest["formal_status"] == "FORMAL_R1_REFERENCE_MISSING"
