"""Outer-gate contract for MATLAB, MoSQITo and human finalist evidence.

The inner Python proxy search is deliberately fast.  This module prevents it
from being confused with a professional acceptance gate by requiring explicit,
SHA-bound receipts from the external tools before a finalist may advance to a
human audition.  It never creates a Profile Freeze on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

VALIDATION_SCHEMA = "s12.stage_y.professional_finalist_validation.v1"
REQUIRED_PSYCHOACOUSTIC_METRICS = (
    "loudness",
    "sharpness",
    "roughness",
    "fluctuation_strength",
    "tonality",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(float(value))


def load_bound_receipt(path: str | Path, expected_sha256: str | None = None) -> dict[str, Any]:
    """Load JSON and optionally verify its external SHA binding."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = _sha(source)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"receipt SHA mismatch: {source}")
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("tool receipt must be a JSON object")
    payload = dict(payload)
    payload["_receipt_path"] = str(source)
    payload["_receipt_sha256"] = digest
    return payload


def validate_psychoacoustic_receipt(receipt: Mapping[str, Any], *, tool: str) -> list[str]:
    """Validate a MATLAB or MoSQITo candidate/reference comparison receipt."""
    errors: list[str] = []
    if receipt.get("tool") != tool:
        errors.append(f"tool must be {tool}")
    if receipt.get("fixture") is True:
        errors.append("fixture receipt cannot qualify a real finalist")
    if receipt.get("candidate_sha256") in {None, ""} or receipt.get("reference_sha256") in {None, ""}:
        errors.append("candidate/reference SHA bindings are required")
    metrics = receipt.get("metrics")
    if not isinstance(metrics, Mapping):
        return errors + ["metrics object is required"]
    for name in REQUIRED_PSYCHOACOUSTIC_METRICS:
        record = metrics.get(name)
        if not isinstance(record, Mapping):
            errors.append(f"metric missing: {name}")
            continue
        for field in ("reference", "candidate", "absolute_error"):
            if not _finite_number(record.get(field)):
                errors.append(f"{name}.{field} must be finite")
    return errors


def validate_order_receipt(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    status = receipt.get("order_metric_status")
    if status not in {"QUALIFIED_WITH_SYNCHRONIZED_RPM", "NOT_QUALIFIED_NO_RPM_TRACE"}:
        errors.append("unknown order metric status")
    if status == "QUALIFIED_WITH_SYNCHRONIZED_RPM":
        if receipt.get("fixture") is True:
            errors.append("fixture order receipt cannot qualify a real finalist")
        if receipt.get("rpm_trace_sha256") in {None, ""}:
            errors.append("synchronized RPM trace SHA is required")
        ridges = receipt.get("order_ridges")
        if not isinstance(ridges, Sequence) or not ridges:
            errors.append("qualified order receipt requires order ridges")
        else:
            for index, ridge in enumerate(ridges):
                if not isinstance(ridge, Mapping) or not all(_finite_number(ridge.get(key)) for key in ("order", "reference_db", "candidate_db", "absolute_error_db")):
                    errors.append(f"invalid order ridge {index}")
    return errors


def _metric_error(receipt: Mapping[str, Any]) -> float:
    metrics = receipt.get("metrics") or {}
    errors = [float(record["absolute_error"]) for record in metrics.values() if isinstance(record, Mapping) and _finite_number(record.get("absolute_error"))]
    return float(np.median(errors)) if errors else float("inf")


def _order_error(receipt: Mapping[str, Any]) -> float | None:
    if receipt.get("order_metric_status") != "QUALIFIED_WITH_SYNCHRONIZED_RPM":
        return None
    ridges = receipt.get("order_ridges") or []
    values = [float(record["absolute_error_db"]) for record in ridges if isinstance(record, Mapping) and _finite_number(record.get("absolute_error_db"))]
    return float(np.median(values)) if values else None


@dataclass(frozen=True)
class FinalistEvidence:
    candidate_id: str
    candidate_sha256: str
    inner_objective: float
    matlab_receipt: Mapping[str, Any]
    mosqito_receipt: Mapping[str, Any]
    order_receipt: Mapping[str, Any]
    human_feedback: Mapping[str, Any] | None = None


def evaluate_finalists(
    finalists: Sequence[FinalistEvidence],
    *,
    maximum_psychoacoustic_median_error: float,
    maximum_order_median_error_db: float = 3.0,
    require_order_for_formal: bool = True,
) -> dict[str, Any]:
    """Rank external-tool finalists and fail closed on missing evidence."""
    if not finalists:
        raise ValueError("at least one finalist is required")
    if not np.isfinite(maximum_psychoacoustic_median_error) or maximum_psychoacoustic_median_error <= 0.0:
        raise ValueError("maximum_psychoacoustic_median_error must be positive")
    records: list[dict[str, Any]] = []
    for finalist in finalists:
        errors = []
        errors += validate_psychoacoustic_receipt(finalist.matlab_receipt, tool="MATLAB_R2026a")
        errors += validate_psychoacoustic_receipt(finalist.mosqito_receipt, tool="MoSQITo_1.2.1")
        errors += validate_order_receipt(finalist.order_receipt)
        sha_values = {
            finalist.candidate_sha256,
            str(finalist.matlab_receipt.get("candidate_sha256", "")),
            str(finalist.mosqito_receipt.get("candidate_sha256", "")),
            str(finalist.order_receipt.get("candidate_sha256", finalist.candidate_sha256)),
        }
        if len(sha_values) != 1:
            errors.append("candidate SHA differs across finalist receipts")
        matlab_error = _metric_error(finalist.matlab_receipt)
        mosqito_error = _metric_error(finalist.mosqito_receipt)
        psycho_error = float(np.median([matlab_error, mosqito_error]))
        order_error = _order_error(finalist.order_receipt)
        order_qualified = order_error is not None
        psycho_pass = bool(np.isfinite(psycho_error) and psycho_error <= maximum_psychoacoustic_median_error)
        order_pass = bool(order_qualified and order_error <= maximum_order_median_error_db)
        human_complete = bool(finalist.human_feedback and finalist.human_feedback.get("complete") is True)
        eligible_for_human_review = not errors and psycho_pass and (order_pass or not require_order_for_formal)
        score = (
            float(finalist.inner_objective)
            - 0.25 * psycho_error
            - (0.04 * order_error if order_error is not None else 0.20 if require_order_for_formal else 0.0)
        )
        records.append(
            {
                "candidate_id": finalist.candidate_id,
                "candidate_sha256": finalist.candidate_sha256,
                "inner_objective": float(finalist.inner_objective),
                "psychoacoustic_median_error": psycho_error,
                "order_median_error_db": order_error,
                "order_qualified": order_qualified,
                "psychoacoustic_gate_passed": psycho_pass,
                "order_gate_passed": order_pass,
                "eligible_for_human_review": eligible_for_human_review,
                "human_feedback_complete": human_complete,
                "profile_freeze_ready": False,
                "errors": errors,
                "ranking_score": score,
            }
        )
    ranking = sorted(records, key=lambda record: (record["eligible_for_human_review"], record["ranking_score"]), reverse=True)
    preferred = ranking[0]["candidate_id"] if ranking[0]["eligible_for_human_review"] else None
    return {
        "schema": VALIDATION_SCHEMA,
        "candidate_count": len(records),
        "records": records,
        "ranking": [record["candidate_id"] for record in ranking],
        "preferred_for_human_review": preferred,
        "formal_selection": None,
        "profile_freeze_ready": False,
        "required_next_gate": "hash-bound blinded human review, followed by R1 formal selection",
        "scope": "professional finalist evidence gate; not an OEM similarity percentage",
    }


__all__ = [
    "FinalistEvidence",
    "REQUIRED_PSYCHOACOUSTIC_METRICS",
    "VALIDATION_SCHEMA",
    "evaluate_finalists",
    "load_bound_receipt",
    "validate_order_receipt",
    "validate_psychoacoustic_receipt",
]
