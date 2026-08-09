from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_f.reference_distance import compare_final_pcm, final_pcm_band_shares, load_target
from ..render_identity_v02 import _read_pcm24_wav


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--stage-c-root", type=Path, required=True)
    parser.add_argument("--stage-f-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for vehicle in ("ferrari_458", "hellcat", "rx7_fd"):
        target = load_target(args.reference_root / f"{vehicle}_reference_targets.json")
        result[vehicle] = {}
        for state, filename in (("idle", "idle.wav"), ("acceleration", "acceleration.wav"), ("afterfire", "deceleration.wav")):
            stage_c = final_pcm_band_shares(_read_pcm24_wav(args.stage_c_root / vehicle / filename))
            stage_f = final_pcm_band_shares(_read_pcm24_wav(args.stage_f_root / vehicle / filename))
            result[vehicle][state] = compare_final_pcm(target, stage_c, stage_f)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
