"""Bind the canonical Stage-Q reference database to AA diagnostic review rules."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from ..stage_v.io import write_json


REPO_ROOT = Path(__file__).resolve().parents[5]
REFERENCE_ROOT = Path("tasks/reports/runtime/s12-stage-q-real-reference/reference_database_v2")
MANIFEST = REFERENCE_ROOT / "reference_manifest.json"
EVIDENCE_MATRIX = REFERENCE_ROOT / "reference_evidence_matrix.json"
SCENARIO_SEGMENTS = REFERENCE_ROOT / "scenario_segments.json"
RPM_BINDINGS = REFERENCE_ROOT / "rpm_state_bindings.json"
OUTPUT = Path("tasks/reports/runtime/s12-stage-aa/reference_diagnostic_contract.json")
RECEIPT = Path("tasks/reports/runtime/s12-stage-aa/receipts/aa2-reference-contract.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_reference_diagnostic_contract(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    root = repo_root / REFERENCE_ROOT
    manifest = _load(repo_root / MANIFEST)
    matrix = _load(repo_root / EVIDENCE_MATRIX)
    bindings = _load(repo_root / RPM_BINDINGS)
    recordings = list(manifest.get("recordings", []))
    counts = {level: sum(1 for item in recordings if item.get("evidence", {}).get("level") == level) for level in ("R1", "R2", "R3")}
    hellcat_r2 = []
    for item in recordings:
        evidence = item.get("evidence", {})
        if item.get("vehicle_id") == "hellcat" and evidence.get("level") == "R2":
            hellcat_r2.append({
                "recording_id": item.get("recording_id"),
                "reference_id": item.get("reference_id"),
                "scenario": item.get("scenario"),
                "level": evidence.get("level"),
                "sha256": item.get("sha256"),
                "external_path": item.get("external_path"),
                "use_policy": evidence.get("use_policy"),
                "missing_requirements": item.get("required_missing", []),
            })
    synchronized = [item for item in bindings if item.get("rpm_source") and item.get("trace_sha256") and item.get("status") not in {"MISSING_RPM_STATE", "ESTIMATED_RPM_NOT_QUALIFIED"}]
    return {
        "schema": "s12.stage_aa.reference_diagnostic_contract.v1",
        "status": "DIAGNOSTIC_ONLY",
        "canonical_root": str(REFERENCE_ROOT).replace("\\", "/"),
        "canonical_file_sha256": {name: _sha256(repo_root / path) for name, path in (("reference_manifest.json", MANIFEST), ("reference_evidence_matrix.json", EVIDENCE_MATRIX), ("scenario_segments.json", SCENARIO_SEGMENTS), ("rpm_state_bindings.json", RPM_BINDINGS))},
        "evidence_counts": counts,
        "matrix_overall_r1_ready": bool(matrix.get("overall_r1_ready")),
        "r1_status": "AVAILABLE" if counts["R1"] else "MISSING",
        "hellcat_r2_records": hellcat_r2,
        "synchronized_state_records": len(synchronized),
        "order_gate": "QUALIFIED" if synchronized else "NOT_QUALIFIED",
        "timbre_review": {
            "loudness_matching": True,
            "matching_policy": "shared RMS derivative for relative timbre only; never used as dynamic evidence",
            "allowed_levels": ["R2", "R3"],
            "metrics": ["spectral_envelope", "band_distribution", "roughness", "sharpness", "tonality", "mechanical_texture", "blower_texture"],
        },
        "dynamic_review": {
            "loudness_matching": False,
            "matching_policy": "preserve relative idle-to-WOT and transient level; no per-segment equalization",
            "metrics": ["idle_vs_wot", "tip_in", "shift", "lift", "afterfire", "idle_return"],
        },
        "r2_r3_rules": {
            "r2_can_support": ["spectral", "loudness", "temporal", "psychoacoustic", "human_diagnostic"],
            "r2_cannot_support": ["synchronized_order_gate", "automatic_oem_tuning", "profile_freeze", "r1_claim"],
            "r3_can_support": ["qualitative_timbre_and_human_diagnostic"],
            "r3_cannot_support": ["r2_promotion", "r1_promotion", "automatic_tuning"],
        },
        "external_audio_embedded": False,
        "raw_audio_policy": "external_only_not_in_git",
        "scope": "Hellcat Stage AA diagnostic reference binding; no evidence-level promotion",
    }


def publish_reference_diagnostic_contract(*, main_head: str, tested_head: str, command: list[str] | None = None, log_path: str | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    payload = build_reference_diagnostic_contract(repo_root=repo_root)
    output = repo_root / OUTPUT
    write_json(output, payload)
    ended = datetime.now(timezone.utc)
    receipt = {
        "schema": "s12.stage_aa.reference_contract_receipt.v1",
        "status": "PASS",
        "main_head": main_head,
        "tested_head": tested_head,
        "output_path": str(OUTPUT).replace("\\", "/"),
        "output_sha256": _sha256(output),
        "command": command or [],
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "ended_at_utc": ended.isoformat().replace("+00:00", "Z"),
        "exit_code": 0,
        "log_path": log_path,
        "log_sha256": _sha256(Path(log_path)) if log_path and Path(log_path).is_file() else None,
        "r1_status": payload["r1_status"],
        "order_gate": payload["order_gate"],
        "evidence_counts": payload["evidence_counts"],
    }
    write_json(repo_root / RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_reference_diagnostic_contract(main_head=args.main_head, tested_head=args.tested_head, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_reference_diagnostic_contract", "publish_reference_diagnostic_contract"]
