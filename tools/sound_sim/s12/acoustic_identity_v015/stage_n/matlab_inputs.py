"""Prepare hash-bound MATLAB project inputs from existing Stage-M evidence.

The inputs retain the archived stereo PCM24 integers and the exact state trace
used to render each final candidate.  They are generated locally, never
committed, and may only be consumed by a manually opened MATLAB Desktop
session through ``s12_stage_n_run_order_analysis``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.cli import _pcm24
from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace


DEFAULT_STAGE_M_REVIEW = Path(r"E:\Tesla_speed\review_packages\s12-stage-m-comparator-and-calibration-v1")
DEFAULT_STAGE_K_THREE = Path(r"E:\Tesla_speed\review_packages\s12-stage-k-three-vehicle-round2-v4")
DEFAULT_STAGE_K_REMAINING = Path(r"E:\Tesla_speed\review_packages\s12-stage-k-remaining-four-round2-v1")
DEFAULT_STAGE_L = Path(r"E:\Tesla_speed\review_packages\s12-stage-l-hellcat-intake-roughness-v6")
DEFAULT_OUTPUT = Path("artifacts/matlab/s12-stage-n-order-inputs-v1")
SAMPLE_RATE_HZ = 48_000


@dataclass(frozen=True)
class CandidateBinding:
    vehicle_id: str
    source_package: str
    candidate_path: str
    candidate_sha256: str
    trace_sha256: str
    trace_hash_kind: str
    frame_count: int
    raw_pcm24: bytes


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stage_k_trace_sha256(trace: object) -> str:
    digest = hashlib.sha256()
    for values in (trace.time_s, trace.rpm, trace.load, trace.throttle, trace.acceleration_mps2):
        digest.update(np.asarray(values, dtype=np.float64).tobytes())
    return digest.hexdigest()


def _stage_l_trace_sha256(trace: object) -> str:
    payload = json.dumps(
        {
            "time_s": np.asarray(trace.time_s, dtype=np.float64).tolist(),
            "rpm": np.asarray(trace.rpm, dtype=np.float64).tolist(),
            "load": np.asarray(trace.load, dtype=np.float64).tolist(),
            "throttle": np.asarray(trace.throttle, dtype=np.float64).tolist(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(payload)


def _state_codes(time_s: np.ndarray) -> np.ndarray:
    """Return the published canonical-cycle state label for each sample."""

    duration_s = float(time_s[-1])
    phase = time_s / duration_s
    return np.select(
        (
            phase < 4.0 / 30.0,
            phase < 13.0 / 30.0,
            phase < 18.0 / 30.0,
            phase < 23.0 / 30.0,
            phase < 26.0 / 30.0,
        ),
        (0, 1, 2, 3, 4),
        default=5,
    ).astype(np.uint8)


def _load_stage_m_candidates(stage_m_review: Path) -> dict[str, str]:
    manifest = _read_json(stage_m_review / "artifact_manifest.json")
    records = manifest.get("vehicles")
    if not isinstance(records, Mapping):
        raise ValueError("Stage-M review manifest does not expose vehicle records")
    result: dict[str, str] = {}
    for record in records.values():
        if not isinstance(record, Mapping):
            raise ValueError("Stage-M review vehicle record is malformed")
        vehicle_id = str(record["vehicle_id"])
        candidate_sha = str(record["candidate_sha256"]).lower()
        if vehicle_id in result:
            raise ValueError(f"Stage-M review maps {vehicle_id} more than once")
        result[vehicle_id] = candidate_sha
    return result


def _load_stage_k_bindings(root: Path, stage_m_candidates: Mapping[str, str]) -> list[CandidateBinding]:
    manifest = _read_json(root / "artifact_manifest.json")
    records = manifest.get("vehicles")
    if not isinstance(records, Mapping):
        raise ValueError(f"Stage-K manifest does not expose vehicles: {root}")
    archives = list(root.glob("*.zip"))
    if len(archives) != 1:
        raise ValueError(f"expected exactly one immutable Stage-K archive: {root}")
    bindings: list[CandidateBinding] = []
    with zipfile.ZipFile(archives[0]) as archive:
        for vehicle_id, record in records.items():
            if not isinstance(record, Mapping):
                raise ValueError(f"malformed Stage-K vehicle record: {vehicle_id}")
            formal = record.get("formal")
            if not isinstance(formal, Mapping) or not isinstance(formal.get("candidate"), Mapping):
                raise ValueError(f"Stage-K candidate receipt missing: {vehicle_id}")
            candidate = formal["candidate"]
            candidate_path = str(candidate["path"]).replace("\\", "/")
            raw = archive.read(candidate_path)
            candidate_sha = str(candidate.get("sha256", candidate.get("pcm_sha256", ""))).lower()
            if _sha256(raw) != candidate_sha or stage_m_candidates.get(str(vehicle_id)) != candidate_sha:
                raise ValueError(f"Stage-M/Stage-K candidate SHA binding failed: {vehicle_id}")
            frame_count = int(candidate.get("frames", candidate.get("header", {}).get("frames", record.get("trace_frames", 0))))
            trace_sha = str(record.get("trace_sha256", candidate.get("trace_sha256", ""))).lower()
            bindings.append(CandidateBinding(
                vehicle_id=str(vehicle_id),
                source_package=root.name,
                candidate_path=candidate_path,
                candidate_sha256=candidate_sha,
                trace_sha256=trace_sha,
                trace_hash_kind="stage_k_binary_time_rpm_load_throttle_acceleration",
                frame_count=frame_count,
                raw_pcm24=raw,
            ))
    return bindings


def _load_stage_l_binding(root: Path, stage_m_candidates: Mapping[str, str]) -> CandidateBinding:
    manifest = _read_json(root / "artifact_manifest.json")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("Stage-L manifest does not expose artifacts")
    candidate_path = next(
        (str(path) for path in artifacts if "StageL_v9_Candidate" in str(path) and "Comfort" not in str(path)),
        None,
    )
    if candidate_path is None or not isinstance(artifacts[candidate_path], Mapping):
        raise ValueError("Stage-L v9 candidate receipt is missing")
    record = artifacts[candidate_path]
    receipt = record.get("producer_receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("Stage-L v9 candidate producer receipt is missing")
    raw = (root / candidate_path).read_bytes()
    candidate_sha = str(record.get("sha256", "")).lower()
    if _sha256(raw) != candidate_sha or stage_m_candidates.get("hellcat") != candidate_sha:
        raise ValueError("Stage-M/Stage-L Hellcat candidate SHA binding failed")
    return CandidateBinding(
        vehicle_id="hellcat",
        source_package=root.name,
        candidate_path=candidate_path.replace("\\", "/"),
        candidate_sha256=candidate_sha,
        trace_sha256=str(receipt["trace_sha256"]).lower(),
        trace_hash_kind="stage_l_json_time_rpm_load_throttle",
        frame_count=int(record["pcm_health"]["frame_count"]),
        raw_pcm24=raw,
    )


def write_matlab_input(binding: CandidateBinding, output_root: Path) -> dict[str, object]:
    """Validate one existing final-PCM candidate and emit a non-lossy MAT input."""

    try:
        from scipy.io import savemat
    except ImportError as exc:  # pragma: no cover - exercised by the Stage-N venv check
        raise RuntimeError("SciPy is required to write a MATLAB input; use the isolated Stage-N venv.") from exc
    pcm, sample_rate_hz = _pcm24(binding.raw_pcm24)
    if sample_rate_hz != SAMPLE_RATE_HZ or pcm.shape != (binding.frame_count, 2):
        raise ValueError(f"PCM header/frame binding failed: {binding.vehicle_id}")
    trace = build_drive_cycle_trace(binding.vehicle_id, duration_s=60.0)
    actual_trace_sha = (
        _stage_l_trace_sha256(trace)
        if binding.trace_hash_kind.startswith("stage_l_")
        else _stage_k_trace_sha256(trace)
    )
    if actual_trace_sha != binding.trace_sha256 or trace.time_s.size != binding.frame_count:
        raise ValueError(f"candidate/state-trace binding failed: {binding.vehicle_id}")
    pcm24 = np.rint(pcm * (1 << 23)).astype(np.int32)
    filename = output_root / f"{binding.vehicle_id}_full_cycle.mat"
    savemat(
        filename,
        {
            "vehicle_id": binding.vehicle_id,
            "scenario": "full_cycle",
            "sample_rate_hz": np.asarray([[sample_rate_hz]], dtype=np.float64),
            "signal_pcm24": pcm24,
            "rpm": np.asarray(trace.rpm, dtype=np.float64),
            "state_trace": _state_codes(np.asarray(trace.time_s, dtype=np.float64)),
            "candidate_sha256": binding.candidate_sha256,
            "trace_sha256": binding.trace_sha256,
        },
        do_compression=True,
        long_field_names=True,
    )
    return {
        "vehicle_id": binding.vehicle_id,
        "scenario": "full_cycle",
        "mat_file": filename.name,
        "mat_sha256": _sha256(filename.read_bytes()),
        "candidate_sha256": binding.candidate_sha256,
        "candidate_path": binding.candidate_path,
        "source_package": binding.source_package,
        "frame_count": binding.frame_count,
        "sample_rate_hz": sample_rate_hz,
        "trace_sha256": binding.trace_sha256,
        "trace_hash_kind": binding.trace_hash_kind,
        "channel_policy": "exact_stereo_pcm24_then_matlab_stereo_mean_to_mono",
        "state_codes": {
            "0": "idle", "1": "acceleration", "2": "full_pull",
            "3": "lift_afterfire", "4": "coast", "5": "idle_return",
        },
    }


def prepare_project_inputs(
    output_root: Path,
    *,
    stage_m_review: Path = DEFAULT_STAGE_M_REVIEW,
    stage_k_three: Path = DEFAULT_STAGE_K_THREE,
    stage_k_remaining: Path = DEFAULT_STAGE_K_REMAINING,
    stage_l: Path = DEFAULT_STAGE_L,
) -> dict[str, object]:
    """Create fresh Stage-N-only MATLAB inputs; a non-empty root is immutable."""

    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite MATLAB project-input root: {output_root}")
    stage_m_candidates = _load_stage_m_candidates(stage_m_review)
    bindings = [
        *_load_stage_k_bindings(stage_k_three, stage_m_candidates),
        *_load_stage_k_bindings(stage_k_remaining, stage_m_candidates),
        _load_stage_l_binding(stage_l, stage_m_candidates),
    ]
    if {binding.vehicle_id for binding in bindings} != set(stage_m_candidates) or len(bindings) != 8:
        raise ValueError("Stage-N MATLAB inputs require exactly the eight Stage-M candidates")
    output_root.mkdir(parents=True)
    records = [write_matlab_input(binding, output_root) for binding in sorted(bindings, key=lambda item: item.vehicle_id)]
    manifest = {
        "schema_version": "s12-stage-n-matlab-project-inputs-1",
        "status": "PREPARED_NOT_EXECUTED_IN_MATLAB",
        "source_policy": "immutable Stage-M candidate PCM plus hash-matched canonical state trace",
        "reference_status": "REFERENCE_RPM_UNAVAILABLE",
        "order_comparison_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "vehicle_count": len(records),
        "records": records,
    }
    (output_root / "input_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stage-m-review", type=Path, default=DEFAULT_STAGE_M_REVIEW)
    parser.add_argument("--stage-k-three", type=Path, default=DEFAULT_STAGE_K_THREE)
    parser.add_argument("--stage-k-remaining", type=Path, default=DEFAULT_STAGE_K_REMAINING)
    parser.add_argument("--stage-l", type=Path, default=DEFAULT_STAGE_L)
    args = parser.parse_args(argv)
    result = prepare_project_inputs(
        args.output,
        stage_m_review=args.stage_m_review,
        stage_k_three=args.stage_k_three,
        stage_k_remaining=args.stage_k_remaining,
        stage_l=args.stage_l,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
