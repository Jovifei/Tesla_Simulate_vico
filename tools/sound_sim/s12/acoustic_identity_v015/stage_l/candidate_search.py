"""Deterministic, fail-closed qualification of measured Stage-L probe evidence.

The caller renders and discards one probe at a time.  This module accepts only
the compact evidence produced from those arrays and reopened PCM24 bytes; a
caller-supplied ``hard_gates`` mapping is deliberately not part of the schema.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math
from typing import Any


MAX_CANDIDATES = 64

REQUIRED_HARD_GATES = (
    "exact_contract_and_reachability",
    "source_physics",
    "final_pcm_health",
    "all_required_states_available",
    "no_state_regression_over_10_percent",
    "reference_mean_improvement_at_least_30_percent",
    "stage_c_identity_regression_within_10_percent",
    "final_pcm_upper_share",
    "final_pcm_upper_share_increment",
    "non_hellcat_isolation",
    "track_p_guard",
    "low_band_pulse_crest_improves_parent",
    "low_band_pulse_crest_auxiliary_1_to_3_db",
    "roughness_auxiliary_10_to_35_percent",
    "acceleration_20_250hz_absolute_error_non_expansion",
    "acceleration_250_1000hz_absolute_error_strict_shrink",
)

_CANDIDATE_KEYS = {
    "candidate_id", "parameters", "probe_duration_s", "full_render_residency_max",
    "metrics", "reference_distance",
}
_METRIC_KEYS = {"schema_version", "domains", "source_domain", "pre_ptr", "final_pcm24"}
_DOMAIN_VALUES = {
    "source_domain": "actual SourceRender arrays and detected events",
    "pre_ptr": "actual named transient arrays before common Pre-PTR EQ",
    "final_pcm24": "reopened PCM24 WAV bytes",
}
_SOURCE_KEYS = {
    "shaft_ratio_error", "shaft_max_rpm", "shaft_anchor_max_rpm", "intake_whine_load_correlation",
    "intake_to_exhaust_ratio_db", "gear_to_aero_ratio", "intake_transfer_energy_ratio",
    "bypass_event_count", "boost_attack_10_90_s", "boost_release_90_10_s",
    "bypass_decay_90_10_s", "order_ridge_continuity", "tone_prominence_ratio",
    "firing_event_angle_error_samples", "bank_interval_pattern_error", "fourth_order_presence",
    "20_80_hz_share", "80_160_hz_share", "160_250_hz_share", "250_1000_hz_share",
    "low_band_pulse_crest_db", "low_band_envelope_cv", "fluctuation_below_20_hz",
    "roughness_20_300_hz", "modulation_peak_hz", "bank_to_bank_delay",
}
_PRE_PTR_KEYS = {
    "shift_dip_db", "shift_settling_s", "shift_overshoot_db", "named_transient_energy",
    "named_transient_event_count", "domain", "candidate_parameter_usage",
    "all_requested_parameters_reachable",
}
_USAGE_KEYS = {"requested", "read", "configured", "active", "inactive", "unused"}
_PCM_KEYS = {
    "wav_sha256", "sample_rate_hz", "channels", "pcm_bits", "finite",
    "final_pcm_lufs", "final_pcm_peak_dbfs", "clipping_count", "band_shares",
    "review_requested_gain_db", "review_actual_gain_db", "headroom_limited",
}
_REFERENCE_KEYS = {
    "schema_version", "candidate_id", "domain", "bands_hz", "windows_s", "formula", "states",
    "missing_states", "mean_improvement_ratio", "gates", "status", "hashes",
    "reference_provenance", "trace_binding", "stage_l_max_eligible_4_12khz_share",
    "protection_evidence",
}
_REFERENCE_GATES = {
    "all_required_states_available", "mean_improvement_at_least_30_percent",
    "no_state_worse_than_10_percent", "stage_c_identity_regression_at_most_10_percent",
    "stage_l_4_12khz_share_at_most_0_06", "seven_non_hellcat_isolation_pass",
    "track_p_guard_pass", "acceleration_20_250hz_absolute_error_non_expansion",
    "acceleration_250_1000hz_absolute_error_strict_shrink",
}
_REFERENCE_HASHES = {
    "stage_k_wav_sha256", "stage_l_wav_sha256", "reference_target_sha256",
    "candidate_profile_sha256", "trace_evidence_sha256", "identity_evidence_sha256",
    "isolation_evidence_sha256", "track_p_evidence_sha256",
}
def qualify_stage_l_candidates(
    candidates: Sequence[Mapping[str, object]], *, parent_parameters: Mapping[str, object],
    parent_metrics: Mapping[str, object],
) -> dict[str, object]:
    """Select the best candidate whose complete measured gate set passes."""
    if not isinstance(parent_parameters, Mapping):
        raise TypeError("parent_parameters must be a mapping")
    validated_parent = _validate_metrics(parent_metrics, "parent_metrics")
    validated_parent_parameters = _validate_parameters(parent_parameters, "parent_parameters")
    if not candidates:
        raise ValueError("Stage-L search requires at least one candidate")
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"Stage-L bounded search accepts at most {MAX_CANDIDATES} candidates")

    compact: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for raw in candidates:
        candidate = _exact_mapping(raw, _CANDIDATE_KEYS, "candidate record")
        candidate_id = candidate["candidate_id"]
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("each Stage-L candidate requires a non-empty candidate_id")
        if candidate_id in identifiers:
            raise ValueError(f"duplicate candidate_id {candidate_id!r}")
        identifiers.add(candidate_id)
        parameters = candidate["parameters"]
        validated_parameters = _validate_parameters(parameters, f"candidate {candidate_id!r} parameters")
        duration = _finite_number(candidate["probe_duration_s"], "probe_duration_s")
        if not 8.0 <= duration <= 12.0:
            raise ValueError("Stage-L probe_duration_s must be within 8..12 seconds")
        residency = candidate["full_render_residency_max"]
        if isinstance(residency, bool) or not isinstance(residency, int):
            raise ValueError("full_render_residency_max must be an exact integer")
        if residency > 1 or residency < 0:
            raise ValueError("one SourceRender resident at a time is required")

        metrics = _validate_metrics(candidate["metrics"], "metrics")
        requested = set(metrics["pre_ptr"]["candidate_parameter_usage"]["requested"])
        if not requested or set(validated_parameters) != requested:
            raise ValueError("candidate parameter keys must exactly match actual requested usage")
        reference = _validate_reference(candidate["reference_distance"])
        if reference["candidate_id"] != candidate_id:
            raise ValueError("reference summary candidate_id mismatch")
        if metrics["final_pcm24"]["wav_sha256"] != reference["hashes"]["stage_l_wav_sha256"]:
            raise ValueError("candidate metrics WAV hash does not match reference summary")
        if validated_parent["final_pcm24"]["wav_sha256"] != reference["hashes"]["stage_k_wav_sha256"]:
            raise ValueError("parent metrics WAV hash does not match reference summary")
        gates = _derive_gates(metrics, validated_parent, reference)
        if set(gates) != set(REQUIRED_HARD_GATES) or any(type(value) is not bool for value in gates.values()):
            raise ValueError("derived hard gate set is incomplete")
        error_components = _vehicle_specific_error_components(metrics, validated_parent, reference)
        error = float(sum(error_components.values()))
        compact.append({
            "candidate_id": candidate_id,
            "parameters": _json_copy(parameters),
            "probe_duration_s": duration,
            "full_render_residency_max": residency,
            "hard_gates": gates,
            "hard_gates_pass": all(gates.values()),
            "vehicle_specific_error": error,
            "vehicle_specific_error_components": error_components,
            "parameter_delta": _parameter_delta(validated_parameters, validated_parent_parameters),
            "evidence_sha256": dict(reference["hashes"]),
        })

    passing = [record for record in compact if record["hard_gates_pass"] is True]
    selected = min(passing, key=_rank_key) if passing else None
    max_residency = max(int(record["full_render_residency_max"]) for record in compact)
    return {
        "status": "PASS" if selected is not None else "PARTIAL / AUTOMATED_GATE_FAIL",
        "selected_candidate_id": selected["candidate_id"] if selected is not None else None,
        "candidate_count": len(compact),
        "passing_candidate_count": len(passing),
        "gate_order": list(REQUIRED_HARD_GATES) + [
            "vehicle_specific_perceptual_error", "minimum_parent_parameter_delta", "lexical_tie_break",
        ],
        "memory_contract": "one SourceRender resident at a time",
        "full_render_residency_max": max_residency,
        "candidate_file_update_performed": False,
        "evaluated": sorted(compact, key=lambda record: str(record["candidate_id"])),
        "scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    }


def _validate_metrics(value: object, label: str) -> Mapping[str, object]:
    metrics = _exact_mapping(value, _METRIC_KEYS, label)
    if metrics["schema_version"] != "s12-stage-l-perceptual-metrics-1":
        raise ValueError(f"{label} schema_version mismatch")
    if metrics["domains"] != _DOMAIN_VALUES:
        raise ValueError(f"{label} domains mismatch")
    source = _exact_mapping(metrics["source_domain"], _SOURCE_KEYS, f"{label}.source_domain")
    pre_ptr = _exact_mapping(metrics["pre_ptr"], _PRE_PTR_KEYS, f"{label}.pre_ptr")
    pcm = _exact_mapping(metrics["final_pcm24"], _PCM_KEYS, f"{label}.final_pcm24")
    if pre_ptr["domain"] != _DOMAIN_VALUES["pre_ptr"]:
        raise ValueError(f"{label}.pre_ptr domain mismatch")
    for name, item in source.items():
        _finite_number(item, f"{label}.source_domain.{name}")
    for name in _PRE_PTR_KEYS - {"domain", "candidate_parameter_usage", "all_requested_parameters_reachable"}:
        _finite_number(pre_ptr[name], f"{label}.pre_ptr.{name}")
    usage = _exact_mapping(
        pre_ptr["candidate_parameter_usage"], _USAGE_KEYS,
        f"{label}.pre_ptr.candidate_parameter_usage",
    )
    normalized: dict[str, tuple[str, ...]] = {}
    for name, values in usage.items():
        if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values) or len(values) != len(set(values)):
            raise ValueError(f"{label}.pre_ptr.candidate_parameter_usage.{name} must be a unique string list")
        normalized[name] = tuple(values)
    requested, read = set(normalized["requested"]), set(normalized["read"])
    configured, active, inactive, unused = (
        set(normalized["configured"]), set(normalized["active"]),
        set(normalized["inactive"]), set(normalized["unused"]),
    )
    derived_reachable = (
        configured == read and active | inactive == read and not active & inactive
        and read <= requested and unused == requested - read and not unused
    )
    if type(pre_ptr["all_requested_parameters_reachable"]) is not bool or pre_ptr["all_requested_parameters_reachable"] != derived_reachable:
        raise ValueError(f"{label}.pre_ptr all_requested_parameters_reachable mismatch")
    for name in ("sample_rate_hz", "channels", "pcm_bits", "clipping_count"):
        if isinstance(pcm[name], bool) or not isinstance(pcm[name], int):
            raise ValueError(f"{label}.final_pcm24.{name} must be an integer")
    for name in ("finite", "headroom_limited"):
        if type(pcm[name]) is not bool:
            raise ValueError(f"{label}.final_pcm24.{name} must be boolean")
    for name in ("final_pcm_lufs", "final_pcm_peak_dbfs", "review_requested_gain_db", "review_actual_gain_db"):
        _finite_number(pcm[name], f"{label}.final_pcm24.{name}")
    _sha256(pcm["wav_sha256"], f"{label}.final_pcm24.wav_sha256")
    shares = _four_finite(pcm["band_shares"], f"{label}.final_pcm24.band_shares")
    if not 0.0 < sum(shares) <= 1.000001:
        raise ValueError(f"{label}.final_pcm24.band_shares total must be within (0, 1]")
    return metrics


def _validate_reference(value: object) -> Mapping[str, object]:
    ref = _exact_mapping(value, _REFERENCE_KEYS, "reference summary")
    if ref["schema_version"] != "s12-stage-l-reference-distance-1" or ref["domain"] != "final_pcm24_reopened_bytes":
        raise ValueError("reference summary schema/domain mismatch")
    if not isinstance(ref["candidate_id"], str) or not ref["candidate_id"]:
        raise ValueError("reference summary candidate_id is invalid")
    if ref["bands_hz"] != [[20.0, 250.0], [250.0, 1000.0], [1000.0, 4000.0], [4000.0, 12000.0]]:
        raise ValueError("reference summary bands mismatch")
    if ref["windows_s"] != {"idle": [0.0, 8.0], "acceleration": [8.0, 26.0], "afterfire": [36.0, 46.0]}:
        raise ValueError("reference summary windows mismatch")
    if ref["formula"] != "sqrt(0.25 * sum((actual_share - target_share)^2))":
        raise ValueError("reference summary formula mismatch")
    gates = _exact_mapping(ref["gates"], _REFERENCE_GATES, "reference summary gates")
    if any(type(value) is not bool for value in gates.values()):
        raise ValueError("reference summary gates must be boolean")
    hashes = _exact_mapping(ref["hashes"], _REFERENCE_HASHES, "reference summary hashes")
    for name, digest in hashes.items():
        _sha256(digest, f"reference summary hashes.{name}")
    states = _exact_mapping(ref["states"], {"idle", "acceleration", "afterfire"}, "reference summary states")
    improvements: list[float] = []
    missing: list[str] = []
    for name, raw in states.items():
        row = _validate_reference_state(raw, f"reference summary states.{name}")
        if row["availability"] == "N/A":
            missing.append(name)
        else:
            improvements.append(float(row["improvement_ratio"]))
    if ref["missing_states"] != missing:
        raise ValueError("reference summary missing_states mismatch")
    actual_mean = float(sum(improvements) / len(improvements)) if improvements else None
    reported_mean = ref["mean_improvement_ratio"]
    if actual_mean is None:
        if reported_mean is not None:
            raise ValueError("reference summary mean mismatch")
    elif not _same_number(reported_mean, actual_mean):
        raise ValueError("reference summary mean mismatch")
    trace_binding = _exact_mapping(
        ref["trace_binding"], {"trace_version", "trace_sha256", "trace_evidence_sha256"},
        "reference summary trace_binding",
    )
    if not isinstance(trace_binding["trace_version"], str) or not trace_binding["trace_version"]:
        raise ValueError("reference summary trace_version is invalid")
    _sha256(trace_binding["trace_sha256"], "reference summary trace_sha256")
    if trace_binding["trace_evidence_sha256"] != hashes["trace_evidence_sha256"]:
        raise ValueError("reference summary trace receipt hash mismatch")
    protection = _exact_mapping(
        ref["protection_evidence"], {"identity", "isolation", "track_p"},
        "reference summary protection_evidence",
    )
    identity = _exact_mapping(
        protection["identity"], {"schema_version", "producer", "source_artifact", "source_artifact_sha256", "status", "stage_c_identity_regression_ratio"},
        "reference summary identity evidence",
    )
    isolation = _exact_mapping(
        protection["isolation"], {"schema_version", "producer", "source_artifact", "source_artifact_sha256", "status", "seven_non_hellcat_pcm_sha_unchanged"},
        "reference summary isolation evidence",
    )
    track_p = _exact_mapping(
        protection["track_p"], {"schema_version", "producer", "source_artifact", "source_artifact_sha256", "status", "passed", "total", "frozen_files", "frozen_symbols", "unchanged"},
        "reference summary Track-P evidence",
    )
    if identity["schema_version"] != "s12-stage-l-produced-identity-evidence-1" or isolation["schema_version"] != "s12-stage-l-produced-isolation-evidence-1" or track_p["schema_version"] != "s12-stage-l-produced-track-p-evidence-1":
        raise ValueError("reference summary protection evidence schema mismatch")
    if identity["producer"] != "stage_c.identity_reference_distance" or isolation["producer"] != "stage_l.regression_isolation.reference_gate" or track_p["producer"] != "assert_track_p_unchanged.py":
        raise ValueError("reference summary protection evidence producer mismatch")
    for label, row in (("identity", identity), ("isolation", isolation), ("Track-P", track_p)):
        if not isinstance(row["source_artifact"], str) or not row["source_artifact"]:
            raise ValueError(f"reference summary {label} source artifact is invalid")
        _sha256(row["source_artifact_sha256"], f"reference summary {label} source artifact SHA-256")
    identity_regression = _finite_number(identity["stage_c_identity_regression_ratio"], "reference summary identity regression")
    expected_identity_status = "PASS" if identity_regression <= 0.10 else "FAIL"
    isolation_pass = isolation["seven_non_hellcat_pcm_sha_unchanged"] is True
    track_p_pass = (
        track_p["passed"] == 21 and track_p["total"] == 21 and track_p["frozen_files"] == 180
        and track_p["frozen_symbols"] == 2 and track_p["unchanged"] is True
    )
    if identity["status"] != expected_identity_status or isolation["status"] != ("PASS" if isolation_pass else "FAIL") or track_p["status"] != ("PASS" if track_p_pass else "FAIL"):
        raise ValueError("reference summary protection evidence status mismatch")
    upper_values = [float(states[name]["actual_stage_l"][3]) for name in states if states[name]["availability"] == "eligible"]
    expected_upper = max(upper_values) if upper_values else None
    reported_upper = ref["stage_l_max_eligible_4_12khz_share"]
    if (expected_upper is None) != (reported_upper is None) or (
        expected_upper is not None and not _same_number(reported_upper, expected_upper)
    ):
        raise ValueError("reference summary upper-share maximum mismatch")
    expected_gates = {
        "all_required_states_available": not missing,
        "mean_improvement_at_least_30_percent": actual_mean is not None and actual_mean >= 0.30,
        "no_state_worse_than_10_percent": bool(improvements) and all(value >= -0.10 for value in improvements),
        "stage_c_identity_regression_at_most_10_percent": identity_regression <= 0.10,
        "stage_l_4_12khz_share_at_most_0_06": expected_upper is not None and expected_upper <= 0.06,
        "acceleration_20_250hz_absolute_error_non_expansion": False,
        "acceleration_250_1000hz_absolute_error_strict_shrink": False,
        "seven_non_hellcat_isolation_pass": isolation_pass,
        "track_p_guard_pass": track_p_pass,
    }
    acceleration = states["acceleration"]
    if acceleration["availability"] == "eligible":
        target = acceleration["target"]
        stage_k = acceleration["actual_stage_k"]
        stage_l = acceleration["actual_stage_l"]
        expected_gates["acceleration_20_250hz_absolute_error_non_expansion"] = (
            abs(float(stage_l[0]) - float(target[0])) <= abs(float(stage_k[0]) - float(target[0]))
        )
        expected_gates["acceleration_250_1000hz_absolute_error_strict_shrink"] = (
            abs(float(stage_l[1]) - float(target[1])) < abs(float(stage_k[1]) - float(target[1]))
        )
    expected_status = "PASS" if all(expected_gates.values()) else "PARTIAL / AUTOMATED_GATE_FAIL"
    if gates != expected_gates or ref["status"] != expected_status:
        raise ValueError("reference summary derived gates/status mismatch")
    provenance = _exact_mapping(
        ref["reference_provenance"], {"source", "boundary", "absolute_loudness_comparison"},
        "reference summary provenance",
    )
    if provenance["absolute_loudness_comparison"] is not False:
        raise ValueError("reference summary must not compare absolute loudness")
    return ref


def _validate_reference_state(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    if value.get("availability") == "N/A":
        row = _exact_mapping(value, {
            "availability", "target", "actual_stage_k", "actual_stage_l",
            "signed_error", "absolute_error", "stage_k_distance", "stage_l_distance",
            "improvement_ratio",
        }, label)
        if any(row[name] is not None for name in set(row) - {"availability"}):
            raise ValueError(f"{label} N/A values must be null")
        return row
    row = _exact_mapping(value, {
        "availability", "target", "actual_stage_k", "actual_stage_l", "signed_error",
        "absolute_error", "stage_k_distance", "stage_l_distance", "improvement_ratio",
    }, label)
    if row["availability"] != "eligible":
        raise ValueError(f"{label}.availability is invalid")
    target = _four_finite(row["target"], f"{label}.target")
    stage_k = _four_finite(row["actual_stage_k"], f"{label}.actual_stage_k")
    stage_l = _four_finite(row["actual_stage_l"], f"{label}.actual_stage_l")
    signed = _four_finite_signed(row["signed_error"], f"{label}.signed_error")
    absolute = _four_finite(row["absolute_error"], f"{label}.absolute_error")
    expected_signed = [a - b for a, b in zip(stage_l, target)]
    expected_absolute = [abs(value) for value in expected_signed]
    if not _same_vector(signed, expected_signed) or not _same_vector(absolute, expected_absolute):
        raise ValueError(f"{label} error arrays mismatch")
    distance_k = math.sqrt(0.25 * sum((a - b) ** 2 for a, b in zip(stage_k, target)))
    distance_l = math.sqrt(0.25 * sum((a - b) ** 2 for a, b in zip(stage_l, target)))
    improvement = (distance_k - distance_l) / max(distance_k, 1.0e-12)
    if not all((_same_number(row["stage_k_distance"], distance_k), _same_number(row["stage_l_distance"], distance_l), _same_number(row["improvement_ratio"], improvement))):
        raise ValueError(f"{label} distance formula mismatch")
    return row


def _derive_gates(metrics: Mapping[str, object], parent: Mapping[str, object], reference: Mapping[str, object]) -> dict[str, bool]:
    source = metrics["source_domain"]
    parent_source = parent["source_domain"]
    pcm = metrics["final_pcm24"]
    ref_gates = reference["gates"]
    source_physics = (
        float(source["shaft_ratio_error"]) <= 0.01
        and float(source["shaft_anchor_max_rpm"]) <= 14600.0
        and float(source["intake_whine_load_correlation"]) >= 0.82
        and float(source["bank_interval_pattern_error"]) <= 1.0
    )
    final_health = (
        pcm["sample_rate_hz"] == 48000 and pcm["channels"] == 2 and pcm["pcm_bits"] == 24
        and pcm["finite"] is True and pcm["clipping_count"] == 0
        and float(pcm["final_pcm_peak_dbfs"]) <= -1.5
    )
    crest_delta = float(source["low_band_pulse_crest_db"]) - float(parent_source["low_band_pulse_crest_db"])
    parent_roughness = float(parent_source["roughness_20_300_hz"])
    roughness_delta = (
        (float(source["roughness_20_300_hz"]) - parent_roughness) / parent_roughness
        if parent_roughness > 0.0 else float("-inf")
    )
    return {
        "exact_contract_and_reachability": metrics["pre_ptr"]["all_requested_parameters_reachable"] is True,
        "source_physics": bool(source_physics),
        "final_pcm_health": bool(final_health),
        "all_required_states_available": bool(ref_gates["all_required_states_available"]),
        "no_state_regression_over_10_percent": bool(ref_gates["no_state_worse_than_10_percent"]),
        "reference_mean_improvement_at_least_30_percent": bool(
            ref_gates["mean_improvement_at_least_30_percent"]
        ),
        "stage_c_identity_regression_within_10_percent": bool(ref_gates["stage_c_identity_regression_at_most_10_percent"]),
        "final_pcm_upper_share": bool(float(pcm["band_shares"][3]) <= 0.06 and ref_gates["stage_l_4_12khz_share_at_most_0_06"]),
        "final_pcm_upper_share_increment": bool(
            float(pcm["band_shares"][3]) - float(parent["final_pcm24"]["band_shares"][3]) <= 0.01
        ),
        "non_hellcat_isolation": bool(ref_gates["seven_non_hellcat_isolation_pass"]),
        "track_p_guard": bool(ref_gates["track_p_guard_pass"]),
        "low_band_pulse_crest_improves_parent": float(source["low_band_pulse_crest_db"]) > float(parent_source["low_band_pulse_crest_db"]),
        "low_band_pulse_crest_auxiliary_1_to_3_db": 1.0 <= crest_delta <= 3.0,
        "roughness_auxiliary_10_to_35_percent": 0.10 <= roughness_delta <= 0.35,
        "acceleration_20_250hz_absolute_error_non_expansion": bool(
            ref_gates["acceleration_20_250hz_absolute_error_non_expansion"]
        ),
        "acceleration_250_1000hz_absolute_error_strict_shrink": bool(
            ref_gates["acceleration_250_1000hz_absolute_error_strict_shrink"]
        ),
    }


def _vehicle_specific_error_components(
    metrics: Mapping[str, object], parent: Mapping[str, object], reference: Mapping[str, object],
) -> dict[str, float]:
    source = metrics["source_domain"]
    parent_source = parent["source_domain"]
    pcm = metrics["final_pcm24"]
    distances = [
        float(row["stage_l_distance"])
        for row in reference["states"].values()
        if row["availability"] == "eligible"
    ]
    return {
        # Missing reference states are already a hard-gate failure.  Keep the
        # ranking evidence finite/JSON-safe while assigning a fixed maximum
        # normalized-distance penalty when no state is eligible.
        "reference_mean_stage_l_distance": float(sum(distances) / len(distances)) if distances else 1.0,
        "shaft_ratio_error": abs(float(source["shaft_ratio_error"])),
        "whine_correlation_shortfall": max(0.0, 0.82 - float(source["intake_whine_load_correlation"])),
        "upper_share_excess": max(0.0, float(pcm["band_shares"][3]) - 0.06),
        "crest_regression": max(0.0, float(parent_source["low_band_pulse_crest_db"]) - float(source["low_band_pulse_crest_db"])),
    }


def _validate_parameters(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{label} must be a non-empty parameter mapping")
    result: dict[str, object] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str) or not raw_name:
            raise ValueError(f"{label} parameter names must be non-empty strings")
        # Compact probes may carry a scalar or the exact Candidate parameter
        # record.  Unknown record fields are rejected so the delta cannot hide
        # behind an arbitrary mapping.
        if isinstance(raw_value, Mapping):
            expected = {"value", "unit", "range", "source_level", "source", "source_scope", "verification_state"}
            record = _exact_mapping(raw_value, expected, f"{label}.{raw_name}")
            _finite_number(record["value"], f"{label}.{raw_name}.value")
            result[raw_name] = _json_copy(record)
        else:
            _finite_number(raw_value, f"{label}.{raw_name}")
            result[raw_name] = raw_value
    return result


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} must have exact keys {sorted(keys)}")
    return value


def _rank_key(record: Mapping[str, object]) -> tuple[float, float, str, str]:
    return (float(record["vehicle_specific_error"]), float(record["parameter_delta"]), _canonical(record["parameters"]), str(record["candidate_id"]))


def _parameter_delta(parameters: Mapping[str, object], parent: Mapping[str, object]) -> float:
    total = 0.0
    for name in set(parameters) | set(parent):
        current = parameters.get(name, 0.0)
        previous = parent.get(name, 0.0)
        if isinstance(current, Mapping) and "value" in current:
            current = current["value"]
        if isinstance(previous, Mapping) and "value" in previous:
            previous = previous["value"]
        total += abs(_finite_number(current, f"parameters.{name}") - _finite_number(previous, f"parent_parameters.{name}"))
    return float(total)


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _four_finite(value: object, label: str) -> list[float]:
    result = _four_finite_signed(value, label)
    if any(item < 0.0 for item in result):
        raise ValueError(f"{label} must be nonnegative")
    return result


def _four_finite_signed(value: object, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{label} must contain four values")
    return [_finite_number(item, label) for item in value]


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise ValueError(f"{label} must be SHA-256")
    return value.lower()


def _same_number(value: object, expected: float) -> bool:
    try:
        actual = _finite_number(value, "derived numeric field")
    except ValueError:
        return False
    return math.isclose(actual, expected, rel_tol=1.0e-9, abs_tol=1.0e-12)


def _same_vector(actual: Sequence[float], expected: Sequence[float]) -> bool:
    return len(actual) == len(expected) and all(math.isclose(a, b, rel_tol=1.0e-9, abs_tol=1.0e-12) for a, b in zip(actual, expected))


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate parameters must be deterministic JSON values") from exc


def _json_copy(value: Mapping[str, object]) -> dict[str, Any]:
    return json.loads(_canonical(value))


__all__ = ("MAX_CANDIDATES", "REQUIRED_HARD_GATES", "qualify_stage_l_candidates")
