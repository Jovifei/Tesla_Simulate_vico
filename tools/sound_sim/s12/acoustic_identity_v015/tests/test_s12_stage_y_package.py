import json
import hashlib
from pathlib import Path
import wave

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_y import package as stage_y_package
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


@pytest.mark.parametrize("relative", ("timbre_review.html", "dynamic_review.html", "AUDITION_GUIDE_ZH.md", "parent_final_diagnostic.json"))
def test_validator_rejects_tampered_listed_page_guide_or_diagnostic(built_package, relative) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / ("tamper-listed-" + relative.replace("/", "-"))
    import shutil
    shutil.copytree(source_root, root)
    path = root / relative
    path.write_bytes(path.read_bytes() + b"\n<!-- tampered -->\n")
    errors = validate_layer_package(root)
    assert any("sha_mismatch:" + relative in error for error in errors)


def test_parent_final_diagnostic_is_hashed_and_summarized_without_a_score(built_package) -> None:
    root, manifest = built_package
    diagnostic_ref = manifest["parent_final_diagnostic"]
    diagnostic_path = root / diagnostic_ref["path"]
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert diagnostic_ref["sha256"] == hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    assert diagnostic["diagnostic_only"] is True
    assert diagnostic["threshold_percent"] == 15.0
    assert "similarity_score" not in json.dumps(diagnostic)
    for scene in SCENES:
        row = diagnostic["scenes"][scene]
        assert row["parent"]["raw_dynamic"]["rms_dbfs"] != row["final"]["raw_dynamic"]["rms_dbfs"]
        assert "rms_dbfs" in row["relative_deltas"]["raw_dynamic"]
        assert isinstance(row["exceeds_15_percent"], bool)
    for page in ("timbre_review.html", "dynamic_review.html"):
        html = (root / page).read_text(encoding="utf-8")
        assert "Parent vs F" in html
        assert "rms_dbfs" in html


@pytest.mark.parametrize("failure", (FileNotFoundError, ValueError))
def test_validator_reports_fitted_map_load_failure(built_package, monkeypatch, failure) -> None:
    root, _manifest = built_package

    def broken_loader():
        raise failure("fixture unavailable")

    monkeypatch.setattr(stage_y_package, "load_committed_fixture_timbre_map", broken_loader)
    errors = validate_layer_package(root)
    assert any(error.startswith("fitted_map_fixture_load:") for error in errors)


def test_validator_rejects_rebound_parent_final_diagnostic_sha(built_package) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / "invalid-parent-final-diagnostic-sha"
    import shutil
    shutil.copytree(source_root, root)
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    diagnostic_path = root / "parent_final_diagnostic.json"
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    scene = SCENES[0]
    diagnostic["scenes"][scene]["parent_sha256"] = manifest["files"][f"{scene}/y5_dp.wav"]
    diagnostic_path.write_text(json.dumps(diagnostic), encoding="utf-8")
    diagnostic_sha = hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    manifest["files"]["parent_final_diagnostic.json"] = diagnostic_sha
    manifest["parent_final_diagnostic"]["sha256"] = diagnostic_sha
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sha_path = root / "sha256_manifest.json"
    sha_manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    sha_manifest["files"]["parent_final_diagnostic.json"] = diagnostic_sha
    sha_path.write_text(json.dumps(sha_manifest), encoding="utf-8")
    errors = validate_layer_package(root)
    assert any("parent_final_diagnostic_sha:" + scene in error for error in errors)


def test_validator_rejects_rebound_parent_final_diagnostic_metric(built_package) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / "invalid-parent-final-diagnostic-metric"
    import shutil
    shutil.copytree(source_root, root)
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    diagnostic_path = root / "parent_final_diagnostic.json"
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    scene = SCENES[0]
    diagnostic["scenes"][scene]["final"]["raw_dynamic"]["rms_dbfs"] += 1.0
    diagnostic_path.write_text(json.dumps(diagnostic), encoding="utf-8")
    diagnostic_sha = hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    manifest["files"]["parent_final_diagnostic.json"] = diagnostic_sha
    manifest["parent_final_diagnostic"]["sha256"] = diagnostic_sha
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sha_path = root / "sha256_manifest.json"
    sha_manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    sha_manifest["files"]["parent_final_diagnostic.json"] = diagnostic_sha
    sha_path.write_text(json.dumps(sha_manifest), encoding="utf-8")
    errors = validate_layer_package(root)
    assert any("parent_final_diagnostic_metrics:" + scene in error for error in errors)


def test_validator_rejects_unbound_renderer_config_hashes(built_package) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / "invalid-renderer-config-hashes"
    import shutil
    shutil.copytree(source_root, root)
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scene_stems = manifest["scenes"][SCENES[0]]["stems"]
    scene_stems["parent"]["engine"]["renderer_config_sha256"] = "not-a-sha"
    rebound = "a" * 64
    scene_stems["y5_dp"]["engine"]["renderer_config_sha256"] = rebound
    scene_stems["monitor"]["engine"]["renderer_config_sha256"] = rebound
    scene_stems["monitor"]["monitor_provenance"]["source_renderer_config_sha256"] = rebound
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_layer_package(root)
    assert any("renderer_config_sha256:" in error for error in errors)
    assert any("monitor_config_binding:" + SCENES[0] in error for error in errors)


def test_monitor_is_policy_processed_reuse_of_f_rendering_with_bound_provenance(built_package) -> None:
    root, manifest = built_package
    scene = SCENES[0]
    final_record = manifest["scenes"][scene]["stems"]["y5_dp"]
    monitor = manifest["scenes"][scene]["stems"]["monitor"]
    assert monitor["raw_dynamic"] is False
    assert monitor["signal_domain"] == "policy_processed_audition_monitor"
    provenance = monitor["monitor_provenance"]
    assert provenance["source_stem"] == "y5_dp"
    assert provenance["source_path"] == f"{scene}/y5_dp.wav"
    assert provenance["source_pcm_sha256"] == final_record["sha256"]
    assert provenance["source_renderer_config_sha256"] == final_record["engine"]["renderer_config_sha256"]
    assert "not raw dynamic" in (root / "dynamic_review.html").read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("kind", ("scope", "boundary_type", "chinese_claim"))
def test_validator_rejects_affirmative_or_malformed_claim_boundary(built_package, kind) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / f"claim-{kind}"
    import shutil
    shutil.copytree(source_root, root)
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if kind == "scope":
        manifest["scope"] = "OEM reproduction"
    elif kind == "boundary_type":
        manifest["review_boundaries"]["oem_reproduction"] = "true"
    else:
        guide = root / "AUDITION_GUIDE_ZH.md"
        guide.write_text(guide.read_text(encoding="utf-8") + "\n本包已通过 OEM 资格认证并已冻结。\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_layer_package(root), kind


def test_validator_requires_matched_pcm24_clipping_and_shared_headroom(built_package) -> None:
    root, manifest = built_package
    tolerance = 1.0 / (1 << 23)
    for scene in SCENES:
        for stem in STEMS:
            audio, metadata = read_pcm24_wav(root / "timbre_review" / scene / f"{stem}_matched.wav")
            assert metadata["clipping"] == 0
            assert float(np.max(np.abs(audio))) <= 0.98 + tolerance


def test_validator_rejects_rebound_hash_for_clipped_matched_wav(built_package) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / "invalid-matched-clipped"
    import shutil
    shutil.copytree(source_root, root)
    relative = f"timbre_review/{SCENES[0]}/parent_matched.wav"
    path = root / relative
    data = bytearray(path.read_bytes())
    data[-6:-3] = b"\xff\xff\x7f"
    path.write_bytes(data)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][relative] = digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sha_path = root / "sha256_manifest.json"
    sha_manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    sha_manifest["files"][relative] = digest
    sha_path.write_text(json.dumps(sha_manifest), encoding="utf-8")
    assert validate_layer_package(root)


def test_manifest_binds_renderer_models_and_fitted_map_fixture(built_package) -> None:
    _root, manifest = built_package
    expected = {
        "y1_event": ("waveguide_v1", "harmonic_v1", "off", "off", "off"),
        "y2_map": ("waveguide_v1", "timbre_map_v1", "off", "off", "off"),
        "y3_p4": ("waveguide_v1", "timbre_map_v1", "fixture_v1", "off", "off"),
        "y4_transients": ("waveguide_v1", "timbre_map_v1", "fixture_v1", "state_v1", "off"),
        "y5_dp": ("waveguide_v1", "timbre_map_v1", "fixture_v1", "state_v1", "dp_v1"),
    }
    for stem, models in expected.items():
        engine = manifest["scenes"][SCENES[0]]["stems"][stem]["engine"]
        assert tuple(engine[key] for key in ("path_model", "forced_induction_model", "cycle_sync_model", "transient_model", "audio_chain")) == models
        if stem != "y1_event":
            assert engine["fitted_timbre_map_schema"] == "s12.stage_y.harmonic_timbre_map.v1"
            assert len(engine["fitted_timbre_map_fixture_sha256"]) == 64


@pytest.mark.parametrize("kind", ("flag", "model", "map"))
def test_validator_rejects_falsified_layer_proof(built_package, kind) -> None:
    source_root, _manifest = built_package
    root = source_root.parent / f"invalid-layer-proof-{kind}"
    import shutil
    shutil.copytree(source_root, root)
    manifest_path = root / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["scenes"][SCENES[0]]["stems"]["y5_dp"]
    if kind == "flag":
        record["layer_flags"]["dp_chain"] = False
    elif kind == "model":
        record["engine"]["audio_chain"] = "off"
    else:
        record["engine"]["fitted_timbre_map_fixture_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_layer_package(root), kind


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
