"""CLI for the explicit Stage-J three-vehicle review package."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.stage_j.named_review import build_stage_j_named_review


def main() -> int:
    parser = argparse.ArgumentParser(description="Build S12 Stage-J named C63/GT-R/LFA review package")
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--review-gain-linear", type=float, default=1.25)
    args = parser.parse_args()
    result = build_stage_j_named_review(args.output_root, duration_s=args.duration_s, requested_review_gain_linear=args.review_gain_linear)
    print(result["status"])
    print(result.get("zip_path", args.output_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
