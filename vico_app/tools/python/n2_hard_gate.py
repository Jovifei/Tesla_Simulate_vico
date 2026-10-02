"""Artifact-bound N2 reservation/check CLI. No objective scorer or playback path.

The pre-score artifact checks and all entry points share n2_artifact_gate. Old unbound
result/ledger schemas are rejected; they must not be silently migrated or reset.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__:
    from .n2_artifact_gate import (
        CANDIDATE, LIMITS, LOW_BAND_DB_LIMIT, MID_BAND_DB_LIMIT, SOURCE_RMS_DB_LIMIT,
        _finite_number, add_artifact_arguments, file_arguments, rejection, reserve, verify,
    )
else:
    from n2_artifact_gate import (
        CANDIDATE, LIMITS, LOW_BAND_DB_LIMIT, MID_BAND_DB_LIMIT, SOURCE_RMS_DB_LIMIT,
        _finite_number, add_artifact_arguments, file_arguments, rejection, reserve, verify,
    )



def metric_reasons(result):
    reasons = []
    evidence = result.get("evidence")
    if (not isinstance(evidence, dict) or type(evidence.get("sample_count")) is not int
            or evidence.get("sample_count", 0) <= 0 or evidence.get("finite") is not True
            or evidence.get("energy_finite") is not True):
        reasons.append("digital_evidence")
    for key in ("partition_invariant", "snapshot_replay", "baseline_t_identity", "state_continuity"):
        if result.get(key) is not True:
            reasons.append(key)
    if result.get("heldout_used_for_fitting") is not False:
        reasons.append("heldout_fit_leak")
    if type(result.get("gain_changes_after_calibration")) is not int or result.get("gain_changes_after_calibration") != 0:
        reasons.append("gain_change")

    continuous = result.get("continuous")
    if not isinstance(continuous, dict):
        reasons.append("continuous_metrics")
    else:
        # A maximum is mandatory: median/p90 alone can hide a violating protected-band tail.
        checks = (("low_max_db", LOW_BAND_DB_LIMIT, True),
                  ("mid_max_rise_db", MID_BAND_DB_LIMIT, False),
                  ("source_rms_change_db", SOURCE_RMS_DB_LIMIT, True))
        # Optional legacy summaries, when supplied, must obey the same registered 1 dB cap.
        checks += tuple((key, LOW_BAND_DB_LIMIT, True) for key in ("low_median_db", "low_p90_db") if key in continuous)
        for key, limit, absolute in checks:
            try:
                value = _finite_number(continuous.get(key), key)
                if (abs(value) if absolute else value) > limit:
                    reasons.append(key + "_gt_1db")
            except ValueError as exc:
                reasons.append(str(exc))
        groups = continuous.get("provenance_groups")
        if not isinstance(groups, dict) or not groups:
            reasons.append("provenance_groups_missing")
        else:
            for name, values in groups.items():
                try:
                    if not name or not isinstance(values, dict):
                        raise ValueError("invalid_group")
                    before = _finite_number(values.get("baseline_distance"), "provenance_baseline")
                    after = _finite_number(values.get("candidate_distance"), "provenance_candidate")
                    if before <= 0 or after < 0 or after / before > 1.1:
                        raise ValueError("provenance_regression")
                except ValueError:
                    reasons.append("provenance:" + name)
    event = result.get("event")
    try:
        if not isinstance(event, dict):
            raise ValueError("event_metrics")
        before = _finite_number(event.get("baseline_distance"), "event_baseline_distance")
        after = _finite_number(event.get("candidate_distance"), "event_candidate_distance")
        if before <= 0 or after < 0 or after / before > .8:
            raise ValueError("event_20pct_gate")
    except ValueError as exc:
        reasons.append(str(exc))
    return reasons


def check(result_path: Path, **files):
    return verify(result_path, **files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    reserve_parser = sub.add_parser("reserve")
    add_artifact_arguments(reserve_parser)
    reserve_parser.add_argument("--kind", choices=sorted(LIMITS), required=True)
    check_parser = sub.add_parser("check")
    add_artifact_arguments(check_parser)
    check_parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "reserve":
            output = reserve(kind=args.kind, **file_arguments(args))
        else:
            output = check(args.result, **file_arguments(args))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, OverflowError) as exc:
        output = rejection(["invalid_reservation:" + str(exc)])
    print(json.dumps(output, sort_keys=True, allow_nan=False))
    return 2 if output.get("feasible") is False else 0


if __name__ == "__main__":
    sys.exit(main())
