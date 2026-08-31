"""Schema inventory for the comparator's exchanged evidence records."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_NAMES = (
    "reference_recording", "synthetic_candidate", "vehicle_state_trace", "comparison_case",
    "comparison_result", "parameter_recommendation", "human_feedback",
)


def schema_directory() -> Path:
    return Path(__file__).with_name("schemas")


def load_schema(name: str) -> dict[str, object]:
    if name not in SCHEMA_NAMES:
        raise ValueError(f"unknown Stage-M comparator schema: {name}")
    return json.loads((schema_directory() / f"{name}.schema.json").read_text(encoding="utf-8"))
