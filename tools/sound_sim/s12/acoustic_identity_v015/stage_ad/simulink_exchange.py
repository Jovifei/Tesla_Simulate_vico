"""JSON exchange helpers for the optional Stage-AD Simulink diagnostic mirror."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SIMULINK_REQUEST_SCHEMA = "s12.stage_ad.simulink_request.v1"


def write_simulink_request(
    path: str | Path,
    *,
    iteration: int,
    scene: str,
    parameter_overrides: dict[str, float],
    profile_id: str = "hellcat_v1",
    reference_id: str | None = None,
) -> dict[str, Any]:
    """Write one deterministic request consumed by the MATLAB bridge."""
    payload = {
        "schema": SIMULINK_REQUEST_SCHEMA,
        "iteration": int(iteration),
        "scene": str(scene),
        "profile_id": str(profile_id),
        "parameter_overrides": {name: float(value) for name, value in sorted(parameter_overrides.items())},
        "reference_id": reference_id,
        "sample_rate_hz": 48000,
        "frame_period_s": 0.02,
        "samples_per_frame": 960,
        "authority": "Python S12 authoritative; Simulink diagnostic mirror",
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


__all__ = ["SIMULINK_REQUEST_SCHEMA", "write_simulink_request"]
