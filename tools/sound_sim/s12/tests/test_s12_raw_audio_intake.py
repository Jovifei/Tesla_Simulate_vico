from __future__ import annotations

import csv
import wave
from pathlib import Path

import numpy as np
import pytest

import tools.sound_sim.s12.real_reference as real_reference
import tools.sound_sim.s12.real_reference.stage_r_execute as stage_r_execute


def _write_wav(path: Path, *, sample_rate_hz: int = 48_000, duration_s: float = 0.1) -> None:
    frames = int(round(sample_rate_hz * duration_s))
    signal = np.zeros(frames, dtype="<i2").tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate_hz)
        stream.writeframes(signal)


def _write_state(root: Path, *, complete: bool = True) -> dict[str, object]:
    rows = [
        {"time_s": 0.0, "rpm": 1_000.0, "load": 0.2, "throttle": 0.3, "gear": 2.0, "shift_event": 0.0},
        {"time_s": 0.05, "rpm": 2_000.0, "load": 0.6, "throttle": 0.8, "gear": 2.0, "shift_event": 0.0},
        {"time_s": 0.099, "rpm": 3_000.0, "load": 0.9, "throttle": 1.0, "gear": 3.0, "shift_event": 1.0},
    ]
    paths: dict[str, str] = {}
    columns = {
        "rpm_trace_path": ("rpm.csv", ("time_s", "rpm")),
        "load_throttle_trace_path": ("load_throttle.csv", ("time_s", "load", "throttle")),
        "gear_shift_trace_path": ("gear_shift.csv", ("time_s", "gear", "shift_event")),
    }
    for key, (name, fields) in columns.items():
        path = root / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields))
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row[field] for field in fields})
        paths[key] = name
    if not complete:
        (root / "gear_shift.csv").write_text("gear\n2\n3\n", encoding="utf-8")
    paths.update(
        {
            "trace_root": str(root),
            "time_window": {"start_s": 0.0, "end_s": 0.099},
            "units": {
                "time_s": "s",
                "rpm": "rpm",
                "load": "fraction_0_1",
                "throttle": "fraction_0_1",
                "gear": "integer_index",
                "shift_event": "0_or_1",
            },
        }
    )
    return paths


def _complete_spec(root: Path) -> dict[str, object]:
    audio = root / "ferrari_full_pull_01.wav"
    _write_wav(audio)
    state = _write_state(root)
    return {
        "recording_id": "ferrari_458_full_pull_01",
        "vehicle_id": "ferrari_458",
        "scenario": "full_pull",
        "audio_path": str(audio),
        "source_url": "https://example.com/original-capture",
        "source_kind": "controlled_raw_audio",
        "license_status": "CONFIRMED",
        "rights_evidence": "E:/Claude_allow/Download/rights/ferrari-license.pdf",
        "exact_vehicle_trim": "Ferrari 458 Italia 2010 stock",
        "stock_exhaust_confirmation": "CONFIRMED_STOCK",
        "microphone_position": "EXTERIOR_REAR",
        "recording_device_agc": "DOCUMENTED_NO_AGC",
        "raw_audio_confirmed": True,
        "state": state,
    }


def _ingest(*args: object, **kwargs: object) -> dict[str, object]:
    function = getattr(real_reference, "ingest_raw_reference_specs", None)
    assert function is not None, "raw R1 intake API is not implemented"
    return function(*args, **kwargs)


def test_raw_intake_rejects_audio_outside_approved_external_root(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    outside = tmp_path / "outside.wav"
    _write_wav(outside)
    spec = _complete_spec(tmp_path)
    spec["audio_path"] = str(outside)
    with pytest.raises(ValueError, match="approved download root"):
        _ingest([spec], output_root=approved / "out", allowed_root=approved)


def test_raw_intake_keeps_incomplete_state_at_not_r1(tmp_path: Path) -> None:
    spec = _complete_spec(tmp_path)
    spec["state"] = _write_state(tmp_path, complete=False)
    manifest = _ingest([spec], output_root=tmp_path / "out", allowed_root=tmp_path)
    record = manifest["records"][0]
    assert record["evidence"]["level"] != "R1"
    assert record["evidence"]["r1_eligible"] is False
    assert manifest["automatic_tuning_eligible"] is False


def test_raw_intake_accepts_complete_external_r1_without_copying_audio(tmp_path: Path) -> None:
    spec = _complete_spec(tmp_path)
    spec["audio_path"] = Path(str(spec["audio_path"])).name
    spec["state"]["trace_root"] = "."
    output_root = tmp_path / "out"
    manifest = _ingest([spec], output_root=output_root, allowed_root=tmp_path)
    record = manifest["records"][0]
    assert manifest["status"] == "R1_REFERENCE_PACKAGE_READY"
    assert record["evidence"]["level"] == "R1"
    assert record["evidence"]["r1_eligible"] is True
    assert Path(record["external_path"]).is_file()
    assert not list(output_root.rglob("*.wav"))
    assert (output_root / "reference_manifest.json").is_file()
    assert record["state_bindings"]["raw_trace_sha256"]

    state, state_meta = stage_r_execute._load_state_bundle(
        record,
        frame_count=4_800,
        sample_rate_hz=48_000,
        fallback_root=Path(record["external_path"]).parent,
    )
    assert state["rpm"].size == 4_800
    assert state["rpm"][0] == pytest.approx(1_000.0)
    assert state["rpm"][-1] == pytest.approx(3_000.0)
    assert state_meta["resampling"] == "timestamp_interpolation_to_audio_sample_grid"
