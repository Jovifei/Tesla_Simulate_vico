"""Run pinned MoSQITo on unique Stage U raw-analysis clips."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.sound_sim.s12.acoustic_comparator.psychoacoustics.mosqito_adapter import compute_mosqito_metrics
from tools.sound_sim.s12.real_reference.run_exact_mosqito_metrics import _read_signal


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    clips = manifest.get("clips")
    if manifest.get("schema_version") != "s12-stage-u-unique-clip-manifest-v1" or not isinstance(clips, list):
        raise ValueError("invalid Stage U clip manifest")
    rows = []
    for index, clip in enumerate(clips, start=1):
        path = Path(clip["path"])
        signal, sample_rate_hz = _read_signal(path)
        actual = _sha256(path)
        if actual.lower() != str(clip["sha256"]).lower():
            raise ValueError(f"SHA mismatch: {clip['clip_id']}")
        measurement = compute_mosqito_metrics(signal, sample_rate_hz)
        metrics = dict(measurement["results"])
        metrics.setdefault("fluctuation_vacil", None)
        rows.append({
            **dict(clip),
            "input_sha256": actual,
            "sample_rate_hz": sample_rate_hz,
            "metrics": metrics,
            "unsupported_metrics": {"fluctuation_vacil": "NOT_SUPPORTED_BY_CURRENT_MOSQITO_ADAPTER"},
            "functions": measurement["functions"],
            "parameters": measurement["parameters"],
            "tool_domain": "Professional MoSQITo",
            "calibration": measurement["input_calibration"],
            "analysis_signal": "raw common-safety PCM; not loudness-matched audition copy",
        })
        print(f"[{index}/{len(clips)}] MoSQITo {clip['clip_id']}", flush=True)
    receipt = {
        "schema_version": "s12-stage-u-mosqito-receipt-v1",
        "status": "EXECUTED_ON_STAGE_U_RAW_CLIPS",
        "tool": "MoSQITo",
        "mosqito_version": "1.2.1",
        "manifest_sha256": _sha256(Path(manifest_path)),
        "clip_count": len(rows),
        "results": rows,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"refusing overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, sort_keys=True); stream.write("\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MoSQITo 1.2.1 on Stage U unique clips")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    receipt = run(arguments.manifest, arguments.output)
    print(json.dumps({"status": receipt["status"], "clip_count": receipt["clip_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
