from __future__ import annotations

from dataclasses import dataclass
import gc
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import weakref

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _write_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.named_review import (
    REQUIRED_SOURCE_FILE_IDS,
    build_stage_i_named_review,
)


_METRIC_ARTIFACT_LAYOUT = {
    "order_map": "04_Metrics/order_map.png",
    "spectrogram": "04_Metrics/spectrogram.png",
    "state_ratio_map": "04_Metrics/state_ratio_map.png",
    "transient_response": "04_Metrics/transient_response.png",
    "candidate_comparison_metrics": "04_Metrics/candidate_comparison_metrics.json",
}
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.source_evidence import (
    CANDIDATE_ROLES,
    _candidate_parameter_usage,
    render_stage_i_named_sources,
)


@dataclass(frozen=True)
class _Profile:
    candidate_id: str
    amplitude: float


def _trace(_: str, duration_s: float) -> VehicleStateTrace:
    frames = int(round(duration_s * 48000))
    time_s = np.arange(frames, dtype=np.float64) / 48000.0
    first = max(frames // 5, 1)
    last = max(frames // 5, 1)
    middle = frames - first - last
    rpm = np.concatenate(
        (
            np.full(first, 900.0),
            np.linspace(1800.0, 4200.0, middle),
            np.full(last, 4200.0),
        )
    )
    load = np.concatenate(
        (
            np.full(first, 0.14),
            np.linspace(0.45, 0.90, middle),
            np.full(last, 0.90),
        )
    )
    throttle = load.copy()
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _scenario(vehicle_id: str, _: str, duration_s: float) -> VehicleStateTrace:
    return _trace(vehicle_id, duration_s)


def _render(
    trace: VehicleStateTrace,
    amplitude: float,
    candidate_id: str,
    *,
    legacy_usage: bool = False,
) -> SourceRender:
    time_s = trace.time_s
    blower_mono = amplitude * np.sin(2.0 * np.pi * 720.0 * time_s)
    exhaust_mono = 0.12 * np.sin(2.0 * np.pi * 95.0 * time_s)
    bypass_mono = amplitude * 0.35 * np.sin(2.0 * np.pi * 430.0 * time_s)
    blower = np.column_stack((blower_mono, blower_mono))
    exhaust = np.column_stack((exhaust_mono, exhaust_mono))
    bypass = np.column_stack((bypass_mono, bypass_mono))
    usage = (
        {"requested": [], "consumed": [], "unused": []}
        if legacy_usage
        else {
            "requested": ["source.blower_gain_scale"],
            "read": ["source.blower_gain_scale"],
            "configured": ["source.blower_gain_scale"],
            "active": ["source.blower_gain_scale"],
            "inactive": [],
            "consumed": ["source.blower_gain_scale"],
            "unused": [],
        }
    )
    return SourceRender(
        pressure=blower + exhaust + bypass,
        stems={
            "blower": blower,
            "blower_shaft": 0.20 * blower,
            "blower_lobe_family": 0.50 * blower,
            "blower_upper_family": 0.15 * blower,
            "blower_sidebands": 0.10 * blower,
            "exhaust": exhaust,
            "blower_bypass_release": bypass,
            "exhaust_rumble": 0.25 * exhaust,
        },
        diagnostics={
            "candidate_id": candidate_id,
            "candidate_parameter_usage": usage,
        },
    ).validate()


def _stage_h_renderer(trace: VehicleStateTrace) -> SourceRender:
    return _render(trace, 0.025, "Hellcat_candidate_v5", legacy_usage=True)


def _stage_i_renderer(trace: VehicleStateTrace, profile: _Profile) -> SourceRender:
    return _render(trace, profile.amplitude, profile.candidate_id)


def _stage_h_root(root: Path, duration_s: float) -> Path:
    anchor_root = root / "02_Anchor_Mapping"
    anchor_root.mkdir(parents=True)
    trace = _trace("hellcat", duration_s)
    for index, name in enumerate(
        ("Ferrari_458_StageG_Unchanged_60s.wav", "RX7_FD_StageG_Unchanged_60s.wav")
    ):
        _write_pcm24_wav(anchor_root / name, _render(trace, 0.02 + index * 0.005, name).pressure)
    return root


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metric_artifacts(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}
    for key, relative in _METRIC_ARTIFACT_LAYOUT.items():
        path = root / Path(relative).name
        if path.suffix == ".png":
            path.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        else:
            path.write_text('{"scope":"synthetic","status":"candidate"}\n', encoding="utf-8")
        artifacts[key] = path
    return artifacts


def _profiles() -> dict[str, _Profile]:
    return {
        "a_balanced": _Profile("I6-A Balanced", 0.030),
        "b_whine_forward": _Profile("I6-B Whine Forward", 0.040),
        "c_softer_mechanical": _Profile("I6-C Softer Mechanical", 0.035),
    }


def test_source_evidence_renders_complete_manifest_with_shared_traces(tmp_path: Path) -> None:
    duration_s = 0.10
    stage_h_root = _stage_h_root(tmp_path / "stage_h", duration_s)
    result = render_stage_i_named_sources(
        tmp_path / "sources",
        stage_h_review_root=stage_h_root,
        stage_i_profiles=_profiles(),
        stage_h_renderer=_stage_h_renderer,
        stage_i_renderer=_stage_i_renderer,
        full_cycle_duration_s=duration_s,
        acceleration_duration_s=duration_s,
        event_duration_s=duration_s,
        trace_builder=_trace,
        scenario_builder=_scenario,
    )

    manifest_path = Path(result["source_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest["files"]) == set(REQUIRED_SOURCE_FILE_IDS)
    assert set(manifest["evidence"]) == set(REQUIRED_SOURCE_FILE_IDS)
    assert manifest["sealed_key_read"] is False
    assert manifest["status"] == "SOURCE_EVIDENCE_READY"

    full_trace_sha = {
        manifest["evidence"][file_id]["trace_sha256"]
        for file_id in (
            "stage_h_v5_baseline_60s",
            "stage_i_v6_a_balanced_60s",
            "stage_i_v6_b_whine_forward_60s",
            "stage_i_v6_c_softer_mechanical_60s",
        )
    }
    assert len(full_trace_sha) == 1
    assert all(item["health"]["pcm"] == "PCM_24" for item in manifest["evidence"].values())
    assert all(item["health"]["sample_rate_hz"] == 48000 for item in manifest["evidence"].values())
    assert all(item["health"]["channels"] == 2 for item in manifest["evidence"].values())
    assert all(item["health"]["finite"] is True for item in manifest["evidence"].values())
    assert all(item["health"]["clipping_count"] == 0 for item in manifest["evidence"].values())
    assert all(item["fixed_loudness_gain_count"] == 1 for item in manifest["evidence"].values() if item["product_audio"])
    for file_id in (
        "stage_h_v5_baseline_60s",
        "stage_i_v6_a_balanced_60s",
        "stage_i_v6_b_whine_forward_60s",
        "stage_i_v6_c_softer_mechanical_60s",
    ):
        item = manifest["evidence"][file_id]
        assert item["source_metrics"]["scope"].startswith("C/synthetic")
        assert len(item["source_render_sha256"]) == 64
        assert item["source_render_hash_scope"] == "pressure_and_named_stems_f64le"
        assert item["candidate_parameter_usage"]["unused"] == []
        assert len(item["profile_binding"]["profile_sha256"]) == 64

    assert manifest["evidence"]["stage_i_shift_dip_rebuild_12s"]["stem"] == "blower"
    assert manifest["evidence"]["stage_i_lift_bypass_12s"]["stem"] == "blower_bypass_release"
    assert manifest["evidence"]["stage_i_exhaust_only_acceleration"]["stem"] == "exhaust"
    assert manifest["evidence"]["stage_h_blower_only_acceleration"]["stem"] == "blower"

    for file_id, source_name in (
        ("ferrari_458_stage_h_unchanged_60s", "Ferrari_458_StageG_Unchanged_60s.wav"),
        ("rx7_fd_stage_h_unchanged_60s", "RX7_FD_StageG_Unchanged_60s.wav"),
    ):
        assert _digest(Path(manifest["files"][file_id])) == _digest(stage_h_root / "02_Anchor_Mapping" / source_name)
        assert manifest["evidence"][file_id]["copied_unchanged"] is True


def test_source_manifest_feeds_named_review_without_renderer_import_coupling(tmp_path: Path) -> None:
    duration_s = 0.08
    stage_h_root = _stage_h_root(tmp_path / "stage_h", duration_s)
    rendered = render_stage_i_named_sources(
        tmp_path / "sources",
        stage_h_review_root=stage_h_root,
        stage_i_profiles=_profiles(),
        stage_h_renderer=_stage_h_renderer,
        stage_i_renderer=_stage_i_renderer,
        full_cycle_duration_s=duration_s,
        acceleration_duration_s=duration_s,
        event_duration_s=duration_s,
        trace_builder=_trace,
        scenario_builder=_scenario,
    )
    manifest = json.loads(Path(rendered["source_manifest"]).read_text(encoding="utf-8"))
    durations = {file_id: duration_s for file_id in REQUIRED_SOURCE_FILE_IDS}
    labels = {
        "I6-A Balanced": "stage_i_v6_a_balanced_60s",
        "I6-B Whine Forward": "stage_i_v6_b_whine_forward_60s",
        "I6-C Softer Mechanical": "stage_i_v6_c_softer_mechanical_60s",
    }
    reference = {
        "schema_version": "test-reference-1",
        "automatic_status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "candidates": {},
    }
    qualification_candidates: dict[str, object] = {}
    metric_candidates: dict[str, object] = {}
    for index, (label, file_id) in enumerate(labels.items(), 1):
        evidence = manifest["evidence"][file_id]
        profile_binding = evidence["profile_binding"]
        profile_file_sha = hashlib.sha256(f"{label}:profile-file".encode()).hexdigest()
        profile_binding["profile_file_sha256"] = profile_file_sha
        metrics = {"blower_load_correlation": 0.90 + index * 0.01}
        qualification_candidates[label] = {
            "source_file_id": file_id,
            "binding": {
                "candidate_id": evidence["candidate_id"],
                "candidate_sha256": profile_binding["profile_sha256"],
                "profile_sha256": profile_file_sha,
                "render_sha256": evidence["source_render_sha256"],
                "final_pcm_sha256": evidence["sha256"],
            },
            "gates": {"all_pass": False},
            "metrics": metrics,
        }
        metric_candidates[label] = {"metrics": metrics}
    source_manifest_path = tmp_path / "source_manifest_bound.json"
    source_manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(
        json.dumps(
            {
                "automatic_reference_status": "PARTIAL / AUTOMATED_GATE_FAIL",
                "candidates": qualification_candidates,
                "reference_summary": reference,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metric_artifacts = _metric_artifacts(tmp_path / "metrics")
    metric_artifacts["candidate_comparison_metrics"].write_text(
        json.dumps({"candidates": metric_candidates}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    package = build_stage_i_named_review(
        tmp_path / "named",
        source_wavs=manifest["files"],
        metric_artifacts=metric_artifacts,
        qualification_json=qualification_path,
        reference_distance_json=reference_path,
        source_manifest=source_manifest_path,
        expected_duration_s=durations,
        diagnostic_mode=True,
    )

    assert package["status"] == "UNQUALIFIED_DIAGNOSTIC_ONLY / PARTIAL / AUTOMATED_GATE_FAIL"


def test_render_stage_i_named_sources_script_supports_direct_help() -> None:
    script = Path(__file__).parents[1] / "scripts" / "render_stage_i_named_sources.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--stage-h-review-root" in result.stdout


def test_source_evidence_requires_exact_three_candidate_roles(tmp_path: Path) -> None:
    profiles = _profiles()
    profiles.pop("c_softer_mechanical")

    with pytest.raises(ValueError, match="candidate roles"):
        render_stage_i_named_sources(
            tmp_path / "sources",
            stage_h_review_root=_stage_h_root(tmp_path / "stage_h", 0.05),
            stage_i_profiles=profiles,
            stage_h_renderer=_stage_h_renderer,
            stage_i_renderer=_stage_i_renderer,
            full_cycle_duration_s=0.05,
            acceleration_duration_s=0.05,
            event_duration_s=0.05,
            trace_builder=_trace,
            scenario_builder=_scenario,
        )

    assert CANDIDATE_ROLES == ("a_balanced", "b_whine_forward", "c_softer_mechanical")


def test_default_stage_h_loader_uses_authoritative_profile_and_checks_review_copy(
    tmp_path: Path,
) -> None:
    duration_s = 0.05
    stage_h_root = _stage_h_root(tmp_path / "stage_h", duration_s)
    authoritative = (
        Path(__file__).resolve().parents[1]
        / "targets"
        / "stage_h_candidates"
        / "Hellcat_candidate_v5.json"
    )
    copied = stage_h_root / "candidates" / "hellcat_StageH_candidate_v5.json"
    copied.parent.mkdir(parents=True)
    shutil.copyfile(authoritative, copied)

    result = render_stage_i_named_sources(
        tmp_path / "sources",
        stage_h_review_root=stage_h_root,
        stage_i_profiles=_profiles(),
        stage_i_renderer=_stage_i_renderer,
        full_cycle_duration_s=duration_s,
        acceleration_duration_s=duration_s,
        event_duration_s=duration_s,
        trace_builder=_trace,
        scenario_builder=_scenario,
    )

    assert result["source_count"] == len(REQUIRED_SOURCE_FILE_IDS)


def test_default_stage_h_loader_rejects_drifted_review_candidate_copy(tmp_path: Path) -> None:
    duration_s = 0.05
    stage_h_root = _stage_h_root(tmp_path / "stage_h", duration_s)
    authoritative = (
        Path(__file__).resolve().parents[1]
        / "targets"
        / "stage_h_candidates"
        / "Hellcat_candidate_v5.json"
    )
    copied = stage_h_root / "candidates" / "hellcat_StageH_candidate_v5.json"
    copied.parent.mkdir(parents=True)
    copied.write_bytes(authoritative.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="does not match authoritative Stage-H candidate"):
        render_stage_i_named_sources(
            tmp_path / "sources",
            stage_h_review_root=stage_h_root,
            stage_i_profiles=_profiles(),
            stage_i_renderer=_stage_i_renderer,
            full_cycle_duration_s=duration_s,
            acceleration_duration_s=duration_s,
            event_duration_s=duration_s,
            trace_builder=_trace,
            scenario_builder=_scenario,
        )


def test_full_cycle_renders_are_released_before_rendering_next_role(tmp_path: Path) -> None:
    active = 0
    maximum = 0

    def tracked(trace: VehicleStateTrace, amplitude: float, candidate_id: str) -> SourceRender:
        nonlocal active, maximum
        render = _render(trace, amplitude, candidate_id)
        active += 1
        maximum = max(maximum, active)

        def released() -> None:
            nonlocal active
            active -= 1

        weakref.finalize(render, released)
        return render

    def render_h(trace: VehicleStateTrace) -> SourceRender:
        render = tracked(trace, 0.025, "Hellcat_candidate_v5")
        return SourceRender(
            pressure=render.pressure,
            stems=render.stems,
            diagnostics={
                **render.diagnostics,
                "candidate_parameter_usage": {
                    "requested": [],
                    "consumed": [],
                    "unused": [],
                },
            },
        )

    def render_i(trace: VehicleStateTrace, profile: _Profile) -> SourceRender:
        return tracked(trace, profile.amplitude, profile.candidate_id)

    gc.collect()
    render_stage_i_named_sources(
        tmp_path / "sources",
        stage_h_review_root=_stage_h_root(tmp_path / "stage_h", 0.05),
        stage_i_profiles=_profiles(),
        stage_h_renderer=render_h,
        stage_i_renderer=render_i,
        full_cycle_duration_s=0.05,
        acceleration_duration_s=0.05,
        event_duration_s=0.05,
        trace_builder=_trace,
        scenario_builder=_scenario,
    )
    gc.collect()

    assert maximum == 1
    assert active == 0


def test_parameter_usage_normalizes_legacy_stage_h_without_inventing_activity() -> None:
    legacy = _stage_h_renderer(_trace("hellcat", 0.05))

    normalized = _candidate_parameter_usage(legacy, role="stage_h")

    assert normalized == {
        "requested": [],
        "read": [],
        "configured": [],
        "active": None,
        "inactive": None,
        "consumed": [],
        "unused": [],
        "activity_verification": "NOT_AVAILABLE_LEGACY_STAGE_H",
    }


def test_parameter_usage_requires_stage_i_activity_evidence() -> None:
    active = _stage_i_renderer(_trace("hellcat", 0.05), _profiles()["a_balanced"])

    normalized = _candidate_parameter_usage(active, role="a_balanced")

    assert normalized["active"] == ["source.blower_gain_scale"]
    assert normalized["inactive"] == []
    assert normalized["activity_verification"] == "MEASURED_STAGE_I_RENDER_ACTIVITY"


def test_blower_diagnostic_group_preserves_raw_loudness_spread_with_one_common_gain(
    tmp_path: Path,
) -> None:
    duration_s = 0.05
    result = render_stage_i_named_sources(
        tmp_path / "sources",
        stage_h_review_root=_stage_h_root(tmp_path / "stage_h", duration_s),
        stage_i_profiles=_profiles(),
        stage_h_renderer=_stage_h_renderer,
        stage_i_renderer=_stage_i_renderer,
        full_cycle_duration_s=duration_s,
        acceleration_duration_s=duration_s,
        event_duration_s=duration_s,
        trace_builder=_trace,
        scenario_builder=_scenario,
    )
    manifest = json.loads(Path(result["source_manifest"]).read_text(encoding="utf-8"))
    blower_ids = (
        "stage_h_blower_only_acceleration",
        "stage_i_a_blower_only_acceleration",
        "stage_i_b_blower_only_acceleration",
        "stage_i_c_blower_only_acceleration",
    )
    entries = [manifest["evidence"][file_id] for file_id in blower_ids]
    raw = [entry["group_raw_integrated_lufs"] for entry in entries]
    final = [entry["loudness"]["integrated_lufs"] for entry in entries]
    gains = [entry["group_gain_db"] for entry in entries]

    assert len({round(value, 9) for value in gains}) == 1
    assert all(value <= 0.0 for value in gains)
    assert max(final) - min(final) == pytest.approx(max(raw) - min(raw), abs=0.10)
    assert max(final) - min(final) > 2.0
    assert all(
        entry["group_target_lufs"] == pytest.approx(min(-20.0, min(raw)))
        for entry in entries
    )
