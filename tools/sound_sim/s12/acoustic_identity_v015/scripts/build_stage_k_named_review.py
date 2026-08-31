"""Build the Stage-K four-vehicle named listening package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.named_review import build_stage_k_named_review
else:
    from ..stage_k.named_review import build_stage_k_named_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1"),
    )
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--review-gain-linear", type=float, default=1.25)
    args = parser.parse_args()
    result = build_stage_k_named_review(
        args.output_root,
        duration_s=args.duration_s,
        requested_review_gain_linear=args.review_gain_linear,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
