"""Run Stage Y authorized local calibration bundle extraction.

Example:

    python -m tools.sound_sim.s12.acoustic_identity_v015.stage_y.drivers.drive_y2_calibration_bundle \
        --bundle E:/Tesla_speed/private_references/hellcat/full_pull_01 \
        --output E:/Tesla_speed/tasks/reports/runtime/s12-stage-y/hellcat_full_pull_01
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..calibration_bundle import run_calibration_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract authorized Stage Y timbre/residual assets")
    parser.add_argument("--bundle", required=True, type=Path, help="directory containing audio.wav/state.csv/rights.json/recording.json")
    parser.add_argument("--output", required=True, type=Path, help="local derived-output directory")
    parser.add_argument("--phase-samples", type=int, default=512)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_calibration_bundle(args.bundle, args.output, phase_samples=args.phase_samples)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
