"""Strict N2 budget reservation and hard-feasibility checker.

This tool intentionally has no objective-score input. A trial must reserve one of the fixed
48/24 attempts first, then pass this hard gate before any separate scoring code may consume it.
The ledger is candidate/profile-bound and cannot be reset by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

CANDIDATE = "C63_N2_CONTINUOUS_V1"
LIMITS = {"continuous": 48, "event": 24}


def _sha(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("invalid sha256")
    int(value, 16)
    return value.lower()


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def reserve(ledger_path: Path, kind: str, trial_id: str, profile_sha256: str) -> dict[str, Any]:
    if kind not in LIMITS:
        raise ValueError("kind must be continuous or event")
    if not trial_id or any(c.isspace() for c in trial_id):
        raise ValueError("trial id must be non-empty and whitespace-free")
    profile_sha256 = _sha(profile_sha256)

    if ledger_path.exists():
        ledger = _read_json(ledger_path)
        if ledger.get("schema") != "c63.n2.budget.v1":
            raise ValueError("budget ledger schema mismatch")
        if ledger.get("candidate") != CANDIDATE or ledger.get("profile_sha256") != profile_sha256:
            raise ValueError("budget ledger identity mismatch; no restart under another identity")
    else:
        ledger = {
            "schema": "c63.n2.budget.v1",
            "candidate": CANDIDATE,
            "profile_sha256": profile_sha256,
            "limits": LIMITS.copy(),
            "continuous": [],
            "event": [],
        }

    attempts = ledger.get(kind)
    if not isinstance(attempts, list):
        raise ValueError("malformed budget ledger")
    if trial_id in attempts:
        raise ValueError("duplicate trial id")
    if len(attempts) >= LIMITS[kind]:
        raise RuntimeError(f"{kind} budget exhausted; no restart")
    attempts.append(trial_id)
    _write_atomic(ledger_path, ledger)
    return {
        "status": "RESERVED",
        "kind": kind,
        "attempt": len(attempts),
        "maximum": LIMITS[kind],
        "trial_id": trial_id,
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
    }


def _finite_number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} missing/non-numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} nonfinite")
    return value


def check(result_path: Path) -> dict[str, Any]:
    result = _read_json(result_path)
    reasons: list[str] = []

    if result.get("schema") != "c63.n2.reference_result.v1":
        reasons.append("schema")
    if result.get("candidate") != CANDIDATE:
        reasons.append("candidate_identity")
    try:
        _sha(result.get("profile_sha256", ""))
        _sha(result.get("reference_targets_sha256", ""))
    except (ValueError, TypeError):
        reasons.append("artifact_identity")

    budget = result.get("budget", {})
    if not isinstance(budget, dict):
        reasons.append("budget")
    else:
        for kind, maximum in LIMITS.items():
            count = budget.get(kind)
            if not isinstance(count, int) or count < 0 or count > maximum:
                reasons.append(f"{kind}_budget")

    evidence = result.get("evidence", {})
    if (
        not isinstance(evidence, dict)
        or not isinstance(evidence.get("sample_count"), int)
        or evidence.get("sample_count", 0) <= 0
        or evidence.get("finite") is not True
        or evidence.get("energy_finite") is not True
    ):
        reasons.append("digital_evidence")

    for key in ("partition_invariant", "snapshot_replay", "baseline_t_identity", "state_continuity"):
        if result.get(key) is not True:
            reasons.append(key)

    if result.get("heldout_used_for_fitting") is not False:
        reasons.append("heldout_fit_leak")
    if result.get("gain_changes_after_calibration") != 0:
        reasons.append("gain_change")

    continuous = result.get("continuous", {})
    if not isinstance(continuous, dict):
        reasons.append("continuous_metrics")
    else:
        try:
            low_median = abs(_finite_number(continuous.get("low_median_db"), "low_median_db"))
            low_p90 = abs(_finite_number(continuous.get("low_p90_db"), "low_p90_db"))
            mid_rise = _finite_number(continuous.get("mid_max_rise_db"), "mid_max_rise_db")
            source_change = abs(_finite_number(continuous.get("source_rms_change_db"), "source_rms_change_db"))
            if low_median > 1.0:
                reasons.append("low_median_gt_1db")
            if low_p90 > 1.5:
                reasons.append("low_p90_gt_1_5db")
            if mid_rise > 1.0:
                reasons.append("mid_rise_gt_1db")
            if source_change > 1.0:
                reasons.append("source_rms_gt_1db")
        except ValueError as exc:
            reasons.append(str(exc))

        groups = continuous.get("provenance_groups", {})
        if not isinstance(groups, dict) or not groups:
            reasons.append("provenance_groups_missing")
        else:
            for name, values in groups.items():
                if not isinstance(values, dict):
                    reasons.append(f"provenance:{name}")
                    continue
                try:
                    before = _finite_number(values.get("baseline_distance"), f"{name}.baseline")
                    after = _finite_number(values.get("candidate_distance"), f"{name}.candidate")
                    if before <= 0.0 or after < 0.0 or after > 1.1 * before:
                        reasons.append(f"provenance:{name}")
                except ValueError:
                    reasons.append(f"provenance:{name}")

    event = result.get("event", {})
    if not isinstance(event, dict):
        reasons.append("event_metrics")
    else:
        try:
            before = _finite_number(event.get("baseline_distance"), "event.baseline_distance")
            after = _finite_number(event.get("candidate_distance"), "event.candidate_distance")
            if before <= 0.0 or after < 0.0 or after > 0.8 * before:
                reasons.append("event_20pct_gate")
        except ValueError as exc:
            reasons.append(str(exc))

    return {
        "schema": "c63.n2.hard_gate.v1",
        "candidate": CANDIDATE,
        "status": "FEASIBLE" if not reasons else "REJECTED_BEFORE_SCORING",
        "feasible": not reasons,
        "reasons": sorted(set(reasons)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    reserve_parser = sub.add_parser("reserve")
    reserve_parser.add_argument("--ledger", type=Path, required=True)
    reserve_parser.add_argument("--kind", choices=sorted(LIMITS), required=True)
    reserve_parser.add_argument("--trial-id", required=True)
    reserve_parser.add_argument("--profile-sha256", required=True)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--result", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "reserve":
        output = reserve(args.ledger, args.kind, args.trial_id, args.profile_sha256)
        print(json.dumps(output, indent=2, allow_nan=False))
        return

    output = check(args.result)
    print(json.dumps(output, indent=2, allow_nan=False))
    if not output["feasible"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
