"""Qualify frozen Stage-I named sources without retaining full renders."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles import (
    StageICandidateProfile,
    load_stage_i_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.probes import (
    build_stage_i_response_probe,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.qualification import (
    qualify_stage_i_source_manifest,
)


_LABELS = ("I6-A Balanced", "I6-B Whine Forward", "I6-C Softer Mechanical")
ProbeBuilder = Callable[[str, StageICandidateProfile], Mapping[str, object]]


def run_stage_i_named_source_qualification(
    source_manifest_path: str | Path,
    candidate_profile_paths: Mapping[str, str | Path],
    reference_summary_path: str | Path,
    output_path: str | Path,
    *,
    track_p_guard_pass: bool,
    regression_isolation_pass: bool,
    probe_builder: ProbeBuilder = build_stage_i_response_probe,
) -> dict[str, object]:
    """Load immutable inputs, build short probes, and run manifest qualification."""
    if set(candidate_profile_paths) != set(_LABELS):
        raise ValueError("candidate_profile_paths must contain exact Stage-I A/B/C labels")
    profiles = {
        label: load_stage_i_candidate(candidate_profile_paths[label])
        for label in _LABELS
    }
    probes = {
        label: probe_builder(label, profiles[label])
        for label in _LABELS
    }
    reference_path = Path(reference_summary_path).resolve()
    if not reference_path.is_file():
        raise ValueError(f"reference summary does not exist: {reference_path}")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if not isinstance(reference, Mapping):
        raise ValueError("reference summary root must be an object")
    result = qualify_stage_i_source_manifest(
        source_manifest_path,
        profiles,
        probes,
        reference,
        track_p_guard_pass=track_p_guard_pass,
        regression_isolation_pass=regression_isolation_pass,
    )
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--candidate-a", required=True)
    parser.add_argument("--candidate-b", required=True)
    parser.add_argument("--candidate-c", required=True)
    parser.add_argument("--reference-summary", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--track-p-guard-pass", action="store_true")
    parser.add_argument("--regression-isolation-pass", action="store_true")
    args = parser.parse_args(argv)
    run_stage_i_named_source_qualification(
        args.source_manifest,
        {
            _LABELS[0]: args.candidate_a,
            _LABELS[1]: args.candidate_b,
            _LABELS[2]: args.candidate_c,
        },
        args.reference_summary,
        args.output,
        track_p_guard_pass=args.track_p_guard_pass,
        regression_isolation_pass=args.regression_isolation_pass,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main", "run_stage_i_named_source_qualification")
