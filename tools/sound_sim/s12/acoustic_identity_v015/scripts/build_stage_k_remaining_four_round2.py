"""Build the independent Ferrari/RX-7/Supra/Aventador Stage-K Round-2 package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_remaining_package import (
        REVIEW_GAIN_LINEAR,
        build_stage_k_remaining_four_round2_review,
    )
else:
    from ..stage_k.round2_remaining_package import REVIEW_GAIN_LINEAR, build_stage_k_remaining_four_round2_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"E:\Tesla_speed\review_packages\s12-stage-k-remaining-four-vehicle-round2-v1"),
    )
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--diagnostic-duration-s", type=float, default=None)
    parser.add_argument("--review-gain-linear", type=float, default=REVIEW_GAIN_LINEAR)
    args = parser.parse_args()
    result = build_stage_k_remaining_four_round2_review(
        args.output_root,
        duration_s=args.duration_s,
        diagnostic_duration_s=args.diagnostic_duration_s,
        requested_review_gain_linear=args.review_gain_linear,
    )
    print(
        json.dumps(
            {
                "output_root": result["output_root"],
                "zip": result["zip"],
                "status": result["status"],
                "vehicle_ids": result["vehicle_ids"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
