"""End-to-end fixture tests for the local Stage Y calibration bundle."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import wave

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.calibration_bundle import (
    load_calibration_bundle,
    run_calibration_bundle,
)


def _write_bundle(root: Path, *, rights_status: str = "PROJECT_OWNED") -> Path:
    root.mkdir(parents=True)
    sample_rate = 8000
    duration_s = 2.0
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    rpm = 1200.0 + 300.0 * t / duration_s
    phase = np.zeros_like(t)
    phase[1:] = np.cumsum(0.5 * (rpm[1:] + rpm[:-1]) * 2.0 * np.pi / 60.0 / sample_rate)
    audio = 0.55 * np.sin(4.0 * phase) + 0.08 * np.sin(11.0 * phase + 0.2)
    pcm = np.clip(np.rint(audio * 32767.0), -32768, 32767).astype("<i2")
    audio_path = root / "audio.wav"
    with wave.open(str(audio_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    (root / "rights.json").write_text(
        json.dumps({"rights_status": rights_status, "source_sha256": digest, "provider": "fixture owner"}),
        encoding="utf-8",
    )
    (root / "recording.json").write_text(
        json.dumps(
            {
                "vehicle_id": "fixture_v8",
                "trim_or_engine": "fixture engine",
                "microphone_position": "rear_exhaust_1m",
                "agc_post_processing": "none",
            }
        ),
        encoding="utf-8",
    )
    with (root / "state.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "rpm", "load", "boost", "state"])
        writer.writeheader()
        for time_s in np.linspace(0.0, duration_s, 21):
            writer.writerow(
                {
                    "time_s": time_s,
                    "rpm": 1200.0 + 300.0 * time_s / duration_s,
                    "load": 0.45,
                    "boost": 0.2,
                    "state": "steady",
                }
            )
    return root


def test_calibration_bundle_fails_closed_without_supported_rights(tmp_path: Path) -> None:
    root = _write_bundle(tmp_path / "unverified", rights_status="UNVERIFIED")
    with pytest.raises(PermissionError):
        load_calibration_bundle(root)


def test_calibration_bundle_emits_only_derived_hash_bound_assets(tmp_path: Path) -> None:
    root = _write_bundle(tmp_path / "authorized")
    output = tmp_path / "derived"
    receipt = run_calibration_bundle(root, output, phase_samples=128)
    assert receipt["status"] == "DERIVED_CALIBRATION_ASSETS_READY"
    assert receipt["raw_audio_copied"] is False
    assert receipt["runtime_default_enabled"] is False
    assert receipt["formal_status"] == "REQUIRES_MATLAB_MOSQITO_AND_HUMAN_VALIDATION"
    assert set(receipt["outputs"]) == {
        "harmonic_timbre_map.json",
        "cycle_residual_manifest.json",
        "cycle_residual_bank.npz",
    }
    for name, digest in receipt["outputs"].items():
        path = output / name
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert not (output / "audio.wav").exists()
    timbre = json.loads((output / "harmonic_timbre_map.json").read_text(encoding="utf-8"))
    assert timbre["raw_audio_embedded"] is False
    residual = json.loads((output / "cycle_residual_manifest.json").read_text(encoding="utf-8"))
    assert residual["runtime_default_enabled"] is False
