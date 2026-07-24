"""Build JSON-only AudioParameterPackage v0.1 contracts."""

from __future__ import annotations

import hashlib
import json


def _hash_without_self(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("hash", None)
    return hashlib.sha256(json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_audio_parameter_package(library, renderer_profile: dict, source_commit: str) -> dict:
    package = {
        "version": "AudioParameterPackage v0.1",
        "engine_id": library.raw["engine_id"]["value"],
        "rpm_range": [library.rpm_grid[0], library.rpm_grid[-1]],
        "load_range": [library.load_grid[0], library.load_grid[-1]],
        "excitation_profile": {
            "interpolation": "bilinear",
            "operating_point_library_hash": library.library_hash,
            "synthetic": True,
        },
        "ptr_profile": {
            "configuration": library.raw["ptr_configuration"]["value"],
            "frozen_math": True,
        },
        "renderer_profile": dict(renderer_profile),
        "source_commit": source_commit,
        "synthetic": True,
    }
    package["hash"] = _hash_without_self(package)
    return package


def validate_audio_parameter_package(package: dict) -> None:
    required = {"version", "engine_id", "rpm_range", "load_range", "excitation_profile", "ptr_profile", "renderer_profile", "hash", "source_commit", "synthetic"}
    if set(package) != required or package["version"] != "AudioParameterPackage v0.1":
        raise ValueError("invalid AudioParameterPackage schema")
    if not package["synthetic"] or not isinstance(package["source_commit"], str) or not package["source_commit"]:
        raise ValueError("AudioParameterPackage synthetic/source commit contract failed")
    if package["hash"] != _hash_without_self(package):
        raise ValueError("AudioParameterPackage hash mismatch")
    json.dumps(package, sort_keys=True)
