"""Compute Stage-D final-PCM band shares against existing relative targets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _read_pcm24_wav
from ..stage_d.reference_distance import band_distance, summarize_reference_distance

VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
STATES = ("idle", "acceleration", "afterfire")
BANDS_HZ = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
SAMPLE_RATE_HZ = 48000


def compute_package_distance(package_root: Path, reference_root: Path) -> dict[str, object]:
    reference_manifest = json.loads((reference_root / "realism_reference_manifest.json").read_text(encoding="utf-8"))
    result: dict[str, object] = {"schema_version": "s12-stage-d-reference-distance-1", "audio_domain": "final_pcm_after_fixed_vehicle_gain", "bands_hz": BANDS_HZ, "vehicles": {}}
    for vehicle_id in VEHICLES:
        manifest_entry = reference_manifest["vehicles"][vehicle_id]
        target_path = reference_root / manifest_entry["target_file"]
        target_payload = json.loads(target_path.read_text(encoding="utf-8"))
        vehicle_result: dict[str, object] = {"target_file": manifest_entry["target_file"], "target_sha256": _sha256(target_path), "states": {}, "eligible_states": list(manifest_entry["eligible_states"])}
        stage_c_distances: dict[str, float] = {}
        candidate_distances: dict[str, float] = {}
        for state in STATES:
            target_key = f"{state}_band_shares"
            target = target_payload["stock_median"].get(target_key)
            if target is None:
                vehicle_result["states"][state] = {"availability": "not_available"}
                continue
            state_result: dict[str, object] = {"availability": "eligible", "target": target, "actual": {}}
            for role in ("baseline", "candidate"):
                wav_path = package_root / "source_evidence" / role / vehicle_id / ("lift.wav" if state == "afterfire" else f"{state}.wav")
                audio = _read_pcm24_wav(wav_path)
                actual = _band_shares(audio)
                state_result["actual"][role] = {"band_shares": actual, "loudness": {"integrated_lufs": measure_loudness(audio).integrated_lufs}}
                distance = band_distance(actual, target)
                state_result[f"{role}_distance"] = distance
                if role == "baseline":
                    stage_c_distances[state] = distance
                else:
                    candidate_distances[state] = distance
            state_result["improvement_ratio"] = (stage_c_distances[state] - candidate_distances[state]) / max(stage_c_distances[state], 1e-12)
            vehicle_result["states"][state] = state_result
        vehicle_result["summary"] = summarize_reference_distance(stage_c_distances, candidate_distances)
        result["vehicles"][vehicle_id] = vehicle_result
    return result


def _band_shares(audio: np.ndarray) -> list[float]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    spectrum = np.abs(np.fft.rfft(mono)) ** 2
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / SAMPLE_RATE_HZ)
    energy = np.asarray([float(np.sum(spectrum[(frequencies >= low) & (frequencies < high)])) for low, high in BANDS_HZ])
    total = float(np.sum(energy))
    if total <= 0.0 or not np.isfinite(total):
        raise ValueError("PCM has no finite band energy")
    return (energy / total).tolist()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--reference-root", default=Path(__file__).resolve().parents[1] / "reference_database", type=Path)
    args = parser.parse_args()
    result = compute_package_distance(args.package_root, args.reference_root)
    output = args.package_root / "reference_distance" / "stage_d_reference_distance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
