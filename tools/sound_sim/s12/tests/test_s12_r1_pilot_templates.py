from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "real_reference"
TEMPLATE = ROOT / "templates" / "s12_r1_pilot_hellcat"


def test_hellcat_template_declares_required_external_delivery_contract() -> None:
    spec = json.loads((TEMPLATE / "spec.template.json").read_text(encoding="utf-8"))
    rights = json.loads((TEMPLATE / "rights.template.json").read_text(encoding="utf-8"))
    assert spec["vehicle_id"] == "hellcat"
    assert spec["recording_id"] == "hellcat_full_pull_01"
    assert spec["raw_media_stored_outside_git"] is True
    assert set(spec["state"]["units"]) == {"time_s", "rpm", "load", "throttle", "gear", "shift_event"}
    assert set(rights["allowed_uses"]) >= {"local_analysis", "derived_features", "comparison", "human_audition", "bounded_tuning"}
    assert rights["raw_media_git_policy"] == "EXTERNAL_ONLY"


def test_hellcat_template_has_three_trace_headers_and_sha_contract() -> None:
    assert (TEMPLATE / "rpm.csv").read_text(encoding="utf-8").splitlines()[0] == "time_s,rpm"
    assert (TEMPLATE / "load_throttle.csv").read_text(encoding="utf-8").splitlines()[0] == "time_s,load,throttle"
    assert (TEMPLATE / "gear_shift.csv").read_text(encoding="utf-8").splitlines()[0] == "time_s,gear,shift_event"
    sha_text = (TEMPLATE / "sha256.txt").read_text(encoding="utf-8")
    assert "raw_audio.wav" in sha_text
    assert "rpm.csv" in sha_text
    assert "load_throttle.csv" in sha_text
    assert "gear_shift.csv" in sha_text


def test_guides_explicitly_forbid_guessing_and_ordinary_sfx_license() -> None:
    contact = (ROOT / "R1_VENDOR_OWNER_CONTACT_REQUEST_ZH.md").read_text(encoding="utf-8")
    capture = (ROOT / "R1_AUDIO_OBD_CAN_CAPTURE_GUIDE_ZH.md").read_text(encoding="utf-8")
    combined = contact + capture
    for phrase in ("不能猜测", "算法开发", "OBD", "CAN", "同步", "原始 WAV/FLAC"):
        assert phrase in combined


def test_template_tree_contains_no_raw_media() -> None:
    media = {".wav", ".flac", ".mp3", ".mp4", ".webm", ".m4a"}
    assert not [path for path in TEMPLATE.rglob("*") if path.is_file() and path.suffix.lower() in media]
