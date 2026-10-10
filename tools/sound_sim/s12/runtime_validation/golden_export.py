"""Build compact, deterministic Python golden receipts for the APP-1 subset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Iterator

from contracts import validate_motion_sample, validate_vehicle_profile
from profiles import load_builtin_profiles
from reference_runtime import CONTROL_RATE_HZ, FRAMES_PER_UPDATE, SAMPLE_RATE_HZ, SyntheticEngine


SCENARIOS = ("idle", "cruise", "acceleration", "lift_coast", "shift")
TRACE_SECONDS = 2
BASE_TIME_NS = 1_000_000_000
SAMPLE_PERIOD_NS = 1_000_000_000 // CONTROL_RATE_HZ
RECEIVE_DELAY_NS = 2_000_000
COMPARISON_TOLERANCES = {
    "virtual_rpm_abs": 0.001,
    "load_abs": 0.000001,
    "pcm_sample_abs": 0.00005,
    "pcm_rms_abs": 0.000005,
    "events": "exact_sequence_and_sample_index",
}


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _motion_samples(scenario: str) -> Iterator[dict[str, Any]]:
    total = TRACE_SECONDS * CONTROL_RATE_HZ
    for sequence in range(total):
        elapsed = sequence / CONTROL_RATE_HZ
        if scenario == "idle":
            speed, acceleration = 0.0, 0.0
        elif scenario == "cruise":
            speed, acceleration = 22.0, 0.1
        elif scenario == "acceleration":
            speed, acceleration = 4.0 + 9.0 * elapsed, 9.0
        elif scenario == "lift_coast":
            speed, acceleration = 32.0 - 8.0 * elapsed, -4.0
        elif scenario == "shift":
            speed, acceleration = 12.0 + 15.0 * elapsed, 15.0
        else:
            raise ValueError(f"unsupported scenario: {scenario}")
        measured = BASE_TIME_NS + sequence * SAMPLE_PERIOD_NS
        yield {
            "schema_version": "s12.motion-sample.v1",
            "source": {"id": "app1-golden-synthetic", "kind": "synthetic"},
            "sequence": sequence,
            "clock_domain": "monotonic",
            "measurement_time_ns": measured,
            "received_time_ns": measured + RECEIVE_DELAY_NS,
            "speed_mps": speed,
            "longitudinal_acceleration_mps2": acceleration,
            "direction": "stationary" if speed == 0.0 else "forward",
            "valid": True,
            "quality": {"score": 1.0, "uncertainty_mps": 0.0},
            "data_age_ms": RECEIVE_DELAY_NS // 1_000_000,
        }


def export_golden_bundle(output_dir: Path, *, source_revision: str, seed: int = 20260924) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = [validate_vehicle_profile(profile) for profile in load_builtin_profiles()]
    cases = []
    for profile in profiles:
        for scenario in SCENARIOS:
            engine = SyntheticEngine(profile, seed)
            previous = None
            motion_bytes = bytearray()
            state_bytes = bytearray()
            pcm_bytes = bytearray()
            for sample in _motion_samples(scenario):
                validate_motion_sample(
                    sample,
                    now_monotonic_ns=sample["received_time_ns"],
                    previous=previous,
                )
                previous = sample
                motion_bytes.extend(_canonical_json(sample))
                state = engine.update_motion(sample)
                state_bytes.extend(_canonical_json(state))
                for mono_sample in engine.render_frames(FRAMES_PER_UPDATE):
                    pcm_bytes.extend(struct.pack("<ff", mono_sample, mono_sample))
            prefix = Path(profile["profile_id"]) / scenario
            artifacts = {
                f"{prefix}.motion.jsonl": bytes(motion_bytes),
                f"{prefix}.state.jsonl": bytes(state_bytes),
                f"{prefix}.pcm.f32le": bytes(pcm_bytes),
            }
            for relative_path, content in artifacts.items():
                path = output_dir / Path(relative_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            cases.append({
                "profile_id": profile["profile_id"],
                "profile_sha256": profile["hashes"]["profile_sha256"],
                "source_sha256": profile["hashes"]["source_sha256"],
                "scenario_id": scenario,
                "motion_sha256": _sha256(bytes(motion_bytes)),
                "state_sha256": _sha256(bytes(state_bytes)),
                "pcm_sha256": _sha256(bytes(pcm_bytes)),
                "motion_samples": TRACE_SECONDS * CONTROL_RATE_HZ,
                "audio_frames": TRACE_SECONDS * SAMPLE_RATE_HZ,
                "shift_events": engine.shift_events,
            })
    manifest = {
        "schema_version": "s12.app1-golden.v1",
        "source_commit": source_revision,
        "seed": seed,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "control_rate_hz": CONTROL_RATE_HZ,
        "frames_per_control_update": FRAMES_PER_UPDATE,
        "comparison_tolerances": COMPARISON_TOLERANCES,
        "qualification": "EXPERIMENTAL_SYNTHETIC_NOT_QUALIFIED",
        "cases": cases,
    }
    (output_dir / "manifest.json").write_bytes(_canonical_json(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--seed", type=int, default=20260924)
    args = parser.parse_args()
    export_golden_bundle(args.output, source_revision=args.source_revision, seed=args.seed)


if __name__ == "__main__":
    main()
