"""Produce Stage-M automated closure artifacts and an optional local review package."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_m.closure import write_automated_closure
from tools.sound_sim.s12.acoustic_identity_v015.stage_m.evidence import load_reference_target_segments, load_round2_evidence
from tools.sound_sim.s12.acoustic_identity_v015.stage_m.review_package import build_local_review_package, write_feedback_binding


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--feedback-schema", type=Path, required=True)
    parser.add_argument("--review-package", type=Path, required=True)
    parser.add_argument("--stage-k-three", type=Path, required=True)
    parser.add_argument("--stage-k-remaining", type=Path, required=True)
    parser.add_argument("--stage-l-hellcat", type=Path, required=True)
    parser.add_argument("--reference-database", type=Path, required=True)
    parser.add_argument("--track-p-status", default="not independently verified in this generation")
    parser.add_argument("--build-review-package", action="store_true")
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    feedback_schema = json.loads(args.feedback_schema.read_text(encoding="utf-8"))
    if args.build_review_package:
        build_local_review_package(args.review_package, comparison, stage_k_three=args.stage_k_three, stage_k_remaining=args.stage_k_remaining, stage_l_hellcat=args.stage_l_hellcat)
    else:
        write_feedback_binding(args.review_package)
    source_metrics, package_status = load_round2_evidence(args.stage_k_three, args.stage_k_remaining, args.stage_l_hellcat)
    head = subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
    commits = subprocess.run(["git", "log", "--format=%h", "-5"], check=True, text=True, capture_output=True).stdout.splitlines()
    git_status = "clean" if not subprocess.run(["git", "status", "--porcelain"], check=True, text=True, capture_output=True).stdout.strip() else "dirty"
    write_automated_closure(
        args.runtime,
        comparison,
        feedback_schema=feedback_schema,
        review_package_root=args.review_package,
        source_metrics=source_metrics,
        target_segments=load_reference_target_segments(args.reference_database),
        package_status=package_status,
        final_context={"head": head, "local_commits": commits, "track_p_status": args.track_p_status, "git_status": git_status},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
