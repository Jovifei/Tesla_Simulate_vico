"""Validate and score a completed Stage-G listener submission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_g.response_contract import score_stage_g_submission, validate_stage_g_submission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    listener = args.package_root / "listener"; sealed = args.package_root / "sealed"
    submission = validate_stage_g_submission(listener / "listener_manifest.json", listener / "blind_responses.csv", listener / "ab_responses.csv", listener / "playback_context.json")
    score = score_stage_g_submission(sealed / "answer_key.json", sealed / "pair_key.json", submission)
    args.output_root.mkdir(parents=True, exist_ok=True)
    payload = {"baseline": score.baseline, "candidate": score.candidate, "delta": dict(score.delta), "pair_results": list(score.pair_results), "gates": dict(score.gates), "status": score.status}
    (args.output_root / "stage_g_audition_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
