"""Render Stage AG-R1 legacy-vs-reference-remediated identity probes."""
from __future__ import annotations

import json
from pathlib import Path

from . import render_identity_probe as _base
from .vehicle_identity import IDENTITY_MODE_LEGACY
from .vehicle_identity_r1 import (
    IDENTITY_MODE_V1R1,
    VehicleIdentityR1Engine,
    vehicle_identity_r1_signature,
)

VEHICLES = _base.VEHICLES
DEFAULT_SCENES = _base.DEFAULT_SCENES


def render_probe_r1(
    output_root: Path,
    *,
    vehicles: tuple[str, ...] = VEHICLES,
    scenes: tuple[str, ...] = DEFAULT_SCENES,
    seed: int = 20260908,
    numerical_fixes: tuple[str, ...] = (),
) -> Path:
    saved = (
        _base.IDENTITY_MODE_V1,
        _base.VehicleIdentityEngine,
        _base.vehicle_identity_signature,
    )
    _base.IDENTITY_MODE_V1 = IDENTITY_MODE_V1R1
    _base.VehicleIdentityEngine = VehicleIdentityR1Engine
    _base.vehicle_identity_signature = vehicle_identity_r1_signature
    try:
        manifest_path = _base.render_probe(
            output_root,
            vehicles=vehicles,
            scenes=scenes,
            seed=seed,
            numerical_fixes=numerical_fixes,
        )
    finally:
        (
            _base.IDENTITY_MODE_V1,
            _base.VehicleIdentityEngine,
            _base.vehicle_identity_signature,
        ) = saved

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["candidate_identity_mode"] = IDENTITY_MODE_V1R1
    payload["remediation_lineage"] = {
        "parent": "vehicle_identity_v1",
        "reason": "REFERENCE_REGRESSION_AND_PER_TRACK_PEAK_RECOVERY",
        "status": "DIAGNOSTIC_ONLY_WAITING_FOR_REFERENCE_RECHECK",
    }
    payload["rules"] = [
        "legacy is the existing EngineAcoustics baseline",
        "Hellcat vehicle_identity_v1r1 must remain byte-identical to legacy",
        "R1 removes per-track identity peak recovery and uses redline-relative state",
        "non-Hellcat R1 remains a diagnostic candidate until Reference and Human gates pass",
        "no Reference audio is downloaded or inferred by this tool",
    ]
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main(argv=None) -> int:
    parser = _base.argparse.ArgumentParser(
        description="Render Stage AG-R1 reference-remediated identity probes"
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--vehicle", choices=["all", *VEHICLES], default="all")
    parser.add_argument("--scenes", nargs="+", choices=DEFAULT_SCENES, default=list(DEFAULT_SCENES))
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    args = parser.parse_args(argv)
    vehicles = VEHICLES if args.vehicle == "all" else (args.vehicle,)
    result = render_probe_r1(
        args.output_root,
        vehicles=tuple(vehicles),
        scenes=tuple(args.scenes),
        seed=args.seed,
        numerical_fixes=tuple(args.numerical_fixes),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
