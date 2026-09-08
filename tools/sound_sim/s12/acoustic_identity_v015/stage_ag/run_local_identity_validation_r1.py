"""One-command Stage AG-R1 local Reference-remediation validation.

R1 is allowed to continue past the old v1 blocker only when BOTH conditions hold:

1. no explicitly supplied governed Reference scene regresses by more than 3%;
2. mean matched-state cross-vehicle separation does not fall below legacy.

If either condition fails, package/blind publication stops.  The guard threshold
is not relaxed and no automatic parameter fitting occurs.

The runner also supports ``--resume-after-package``.  This is deliberately narrow:
it resumes only after a gate-passed run has already published the immutable legacy
and R1 packages but failed before blind-package/final-summary publication.  It does
not re-render or silently bypass any gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..stage_af.package_integrity import canonical_json_bytes, sha256_file
from .analyze_vehicle_identity_r1 import analyze_identity_r1
from .build_blind_identity_package import build_blind_package
from .build_identity_dashboards_r1 import build_identity_package_r1
from .render_identity_probe_r1 import render_probe_r1
from .vehicle_identity import IDENTITY_MODE_LEGACY
from .vehicle_identity_r1 import IDENTITY_MODE_V1R1


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_package_manifest(path: Path, expected_mode: str) -> dict:
    payload = _load(path)
    if payload.get("schema") != "s12.stage_ag.package_manifest.v1":
        raise ValueError(f"unsupported Stage AG package manifest: {path}")
    if payload.get("identity_mode") != expected_mode:
        raise ValueError(
            f"unexpected package identity mode for {path}: {payload.get('identity_mode')}"
        )
    recorded = str(payload.get("manifest_sha256", ""))
    canonical = dict(payload)
    canonical.pop("manifest_sha256", None)
    calculated = hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()
    if not recorded or recorded != calculated:
        raise ValueError(f"Stage AG package manifest checksum mismatch: {path}")
    return payload


def _verify_package_pair(legacy: Path, identity: Path) -> tuple[dict, dict]:
    legacy_manifest = _validate_package_manifest(
        legacy / "audition_manifest.json", IDENTITY_MODE_LEGACY
    )
    identity_manifest = _validate_package_manifest(
        identity / "audition_manifest.json", IDENTITY_MODE_V1R1
    )
    legacy_by_vehicle = {
        row["vehicle"]: row for row in legacy_manifest.get("vehicles", [])
    }
    identity_by_vehicle = {
        row["vehicle"]: row for row in identity_manifest.get("vehicles", [])
    }
    expected = {"hellcat", "ferrari_458", "lfa", "gtr_r35"}
    if set(legacy_by_vehicle) != expected or set(identity_by_vehicle) != expected:
        raise RuntimeError("Stage AG-R1 package pair must contain exactly four vehicles")

    if (
        legacy_by_vehicle["hellcat"]["candidate_pcm_sha256"]
        != identity_by_vehicle["hellcat"]["candidate_pcm_sha256"]
    ):
        raise RuntimeError("Hellcat R1 drifted from the protected legacy anchor")

    for vehicle in ("ferrari_458", "lfa", "gtr_r35"):
        if (
            legacy_by_vehicle[vehicle]["candidate_pcm_sha256"]
            == identity_by_vehicle[vehicle]["candidate_pcm_sha256"]
        ):
            raise RuntimeError(f"{vehicle} R1 did not change any candidate PCM")
        if legacy_by_vehicle[vehicle].get("reference_sha256") != identity_by_vehicle[
            vehicle
        ].get("reference_sha256"):
            raise RuntimeError(f"{vehicle} legacy/R1 Reference bytes differ")
    return legacy_manifest, identity_manifest


def _publish_blind_and_summary(
    *,
    run_root: Path,
    mapping_root: Path,
    run_id: str,
    reference_root: Path | None,
    seed: int,
    numerical_fixes: tuple[str, ...],
    probe_manifest: Path,
    scorecard_path: Path,
    gate_path: Path,
    legacy: Path,
    identity: Path,
    regressions: int,
    separation_nonnegative: bool,
) -> Path:
    _verify_package_pair(legacy, identity)

    blind_root = run_root / "blind_identity"
    mapping_output = mapping_root / f"{run_id}-blind-identity-mapping.json"
    if blind_root.exists():
        raise FileExistsError(
            f"blind output already exists; refusing overwrite during resume: {blind_root}"
        )
    if mapping_output.exists():
        raise FileExistsError(
            f"sealed mapping already exists; refusing overwrite during resume: {mapping_output}"
        )

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
    if summary_path.exists():
        raise FileExistsError(f"summary already exists; refusing overwrite: {summary_path}")
    summary_path.write_text(
        json.dumps(final, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary_path


def resume_after_package_r1(
    *,
    output_root: Path,
    mapping_root: Path,
    run_id: str,
    reference_root: Path | None,
) -> Path:
    """Resume a gate-passed R1 run from already-published immutable packages."""
    run_root = output_root / run_id
    if not run_root.is_dir():
        raise FileNotFoundError(run_root)

    probe_manifest = run_root / "probe" / "identity_probe_manifest.json"
    scorecard_path = run_root / "identity_separation_scorecard_r1.json"
    gate_path = run_root / "stage_ag_r1_gate_receipt.json"
    for required in (probe_manifest, scorecard_path, gate_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    scorecard = _load(scorecard_path)
    score_summary = scorecard.get("summary", {})
    regressions = int(score_summary.get("reference_regressions_gt_3pct", -1))
    separation_nonnegative = bool(score_summary.get("separation_nonnegative", False))
    gate = _load(gate_path)
    if gate.get("schema") != "s12.stage_ag.r1_gate_receipt.v1":
        raise ValueError("unsupported Stage AG-R1 gate receipt")
    if int(gate.get("reference_regressions_gt_3pct", -1)) != regressions:
        raise ValueError("R1 gate receipt/scorecard regression count mismatch")
    if bool(gate.get("separation_nonnegative", False)) != separation_nonnegative:
        raise ValueError("R1 gate receipt/scorecard separation status mismatch")
    if str(gate.get("scorecard_sha256", "")) != sha256_file(scorecard_path):
        raise ValueError("R1 gate receipt scorecard SHA mismatch")
    if regressions != 0:
        raise RuntimeError("cannot resume: R1 Reference gate is not green")
    if not separation_nonnegative:
        raise RuntimeError("cannot resume: R1 separation gate is not green")

    seed = int(scorecard.get("seed", 20260908))
    numerical_fixes = tuple(scorecard.get("numerical_fixes", []))
    package_root = run_root / "packages"
    legacy = package_root / f"{run_id}-legacy"
    identity = package_root / f"{run_id}-identity-v1r1"
    if not legacy.is_dir() or not identity.is_dir():
        raise FileNotFoundError("R1 immutable package pair is incomplete")

    return _publish_blind_and_summary(
        run_root=run_root,
        mapping_root=mapping_root,
        run_id=run_id,
        reference_root=reference_root,
        seed=seed,
        numerical_fixes=numerical_fixes,
        probe_manifest=probe_manifest,
        scorecard_path=scorecard_path,
        gate_path=gate_path,
        legacy=legacy,
        identity=identity,
        regressions=regressions,
        separation_nonnegative=separation_nonnegative,
    )


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
            sha256_file(parent_scorecard)
            if parent_scorecard and parent_scorecard.is_file()
            else None
        ),
    }
    gate_path = run_root / "stage_ag_r1_gate_receipt.json"
    gate_path.write_text(
        json.dumps(blocker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

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

    return _publish_blind_and_summary(
        run_root=run_root,
        mapping_root=mapping_root,
        run_id=run_id,
        reference_root=reference_root,
        seed=seed,
        numerical_fixes=numerical_fixes,
        probe_manifest=probe_manifest,
        scorecard_path=scorecard_path,
        gate_path=gate_path,
        legacy=legacy,
        identity=identity,
        regressions=regressions,
        separation_nonnegative=separation_nonnegative,
    )


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
    parser.add_argument(
        "--resume-after-package",
        action="store_true",
        help=(
            "resume only from an existing gate-passed run with both immutable packages; "
            "creates blind package + final summary without re-rendering"
        ),
    )
    args = parser.parse_args(argv)
    if args.resume_after_package:
        result = resume_after_package_r1(
            output_root=args.output_root,
            mapping_root=args.mapping_root,
            run_id=args.run_id,
            reference_root=args.reference_root,
        )
    else:
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
