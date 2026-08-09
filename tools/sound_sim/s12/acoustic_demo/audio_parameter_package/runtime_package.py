"""JSON-only runtime extension for AudioParameterPackage v0.2."""

from __future__ import annotations

import hashlib
import json
import math

from .package import build_audio_parameter_package, validate_audio_parameter_package


def _hash_without_self(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("hash", None)
    return hashlib.sha256(json.dumps(copy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def build_runtime_audio_parameter_package(library, renderer_profile: dict, source_commit: str) -> dict:
    """Build a portable v0.2 runtime contract from the accepted v0.1 inputs."""
    v01 = build_audio_parameter_package(library, renderer_profile, source_commit)
    package = {key: value for key, value in v01.items() if key not in {"version", "hash"}}
    package["version"] = "AudioParameterPackage v0.2"
    package["runtime_profile"] = {
        "rpm_map": {
            "minimum_rpm": library.rpm_grid[0],
            "maximum_rpm": library.rpm_grid[-1],
            "interpolation": "bilinear_operating_point",
        },
        "load_map": {
            "minimum_load": library.load_grid[0],
            "maximum_load": library.load_grid[-1],
            "smoothing_time_constant_s": 0.050,
        },
        "transition_curve": {
            "kind": "first_order",
            "time_constant_s": 0.250,
        },
        "renderer_config": dict(renderer_profile),
        "pcm": {
            "sample_rate_hz": 48000,
            "block_samples": 960,
            "channels": 2,
            "bits_per_sample": 24,
        },
    }
    package["hash"] = _hash_without_self(package)
    return package


def validate_runtime_audio_parameter_package(package: dict) -> None:
    """Validate the v0.2 extension and its unchanged v0.1 base contract."""
    required = {
        "version", "engine_id", "rpm_range", "load_range", "excitation_profile", "ptr_profile",
        "renderer_profile", "runtime_profile", "hash", "source_commit", "synthetic", "provenance",
    }
    if set(package) != required or package["version"] != "AudioParameterPackage v0.2":
        raise ValueError("invalid AudioParameterPackage v0.2 schema")
    v01 = {key: value for key, value in package.items() if key not in {"runtime_profile", "hash"}}
    v01["version"] = "AudioParameterPackage v0.1"
    v01["hash"] = _hash_without_self(v01)
    validate_audio_parameter_package(v01)
    profile = package["runtime_profile"]
    if set(profile) != {"rpm_map", "load_map", "transition_curve", "renderer_config", "pcm"}:
        raise ValueError("runtime profile keys are invalid")
    rpm_map = profile["rpm_map"]
    load_map = profile["load_map"]
    transition = profile["transition_curve"]
    pcm = profile["pcm"]
    if set(rpm_map) != {"minimum_rpm", "maximum_rpm", "interpolation"} or not all(isinstance(rpm_map[key], (int, float)) and not isinstance(rpm_map[key], bool) and math.isfinite(float(rpm_map[key])) for key in ("minimum_rpm", "maximum_rpm")) or rpm_map["minimum_rpm"] > rpm_map["maximum_rpm"] or rpm_map["interpolation"] != "bilinear_operating_point":
        raise ValueError("runtime RPM map is invalid")
    if set(load_map) != {"minimum_load", "maximum_load", "smoothing_time_constant_s"} or not all(isinstance(load_map[key], (int, float)) and not isinstance(load_map[key], bool) and math.isfinite(float(load_map[key])) for key in load_map) or not 0.0 <= load_map["minimum_load"] <= load_map["maximum_load"] <= 1.0 or load_map["smoothing_time_constant_s"] <= 0.0:
        raise ValueError("runtime load map is invalid")
    if transition != {"kind": "first_order", "time_constant_s": 0.250}:
        raise ValueError("runtime transition curve is invalid")
    if profile["renderer_config"] != package["renderer_profile"]:
        raise ValueError("runtime renderer configuration must match renderer profile")
    if pcm != {"sample_rate_hz": 48000, "block_samples": 960, "channels": 2, "bits_per_sample": 24}:
        raise ValueError("runtime PCM contract is invalid")
    if not isinstance(package["hash"], str) or package["hash"] != _hash_without_self(package):
        raise ValueError("AudioParameterPackage v0.2 hash mismatch")
    json.dumps(package, sort_keys=True, allow_nan=False)
