"""Compare formal, unaltered PCM package members without claiming real-reference identity."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import wave
import zipfile
from pathlib import Path

import numpy as np

from .core import ComparisonCase, compare_signals
from .reporting import write_json_report


def _pcm24(raw: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(raw)) as wav:
        if (wav.getnchannels(), wav.getsampwidth()) != (2, 3):
            raise ValueError("expected stereo PCM24")
        data = np.frombuffer(wav.readframes(wav.getnframes()), np.uint8).reshape(-1, 3)
        values = data[:, 0].astype(np.int32) | (data[:, 1].astype(np.int32) << 8) | (data[:, 2].astype(np.int32) << 16)
        values = np.where(values & 0x800000, values - (1 << 24), values).astype(np.float64) / (1 << 23)
        return values.reshape(-1, 2), wav.getframerate()


def _internal_result(
    vehicle_id: str,
    parent_raw: bytes,
    candidate_raw: bytes,
    *,
    parent_role: str,
    source_package_status: str | None = None,
    candidate_id: str | None = None,
) -> dict[str, object]:
    parent, sample_rate_hz = _pcm24(parent_raw)
    candidate, candidate_rate_hz = _pcm24(candidate_raw)
    if sample_rate_hz != candidate_rate_hz:
        raise ValueError("sample rate mismatch")
    parent_sha = hashlib.sha256(parent_raw).hexdigest()
    candidate_sha = hashlib.sha256(candidate_raw).hexdigest()
    case = ComparisonCase(
        vehicle_id=vehicle_id,
        scenario="full_cycle",
        reference_id=f"synthetic_parent:{parent_sha}",
        candidate_id=candidate_id or f"synthetic_candidate:{candidate_sha}",
        sample_rate_hz=sample_rate_hz,
        reference_rpm=(0.0, 0.0),
        candidate_rpm=(0.0, 0.0),
        reference_load=(0.0, 0.0),
        candidate_load=(0.0, 0.0),
        analysis_domain="unaltered_analysis_signal",
        reference_kind="synthetic_parent",
    )
    result = compare_signals(parent, candidate, case)
    result.update(
        {
            "comparison_kind": "synthetic_parent_to_candidate_internal_regression_only",
            "reference_limited": True,
            "external_identity_score": None,
            "parent_role": parent_role,
            "parent_sha256": parent_sha,
            "candidate_sha256": candidate_sha,
        }
    )
    if source_package_status is not None:
        result["source_package_status"] = source_package_status
    return result


def _compare_stage_k_package(root: Path, manifest: dict[str, object], vehicles: dict[str, object]) -> None:
    archive = next(root.glob("*.zip"))
    with zipfile.ZipFile(archive) as package:
        for vehicle_id, record in manifest["vehicles"].items():
            formal = record["formal"]
            parent = formal.get("parent", formal["baseline"])
            candidate = formal["candidate"]
            parent_raw = package.read(parent["path"].replace("\\", "/"))
            candidate_raw = package.read(candidate["path"].replace("\\", "/"))
            vehicles[vehicle_id] = _internal_result(
                vehicle_id,
                parent_raw,
                candidate_raw,
                parent_role="parent" if "parent" in formal else "baseline_fallback_parent_missing",
                source_package_status=manifest.get("status"),
            )


def _compare_stage_l_package(root: Path, manifest: dict[str, object], vehicles: dict[str, object]) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("Stage-L artifact manifest must expose artifacts by relative path")
    parent_path = next((path for path in artifacts if "StageK_Parent" in path), None)
    candidate_path = next((path for path in artifacts if "StageL_v9_Candidate" in path and "Comfort" not in path), None)
    if parent_path is None or candidate_path is None:
        raise ValueError("Stage-L formal parent/candidate pair not found")
    candidate_receipt = artifacts[candidate_path].get("producer_receipt", {})
    vehicles["hellcat"] = _internal_result(
        "hellcat",
        (root / parent_path).read_bytes(),
        (root / candidate_path).read_bytes(),
        parent_role="stage_k_parent",
        source_package_status=str(manifest.get("status")),
        candidate_id=str(candidate_receipt.get("candidate_id", "hellcat_stage_l_v9")),
    )
    vehicles["hellcat"]["stage_l_candidate_version"] = "v9"
    vehicles["hellcat"]["stage_l_diagnostic_only"] = True


def compare_packages(roots: list[Path]) -> dict[str, object]:
    vehicles: dict[str, object] = {}
    for root in roots:
        manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
        if "vehicles" in manifest:
            _compare_stage_k_package(root, manifest, vehicles)
        elif manifest.get("package_id") == "s12-stage-l-hellcat-intake-roughness-v6":
            _compare_stage_l_package(root, manifest, vehicles)
        else:
            raise ValueError(f"unsupported package manifest: {root}")
    return {
        "schema_version": "s12-stage-m-comparator-results-2",
        "analysis_domain": "unaltered_final_pcm",
        "vehicles": vehicles,
        "limitations": [
            "no legally/provenance-bound external reference waveform supplied",
            "all computed deltas are synthetic-parent-to-candidate internal regression evidence",
            "full-cycle package comparison is not a scenario/RPM matched real-reference comparison",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 3:
        raise SystemExit("usage: python -m tools.sound_sim.s12.acoustic_comparator.cli OUTPUT PACKAGE_ROOT...")
    output = Path(args[0])
    write_json_report(output, compare_packages([Path(item) for item in args[1:]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
