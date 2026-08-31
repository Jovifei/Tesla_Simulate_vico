"""Render labelled final-PCM Stage C/Stage G reference evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..stage_g.candidate_profiles import load_stage_g_candidate
from ..stage_g.reference_evidence import (
    ANCHOR_VEHICLE_IDS,
    build_stage_g_reference_evidence,
)
from ..stage_g.reference_targets import REFERENCE_STATE_IDS, load_reference_state_target
from ..stage_g.render_candidate import render_stage_g_candidate


_CANDIDATE_FILENAMES = {
    "ferrari_458": "Ferrari_candidate_v4.json",
    "hellcat": "Hellcat_candidate_v4.json",
    "rx7_fd": "RX7_candidate_v4.json",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=60.0)
    args = parser.parse_args()

    index: dict[str, object] = {
        "schema_version": "s12-stage-g-reference-evidence-index-1",
        "vehicles": {},
    }
    for vehicle_id in ANCHOR_VEHICLE_IDS:
        candidate_path = args.candidate_root / _CANDIDATE_FILENAMES[vehicle_id]
        candidate = load_stage_g_candidate(candidate_path)
        candidate_sha = _sha256(candidate_path)
        evidence = build_stage_g_reference_evidence(
            vehicle_id,
            args.output_root,
            stage_g_renderer=lambda current_vehicle, trace, current=candidate: render_stage_g_candidate(
                current_vehicle, trace, current
            ),
            duration_s=args.duration_s,
            candidate_sha256=candidate_sha,
        )
        reference_path = args.reference_root / f"{vehicle_id}_reference_targets.json"
        reference_sha = _sha256(reference_path)
        targets = {}
        for state_id in REFERENCE_STATE_IDS:
            target = load_reference_state_target(
                reference_path, vehicle_id, state_id, reference_sha
            )
            targets[state_id] = None if target is None else {
                "band_shares": list(target.band_shares),
                "spectral_centroid_hz": target.spectral_centroid_hz,
                "source_sha256": target.source_sha256,
                "provenance": dict(target.provenance),
            }
        index["vehicles"][vehicle_id] = {
            "candidate_sha256": candidate_sha,
            "reference_target_sha256": reference_sha,
            "trace_sha256": evidence["trace_sha256"],
            "targets": targets,
            "evidence_path": str(
                args.output_root / vehicle_id / "reference_evidence.json"
            ),
        }

    output = args.output_root / "stage_g_reference_evidence_index.json"
    output.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
