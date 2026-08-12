"""Fail-closed feedback contract for the Stage-L named diagnostic package."""

from __future__ import annotations

from typing import Iterable, Mapping


FEEDBACK_FIELDS = (
    "package_id", "listener_id", "file_id", "vehicle_id",
    "supercharger_intake_likeness_1_5", "whine_presence_1_5",
    "whine_naturalness_1_5", "low_frequency_weight_1_5",
    "crossplane_pulse_naturalness_1_5", "roughness_naturalness_1_5",
    "shift_naturalness_1_5", "high_frequency_harshness_1_5",
    "loudness_balance_1_5", "artifact_freedom_1_5", "keep_or_change", "notes",
)
SCORE_FIELDS = tuple(field for field in FEEDBACK_FIELDS if field.endswith("_1_5"))


class FeedbackContractError(ValueError):
    """Raised when submitted Stage-L feedback violates the canonical contract."""


def validate_feedback_rows(rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, str], ...]:
    """Validate submitted feedback rows; score zero is always invalid."""

    validated: list[dict[str, str]] = []
    identities: set[tuple[str, str, str, str]] = set()
    for source in rows:
        if tuple(source.keys()) != FEEDBACK_FIELDS:
            raise FeedbackContractError("feedback columns do not match the canonical contract")
        row = {field: str(source[field]) for field in FEEDBACK_FIELDS}
        for field in ("package_id", "listener_id", "file_id", "vehicle_id"):
            if not row[field].strip():
                raise FeedbackContractError(f"{field} must not be blank")
        identity = tuple(row[field] for field in FEEDBACK_FIELDS[:4])
        if identity in identities:
            raise FeedbackContractError("feedback IDs must be complete and unique")
        identities.add(identity)
        for field in SCORE_FIELDS:
            try:
                score = int(row[field])
            except ValueError as exc:
                raise FeedbackContractError(f"{field} must be an integer from 1-5") from exc
            if str(score) != row[field].strip() or not 1 <= score <= 5:
                raise FeedbackContractError(f"{field} must be an integer from 1-5")
        if row["keep_or_change"] not in {"keep", "change"}:
            raise FeedbackContractError("keep_or_change must be keep or change")
        validated.append(row)
    if not validated:
        raise FeedbackContractError("feedback must contain at least one row")
    return tuple(validated)


__all__ = ("FEEDBACK_FIELDS", "FeedbackContractError", "SCORE_FIELDS", "validate_feedback_rows")
