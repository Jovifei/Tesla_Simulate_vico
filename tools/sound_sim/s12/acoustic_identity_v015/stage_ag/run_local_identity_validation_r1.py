"""One-command Stage AG-R1 local Reference-remediation validation.

R1 is allowed to continue past the old v1 blocker only when BOTH conditions hold:

1. no explicitly supplied governed Reference scene regresses by more than 3%;
2. mean matched-state cross-vehicle separation does not fall below legacy.

If either condition fails, package/blind publication stops.  The guard threshold
is not relaxed and no automatic parameter fitting occurs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_af.package_integrity import sha256_file
from .analyze_vehicle_identity_r1 import analyze_identity_r1
from .build_blind_identity_package import build_blind_package
from .build_identity_dashboards_r1 import build_identity_package_r1
from .render_identity_probe_r1 import render_probe_r1
from .vehicle_identity import IDENTITY_MODE_LEGACY
from .vehicle_identity_r1 import IDENTITY_MODE_V1R1


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_validation_r1(
    *,
    output_root: Path,
    mapping_root: Path,
    run_id: str,
    reference_root: Path | None,
    seed: int,
    numerical_fixes: tuple[str, ...],
    legacy_port_base: int,
    identity_port_base: int,
    parent_scorecard: Path | None = None,
) -> Path:
    run_root = output_root / run_id
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True, exist_ok=False)

    probe_root = run_root / "probe"
    probe_manifest = render_probe_r1(
        probe_root,
        seed=seed,
        numerical_fixes=numerical_fixes,
    )
    scorecard_path = analyze_identity_r1(
        probe_root,
        run_root / "identity_separation_scorecard_r1.json",
        reference_root=reference_root,
        seed=seed,
        numerical_fixes=numerical_fixes,
    )
    scorecard = _load(scorecard_path)
    summary = scorecard.get("summary", {})
    regressions = int(summary.get("reference_regressions_gt_3pct", 0))
    separation_nonnegative = bool(summary.get("separation_nonnegative", False))

    blocker = {
        "schema": "s12.stage_ag.r1_gate_receipt.v1",
        "candidate_identity_mode": IDENTITY_MODE_V1R1,
        "scorecard": str(scorecard_path),
        "scorecard_sha256": sha256_file(scorecard_path),
        "reference_regressions_gt_3pct": regressions,
        "separation_nonnegative": separation_nonnegative,
        "parent_scorecard": str(parent_scorecard.resolve()) if parent_scorecard else None,
        "parent_scorecard_sha256": (
            sha256_file(parent_scorecard) if parent_scorecard and parent_scorecard.is_file() else None
        ),
    }
    gate_path = run_root / "stage_ag_r1_gate_receipt.json"
    gate_path.write_text(json.dumps(blocker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if reference_root is not None and regressions:
        raise RuntimeError(
            "Stage AG-R1 still increases at least one governed Reference distance >3%; "
            "stop before immutable package promotion"
        )
    if not separation_nonnegative:
        raise RuntimeError(
            "Stage AG-R1 removed too much cross-vehicle separation; stop before package promotion"
        )

    package_root = run_root / "packages"
    common = dict(
        output_root=package_root,
        reference_root=reference_root,
        vehicle="all",
        seed=seed,
        numerical_fixes=list(numerical_fixes),
        allow_dirty_dev=False,
        fit_root=None,
    )
    legacy = build_identity_package_r1(
        argparse.Namespace(
            **common,
            identity_mode=IDENTITY_MODE_LEGACY,
            package_id=f"{run_id}-legacy",
            candidate_id="stage-ag-r1-legacy-anchor",
            port_base=legacy_port_base,
        )
    )
    identity = build_identity_package_r1(
        argparse.Namespace(
            **common,
            identity_mode=IDENTITY_MODE_V1R1,
            package_id=f"{run_id}-identity-v1r1",
            candidate_id="stage-ag-vehicle-identity-v1r1",
            port_base=identity_port_base,
        )
    )

    legacy_manifest = _load(legacy / "audition_manifest.json")
    identity_manifest = _load(identity / "audition_manifest.json")
    legacy_by_vehicle = {row["vehicle"]: row for row in legacy_manifest.get("vehicles", [])}
    identity_by_vehicle = {row["vehicle"]: row for row in identity_manifest.get("vehicles", [])}

    if legacy_by_vehicle["hellcat"]["candidate_pcm_sha256"] != identity_by_vehicle["hellcat"]["candidate_pcm_sha256"]:
        raise RuntimeError("Hellcat R1 drifted from the protected legacy anchor")

    for vehicle in ("ferrari_458", "lfa", "gtr_r35"):
        if legacy_by_vehicle[vehicle]["candidate_pcm_sha256"] == identity_by_vehicle[vehicle]["candidate_pcm_sha256"]:
            raise RuntimeError(f"{vehicle} R1 did not change any candidate PCM")
        if legacy_by_vehicle[vehicle].get("reference_sha256") != identity_by_vehicle[vehicle].get("reference_sha256"):
            raise RuntimeError(f"{vehicle} legacy/R1 Reference bytes differ")

    blind_root = run_root / "blind_identity"
    mapping_output = mapping_root / f"{run_id}-blind-identity-mapping.json"
    blind_manifest = build_blind_package(
        identity,
        blind_root,
        mapping_output,
        seed=None,
    )

    final = {
        "schema": "s12.stage_ag.local_validation_summary.v1r1",
        "status": "STAGE_AG_R1_IDENTITY_CANDIDATES_READY",
        "human_status": "WAITING_FOR_JOVI_BLIND_IDENTITY_FEEDBACK",
        "candidate_identity_mode": IDENTITY_MODE_V1R1,
        "run_id": run_id,
        "seed": seed,
        "numerical_fixes": list(numerical_fixes),
        "reference_root": str(reference_root.resolve()) if reference_root else None,
        "probe_manifest": str(probe_manifest),
        "probe_manifest_sha256": sha256_file(probe_manifest),
        "scorecard": str(scorecard_path),
        "scorecard_sha256": sha256_file(scorecard_path),
        "gate_receipt": str(gate_path),
        "gate_receipt_sha256": sha256_file(gate_path),
        "legacy_package": str(legacy),
        "legacy_manifest_sha256": sha256_file(legacy / "audition_manifest.json"),
        "identity_package": str(identity),
        "identity_manifest_sha256": sha256_file(identity / "audition_manifest.json"),
        "blind_package": str(blind_root),
        "blind_manifest": str(blind_manifest),
        "blind_manifest_sha256": sha256_file(blind_manifest),
        "sealed_mapping_path": str(mapping_output),
        "sealed_mapping_sha256": sha256_file(mapping_output),
        "hellcat_anchor_byte_identical": True,
        "reference_regressions_gt_3pct": regressions,
        "separation_nonnegative": separation_nonnegative,
        "rules": [
            "R1 does not relax the 3% governed Reference guard",
            "do not reveal blind mapping before Jovi feedback",
            "do not fit/freeze profiles automatically",
            "do not promote R3/AUDITION_ONLY evidence to R1/OEM",
        ],
    }
    summary_path = run_root / "stage_ag_r1_validation_summary.json"
    summary_path.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Stage AG-R1 probe -> scorecard -> guarded packages -> blind gate"
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--mapping-root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--parent-scorecard", type=Path)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    parser.add_argument("--legacy-port-base", type=int, default=23380)
    parser.add_argument("--identity-port-base", type=int, default=23480)
    args = parser.parse_args(argv)
    result = run_validation_r1(
        output_root=args.output_root,
        mapping_root=args.mapping_root,
        run_id=args.run_id,
        reference_root=args.reference_root,
        seed=args.seed,
        numerical_fixes=tuple(args.numerical_fixes),
        legacy_port_base=args.legacy_port_base,
        identity_port_base=args.identity_port_base,
        parent_scorecard=args.parent_scorecard,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
