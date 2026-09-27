"""Uncalibrated, original synthetic profiles used only for the APP-1 MVP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REFERENCE_SOURCE = Path(__file__).with_name("reference_runtime.py")
FEATURES = [
    "speed_acceleration_mapping",
    "virtual_gear_shift",
    "phase_continuous_orders",
    "acceleration_transient",
    "soft_limiter",
]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_builtin_profiles() -> list[dict]:
    source_hash = hashlib.sha256(REFERENCE_SOURCE.read_bytes()).hexdigest()
    definitions = (
        {
            "profile_id": "experimental-v8-synth",
            "display_name": "Experimental V8 Synth",
            "engine_topology": "synthetic_v8",
            "state_mapping": {
                "idle_rpm": 850.0, "max_rpm": 6500.0,
                "rpm_per_mps_by_gear": [220.0, 135.0, 95.0, 72.0],
                "acceleration_rpm_per_mps2": 60.0, "upshift_rpm": 5600.0,
                "downshift_rpm": 1700.0, "shift_rpm_drop": 0.70,
                "idle_load": 0.12, "positive_acceleration_load_per_mps2": 0.14,
                "negative_acceleration_load_per_mps2": 0.04,
            },
            "orders": [
                {"order": 4.0, "amplitude": 0.68, "phase_rad": 0.0},
                {"order": 8.0, "amplitude": 0.24, "phase_rad": 0.15},
                {"order": 12.0, "amplitude": 0.08, "phase_rad": -0.2},
            ],
            "transient": {
                "gain": 0.12, "acceleration_reference_mps2": 4.0,
                "attack_s": 0.035, "release_s": 0.14,
                "shift_impulse": 0.35, "carrier_order": 1.5,
            },
            "output_policy": {
                "sample_rate_hz": 48000, "channels": 2, "format": "float32le",
                "gain": 0.42, "peak_limit": 0.92,
            },
        },
        {
            "profile_id": "experimental-rotary-synth",
            "display_name": "Experimental Rotary Synth",
            "engine_topology": "synthetic_rotary",
            "state_mapping": {
                "idle_rpm": 950.0, "max_rpm": 9000.0,
                "rpm_per_mps_by_gear": [300.0, 180.0, 125.0, 90.0],
                "acceleration_rpm_per_mps2": 75.0, "upshift_rpm": 8200.0,
                "downshift_rpm": 2400.0, "shift_rpm_drop": 0.76,
                "idle_load": 0.10, "positive_acceleration_load_per_mps2": 0.13,
                "negative_acceleration_load_per_mps2": 0.035,
            },
            "orders": [
                {"order": 6.0, "amplitude": 0.66, "phase_rad": 0.0},
                {"order": 12.0, "amplitude": 0.25, "phase_rad": -0.12},
                {"order": 18.0, "amplitude": 0.09, "phase_rad": 0.22},
            ],
            "transient": {
                "gain": 0.10, "acceleration_reference_mps2": 4.0,
                "attack_s": 0.025, "release_s": 0.12,
                "shift_impulse": 0.30, "carrier_order": 1.8,
            },
            "output_policy": {
                "sample_rate_hz": 48000, "channels": 2, "format": "float32le",
                "gain": 0.40, "peak_limit": 0.92,
            },
        },
    )
    profiles = []
    for definition in definitions:
        body = {
            "schema_version": "s12.vehicle-profile.v1",
            **definition,
            "version": "1.0.0",
            "supported_features": FEATURES.copy(),
            "provenance": {
                "kind": "synthetic",
                "source_id": "app1-original-synth-v1",
                "rights": "original_synthetic",
            },
            "qualification": "EXPERIMENTAL_NOT_QUALIFIED",
        }
        profile_hash = hashlib.sha256(_canonical_bytes(body)).hexdigest()
        profiles.append({
            **body,
            "hashes": {"profile_sha256": profile_hash, "source_sha256": source_hash},
        })
    return profiles
