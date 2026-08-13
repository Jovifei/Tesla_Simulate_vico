"""Focused contract tests for the Stage L named diagnostic review package."""

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import wave

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.named_review import (
    AUTOMATED_GATE_FAIL,
    DIAGNOSTIC_FEEDBACK_ALLOWED,
    PARTIAL,
    UNQUALIFIED_DIAGNOSTIC_ONLY,
    build_unqualified_diagnostic_package,
    render_stage_l_named_artifacts,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l import named_review as named_review_module


ZIP_NAME = "S12_Stage_L_Hellcat_UNQUALIFIED_DIAGNOSTIC_Review.zip"
WAV_DESTINATIONS = (
    "01_Formal_Comparison/01_StageK_Parent_60s.wav",
    "01_Formal_Comparison/02_StageL_Candidate_60s.wav",
    "01_Formal_Comparison/03_StageL_Candidate_Comfort_60s.wav",
    "02_Source_Separation/01_SC_Intake_Aero_Acceleration.wav",
    "02_Source_Separation/02_SC_Gear_Casing_Acceleration.wav",
    "02_Source_Separation/03_HEMI_Exhaust_Body_Acceleration.wav",
    "02_Source_Separation/04_HEMI_Structure_Shock_Acceleration.wav",
    "02_Source_Separation/05_Full_Mix_Acceleration.wav",
    "03_State_Review/01_Idle_12s.wav",
    "03_State_Review/02_Low_Load_12s.wav",
    "03_State_Review/03_High_Load_12s.wav",
    "03_State_Review/04_Shift_12s.wav",
    "03_State_Review/05_Lift_Bypass_12s.wav",
)
NON_WAV_DESTINATIONS = (
    "04_Metrics/order_map.png",
    "04_Metrics/intake_vs_exhaust_spectrogram.png",
    "04_Metrics/bank_event_timeline.png",
    "04_Metrics/modulation_spectrum.png",
    "04_Metrics/shift_response.png",
    "04_Metrics/stage_l_hellcat_metrics.json",
)


@pytest.fixture(autouse=True)
def _fast_named_review_loudness(monkeypatch) -> None:
    """Named-review tests exercise binding/transport; loudness DSP is covered separately."""
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_pcm24(path: Path, value: float = 0.1) -> None:
    samples = np.full((480, 2), value, dtype=np.float64)
    pcm = np.clip(np.rint(samples * 8388607.0), -8388608, 8388607).astype("<i4")
    packed = pcm.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(48_000)
        stream.writeframes(packed)


def _short_trace() -> VehicleStateTrace:
    time_s = np.linspace(0.0, 0.04, 41)
    rpm = np.linspace(900.0, 3600.0, time_s.size)
    load = np.linspace(0.15, 0.9, time_s.size)
    throttle = np.where(time_s < 0.035, load, 0.02)
    return VehicleStateTrace(
        time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s),
    ).validate()


def _diagnostic_render(trace: VehicleStateTrace, *, candidate: bool) -> SourceRender:
    count = int(round(float(trace.time_s[-1]) * 48_000)) + 1
    time_s = np.arange(count, dtype=np.float64) / 48_000.0
    operating_scale = 0.5 + float(np.mean(trace.load))
    scale = (1.15 if candidate else 1.0) * operating_scale
    left = 0.025 * scale * np.sin(2.0 * np.pi * 90.0 * time_s)
    right = 0.024 * scale * np.sin(2.0 * np.pi * 92.0 * time_s)
    intake = 0.010 * scale * np.sin(2.0 * np.pi * (550.0 + 80.0 * time_s) * time_s)
    casing = 0.004 * scale * np.sin(2.0 * np.pi * 1100.0 * time_s)
    structure = 0.007 * scale * np.sin(2.0 * np.pi * 160.0 * time_s)
    bypass = np.where(time_s > 0.035, 0.004 * np.exp(-(time_s - 0.035) / 0.008), 0.0)
    stereo = lambda mono: np.column_stack((mono, 0.98 * mono))
    stems = {
        "hemi_exhaust_left": stereo(left), "hemi_exhaust_right": stereo(right),
        "hemi_blowdown_body": stereo(0.6 * structure), "hemi_structure_shock": stereo(structure),
        "hemi_mechanical_torque_ripple": stereo(0.35 * structure),
        "sc_intake_radiated": stereo(intake), "sc_casing_radiated": stereo(casing),
        "sc_bypass_release": stereo(bypass), "hellcat_shift_reengagement": stereo(0.2 * structure),
        "hellcat_sc_drive_transient": stereo(0.2 * intake), "hellcat_tip_in_blowdown": stereo(0.3 * structure),
    }
    pressure = sum(stems.values(), np.zeros_like(next(iter(stems.values()))))
    return SourceRender(pressure, stems, {
        "render_path": "StageL_candidate" if candidate else "StageK_parent",
        "candidate_parameter_usage": {
            "requested": ["source.fixture"], "read": ["source.fixture"],
            "configured": ["source.fixture"], "active": ["source.fixture"],
            "inactive": [], "unused": [],
        },
    }).validate()


def _hot_diagnostic_render(trace: VehicleStateTrace) -> SourceRender:
    render = _diagnostic_render(trace, candidate=True)
    stems = dict(render.stems)
    stems["hemi_exhaust_left"] = 40.0 * stems["hemi_exhaust_left"]
    stems["hemi_exhaust_right"] = 40.0 * stems["hemi_exhaust_right"]
    pressure = sum(stems.values(), np.zeros_like(render.pressure))
    return SourceRender(pressure, stems, render.diagnostics).validate()


def _arbitrary_artifact_input(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    artifacts: dict[str, object] = {}
    for index, destination in enumerate(WAV_DESTINATIONS):
        path = source / f"audio-{index:02d}.wav"
        _write_pcm24(path)
        artifacts[destination] = {
            "kind": "pcm24_wav", "path": str(path), "sha256": _sha(path),
            "requested_gain_db": 1.9382, "actual_gain_db": 0.0,
            "headroom_limited": True, "raw_lufs": -20.0, "final_lufs": -20.0,
            "raw_peak_dbfs": -20.0, "final_peak_dbfs": -20.0,
        }
    for index, destination in enumerate(NON_WAV_DESTINATIONS):
        path = source / (f"plot-{index}.png" if destination.endswith(".png") else "metrics.json")
        if destination.endswith(".png"):
            path.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        else:
            path.write_text(json.dumps({"status": "PARTIAL / AUTOMATED_GATE_FAIL"}), encoding="utf-8")
        artifacts[destination] = {
            "kind": "png" if destination.endswith(".png") else "json",
            "path": str(path), "sha256": _sha(path),
        }
    payload = {
        "schema_version": "s12-stage-l-named-artifact-input-1",
        "package_id": "s12-stage-l-hellcat-intake-roughness-v1",
        "bindings": {
            "source_commit": "3d65c04d2101048190aa8a720972366dec9a604b",
            "candidate_profile_sha256": "1" * 64,
            "parent_profile_sha256": "2" * 64,
            "trace_version": "stage-l-canonical-cycle-v1",
            "trace_sha256": "3" * 64,
        },
        "formal_common_gain": {
            "requested_gain_db": 1.9382, "actual_gain_db": 0.0,
            "headroom_limited": True, "compressor": False, "limiter": False,
            "eq": False, "per_section_agc": False,
        },
        "artifacts": artifacts,
    }
    manifest = tmp_path / "artifact-input.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return manifest, _sha(manifest)


def _artifact_input(tmp_path: Path) -> tuple[Path, str]:
    result, _ = _produced_input(tmp_path)
    path = Path(result["artifact_manifest_path"])
    return path, str(result["artifact_manifest_sha256"])


def _produced_input(tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    result = render_stage_l_named_artifacts(
        tmp_path / "produced",
        trace=_short_trace(),
        parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
        candidate_renderer=lambda actual: _diagnostic_render(actual, candidate=True),
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )
    path = Path(result["artifact_manifest_path"])
    return result, json.loads(path.read_text(encoding="utf-8"))


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def _wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes()


def test_builder_rejects_caller_created_self_hash_fixture(tmp_path: Path) -> None:
    manifest, manifest_sha = _arbitrary_artifact_input(tmp_path)

    with pytest.raises(ValueError, match="producer"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            artifact_manifest_path=manifest,
            expected_artifact_manifest_sha256=manifest_sha,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )


def test_builder_rejects_missing_per_file_producer_receipt(tmp_path: Path) -> None:
    _, payload = _produced_input(tmp_path)
    payload["artifacts"][WAV_DESTINATIONS[3]].pop("producer_receipt", None)
    manifest = tmp_path / "missing-receipt.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="producer receipt"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            artifact_manifest_path=manifest,
            expected_artifact_manifest_sha256=_sha(manifest),
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )


def test_builder_rejects_producer_receipt_frame_count_not_matching_pcm(tmp_path: Path) -> None:
    _, payload = _produced_input(tmp_path)
    receipt = payload["artifacts"][WAV_DESTINATIONS[3]]["producer_receipt"]
    receipt["frame_count"] += 1
    manifest = tmp_path / "wrong-frame-count.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="frame count or duration"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            artifact_manifest_path=manifest,
            expected_artifact_manifest_sha256=_sha(manifest),
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )


def test_state_wavs_are_exactly_12_seconds_and_low_load_differs_from_shift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    _, payload = _produced_input(tmp_path)
    artifacts = payload["artifacts"]
    for destination in WAV_DESTINATIONS[8:]:
        item = artifacts[destination]
        assert _wav_duration(Path(item["path"])) == pytest.approx(12.0, abs=1.0 / 48_000)
        assert item["producer_receipt"]["frame_count"] == 12 * 48_000
        assert item["producer_receipt"]["duration_s"] == 12.0
        if np.isfinite(item["raw_lufs"]):
            assert item["final_lufs"] == pytest.approx(item["raw_lufs"] + item["actual_gain_db"])
        if np.isfinite(item["raw_peak_dbfs"]):
            assert item["final_peak_dbfs"] == pytest.approx(item["raw_peak_dbfs"] + item["actual_gain_db"])
    low = payload["artifacts"][WAV_DESTINATIONS[9]]
    shift = payload["artifacts"][WAV_DESTINATIONS[11]]

    assert low["pcm_sha256"] != shift["pcm_sha256"]


def test_source_separation_wavs_are_exactly_18_seconds_and_full_mix_differs_from_formal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    _, payload = _produced_input(tmp_path)
    artifacts = payload["artifacts"]
    formal_candidate_sha = artifacts[WAV_DESTINATIONS[1]]["pcm_sha256"]
    for destination in WAV_DESTINATIONS[3:8]:
        item = artifacts[destination]
        assert _wav_duration(Path(item["path"])) == pytest.approx(18.0, abs=1.0 / 48_000)
        assert item["producer_receipt"]["frame_count"] == 18 * 48_000
    assert artifacts[WAV_DESTINATIONS[7]]["pcm_sha256"] != formal_candidate_sha


def _fast_loudness(audio: np.ndarray, sample_rate_hz: int) -> SimpleNamespace:
    del sample_rate_hz
    peak = float(np.max(np.abs(audio)))
    return SimpleNamespace(integrated_lufs=-20.0, peak_dbfs=20.0 * np.log10(max(peak, 1.0e-30)))


def test_initial_named_review_forces_task6_failure_to_diagnostic_status(tmp_path: Path) -> None:
    package = build_unqualified_diagnostic_package(
        output_root=tmp_path / "s12-stage-l-hellcat-intake-roughness-v1",
        task6_gate_status={
            "residency_max": 5,
            "formal_final_provenance": "NOT_AVAILABLE",
        },
        render=False,
    )

    assert package["package_status"] == PARTIAL
    assert package["gate_status"] == AUTOMATED_GATE_FAIL
    assert package["qualification_status"] == UNQUALIFIED_DIAGNOSTIC_ONLY
    assert package["feedback_status"] == DIAGNOSTIC_FEEDBACK_ALLOWED
    assert "WAITING" not in str(package)
    assert "APPROVED" not in str(package)


def test_artifact_producer_uses_actual_parent_candidate_paths_and_emits_complete_health_bound_handoff(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    trace = _short_trace()
    calls: list[str] = []

    def parent_renderer(actual_trace: VehicleStateTrace) -> SourceRender:
        assert actual_trace is trace
        calls.append("stage_k_parent")
        return _diagnostic_render(actual_trace, candidate=False)

    def candidate_renderer(actual_trace: VehicleStateTrace) -> SourceRender:
        calls.append("stage_l_candidate_canonical" if actual_trace is trace else "stage_l_candidate_scenario")
        return _diagnostic_render(actual_trace, candidate=True)

    result = render_stage_l_named_artifacts(
        tmp_path / "produced",
        trace=trace,
        parent_renderer=parent_renderer,
        candidate_renderer=candidate_renderer,
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )

    assert calls == ["stage_k_parent", "stage_l_candidate_canonical"] + ["stage_l_candidate_scenario"] * 5
    manifest_path = Path(result["artifact_manifest_path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert set(payload["artifacts"]) == set(WAV_DESTINATIONS + NON_WAV_DESTINATIONS)
    assert len([item for item in payload["artifacts"].values() if item["kind"] == "pcm24_wav"]) == 13
    assert len([item for item in payload["artifacts"].values() if item["kind"] == "png"]) == 5
    trace_bindings = {item["trace_binding"]["trace_sha256"] for item in payload["artifacts"].values()}
    assert trace_bindings == {payload["bindings"]["trace_sha256"]}
    formal_parent = payload["artifacts"][WAV_DESTINATIONS[0]]
    formal_candidate = payload["artifacts"][WAV_DESTINATIONS[1]]
    assert formal_parent["source_render_path"] == "StageK_parent"
    assert formal_candidate["source_render_path"] == "StageL_candidate"
    assert formal_parent["actual_gain_db"] == formal_candidate["actual_gain_db"]
    for destination in WAV_DESTINATIONS:
        path = Path(payload["artifacts"][destination]["path"])
        with wave.open(str(path), "rb") as stream:
            assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (48_000, 2, 3)
            assert payload["artifacts"][destination]["producer_receipt"]["frame_count"] == stream.getnframes()
    for destination in NON_WAV_DESTINATIONS[:5]:
        assert Path(payload["artifacts"][destination]["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_artifact_producer_attenuates_hot_diagnostic_stems_to_pcm_health(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    trace = _short_trace()
    result = render_stage_l_named_artifacts(
        tmp_path / "hot-produced",
        trace=trace,
        parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
        candidate_renderer=_hot_diagnostic_render,
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )
    payload = json.loads(Path(result["artifact_manifest_path"]).read_text(encoding="utf-8"))
    item = payload["artifacts"]["02_Source_Separation/03_HEMI_Exhaust_Body_Acceleration.wav"]
    assert item["requested_gain_db"] == 0.0
    assert item["actual_gain_db"] < 0.0
    assert item["headroom_limited"] is True
    assert item["final_peak_dbfs"] <= -1.5


def test_builds_complete_content_addressed_unqualified_package_deterministically(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    source_manifest, source_sha = _artifact_input(tmp_path)
    roots = [tmp_path / "review-a", tmp_path / "review-b"]
    results = [
        build_unqualified_diagnostic_package(
            root,
            artifact_manifest_path=source_manifest,
            expected_artifact_manifest_sha256=source_sha,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )
        for root in roots
    ]
    required = {
        "00_OPEN_ME_FIRST.md", *WAV_DESTINATIONS, *NON_WAV_DESTINATIONS,
        "05_Feedback/Jovi_Stage_L_Hellcat_Feedback.csv", "artifact_manifest.json",
        "SHA256SUMS.txt", ZIP_NAME,
    }
    for root, result in zip(roots, results):
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        assert actual == required
        assert result["package_status"] == PARTIAL
        manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
        assert manifest["qualification_status"] == UNQUALIFIED_DIAGNOSTIC_ONLY
        assert manifest["feedback_status"] == DIAGNOSTIC_FEEDBACK_ALLOWED
        assert manifest["artifact_input_sha256"] == source_sha
        assert manifest["formal_final_provenance"] == "NOT_AVAILABLE"
        assert manifest["full_pipeline_peak_residency"] == 5
        assert all(item["pcm_health"]["frame_count"] > 0 for item in manifest["wav_artifacts"])
        assert all(item["pcm_health"]["peak_dbfs"] <= -1.5 for item in manifest["wav_artifacts"])
        assert all(item["pcm_health"]["clipping_count"] == 0 for item in manifest["wav_artifacts"])
        readme = (root / "00_OPEN_ME_FIRST.md").read_text(encoding="utf-8")
        assert "UNQUALIFIED_DIAGNOSTIC_ONLY" in readme
        assert "Human PASS" not in readme and "Approved" not in readme
        with (root / "05_Feedback/Jovi_Stage_L_Hellcat_Feedback.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert [row["file_id"] for row in rows] == list(WAV_DESTINATIONS)
        assert all(row["listener_id"] == "" and row["keep_or_change"] == "" for row in rows)
    assert _sha(roots[0] / ZIP_NAME) == _sha(roots[1] / ZIP_NAME)


def test_builder_cli_supports_direct_and_module_help() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    script = repo_root / "tools/sound_sim/s12/acoustic_identity_v015/scripts/build_stage_l_named_review.py"
    commands = (
        [sys.executable, str(script), "--help"],
        [sys.executable, "-m", "tools.sound_sim.s12.acoustic_identity_v015.scripts.build_stage_l_named_review", "--help"],
    )
    for command in commands:
        run = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False)
        assert run.returncode == 0, run.stderr
        assert "artifact-manifest" in run.stdout
