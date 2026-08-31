"""Drive X8 R1 formal gate readiness on the synthetic fixture (offline)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_identity_v015.stage_x.formal_gate_fixture import (  # noqa: E402
    evaluate_formal_selection,
    export_matlab_order_input,
    generate_synthetic_r1_fixture,
)

RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x"


def main() -> int:
    started = time.perf_counter()
    root = RUNTIME / "x8_formal_gate_fixture"
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                path.unlink()
    receipt = generate_synthetic_r1_fixture(root)
    cases = [
        {
            key: case[key]
            for key in (
                "scenario", "audio_path", "audio_sha256", "evidence_level", "rights_status",
                "sample_rate", "start_s", "end_s", "microphone_position", "agc_post_processing",
                "rpm_trace", "load_trace", "gear_trace", "time_coverage_s",
            )
        }
        for case in receipt["cases"]
    ]
    from tools.sound_sim.s12.acoustic_identity_v015.stage_x.formal_gate_fixture import FormalReferenceCase

    typed = [FormalReferenceCase(**case, uncertainty={"fixture": True}) for case in cases]
    export_matlab_order_input(typed, root / "order_input.json")
    result = evaluate_formal_selection(receipt, {"P2H": 0.18, "P3": 0.42, "P5": 0.27}, human_confirmation=False)
    (root / "formal_gate_result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {
        "schema": "s12.stage_x.x8_summary.v1",
        "all_checks_pass": result["all_checks_pass"],
        "formal_selection_status": result["formal_selection_status"],
        "selected_architecture": result["selected_architecture"],
        "profile_candidate_opened": result["profile_candidate_gate"]["opened"],
        "real_status": result["real_status"]["status"],
        "fixture_markers": result["fixture_markers"],
        "wall_seconds": round(time.perf_counter() - started, 2),
    }
    (root / "x8_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
