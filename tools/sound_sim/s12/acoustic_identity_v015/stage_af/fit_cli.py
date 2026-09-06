"""Bounded fitting of the same EngineAcoustics mode used by the old dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_ad.engine_sim_acoustics import NUMERICAL_FIXES
from .physical_closed_loop import fit_vehicle, write_fit_result, validate_fit_payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vehicle",
        required=True,
        choices=["hellcat", "ferrari_458", "lfa", "gtr_r35"],
    )
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--family",
        action="append",
        choices=["body", "path", "induction", "afterfire"],
    )
    parser.add_argument("--base-fit", type=Path)
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument(
        "--reference-level",
        default="R3_PRIVATE_DIAGNOSTIC_ONLY",
        choices=["R3_PRIVATE_DIAGNOSTIC_ONLY", "R2_AUTHORIZED_DIAGNOSTIC"],
    )
    parser.add_argument(
        "--numerical-fixes",
        nargs="*",
        default=[],
        choices=sorted(NUMERICAL_FIXES),
    )
    args = parser.parse_args(argv)
    if (args.output_dir / "final_r3_diagnostic_fit.json").exists():
        parser.error(
            "fit output exists; preserve previous experiment and use a fresh directory"
        )
    base: dict[str, float] = {}
    if args.base_fit:
        base = validate_fit_payload(
            json.loads(args.base_fit.read_text(encoding="utf-8")),
            args.vehicle,
            args.numerical_fixes,
            args.seed,
        )
    result = fit_vehicle(
        args.vehicle,
        args.reference_dir,
        families=args.family or ("body", "path", "induction", "afterfire"),
        base_overrides=base,
        candidates_per_round=args.candidates,
        max_rounds=args.rounds,
        seed=args.seed,
        reference_level=args.reference_level,
        numerical_fixes=args.numerical_fixes,
    )
    output = write_fit_result(result, args.output_dir)
    print(f"baseline_distance={result.baseline_distance:.6f}")
    print(f"final_distance={result.final_distance:.6f}")
    print(f"fit={output}; HUMAN_NOT_EVALUATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
