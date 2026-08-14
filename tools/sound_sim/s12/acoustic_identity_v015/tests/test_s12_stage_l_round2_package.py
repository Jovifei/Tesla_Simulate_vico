from __future__ import annotations

import importlib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave
import zipfile

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import (
    SourceRender,
    VehicleStateTrace,
)


REPO_ROOT = Path(__file__).resolve().parents[5]
MODULE_NAME = (
    "tools.sound_sim.s12.acoustic_identity_v015.scripts."
    "build_stage_l_hellcat_round2_review"
)
SCRIPT_PATH = (
    REPO_ROOT
    / "tools/sound_sim/s12/acoustic_identity_v015/scripts/"
    "build_stage_l_hellcat_round2_review.py"
)


def _package_module():
    return importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.named_review_round2"
    )


def _short_trace() -> VehicleStateTrace:
    time_s = np.linspace(0.0, 0.04, 41, dtype=np.float64)
    rpm = np.linspace(900.0, 4200.0, time_s.size)
    load = np.linspace(0.18, 0.92, time_s.size)
    throttle = np.where(time_s < 0.035, load, 0.01)
    return VehicleStateTrace(
        time_s=time_s,
        rpm=rpm,
        load=load,
        throttle=throttle,
        acceleration_mps2=np.gradient(rpm / 60.0, time_s),
    ).validate()


def _render(trace: VehicleStateTrace, role: str) -> SourceRender:
    count = int(round(float(trace.time_s[-1]) * 48_000)) + 1
    time_s = np.arange(count, dtype=np.float64) / 48_000.0
    scale = {"parent": 0.72, "v8": 0.86, "v9": 1.0}[role]

    def stereo(mono: np.ndarray) -> np.ndarray:
        return np.column_stack((mono, 0.97 * mono))

    low = stereo(0.018 * scale * np.sin(2.0 * np.pi * 92.0 * time_s))
    body = stereo(0.014 * scale * np.sin(2.0 * np.pi * 168.0 * time_s))
    whine = stereo(0.009 * scale * np.sin(2.0 * np.pi * 920.0 * time_s))
    casing = stereo(0.005 * scale * np.sin(2.0 * np.pi * 1460.0 * time_s))
    afterfire = stereo(
        np.where(
            time_s >= 0.032,
            0.008 * scale * np.exp(-(time_s - 0.032) / 0.004),
            0.0,
        )
    )
    stems = {
        "hemi_exhaust_left": 0.54 * low,
        "hemi_exhaust_right": 0.46 * low,
        "hemi_blowdown_body": body,
        "hemi_structure_shock": 0.40 * body,
        "hemi_mechanical_torque_ripple": 0.20 * body,
        "sc_intake_radiated": whine,
        "sc_casing_radiated": casing,
        "sc_bypass_release": 0.10 * whine,
        "afterfire": afterfire,
    }
    pressure = sum(stems.values(), np.zeros_like(low))
    return SourceRender(
        pressure=pressure,
        stems=stems,
        diagnostics={"render_path": f"fixture_{role}"},
    ).validate()


def _produce(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    package = _package_module()
    metrics_calls: list[tuple[object, ...]] = []

    def metrics(*args, **kwargs):
        metrics_calls.append((*args, kwargs))
        return {
            "schema_version": "s12-stage-l-round2-metrics-1",
            "measurement_sources": {
                "source": "actual SourceRender arrays",
                "final_pcm": "independently reopened PCM24 WAVs",
            },
        }

    monkeypatch.setattr(package, "compute_round2_metrics", metrics)
    trace = _short_trace()
    render_calls: list[tuple[str, object]] = []

    def renderer(role: str):
        def run(actual_trace: object) -> SourceRender:
            render_calls.append((role, actual_trace))
            return _render(actual_trace, role)

        return run

    produced = package.render_stage_l_round2_named_artifacts(
        tmp_path / "producer-artifacts",
        trace=trace,
        stage_k_parent_renderer=renderer("parent"),
        stage_l_v8_renderer=renderer("v8"),
        stage_l_v9_renderer=renderer("v9"),
        source_commit="a" * 40,
        candidate_base_commit="b" * 40,
        producer_source_dirty=False,
        producer_source_file_sha256={
            "named_review_round2.py": "4" * 64,
            "render_candidate.py": "5" * 64,
        },
        stage_k_parent_profile_sha256="1" * 64,
        stage_l_v8_profile_sha256="2" * 64,
        stage_l_v9_profile_sha256="3" * 64,
        trace_version="stage-l-round2-short-test-v1",
        diagnostic_durations_s={
            "sc_whine": 0.020,
            "hemi_rumble": 0.020,
            "sc_plus_hemi": 0.020,
            "afterfire": 0.010,
        },
    )
    return package, produced, trace, render_calls, metrics_calls


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_round2_package_module_declares_independent_v6_contract() -> None:
    package = _package_module()

    assert package.PACKAGE_ID == "s12-stage-l-hellcat-intake-roughness-v6"
    assert package.PRODUCER_SCHEMA == "s12-stage-l-round2-named-artifact-producer-1"
    assert package.PACKAGE_SCHEMA == "s12-stage-l-round2-named-review-package-1"
    assert callable(package.render_stage_l_round2_named_artifacts)
    assert callable(package.build_round2_unqualified_diagnostic_package)


def test_round2_producer_uses_same_trace_once_and_one_formal_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package_module()
    real_bundle = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate"
    ).render_stage_l_round2_formal_final_pcm_bundle
    formal_calls: list[tuple[object, ...]] = []

    def formal(*args, **kwargs):
        formal_calls.append((*args, kwargs))
        return real_bundle(*args, **kwargs)

    monkeypatch.setattr(package, "render_stage_l_round2_formal_final_pcm_bundle", formal)
    package, produced, trace, render_calls, metrics_calls = _produce(tmp_path, monkeypatch)
    producer_manifest = json.loads(
        Path(str(produced["artifact_manifest_path"])).read_text(encoding="utf-8")
    )

    assert [role for role, _ in render_calls] == ["parent", "v8", "v9"]
    assert all(actual_trace is trace for _, actual_trace in render_calls)
    assert len(formal_calls) == 1
    assert len(metrics_calls) == 1
    formal = [
        producer_manifest["artifacts"][path]
        for path in package.FORMAL_WAV_DESTINATIONS
    ]
    assert formal[3]["receipt"]["final_pcm_input_sha256"] == formal[2]["pcm_sha256"]
    assert producer_manifest["bindings"]["producer_source_commit"] == "a" * 40
    assert producer_manifest["bindings"]["candidate_base_commit"] == "b" * 40
    assert formal[3]["receipt"]["comfort_static_gain_db"] >= 0.0
    assert formal[3]["receipt"]["pipeline_order"] == [
        "frozen_ptr",
        "edge_fade",
        "one_fixed_whole_cycle_gain",
        "pcm24",
        "candidate_comfort_static_gain",
        "pcm24",
    ]
    assert formal[3]["receipt"]["final_pcm_input_sha256"] == formal[2]["pcm_sha256"]


def test_round2_package_builds_exact_four_plus_four_wavs_with_receipts_sha_and_crc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, produced, _trace, _render_calls, _metrics_calls = _produce(
        tmp_path, monkeypatch
    )
    root = tmp_path / "review-v6"
    result = package.build_round2_unqualified_diagnostic_package(
        root,
        produced_artifacts=produced,
    )

    assert result["package_status"] == "PARTIAL"
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert manifest["qualification_status"] == "UNQUALIFIED_DIAGNOSTIC_ONLY"
    assert manifest["human_feedback_content_read"] is False
    assert manifest["wav_count"] == 8
    assert len(package.FORMAL_WAV_DESTINATIONS) == 4
    assert len(package.DIAGNOSTIC_WAV_DESTINATIONS) == 4
    assert set(package.WAV_DESTINATIONS) == {
        item["path"] for item in manifest["wav_artifacts"]
    }
    assert all(item["pcm_health"]["passes"] for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["sample_rate_hz"] == 48_000 for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["channels"] == 2 for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["pcm_bits"] == 24 for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["clipping_count"] == 0 for item in manifest["wav_artifacts"])
    assert all(item["pcm_health"]["peak_dbfs"] <= -1.5 + 1.0e-6 for item in manifest["wav_artifacts"])
    afterfire = next(
        item for item in manifest["wav_artifacts"]
        if item["path"].endswith("Dodge_Hellcat_Afterfire_10s.wav")
    )
    assert afterfire["pcm_health"]["peak_dbfs"] > -100.0
    assert not tuple(root.rglob("*.csv"))
    metrics = json.loads((root / "03_Metrics/round2_metrics.json").read_text(encoding="utf-8"))
    assert metrics["final_pcm24"]["reference_role"] == "StageL_v8_baseline"
    assert metrics["final_pcm24"]["candidate_role"] == "StageL_v9_candidate"

    diagnostics = [
        next(item for item in manifest["wav_artifacts"] if item["path"] == path)
        for path in package.DIAGNOSTIC_WAV_DESTINATIONS
    ]
    for item in diagnostics:
        evidence = item["producer_receipt"]["event_evidence"]
        assert evidence["window_end_sample"] > evidence["window_start_sample"]
        assert evidence["window_end_s"] >= evidence["window_start_s"]
        assert evidence["source_stems"]
        assert evidence["window_policy"] == "actual_source_array_slice_then_length_bound"

    sums = (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    for line in sums:
        expected, relative = line.split("  ", 1)
        assert _sha256(root / relative) == expected
    zip_path = root / package.ZIP_NAME
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path != zip_path
        }


def test_round2_capability_is_one_time_and_arbitrary_self_hash_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, produced, _trace, _render_calls, _metrics_calls = _produce(
        tmp_path, monkeypatch
    )
    first = tmp_path / "first"
    package.build_round2_unqualified_diagnostic_package(
        first,
        produced_artifacts=produced,
    )

    second = tmp_path / "second"
    with pytest.raises(ValueError, match="already consumed"):
        package.build_round2_unqualified_diagnostic_package(
            second,
            produced_artifacts=produced,
        )
    with pytest.raises(ValueError, match="trusted in-process producer capability"):
        package.build_round2_unqualified_diagnostic_package(
            tmp_path / "forged",
            produced_artifacts={
                "artifact_manifest_path": str(first / "artifact_manifest.json"),
                "artifact_manifest_sha256": _sha256(first / "artifact_manifest.json"),
            },
        )
    assert not second.exists()
    assert not (tmp_path / "forged").exists()


def test_round2_packager_rejects_tampered_trusted_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, produced, _trace, _render_calls, _metrics_calls = _produce(tmp_path, monkeypatch)
    manifest_path = Path(str(produced["artifact_manifest_path"]))
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = payload["artifacts"][package.FORMAL_WAV_DESTINATIONS[2]]
    target["producer_receipt"]["pcm_sha256"] = "0" * 64
    target["receipt"]["pcm_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package._CAPABILITIES[produced] = (manifest_path.resolve(), _sha256(manifest_path))
    with pytest.raises(ValueError, match="PCM SHA"):
        package.build_round2_unqualified_diagnostic_package(
            tmp_path / "tampered-receipt", produced_artifacts=produced
        )
    assert not (tmp_path / "tampered-receipt").exists()


def test_round2_packager_rejects_silent_invalid_zip_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, produced, _trace, _render_calls, _metrics_calls = _produce(tmp_path, monkeypatch)

    def broken_writer(_root: Path, zip_path: Path) -> None:
        zip_path.write_bytes(b"not-a-zip")

    monkeypatch.setattr(package, "_write_deterministic_zip", broken_writer)
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        package.build_round2_unqualified_diagnostic_package(
            tmp_path / "invalid-zip", produced_artifacts=produced
        )
    assert not (tmp_path / "invalid-zip").exists()


def test_round2_atomic_publish_leaves_final_root_absent_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, produced, _trace, _render_calls, _metrics_calls = _produce(
        tmp_path, monkeypatch
    )

    def fail_zip(*_args, **_kwargs) -> None:
        raise RuntimeError("injected ZIP failure")

    monkeypatch.setattr(package, "_write_deterministic_zip", fail_zip)
    root = tmp_path / "atomic-review"
    with pytest.raises(RuntimeError, match="injected ZIP failure"):
        package.build_round2_unqualified_diagnostic_package(
            root,
            produced_artifacts=produced,
        )

    assert not root.exists()
    assert not tuple(tmp_path.glob(".atomic-review.staging-*"))


def test_round2_default_diagnostic_windows_are_exactly_18_18_18_10_seconds() -> None:
    package = _package_module()

    assert package.DIAGNOSTIC_DURATIONS_S == {
        "sc_whine": 18.0,
        "hemi_rumble": 18.0,
        "sc_plus_hemi": 18.0,
        "afterfire": 10.0,
    }


@pytest.mark.parametrize(
    "command",
    (
        (sys.executable, str(SCRIPT_PATH), "--help"),
        (sys.executable, "-m", MODULE_NAME, "--help"),
    ),
    ids=("direct", "module"),
)
def test_round2_cli_supports_help(command: tuple[str, ...]) -> None:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
    assert "artifact-manifest" not in completed.stdout


def test_round2_cli_defaults_to_canonical_v6_paths() -> None:
    cli = importlib.import_module(MODULE_NAME)

    assert cli.DEFAULT_OUTPUT == Path(
        r"E:\Tesla_speed\review_packages\s12-stage-l-hellcat-intake-roughness-v6"
    )
    assert cli.DEFAULT_V8_PROFILE.name == "hellcat_candidate_v8.json"
    assert cli.DEFAULT_V9_PROFILE.name == "hellcat_candidate_v9.json"
