"""Drive X7 review package build + validation (requires X5 summary)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_identity_v015.stage_x import reference_caseset as rc  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.review_package import build_review_package, validate_review_package  # noqa: E402

MANIFEST = REPO_ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "reference_database" / "realism_reference_manifest.json"
R2_AUDIO_DIR = Path("E:/Claude_allow/Download/s12-acoustic-realism-v10")
RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x"
PACKAGE_ROOT = Path("E:/Tesla_speed/review_packages/s12-stage-x-r2-engineering-selection-v1")


def main() -> int:
    started = time.perf_counter()
    preselection = json.loads((RUNTIME / "x5_hellcat_preselection_summary.json").read_text(encoding="utf-8"))
    caseset = rc.build_reference_caseset("hellcat", MANIFEST, R2_AUDIO_DIR)
    if PACKAGE_ROOT.exists():
        import shutil

        shutil.rmtree(PACKAGE_ROOT)
    manifest = build_review_package(PACKAGE_ROOT, caseset, preselection)
    errors = validate_review_package(PACKAGE_ROOT)
    summary = {
        "schema": "s12.stage_x.x7_summary.v1",
        "package_root": str(PACKAGE_ROOT),
        "selected_architecture": manifest["selected_engineering_architecture"],
        "scenario_count": len(manifest["scenarios"]),
        "reference_bound_scenarios": sum(1 for entry in manifest["scenarios"].values() if entry["reference_bound"]),
        "validator_errors": errors,
        "package_zip_sha256": None,
        "wall_seconds": round(time.perf_counter() - started, 1),
    }
    if not errors:
        import shutil

        zip_path = PACKAGE_ROOT.with_suffix(".zip")
        shutil.make_archive(str(PACKAGE_ROOT), "zip", PACKAGE_ROOT)
        import hashlib

        summary["package_zip_sha256"] = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (RUNTIME / "x7_package_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "validator_errors"}, ensure_ascii=False), "errors:", errors)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
