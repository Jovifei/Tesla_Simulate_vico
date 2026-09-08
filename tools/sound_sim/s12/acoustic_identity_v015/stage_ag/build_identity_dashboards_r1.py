"""Build immutable Stage AG-R1 audition packages using the proven AG/AF-R path.

This wrapper deliberately reuses the existing Stage-AG package builder rather
than forking a third dashboard/backend.  It temporarily binds the builder to the
R1 renderer/signature/fingerprint and restores all globals before returning.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from ..stage_af.package_integrity import REPOSITORY_ROOT, sha256_file
from . import build_identity_dashboards as _base
from .vehicle_identity import IDENTITY_MODE_LEGACY
from .vehicle_identity_r1 import (
    IDENTITY_MODE_V1R1,
    IDENTITY_MODES_R1,
    VehicleIdentityR1Engine,
    vehicle_identity_r1_signature,
)


def identity_runtime_fingerprint_r1() -> list[dict[str, str]]:
    path = Path(__file__).with_name("vehicle_identity_r1.py").resolve()
    return [
        {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": sha256_file(path),
        }
    ]


def _extend_source_receipt(
    original_receipt_fn,
    *,
    allow_dirty_dev: bool = False,
) -> dict[str, Any]:
    receipt = dict(original_receipt_fn(allow_dirty_dev=allow_dirty_dev))
    tracked = (
        Path(__file__).resolve(),
        Path(__file__).with_name("vehicle_identity_r1.py").resolve(),
        Path(__file__).with_name("render_identity_probe_r1.py").resolve(),
        Path(__file__).with_name("analyze_vehicle_identity_r1.py").resolve(),
        Path(__file__).with_name("run_local_identity_validation_r1.py").resolve(),
    )
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            *(str(path.relative_to(REPOSITORY_ROOT)) for path in tracked),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    extra_dirty = bool(result.stdout.strip())
    if extra_dirty and not allow_dirty_dev:
        raise ValueError("Stage AG-R1 tracked source is dirty; official package refused")
    if extra_dirty:
        receipt["dependency_dirty"] = True
        receipt["source_policy"] = "DEV_DIRTY_SOURCE / NOT_PROMOTABLE"
        receipt["source_status"] = "DEV_DIRTY_SOURCE"
        receipt["promotable"] = False
        receipt["promotion_status"] = "NOT_PROMOTABLE"
        dirty = list(receipt.get("dependency_dirty_paths", []))
        dirty.extend(
            line[3:].strip()
            for line in result.stdout.splitlines()
            if len(line) >= 4
        )
        receipt["dependency_dirty_paths"] = sorted(set(dirty))
    return receipt


def build_identity_package_r1(args: argparse.Namespace) -> Path:
    if args.identity_mode not in IDENTITY_MODES_R1:
        raise ValueError(f"unsupported Stage AG-R1 mode: {args.identity_mode}")

    original_receipt_fn = _base.stage_ag_source_receipt

    def receipt_fn(*, allow_dirty_dev: bool = False):
        return _extend_source_receipt(
            original_receipt_fn,
            allow_dirty_dev=allow_dirty_dev,
        )

    saved = {
        "IDENTITY_MODE_V1": _base.IDENTITY_MODE_V1,
        "IDENTITY_MODES": _base.IDENTITY_MODES,
        "VehicleIdentityEngine": _base.VehicleIdentityEngine,
        "vehicle_identity_signature": _base.vehicle_identity_signature,
        "identity_runtime_fingerprint": _base.identity_runtime_fingerprint,
        "stage_ag_source_receipt": _base.stage_ag_source_receipt,
    }
    _base.IDENTITY_MODE_V1 = IDENTITY_MODE_V1R1
    _base.IDENTITY_MODES = IDENTITY_MODES_R1
    _base.VehicleIdentityEngine = VehicleIdentityR1Engine
    _base.vehicle_identity_signature = vehicle_identity_r1_signature
    _base.identity_runtime_fingerprint = identity_runtime_fingerprint_r1
    _base.stage_ag_source_receipt = receipt_fn
    try:
        return _base.build_identity_package(args)
    finally:
        for name, value in saved.items():
            setattr(_base, name, value)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build immutable Stage AG-R1 legacy/R1 audition package"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--vehicle", choices=["all", *_base.af_builder.VEHICLES], default="all")
    parser.add_argument("--identity-mode", choices=sorted(IDENTITY_MODES_R1), required=True)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    parser.add_argument("--package-id")
    parser.add_argument("--candidate-id", default="candidate-stage-ag-r1")
    parser.add_argument("--port-base", type=int, default=23380)
    parser.add_argument("--allow-dirty-dev", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port_base <= 65532:
        parser.error("--port-base must leave room for selected vehicle ports")
    result = build_identity_package_r1(args)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
