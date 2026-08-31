"""Hard gates for the professional Dashboard and Jovi feedback export."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


class DashboardContractError(ValueError):
    """Raised when Dashboard data cannot safely be presented or submitted."""


def validate_dashboard_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    pairs = payload.get("pairs")
    if payload.get("schema_version") != "s12-professional-pair-metrics-v1" or not isinstance(pairs, list) or len(pairs) != 9:
        raise DashboardContractError("Dashboard requires exactly 9 professional pairs")
    seen: set[str] = set()
    vehicles: Counter[str] = Counter()
    for pair in pairs:
        if not isinstance(pair, Mapping):
            raise DashboardContractError("Dashboard pair is malformed")
        pair_id = str(pair.get("pair_id") or "")
        if not pair_id or pair_id in seen:
            raise DashboardContractError("Dashboard pair_id is missing or duplicated")
        seen.add(pair_id)
        file_id = str(pair.get("file_id") or "")
        if file_id != f"{pair_id}-reference-vs-candidate":
            raise DashboardContractError(f"Dashboard file_id mismatch: {pair_id}")
        vehicles[str(pair.get("vehicle_id") or "")] += 1
        integrity = pair.get("integrity")
        if not isinstance(integrity, Mapping) or integrity.get("required_files") is not True:
            raise DashboardContractError(f"required files gate failed: {pair_id}")
        for side in ("reference", "candidate"):
            evidence = integrity.get(side)
            if not isinstance(evidence, Mapping) or evidence.get("sha_status") != "MATCH":
                raise DashboardContractError(f"SHA gate failed: {pair_id}/{side}")
            duration = evidence.get("duration_s")
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise DashboardContractError(f"duration gate failed: {pair_id}/{side}")
        if (pair.get("order") or {}).get("status") != "ORDER_COMPARISON_NOT_QUALIFIED":
            raise DashboardContractError(f"Order gate must remain not qualified: {pair_id}")
    if any(count != 3 for count in vehicles.values()) or set(vehicles) != {"ferrari_458", "hellcat", "rx7_fd"}:
        raise DashboardContractError(f"Dashboard anchor coverage is wrong: {dict(vehicles)}")
    if isinstance(payload.get("total_similarity_percent"), (int, float)):
        raise DashboardContractError("Dashboard must not contain a total similarity percentage")
    return {
        "status": "PASS",
        "pair_count": len(pairs),
        "vehicle_counts": dict(sorted(vehicles.items())),
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "submit_gate": "AUDIO_CANPLAYTHROUGH_DURATION_SHA_REQUIRED",
    }


__all__ = ["DashboardContractError", "validate_dashboard_payload"]
