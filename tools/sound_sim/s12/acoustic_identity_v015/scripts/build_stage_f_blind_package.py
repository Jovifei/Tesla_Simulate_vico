from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_f.package_builder import build_stage_f_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--duration-s", type=float, default=60.0)
    args = parser.parse_args()
    result = build_stage_f_package(args.output_root, seed=args.seed, duration_s=args.duration_s)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
