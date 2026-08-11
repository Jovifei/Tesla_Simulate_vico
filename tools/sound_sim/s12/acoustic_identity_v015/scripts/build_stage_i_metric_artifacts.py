"""Build the five formal Stage-I metric artifacts from qualified candidates."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import gc
import json
from pathlib import Path
import sys

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.contracts import (
    SourceRender,
    VehicleStateTrace,
)
from tools.sound_sim.s12.acoustic_identity_v015.loudness_manager import (
    manage_bundle_loudness,
)
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import (
    _apply_frozen_ptr,
    _edge_fade,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_d.scenarios import (
    build_stage_d_scenario_trace,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles import (
    StageICandidateProfile,
    load_stage_i_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.metric_artifacts import (
    write_stage_i_metric_artifacts,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.probes import (
    candidate_profile_binding,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.render_candidate import (
    render_stage_i_candidate,
)


_IDS = ("I6-A Balanced", "I6-B Whine Forward", "I6-C Softer Mechanical")
TraceBuilder = Callable[[], VehicleStateTrace]
Renderer = Callable[[VehicleStateTrace, StageICandidateProfile], SourceRender]
AudioTransform = Callable[[np.ndarray], np.ndarray]


def run_stage_i_metric_artifacts(
    candidate_profile_paths: Mapping[str, str | Path],
    qualification_json_path: str | Path,
    output_root: str | Path,
    *,
    trace_builder: TraceBuilder | None = None,
    renderer: Renderer | None = None,
    ptr_transform: AudioTransform = _apply_frozen_ptr,
    edge_transform: AudioTransform = _edge_fade,
) -> dict[str, object]:
    """Sequentially render A/B/C and write exactly five metric artifacts."""
    if set(candidate_profile_paths) != set(_IDS):
        raise ValueError("candidate_profile_paths must contain exact Stage-I A/B/C labels")
    qualification_path = Path(qualification_json_path).resolve()
    if not qualification_path.is_file():
        raise ValueError(f"qualification JSON does not exist: {qualification_path}")
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    if not isinstance(qualification, Mapping) or qualification.get("schema_version") != "s12-stage-i-manifest-qualification-1":
        raise ValueError("qualification JSON schema is invalid")
    candidates = qualification.get("candidates")
    baseline = qualification.get("stage_h_baseline_metrics")
    if not isinstance(candidates, Mapping) or set(candidates) != set(_IDS) or not isinstance(baseline, Mapping):
        raise ValueError("qualification JSON lacks exact candidates or Stage-H baseline")
    profiles = {label: load_stage_i_candidate(candidate_profile_paths[label]) for label in _IDS}
    metrics: dict[str, Mapping[str, object]] = {}
    for label in _IDS:
        entry = candidates[label]
        if not isinstance(entry, Mapping) or not isinstance(entry.get("metrics"), Mapping):
            raise ValueError(f"qualification candidate metrics are missing for {label!r}")
        binding = entry.get("binding")
        expected_binding = candidate_profile_binding(profiles[label])
        if not isinstance(binding, Mapping) or any(binding.get(key) != value for key, value in expected_binding.items()):
            raise ValueError(f"qualification candidate/profile binding mismatch for {label!r}")
        metrics[label] = entry["metrics"]  # type: ignore[assignment]

    trace = (trace_builder or _default_trace)().validate()
    render_one = renderer or _default_renderer
    minimal_renders: dict[str, SourceRender] = {}
    pre_loudness_pcm: dict[str, np.ndarray] = {}
    live_full = 0
    max_live_full = 0
    for label in _IDS:
        full = render_one(trace, profiles[label]).validate()
        live_full += 1
        max_live_full = max(max_live_full, live_full)
        required_stems = {}
        for stem_name in ("blower", "exhaust"):
            if stem_name not in full.stems:
                raise ValueError(f"full render for {label!r} lacks required stem {stem_name!r}")
            required_stems[stem_name] = np.asarray(full.stems[stem_name], dtype=np.float64)
        minimal_renders[label] = SourceRender(
            pressure=np.asarray(full.pressure, dtype=np.float64),
            stems=required_stems,
            diagnostics={"stage_i_candidate_id": profiles[label].candidate_id, "minimal_metric_render": True},
        ).validate()
        pre_loudness_pcm[label] = np.asarray(edge_transform(ptr_transform(full.pressure)), dtype=np.float64)
        del full
        live_full -= 1
        gc.collect()
    managed = manage_bundle_loudness(
        pre_loudness_pcm,
        48000,
        target_lufs=-16.0,
        peak_limit_dbfs=-1.5,
    )
    artifacts = write_stage_i_metric_artifacts(
        Path(output_root).resolve(),
        managed.segments,
        minimal_renders,
        trace,
        metrics,
        baseline,
        48000,
    )
    return {
        "schema_version": "s12-stage-i-metric-artifact-run-1",
        "trace_duration_s": float(trace.time_s[-1] - trace.time_s[0]),
        "common_fixed_gain_db": float(managed.gain_db),
        "max_live_full_render": max_live_full,
        "artifacts": artifacts,
    }


def _default_trace() -> VehicleStateTrace:
    return build_stage_d_scenario_trace("hellcat", "acceleration", 8.0)


def _default_renderer(trace: VehicleStateTrace, profile: StageICandidateProfile) -> SourceRender:
    return render_stage_i_candidate("hellcat", trace, profile)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-a", required=True)
    parser.add_argument("--candidate-b", required=True)
    parser.add_argument("--candidate-c", required=True)
    parser.add_argument("--qualification-json", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    result = run_stage_i_metric_artifacts(
        {_IDS[0]: args.candidate_a, _IDS[1]: args.candidate_b, _IDS[2]: args.candidate_c},
        args.qualification_json,
        args.output_root,
    )
    print(json.dumps({**result, "artifacts": {key: str(value) for key, value in result["artifacts"].items()}}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main", "run_stage_i_metric_artifacts")
