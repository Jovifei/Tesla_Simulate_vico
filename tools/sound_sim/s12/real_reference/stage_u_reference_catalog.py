"""Deterministic Stage U reference catalog assembled from existing professional receipts."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping


class StageUReferenceCatalogError(ValueError):
    """Raised when a Stage U reference cannot be bound to one trace."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageUReferenceCatalogError(f"cannot read reference source: {path}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("pairs"), list):
        raise StageUReferenceCatalogError(f"reference source has no pairs: {path}")
    return value


def _profile(pair: Mapping[str, Any]) -> str:
    window = pair.get("window")
    if isinstance(window, Mapping):
        return str(window.get("profile") or "")
    return ""


def _record(pair: Mapping[str, Any]) -> dict[str, Any]:
    for field in ("pair_id", "vehicle_id", "scenario", "reference_class", "reference_path", "reference_sha256"):
        if not str(pair.get(field) or ""):
            raise StageUReferenceCatalogError(f"reference pair is missing {field}")
    pair_id = str(pair["pair_id"])
    vehicle_id = str(pair["vehicle_id"])
    scenario = str(pair["scenario"])
    return {
        "reference_id": f"stage_u:{pair_id}:reference",
        "source_pair_id": pair_id,
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "matching_trace_scenario": scenario,
        "candidate_audio_id": f"stage_u_parent:{vehicle_id}:{pair_id}",
        "reference_class": str(pair["reference_class"]),
        "reference_path": str(pair["reference_path"]),
        "reference_sha256": str(pair["reference_sha256"]).lower(),
        "microphone_uncertainty": str(pair.get("microphone_uncertainty") or "UNKNOWN"),
        "manual_contamination_review": "NOT_REVIEWED",
    }


def build_stage_u_reference_catalog(long_metrics_path: Path, rx7_metrics_path: Path) -> list[dict[str, Any]]:
    """Select unique long-window Ferrari/Hellcat and all clean RX-7 R2 references."""

    long_pairs = _json(Path(long_metrics_path))["pairs"]
    rx7_pairs = _json(Path(rx7_metrics_path))["pairs"]
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for pair in long_pairs:
        if not isinstance(pair, Mapping) or str(pair.get("vehicle_id")) not in {"ferrari_458", "hellcat"}:
            continue
        base = str(pair.get("base_trial_id") or str(pair.get("pair_id")).removesuffix("_15s").removesuffix("_30s"))
        grouped[(str(pair["vehicle_id"]), base)].append(pair)
    result: list[dict[str, Any]] = []
    for key in sorted(grouped):
        candidates = grouped[key]
        preferred = next((pair for pair in candidates if _profile(pair) == "15s" or str(pair.get("pair_id", "")).endswith("_15s")), candidates[0])
        result.append(_record(preferred))
    for pair in rx7_pairs:
        if not isinstance(pair, Mapping) or str(pair.get("vehicle_id")) != "rx7_fd":
            continue
        if str(pair.get("reference_class")) != "R2":
            continue
        result.append(_record(pair))
    if not result:
        raise StageUReferenceCatalogError("Stage U reference catalog is empty")
    ids = [str(row["reference_id"]) for row in result]
    if len(ids) != len(set(ids)):
        raise StageUReferenceCatalogError("Stage U reference IDs must be unique")
    return result


__all__ = ["StageUReferenceCatalogError", "build_stage_u_reference_catalog"]
