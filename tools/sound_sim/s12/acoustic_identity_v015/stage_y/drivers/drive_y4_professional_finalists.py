"""Evaluate SHA-bound MATLAB/MoSQITo/order finalist receipts.

Input JSON schema (compact)::

    {
      "maximum_psychoacoustic_median_error": 0.15,
      "maximum_order_median_error_db": 2.0,
      "require_order_for_formal": true,
      "finalists": [
        {
          "candidate_id": "hellcat-p3-r2",
          "candidate_sha256": "...",
          "inner_objective": 0.2,
          "matlab_receipt": "...json",
          "matlab_receipt_sha256": "...",
          "mosqito_receipt": "...json",
          "mosqito_receipt_sha256": "...",
          "order_receipt": "...json",
          "order_receipt_sha256": "...",
          "human_feedback": null
        }
      ]
    }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ...stage_v.io import write_json
from ..finalist_validation import FinalistEvidence, evaluate_finalists, load_bound_receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Stage Y professional finalists")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = json.loads(args.input.read_text(encoding="utf-8-sig"))
    finalists = []
    for item in spec.get("finalists", []):
        finalists.append(
            FinalistEvidence(
                candidate_id=str(item["candidate_id"]),
                candidate_sha256=str(item["candidate_sha256"]),
                inner_objective=float(item["inner_objective"]),
                matlab_receipt=load_bound_receipt(item["matlab_receipt"], item.get("matlab_receipt_sha256")),
                mosqito_receipt=load_bound_receipt(item["mosqito_receipt"], item.get("mosqito_receipt_sha256")),
                order_receipt=load_bound_receipt(item["order_receipt"], item.get("order_receipt_sha256")),
                human_feedback=item.get("human_feedback"),
            )
        )
    result = evaluate_finalists(
        finalists,
        maximum_psychoacoustic_median_error=float(spec["maximum_psychoacoustic_median_error"]),
        maximum_order_median_error_db=float(spec.get("maximum_order_median_error_db", 3.0)),
        require_order_for_formal=bool(spec.get("require_order_for_formal", True)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["preferred_for_human_review"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
