"""Render Stage-D baseline/candidates and publish a sealed blind package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..acoustic_layers.realism_profiles import SUPPORTED_REALISM_VEHICLE_IDS
from ..loudness_manager import manage_bundle_loudness
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _write_pcm24_wav
from ..stage_d.blind_audition import build_blind_package
from ..stage_d.candidate_profiles import load_stage_d_candidate
from ..stage_d.render_candidate import render_stage_d_candidate
from ..stage_d.scenarios import SCENES, build_stage_d_scenario_trace
from ..render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _render_stateful


def publish_sources(output_root: Path, candidate_root: Path) -> Path:
    source_root = output_root / "source_evidence"
    source_root.mkdir(parents=True, exist_ok=False)
    manifest_trials: list[dict[str, object]] = []
    for role in ("baseline", "candidate"):
        role_root = source_root / role
        role_root.mkdir()
        for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
            trace_map = {scene: build_stage_d_scenario_trace(vehicle_id, scene) for scene in SCENES}
            ptr_segments = {}
            for scene, trace in trace_map.items():
                if role == "baseline":
                    rendered = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
                else:
                    candidate_path = candidate_root / {"ferrari_458": "Ferrari_candidate_v1.json", "hellcat": "Hellcat_candidate_v1.json", "rx7_fd": "RX7_candidate_v1.json"}[vehicle_id]
                    rendered = render_stage_d_candidate(vehicle_id, trace, load_stage_d_candidate(candidate_path))
                ptr_segments[scene] = _edge_fade(_apply_frozen_ptr(rendered.pressure))
                del rendered
            managed = manage_bundle_loudness(ptr_segments, _SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=-1.5)
            vehicle_root = role_root / vehicle_id
            vehicle_root.mkdir()
            for scene in SCENES:
                wav_path = vehicle_root / f"{scene}.wav"
                _write_pcm24_wav(wav_path, managed.segments[scene])
                manifest_trials.append({"role": role, "vehicle_id": vehicle_id, "scene_id": scene, "wav": str(wav_path.relative_to(source_root))})
    manifest_path = source_root / "source_manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": "s12-stage-d-source-manifest-1", "trials": manifest_trials}, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--candidate-root", default=Path(__file__).resolve().parents[1] / "targets" / "stage_d_candidates", type=Path)
    parser.add_argument("--seed", type=int, default=20260809)
    args = parser.parse_args()
    if args.output_root.exists():
        unexpected = [item.name for item in args.output_root.iterdir() if item.name != "source_evidence"]
        if unexpected:
            raise SystemExit("output root contains an unexpected existing artifact")
    else:
        args.output_root.mkdir(parents=True, exist_ok=False)
    manifest = publish_sources(args.output_root, args.candidate_root)
    summary = build_blind_package(args.output_root / "source_evidence", manifest, args.output_root, seed=args.seed)
    (args.output_root / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
