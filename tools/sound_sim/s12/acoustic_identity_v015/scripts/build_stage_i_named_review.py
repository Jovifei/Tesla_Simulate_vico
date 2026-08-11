"""Build the named Stage-I review from a JSON map of rendered PCM24 WAVs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.named_review import (
    METRIC_ARTIFACT_LAYOUT,
    build_stage_i_named_review,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--qualification-json", type=Path, required=True)
    parser.add_argument("--reference-distance-json", type=Path, required=True)
    parser.add_argument("--metric-artifacts-root", type=Path, required=True)
    parser.add_argument(
        "--unqualified-diagnostic",
        action="store_true",
        help="build an explicitly unqualified diagnostic package instead of failing closed",
    )
    args = parser.parse_args()
    metric_artifacts = {
        artifact_id: args.metric_artifacts_root / Path(relative_path).name
        for artifact_id, relative_path in METRIC_ARTIFACT_LAYOUT.items()
    }
    result = build_stage_i_named_review(
        args.output_root,
        metric_artifacts=metric_artifacts,
        qualification_json=args.qualification_json,
        reference_distance_json=args.reference_distance_json,
        source_manifest=args.source_manifest,
        diagnostic_mode=args.unqualified_diagnostic,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
