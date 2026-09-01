"""Publish the Stage Z v2 package and repository-side evidence receipts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..stage_v.io import sha256_file, write_json
from .method_ablation import build_method_adoption_matrix, build_teacher_vs_reduced_response
from .package_v2 import build_stage_z_package

REPO_ROOT = Path(__file__).resolve().parents[5]
MATRIX_PATH = REPO_ROOT / "docs/research/engine-audio-ecosystem/method_adoption_matrix_v2.json"
REPORT_ROOT = REPO_ROOT / "tasks/reports/runtime/s12-stage-z"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=8.0)
    parser.add_argument("--hot-idle-duration-s", type=float, default=20.0)
    args = parser.parse_args()
    main_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    rows = build_method_adoption_matrix()
    write_json(MATRIX_PATH, {"schema": "s12.stage_z.method_adoption_matrix.v2", "main_head": main_head, "rows": rows, "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"})
    teacher_path = REPORT_ROOT / "teacher_vs_reduced_response.json"
    write_json(teacher_path, build_teacher_vs_reduced_response())
    manifest = build_stage_z_package(args.package_root, duration_s=args.duration_s, hot_idle_duration_s=args.hot_idle_duration_s)
    package_manifest = args.package_root / "package_manifest.json"
    receipt = {
        "schema": "s12.stage_z.publish_receipt.v1",
        "run_id": "stage-z-publish-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "main_head": main_head,
        "package_root": str(args.package_root),
        "package_manifest_sha256": sha256_file(package_manifest),
        "package_parent_sha256": manifest["parent_sha256"],
        "package_final_raw_sha256": manifest["final_raw_sha256"],
        "method_count": len(rows),
        "method_ablation_count": len(manifest["method_ablation_views"]),
        "matrix_path": str(MATRIX_PATH.relative_to(REPO_ROOT).as_posix()),
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "teacher_path": str(teacher_path.relative_to(REPO_ROOT).as_posix()),
        "teacher_sha256": sha256_file(teacher_path),
        "status": "PUBLISHED_DIAGNOSTIC_ONLY",
        "boundary": manifest["review_boundaries"],
    }
    receipt_path = REPORT_ROOT / "stage_z_publish_receipt.json"
    write_json(receipt_path, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
