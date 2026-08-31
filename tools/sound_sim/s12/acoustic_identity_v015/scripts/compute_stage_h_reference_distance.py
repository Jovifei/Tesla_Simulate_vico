"""Compute Stage-H Hellcat final-PCM reference distance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_h.reference_distance import compute_stage_h_reference_distance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-g-wav", required=True, type=Path)
    parser.add_argument("--stage-h-wav", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compute_stage_h_reference_distance(
        args.stage_g_wav,
        args.stage_h_wav,
        args.target,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "status": result["automatic_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
