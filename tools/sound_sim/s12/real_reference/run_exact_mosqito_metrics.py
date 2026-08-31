"""Run real MoSQITo 1.2.1 on both sides of the exact anchor A/B clips."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from math import gcd
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.signal import resample_poly
from scipy.io import wavfile

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_comparator.psychoacoustics.mosqito_adapter import compute_mosqito_metrics  # noqa: E402
from tools.sound_sim.s12.real_reference.professional_clip_analysis import load_exact_anchor_pairs, validate_exact_clip_pair  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_signal(path: Path, target_fs: int | None = None) -> tuple[np.ndarray, int]:
    fs, raw = wavfile.read(str(path))
    values = np.asarray(raw)
    if np.issubdtype(values.dtype, np.integer):
        info = np.iinfo(values.dtype)
        scale = float(max(abs(info.min), info.max))
        values = values.astype(np.float64) / scale
    else:
        values = values.astype(np.float64)
    mono = values.mean(axis=1) if values.ndim > 1 else values
    if target_fs is not None and fs != target_fs:
        divisor = gcd(int(fs), int(target_fs))
        mono = resample_poly(mono, target_fs // divisor, int(fs) // divisor)
        fs = target_fs
    return mono, int(fs)


def build_receipt_from_rows(rows: Sequence[Mapping[str, Any]], manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "s12-professional-mosqito-exact-clip-receipt-v1",
        "status": "EXECUTED_ON_EXACT_CLIPS",
        "tool": "MoSQITo",
        "mosqito_version": "1.2.1",
        "manifest_sha256": manifest_sha256,
        "clip_count": len(rows),
        "results": list(rows),
        "input_calibration": "digital-domain relative input; no full-scale-to-Pascal calibration or absolute SPL claim",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }


def run_exact_mosqito(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path).resolve()
    pairs = load_exact_anchor_pairs(manifest_path)
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        validate_exact_clip_pair(pair)
        reference, reference_fs = _read_signal(Path(pair["reference_path"]))
        candidate, _ = _read_signal(Path(pair["candidate_path"]), reference_fs)
        window_samples = min(reference.size, candidate.size, int(round(5.0 * reference_fs)))
        for side, signal in (("reference", reference[:window_samples]), ("candidate", candidate[:window_samples])):
            measurement = compute_mosqito_metrics(signal, reference_fs)
            mosqito_metrics = dict(measurement["results"])
            # MoSQITo 1.2.1 does not expose the MATLAB fluctuation metric in
            # this adapter. Keep the column explicit instead of substituting a
            # proxy or pretending the tool measured it.
            mosqito_metrics.setdefault("fluctuation_vacil", None)
            rows.append({
                "pair_id": pair["pair_id"],
                "file_id": pair["file_id"],
                "side": side,
                "vehicle_id": pair["vehicle_id"],
                "sample_rate_hz": reference_fs,
                "window": {"start_s": 0.0, "duration_s": window_samples / reference_fs},
                "input_path": pair[f"{side}_path"],
                "input_sha256": pair[f"{side}_sha256"],
                "metrics": mosqito_metrics,
                "unsupported_metrics": {"fluctuation_vacil": "NOT_SUPPORTED_BY_CURRENT_MOSQITO_ADAPTER"},
                "functions": measurement["functions"],
                "parameters": measurement["parameters"],
                "tool_domain": "Professional MoSQITo",
                "calibration": measurement["input_calibration"],
            })
        print(f"[{index}/{len(pairs)}] MoSQITo {pair['pair_id']}", flush=True)
    receipt = build_receipt_from_rows(rows, _sha256(manifest_path))
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite MoSQITo receipt: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行隔离 MoSQITo 1.2.1 的 exact A/B 指标")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run_exact_mosqito(args.manifest, args.output)
    print(json.dumps({"status": receipt["status"], "clip_count": receipt["clip_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_receipt_from_rows", "run_exact_mosqito", "main"]
