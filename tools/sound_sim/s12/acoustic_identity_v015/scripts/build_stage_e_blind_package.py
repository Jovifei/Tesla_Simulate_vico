"""Render Stage-C/Stage-E anonymous source evidence and package it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..loudness_manager import manage_bundle_loudness
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _write_pcm24_wav
from ..render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _render_stateful
from ..stage_d.scenarios import SCENES, build_stage_d_scenario_trace
from ..stage_e.blind_audition import build_stage_e_blind_package
from ..stage_e.candidate_profiles import load_stage_e_candidate
from ..stage_e.render_candidate import render_stage_e_candidate


def publish_sources(output_root: Path, candidate_root: Path) -> Path:
    source_root = output_root / "source_evidence"
    source_root.mkdir(parents=True, exist_ok=False)
    trials = []
    names = {"ferrari_458": "Ferrari_candidate_v2.json", "hellcat": "Hellcat_candidate_v2.json", "rx7_fd": "RX7_candidate_v2.json"}
    for role in ("baseline", "candidate"):
        role_root = source_root / role; role_root.mkdir()
        for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
            clips = {}
            profile = load_stage_e_candidate(candidate_root / names[vehicle_id]) if role == "candidate" else None
            for scene in SCENES:
                trace = build_stage_d_scenario_trace(vehicle_id, scene)
                rendered = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace) if profile is None else render_stage_e_candidate(vehicle_id, trace, profile)
                clips[scene] = _edge_fade(_apply_frozen_ptr(rendered.pressure))
            managed = manage_bundle_loudness(clips, _SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=-1.5)
            vehicle_root = role_root / vehicle_id; vehicle_root.mkdir()
            for scene in SCENES:
                path = vehicle_root / f"{scene}.wav"; _write_pcm24_wav(path, managed.segments[scene])
                trials.append({"role": role, "vehicle_id": vehicle_id, "scene_id": scene, "wav": str(path.relative_to(source_root))})
    manifest = source_root / "source_manifest.json"
    manifest.write_text(json.dumps({"schema_version": "s12-stage-e-source-manifest-1", "trials": trials}, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, default=Path(__file__).resolve().parents[1] / "targets/stage_e_candidates")
    parser.add_argument("--seed", type=int, default=20260809)
    args = parser.parse_args()
    if args.output_root.exists() and any(args.output_root.iterdir()): raise SystemExit("output root must be empty")
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest = publish_sources(args.output_root, args.candidate_root)
    summary = build_stage_e_blind_package(args.output_root / "source_evidence", manifest, args.output_root, seed=args.seed)
    (args.output_root / "build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__": main()
