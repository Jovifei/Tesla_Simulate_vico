"""Local authorized calibration-bundle intake and derived feature pipeline.

Expected bundle layout::

    bundle/
      audio.wav
      state.csv                 # time_s,rpm,load,boost,state
      rights.json               # rights_status, source_sha256, provider
      recording.json            # vehicle/trim/microphone/AGC metadata

The pipeline emits only local derived files.  It never uploads or commits the
source audio and fails closed when rights or SHA bindings are incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..stage_v.io import sha256_file, write_json
from ..stage_x.reference_caseset import read_wav_mono
from .cycle_residual_bank import CLEARED_RIGHTS, build_cycle_residual_bank
from .harmonic_timbre_extractor import extract_harmonic_timbre_map

BUNDLE_SCHEMA = "s12.stage_y.calibration_bundle.v1"
RECEIPT_SCHEMA = "s12.stage_y.calibration_bundle_receipt.v1"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _read_state_csv(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"time_s", "rpm", "load"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("state.csv must contain time_s,rpm,load")
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError("state.csv requires at least two rows")
    result: dict[str, np.ndarray] = {}
    for name in ("time_s", "rpm", "load", "boost", "phase_rad"):
        if name in rows[0] and all(row.get(name, "") not in {None, ""} for row in rows):
            try:
                result[name] = np.asarray([float(row[name]) for row in rows], dtype=np.float64)
            except (TypeError, ValueError):
                raise ValueError(f"state.csv column {name} must be numeric") from None
    result["state"] = np.asarray([str(row.get("state") or "unspecified") for row in rows], dtype=object)
    times = result["time_s"]
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0.0):
        raise ValueError("state time_s must be finite and strictly increasing")
    for name in ("rpm", "load"):
        if name not in result or not np.all(np.isfinite(result[name])):
            raise ValueError(f"state {name} must be finite")
    if np.any(result["rpm"] <= 0.0):
        raise ValueError("state RPM must be positive")
    return result


def _sample_aligned_state(state: dict[str, np.ndarray], sample_count: int, sample_rate_hz: int) -> dict[str, np.ndarray]:
    time = np.arange(sample_count, dtype=np.float64) / sample_rate_hz
    source_time = state["time_s"]
    if source_time[0] > 0.0 or source_time[-1] < time[-1]:
        raise ValueError("state.csv does not cover the complete audio duration")
    rpm = np.interp(time, source_time, state["rpm"])
    load = np.clip(np.interp(time, source_time, state["load"]), 0.0, 1.0)
    boost_source = state.get("boost", np.zeros_like(source_time))
    boost = np.clip(np.interp(time, source_time, boost_source), 0.0, 1.0)
    if "phase_rad" in state:
        phase = np.interp(time, source_time, state["phase_rad"])
        phase = np.unwrap(phase)
    else:
        angular_speed = 2.0 * np.pi * rpm / 60.0
        phase = np.zeros_like(time)
        if time.size > 1:
            phase[1:] = np.cumsum(0.5 * (angular_speed[1:] + angular_speed[:-1]) / sample_rate_hz)
    indices = np.clip(np.searchsorted(source_time, time, side="right") - 1, 0, source_time.size - 1)
    labels = state["state"][indices]
    return {"time_s": time, "rpm": rpm, "load": load, "boost": boost, "phase_rad": phase, "state": labels}


@dataclass(frozen=True)
class CalibrationBundle:
    root: Path
    audio: np.ndarray
    sample_rate_hz: int
    state: dict[str, np.ndarray]
    rights: dict[str, Any]
    recording: dict[str, Any]
    audio_sha256: str


def load_calibration_bundle(root: str | Path) -> CalibrationBundle:
    root = Path(root)
    audio_path = root / "audio.wav"
    rights = _read_json(root / "rights.json")
    recording = _read_json(root / "recording.json")
    state = _read_state_csv(root / "state.csv")
    if rights.get("rights_status") not in CLEARED_RIGHTS:
        raise PermissionError("rights.json does not grant a supported calibration right")
    actual_sha = sha256_file(audio_path)
    if rights.get("source_sha256") != actual_sha:
        raise ValueError("rights.json source_sha256 does not match audio.wav")
    for field in ("vehicle_id", "trim_or_engine", "microphone_position", "agc_post_processing"):
        if recording.get(field) in {None, "", "UNVERIFIED", "UNKNOWN"}:
            raise ValueError(f"recording.json field is required: {field}")
    audio, sample_rate = read_wav_mono(audio_path)
    aligned = _sample_aligned_state(state, audio.size, sample_rate)
    return CalibrationBundle(root, audio, sample_rate, aligned, rights, recording, actual_sha)


def run_calibration_bundle(
    root: str | Path,
    output_root: str | Path,
    *,
    order_axis: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 12.0, 16.0),
    phase_samples: int = 512,
) -> dict[str, Any]:
    """Extract a harmonic map and cycle-residual bank into a local output dir."""
    bundle = load_calibration_bundle(root)
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    duration_s = bundle.audio.size / bundle.sample_rate_hz
    state_times = bundle.state["time_s"]
    rpm_min, rpm_max = float(np.min(bundle.state["rpm"])), float(np.max(bundle.state["rpm"]))
    load_min, load_max = float(np.min(bundle.state["load"])), float(np.max(bundle.state["load"]))
    boost_min, boost_max = float(np.min(bundle.state["boost"])), float(np.max(bundle.state["boost"]))

    def axis(lo: float, hi: float, count: int) -> tuple[float, ...]:
        if abs(hi - lo) <= 1e-9:
            return (lo,)
        return tuple(float(value) for value in np.linspace(lo, hi, count))

    timbre = extract_harmonic_timbre_map(
        bundle.audio,
        bundle.sample_rate_hz,
        state_times_s=state_times,
        rpm_trace=bundle.state["rpm"],
        load_trace=bundle.state["load"],
        boost_trace=bundle.state["boost"],
        rpm_axis=axis(rpm_min, rpm_max, 6),
        load_axis=axis(load_min, load_max, 4),
        boost_axis=axis(boost_min, boost_max, 3),
        order_axis=order_axis,
        provenance={
            "audio_sha256": bundle.audio_sha256,
            "rights_status": bundle.rights["rights_status"],
            "vehicle_id": bundle.recording["vehicle_id"],
        },
    )
    timbre_path = write_json(output / "harmonic_timbre_map.json", timbre.to_dict())

    bank = build_cycle_residual_bank(
        bundle.audio,
        phase_rad=bundle.state["phase_rad"],
        rpm=bundle.state["rpm"],
        load=bundle.state["load"],
        state_labels=bundle.state["state"],
        source_sha256=bundle.audio_sha256,
        rights_status=str(bundle.rights["rights_status"]),
        phase_samples=phase_samples,
    )
    waveforms = np.stack([record.waveform for record in bank.records])
    npz_path = output / "cycle_residual_bank.npz"
    np.savez_compressed(
        npz_path,
        waveforms=waveforms,
        rpm=np.asarray([record.rpm for record in bank.records]),
        load=np.asarray([record.load for record in bank.records]),
        state=np.asarray([record.state for record in bank.records]),
    )
    bank_manifest = bank.to_manifest()
    bank_manifest["derived_npz"] = {"path": npz_path.name, "sha256": sha256_file(npz_path)}
    bank_path = write_json(output / "cycle_residual_manifest.json", bank_manifest)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "DERIVED_CALIBRATION_ASSETS_READY",
        "vehicle_id": bundle.recording["vehicle_id"],
        "source_audio_sha256": bundle.audio_sha256,
        "rights_status": bundle.rights["rights_status"],
        "sample_rate_hz": bundle.sample_rate_hz,
        "duration_s": duration_s,
        "state_coverage_s": [float(state_times[0]), float(state_times[-1])],
        "recording": bundle.recording,
        "outputs": {
            timbre_path.name: sha256_file(timbre_path),
            bank_path.name: sha256_file(bank_path),
            npz_path.name: sha256_file(npz_path),
        },
        "raw_audio_copied": False,
        "runtime_default_enabled": False,
        "formal_status": "REQUIRES_MATLAB_MOSQITO_AND_HUMAN_VALIDATION",
        "scope": "local authorized feature derivation; not an OEM reproduction claim",
    }
    write_json(output / "calibration_bundle_receipt.json", receipt)
    return receipt


__all__ = [
    "BUNDLE_SCHEMA",
    "CalibrationBundle",
    "load_calibration_bundle",
    "run_calibration_bundle",
]
