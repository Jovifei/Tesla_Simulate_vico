"""Publish anonymous 60-second Stage-D baseline/candidate preference pairs."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _write_pcm24_wav
from ..render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _render_stateful
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..stage_d.candidate_profiles import load_stage_d_candidate
from ..stage_d.render_candidate import render_stage_d_candidate
from ..stage_d.blind_audition import _zip_tree

_VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
_CANDIDATE_FILES = {
    "ferrari_458": "Ferrari_candidate_v1.json",
    "hellcat": "Hellcat_candidate_v1.json",
    "rx7_fd": "RX7_candidate_v1.json",
}


def publish_pairs(output_root: Path, candidate_root: Path, seed: int = 20260809) -> dict[str, object]:
    output_root = output_root.resolve()
    listener_pairs = output_root / "listener" / "qualitative_full_cycle_pairs"
    sealed = output_root / "sealed"
    source_root = output_root / "source_evidence" / "full_cycle"
    for path in (listener_pairs, sealed, source_root):
        path.mkdir(parents=True, exist_ok=True)
    generator = np.random.Generator(np.random.PCG64(seed))
    pair_key: dict[str, object] = {"package_id": "S12_Blind_Audition_Package_v1", "seed": seed, "pairs": {}}
    for index, vehicle_id in enumerate(_VEHICLES, start=1):
        trace = build_drive_cycle_trace(vehicle_id, duration_s=60.0)
        baseline = _render_and_ptr(vehicle_id, trace, None)
        candidate = _render_and_ptr(vehicle_id, trace, load_stage_d_candidate(candidate_root / _CANDIDATE_FILES[vehicle_id]))
        base_lufs = float(measure_loudness(baseline).integrated_lufs)
        candidate_lufs = float(measure_loudness(candidate).integrated_lufs)
        target = min(-20.0, base_lufs, candidate_lufs)
        base_gain = min(0.0, target - base_lufs)
        candidate_gain = min(0.0, target - candidate_lufs)
        baseline *= 10.0 ** (base_gain / 20.0)
        candidate *= 10.0 ** (candidate_gain / 20.0)
        source_vehicle = source_root / vehicle_id
        source_vehicle.mkdir(parents=True, exist_ok=True)
        base_path = _write_pcm24_wav(source_vehicle / "baseline.wav", baseline)
        candidate_path = _write_pcm24_wav(source_vehicle / "candidate.wav", candidate)
        if bool(generator.integers(0, 2)):
            first, second, first_role, second_role = baseline, candidate, "baseline", "candidate"
        else:
            first, second, first_role, second_role = candidate, baseline, "candidate", "baseline"
        a_path = _write_pcm24_wav(listener_pairs / f"P{index:02d}_A.wav", first)
        b_path = _write_pcm24_wav(listener_pairs / f"P{index:02d}_B.wav", second)
        pair_key["pairs"][f"P{index:02d}"] = {
            "vehicle_id": vehicle_id,
            "a_role": first_role,
            "b_role": second_role,
            "baseline_source_sha256": _sha256(base_path),
            "candidate_source_sha256": _sha256(candidate_path),
            "a_sha256": _sha256(a_path),
            "b_sha256": _sha256(b_path),
            "common_target_lufs": target,
        }
    (listener_pairs / "README.md").write_text(
        "These three anonymous pairs are for qualitative A/B preference only. "
        "Choose A or B after listening; do not infer a vehicle label from the filename.\n",
        encoding="utf-8",
    )
    key_path = sealed / "full_cycle_pair_key.json"
    key_path.write_text(json.dumps(pair_key, ensure_ascii=False, indent=2), encoding="utf-8")
    _zip_tree(output_root / "S12_Stage_D_Listener_Package.zip", output_root / "listener", "listener")
    _zip_tree(output_root / "S12_Stage_D_Answer_Key.zip", output_root / "sealed", "sealed")
    return {"pair_count": len(pair_key["pairs"]), "key_sha256": _sha256(key_path), "seed": seed}


def _render_and_ptr(vehicle_id: str, trace: object, candidate: object) -> np.ndarray:
    if candidate is None:
        rendered = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    else:
        rendered = render_stage_d_candidate(vehicle_id, trace, candidate)
    pressure = rendered.pressure
    # SourceRender retains every named stem; release that graph before the
    # frozen PTR allocates its working buffers for a 60-second cycle.
    del rendered
    gc.collect()
    result = _edge_fade(_apply_frozen_ptr(pressure))
    del pressure
    gc.collect()
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260809)
    args = parser.parse_args()
    print(json.dumps(publish_pairs(args.output_root, args.candidate_root, args.seed), indent=2))


if __name__ == "__main__":
    main()
