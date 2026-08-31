"""Build the Stage-G v4 listener package outside Git."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..stage_g.package_builder import build_stage_g_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=None)
    args = parser.parse_args()
    candidate_paths = {
        "ferrari_458": args.candidate_root / "Ferrari_candidate_v4.json",
        "hellcat": args.candidate_root / "Hellcat_candidate_v4.json",
        "rx7_fd": args.candidate_root / "RX7_candidate_v4.json",
    }
    result = build_stage_g_package(args.output_root, candidate_paths=candidate_paths, duration_s=args.duration_s, seed=args.seed if args.seed is not None else 0x5331325F53544147455F475F56345F31)
    print(result)


if __name__ == "__main__":
    main()
