"""Read only existing package/reference receipts for Stage-M attribution."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


def load_reference_target_segments(reference_database: Path) -> dict[str, dict[str, dict[str, object]]]:
    """Load relative B/R2 summaries; this function never opens the referenced audio."""

    result: dict[str, dict[str, dict[str, object]]] = {}
    for path in sorted(reference_database.glob("*_reference_targets.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        vehicle_id = str(payload["vehicle"])
        source = next((item for item in payload.get("sources", []) if item.get("include_in_stock_target") is True), None)
        segments = source.get("segments", {}) if isinstance(source, dict) else {}
        result[vehicle_id] = {
            str(name): {
                "source_id": source.get("id") if isinstance(source, dict) else None,
                "provenance": payload.get("provenance"),
                "note": payload.get("note"),
                **value,
            }
            for name, value in segments.items()
            if isinstance(value, dict)
        }
    return result


def _load_stage_k_manifest(root: Path, metrics: dict[str, dict[str, object]], statuses: dict[str, str]) -> None:
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    archive = next(root.glob("*.zip"))
    with zipfile.ZipFile(archive) as package:
        for vehicle_id, record in manifest["vehicles"].items():
            metric_path = str(record["metrics_json"]).replace("\\", "/")
            payload = json.loads(package.read(metric_path))
            metrics[vehicle_id] = dict(payload.get("metrics", {}))
            statuses[vehicle_id] = str(payload.get("status", manifest.get("status", "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY")))


def _load_stage_l_hellcat(root: Path, metrics: dict[str, dict[str, object]], statuses: dict[str, str]) -> None:
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", {})
    metric_path = next((path for path in artifacts if path.endswith("round2_metrics.json")), None)
    if metric_path is None:
        metrics["hellcat"] = {}
    else:
        payload = json.loads((root / metric_path).read_text(encoding="utf-8"))
        metrics["hellcat"] = dict(payload.get("metrics", payload))
    statuses["hellcat"] = str(manifest.get("status", "PARTIAL / AUTOMATED_GATE_FAIL"))


def load_round2_evidence(stage_k_three: Path, stage_k_remaining: Path, stage_l_hellcat: Path) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    metrics: dict[str, dict[str, object]] = {}
    statuses: dict[str, str] = {}
    _load_stage_k_manifest(stage_k_three, metrics, statuses)
    _load_stage_k_manifest(stage_k_remaining, metrics, statuses)
    _load_stage_l_hellcat(stage_l_hellcat, metrics, statuses)
    return metrics, statuses
