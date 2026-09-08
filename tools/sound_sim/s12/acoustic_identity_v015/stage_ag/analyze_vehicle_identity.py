"""Stage AG vehicle-identity diagnostics.

This module measures two separate questions without confusing them:

1. identity separation: do different vehicle candidates become more distinguishable?
2. reference direction: where governed local references exist, does identity_v1 move
   toward or away from those references?

Neither score is a Human realism certificate.  The module never downloads audio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from ..stage_af.physical_closed_loop import (
    REFERENCE_FILENAMES,
    VEHICLE_SPECS,
    fixed_reference_distance,
)
from ..stage_af.spectral_guard import multires_spectral_distance
from .render_identity_probe import DEFAULT_SCENES, VEHICLES
from .vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1,
    VEHICLE_IDENTITY_PROFILES,
    VehicleIdentityEngine,
)

MATCHED_STATES = (
    ("quarter_redline", 0.25, 0.25),
    ("mid_redline", 0.50, 0.45),
    ("high_redline", 0.75, 0.80),
)
PAIRWISE_VEHICLES = tuple(
    (a, b)
    for index, a in enumerate(VEHICLES)
    for b in VEHICLES[index + 1 :]
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mono_float(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio)
    if values.dtype == np.uint8:
        values = (values.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(values.dtype, np.integer):
        info = np.iinfo(values.dtype)
        values = values.astype(np.float64) / float(max(abs(info.min), info.max))
    else:
        values = values.astype(np.float64)
    if values.ndim == 2:
        values = values.mean(axis=1)
    if values.ndim != 1 or values.size < 32 or not np.all(np.isfinite(values)):
        raise ValueError("audio must be finite mono/stereo PCM")
    return values


def _read_audio(path: Path, target_sr: int = 48_000) -> np.ndarray:
    sr, audio = wavfile.read(path)
    values = np.asarray(audio)
    if int(sr) == target_sr:
        return values
    mono = _mono_float(values)
    divisor = math.gcd(int(sr), int(target_sr))
    return resample_poly(mono, target_sr // divisor, int(sr) // divisor)


def _spectral_summary(audio: np.ndarray, sr: int = 48_000) -> dict[str, float]:
    x = _mono_float(audio)
    x = x - np.mean(x)
    window = np.hanning(x.size)
    spectrum = np.fft.rfft(x * window)
    power = np.abs(spectrum) ** 2 + 1e-18
    frequencies = np.fft.rfftfreq(x.size, 1.0 / sr)
    total = float(np.sum(power)) + 1e-18
    centroid = float(np.sum(frequencies * power) / total)
    bands = {
        "low_20_250": (20.0, 250.0),
        "mid_250_2000": (250.0, 2000.0),
        "high_2000_10000": (2000.0, 10000.0),
    }
    result = {"spectral_centroid_hz": centroid}
    for name, (low, high) in bands.items():
        mask = (frequencies >= low) & (frequencies < high)
        result[f"{name}_ratio"] = (
            float(np.sum(power[mask]) / total) if np.any(mask) else 0.0
        )
    frame = min(2048, x.size)
    usable = x[: (x.size // frame) * frame]
    if usable.size:
        rms = np.sqrt(np.mean(usable.reshape(-1, frame) ** 2, axis=1) + 1e-18)
        mean = float(np.mean(rms)) + 1e-18
        result["envelope_cv"] = float(np.std(rms) / mean)
        result["envelope_peak_ratio"] = float(np.max(rms) / mean)
    else:
        result["envelope_cv"] = 0.0
        result["envelope_peak_ratio"] = 1.0
    return result


def engine_order_energy_ratios(
    audio: np.ndarray,
    rpm: float,
    vehicle: str,
    sr: int = 48_000,
) -> dict[str, float]:
    """Approximate steady-state energy around the configured engine orders."""
    x = _mono_float(audio)
    x = x - np.mean(x)
    spectrum = np.fft.rfft(x * np.hanning(x.size))
    power = np.abs(spectrum) ** 2 + 1e-18
    frequencies = np.fft.rfftfreq(x.size, 1.0 / sr)
    total = float(np.sum(power)) + 1e-18
    crank_hz = max(float(rpm), 0.0) / 60.0
    profile = VEHICLE_IDENTITY_PROFILES[vehicle]
    result: dict[str, float] = {}
    for order, _, _ in profile.orders:
        center = crank_hz * float(order)
        width = max(8.0, center * 0.02)
        mask = np.abs(frequencies - center) <= width
        key = f"E{order:g}"
        result[key] = float(np.sum(power[mask]) / total) if np.any(mask) else 0.0
    return result


def _probe_index(probe_root: Path) -> tuple[dict[str, Any], dict[tuple[str, str, str], Path]]:
    manifest_path = probe_root / "identity_probe_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "s12.stage_ag.vehicle_identity_probe.v1":
        raise ValueError("unsupported Stage AG probe manifest")
    index: dict[tuple[str, str, str], Path] = {}
    for row in payload.get("artifacts", []):
        key = (str(row["vehicle"]), str(row["scene"]), str(row["identity_mode"]))
        path = probe_root / str(row["path"])
        if _sha256(path) != str(row["sha256"]):
            raise ValueError(f"probe artifact SHA mismatch: {path}")
        index[key] = path
    return payload, index


def _reference_candidates(root: Path, vehicle: str, filename: str) -> tuple[Path, ...]:
    package_names = (
        vehicle,
        f"s12-stage-ad-{vehicle.replace('_', '-')}-closed-loop-v1",
    )
    candidates: list[Path] = []
    for package in package_names:
        candidates.extend(
            [
                root / package / filename,
                root / package / "web_audio" / filename,
            ]
        )
    candidates.extend([root / filename, root / "web_audio" / filename])
    return tuple(candidates)


def find_reference(root: Path, vehicle: str, filename: str) -> Path | None:
    return next((path for path in _reference_candidates(root, vehicle, filename) if path.is_file()), None)


def _matched_trace(vehicle: str, rpm_fraction: float, throttle_value: float, duration: float = 1.2):
    sr = 48_000
    n = int(sr * duration)
    rpm = np.full(
        n,
        max(VEHICLE_SPECS[vehicle].idle_rpm, VEHICLE_SPECS[vehicle].redline_rpm * rpm_fraction),
        dtype=np.float64,
    )
    throttle = np.full(n, throttle_value, dtype=np.float64)
    return rpm, throttle, duration


def _render_matched(
    vehicle: str,
    mode: str,
    *,
    seed: int,
    numerical_fixes: tuple[str, ...],
) -> dict[str, np.ndarray]:
    renderer = VehicleIdentityEngine(
        vehicle,
        identity_mode=mode,
        numerical_fixes=numerical_fixes,
        seed=seed,
    )
    result: dict[str, np.ndarray] = {}
    for state, rpm_fraction, throttle in MATCHED_STATES:
        rpm, thr, duration = _matched_trace(vehicle, rpm_fraction, throttle)
        result[state] = renderer.render_track(rpm, thr, duration)
    n = int(48_000 * 1.8)
    start = max(VEHICLE_SPECS[vehicle].idle_rpm * 1.5, VEHICLE_SPECS[vehicle].redline_rpm * 0.22)
    end = VEHICLE_SPECS[vehicle].redline_rpm * 0.88
    rpm = np.linspace(start, end, n, endpoint=False)
    throttle = np.ones(n, dtype=np.float64)
    result["normalized_full_pull"] = renderer.render_track(rpm, throttle, n / 48_000.0)
    return result


def analyze_identity(
    probe_root: Path,
    output_path: Path,
    *,
    reference_root: Path | None = None,
    seed: int = 20260908,
    numerical_fixes: tuple[str, ...] = (),
) -> Path:
    manifest, index = _probe_index(probe_root)
    own_changes: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []

    for vehicle in VEHICLES:
        for scene in DEFAULT_SCENES:
            legacy_path = index[(vehicle, scene, IDENTITY_MODE_LEGACY)]
            identity_path = index[(vehicle, scene, IDENTITY_MODE_V1)]
            legacy = _read_audio(legacy_path)
            identity = _read_audio(identity_path)
            legacy_summary = _spectral_summary(legacy)
            identity_summary = _spectral_summary(identity)
            row = {
                "vehicle": vehicle,
                "scene": scene,
                "legacy_sha256": _sha256(legacy_path),
                "identity_sha256": _sha256(identity_path),
                "pcm_changed": _sha256(legacy_path) != _sha256(identity_path),
                "legacy_to_identity_multires_distance": multires_spectral_distance(
                    legacy, identity
                ),
                "legacy_features": legacy_summary,
                "identity_features": identity_summary,
            }
            if scene in ("hot_idle", "steady_mid"):
                if scene == "hot_idle":
                    rpm_value = VEHICLE_SPECS[vehicle].idle_rpm
                else:
                    rpm_value = min(VEHICLE_SPECS[vehicle].redline_rpm * 0.48, 4200.0)
                row["order_energy_legacy"] = engine_order_energy_ratios(
                    legacy, rpm_value, vehicle
                )
                row["order_energy_identity"] = engine_order_energy_ratios(
                    identity, rpm_value, vehicle
                )
            own_changes.append(row)

            if reference_root is not None and scene in REFERENCE_FILENAMES:
                filename = REFERENCE_FILENAMES[scene]
                ref_path = find_reference(reference_root, vehicle, filename)
                if ref_path is not None:
                    reference = _read_audio(ref_path)
                    legacy_distance = fixed_reference_distance(legacy, reference)
                    identity_distance = fixed_reference_distance(identity, reference)
                    regression = (
                        (identity_distance - legacy_distance) / max(legacy_distance, 1e-12)
                    )
                    reference_rows.append(
                        {
                            "vehicle": vehicle,
                            "scene": scene,
                            "reference_file": filename,
                            "reference_path": str(ref_path.resolve()),
                            "reference_sha256": _sha256(ref_path),
                            "legacy_distance": legacy_distance,
                            "identity_distance": identity_distance,
                            "relative_change": regression,
                            "guard_3pct": (
                                "PASS"
                                if identity_distance <= legacy_distance * 1.03 + 1e-12
                                else "REGRESSION_GT_3PCT"
                            ),
                        }
                    )

    rendered: dict[str, dict[str, dict[str, np.ndarray]]] = {
        mode: {
            vehicle: _render_matched(
                vehicle,
                mode,
                seed=seed,
                numerical_fixes=numerical_fixes,
            )
            for vehicle in VEHICLES
        }
        for mode in (IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1)
    }
    pairwise: list[dict[str, Any]] = []
    states = [row[0] for row in MATCHED_STATES] + ["normalized_full_pull"]
    for vehicle_a, vehicle_b in PAIRWISE_VEHICLES:
        for state in states:
            legacy_distance = multires_spectral_distance(
                rendered[IDENTITY_MODE_LEGACY][vehicle_a][state],
                rendered[IDENTITY_MODE_LEGACY][vehicle_b][state],
            )
            identity_distance = multires_spectral_distance(
                rendered[IDENTITY_MODE_V1][vehicle_a][state],
                rendered[IDENTITY_MODE_V1][vehicle_b][state],
            )
            pairwise.append(
                {
                    "vehicle_a": vehicle_a,
                    "vehicle_b": vehicle_b,
                    "state": state,
                    "legacy_distance": legacy_distance,
                    "identity_distance": identity_distance,
                    "separation_delta": identity_distance - legacy_distance,
                }
            )

    mean_legacy = float(np.mean([row["legacy_distance"] for row in pairwise]))
    mean_identity = float(np.mean([row["identity_distance"] for row in pairwise]))
    regressions = [
        row for row in reference_rows if row["guard_3pct"] == "REGRESSION_GT_3PCT"
    ]
    output = {
        "schema": "s12.stage_ag.identity_separation_scorecard.v1",
        "status": "DIAGNOSTIC_ONLY_NOT_HUMAN_PASS",
        "probe_manifest_sha256": _sha256(probe_root / "identity_probe_manifest.json"),
        "seed": int(seed),
        "numerical_fixes": list(numerical_fixes),
        "legacy_to_identity": own_changes,
        "matched_state_pairwise": pairwise,
        "summary": {
            "mean_pairwise_legacy_distance": mean_legacy,
            "mean_pairwise_identity_distance": mean_identity,
            "mean_pairwise_separation_delta": mean_identity - mean_legacy,
            "reference_rows": len(reference_rows),
            "reference_regressions_gt_3pct": len(regressions),
            "interpretation": (
                "larger separation is diagnostic only; correctness requires governed "
                "Reference checks and Jovi blind listening"
            ),
        },
        "reference_diagnostics": reference_rows,
        "reference_policy": (
            "EXISTING_LOCAL_BYTES_ONLY_NO_NETWORK_DOWNLOAD"
            if reference_root is not None
            else "NOT_PROVIDED"
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Stage AG vehicle identity separation")
    parser.add_argument("--probe-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    args = parser.parse_args(argv)
    result = analyze_identity(
        args.probe_root,
        args.output,
        reference_root=args.reference_root,
        seed=args.seed,
        numerical_fixes=tuple(args.numerical_fixes),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
