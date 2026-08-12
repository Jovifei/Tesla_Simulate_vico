"""Build a Stage-L Hellcat unqualified diagnostic named review package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
    from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.named_review import (
        build_unqualified_diagnostic_package, render_stage_l_named_artifacts,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
        _apply_current_frozen_layers, render_stage_l_candidate, render_stage_l_parent,
    )
else:
    from ..render_drive_cycle_v10 import build_drive_cycle_trace
    from ..stage_l.candidate_profiles import load_stage_l_candidate
    from ..stage_l.named_review import build_unqualified_diagnostic_package, render_stage_l_named_artifacts
    from ..stage_l.render_candidate import (
        _apply_current_frozen_layers, render_stage_l_candidate, render_stage_l_parent,
    )


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = PACKAGE_ROOT / "targets/stage_l_candidates/hellcat_candidate_v8.json"
DEFAULT_OUTPUT = Path(r"E:\Tesla_speed\review_packages\s12-stage-l-hellcat-intake-roughness-v1")


def build_production_stage_l_named_review(
    output_root: str | Path,
    *,
    candidate_profile_path: str | Path = DEFAULT_PROFILE,
    duration_s: float = 60.0,
    requested_gain_db: float = 1.9382,
) -> dict[str, object]:
    """Render the canonical parent/candidate once, then publish the diagnostic package."""
    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"output root already exists; refusing overwrite: {root}")
    profile_path = Path(candidate_profile_path).resolve()
    candidate = load_stage_l_candidate(profile_path)
    parent_profile = PACKAGE_ROOT / str(candidate.payload["parent_candidate_path"])
    artifact_root = root.parent / f".{root.name}-artifacts"
    if artifact_root.exists():
        raise FileExistsError(f"artifact output root already exists; refusing overwrite: {artifact_root}")
    trace = build_drive_cycle_trace("hellcat", duration_s=float(duration_s))

    def parent_renderer(actual_trace):
        return render_stage_l_parent(actual_trace)

    def candidate_renderer(actual_trace):
        source = render_stage_l_candidate(actual_trace, candidate)
        return _apply_current_frozen_layers(source, actual_trace, candidate, include_l4=True)

    produced = render_stage_l_named_artifacts(
        artifact_root,
        trace=trace,
        parent_renderer=parent_renderer,
        candidate_renderer=candidate_renderer,
        source_commit=str(candidate.payload["base_commit"]),
        parent_profile_sha256=hashlib.sha256(parent_profile.read_bytes()).hexdigest(),
        candidate_profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        trace_version="stage-l-canonical-cycle-v1",
        requested_gain_db=float(requested_gain_db),
    )
    return build_unqualified_diagnostic_package(
        root,
        artifact_manifest_path=produced["artifact_manifest_path"],
        expected_artifact_manifest_sha256=produced["artifact_manifest_sha256"],
        task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidate-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--review-gain-db", type=float, default=1.9382)
    parser.add_argument("--artifact-manifest", type=Path)
    parser.add_argument("--expected-artifact-manifest-sha256")
    args = parser.parse_args(argv)
    if (args.artifact_manifest is None) != (args.expected_artifact_manifest_sha256 is None):
        parser.error("--artifact-manifest and --expected-artifact-manifest-sha256 must be supplied together")
    if args.artifact_manifest is not None:
        result = build_unqualified_diagnostic_package(
            args.output_root,
            artifact_manifest_path=args.artifact_manifest,
            expected_artifact_manifest_sha256=args.expected_artifact_manifest_sha256,
            task6_gate_status={"residency_max": 5, "formal_final_provenance": "NOT_AVAILABLE"},
        )
    else:
        result = build_production_stage_l_named_review(
            args.output_root,
            candidate_profile_path=args.candidate_profile,
            duration_s=args.duration_s,
            requested_gain_db=args.review_gain_db,
        )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
