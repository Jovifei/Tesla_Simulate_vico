"""Fail-closed Stage-V candidate grid: render, reopen, compare, rank or reject."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ...acoustic_comparator.core import ComparisonCase
from ..event_domain.diagnostics import measure_audio
from .comparator import compare_three_way
from .io import sha256_file, write_json, write_pcm24_wav
from .pipeline import SAMPLE_RATE_HZ, render_stage_v_case

_GRID: tuple[dict[str, Any], ...] = (
    {"candidate_id": "hellcat_event_nominal", "overrides": {}},
    {"candidate_id": "hellcat_event_attack", "overrides": {"combustion_event.rise_time_s": 0.0028, "combustion_event.decay_time_s": 0.026}},
    {"candidate_id": "hellcat_event_path_spread", "overrides": {"per_path_primary_length_m": [0.90, 1.00, 1.04, 1.10, 0.92, 1.02, 1.06, 1.13]}},
)


def _jsonable(value: object) -> object:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _distance(pair: dict[str, Any]) -> float | None:
    value = pair.get("spectral", {}).get("log_distance")
    return float(value) if isinstance(value, (float, int)) else None


def run_hellcat_candidate_grid(output_root: str | Path, duration_s: float = 8.0, reference: np.ndarray | None = None) -> dict[str, object]:
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty candidate grid: {root}")
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    parent_sha: str | None = None
    parent_audio: np.ndarray | None = None
    case: ComparisonCase | None = None
    for spec in _GRID:
        result = render_stage_v_case("hellcat_v1", "full_load_acceleration", duration_s, candidate_overrides=spec["overrides"])
        candidate_dir = root / "candidates" / str(spec["candidate_id"])
        parent_receipt = write_pcm24_wav(candidate_dir / "legacy_parent_raw.wav", result.parent.pressure, SAMPLE_RATE_HZ)
        candidate_receipt = write_pcm24_wav(candidate_dir / "event_candidate_raw.wav", result.candidate.pressure, SAMPLE_RATE_HZ)
        monitor_receipt = write_pcm24_wav(candidate_dir / "event_candidate_monitor.wav", result.monitor_audio, SAMPLE_RATE_HZ)
        if parent_sha is None:
            parent_sha = parent_receipt.sha256
            parent_audio = result.parent.pressure
            case = ComparisonCase(
                "hellcat_v1",
                "full_load_acceleration",
                "grid-reference" if reference is not None else None,
                str(spec["candidate_id"]),
                SAMPLE_RATE_HZ,
                (float(result.trace.rpm[0]), float(result.trace.rpm[-1])),
                (float(result.trace.rpm[0]), float(result.trace.rpm[-1])),
                (float(result.trace.load[0]), float(result.trace.load[-1])),
                (float(result.trace.load[0]), float(result.trace.load[-1])),
                "unaltered_analysis_signal",
                reference_provenance="R2/external pointer" if reference is not None else "not bound",
                candidate_source_commit="working-tree",
            )
        assert case is not None and parent_audio is not None and parent_sha is not None
        comparison = compare_three_way(reference, parent_audio, result.candidate.pressure, case)
        rows.append(
            {
                "candidate_id": spec["candidate_id"],
                "overrides": spec["overrides"],
                "rendered": True,
                "reopened": True,
                "raw_sha256": candidate_receipt.sha256,
                "parent_sha256": parent_sha,
                "monitor_sha256": monitor_receipt.sha256,
                "parent_candidate_difference_rms": comparison["parent_candidate_difference_rms"],
                "candidate_metrics": measure_audio(result.candidate.pressure, SAMPLE_RATE_HZ),
                "comparison": _jsonable(comparison),
                "reference_distance": _distance(comparison["pairs"]["reference_candidate"]),
            }
        )
    if reference is None:
        status = "REFERENCE_TARGET_MISSING"
        selected: list[str] = []
        rejected = [{"candidate_id": row["candidate_id"], "reason": "reference target missing; selection withheld"} for row in rows]
    else:
        parent_distance = _distance(rows[0]["comparison"]["pairs"]["reference_parent"])  # type: ignore[index]
        eligible = [row for row in rows if parent_distance is not None and row["reference_distance"] is not None and float(row["reference_distance"]) <= parent_distance * 0.80]
        eligible.sort(key=lambda row: float(row["reference_distance"]))
        selected = [str(eligible[0]["candidate_id"])] if eligible else []
        status = "CANDIDATE_SELECTED" if selected else "NO_MEASURABLE_IMPROVEMENT"
        rejected = [{"candidate_id": row["candidate_id"], "reason": "below 20% objective improvement"} for row in rows if row["candidate_id"] not in selected]
    result = {"schema_version": "s12.stage_v.candidate_grid.v1", "status": status, "scope": "synthetic; uncalibrated; not OEM reproduction", "vehicle_id": "hellcat_v1", "candidates": rows, "selected_candidates": selected, "rejected_candidates": rejected, "parameter_reachability": {"combustion_event.rise_time_s": "attack", "combustion_event.decay_time_s": "tail", "per_path_primary_length_m": "arrival/path spectrum"}}
    write_json(root / "candidate_grid_results.json", result)
    write_json(root / "selected_candidates.json", {"status": status, "selected_candidates": selected})
    write_json(root / "rejected_candidates.json", {"status": status, "rejected_candidates": rejected})
    return result


__all__ = ["run_hellcat_candidate_grid"]
