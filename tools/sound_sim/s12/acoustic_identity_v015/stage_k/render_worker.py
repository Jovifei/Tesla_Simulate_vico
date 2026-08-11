"""One-render process worker for the Stage-K named review builder.

The frozen PTR adapter and loudness analysis use native numerical routines. A
fresh short-lived process per render prevents allocator/native state from
accumulating while a 60-second package is assembled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from ..contracts import VehicleStateTrace
from ..loudness_manager import measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip
from ..stage_d.scenarios import build_stage_d_scenario_trace
from ..stage_k.candidate_profiles import load_stage_k_candidate
from ..stage_k.named_review import _build_operating_trace, _formal_audio
from ..stage_k.perceptual_metrics import compute_stage_k_perceptual_metrics
from ..stage_k.render_candidate import render_stage_k_candidate, render_stage_k_parent


SAMPLE_RATE_HZ = 48000


def _trace(vehicle_id: str, mode: str, duration_s: float) -> VehicleStateTrace:
    if mode == "cycle":
        return build_drive_cycle_trace(vehicle_id, duration_s)
    if mode in {"Low_Load_12s", "High_Load_12s"}:
        state = "low_load" if mode.startswith("Low") else "high_load"
        return _build_operating_trace(vehicle_id, state, duration_s)
    if mode == "Shift_12s":
        return build_stage_d_scenario_trace(vehicle_id, "shift", duration_s)
    if mode == "Lift_Deceleration_12s":
        return build_stage_d_scenario_trace(vehicle_id, "lift", duration_s)
    raise ValueError(f"unknown Stage-K worker mode: {mode}")


def _diagnostic_stem(render: object, stem_name: str) -> np.ndarray:
    pressure = np.asarray(render.pressure, dtype=np.float64)
    if stem_name == "turbo":
        stem = sum(
            (
                np.asarray(render.stems.get(name, np.zeros_like(pressure)), dtype=np.float64)
                for name in ("turbo_primary", "turbo_secondary", "turbo_sidebands", "intake_duct")
            ),
            np.zeros_like(pressure),
        )
    elif stem_name == "bov":
        stem = np.asarray(render.stems.get("wastegate", np.zeros_like(pressure)), dtype=np.float64)
    else:
        stem = np.asarray(render.stems.get(stem_name, np.zeros_like(pressure)), dtype=np.float64)
    return _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(stem)))


def render_one(
    *,
    vehicle_id: str,
    candidate_path: str | None,
    mode: str,
    stem_name: str | None,
    duration_s: float,
    output_path: Path,
    metadata_path: Path,
) -> dict[str, object]:
    trace = _trace(vehicle_id, mode, duration_s)
    candidate = load_stage_k_candidate(candidate_path) if candidate_path else None
    render = render_stage_k_parent(vehicle_id, trace) if candidate is None else render_stage_k_candidate(vehicle_id, trace, candidate)
    metadata: dict[str, object] = {}
    if candidate is not None:
        if duration_s <= 8.0:
            source_metrics = compute_stage_k_perceptual_metrics(render, trace, SAMPLE_RATE_HZ, vehicle_id=vehicle_id)
            metadata["source_metrics"] = source_metrics
        else:
            metadata["source_metrics"] = {
                "status": "NOT_COMPUTED_ON_FULL_CYCLE",
                "reason": "Stage-K perceptual metrics are measured on bounded probe windows to avoid retaining a 60-second source-domain FFT",
            }
        metadata["candidate_parameter_usage"] = render.diagnostics.get("candidate_parameter_usage", {})
        metadata["pipeline_order"] = list(render.diagnostics.get("pipeline_order", ()))
    if stem_name is None:
        # PTR and loudness only consume pressure.  Drop the many source/layer
        # stems before those transforms allocate their working buffers; this
        # keeps a 60-second worker below the native allocator's peak.
        pressure = np.asarray(render.pressure, dtype=np.float64).copy()
        del render
        audio = _formal_audio(SimpleNamespace(pressure=pressure))
        del pressure
    else:
        audio = _diagnostic_stem(render, stem_name)
    metrics = measure_loudness(audio, SAMPLE_RATE_HZ)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, np.asarray(audio, dtype=np.float64), allow_pickle=False)
    metadata.update(
        {
            "loudness": {
                "integrated_lufs": float(metrics.integrated_lufs),
                "rms_dbfs": float(metrics.rms_dbfs),
                "peak_dbfs": float(metrics.peak_dbfs),
                "crest_factor_db": float(metrics.crest_factor_db),
                "clipping_count": int(metrics.clipping_count),
            },
            "peak_linear": float(np.max(np.abs(audio))) if audio.size else 0.0,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "finite": bool(np.all(np.isfinite(audio))),
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vehicle-id", required=True)
    parser.add_argument("--candidate-path", type=Path)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--stem-name")
    parser.add_argument("--duration-s", type=float, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--metadata-path", type=Path, required=True)
    args = parser.parse_args()
    render_one(
        vehicle_id=args.vehicle_id,
        candidate_path=str(args.candidate_path.resolve()) if args.candidate_path else None,
        mode=args.mode,
        stem_name=args.stem_name,
        duration_s=args.duration_s,
        output_path=args.output_path.resolve(),
        metadata_path=args.metadata_path.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
