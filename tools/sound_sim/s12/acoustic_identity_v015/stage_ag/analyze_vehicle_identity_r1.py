"""Analyze Stage AG-R1 separation and governed Reference direction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import analyze_vehicle_identity as _base
from .vehicle_identity_r1 import IDENTITY_MODE_V1R1, VehicleIdentityR1Engine


def analyze_identity_r1(
    probe_root: Path,
    output_path: Path,
    *,
    reference_root: Path | None = None,
    seed: int = 20260908,
    numerical_fixes: tuple[str, ...] = (),
) -> Path:
    saved = (_base.IDENTITY_MODE_V1, _base.VehicleIdentityEngine)
    _base.IDENTITY_MODE_V1 = IDENTITY_MODE_V1R1
    _base.VehicleIdentityEngine = VehicleIdentityR1Engine
    try:
        result = _base.analyze_identity(
            probe_root,
            output_path,
            reference_root=reference_root,
            seed=seed,
            numerical_fixes=numerical_fixes,
        )
    finally:
        _base.IDENTITY_MODE_V1, _base.VehicleIdentityEngine = saved

    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["schema"] = "s12.stage_ag.identity_separation_scorecard.v1r1"
    payload["candidate_identity_mode"] = IDENTITY_MODE_V1R1
    payload["remediation_policy"] = {
        "reference_guard_fraction": 0.03,
        "guard_unchanged": True,
        "parent_candidate": "vehicle_identity_v1",
        "root_cause": (
            "v1 restored each identity track to a fixed peak after state attenuation; "
            "R1 keeps absolute state amplitude and uses redline-relative RPM"
        ),
    }
    summary = payload.setdefault("summary", {})
    mean_legacy = float(summary.get("mean_pairwise_legacy_distance", 0.0))
    mean_identity = float(summary.get("mean_pairwise_identity_distance", 0.0))
    summary["separation_nonnegative"] = mean_identity + 1e-12 >= mean_legacy
    result.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Stage AG-R1 vehicle identity")
    parser.add_argument("--probe-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    args = parser.parse_args(argv)
    result = analyze_identity_r1(
        args.probe_root,
        args.output,
        reference_root=args.reference_root,
        seed=args.seed,
        numerical_fixes=tuple(args.numerical_fixes),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
