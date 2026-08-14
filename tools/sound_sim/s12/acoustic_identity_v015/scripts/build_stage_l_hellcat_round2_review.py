"""Build the S12 Stage-L Hellcat Round-2 v6 diagnostic audition package.

The command renders the frozen Stage-K parent, the Stage-L v8 baseline, and
the schema-v2 v9 candidate with one canonical trace.  It publishes only the
unqualified, synthetic diagnostic package; no feedback CSV is read and an
existing output root is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
    from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.named_review_round2 import (
        build_round2_unqualified_diagnostic_package,
        render_stage_l_round2_named_artifacts,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
        _apply_current_frozen_layers,
        render_stage_l_candidate,
        render_stage_l_parent,
    )
else:
    from ..render_drive_cycle_v10 import build_drive_cycle_trace
    from ..stage_l.candidate_profiles import load_stage_l_candidate
    from ..stage_l.named_review_round2 import (
        build_round2_unqualified_diagnostic_package,
        render_stage_l_round2_named_artifacts,
    )
    from ..stage_l.render_candidate import (
        _apply_current_frozen_layers,
        render_stage_l_candidate,
        render_stage_l_parent,
    )


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(r"E:\Tesla_speed\review_packages\s12-stage-l-hellcat-intake-roughness-v6")
DEFAULT_V8_PROFILE = PACKAGE_ROOT / "targets/stage_l_candidates/hellcat_candidate_v8.json"
DEFAULT_V9_PROFILE = PACKAGE_ROOT / "targets/stage_l_candidates/hellcat_candidate_v9.json"
DEFAULT_STAGE_K_PROFILE = PACKAGE_ROOT / "targets/stage_k_candidates/hellcat_candidate_v7.json"
REPO_ROOT = Path(__file__).resolve().parents[5]
PRODUCER_SOURCE_PATHS = (
    "tools/sound_sim/s12/acoustic_identity_v015/stage_l/named_review_round2.py",
    "tools/sound_sim/s12/acoustic_identity_v015/stage_l/render_candidate.py",
    "tools/sound_sim/s12/acoustic_identity_v015/scripts/build_stage_l_hellcat_round2_review.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("unable to bind producer source commit")
    value = completed.stdout.strip()
    if len(value) != 40:
        raise RuntimeError("producer source commit is not a full SHA")
    return value.lower()


def _producer_source_state(repo_root: Path) -> tuple[bool, dict[str, str]]:
    paths = [repo_root / relative for relative in PRODUCER_SOURCE_PATHS]
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError("producer source files are incomplete")
    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1", "--untracked-files=no", "--", *PRODUCER_SOURCE_PATHS],
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise RuntimeError("unable to bind producer source cleanliness")
    return bool(status.stdout.strip()), {
        relative: _sha256(repo_root / relative) for relative in PRODUCER_SOURCE_PATHS
    }


def build_production_stage_l_round2_review(
    output_root: str | Path,
    *,
    v8_profile_path: str | Path = DEFAULT_V8_PROFILE,
    v9_profile_path: str | Path = DEFAULT_V9_PROFILE,
    duration_s: float = 60.0,
    comfort_gain_db: float = 1.0,
) -> dict[str, object]:
    """Render the canonical parent/v8/v9 pair and atomically publish v6."""

    root = Path(output_root).resolve()
    if root.exists():
        raise FileExistsError(f"output root already exists; refusing overwrite: {root}")
    v8_path = Path(v8_profile_path).resolve()
    v9_path = Path(v9_profile_path).resolve()
    stage_k_path = DEFAULT_STAGE_K_PROFILE.resolve()
    if not v8_path.is_file() or not v9_path.is_file() or not stage_k_path.is_file():
        raise FileNotFoundError("the frozen Stage-K/v8/v9 profile set is incomplete")
    v8 = load_stage_l_candidate(v8_path)
    v9 = load_stage_l_candidate(v9_path)
    if v8.payload["schema_version"] != "s12-stage-l-hellcat-candidate-profile-1":
        raise ValueError("v8 baseline must remain schema v1")
    if v9.payload["schema_version"] != "s12-stage-l-hellcat-candidate-profile-2":
        raise ValueError("v9 candidate must use schema v2")
    if float(duration_s) <= 0.0:
        raise ValueError("duration_s must be positive")
    artifact_root = root.parent / f".{root.name}-artifacts"
    if artifact_root.exists():
        raise FileExistsError(f"artifact output root already exists; refusing overwrite: {artifact_root}")

    trace = build_drive_cycle_trace("hellcat", duration_s=float(duration_s))
    producer_source_commit = _git_head(REPO_ROOT)
    producer_source_dirty, producer_source_file_sha256 = _producer_source_state(REPO_ROOT)

    def parent_renderer(actual_trace):
        return render_stage_l_parent(actual_trace)

    def v8_renderer(actual_trace):
        source = render_stage_l_candidate(actual_trace, v8)
        return _apply_current_frozen_layers(source, actual_trace, v8, include_l4=True)

    def v9_renderer(actual_trace):
        source = render_stage_l_candidate(actual_trace, v9)
        # Schema-v2 owns the new source-domain contributors but deliberately
        # omits the frozen operating/shift sections.  Apply those common
        # layers with the immutable v8 baseline while the renderer preserves
        # the v9 parameter-usage receipt and dedicated afterfire contributor.
        return _apply_current_frozen_layers(source, actual_trace, v8, include_l4=True)

    produced = render_stage_l_round2_named_artifacts(
        artifact_root,
        trace=trace,
        stage_k_parent_renderer=parent_renderer,
        stage_l_v8_renderer=v8_renderer,
        stage_l_v9_renderer=v9_renderer,
        source_commit=producer_source_commit,
        candidate_base_commit=str(v9.payload["base_commit"]),
        producer_source_dirty=producer_source_dirty,
        producer_source_file_sha256=producer_source_file_sha256,
        stage_k_parent_profile_sha256=_sha256(stage_k_path),
        stage_l_v8_profile_sha256=_sha256(v8_path),
        stage_l_v9_profile_sha256=_sha256(v9_path),
        trace_version="stage-l-round2-canonical-cycle-v1",
        comfort_requested_gain_db=float(comfort_gain_db),
    )
    return build_round2_unqualified_diagnostic_package(
        root,
        produced_artifacts=produced,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--v8-profile", type=Path, default=DEFAULT_V8_PROFILE)
    parser.add_argument("--v9-profile", type=Path, default=DEFAULT_V9_PROFILE)
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--comfort-gain-db", type=float, default=1.0)
    args = parser.parse_args(argv)
    result = build_production_stage_l_round2_review(
        args.output_root,
        v8_profile_path=args.v8_profile,
        v9_profile_path=args.v9_profile,
        duration_s=args.duration_s,
        comfort_gain_db=args.comfort_gain_db,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
