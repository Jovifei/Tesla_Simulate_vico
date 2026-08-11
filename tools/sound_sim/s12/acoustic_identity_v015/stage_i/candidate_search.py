"""Deterministic bounded selection of three Stage-I listening candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math


_CANDIDATE_KEYS = (
    "shaft_order_error",
    "lobe_order_error",
    "blower_load_correlation",
    "blower_to_exhaust_ratio_idle_db",
    "blower_to_exhaust_ratio_acceleration_db",
    "blower_to_exhaust_ratio_full_pull_db",
    "sideband_to_main_ratio",
    "order_cluster_width_ratio",
    "single_ridge_concentration",
    "upper_band_share_4_12khz",
    "upper_band_short_time_peak",
    "boost_attack_10_90_s",
    "boost_release_90_10_s",
    "bypass_decay_90_10_s",
    "bypass_event_count",
    "low_frequency_share_40_200hz",
    "rumble_energy",
    "whole_cycle_lufs",
    "peak_dbfs",
    "clipping_count",
    "sample_rate_hz",
    "channels",
    "pcm_bits",
    "finite",
    "track_p_guard_pass",
    "regression_isolation_pass",
)

_BASELINE_KEYS = (
    "blower_to_exhaust_ratio_idle_db",
    "blower_to_exhaust_ratio_acceleration_db",
    "blower_to_exhaust_ratio_full_pull_db",
    "single_ridge_concentration",
    "upper_band_share_4_12khz",
    "upper_band_short_time_peak",
    "low_frequency_share_40_200hz",
    "rumble_energy",
    "whole_cycle_lufs",
)
_BOOLEAN_KEYS = ("finite", "track_p_guard_pass", "regression_isolation_pass")


def evaluate_stage_i_hard_gates(
    metrics: Mapping[str, object],
    stage_h_baseline: Mapping[str, object],
) -> dict[str, bool]:
    """Evaluate fixed Stage-I health gates without altering reference gates."""
    for key in _BOOLEAN_KEYS:
        if key not in metrics or not isinstance(metrics[key], bool):
            raise ValueError(f"candidate metrics field {key!r} must be an exact boolean")
    values = _required_finite(
        metrics,
        tuple(key for key in _CANDIDATE_KEYS if key not in _BOOLEAN_KEYS),
        "candidate metrics",
    )
    baseline = _required_finite(stage_h_baseline, _BASELINE_KEYS, "Stage-H baseline")

    acceleration_delta = values["blower_to_exhaust_ratio_acceleration_db"] - baseline["blower_to_exhaust_ratio_acceleration_db"]
    idle_delta = values["blower_to_exhaust_ratio_idle_db"] - baseline["blower_to_exhaust_ratio_idle_db"]
    full_pull_delta = values["blower_to_exhaust_ratio_full_pull_db"] - baseline["blower_to_exhaust_ratio_full_pull_db"]
    ridge_reduction = (baseline["single_ridge_concentration"] - values["single_ridge_concentration"]) / max(abs(baseline["single_ridge_concentration"]), 1e-18)
    low_frequency_change = abs(values["low_frequency_share_40_200hz"] - baseline["low_frequency_share_40_200hz"]) / max(abs(baseline["low_frequency_share_40_200hz"]), 1e-18)
    gates = {
        "shaft_order_error": values["shaft_order_error"] <= 0.01,
        "lobe_order_error": values["lobe_order_error"] <= 0.01,
        "blower_load_correlation": values["blower_load_correlation"] >= 0.82,
        "acceleration_blower_exhaust_delta": 2.0 <= acceleration_delta <= 4.0,
        "idle_blower_exhaust_delta": idle_delta <= 0.5,
        "full_pull_blower_exhaust_delta": 1.5 <= full_pull_delta <= 3.5,
        "sideband_to_main_ratio": 0.08 <= values["sideband_to_main_ratio"] <= 0.18,
        "order_cluster_width_ratio": 0.006 <= values["order_cluster_width_ratio"] <= 0.030,
        "single_ridge_reduction": 0.15 <= ridge_reduction <= 0.40,
        "upper_band_share": values["upper_band_share_4_12khz"] <= 0.010 and values["upper_band_share_4_12khz"] - baseline["upper_band_share_4_12khz"] <= 0.003,
        "upper_band_short_time_peak": values["upper_band_short_time_peak"] <= baseline["upper_band_short_time_peak"],
        "boost_attack": 0.060 <= values["boost_attack_10_90_s"] <= 0.120,
        "boost_release": 0.18 <= values["boost_release_90_10_s"] <= 0.35,
        "bypass_decay": 0.08 <= values["bypass_decay_90_10_s"] <= 0.30 and values["bypass_event_count"] >= 1.0,
        "low_frequency_share": low_frequency_change <= 0.05,
        "rumble_energy": values["rumble_energy"] >= 0.95 * baseline["rumble_energy"],
        "whole_cycle_lufs": abs(values["whole_cycle_lufs"] - baseline["whole_cycle_lufs"]) <= 0.5,
        "peak": values["peak_dbfs"] <= -1.5,
        "clipping": values["clipping_count"] == 0.0,
        "pcm_contract": values["sample_rate_hz"] == 48000.0 and values["channels"] == 2.0 and values["pcm_bits"] == 24.0,
        "finite": metrics["finite"] is True,
        "track_p_guard": metrics["track_p_guard_pass"] is True,
        "regression_isolation": metrics["regression_isolation_pass"] is True,
    }
    gates["all_pass"] = all(gates.values())
    return gates


def select_stage_i_candidates(
    candidates: Sequence[Mapping[str, object]],
    stage_h_baseline: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    """Select Balanced, Whine Forward, and Softer Mechanical candidates.

    The search space is capped at 36 records.  Selection is intentionally
    deterministic and only chooses three engineering-qualified orientations;
    it does not claim which one sounds most like a Hellcat.
    """
    if len(candidates) > 36:
        raise ValueError("Stage-I bounded search accepts at most 36 candidates")
    accepted: list[Mapping[str, object]] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        parameters = candidate.get("parameters")
        metrics = candidate.get("metrics")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("each candidate requires a non-empty candidate_id")
        if candidate_id in seen_ids:
            raise ValueError(f"duplicate candidate_id {candidate_id!r}")
        seen_ids.add(candidate_id)
        if not isinstance(parameters, Mapping) or not isinstance(metrics, Mapping):
            raise ValueError(f"candidate {candidate_id!r} requires parameters and metrics mappings")
        if evaluate_stage_i_hard_gates(metrics, stage_h_baseline)["all_pass"]:
            accepted.append(candidate)
    if len(accepted) < 3:
        raise ValueError("Stage-I selection requires at least three hard-gate-passing candidates")

    baseline_acceleration = _number(stage_h_baseline, "blower_to_exhaust_ratio_acceleration_db")
    baseline_full_pull = _number(stage_h_baseline, "blower_to_exhaust_ratio_full_pull_db")

    def stable(candidate: Mapping[str, object]) -> tuple[str, str]:
        parameters = candidate["parameters"]
        assert isinstance(parameters, Mapping)
        return (_canonical_parameters(parameters), str(candidate["candidate_id"]))

    def metric(candidate: Mapping[str, object], name: str) -> float:
        values = candidate["metrics"]
        assert isinstance(values, Mapping)
        return _number(values, name)

    balanced = min(
        accepted,
        key=lambda item: (
            abs((metric(item, "blower_to_exhaust_ratio_acceleration_db") - baseline_acceleration) - 3.0),
            abs((metric(item, "blower_to_exhaust_ratio_full_pull_db") - baseline_full_pull) - 2.5),
            abs(metric(item, "sideband_to_main_ratio") - 0.13),
            metric(item, "upper_band_short_time_peak"),
            stable(item),
        ),
    )
    remaining = [candidate for candidate in accepted if candidate["candidate_id"] != balanced["candidate_id"]]
    forward = min(
        remaining,
        key=lambda item: (
            -metric(item, "blower_to_exhaust_ratio_acceleration_db"),
            -metric(item, "blower_to_exhaust_ratio_full_pull_db"),
            metric(item, "upper_band_short_time_peak"),
            stable(item),
        ),
    )
    remaining = [candidate for candidate in remaining if candidate["candidate_id"] != forward["candidate_id"]]
    soft = min(
        remaining,
        key=lambda item: (
            metric(item, "upper_band_short_time_peak"),
            -metric(item, "sideband_to_main_ratio"),
            metric(item, "single_ridge_concentration"),
            stable(item),
        ),
    )
    return {
        "I6-A Balanced": balanced,
        "I6-B Whine Forward": forward,
        "I6-C Softer Mechanical": soft,
    }


def _required_finite(source: Mapping[str, object], keys: tuple[str, ...], label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for key in keys:
        if key not in source:
            raise ValueError(f"{label} missing required field {key!r}")
        value = source[key]
        if isinstance(value, bool):
            values[key] = float(value)
            continue
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{label} field {key!r} must be finite")
        values[key] = float(value)
    return values


def _number(source: Mapping[str, object], key: str) -> float:
    value = source.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"field {key!r} must be a finite number")
    return float(value)


def _canonical_parameters(parameters: Mapping[str, object]) -> str:
    try:
        return json.dumps(parameters, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate parameters must be deterministic JSON values") from exc


__all__ = ("evaluate_stage_i_hard_gates", "select_stage_i_candidates")
