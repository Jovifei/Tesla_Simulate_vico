"""Versioned input/profile validation for the APP-1 synthetic runtime."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "contracts" / "runtime"
REFERENCE_SOURCE = Path(__file__).with_name("reference_runtime.py")


@lru_cache(maxsize=2)
def _validator(name: str) -> jsonschema.Draft202012Validator:
    path = SCHEMA_ROOT / name
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _require_finite_numbers(value: Any, path: str = "payload") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must contain only finite numbers")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _require_finite_numbers(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_finite_numbers(item, f"{path}[{index}]")


def validate_motion_sample(
    sample: Mapping[str, Any],
    *,
    now_monotonic_ns: int,
    max_age_ms: int = 500,
    previous: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Validate shape and stream semantics before handing a sample to audio code."""
    _require_finite_numbers(sample, "motion sample")
    errors = sorted(_validator("motion-sample-v1.schema.json").iter_errors(sample), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"motion sample schema invalid: {errors[0].message}")
    if sample["valid"] is not True:
        raise ValueError("motion sample valid flag must be true")
    measured = sample["measurement_time_ns"]
    received = sample["received_time_ns"]
    if received < measured or received > now_monotonic_ns:
        raise ValueError("motion sample timestamps are inconsistent with the monotonic clock")
    declared_age_ms = (received - measured) // 1_000_000
    if declared_age_ms != sample["data_age_ms"]:
        raise ValueError("motion sample data_age_ms does not match its timestamps")
    age_ns = now_monotonic_ns - measured
    if age_ns < 0 or age_ns > max_age_ms * 1_000_000:
        raise ValueError("motion sample is stale or from the future")
    if previous is not None and (
        sample["sequence"] <= previous["sequence"]
        or measured <= previous["measurement_time_ns"]
    ):
        raise ValueError("motion sample sequence and timestamps must be strictly monotonic")
    return sample


def validate_vehicle_profile(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate a bounded synthetic profile and both of its immutable hashes."""
    _require_finite_numbers(profile, "vehicle profile")
    errors = sorted(_validator("vehicle-profile-v1.schema.json").iter_errors(profile), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"vehicle profile schema invalid: {errors[0].message}")
    body = {key: value for key, value in profile.items() if key != "hashes"}
    expected_profile_hash = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    expected_source_hash = hashlib.sha256(REFERENCE_SOURCE.read_bytes()).hexdigest()
    if profile["hashes"]["profile_sha256"] != expected_profile_hash:
        raise ValueError("vehicle profile hash does not match its configuration")
    if profile["hashes"]["source_sha256"] != expected_source_hash:
        raise ValueError("vehicle profile source hash does not match the reference runtime")
    return profile
