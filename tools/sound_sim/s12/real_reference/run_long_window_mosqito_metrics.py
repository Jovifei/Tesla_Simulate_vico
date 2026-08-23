"""Run isolated MoSQITo on all 15/30-second long-window pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.real_reference.long_window_analysis import load_long_window_pairs
from tools.sound_sim.s12.real_reference.run_exact_mosqito_metrics import _read_signal
from tools.sound_sim.s12.acoustic_comparator.psychoacoustics.mosqito_adapter import compute_mosqito_metrics


def run_long_mosqito(manifest_path: Path, output_path: Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    pairs = load_long_window_pairs(manifest_path)
    rows = []
    for index, pair in enumerate(pairs, 1):
        reference, reference_fs = _read_signal(Path(pair["reference_path"]))
        candidate, _ = _read_signal(Path(pair["candidate_path"]), reference_fs)
        duration_s = float(pair["window"]["duration_s"])
        samples = min(reference.size, candidate.size, int(round(duration_s * reference_fs)))
        for side, signal in (("reference", reference[:samples]), ("candidate", candidate[:samples])):
            measurement = compute_mosqito_metrics(signal, reference_fs)
            metrics = dict(measurement["results"])
            metrics.setdefault("fluctuation_vacil", None)
            rows.append({
                "pair_id": pair["pair_id"],
                "file_id": pair["file_id"],
                "side": side,
                "vehicle_id": pair["vehicle_id"],
                "scenario": pair["scenario"],
                "window_profile": pair["window"]["profile"],
                "sample_rate_hz": reference_fs,
                "window": {"start_s": 0.0, "duration_s": samples / reference_fs},
                "input_path": pair[f"{side}_path"],
                "input_sha256": pair[f"{side}_sha256"],
                "metrics": metrics,
                "unsupported_metrics": {"fluctuation_vacil": "NOT_SUPPORTED_BY_CURRENT_MOSQITO_ADAPTER"},
                "functions": measurement["functions"],
                "parameters": measurement["parameters"],
                "tool_domain": "Professional MoSQITo",
                "calibration": measurement["input_calibration"],
            })
        print(f"[{index}/{len(pairs)}] MoSQITo {pair['pair_id']}", flush=True)
    receipt = {
        "schema_version": "s12-professional-mosqito-long-window-receipt-v1",
        "status": "EXECUTED_ON_LONG_WINDOWS",
        "tool": "MoSQITo",
        "mosqito_version": "1.2.1",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "clip_count": len(rows),
        "window_profiles_s": [15.0, 30.0],
        "results": rows,
        "input_calibration": "digital-domain relative input; no full-scale-to-Pascal calibration or absolute SPL claim",
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite long-window MoSQITo receipt: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行隔离 MoSQITo 1.2.1 的 15/30 秒长窗口")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run_long_mosqito(args.manifest, args.output)
    print(json.dumps({"status": receipt["status"], "clip_count": receipt["clip_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
