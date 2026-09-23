"""Read-only AI-8 reference readiness preflight; never grants approval or rights."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ..stage_ah.fourcar_reference_loop import load_plan
from ..stage_ah.c63_package import DEFAULT_REFERENCE_ROOT as C63_ROOT, REFERENCE_SOURCES as C63_SOURCES
from ..stage_ah.supra_package import DEFAULT_REFERENCE_ROOT as SUPRA_ROOT, REFERENCE_SOURCES as SUPRA_SOURCES

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35", "c63_w204", "supra_jza80")
ROOT = Path(__file__).resolve().parents[1]
CATALOGS = {
    "c63_w204": ROOT / "reference_database" / "c63_w204_reference_targets.json",
    "supra_jza80": ROOT / "reference_database" / "supra_jza80_multi_reference_targets_v3.json",
}
GOVERNED = {"c63_w204": (C63_ROOT, C63_SOURCES),
            "supra_jza80": (SUPRA_ROOT, SUPRA_SOURCES)}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _catalog_receipt(path: Path, source_root: Path,
                     source_specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = {"path": str(path), "exists": path.is_file(), "sha256": None,
              "sources": [], "catalog_has_byte_bindings": False,
              "governed_receipt_all_verified": False}
    if not path.is_file():
        return result
    result["sha256"] = _sha(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    catalog_sources = data.get("recordings", data.get("sources", []))
    by_filename = {Path(str(source.get("external_audio_path") or source.get("url", ""))).name: source
                   for source in catalog_sources}
    result["catalog_has_byte_bindings"] = bool(catalog_sources) and all(
        source.get("external_audio_path") and
        (source.get("audio_sha256") or source.get("wav_sha256")) for source in catalog_sources)
    for source_id, spec in source_specs.items():
        audio_path = source_root / spec["filename"]
        catalog_source = by_filename.get(spec["filename"], {})
        exists = audio_path.is_file()
        actual = _sha(audio_path) if exists else None
        governed_sha = str(spec["sha256"]).lower()
        result["sources"].append({
            "id": source_id, "path": str(audio_path), "exists": exists,
            "catalog_member": bool(catalog_source),
            "catalog_declared_sha256": catalog_source.get("audio_sha256") or
                                        catalog_source.get("wav_sha256"),
            "governed_declared_sha256": governed_sha, "actual_sha256": actual,
            "governed_sha256_match": bool(actual and actual == governed_sha),
            "rights_status": catalog_source.get("rights_status", "UNVERIFIED_LOCAL_ASSET"),
        })
    result["governed_receipt_all_verified"] = bool(result["sources"]) and all(
        row["governed_sha256_match"] for row in result["sources"])
    return result


def _base(vehicle: str) -> dict[str, Any]:
    return {"vehicle": vehicle, "search_ready": False, "diagnostic_only": True,
            "splits": {"train": 0, "validation": 0}, "reviewed_comparability": False,
            "rights_verified_for_redistribution": False, "missing_items": [],
            "excluded_reasons": [], "validation_error": None}


def assess_readiness(fourcar_plan: str | Path) -> dict[str, Any]:
    """Return fail-closed readiness for the fixed six-car scope."""
    plan_path = Path(fourcar_plan).resolve()
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    rows = {vehicle: _base(vehicle) for vehicle in VEHICLES}
    for item in raw.get("excluded_sources", []):
        vehicle = item.get("vehicle")
        if vehicle in rows:
            rows[vehicle]["excluded_reasons"].append(item.get("reason", "UNSPECIFIED_EXCLUSION"))
    try:
        _, cases, evidence, _ = load_plan(plan_path)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        message = str(exc)
        affected = {case.get("vehicle") for case in raw.get("cases", [])}
        for vehicle in affected & rows.keys():
            rows[vehicle]["validation_error"] = message
            rows[vehicle]["missing_items"].append("FOURCAR_PLAN_VALIDATION_FAILED")
    else:
        for vehicle, refs in cases.items():
            if vehicle not in rows:
                continue
            splits = {name: sum(ref.split == name for ref in refs)
                      for name in ("train", "validation")}
            rights = [entry.get("rights_status", "UNVERIFIED") for entry in evidence
                      if entry.get("vehicle") == vehicle]
            rows[vehicle].update(search_ready=True, splits=splits,
                                 reviewed_comparability=True,
                                 source_rights_status=sorted(set(rights)))
            if any("UNVERIFIED" in status or status == "MISSING" for status in rights):
                rows[vehicle]["missing_items"].append("REDISTRIBUTION_RIGHTS_UNVERIFIED")
    for vehicle in ("hellcat", "lfa"):
        if not rows[vehicle]["search_ready"]:
            rows[vehicle]["missing_items"].append("APPROVED_SPLIT_NOT_AVAILABLE")
    for vehicle in ("c63_w204", "supra_jza80"):
        receipt = _catalog_receipt(CATALOGS[vehicle], *GOVERNED[vehicle])
        rows[vehicle]["catalog"] = receipt
        rows[vehicle]["missing_items"].append("EXPLICIT_REVIEWED_PLAN_MISSING")
        if not receipt["catalog_has_byte_bindings"]:
            rows[vehicle]["missing_items"].append("CATALOG_BYTE_BINDING_ABSENT")
        if not receipt["governed_receipt_all_verified"]:
            rows[vehicle]["missing_items"].append("GOVERNED_SOURCE_BYTES_MISSING_OR_DRIFTED")
        statuses = {source["rights_status"] for source in receipt["sources"]}
        rows[vehicle]["source_rights_status"] = sorted(statuses)
        if not statuses or any("UNVERIFIED" in status or status == "MISSING" for status in statuses):
            rows[vehicle]["missing_items"].append("REDISTRIBUTION_RIGHTS_UNVERIFIED")
    return {"schema": "s12.stage_ai8.reference_readiness.v1",
            "fourcar_plan": str(plan_path),
            "fourcar_plan_sha256": _sha(plan_path),
            "rights_policy": "UNVERIFIED_RIGHTS_DIAGNOSTIC_ONLY",
            "vehicles": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fourcar-plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    report = assess_readiness(args.fourcar_plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
