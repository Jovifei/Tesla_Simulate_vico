"""Export the current S12 acoustic_identity_v015 renderers for Vico Android.

The source workspace is intentionally external: E:\\Tesla_speed remains the
algorithm authority, while this script writes only the Vico app bank assets.
The generated bank keeps one fixed gain per vehicle and never normalizes an
individual RPM/load loop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


APP_VEHICLES = {
    "hellcat_v6": "hellcat",
    "ferrari_458": "ferrari_458",
    "lfa": "lfa",
    "gtr_r35": "gtr_r35",
    "c63_w204_v6": "c63_w204",
    "supra_jza80": "supra_jza80",
}
RPM_LEVELS = {
    "hellcat_v6": (750, 1300, 2100, 3000, 3900, 4900, 5800, 6200),
    "ferrari_458": (1050, 1800, 3200, 4800, 6200, 7400, 8400, 9000),
    "lfa": (900, 1600, 3000, 4800, 6200, 7600, 8400, 9000),
    "gtr_r35": (1000, 1450, 2200, 3200, 4300, 5200, 6200, 7000),
    "c63_w204_v6": (700, 1400, 2200, 3200, 4300, 5500, 6800, 7200),
    "supra_jza80": (800, 1400, 2200, 3200, 4400, 5600, 6500, 7200),
}
LOAD_LEVELS = (0.32, 0.92)
POWERTRAIN = {
    "hellcat_v6": dict(idle=750, redline=6200, ratios=(4.714, 3.143, 2.106), final=2.62, wheel=0.347, launch=2100, shift=6100),
    "ferrari_458": dict(idle=1050, redline=9000, ratios=(3.29, 2.16, 1.61, 1.28), final=4.18, wheel=0.34, launch=3000, shift=8400),
    "lfa": dict(idle=900, redline=9000, ratios=(3.54, 2.06, 1.42, 1.03), final=3.27, wheel=0.33, launch=2800, shift=8500),
    "gtr_r35": dict(idle=1000, redline=7000, ratios=(3.827, 2.36, 1.685, 1.313), final=3.70, wheel=0.34, launch=2400, shift=6500),
    "c63_w204_v6": dict(idle=700, redline=7200, ratios=(4.38, 2.86, 1.92), final=2.85, wheel=0.335, launch=2300, shift=7000),
    "supra_jza80": dict(idle=800, redline=7200, ratios=(3.827, 2.36, 1.685, 1.312), final=3.266, wheel=0.34, launch=2300, shift=6500),
}
SRC_RATE = 48000
APP_RATE = 48000
APP_CHANNELS = 1
LOOP_SECONDS = 0.36
TARGET_LUFS = -16.0
PEAK_LIMIT_DBFS = -1.5


def _load_source_api(source_root: Path):
    sys.path.insert(0, str(source_root.resolve()))
    from sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
    from sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
    from sound_sim.s12.acoustic_identity_v015.acoustic_layers.shift_dynamics import detect_shift_events
    from sound_sim.s12.acoustic_identity_v015.render_realism_v10 import (
        _RENDERERS,
        _SAMPLE_RATE_HZ,
        _apply_frozen_ptr,
        _edge_fade,
        _render_stateful,
    )

    if _SAMPLE_RATE_HZ != SRC_RATE:
        raise RuntimeError(f"Unexpected S12 source rate: {_SAMPLE_RATE_HZ}")
    from sound_sim.s12.acoustic_identity_v015.loudness_manager import manage_bundle_loudness, measure_loudness

    return (
        VehicleStateTrace,
        build_drive_cycle_trace,
        detect_shift_events,
        manage_bundle_loudness,
        measure_loudness,
        _RENDERERS,
        _apply_frozen_ptr,
        _edge_fade,
        _render_stateful,
    )


def _constant_trace(vehicle_state_trace, rpm: float, load: float, seconds: float):
    count = int(round(seconds * SRC_RATE)) + 1
    time_s = np.linspace(0.0, seconds, count)
    return vehicle_state_trace(
        time_s=time_s,
        rpm=np.full(count, rpm, dtype=np.float64),
        load=np.full(count, load, dtype=np.float64),
        throttle=np.full(count, load, dtype=np.float64),
        acceleration_mps2=np.zeros(count, dtype=np.float64),
    ).validate()


def _mono_48k(stereo_48k: np.ndarray) -> np.ndarray:
    value = np.asarray(stereo_48k, dtype=np.float64)
    if value.ndim == 1:
        mono = value
    elif value.ndim == 2 and value.shape[1] == 2:
        mono = value.mean(axis=1)
    else:
        raise ValueError(f"expected mono or stereo source, got shape {value.shape}")
    return mono.astype(np.float32)


def _loop(signal: np.ndarray) -> np.ndarray:
    count = min(int(round(LOOP_SECONDS * APP_RATE)), signal.size)
    loop = signal[-count:].copy()
    crossfade = min(int(round(0.008 * APP_RATE)), loop.size // 8)
    blend = np.linspace(0.0, 1.0, crossfade, dtype=np.float32)
    loop[:crossfade] = (1.0 - blend) * loop[-crossfade:] + blend * loop[:crossfade]
    loop -= np.mean(loop, dtype=np.float32)
    return loop


def _source_commit(source_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _trace_payload(trace, step_s: float = 0.02) -> dict:
    times = np.arange(trace.time_s[0], trace.time_s[-1] + step_s * 0.5, step_s, dtype=np.float64)
    if times[-1] < trace.time_s[-1]:
        times = np.append(times, trace.time_s[-1])
    return {
        "schema": "vico.s12.common_input_trace.v1",
        "sample_period_s": step_s,
        "fields": ["time_s", "rpm", "load", "throttle", "acceleration_mps2"],
        "points": [
            {
                "time_s": round(float(time), 6),
                "rpm": round(float(np.interp(time, trace.time_s, trace.rpm)), 6),
                "load": round(float(np.interp(time, trace.time_s, trace.load)), 6),
                "throttle": round(float(np.interp(time, trace.time_s, trace.throttle)), 6),
                "acceleration_mps2": round(float(np.interp(time, trace.time_s, trace.acceleration_mps2)), 6),
            }
            for time in times
        ],
    }


def _fade_event(signal: np.ndarray, fade_samples: int = 240) -> np.ndarray:
    result = np.asarray(signal, dtype=np.float32).copy()
    fade = min(fade_samples, result.size // 2)
    if fade:
        result[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
        result[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return result


def _dbfs(value: float) -> float:
    return float(20.0 * np.log10(value)) if value > 0.0 else float("-inf")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _afterfire_source_frames(
    window_start_frame: int, active_first_frame: int, pre_roll_frames: int,
) -> tuple[int, int, int]:
    if window_start_frame < 0 or active_first_frame < 0 or pre_roll_frames < 0:
        raise ValueError("Afterfire source frames must be non-negative")
    source_frame = window_start_frame + active_first_frame
    crop_start_frame = window_start_frame + max(0, active_first_frame - pre_roll_frames)
    return source_frame, crop_start_frame, source_frame - crop_start_frame


def _s13_event_extraction_contract() -> dict:
    return {
        "shift": {
            "detector": "detect_shift_events",
            "pre_roll_frames": int(.040 * APP_RATE),
            "post_roll_frames": int(.220 * APP_RATE),
            "edge_fade_frames": 240,
        },
        "afterfire": {
            "source_stem": "post_ptr_afterfire",
            "window_start_frame": int(18.0 * SRC_RATE),
            "window_end_frame": int(23.0 * SRC_RATE),
            "threshold_relative_peak": 0.015,
            "threshold_absolute_floor": 1e-6,
            "pre_roll_frames": int(.025 * APP_RATE),
            "post_roll_frames": int(.30 * APP_RATE),
        },
    }


def _s13_event_binding(
    *,
    event_id: str,
    kind: str,
    asset_file: str,
    asset_sha256: str,
    trace_sha256: str,
    source_domain: str,
    source_time_s: float,
    source_frame: int,
    crop_start_frame: int,
    sample_count: int,
) -> dict:
    total_frames = int(30.0 * APP_RATE)
    hashes = (asset_sha256, trace_sha256)
    if not event_id or kind not in {"shift", "afterfire"}:
        raise ValueError("Invalid S13 event identity")
    if source_domain not in {"TRACE_EVENT", "POST_PTR_STEM_ONSET"}:
        raise ValueError("Invalid S13 event source domain")
    if not asset_file or asset_file.startswith("/") or "\\" in asset_file or ":" in asset_file:
        raise ValueError("Event asset path must be relative")
    if any(len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value) for value in hashes):
        raise ValueError("Event and trace SHA-256 values must be 64 hexadecimal characters")
    if sample_count <= 0 or not np.isfinite(source_time_s):
        raise ValueError("Invalid S13 event time or sample count")
    if not 0 <= source_frame < total_frames or not 0 <= crop_start_frame < total_frames:
        raise ValueError("Event frames are outside the 30-second trace")
    if source_time_s < 0.0 or source_time_s >= 30.0:
        raise ValueError("Event source time is outside the 30-second trace")
    if abs(source_time_s * APP_RATE - source_frame) > 0.500001:
        raise ValueError("Event time and source frame disagree")
    offset = source_frame - crop_start_frame
    if offset < 0 or offset >= sample_count:
        raise ValueError("Event source frame is outside the decoded clip")
    if crop_start_frame + sample_count > total_frames:
        raise ValueError("Event clip exceeds the 30-second trace")
    return {
        "id": event_id,
        "kind": kind,
        "file": asset_file,
        "asset_sha256": asset_sha256.lower(),
        "trace_sha256": trace_sha256.lower(),
        "source_domain": source_domain,
        "source_time_s": float(source_time_s),
        "source_frame": int(source_frame),
        "crop_start_frame": int(crop_start_frame),
        "trigger_offset_frames": int(offset),
        "samples": int(sample_count),
    }


def _manifest(
    app_key: str,
    source_key: str,
    fixed_gain: float,
    loops: list[dict],
    afterfire: dict,
    shift_events: list[dict],
    source_commit: str,
    trace: dict,
    trace_sha256: str,
    drive_loudness: dict,
) -> dict:
    p = POWERTRAIN[app_key]
    shift_speed = [
        p["shift"] / 60.0 / (ratio * p["final"]) * (2.0 * np.pi * p["wheel"]) * 3.6
        for ratio in p["ratios"][:-1]
    ]
    return {
        "schema": "vico.s12.soundbank.v1",
        "source": "E:/Tesla_speed/prj/tools/sound_sim/s12/acoustic_identity_v015",
        "source_commit": source_commit,
        "source_scope": "synthetic; uncalibrated; not OEM reproduction",
        "algorithm": "render_realism_v10: independent_source -> realism_layers -> frozen_ptr",
        "vehicle_key": app_key,
        "source_vehicle_id": source_key,
        "sample_rate_hz": APP_RATE,
        "audio_contract": {
            "sample_rate_hz": APP_RATE,
            "channels": APP_CHANNELS,
            "channel_layout": "mono",
            "target_integrated_lufs": TARGET_LUFS,
            "peak_limit_dbfs": PEAK_LIMIT_DBFS,
            "downmix": "arithmetic_mean_left_right",
            "gain_policy": "one_fixed_vehicle_gain_from_common_drive_cycle",
        },
        "fixed_vehicle_gain": fixed_gain,
        "reference_loudness": drive_loudness,
        "common_input_trace": {
            "schema": trace["schema"],
            "file": "common_input_trace.json",
            "duration_s": trace["points"][-1]["time_s"],
            "sample_period_s": trace["sample_period_s"],
            "fields": trace["fields"],
            "sha256": trace_sha256,
        },
        "layer_contract": {
            "continuous": "final_s12_pressure_including_low_frequency_body_and_exhaust_rumble",
            "low_frequency": ["low_frequency_body", "exhaust_rumble"],
            "shift": ["shift_impact", "shift_recovery_boom"],
            "afterfire": "afterfire",
        },
        "idle_rpm": p["idle"],
        "redline_rpm": p["redline"],
        "peak_limit_dbfs": PEAK_LIMIT_DBFS,
        "gear_ratios": list(p["ratios"]),
        "final_drive": p["final"],
        "wheel_radius_m": p["wheel"],
        "launch_rpm": p["launch"],
        "shift_rpm": p["shift"],
        "shift_speed_kmh": shift_speed,
        "shift_attack_s": 0.018,
        "shift_hold_s": 0.032,
        "shift_recovery_s": 0.075,
        "shift_settle_s": 0.055,
        "shift_min_torque": 0.22,
        "shift_reengage_gain": 1.08,
        "minimum_shift_interval_s": 0.35,
        "downshift_ratio": 0.68,
        "speed_ceiling_kmh": 144.0,
        "afterfire_minimum_rpm": 2600.0,
        "loops": loops,
        "afterfire": afterfire,
        "shift_events": shift_events,
    }


def _require_same_pcm(generated_path: Path, reference_path: Path) -> None:
    if not reference_path.is_file():
        raise ValueError(f"Missing reference asset: {reference_path.name}")
    generated, generated_rate = sf.read(generated_path, dtype="float32", always_2d=True)
    reference, reference_rate = sf.read(reference_path, dtype="float32", always_2d=True)
    if generated_rate != reference_rate or generated.shape != reference.shape:
        raise ValueError(f"Reference PCM shape/rate mismatch: {reference_path.name}")
    if not np.array_equal(generated, reference):
        difference = float(np.max(np.abs(generated - reference)))
        raise ValueError(
            f"Reference PCM differs for {reference_path.name}: max_abs={difference}"
        )


def _write_s13_review_sidecar(
    sidecar_root: Path,
    app_key: str,
    manifest: dict,
    vehicle_root: Path,
    trace_path: Path,
    reference_bank_root: Path | None,
) -> Path:
    reference_vehicle = reference_bank_root / app_key if reference_bank_root else None
    reference_trace = reference_vehicle / "common_input_trace.json" if reference_vehicle else None
    if reference_trace:
        if not reference_trace.is_file() or reference_trace.read_bytes() != trace_path.read_bytes():
            raise ValueError(f"Reference trace differs for {app_key}")
        reference_manifest_path = reference_vehicle / "manifest.json"
        reference_manifest = json.loads(reference_manifest_path.read_text(encoding="utf-8"))
        if reference_manifest.get("source_commit") != manifest["source_commit"]:
            raise ValueError(f"Reference source commit differs for {app_key}")
        manifest_path = reference_manifest_path
    else:
        manifest_path = vehicle_root / "manifest.json"

    entries = [*manifest["loops"], manifest["afterfire"], *manifest["shift_events"]]
    bank_assets = {}
    for entry in entries:
        generated_path = vehicle_root / entry["file"]
        reference_path = reference_vehicle / entry["file"] if reference_vehicle else None
        if reference_path:
            _require_same_pcm(generated_path, reference_path)
            asset_sha256 = _sha256_file(reference_path)
        else:
            asset_sha256 = _sha256_file(generated_path)
        bank_assets[entry["file"]] = asset_sha256

    events = []
    for event in [manifest["afterfire"], *manifest["shift_events"]]:
        required = (
            "id", "kind", "source_domain", "source_time_s", "source_frame",
            "crop_start_frame", "trigger_offset_frames", "samples",
        )
        if any(field not in event for field in required):
            raise ValueError(f"BLOCKED_MISSING_EVENT_PROVENANCE:{app_key}:{event['file']}")
        events.append({
            **{field: event[field] for field in required},
            "asset_path": f"s12_v10/{app_key}/{event['file']}",
            "asset_sha256": bank_assets[event["file"]],
        })

    trace = manifest["common_input_trace"]
    sidecar = {
        "schema": "vico.s13.review_sidecar.v1",
        "vehicle_key": app_key,
        "source_vehicle_id": manifest["source_vehicle_id"],
        "source_commit": manifest["source_commit"],
        "exporter_sha256": _sha256_file(Path(__file__).resolve()),
        "source_scope": manifest["source_scope"],
        "sample_rate_hz": APP_RATE,
        "channels": APP_CHANNELS,
        "duration_s": 30.0,
        "total_frames": int(30.0 * APP_RATE),
        "control_interpolation": "linear_per_audio_frame",
        "event_extraction": _s13_event_extraction_contract(),
        "gain_is_embedded_in_assets": True,
        "fixed_vehicle_gain": manifest["fixed_vehicle_gain"],
        "trace": {
            "asset_path": f"s12_v10/{app_key}/{trace['file']}",
            "sha256": _sha256_file(reference_trace or trace_path),
            "point_count": len(json.loads(trace_path.read_text(encoding="utf-8"))["points"]),
            "sample_period_s": trace["sample_period_s"],
            "fields": trace["fields"],
        },
        "bank_manifest": {
            "asset_path": f"s12_v10/{app_key}/manifest.json",
            "sha256": _sha256_file(manifest_path),
        },
        "bank_assets_sha256": bank_assets,
        "audio_pcm_verification": (
            "EXACT_FLOAT32_MATCH" if reference_vehicle else "GENERATED_ONLY_NOT_COMPARED"
        ),
        "events": events,
    }
    sidecar_root.mkdir(parents=True, exist_ok=True)
    sidecar_path = sidecar_root / f"{app_key}.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return sidecar_path


def export(
    app_root: Path,
    source_root: Path,
    reference_bank_root: Path | None = None,
    review_sidecar_root: Path | None = None,
) -> dict:
    (
        VehicleStateTrace,
        build_drive_cycle_trace,
        detect_shift_events,
        manage_bundle_loudness,
        measure_loudness,
        renderers,
        apply_ptr,
        edge_fade,
        render_stateful,
    ) = _load_source_api(source_root)
    output_root = app_root / "Project" / "android" / "app" / "src" / "main" / "assets" / "s12_v10"
    if review_sidecar_root is None:
        review_sidecar_root = output_root.parent / "s13_review_v1"
    output_root.mkdir(parents=True, exist_ok=True)
    commit = _source_commit(source_root)
    report = {"schema": "vico.s12.android.bank_export.v1", "source_commit": commit, "vehicles": {}}
    for app_key, source_key in APP_VEHICLES.items():
        vehicle_root = output_root / app_key
        vehicle_root.mkdir(parents=True, exist_ok=True)
        raw_loops: list[tuple[int, float, np.ndarray]] = []
        renderer = renderers[source_key]
        for rpm in RPM_LEVELS[app_key]:
            for load in LOAD_LEVELS:
                trace = _constant_trace(VehicleStateTrace, rpm, load, 0.52)
                rendered = render_stateful(renderer, source_key, trace)
                signal = _loop(_mono_48k(apply_ptr(rendered.pressure)))
                raw_loops.append((rpm, load, signal))

        drive_trace = build_drive_cycle_trace(source_key, 30.0)
        drive = render_stateful(renderer, source_key, drive_trace)
        drive_reference = _mono_48k(edge_fade(apply_ptr(drive.pressure)))
        managed = manage_bundle_loudness(
            {"drive_cycle": drive_reference},
            APP_RATE,
            target_lufs=TARGET_LUFS,
            peak_limit_dbfs=PEAK_LIMIT_DBFS,
        )
        afterfire = _mono_48k(apply_ptr(drive.stems["afterfire"]))
        lift_start = int(18.0 * SRC_RATE)
        lift_finish = int(23.0 * SRC_RATE)
        afterfire_signal = _mono_48k(afterfire[lift_start:lift_finish])
        active = np.flatnonzero(np.abs(afterfire_signal) >= max(np.max(np.abs(afterfire_signal)) * 0.015, 1e-6))
        afterfire_source_frame = None
        afterfire_crop_start_frame = None
        afterfire_trigger_offset_frames = None
        if active.size:
            afterfire_source_frame, afterfire_crop_start_frame, afterfire_trigger_offset_frames = (
                _afterfire_source_frames(lift_start, int(active[0]), int(.025 * APP_RATE))
            )
            crop_start = afterfire_crop_start_frame - lift_start
            crop_end = min(afterfire_signal.size, int(active[-1]) + int(.30 * APP_RATE))
            afterfire_signal = afterfire_signal[crop_start:crop_end]
        afterfire_signal -= np.mean(afterfire_signal, dtype=np.float32)
        common_trace = _trace_payload(drive_trace)
        trace_path = vehicle_root / "common_input_trace.json"
        trace_path.write_text(json.dumps(common_trace, indent=2), encoding="utf-8")
        trace_sha256 = _sha256_file(trace_path)
        shift_source = _mono_48k(
            apply_ptr(drive.stems["shift_impact"] + drive.stems["shift_recovery_boom"])
        )
        events = []
        shift_clips = []
        for event in detect_shift_events(drive_trace, SRC_RATE):
            start = max(0, event.sample_index - int(0.040 * SRC_RATE))
            finish = min(shift_source.size, event.sample_index + int(0.220 * SRC_RATE))
            shift_clips.append(_fade_event(shift_source[start:finish]))
            events.append(event)
        raw_peak = max(
            [float(np.max(np.abs(drive_reference))), *[float(np.max(np.abs(signal))) for _, _, signal in raw_loops], float(np.max(np.abs(afterfire_signal))), *[float(np.max(np.abs(signal))) for signal in shift_clips]]
        )
        target_gain_db = TARGET_LUFS - managed.input_bundle_metrics.integrated_lufs
        peak_gain_db = PEAK_LIMIT_DBFS - _dbfs(raw_peak)
        fixed_gain_db = min(target_gain_db, peak_gain_db)
        fixed_gain = float(10.0 ** (fixed_gain_db / 20.0))
        drive_metrics = measure_loudness(drive_reference * fixed_gain, APP_RATE)
        drive_loudness = {
            "target_integrated_lufs": TARGET_LUFS,
            "peak_limit_dbfs": PEAK_LIMIT_DBFS,
            "integrated_lufs": float(drive_metrics.integrated_lufs),
            "rms_dbfs": float(drive_metrics.rms_dbfs),
            "peak_dbfs": float(drive_metrics.peak_dbfs),
            "fixed_gain_db": fixed_gain_db,
            "headroom_limited": bool(target_gain_db > peak_gain_db),
            "all_bank_peak_dbfs": _dbfs(raw_peak * fixed_gain),
        }
        shift_entries = []
        for event_index, (event, signal) in enumerate(zip(events, shift_clips), start=1):
            filename = f"shift_event_{event_index:02d}_s12.wav"
            asset_path = vehicle_root / filename
            sf.write(asset_path, signal * fixed_gain, APP_RATE, subtype="FLOAT", format="WAV")
            event_source_frame = int(event.sample_index)
            event_entry = _s13_event_binding(
                event_id=f"shift_event_{event_index:02d}",
                kind="shift",
                asset_file=filename,
                asset_sha256=_sha256_file(asset_path),
                trace_sha256=trace_sha256,
                source_domain="TRACE_EVENT",
                source_time_s=float(event.time_s),
                source_frame=event_source_frame,
                crop_start_frame=max(0, event_source_frame - int(.040 * APP_RATE)),
                sample_count=int(signal.size),
            )
            shift_entries.append(
                {
                    "file": filename,
                    "samples": int(signal.size),
                    "time_s": float(event.time_s),
                    "rpm_before": float(event.rpm_before),
                    "rpm_after": float(event.rpm_after),
                    "rms": float(np.sqrt(np.mean(np.square(signal * fixed_gain)))),
                    **event_entry,
                }
            )
        loop_entries = []
        for rpm, load, signal in raw_loops:
            signal = (signal * fixed_gain).astype(np.float32)
            filename = f"rpm_{rpm:04d}_load_{round(load * 100):02d}.wav"
            asset_path = vehicle_root / filename
            sf.write(asset_path, signal, APP_RATE, subtype="FLOAT", format="WAV")
            loop_entries.append({
                "rpm": rpm,
                "load": load,
                "file": filename,
                "samples": int(signal.size),
                "rms": float(np.sqrt(np.mean(signal * signal))),
                "asset_sha256": _sha256_file(asset_path),
            })
        afterfire_signal = (afterfire_signal * fixed_gain).astype(np.float32)
        afterfire_file = "afterfire_tipout_s12.wav"
        afterfire_path = vehicle_root / afterfire_file
        sf.write(afterfire_path, afterfire_signal, APP_RATE, subtype="FLOAT", format="WAV")
        afterfire_entry = {
            "file": afterfire_file,
            "samples": int(afterfire_signal.size),
            "rms": float(np.sqrt(np.mean(afterfire_signal * afterfire_signal))),
            "asset_sha256": _sha256_file(afterfire_path),
        }
        if afterfire_source_frame is not None:
            afterfire_entry.update(_s13_event_binding(
                event_id="afterfire_tipout",
                kind="afterfire",
                asset_file=afterfire_file,
                asset_sha256=afterfire_entry["asset_sha256"],
                trace_sha256=trace_sha256,
                source_domain="POST_PTR_STEM_ONSET",
                source_time_s=afterfire_source_frame / APP_RATE,
                source_frame=afterfire_source_frame,
                crop_start_frame=afterfire_crop_start_frame,
                sample_count=int(afterfire_signal.size),
            ))
        manifest = _manifest(
            app_key,
            source_key,
            fixed_gain,
            loop_entries,
            afterfire_entry,
            shift_entries,
            commit,
            common_trace,
            trace_sha256,
            drive_loudness,
        )
        manifest_path = vehicle_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        _write_s13_review_sidecar(
            review_sidecar_root,
            app_key,
            manifest,
            vehicle_root,
            trace_path,
            reference_bank_root,
        )
        report["vehicles"][app_key] = {
            "source_vehicle_id": source_key,
            "loop_count": len(loop_entries),
            "fixed_gain": fixed_gain,
            "afterfire_samples": afterfire_entry["samples"],
            "shift_event_count": len(shift_entries),
            "audio_contract": manifest["audio_contract"],
            "reference_loudness": drive_loudness,
        }
    (output_root / "export_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-root", type=Path, default=Path(r"E:\Tesla_speed\prj\tools"))
    parser.add_argument("--reference-bank-root", type=Path)
    parser.add_argument("--review-sidecar-root", type=Path)
    args = parser.parse_args()
    report = export(
        args.app_root,
        args.source_root,
        args.reference_bank_root,
        args.review_sidecar_root,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
