"""Identify a causal FIR from local ENSIM4/CFD or measured I/O WAV pairs.

The command stores only FIR coefficients, input/output SHA bindings and fit
metrics.  It does not copy the source WAV files and does not alter frozen PTR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ...stage_v.io import write_json
from ...stage_x.reference_caseset import read_wav_mono
from ..transfer_response_id import identify_fir_response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Identify a Stage Y causal transfer response")
    parser.add_argument("--input", required=True, type=Path, help="source pressure/excitation WAV")
    parser.add_argument("--output-response", required=True, type=Path, help="measured/teacher output WAV")
    parser.add_argument("--receipt", required=True, type=Path, help="JSON provenance/rights or simulation receipt")
    parser.add_argument("--output", required=True, type=Path, help="FIR result JSON")
    parser.add_argument("--taps", type=int, default=128)
    parser.add_argument("--regularization", type=float, default=1e-5)
    parser.add_argument("--maximum-validation-nrmse", type=float, default=0.35)
    return parser.parse_args()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    args = parse_args()
    provenance = json.loads(args.receipt.read_text(encoding="utf-8-sig"))
    if not isinstance(provenance, dict):
        raise ValueError("receipt must be a JSON object")
    if provenance.get("source_type") not in {"ENSIM4_SIMULATION", "CFD_SIMULATION", "PROJECT_MEASUREMENT", "OWNER_AUTHORIZED_MEASUREMENT"}:
        raise PermissionError("receipt source_type is not eligible for transfer identification")
    expected_input = provenance.get("input_sha256")
    expected_output = provenance.get("output_sha256")
    if expected_input != _sha(args.input) or expected_output != _sha(args.output_response):
        raise ValueError("receipt SHA bindings do not match input/output WAV files")
    source, source_rate = read_wav_mono(args.input)
    response, response_rate = read_wav_mono(args.output_response)
    if source_rate != response_rate:
        raise ValueError("input and output sample rates must match")
    result = identify_fir_response(
        source,
        response,
        source_rate,
        tap_count=args.taps,
        regularization=args.regularization,
        provenance={
            "receipt_path": str(args.receipt),
            "receipt_sha256": _sha(args.receipt),
            "source_type": provenance["source_type"],
        },
    )
    payload = result.to_dict()
    payload["validation_gate"] = {
        "maximum_validation_nrmse": args.maximum_validation_nrmse,
        "passed": result.validation_nrmse <= args.maximum_validation_nrmse,
    }
    payload["integration_status"] = "CANDIDATE_FOR_REVIEW" if payload["validation_gate"]["passed"] else "REJECTED_FIT_ERROR"
    payload["frozen_ptr_modified"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["validation_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
