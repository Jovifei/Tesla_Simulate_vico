"""Build the named Stage-H Hellcat engineering audition package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_h.named_review import build_stage_h_named_review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--candidate", type=Path, default=None)
    args = parser.parse_args()
    result = build_stage_h_named_review(args.output_root, stage_h_candidate_path=args.candidate, duration_s=args.duration_s)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
