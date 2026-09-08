"""One-command local Stage AG validation orchestrator.

This script performs only deterministic diagnostics and immutable package creation.
It never tunes parameters and it stops before Human acceptance.  Real local IR and
existing governed Reference bytes must be supplied by the caller/environment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..stage_af.package_integrity import sha256_file
from .analyze_vehicle_identity import analyze_identity
from .build_blind_identity_package import build_blind_package
from .build_identity_dashboards import build_identity_package
from .render_identity_probe import render_probe
from .vehicle_identity import IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_validation(
    *,
    output_root: Path,
    mapping_root: Path,
    run_id: str,
    reference_root: Path | None,
    seed: int,
    numerical_fixes: tuple[str, ...],
    legacy_port_base: int,
    identity_port_base: int,
) -> Path:
    run_root = output_root / run_id
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True, exist_ok=False)

    probe_root = run_root / "probe"
    probe_manifest = render_probe(
        probe_root,
        seed=seed,
        numerical_fixes=numerical_fixes,
    )
    scorecard_path = analyze_identity(
        probe_root,
        run_root / "identity_separation_scorecard.json",
        reference_root=reference_root,
        seed=seed,
        numerical_fixes=numerical_fixes,
    )
    scorecard = _load(scorecard_path)
    regressions = int(
        scorecard.get("summary", {}).get("reference_regressions_gt_3pct", 0)
    )
    if reference_root is not None and regressions:
        raise RuntimeError(
            "Stage AG identity increases at least one governed Reference distance "
            ">3%; stop before immutable package promotion and review scorecard"
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
    legacy = build_identity_package(
        argparse.Namespace(
            **common,
            identity_mode=IDENTITY_MODE_LEGACY,
            package_id=f"{run_id}-legacy",
            candidate_id="stage-ag-legacy-anchor",
            port_base=legacy_port_base,
        )
    )
    identity = build_identity_package(
        argparse.Namespace(
            **common,
            identity_mode=IDENTITY_MODE_V1,
            package_id=f"{run_id}-identity-v1",
            candidate_id="stage-ag-vehicle-identity-v1",
            port_base=identity_port_base,
        )
    )

    legacy_manifest = _load(legacy / "audition_manifest.json")
    identity_manifest = _load(identity / "audition_manifest.json")
    legacy_by_vehicle = {
        row["vehicle"]: row for row in legacy_manifest.get("vehicles", [])
    }
    identity_by_vehicle = {
        row["vehicle"]: row for row in identity_manifest.get("vehicles", [])
    }

    hellcat_legacy = legacy_by_vehicle["hellcat"]["candidate_pcm_sha256"]
    hellcat_identity = identity_by_vehicle["hellcat"]["candidate_pcm_sha256"]
    if hellcat_legacy != hellcat_identity:
        raise RuntimeError("Hellcat identity_v1 drifted from the protected legacy anchor")

    for vehicle in ("ferrari_458", "lfa", "gtr_r35"):
        left = legacy_by_vehicle[vehicle]["candidate_pcm_sha256"]
        right = identity_by_vehicle[vehicle]["candidate_pcm_sha256"]
        if left == right:
            raise RuntimeError(f"{vehicle} identity_v1 did not change any candidate PCM")
        if legacy_by_vehicle[vehicle].get("reference_sha256") != identity_by_vehicle[vehicle].get(
            "reference_sha256"
        ):
            raise RuntimeError(f"{vehicle} legacy/identity Reference bytes differ")

    blind_root = run_root / "blind_identity"
    mapping_output = mapping_root / f"{run_id}-blind-identity-mapping.json"
    # The render/probe seed remains deterministic, but the official blind label
    # mapping must not be derivable from that public seed.  Omit the blind seed
    # so build_blind_package uses a system-random mapping.
    blind_manifest = build_blind_package(
        identity,
        blind_root,
        mapping_output,
        seed=None,
    )

    summary = {
        "schema": "s12.stage_ag.local_validation_summary.v1",
        "status": "STAGE_AG_IDENTITY_CANDIDATES_READY",
        "human_status": "WAITING_FOR_JOVI_BLIND_IDENTITY_FEEDBACK",
        "run_id": run_id,
        "seed": seed,
        "numerical_fixes": list(numerical_fixes),
        "reference_root": str(reference_root.resolve()) if reference_root else None,
        "probe_manifest": str(probe_manifest),
        "probe_manifest_sha256": sha256_file(probe_manifest),
        "scorecard": str(scorecard_path),
        "scorecard_sha256": sha256_file(scorecard_path),
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
        "rules": [
            "do not reveal blind mapping before Jovi feedback",
            "do not fit or freeze profiles automatically",
            "do not promote R3/AUDITION_ONLY evidence to R1/OEM",
        ],
    }
    summary_path = run_root / "stage_ag_validation_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Stage AG probe -> scorecard -> immutable packages -> blind gate"
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--mapping-root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    parser.add_argument("--legacy-port-base", type=int, default=23080)
    parser.add_argument("--identity-port-base", type=int, default=23180)
    args = parser.parse_args(argv)
    result = run_validation(
        output_root=args.output_root,
        mapping_root=args.mapping_root,
        run_id=args.run_id,
        reference_root=args.reference_root,
        seed=args.seed,
        numerical_fixes=tuple(args.numerical_fixes),
        legacy_port_base=args.legacy_port_base,
        identity_port_base=args.identity_port_base,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
