"""Render the thirteen source WAVs for the Stage-I named review package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.source_evidence import (
    render_stage_i_named_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--stage-h-review-root", type=Path, required=True)
    parser.add_argument("--candidate-a", type=Path, required=True)
    parser.add_argument("--candidate-b", type=Path, required=True)
    parser.add_argument("--candidate-c", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=60.0)
    args = parser.parse_args()
    result = render_stage_i_named_sources(
        args.output_root,
        stage_h_review_root=args.stage_h_review_root,
        stage_i_candidate_paths={
            "a_balanced": args.candidate_a,
            "b_whine_forward": args.candidate_b,
            "c_softer_mechanical": args.candidate_c,
        },
        full_cycle_duration_s=args.duration_s,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
