"""Stage AC (AC5): generate isolated dynamic-event timing + afterfire receipts.

Diagnostic-only. Reuses the unchanged production engine to render ISOLATED
single-event state traces (no product scene / PCM / renderer change). Emits:

  tasks/reports/runtime/s12-stage-ac/receipts/
    dynamic_event_timing_contract.json
    afterfire_metric_validation_v2.json

Plus a machine-readable per-stage summary the human-audition prep can consume.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .isolated_events import (
    ISOLATED_SCENES,
    afterfire_metric_validation_v2,
    isolated_event_timing_document,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
AC_RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-ac"
RECEIPTS = AC_RUNTIME / "receipts"

DURATION_S = 2.0


def main() -> int:
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    started = time.time()

    timing: dict[str, Any] = {
        "schema": "s12.stage_ac.dynamic_event_timing_contract.v1",
        "duration_s": DURATION_S,
        "state_block_ms": 20.0,
        "semantics": (
            "state and renderer response share the 20 ms audio block; a response within the "
            "same block as the state onset is SAME_BLOCK_RESPONSE (frame quantization), never "
            "an 'instant physical response' or transport-delay claim. Sub-20 ms distinctions "
            "are not resolvable at the 50-frame/sec block rate and are not asserted as delay."
        ),
        "isolated_scenes": list(ISOLATED_SCENES),
    }
    for kind in ISOLATED_SCENES:
        timing[kind] = isolated_event_timing_document(kind, DURATION_S)
    path = RECEIPTS / "dynamic_event_timing_contract.json"
    path.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[stage-ac] wrote {path}", flush=True)

    after = afterfire_metric_validation_v2("isolated_afterfire_eligible", "isolated_afterfire_ineligible", DURATION_S)
    path2 = RECEIPTS / "afterfire_metric_validation_v2.json"
    path2.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[stage-ac] wrote {path2}", flush=True)

    print(f"[stage-ac] AC5 receipts done in {time.time() - started:.1f}s -> {RECEIPTS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
