"""CLI for Stage-AF physical negative-feedback tuning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .physical_closed_loop import fit_vehicle, write_fit_result


def _load_base(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "overrides" in payload:
        payload = payload["overrides"]
    return {str(k): float(v) for k, v in payload.items()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tune the successful Stage-AD EngineAcoustics against governed reference WAVs")
    parser.add_argument("--vehicle", required=True, choices=["hellcat", "ferrari_458", "lfa", "gtr_r35"])
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--family", action="append", choices=["body", "path", "induction", "afterfire"])
    parser.add_argument("--base-fit", type=Path)
    parser.add_argument("--candidates", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--reference-level", default="R3_PRIVATE_DIAGNOSTIC_ONLY")
    args = parser.parse_args(argv)

    result = fit_vehicle(
        args.vehicle,
        args.reference_dir,
        families=args.family or ("body", "path", "induction", "afterfire"),
        base_overrides=_load_base(args.base_fit),
        candidates_per_round=args.candidates,
        max_rounds=args.rounds,
        seed=args.seed,
        reference_level=args.reference_level,
    )
    path = write_fit_result(result, args.output_dir)
    print(f"Stage AF fit: {args.vehicle}")
    print(f"baseline_distance={result.baseline_distance:.6f}")
    print(f"final_distance={result.final_distance:.6f}")
    print(f"fit={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
