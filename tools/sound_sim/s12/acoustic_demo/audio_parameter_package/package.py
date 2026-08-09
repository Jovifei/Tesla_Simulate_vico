"""Build JSON-only AudioParameterPackage v0.1 contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re

from frozen_ptr_contract import verify_frozen_radiation_package


def _hash_without_self(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("hash", None)
    return hashlib.sha256(
        json.dumps(copy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _require_commit(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("source commit must be a full lowercase Git SHA-1")
    return value


def build_audio_parameter_package(library, renderer_profile: dict, source_commit: str) -> dict:
    _require_commit(source_commit)
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
        "ptr_profile": verify_frozen_radiation_package(),
        "renderer_profile": dict(renderer_profile),
        "source_commit": source_commit,
        "synthetic": True,
        "provenance": {
            "source_level": "C",
            "source": "synthetic",
            "description": "Portable classification for a synthetic operating-point and renderer package; no OEM or vehicle measurement data.",
        },
    }
    package["hash"] = _hash_without_self(package)
    return package


def validate_audio_parameter_package(package: dict) -> None:
    required = {
        "version",
        "engine_id",
        "rpm_range",
        "load_range",
        "excitation_profile",
        "ptr_profile",
        "renderer_profile",
        "hash",
        "source_commit",
        "synthetic",
        "provenance",
    }
    if set(package) != required or package["version"] != "AudioParameterPackage v0.1":
        raise ValueError("invalid AudioParameterPackage schema")
    if (
        package["synthetic"] is not True
        or not isinstance(package["engine_id"], str)
        or not package["engine_id"]
    ):
        raise ValueError("AudioParameterPackage synthetic/source commit contract failed")
    _require_commit(package["source_commit"])
    if not isinstance(package["hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", package["hash"]):
        raise ValueError("AudioParameterPackage hash format is invalid")
    if not all(
        isinstance(value, list)
        and len(value) == 2
        and all(_finite_number(item) for item in value)
        and value[0] <= value[1]
        for value in (package["rpm_range"], package["load_range"])
    ):
        raise ValueError("AudioParameterPackage ranges are invalid")
    excitation = package["excitation_profile"]
    ptr = package["ptr_profile"]
    renderer = package["renderer_profile"]
    provenance = package["provenance"]
    if (
        set(excitation) != {"interpolation", "operating_point_library_hash", "synthetic"}
        or excitation["interpolation"] != "bilinear"
        or excitation["synthetic"] is not True
        or not isinstance(excitation["operating_point_library_hash"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", excitation["operating_point_library_hash"])
    ):
        raise ValueError("AudioParameterPackage excitation profile is invalid")
    if (
        set(ptr)
        != {"configuration", "frozen_math", "radiation_package_sha256", "radiation_source_commit"}
        or not isinstance(ptr["configuration"], str)
        or not ptr["configuration"]
        or ptr["frozen_math"] is not True
        or not isinstance(ptr["radiation_package_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", ptr["radiation_package_sha256"])
        or not isinstance(ptr["radiation_source_commit"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", ptr["radiation_source_commit"])
    ):
        raise ValueError("AudioParameterPackage PTR profile is invalid")
    if (
        set(renderer) != {"sample_rate_hz", "gain_db", "edge_fade_s"}
        or not isinstance(renderer["sample_rate_hz"], int)
        or isinstance(renderer["sample_rate_hz"], bool)
        or renderer["sample_rate_hz"] <= 0
        or not _finite_number(renderer["gain_db"])
        or not _finite_number(renderer["edge_fade_s"])
        or renderer["edge_fade_s"] < 0.0
    ):
        raise ValueError("AudioParameterPackage renderer profile is invalid")
    if (
        set(provenance) != {"source_level", "source", "description"}
        or provenance["source_level"] != "C"
        or provenance["source"] != "synthetic"
        or not isinstance(provenance["description"], str)
        or not provenance["description"]
    ):
        raise ValueError("AudioParameterPackage provenance is invalid")
    if package["hash"] != _hash_without_self(package):
        raise ValueError("AudioParameterPackage hash mismatch")
    json.dumps(package, sort_keys=True, allow_nan=False)
