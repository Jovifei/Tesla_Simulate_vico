"""Focused contract tests for the Stage L named diagnostic review package."""

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
    ProducedStageLArtifacts,
    UNQUALIFIED_DIAGNOSTIC_ONLY,
    build_unqualified_diagnostic_package,
    render_stage_l_named_artifacts,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l import named_review as named_review_module
from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as render_candidate_module
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
    StageLFormalPcmBundle,
    render_stage_l_formal_final_pcm_bundle,
)


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


def _pcm_payload_sha(audio: np.ndarray) -> str:
    pcm = np.clip(np.rint(np.asarray(audio, dtype=np.float64) * 8388607.0), -8388608, 8388607).astype("<i4")
    payload = pcm.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    return hashlib.sha256(payload).hexdigest()


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


def _artifact_input(tmp_path: Path) -> ProducedStageLArtifacts:
    result, _ = _produced_input(tmp_path)
    return result


def _produced_input(tmp_path: Path) -> tuple[ProducedStageLArtifacts, dict[str, object]]:
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


def test_formal_parent_candidate_wavs_use_exact_frozen_final_pcm_bundle_and_bind_pcm_payload_hashes(
    tmp_path: Path,
) -> None:
    trace = _short_trace()
    parent = _diagnostic_render(trace, candidate=False)
    candidate = _diagnostic_render(trace, candidate=True)
    expected = render_stage_l_formal_final_pcm_bundle(
        parent.pressure,
        candidate.pressure,
        target_lufs=-16.0,
        peak_limit_dbfs=-1.5,
    )

    produced = render_stage_l_named_artifacts(
        tmp_path / "produced",
        trace=trace,
        parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
        candidate_renderer=lambda actual: _diagnostic_render(actual, candidate=True),
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )
    payload = json.loads(Path(produced["artifact_manifest_path"]).read_text(encoding="utf-8"))

    assert expected.pipeline_order == (
        "frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24",
    )
    for relative, final_pcm in (
        (WAV_DESTINATIONS[0], expected.parent_pcm),
        (WAV_DESTINATIONS[1], expected.candidate_pcm),
    ):
        record = payload["artifacts"][relative]
        receipt = record["producer_receipt"]
        final_pcm_sha256 = _pcm_payload_sha(final_pcm)
        assert record["pcm_sha256"] == final_pcm_sha256
        assert record["final_pcm_sha256"] == final_pcm_sha256
        assert receipt["final_pcm_sha256"] == final_pcm_sha256
        assert receipt["final_pipeline"]["pipeline_order"] == list(expected.pipeline_order)
    assert payload["artifacts"][WAV_DESTINATIONS[0]]["actual_gain_db"] == pytest.approx(expected.gain_db)
    assert payload["artifacts"][WAV_DESTINATIONS[1]]["actual_gain_db"] == pytest.approx(expected.gain_db)


def test_candidate_comfort_copy_starts_with_the_frozen_final_candidate_pcm(tmp_path: Path) -> None:
    trace = _short_trace()
    parent = _diagnostic_render(trace, candidate=False)
    candidate = _diagnostic_render(trace, candidate=True)
    expected = render_stage_l_formal_final_pcm_bundle(
        parent.pressure,
        candidate.pressure,
        target_lufs=-16.0,
        peak_limit_dbfs=-1.5,
    )
    produced = render_stage_l_named_artifacts(
        tmp_path / "produced",
        trace=trace,
        parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
        candidate_renderer=lambda actual: _diagnostic_render(actual, candidate=True),
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )
    payload = json.loads(Path(produced["artifact_manifest_path"]).read_text(encoding="utf-8"))
    record = payload["artifacts"][WAV_DESTINATIONS[2]]
    additional_gain_db = record["comfort_additional_gain_db"]

    assert record["final_pcm_input_sha256"] == _pcm_payload_sha(expected.candidate_pcm)
    assert record["producer_receipt"]["final_pcm_input_sha256"] == _pcm_payload_sha(expected.candidate_pcm)
    assert record["final_pipeline"]["pipeline_order"] == [
        "frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24",
        "candidate_comfort_static_gain", "pcm24",
    ]
    expected_comfort = expected.candidate_pcm * 10.0 ** (additional_gain_db / 20.0)
    assert record["pcm_sha256"] == _pcm_payload_sha(expected_comfort)


def test_formal_final_pcm_bundle_uses_one_shared_frozen_final_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = _short_trace()
    parent = _diagnostic_render(trace, candidate=False).pressure
    candidate = _diagnostic_render(trace, candidate=True).pressure
    original = render_candidate_module.manage_bundle_loudness
    managed_calls = []

    def capture_managed_bundle(segments, sample_rate_hz, *, target_lufs, peak_limit_dbfs):
        managed = original(
            segments, sample_rate_hz,
            target_lufs=target_lufs,
            peak_limit_dbfs=peak_limit_dbfs,
        )
        managed_calls.append(managed)
        return managed

    monkeypatch.setattr(render_candidate_module, "manage_bundle_loudness", capture_managed_bundle)
    bundle = render_stage_l_formal_final_pcm_bundle(
        parent, candidate, target_lufs=-16.0, peak_limit_dbfs=-1.5,
    )

    assert bundle.pipeline_order == (
        "frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24",
    )
    assert bundle.parent_pcm.shape == parent.shape
    assert bundle.candidate_pcm.shape == candidate.shape
    assert np.all(np.isfinite(bundle.parent_pcm))
    assert np.all(np.isfinite(bundle.candidate_pcm))
    assert len(managed_calls) == 1
    assert bundle.gain_db == pytest.approx(managed_calls[0].gain_db)
    assert bundle.headroom_limited is managed_calls[0].headroom_limited


def test_formal_package_rejects_a_pre_ptr_only_bypass_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = _short_trace()

    bypass = StageLFormalPcmBundle(
        parent_pcm=_diagnostic_render(trace, candidate=False).pressure,
        candidate_pcm=_diagnostic_render(trace, candidate=True).pressure,
        parent_pre_gain_lufs=-20.0,
        candidate_pre_gain_lufs=-20.0,
        parent_pre_gain_peak_dbfs=-6.0,
        candidate_pre_gain_peak_dbfs=-6.0,
        gain_db=0.0,
        headroom_limited=False,
        pipeline_order=("pre_ptr_only", "pcm24"),
    )
    monkeypatch.setattr(
        named_review_module,
        "render_stage_l_formal_final_pcm_bundle",
        lambda *_args, **_kwargs: bypass,
    )

    with pytest.raises(ValueError, match="frozen final PCM pipeline"):
        render_stage_l_named_artifacts(
            tmp_path / "bypassed",
            trace=trace,
            parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
            candidate_renderer=lambda actual: _diagnostic_render(actual, candidate=True),
            source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
            parent_profile_sha256="2" * 64,
            candidate_profile_sha256="1" * 64,
            trace_version="stage-l-short-test-v1",
        )


def test_formal_pair_preserves_the_renderer_headroom_limited_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = _short_trace()
    parent = _diagnostic_render(trace, candidate=False).pressure
    candidate = _diagnostic_render(trace, candidate=True).pressure
    expected = render_stage_l_formal_final_pcm_bundle(
        parent, candidate, target_lufs=-16.0, peak_limit_dbfs=-1.5,
    )
    unbounded = StageLFormalPcmBundle(
        parent_pcm=expected.parent_pcm,
        candidate_pcm=expected.candidate_pcm,
        parent_pre_gain_lufs=expected.parent_pre_gain_lufs,
        candidate_pre_gain_lufs=expected.candidate_pre_gain_lufs,
        parent_pre_gain_peak_dbfs=expected.parent_pre_gain_peak_dbfs,
        candidate_pre_gain_peak_dbfs=expected.candidate_pre_gain_peak_dbfs,
        gain_db=0.0,
        headroom_limited=False,
        pipeline_order=expected.pipeline_order,
    )
    monkeypatch.setattr(
        named_review_module,
        "render_stage_l_formal_final_pcm_bundle",
        lambda *_args, **_kwargs: unbounded,
    )

    produced = render_stage_l_named_artifacts(
        tmp_path / "produced",
        trace=trace,
        parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
        candidate_renderer=lambda actual: _diagnostic_render(actual, candidate=True),
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )
    payload = json.loads(Path(produced["artifact_manifest_path"]).read_text(encoding="utf-8"))

    for relative in WAV_DESTINATIONS[:2]:
        assert payload["artifacts"][relative]["headroom_limited"] is False
        assert payload["artifacts"][relative]["producer_receipt"]["headroom_limited"] is False


def test_formal_pair_reports_pre_gain_and_final_pcm_metrics_at_their_actual_layers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def measure_formal_pcm_or_fast_diagnostics(audio: np.ndarray, sample_rate_hz: int):
        if np.asarray(audio).shape[0] <= 48_000:
            return render_candidate_module.measure_loudness(audio, sample_rate_hz)
        return _fast_loudness(audio, sample_rate_hz)

    monkeypatch.setattr(
        named_review_module,
        "measure_loudness",
        measure_formal_pcm_or_fast_diagnostics,
    )
    trace = _short_trace()
    parent = _diagnostic_render(trace, candidate=False)
    candidate = _diagnostic_render(trace, candidate=True)
    bundle = render_stage_l_formal_final_pcm_bundle(
        parent.pressure,
        candidate.pressure,
        target_lufs=-16.0,
        peak_limit_dbfs=-1.5,
    )
    parent_pre_gain = render_candidate_module._edge_fade(
        render_candidate_module._apply_frozen_ptr(parent.pressure),
    )
    candidate_pre_gain = render_candidate_module._edge_fade(
        render_candidate_module._apply_frozen_ptr(candidate.pressure),
    )

    produced = render_stage_l_named_artifacts(
        tmp_path / "produced",
        trace=trace,
        parent_renderer=lambda actual: _diagnostic_render(actual, candidate=False),
        candidate_renderer=lambda actual: _diagnostic_render(actual, candidate=True),
        source_commit="3d65c04d2101048190aa8a720972366dec9a604b",
        parent_profile_sha256="2" * 64,
        candidate_profile_sha256="1" * 64,
        trace_version="stage-l-short-test-v1",
    )
    payload = json.loads(Path(produced["artifact_manifest_path"]).read_text(encoding="utf-8"))

    for relative, raw_lufs, raw_peak_dbfs, final_pcm in (
        (
            WAV_DESTINATIONS[0],
            render_candidate_module.measure_loudness(parent_pre_gain, 48_000).integrated_lufs,
            render_candidate_module.measure_loudness(parent_pre_gain, 48_000).peak_dbfs,
            bundle.parent_pcm,
        ),
        (
            WAV_DESTINATIONS[1],
            render_candidate_module.measure_loudness(candidate_pre_gain, 48_000).integrated_lufs,
            render_candidate_module.measure_loudness(candidate_pre_gain, 48_000).peak_dbfs,
            bundle.candidate_pcm,
        ),
    ):
        record = payload["artifacts"][relative]
        final_metrics = render_candidate_module.measure_loudness(final_pcm, 48_000)
        assert record["actual_gain_db"] == pytest.approx(bundle.gain_db)
        assert record["raw_lufs"] == pytest.approx(raw_lufs)
        assert record["raw_peak_dbfs"] == pytest.approx(raw_peak_dbfs)
        assert record["final_lufs"] == pytest.approx(final_metrics.integrated_lufs)
        assert record["final_peak_dbfs"] == pytest.approx(final_metrics.peak_dbfs)


def test_producer_handoff_rejects_unbound_final_pcm_input_sha_claims(tmp_path: Path) -> None:
    _produced, payload = _produced_input(tmp_path)
    for relative in WAV_DESTINATIONS[:3]:
        forged = json.loads(json.dumps(payload))
        record = forged["artifacts"][relative]
        record["final_pcm_input_sha256"] = "f" * 64
        record["producer_receipt"]["final_pcm_input_sha256"] = "f" * 64

        with pytest.raises(ValueError, match="final PCM input binding"):
            named_review_module._validate_producer_handoff(forged)


def _fully_forged_v3_artifact_input(tmp_path: Path) -> ProducedStageLArtifacts:
    """Forge a self-consistent v3 JSON handoff around arbitrary healthy PCM."""
    _, payload = _produced_input(tmp_path)
    forged_root = tmp_path / "forged"
    forged_root.mkdir()
    for index, destination in enumerate(WAV_DESTINATIONS):
        path = forged_root / f"arbitrary-{index:02d}.wav"
        _write_pcm24(path, value=0.01 + index * 0.001)
        pcm_sha = _sha(path)
        record = payload["artifacts"][destination]
        record["path"] = str(path)
        record["sha256"] = pcm_sha
        record["pcm_sha256"] = pcm_sha
        receipt = record["producer_receipt"]
        receipt["pcm_sha256"] = pcm_sha
        receipt["frame_count"] = _wav_frames(path)
        receipt["duration_s"] = _wav_duration(path)
    manifest = tmp_path / "fully-forged-v3.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    serialized_metadata = json.loads(json.dumps({
        "artifact_manifest_path": str(manifest),
        "artifact_manifest_sha256": _sha(manifest),
    }))
    forged = object.__new__(ProducedStageLArtifacts)
    forged._metadata = serialized_metadata  # type: ignore[attr-defined]
    return forged


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def _wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes()


def test_builder_rejects_caller_created_self_hash_fixture(tmp_path: Path) -> None:
    manifest, _manifest_sha = _arbitrary_artifact_input(tmp_path)

    with pytest.raises(ValueError, match="producer"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            produced_artifacts=manifest,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )


def test_builder_rejects_fully_schema_valid_forged_v3_with_healthy_arbitrary_pcm(tmp_path: Path) -> None:
    forged_capability = _fully_forged_v3_artifact_input(tmp_path)

    with pytest.raises(ValueError, match="trusted in-process producer capability"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            produced_artifacts=forged_capability,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )


def test_builder_rejects_missing_per_file_producer_receipt(tmp_path: Path) -> None:
    produced, payload = _produced_input(tmp_path)
    payload["artifacts"][WAV_DESTINATIONS[3]].pop("producer_receipt", None)
    manifest = tmp_path / "missing-receipt.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    Path(produced["artifact_manifest_path"]).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest SHA256 mismatch"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            produced_artifacts=produced,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )


def test_builder_rejects_producer_receipt_frame_count_not_matching_pcm(tmp_path: Path) -> None:
    produced, payload = _produced_input(tmp_path)
    receipt = payload["artifacts"][WAV_DESTINATIONS[3]]["producer_receipt"]
    receipt["frame_count"] += 1
    manifest = tmp_path / "wrong-frame-count.json"
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    Path(produced["artifact_manifest_path"]).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest SHA256 mismatch"):
        build_unqualified_diagnostic_package(
            tmp_path / "review",
            produced_artifacts=produced,
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
        produced_artifacts=None,
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


def test_trusted_producer_capability_is_consumed_after_one_build(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    produced = _artifact_input(tmp_path)
    first_root = tmp_path / "review-first"
    second_root = tmp_path / "review-second"

    build_unqualified_diagnostic_package(
        first_root,
        produced_artifacts=produced,
        task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
    )

    with pytest.raises(ValueError, match="trusted capability already consumed"):
        build_unqualified_diagnostic_package(
            second_root,
            produced_artifacts=produced,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )

    assert first_root.is_dir()
    assert not second_root.exists()


def test_builds_complete_content_addressed_unqualified_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(named_review_module, "measure_loudness", _fast_loudness)
    produced = _artifact_input(tmp_path)
    root = tmp_path / "review"
    result = build_unqualified_diagnostic_package(
        root,
        produced_artifacts=produced,
        task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
    )
    required = {
        "00_OPEN_ME_FIRST.md", *WAV_DESTINATIONS, *NON_WAV_DESTINATIONS,
        "05_Feedback/Jovi_Stage_L_Hellcat_Feedback.csv", "artifact_manifest.json",
        "SHA256SUMS.txt", ZIP_NAME,
    }
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    assert actual == required
    assert result["package_status"] == PARTIAL
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert manifest["qualification_status"] == UNQUALIFIED_DIAGNOSTIC_ONLY
    assert manifest["feedback_status"] == DIAGNOSTIC_FEEDBACK_ALLOWED
    assert manifest["artifact_input_sha256"] == produced["artifact_manifest_sha256"]
    assert manifest["formal_final_provenance"] == "NOT_AVAILABLE"
    assert manifest["full_pipeline_peak_residency"] == 5
    assert all(item["pcm_health"]["frame_count"] > 0 for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["peak_dbfs"] <= -1.5 for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["clipping_count"] == 0 for item in manifest["wav_artifacts"])
    readme = (root / "00_OPEN_ME_FIRST.md").read_text(encoding="utf-8")
    assert "UNQUALIFIED_DIAGNOSTIC_ONLY" in readme
    assert "Human PASS" not in readme and "Approved" not in readme
    feedback_template = root / "05_Feedback/Jovi_Stage_L_Hellcat_Feedback.csv"
    assert feedback_template.is_file()
    assert feedback_template.stat().st_size > 0


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
        assert "artifact-manifest" not in run.stdout
        assert "duration-s" in run.stdout


def test_production_cli_defaults_to_the_non_overwriting_v5_package_root() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.scripts import build_stage_l_named_review

    assert build_stage_l_named_review.DEFAULT_OUTPUT == Path(
        r"E:\Tesla_speed\review_packages\s12-stage-l-hellcat-intake-roughness-v5"
    )
