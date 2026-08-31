import json
import hashlib
from pathlib import Path
import wave

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import read_pcm24_wav, write_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.package import (
    build_hellcat_layer_package,
    validate_layer_package,
)

SCENES = (
    "hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm",
    "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift",
    "afterfire_eligible", "afterfire_ineligible", "idle_return",
)
STEMS = ("parent", "y1_event", "y2_map", "y3_p4", "y4_transients", "y5_dp", "monitor")


@pytest.fixture(scope="module")
def built_package(tmp_path_factory):
    root = tmp_path_factory.mktemp("stage-y6") / "pkg"
    return root, build_hellcat_layer_package(root, long_window=False, duration_s=0.2)


def test_package_writes_required_wavs_and_distinct_parent_candidate(built_package) -> None:
    root, manifest = built_package
    errors = validate_layer_package(root)
    assert errors == []
    for scene in SCENES:
        for stem in STEMS:
            wav = root / scene / f"{stem}.wav"
            assert wav.is_file(), wav
            with wave.open(str(wav), "rb") as handle:
                assert handle.getnframes() > 0
    assert manifest["parent_sha256"] != manifest["candidate_sha256"]
    assert "not OEM reproduction" in json.dumps(manifest)
    assert manifest["formal_status"] == "FORMAL_R1_REFERENCE_MISSING"


def test_manifest_proves_cumulative_layers_and_single_fixed_gain(built_package) -> None:
    _root, manifest = built_package
    expected = {
        "parent": (),
        "y1_event": ("event_domain",),
        "y2_map": ("event_domain", "timbre_map"),
        "y3_p4": ("event_domain", "timbre_map", "cycle_sync"),
        "y4_transients": ("event_domain", "timbre_map", "cycle_sync", "transients"),
        "y5_dp": ("event_domain", "timbre_map", "cycle_sync", "transients", "dp_chain"),
        "monitor": ("event_domain", "timbre_map", "cycle_sync", "transients", "dp_chain", "monitor"),
    }
    assert manifest["publication"]["fixed_gain_applications"] == 1
    assert manifest["dynamic_review"]["normalization"] == "none"
    for scene in SCENES:
        for stem, layers in expected.items():
            record = manifest["scenes"][scene]["stems"][stem]
            assert tuple(record["consumed_layers"]) == layers
            assert record["fixed_gain_applications"] == 1


def test_timbre_derivatives_match_shared_rms_target_but_dynamic_stems_are_raw(built_package) -> None:
    root, manifest = built_package
    target = manifest["timbre_review"]["target_rms_proxy"]
    assert target > 0.0
    dynamic_rms = []
    for scene in SCENES:
        dynamic, _ = read_pcm24_wav(root / scene / "y5_dp.wav")
        matched, _ = read_pcm24_wav(root / "timbre_review" / scene / "y5_dp_matched.wav")
        dynamic_rms.append(float(np.sqrt(np.mean(np.square(dynamic)))))
        matched_rms = float(np.sqrt(np.mean(np.square(matched))))
        assert matched_rms == pytest.approx(target, abs=2.0e-5)
    assert max(dynamic_rms) > min(dynamic_rms) * 1.05


def test_two_chinese_review_pages_link_relative_playable_audio(built_package) -> None:
    root, manifest = built_package
    assert {"timbre_review.html", "dynamic_review.html"} <= set(manifest["review_pages"])
    for name, marker in (("timbre_review.html", "音色"), ("dynamic_review.html", "动态")):
        html = (root / name).read_text(encoding="utf-8")
        assert marker in html
        assert 'controls' in html
        assert 'src="' in html
        assert "E:/" not in html and "..\\" not in html
        for scene in SCENES:
            assert scene in html


@pytest.mark.parametrize("kind", ("pcm", "wav", "duration", "status", "unsafe", "extra"))
def test_validator_fails_closed_for_tampering(built_package, kind) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / f"tamper-{kind}"
    # Keep the generated fixture immutable: copy only files needed by this case.
    import shutil
    shutil.copytree(source_root, root)
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if kind == "pcm":
        path = root / SCENES[0] / "parent.wav"
        data = bytearray(path.read_bytes())
        data[-1] ^= 0x01
        path.write_bytes(data)
    elif kind == "wav":
        (root / SCENES[1] / "y5_dp.wav").write_bytes(b"not a wav")
    elif kind == "duration":
        if isinstance(manifest.get("scenes"), dict):
            manifest["scenes"][SCENES[2]]["duration_s"] += 0.1
        else:
            manifest["duration_s"] += 0.1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif kind == "status":
        manifest["status"] = "Y6PASS"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif kind == "unsafe":
        manifest["files"]["../escape.wav"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        (root / SCENES[0] / "extra.wav").write_bytes((root / SCENES[0] / "parent.wav").read_bytes())
    errors = validate_layer_package(root)
    assert errors, kind


def test_builder_refuses_to_overwrite_existing_output(tmp_path) -> None:
    root = tmp_path / "pkg"
    root.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        build_hellcat_layer_package(root, long_window=False, duration_s=0.2)


@pytest.mark.parametrize("tamper", ("nonfinite", "sample_rate", "channels", "pcm16", "zero_frames", "truncated", "page_claim"))
def test_validator_rejects_invalid_numeric_wav_or_claim_contract(built_package, tamper) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / f"invalid-{tamper}"
    import shutil
    shutil.copytree(source_root, root)
    target = root / SCENES[0] / "parent.wav"
    if tamper == "nonfinite":
        path = root / "package_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["duration_s"] = float("nan")
        path.write_text(json.dumps(manifest, allow_nan=True), encoding="utf-8")
    elif tamper == "sample_rate":
        audio, _ = read_pcm24_wav(target)
        write_pcm24_wav(target, audio, 44100)
    elif tamper == "channels":
        with wave.open(str(target), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(3)
            stream.setframerate(48000)
            stream.writeframes(b"\0\0\0")
    elif tamper == "pcm16":
        with wave.open(str(target), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"\0\0\0\0")
    elif tamper == "zero_frames":
        with wave.open(str(target), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(3)
            stream.setframerate(48000)
            stream.writeframes(b"")
    elif tamper == "truncated":
        target.write_bytes(target.read_bytes()[:-1])
    else:
        page = root / "dynamic_review.html"
        page.write_text(page.read_text(encoding="utf-8") + "<p>Y6PASS</p>", encoding="utf-8")
    assert validate_layer_package(root), tamper


def test_validator_rejects_rebound_identical_parent_candidate_even_when_hashes_rebound(built_package) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / "invalid-rebound"
    import shutil
    shutil.copytree(source_root, root)
    parent = root / SCENES[0] / "parent.wav"
    candidate = root / SCENES[0] / "y5_dp.wav"
    candidate.write_bytes(parent.read_bytes())
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rebound_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    manifest["files"][f"{SCENES[0]}/y5_dp.wav"] = rebound_sha
    manifest["scenes"][SCENES[0]]["stems"]["y5_dp"]["sha256"] = rebound_sha
    sha_path = root / "sha256_manifest.json"
    sha_manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    sha_manifest["files"][f"{SCENES[0]}/y5_dp.wav"] = rebound_sha
    sha_path.write_text(json.dumps(sha_manifest), encoding="utf-8")
    candidate_bytes = b"".join((root / scene / "y5_dp.wav").read_bytes() for scene in SCENES)
    manifest["candidate_sha256"] = hashlib.sha256(candidate_bytes).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_layer_package(root)
    assert any("rebound_identical" in error for error in errors)
