"""Fail-closed binding for legacy numbered listening feedback.

Stage-G pair numbers were anonymous.  Text such as "the second sound" is not
enough to identify a vehicle and must remain unbound until Jovi supplies a
file_id from a named engineering package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


UNBOUND = "UNBOUND"
BOUND_EXPLICIT_FILE_ID = "BOUND_EXPLICIT_FILE_ID"


@dataclass(frozen=True)
class FeedbackBinding:
    feedback_id: str
    raw_feedback: str
    file_id: str | None
    vehicle_id: str | None
    binding_status: str
    modification_authorized: bool


def bind_numbered_feedback(
    entries: Iterable[Mapping[str, object]],
    *,
    file_catalog: Mapping[str, str],
) -> tuple[FeedbackBinding, ...]:
    """Bind feedback only when an explicit named-package file_id is present."""
    normalized_catalog = {
        _required_text(file_id, "file_catalog file_id"): _required_text(vehicle_id, "vehicle_id")
        for file_id, vehicle_id in file_catalog.items()
    }
    results: list[FeedbackBinding] = []
    seen: set[str] = set()
    for entry in entries:
        feedback_id = _required_text(entry.get("feedback_id"), "feedback_id")
        if feedback_id in seen:
            raise ValueError(f"duplicate feedback_id: {feedback_id}")
        seen.add(feedback_id)
        raw_feedback = _required_text(entry.get("raw_feedback"), "raw_feedback")
        raw_file_id = entry.get("file_id")
        file_id = str(raw_file_id).strip() if raw_file_id is not None else ""
        if not file_id:
            results.append(
                FeedbackBinding(
                    feedback_id=feedback_id,
                    raw_feedback=raw_feedback,
                    file_id=None,
                    vehicle_id=None,
                    binding_status=UNBOUND,
                    modification_authorized=False,
                )
            )
            continue
        if file_id not in normalized_catalog:
            raise ValueError(f"unknown explicit file_id: {file_id}")
        results.append(
            FeedbackBinding(
                feedback_id=feedback_id,
                raw_feedback=raw_feedback,
                file_id=file_id,
                vehicle_id=normalized_catalog[file_id],
                binding_status=BOUND_EXPLICIT_FILE_ID,
                modification_authorized=True,
            )
        )
    return tuple(results)


def _required_text(value: object, field: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ValueError(f"{field} must be non-empty")
    return text


__all__ = (
    "BOUND_EXPLICIT_FILE_ID",
    "FeedbackBinding",
    "UNBOUND",
    "bind_numbered_feedback",
)
