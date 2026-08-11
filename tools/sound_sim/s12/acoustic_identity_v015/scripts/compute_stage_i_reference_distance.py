"""Compute Stage-I A/B/C final-PCM reference distance from Stage H."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.reference_distance import (
    CANDIDATE_IDS,
    compute_stage_i_reference_distance,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-h-wav", required=True, type=Path)
    parser.add_argument("--candidate-a-wav", required=True, type=Path)
    parser.add_argument("--candidate-b-wav", required=True, type=Path)
    parser.add_argument("--candidate-c-wav", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compute_stage_i_reference_distance(
        args.stage_h_wav,
        {
            CANDIDATE_IDS[0]: args.candidate_a_wav,
            CANDIDATE_IDS[1]: args.candidate_b_wav,
            CANDIDATE_IDS[2]: args.candidate_c_wav,
        },
        args.target,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"output": str(args.output.resolve()), "status": result["automatic_status"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
