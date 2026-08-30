"""Compatibility helper for Stage Y file-writing paths.

`stage_v.io.write_json` is intentionally treated as a side-effect-only helper.
Callers should create and retain the Path before invoking it rather than rely
on a return value.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def write_json_at(writer: Callable[[Path, dict[str, Any]], Any], path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    writer(target, payload)
    return target


__all__ = ["write_json_at"]
