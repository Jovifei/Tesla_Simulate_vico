"""Drive X4 Hellcat parameter reachability (offline, deterministic)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import run_parameter_reachability  # noqa: E402

OUTPUT_ROOT = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x" / "x4_reachability"


def main() -> int:
    started = time.perf_counter()
    traces = [
        build_hellcat_bakeoff_trace("hot_idle_20s", 2.0),
        build_hellcat_bakeoff_trace("full_load_acceleration", 2.0),
    ]
    summary = run_parameter_reachability(OUTPUT_ROOT, traces, architecture="P2H")
    
    elapsed = time.perf_counter() - started
    print(json.dumps({"reachable": summary["reachable_count"], "total": summary["parameter_count"], "unreachable": summary["unreachable"], "seconds": round(elapsed, 1)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
