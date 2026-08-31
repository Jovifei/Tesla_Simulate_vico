"""Validate, but do not silently install, official-source ViSQOL invocations."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping


def validate_visqol_request(request: Mapping[str, object]) -> dict[str, object]:
    """Return an auditable allow/block decision for an internal regression pair.

    ViSQOL is a full-reference quality metric, not a synthetic-to-real identity
    metric.  The adapter accepts only a locally built official checkout and an
    identical vehicle/scenario/state-trace/role pair.
    """

    checkout = Path(str(request.get("checkout", "")))
    binary = Path(str(request.get("binary", "")))
    reasons: list[str] = []
    if not (checkout / ".git").exists() or not (checkout / "WORKSPACE").is_file():
        reasons.append("official_google_visqol_checkout_required")
    if not binary.is_file() or "pypi" in str(binary).lower():
        reasons.append("official_local_build_binary_required")
    commit = request.get("commit")
    source_sha = str(request.get("source_sha256", ""))
    if not isinstance(commit, str) or not commit.strip() or len(source_sha) != 64:
        reasons.append("commit_and_source_sha256_required")
    reference = request.get("reference")
    degraded = request.get("degraded")
    if not isinstance(reference, Mapping) or not isinstance(degraded, Mapping):
        reasons.append("reference_and_degraded_scope_required")
    else:
        for field in ("vehicle_id", "scenario", "state_trace_sha256", "role"):
            if reference.get(field) != degraded.get(field):
                reasons.append(f"{field}_must_match")
        if reference.get("role") not in {"synthetic", "internal_regression"}:
            reasons.append("only_internal_synthetic_regression_is_in_scope")
    return {
        "allowed": not reasons,
        "reason": "; ".join(reasons) if reasons else "same vehicle/scenario/state trace internal regression pair",
        "tool": "ViSQOL",
        "status": "ADAPTER_IMPLEMENTED" if reasons else "RESEARCHED_ONLY",
    }
