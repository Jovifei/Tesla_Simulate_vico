"""CLI and library wrapper for deterministic Stage-K candidate qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_search import select_stage_k_candidate


def qualify_stage_k_candidates(
    candidates: list[dict[str, Any]],
    parent_metrics: dict[str, Any] | None = None,
    vehicle_id: str | None = None,
) -> dict[str, Any]:
    """Return the selected record plus deterministic gate/report metadata."""

    selected = select_stage_k_candidate(candidates, parent_metrics, vehicle_id)
    return {
        "vehicle_id": vehicle_id or "unknown",
        "candidate_count": len(candidates),
        "selected_candidate_id": selected["candidate_id"],
        "selected": selected,
        "scope": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path, help="JSON array or object with a candidates array")
    parser.add_argument("--parent", type=Path, help="optional parent metrics JSON")
    parser.add_argument("--vehicle-id", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise SystemExit("candidate JSON object must contain a candidates array")
    elif isinstance(payload, list):
        candidates = payload
    else:
        raise SystemExit("candidate JSON must be an array or object")
    parent = json.loads(args.parent.read_text(encoding="utf-8")) if args.parent else None
    result = qualify_stage_k_candidates(candidates, parent, args.vehicle_id)
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
