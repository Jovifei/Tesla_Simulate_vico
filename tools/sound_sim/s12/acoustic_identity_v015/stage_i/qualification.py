"""Assemble Stage-I automatic candidate qualification from explicit evidence."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _health, _read_pcm24_wav
from .candidate_search import evaluate_stage_i_hard_gates
from .candidate_profiles import StageICandidateProfile
from .perceptual_metrics import (
    compute_stage_i_perceptual_metrics,
    measure_bypass_decay,
    measure_step_response,
)
from .probes import array_sha256, candidate_profile_binding, source_render_sha256


_CANDIDATE_IDS = (
    "I6-A Balanced",
    "I6-B Whine Forward",
    "I6-C Softer Mechanical",
)
_PROBE_KEYS = (
    "sample_rate_hz",
    "boost_response",
    "boost_command",
    "bypass_response",
    "bypass_gate",
)
_PROBE_EVIDENCE_KEYS = {
    "schema_version",
    "candidate_label",
    "candidate_id",
    "candidate_sha256",
    "profile_sha256",
    "probes",
    "array_sha256",
}
_SOURCE_EVIDENCE_KEYS = {
    "schema_version",
    "candidate_label",
    "candidate_id",
    "candidate_sha256",
    "profile_sha256",
    "render_sha256",
    "final_pcm_sha256",
}
_MULTI_REFERENCE_GATE_KEYS = (
    "all_required_states_available",
    "mean_improvement_at_least_30_percent",
    "no_state_worse_than_10_percent",
)
_REFERENCE_TOP_KEYS = {
    "schema_version",
    "vehicle_id",
    "domain",
    "bands_hz",
    "windows_s",
    "candidates",
    "automatic_status",
    "reference_target_sha256",
    "provenance",
}
_REFERENCE_CANDIDATE_KEYS = {
    "states",
    "mean_improvement_ratio",
    "gates",
    "automatic_status",
}
_REFERENCE_STATE_KEYS = {
    "availability",
    "target",
    "actual_stage_h",
    "actual_stage_i",
    "signed_error",
    "absolute_error",
    "stage_h_distance",
    "stage_i_distance",
    "improvement_ratio",
    "reference_provenance",
}
_REFERENCE_FEATURE_KEYS = {"band_shares", "spectral_centroid_hz"}
_REFERENCE_BANDS = (
    (20.0, 250.0),
    (250.0, 1000.0),
    (1000.0, 4000.0),
    (4000.0, 12000.0),
)
_REFERENCE_WINDOWS = {
    "idle": (0.0, 8.0),
    "acceleration": (8.0, 26.0),
    "afterfire": (36.0, 46.0),
}
_MANIFEST_FILE_IDS = {
    "I6-A Balanced": "stage_i_v6_a_balanced_60s",
    "I6-B Whine Forward": "stage_i_v6_b_whine_forward_60s",
    "I6-C Softer Mechanical": "stage_i_v6_c_softer_mechanical_60s",
}
_MANIFEST_ROLE_IDS = {
    "I6-A Balanced": "a_balanced",
    "I6-B Whine Forward": "b_whine_forward",
    "I6-C Softer Mechanical": "c_softer_mechanical",
}
_SOURCE_METRIC_KEYS = (
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
    "low_frequency_share_40_200hz",
    "rumble_energy",
)


def qualify_stage_i_candidates(
    candidate_renders: Mapping[str, SourceRender],
    trace: VehicleStateTrace,
    final_pcm_paths: Mapping[str, str | Path],
    stage_h_render: SourceRender,
    stage_h_pcm_path: str | Path,
    reference_summary: Mapping[str, object],
    candidate_profiles: Mapping[str, StageICandidateProfile],
    response_probes: Mapping[str, Mapping[str, object]],
    final_pcm_source_evidence: Mapping[str, Mapping[str, object]],
    *,
    track_p_guard_pass: bool,
    regression_isolation_pass: bool,
    state_masks: Mapping[str, np.ndarray] | None = None,
    sample_rate_hz: int = 48000,
) -> dict[str, object]:
    """Merge source, PCM, reference and isolation evidence without rendering.

    The 30 percent final-PCM reference result is validated and passed through
    verbatim.  This function never recalculates or relaxes that independent
    distance gate, and it does not read any anonymous audition key.
    """
    if not isinstance(track_p_guard_pass, bool) or not isinstance(regression_isolation_pass, bool):
        raise ValueError("Track-P and regression isolation evidence must be booleans")
    if sample_rate_hz != 48000:
        raise ValueError("Stage-I qualification requires 48 kHz")
    automatic_reference_status = _validate_reference_summary(reference_summary)
    expected = set(_CANDIDATE_IDS)
    if set(candidate_renders) != expected or set(final_pcm_paths) != expected or set(candidate_profiles) != expected:
        raise ValueError("candidate render and final PCM candidate IDs must exactly match Stage-I A/B/C IDs")
    if set(response_probes) != expected:
        raise ValueError("response probe candidate IDs must exactly match Stage-I A/B/C IDs")
    if set(final_pcm_source_evidence) != expected:
        raise ValueError("final PCM source evidence candidate IDs must exactly match Stage-I A/B/C IDs")
    trace.validate()
    stage_h_render.validate()
    for candidate_id in _CANDIDATE_IDS:
        profile = candidate_profiles[candidate_id]
        if not isinstance(profile, StageICandidateProfile):
            raise ValueError(f"candidate profile for {candidate_id!r} must be a StageICandidateProfile")
        render = candidate_renders[candidate_id].validate()
        if render.diagnostics.get("stage_i_candidate_id") != profile.candidate_id:
            raise ValueError(f"SourceRender candidate_id binding mismatch for {candidate_id!r}")
        _validate_probe(response_probes[candidate_id], candidate_id, profile)
        _validate_pcm_source_evidence(
            final_pcm_source_evidence[candidate_id],
            candidate_id,
            profile,
            render,
            Path(final_pcm_paths[candidate_id]),
        )

    stage_h_pcm = _read_and_validate_pcm(stage_h_pcm_path, stage_h_render, sample_rate_hz)
    stage_h_metrics = compute_stage_i_perceptual_metrics(
        stage_h_render,
        trace,
        sample_rate_hz,
        state_masks=state_masks,
    )
    stage_h_metrics.update(_pcm_metrics(stage_h_pcm, sample_rate_hz))

    candidates: dict[str, object] = {}
    for candidate_id in _CANDIDATE_IDS:
        render = candidate_renders[candidate_id]
        pcm = _read_and_validate_pcm(final_pcm_paths[candidate_id], render, sample_rate_hz)
        metrics = compute_stage_i_perceptual_metrics(
            render,
            trace,
            sample_rate_hz,
            state_masks=state_masks,
            response_probe=response_probes[candidate_id],
        )
        metrics.update(_pcm_metrics(pcm, sample_rate_hz))
        metrics["track_p_guard_pass"] = track_p_guard_pass
        metrics["regression_isolation_pass"] = regression_isolation_pass
        gates = evaluate_stage_i_hard_gates(metrics, stage_h_metrics)
        candidates[candidate_id] = {
            "metrics": metrics,
            "gates": gates,
            "final_pcm_path": str(Path(final_pcm_paths[candidate_id]).resolve()),
            "binding": {
                **candidate_profile_binding(candidate_profiles[candidate_id]),
                "response_probe_evidence": dict(response_probes[candidate_id]["evidence"]),
                "final_pcm_source_evidence": dict(final_pcm_source_evidence[candidate_id]),
            },
        }

    return {
        "schema_version": "s12-stage-i-qualification-1",
        "scope": "synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction",
        "automatic_reference_status": automatic_reference_status,
        "reference_summary": dict(reference_summary),
        "reference_summary_sha256": _canonical_json_sha256(reference_summary),
        "stage_h_baseline_metrics": stage_h_metrics,
        "evidence": {
            "track_p_guard_pass": track_p_guard_pass,
            "regression_isolation_pass": regression_isolation_pass,
            "sealed_key_read": False,
        },
        "candidates": candidates,
    }


def qualify_stage_i_source_manifest(
    source_manifest: str | Path | Mapping[str, object],
    candidate_profiles: Mapping[str, StageICandidateProfile],
    response_probes: Mapping[str, Mapping[str, object]],
    reference_summary: Mapping[str, object],
    *,
    track_p_guard_pass: bool,
    regression_isolation_pass: bool,
) -> dict[str, object]:
    """Production qualification from frozen sequential-render evidence only.

    No ``SourceRender`` is accepted, reconstructed or retained.  Source-domain
    metrics and render bindings must already be content-addressed in the source
    manifest; only small deterministic response-probe arrays are evaluated.
    """
    if not isinstance(track_p_guard_pass, bool) or not isinstance(regression_isolation_pass, bool):
        raise ValueError("Track-P and regression isolation evidence must be booleans")
    automatic_reference_status = _validate_reference_summary(reference_summary)
    manifest, manifest_root = _load_source_manifest(source_manifest)
    _validate_manifest_header(manifest)
    expected = set(_CANDIDATE_IDS)
    if set(candidate_profiles) != expected:
        raise ValueError("candidate profile IDs must exactly match Stage-I A/B/C IDs")
    if set(response_probes) != expected:
        raise ValueError("response probe candidate IDs must exactly match Stage-I A/B/C IDs")
    files = manifest["files"]
    evidence = manifest["evidence"]
    roles = manifest["candidate_roles"]
    assert isinstance(files, Mapping) and isinstance(evidence, Mapping) and isinstance(roles, Mapping)

    for candidate_label in _CANDIDATE_IDS:
        profile = candidate_profiles[candidate_label]
        if not isinstance(profile, StageICandidateProfile):
            raise ValueError(f"candidate profile for {candidate_label!r} must be a StageICandidateProfile")
        role = _MANIFEST_ROLE_IDS[candidate_label]
        if roles.get(role) != profile.candidate_id:
            raise ValueError(f"source manifest candidate role mismatch for {candidate_label!r}")
        _validate_probe(response_probes[candidate_label], candidate_label, profile)

    baseline_entry = _manifest_entry(files, evidence, "stage_h_v5_baseline_60s", manifest_root)
    stage_h_metrics = _manifest_source_metrics(baseline_entry, "Stage H baseline")
    stage_h_metrics.update(_manifest_pcm_metrics(baseline_entry, "Stage H baseline"))

    candidates: dict[str, object] = {}
    for candidate_label in _CANDIDATE_IDS:
        profile = candidate_profiles[candidate_label]
        file_id = _MANIFEST_FILE_IDS[candidate_label]
        entry = _manifest_entry(files, evidence, file_id, manifest_root)
        _validate_manifest_candidate_binding(entry, candidate_label, profile)
        parameter_usage = _manifest_candidate_parameter_usage(
            entry, candidate_label, profile
        )
        metrics = _manifest_source_metrics(entry, candidate_label)
        metrics.update(_manifest_pcm_metrics(entry, candidate_label))
        probe = response_probes[candidate_label]
        probe_rate = int(probe["sample_rate_hz"])
        metrics.update(measure_step_response(
            np.asarray(probe["boost_response"], dtype=np.float64),
            np.asarray(probe["boost_command"], dtype=np.float64),
            probe_rate,
        ))
        metrics.update(measure_bypass_decay(
            np.asarray(probe["bypass_response"], dtype=np.float64),
            np.asarray(probe["bypass_gate"], dtype=np.float64),
            probe_rate,
        ))
        metrics["track_p_guard_pass"] = track_p_guard_pass
        metrics["regression_isolation_pass"] = regression_isolation_pass
        gates = evaluate_stage_i_hard_gates(metrics, stage_h_metrics)
        candidates[candidate_label] = {
            "metrics": metrics,
            "gates": gates,
            "candidate_parameter_usage": parameter_usage,
            "source_file_id": file_id,
            "binding": {
                **candidate_profile_binding(profile),
                "render_sha256": _manifest_render_sha256(entry, candidate_label),
                "final_pcm_sha256": entry["sha256"],
                "response_probe_evidence": dict(probe["evidence"]),
            },
        }
    return {
        "schema_version": "s12-stage-i-manifest-qualification-1",
        "scope": "synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction",
        "automatic_reference_status": automatic_reference_status,
        "reference_summary": dict(reference_summary),
        "reference_summary_sha256": _canonical_json_sha256(reference_summary),
        "stage_h_baseline_metrics": stage_h_metrics,
        "production_evidence": {
            "source": "sequential frozen source manifest",
            "full_render_residency_max": 0,
            "sealed_key_read": False,
            "track_p_guard_pass": track_p_guard_pass,
            "regression_isolation_pass": regression_isolation_pass,
        },
        "candidates": candidates,
    }


def _manifest_candidate_parameter_usage(
    entry: Mapping[str, object],
    candidate_label: str,
    profile: StageICandidateProfile,
) -> dict[str, object]:
    usage = entry.get("candidate_parameter_usage")
    keys = {
        "requested",
        "read",
        "configured",
        "active",
        "inactive",
        "consumed",
        "unused",
        "activity_verification",
    }
    if not isinstance(usage, Mapping) or set(usage) != keys:
        raise ValueError(
            f"candidate_parameter_usage is missing or incomplete for {candidate_label!r}"
        )
    normalized: dict[str, list[str]] = {}
    for key in keys - {"activity_verification"}:
        value = usage[key]
        if (
            not isinstance(value, (list, tuple))
            or not all(isinstance(item, str) for item in value)
            or len(set(value)) != len(value)
        ):
            raise ValueError(
                f"candidate_parameter_usage.{key} is invalid for {candidate_label!r}"
            )
        normalized[key] = sorted(value)
    requested = sorted(profile.requested_parameters())
    read = normalized["read"]
    active = set(normalized["active"])
    inactive = set(normalized["inactive"])
    if (
        normalized["requested"] != requested
        or normalized["configured"] != read
        or normalized["consumed"] != read
        or active & inactive
        or active | inactive != set(read)
        or normalized["unused"] != sorted(set(requested) - set(read))
        or usage["activity_verification"] != "MEASURED_STAGE_I_RENDER_ACTIVITY"
    ):
        raise ValueError(
            f"candidate_parameter_usage activity evidence is inconsistent for {candidate_label!r}"
        )
    return {
        **normalized,
        "activity_verification": "MEASURED_STAGE_I_RENDER_ACTIVITY",
    }


def _validate_reference_summary(summary: Mapping[str, object]) -> str:
    if set(summary) != _REFERENCE_TOP_KEYS:
        raise ValueError("reference_summary must contain exact keys")
    if summary.get("schema_version") != "s12-stage-i-reference-distance-1":
        raise ValueError("reference_summary schema_version is invalid")
    return _validate_multi_candidate_reference_summary(summary)


def _validate_multi_candidate_reference_summary(summary: Mapping[str, object]) -> str:
    if summary.get("domain") != "final_pcm":
        raise ValueError("reference_summary domain must be final_pcm")
    if summary.get("vehicle_id") != "hellcat":
        raise ValueError("reference_summary vehicle_id must be hellcat")
    _validate_fixed_pairs(summary.get("bands_hz"), _REFERENCE_BANDS, "bands_hz")
    windows = summary.get("windows_s")
    if not isinstance(windows, Mapping) or set(windows) != set(_REFERENCE_WINDOWS):
        raise ValueError("reference_summary windows_s must contain exact states")
    for state_id, expected_bounds in _REFERENCE_WINDOWS.items():
        _validate_fixed_pairs([windows[state_id]], (expected_bounds,), f"windows_s.{state_id}")
    if not _is_sha(summary.get("reference_target_sha256")):
        raise ValueError("reference_summary reference_target_sha256 must be SHA-256")
    provenance = summary.get("provenance")
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("reference_summary provenance must be a non-empty string")
    candidates = summary.get("candidates")
    if not isinstance(candidates, Mapping) or set(candidates) != set(_CANDIDATE_IDS):
        raise ValueError("reference_summary candidates must exactly match Stage-I A/B/C IDs")
    candidate_statuses: list[str] = []
    for candidate_id in _CANDIDATE_IDS:
        row = candidates[candidate_id]
        if not isinstance(row, Mapping) or set(row) != _REFERENCE_CANDIDATE_KEYS:
            raise ValueError(f"reference_summary candidate {candidate_id!r} must contain exact keys")
        states = row["states"]
        if not isinstance(states, Mapping) or set(states) != set(_REFERENCE_WINDOWS):
            raise ValueError(f"reference_summary candidate {candidate_id!r} states must contain exact keys")
        improvements = [
            value
            for state_id in _REFERENCE_WINDOWS
            if (value := _validate_reference_state(states[state_id], candidate_id, state_id)) is not None
        ]
        expected_mean = float(np.mean(improvements)) if improvements else None
        _validate_optional_number(row["mean_improvement_ratio"], expected_mean, f"candidate {candidate_id!r} mean_improvement_ratio")
        gates = row["gates"]
        if not isinstance(gates, Mapping) or set(gates) != set(_MULTI_REFERENCE_GATE_KEYS):
            raise ValueError(f"reference_summary candidate {candidate_id!r} gates must contain exact keys")
        expected_gates = {
            "all_required_states_available": len(improvements) == len(_REFERENCE_WINDOWS),
            "mean_improvement_at_least_30_percent": expected_mean is not None and expected_mean >= 0.30,
            "no_state_worse_than_10_percent": all(value >= -0.10 for value in improvements),
        }
        for key, expected_value in expected_gates.items():
            if not isinstance(gates[key], bool) or gates[key] is not expected_value:
                raise ValueError(f"reference_summary candidate {candidate_id!r} gate {key!r} does not match recomputed value")
        expected = "PASS" if all(gates[key] for key in _MULTI_REFERENCE_GATE_KEYS) else "PARTIAL / AUTOMATED_GATE_FAIL"
        status = row["automatic_status"]
        if status != expected:
            raise ValueError(f"reference_summary candidate {candidate_id!r} status does not match gates")
        candidate_statuses.append(expected)
    expected_overall = "PASS" if all(status == "PASS" for status in candidate_statuses) else "PARTIAL / AUTOMATED_GATE_FAIL"
    if summary.get("automatic_status") != expected_overall:
        raise ValueError("reference_summary automatic_status does not match candidate gates")
    return expected_overall


def _validate_reference_state(row: object, candidate_id: str, state_id: str) -> float | None:
    label = f"reference_summary candidate {candidate_id!r} state {state_id!r}"
    if not isinstance(row, Mapping) or set(row) != _REFERENCE_STATE_KEYS:
        raise ValueError(f"{label} must contain exact keys")
    availability = row["availability"]
    if availability == "not_available":
        if any(row[key] is not None for key in _REFERENCE_STATE_KEYS - {"availability"}):
            raise ValueError(f"{label} not_available fields must all be null")
        return None
    if availability != "eligible":
        raise ValueError(f"{label} availability is invalid")
    target = _validate_reference_feature(row["target"], f"{label} target")
    actual_h = _validate_reference_feature(row["actual_stage_h"], f"{label} actual_stage_h")
    actual_i = _validate_reference_feature(row["actual_stage_i"], f"{label} actual_stage_i")
    provenance = row["reference_provenance"]
    if not isinstance(provenance, Mapping) or not provenance:
        raise ValueError(f"{label} reference_provenance must be a non-empty object")
    signed_error = [a - t for a, t in zip(actual_i, target, strict=True)]
    absolute_error = [abs(value) for value in signed_error]
    _validate_number_list(row["signed_error"], signed_error, f"{label} signed_error")
    _validate_number_list(row["absolute_error"], absolute_error, f"{label} absolute_error")
    distance_h = _reference_distance(actual_h, target)
    distance_i = _reference_distance(actual_i, target)
    improvement = (distance_h - distance_i) / max(distance_h, 1.0e-12)
    _validate_number(row["stage_h_distance"], distance_h, f"{label} stage_h_distance")
    _validate_number(row["stage_i_distance"], distance_i, f"{label} stage_i_distance")
    _validate_number(row["improvement_ratio"], improvement, f"{label} improvement_ratio")
    return improvement


def _validate_reference_feature(value: object, label: str) -> list[float]:
    if not isinstance(value, Mapping) or set(value) != _REFERENCE_FEATURE_KEYS:
        raise ValueError(f"{label} must contain exact keys")
    shares = value["band_shares"]
    if not isinstance(shares, (list, tuple)) or len(shares) != 4:
        raise ValueError(f"{label} band_shares must contain four finite values")
    output = [_finite_number(item, f"{label} band_shares") for item in shares]
    _finite_number(value["spectral_centroid_hz"], f"{label} spectral_centroid_hz")
    return output


def _validate_fixed_pairs(value: object, expected: tuple[tuple[float, float], ...], label: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != len(expected):
        raise ValueError(f"reference_summary {label} is invalid")
    for actual_pair, expected_pair in zip(value, expected, strict=True):
        if not isinstance(actual_pair, (list, tuple)) or len(actual_pair) != 2:
            raise ValueError(f"reference_summary {label} is invalid")
        for actual, expected_value in zip(actual_pair, expected_pair, strict=True):
            _validate_number(actual, expected_value, f"reference_summary {label}")


def _validate_number_list(value: object, expected: list[float], label: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != len(expected):
        raise ValueError(f"{label} does not match recomputed value")
    for actual, expected_value in zip(value, expected, strict=True):
        _validate_number(actual, expected_value, label)


def _validate_optional_number(value: object, expected: float | None, label: str) -> None:
    if expected is None:
        if value is not None:
            raise ValueError(f"{label} must be null")
        return
    _validate_number(value, expected, label)


def _validate_number(value: object, expected: float, label: str) -> None:
    actual = _finite_number(value, label)
    if not math.isclose(actual, expected, rel_tol=1.0e-9, abs_tol=1.0e-12):
        raise ValueError(f"{label} does not match recomputed value")


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _reference_distance(actual: list[float], target: list[float]) -> float:
    return math.sqrt(0.25 * sum((a - t) ** 2 for a, t in zip(actual, target, strict=True)))


def _canonical_json_sha256(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_probe(
    probe: Mapping[str, object],
    candidate_label: str,
    profile: StageICandidateProfile,
) -> None:
    if set(probe) != set(_PROBE_KEYS) | {"evidence"}:
        raise ValueError(f"response probe for {candidate_label!r} must contain exact required fields")
    rate = probe["sample_rate_hz"]
    if not isinstance(rate, int) or rate <= 0:
        raise ValueError(f"response probe for {candidate_label!r} requires a positive integer sample rate")
    lengths: set[int] = set()
    for key in _PROBE_KEYS[1:]:
        value = np.asarray(probe[key], dtype=np.float64)
        if value.ndim != 1 or value.size < 3 or not np.all(np.isfinite(value)):
            raise ValueError(f"response probe field {key!r} for {candidate_label!r} must be finite one-dimensional data")
        lengths.add(value.size)
    if len(lengths) != 1:
        raise ValueError(f"response probe arrays for {candidate_label!r} must have equal lengths")
    evidence = probe["evidence"]
    if not isinstance(evidence, Mapping) or set(evidence) != _PROBE_EVIDENCE_KEYS:
        raise ValueError(f"response probe evidence for {candidate_label!r} is incomplete")
    if evidence["schema_version"] != "s12-stage-i-response-probe-evidence-1":
        raise ValueError("response probe evidence schema_version is invalid")
    _validate_candidate_binding(evidence, candidate_label, profile, "response probe")
    hashes = evidence["array_sha256"]
    if not isinstance(hashes, Mapping) or set(hashes) != set(_PROBE_KEYS[1:]):
        raise ValueError("response probe array SHA evidence is incomplete")
    for key in _PROBE_KEYS[1:]:
        expected = array_sha256(np.asarray(probe[key], dtype=np.float64))
        if hashes[key] != expected:
            raise ValueError(f"response probe array SHA mismatch for {candidate_label!r}/{key}")
    probe_renders = evidence["probes"]
    if not isinstance(probe_renders, Mapping) or set(probe_renders) != {"boost", "lift"}:
        raise ValueError("response probe render evidence must contain boost and lift")
    for probe_name, details in probe_renders.items():
        if not isinstance(details, Mapping) or set(details) != {"trace_sha256", "render_sha256", "stem_sha256"}:
            raise ValueError(f"response probe {probe_name!r} binding is incomplete")
        if not _is_sha(details["trace_sha256"]) or not _is_sha(details["render_sha256"]):
            raise ValueError(f"response probe {probe_name!r} trace/render SHA is invalid")
        stems = details["stem_sha256"]
        if not isinstance(stems, Mapping) or set(stems) != {"blower", "blower_bypass_release"} or not all(_is_sha(value) for value in stems.values()):
            raise ValueError(f"response probe {probe_name!r} stem SHA evidence is invalid")


def _validate_pcm_source_evidence(
    evidence: Mapping[str, object],
    candidate_label: str,
    profile: StageICandidateProfile,
    render: SourceRender,
    path: Path,
) -> None:
    if set(evidence) != _SOURCE_EVIDENCE_KEYS:
        raise ValueError(f"final PCM source evidence for {candidate_label!r} is incomplete")
    if evidence["schema_version"] != "s12-stage-i-final-pcm-source-evidence-1":
        raise ValueError("final PCM source evidence schema_version is invalid")
    _validate_candidate_binding(evidence, candidate_label, profile, "final PCM source evidence")
    if evidence["render_sha256"] != source_render_sha256(render):
        raise ValueError(f"final PCM source render SHA mismatch for {candidate_label!r}")
    if not path.is_file() or evidence["final_pcm_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f"final PCM byte SHA mismatch for {candidate_label!r}")


def _validate_candidate_binding(
    evidence: Mapping[str, object],
    candidate_label: str,
    profile: StageICandidateProfile,
    label: str,
) -> None:
    expected = candidate_profile_binding(profile)
    if evidence.get("candidate_label") != candidate_label:
        raise ValueError(f"{label} candidate_label mismatch for {candidate_label!r}")
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ValueError(f"{label} {key} mismatch for {candidate_label!r}")


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _load_source_manifest(
    source: str | Path | Mapping[str, object],
) -> tuple[Mapping[str, object], Path]:
    if isinstance(source, Mapping):
        return source, Path.cwd()
    path = Path(source).resolve()
    if not path.is_file():
        raise ValueError(f"source manifest does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("source manifest root must be an object")
    return payload, path.parent


def _validate_manifest_header(manifest: Mapping[str, object]) -> None:
    for key in ("package_id", "status", "sealed_key_read", "files", "evidence", "candidate_roles"):
        if key not in manifest:
            raise ValueError(f"source manifest missing required field {key!r}")
    if manifest["status"] != "SOURCE_EVIDENCE_READY" or manifest["sealed_key_read"] is not False:
        raise ValueError("source manifest is not frozen unsealed source evidence")
    for key in ("files", "evidence", "candidate_roles"):
        if not isinstance(manifest[key], Mapping):
            raise ValueError(f"source manifest {key} must be a mapping")
    files = manifest["files"]
    evidence = manifest["evidence"]
    assert isinstance(files, Mapping) and isinstance(evidence, Mapping)
    required = {"stage_h_v5_baseline_60s", *_MANIFEST_FILE_IDS.values()}
    if not required.issubset(files) or not required.issubset(evidence):
        raise ValueError("source manifest lacks qualification source entries")


def _manifest_entry(
    files: Mapping[str, object],
    evidence: Mapping[str, object],
    file_id: str,
    manifest_root: Path,
) -> dict[str, object]:
    entry = evidence.get(file_id)
    if not isinstance(entry, Mapping):
        raise ValueError(f"source manifest evidence is missing for {file_id!r}")
    file_value = files.get(file_id)
    if not isinstance(file_value, str) or not file_value:
        raise ValueError(f"source manifest file path is invalid for {file_id!r}")
    path = Path(file_value)
    if not path.is_absolute():
        path = manifest_root / path
    path = path.resolve()
    entry_path = entry.get("path")
    if not isinstance(entry_path, str) or Path(entry_path).resolve() != path:
        raise ValueError(f"source manifest path binding mismatch for {file_id!r}")
    sha = entry.get("sha256")
    if not _is_sha(sha):
        raise ValueError(f"source manifest PCM SHA is invalid for {file_id!r}")
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError(f"source manifest PCM byte SHA mismatch for {file_id!r}")
    return dict(entry)


def _validate_manifest_candidate_binding(
    entry: Mapping[str, object],
    candidate_label: str,
    profile: StageICandidateProfile,
) -> None:
    expected = candidate_profile_binding(profile)
    nested = entry.get("profile_binding")
    if nested is None:
        for key, value in expected.items():
            if entry.get(key) != value:
                raise ValueError(f"source manifest {key} mismatch for {candidate_label!r}")
    else:
        if not isinstance(nested, Mapping):
            raise ValueError(f"source manifest profile_binding is invalid for {candidate_label!r}")
        mapped = {
            "candidate_id": nested.get("candidate_id"),
            "candidate_sha256": nested.get("profile_sha256"),
            "profile_sha256": nested.get("profile_file_sha256"),
        }
        for key, value in expected.items():
            if mapped.get(key) != value:
                raise ValueError(f"source manifest nested {key} mismatch for {candidate_label!r}")
    _manifest_render_sha256(entry, candidate_label)


def _manifest_render_sha256(entry: Mapping[str, object], candidate_label: str) -> str:
    value = entry.get("source_render_sha256", entry.get("render_sha256"))
    if not _is_sha(value):
        raise ValueError(f"source manifest render SHA is invalid for {candidate_label!r}")
    return str(value)


def _manifest_source_metrics(entry: Mapping[str, object], label: str) -> dict[str, float]:
    source = entry.get("source_metrics")
    if not isinstance(source, Mapping):
        raise ValueError(f"source_metrics are missing for {label}")
    output: dict[str, float] = {}
    for key in _SOURCE_METRIC_KEYS:
        output[key] = _finite_manifest_number(source, key, f"source_metrics for {label}")
    return output


def _manifest_pcm_metrics(entry: Mapping[str, object], label: str) -> dict[str, object]:
    health = entry.get("health")
    loudness = entry.get("loudness")
    if not isinstance(health, Mapping) or not isinstance(loudness, Mapping):
        raise ValueError(f"PCM health/loudness evidence is missing for {label}")
    if health.get("finite") is not True:
        raise ValueError(f"PCM finite evidence must be exact true for {label}")
    if health.get("sample_rate_hz") != 48000 or health.get("channels") != 2 or health.get("pcm") != "PCM_24":
        raise ValueError(f"PCM format evidence is invalid for {label}")
    clipping = health.get("clipping_count")
    loudness_clipping = loudness.get("clipping_count")
    if isinstance(clipping, bool) or not isinstance(clipping, int) or isinstance(loudness_clipping, bool) or not isinstance(loudness_clipping, int):
        raise ValueError(f"PCM clipping evidence must use integers for {label}")
    if clipping != loudness_clipping:
        raise ValueError(f"PCM health/loudness clipping evidence disagrees for {label}")
    peak = _finite_manifest_number(loudness, "peak_dbfs", f"loudness for {label}")
    health_peak = _finite_manifest_number(health, "peak_dbfs", f"health for {label}")
    if abs(peak - health_peak) > 1e-9:
        raise ValueError(f"PCM health/loudness peak evidence disagrees for {label}")
    return {
        "whole_cycle_lufs": _finite_manifest_number(loudness, "integrated_lufs", f"loudness for {label}"),
        "rms_dbfs": _finite_manifest_number(loudness, "rms_dbfs", f"loudness for {label}"),
        "peak_dbfs": peak,
        "crest_factor_db": _finite_manifest_number(loudness, "crest_factor_db", f"loudness for {label}"),
        "clipping_count": clipping,
        "sample_rate_hz": 48000,
        "channels": 2,
        "pcm_bits": 24,
        "finite": True,
        "pcm_format": "PCM_24",
    }


def _finite_manifest_number(source: Mapping[str, object], key: str, label: str) -> float:
    value = source.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} field {key!r} must be finite")
    return float(value)


def _read_and_validate_pcm(path_value: str | Path, render: SourceRender, sample_rate_hz: int) -> np.ndarray:
    path = Path(path_value)
    if not path.is_file():
        raise ValueError(f"final PCM file does not exist: {path}")
    pcm = _read_pcm24_wav(path)
    if pcm.shape[0] != render.pressure.shape[0]:
        raise ValueError(f"final PCM and SourceRender lengths differ: {path}")
    duration = (pcm.shape[0] - 1) / sample_rate_hz
    if duration < 0.0:
        raise ValueError(f"final PCM is empty: {path}")
    return pcm


def _pcm_metrics(pcm: np.ndarray, sample_rate_hz: int) -> dict[str, object]:
    health = _health(pcm)
    loudness = measure_loudness(pcm, sample_rate_hz)
    if not math.isfinite(float(loudness.integrated_lufs)):
        raise ValueError("final PCM integrated LUFS must be finite")
    return {
        "whole_cycle_lufs": float(loudness.integrated_lufs),
        "rms_dbfs": float(loudness.rms_dbfs),
        "peak_dbfs": float(loudness.peak_dbfs),
        "crest_factor_db": float(loudness.crest_factor_db),
        "clipping_count": int(loudness.clipping_count),
        "sample_rate_hz": int(health["sample_rate_hz"]),
        "channels": int(health["channels"]),
        "pcm_bits": 24,
        "finite": bool(health["finite"]),
        "pcm_format": str(health["pcm"]),
        "frames": int(health["frames"]),
    }


__all__ = ("qualify_stage_i_candidates", "qualify_stage_i_source_manifest")
