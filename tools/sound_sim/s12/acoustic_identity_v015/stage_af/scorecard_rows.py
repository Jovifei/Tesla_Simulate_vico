"""Fail-closed helpers for counting executable ablation rows."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def row_is_executable(row: Mapping[str, object]) -> bool:
    """Return whether one scorecard row carries real OFF/ON execution proof."""
    off = row.get("off_pcm_sha")
    on = row.get("on_pcm_sha")
    call_path = row.get("runtime_call_path")
    return (
        isinstance(off, str)
        and isinstance(on, str)
        and bool(_SHA256.fullmatch(off))
        and bool(_SHA256.fullmatch(on))
        and off.lower() != on.lower()
        and isinstance(call_path, str)
        and bool(call_path.strip())
    )


def executable_row_count(rows: Iterable[Mapping[str, object]]) -> int:
    """Count executable rows from row evidence; never trust aggregate fields."""
    return sum(1 for row in rows if row_is_executable(row))
