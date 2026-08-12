"""Hash-bound Stage-L final-PCM reference-distance evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from ..acoustic_analysis.reference_feature_extractor import extract_reference_features
from .candidate_profiles import load_stage_l_candidate


BANDS = ((20.0, 250.0), (250.0, 1_000.0), (1_000.0, 4_000.0), (4_000.0, 12_000.0))
WINDOWS = {"idle": (0.0, 8.0), "acceleration": (8.0, 26.0), "afterfire": (36.0, 46.0)}
_TARGET_TOP_KEYS = {
    "schema", "vehicle", "display_name", "note", "provenance", "boundary",
    "band_edges_hz", "bandwidth_gate", "sources", "stock_median",
}
_STOCK_METRICS = {
    "band_shares", "spectral_flux", "modulation_depth", "modulation_peak_hz",
    "modulation_energy", "pulse_amplitude_cv", "pulse_interval_cv", "crest_factor",
    "dropout_ratio", "spectral_centroid_hz", "rms_dbfs",
}
_STOCK_KEYS = {f"{state}_{metric}" for state in WINDOWS for metric in _STOCK_METRICS}
_TARGET_PROVENANCE = (
    "B/R2 extracted from external recording; microphone/AGC/configuration dependent; "
    "not OEM calibration"
)
_TARGET_BOUNDARY = "synthetic; uncalibrated; not OEM reproduction"


def compute_stage_l_reference_distance(
    stage_k_wav_path: str | Path,
    stage_l_wav_path: str | Path,
    reference_target_path: str | Path,
    *,
    profile_path: str | Path,
    expected_stage_k_wav_sha256: str,
    expected_stage_l_wav_sha256: str,
    expected_target_sha256: str,
    expected_profile_sha256: str,
    trace_version: str,
    expected_trace_sha256: str,
    trace_evidence_path: str | Path,
    expected_trace_evidence_sha256: str,
    identity_evidence_path: str | Path,
    expected_identity_evidence_sha256: str,
    isolation_evidence_path: str | Path,
    expected_isolation_evidence_sha256: str,
    track_p_evidence_path: str | Path,
    expected_track_p_evidence_sha256: str,
) -> dict[str, object]:
    """Compare hash-bound Stage-K/Stage-L PCM24 windows to relative targets."""
    stage_k = _bind_file(stage_k_wav_path, expected_stage_k_wav_sha256, "Stage-K WAV")
    stage_l = _bind_file(stage_l_wav_path, expected_stage_l_wav_sha256, "Stage-L WAV")
    target_path = _bind_file(reference_target_path, expected_target_sha256, "reference target")
    profile = _bind_file(profile_path, expected_profile_sha256, "candidate profile")
    trace_file = _bind_file(trace_evidence_path, expected_trace_evidence_sha256, "trace evidence")
    identity_file = _bind_file(
        identity_evidence_path, expected_identity_evidence_sha256, "identity evidence"
    )
    isolation_file = _bind_file(
        isolation_evidence_path, expected_isolation_evidence_sha256, "isolation evidence"
    )
    track_p_file = _bind_file(
        track_p_evidence_path, expected_track_p_evidence_sha256, "Track-P evidence"
    )

    # Fail before the extractor can accept the wrong transport domain.
    _verify_pcm24_wav(stage_k, "Stage-K WAV")
    _verify_pcm24_wav(stage_l, "Stage-L WAV")
    candidate_profile = load_stage_l_candidate(profile)
    profile_reference = candidate_profile.payload["reference_target"]
    if not isinstance(profile_reference, Mapping) or (
        str(profile_reference.get("sha256", "")).lower() != _sha256(target_path)
    ):
        raise ValueError("reference target does not match the validated candidate profile")
    trace_evidence = _trace_evidence(
        trace_file, trace_version=trace_version, expected_trace_sha256=expected_trace_sha256
    )
    identity_evidence = _identity_evidence(identity_file)
    isolation_evidence = _isolation_evidence(isolation_file)
    track_p_evidence = _track_p_evidence(track_p_file)

    target = _load_target(target_path)
    baseline = _extract_segments(stage_k)
    candidate = _extract_segments(stage_l)
    states: dict[str, object] = {}
    improvements: list[float] = []
    eligible_upper_shares: list[float] = []
    missing: list[str] = []
    for state in WINDOWS:
        target_shares = _target_band_shares(target, state)
        if target_shares is None:
            states[state] = {
                "availability": "N/A",
                "target": None,
                "actual_stage_k": None,
                "actual_stage_l": None,
                "signed_error": None,
                "absolute_error": None,
                "stage_k_distance": None,
                "stage_l_distance": None,
                "improvement_ratio": None,
            }
            missing.append(state)
            continue
        stage_k_shares = _feature_band_shares(baseline, state, "Stage-K")
        stage_l_shares = _feature_band_shares(candidate, state, "Stage-L")
        stage_k_distance = _distance(stage_k_shares, target_shares)
        stage_l_distance = _distance(stage_l_shares, target_shares)
        improvement = (stage_k_distance - stage_l_distance) / max(stage_k_distance, 1.0e-12)
        states[state] = {
            "availability": "eligible",
            "target": list(target_shares),
            "actual_stage_k": list(stage_k_shares),
            "actual_stage_l": list(stage_l_shares),
            "signed_error": [float(a - b) for a, b in zip(stage_l_shares, target_shares)],
            "absolute_error": [float(abs(a - b)) for a, b in zip(stage_l_shares, target_shares)],
            "stage_k_distance": stage_k_distance,
            "stage_l_distance": stage_l_distance,
            "improvement_ratio": improvement,
        }
        improvements.append(improvement)
        eligible_upper_shares.append(float(stage_l_shares[3]))

    mean_improvement = float(np.mean(improvements)) if improvements else None
    max_upper_share = max(eligible_upper_shares) if eligible_upper_shares else None
    identity_ratio = float(identity_evidence["stage_c_identity_regression_ratio"])
    isolation_pass = isolation_evidence["status"] == "PASS"
    track_p_pass = track_p_evidence["status"] == "PASS"
    acceleration = states.get("acceleration")
    if isinstance(acceleration, Mapping) and acceleration.get("availability") == "eligible":
        target_accel = acceleration["target"]
        stage_k_accel = acceleration["actual_stage_k"]
        stage_l_accel = acceleration["actual_stage_l"]
        assert isinstance(target_accel, list)
        assert isinstance(stage_k_accel, list)
        assert isinstance(stage_l_accel, list)
        low_error_k = abs(float(stage_k_accel[0]) - float(target_accel[0]))
        low_error_l = abs(float(stage_l_accel[0]) - float(target_accel[0]))
        mid_error_k = abs(float(stage_k_accel[1]) - float(target_accel[1]))
        mid_error_l = abs(float(stage_l_accel[1]) - float(target_accel[1]))
        low_error_non_expansion = low_error_l <= low_error_k
        mid_error_strict_shrink = mid_error_l < mid_error_k
    else:
        low_error_non_expansion = False
        mid_error_strict_shrink = False
    gates = {
        "all_required_states_available": not missing,
        "mean_improvement_at_least_30_percent": (
            mean_improvement is not None and mean_improvement >= 0.30
        ),
        "no_state_worse_than_10_percent": bool(improvements) and all(
            value >= -0.10 for value in improvements
        ),
        "stage_c_identity_regression_at_most_10_percent": identity_ratio <= 0.10,
        "stage_l_4_12khz_share_at_most_0_06": (
            max_upper_share is not None and max_upper_share <= 0.06
        ),
        "acceleration_20_250hz_absolute_error_non_expansion": low_error_non_expansion,
        "acceleration_250_1000hz_absolute_error_strict_shrink": mid_error_strict_shrink,
        "seven_non_hellcat_isolation_pass": isolation_pass,
        "track_p_guard_pass": track_p_pass,
    }
    return {
        "schema_version": "s12-stage-l-reference-distance-1",
        "candidate_id": candidate_profile.candidate_id,
        "domain": "final_pcm24_reopened_bytes",
        "bands_hz": [list(bounds) for bounds in BANDS],
        "windows_s": {name: list(bounds) for name, bounds in WINDOWS.items()},
        "formula": "sqrt(0.25 * sum((actual_share - target_share)^2))",
        "trace_binding": {
            "trace_version": trace_evidence["trace_version"],
            "trace_sha256": trace_evidence["trace_sha256"],
            "trace_evidence_sha256": _sha256(trace_file),
        },
        "states": states,
        "missing_states": missing,
        "mean_improvement_ratio": mean_improvement,
        "stage_l_max_eligible_4_12khz_share": max_upper_share,
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "PARTIAL / AUTOMATED_GATE_FAIL",
        "hashes": {
            "stage_k_wav_sha256": _sha256(stage_k),
            "stage_l_wav_sha256": _sha256(stage_l),
            "reference_target_sha256": _sha256(target_path),
            "candidate_profile_sha256": _sha256(profile),
            "trace_evidence_sha256": _sha256(trace_file),
            "identity_evidence_sha256": _sha256(identity_file),
            "isolation_evidence_sha256": _sha256(isolation_file),
            "track_p_evidence_sha256": _sha256(track_p_file),
        },
        "protection_evidence": {
            "identity": dict(identity_evidence),
            "isolation": dict(isolation_evidence),
            "track_p": dict(track_p_evidence),
        },
        "reference_provenance": {
            "source": target.get("provenance", "B/R2 relative features"),
            "boundary": target.get("boundary", "uncalibrated; not OEM reproduction"),
            "absolute_loudness_comparison": False,
        },
    }


def _validated_sha_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is invalid")
    normalized = value.lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{label} is invalid")
    return normalized


def _bind_file(path: str | Path, expected_sha256: str, label: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} is missing")
    expected = _validated_sha_text(expected_sha256, f"{label} expected SHA-256")
    if _sha256(resolved) != expected:
        raise ValueError(f"{label} SHA-256 mismatch")
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_pcm24_wav(path: Path, label: str) -> None:
    try:
        with wave.open(str(path), "rb") as stream:
            actual = (
                stream.getframerate(), stream.getnchannels(),
                stream.getsampwidth(), stream.getcomptype(),
            )
    except (OSError, wave.Error) as exc:
        raise ValueError(f"{label} is not a valid WAV") from exc
    if actual != (48_000, 2, 3, "NONE"):
        raise ValueError(f"{label} must be 48 kHz stereo PCM24")


def _load_exact_json(path: Path, expected_keys: set[str], label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, Mapping) or set(payload) != expected_keys:
        raise ValueError(f"{label} must use the exact schema")
    return payload


def _trace_evidence(
    path: Path, *, trace_version: str, expected_trace_sha256: str,
) -> Mapping[str, object]:
    payload = _load_exact_json(
        path, {"schema_version", "status", "trace_version", "trace_sha256"}, "trace evidence"
    )
    if payload["schema_version"] != "s12-stage-l-trace-evidence-1" or payload["status"] != "PASS":
        raise ValueError("trace evidence schema/status is invalid")
    if not isinstance(trace_version, str) or not trace_version:
        raise ValueError("trace version must be non-empty")
    trace_sha = _validated_sha_text(expected_trace_sha256, "trace SHA-256")
    if payload["trace_version"] != trace_version or payload["trace_sha256"] != trace_sha:
        raise ValueError("trace binding mismatch")
    return payload


def _identity_evidence(path: Path) -> Mapping[str, object]:
    payload = _load_exact_json(
        path,
        {"schema_version", "status", "stage_c_identity_regression_ratio"},
        "identity evidence",
    )
    if payload["schema_version"] != "s12-stage-l-identity-evidence-1":
        raise ValueError("identity evidence schema/status is invalid")
    ratio = _finite_ratio(payload["stage_c_identity_regression_ratio"], "identity regression")
    expected_status = "PASS" if ratio <= 0.10 else "FAIL"
    if payload["status"] != expected_status:
        raise ValueError("identity evidence schema/status is invalid")
    return payload


def _isolation_evidence(path: Path) -> Mapping[str, object]:
    payload = _load_exact_json(
        path,
        {"schema_version", "status", "seven_non_hellcat_pcm_sha_unchanged"},
        "isolation evidence",
    )
    if payload["schema_version"] != "s12-stage-l-isolation-evidence-1":
        raise ValueError("isolation evidence schema/status is invalid")
    unchanged = _strict_bool(
        payload["seven_non_hellcat_pcm_sha_unchanged"], "isolation evidence unchanged"
    )
    expected_status = "PASS" if unchanged else "FAIL"
    if payload["status"] != expected_status:
        raise ValueError("isolation evidence schema/status is invalid")
    return payload


def _track_p_evidence(path: Path) -> Mapping[str, object]:
    payload = _load_exact_json(
        path,
        {"schema_version", "status", "passed", "total", "frozen_files", "frozen_symbols", "unchanged"},
        "Track-P evidence",
    )
    if payload["schema_version"] != "s12-stage-l-track-p-evidence-1":
        raise ValueError("Track-P evidence schema/status is invalid")
    counts = (payload["passed"], payload["total"], payload["frozen_files"], payload["frozen_symbols"])
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("Track-P evidence counts are invalid")
    unchanged = _strict_bool(payload["unchanged"], "Track-P evidence unchanged")
    passed = counts == (21, 21, 180, 2) and unchanged
    expected_status = "PASS" if passed else "FAIL"
    if payload["status"] != expected_status:
        raise ValueError("Track-P evidence schema/status is invalid")
    return payload


def _load_target(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("reference target is not valid JSON") from exc
    if not isinstance(payload, Mapping) or set(payload) != _TARGET_TOP_KEYS:
        raise ValueError("reference target must use the exact Hellcat target contract")
    if payload["schema"] != "s12.hellcat_reference_targets.v1" or payload["vehicle"] != "hellcat":
        raise ValueError("reference target vehicle/schema is not the frozen Hellcat target")
    if payload["provenance"] != _TARGET_PROVENANCE or payload["boundary"] != _TARGET_BOUNDARY:
        raise ValueError("reference target provenance/boundary is invalid")
    if payload["band_edges_hz"] != [list(bounds) for bounds in BANDS]:
        raise ValueError("reference target band edges do not match the formal distance domain")
    stock = payload["stock_median"]
    if not isinstance(stock, Mapping) or set(stock) != _STOCK_KEYS:
        raise ValueError("reference target stock_median must use the exact allowed keys")
    return payload


def _extract_segments(path: Path) -> Mapping[str, object]:
    evidence = extract_reference_features(path, segments=WINDOWS)
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("segments"), Mapping):
        raise ValueError("final PCM feature evidence is missing labelled segments")
    return evidence["segments"]  # type: ignore[return-value]


def _target_band_shares(payload: Mapping[str, object], state: str) -> tuple[float, ...] | None:
    stock = payload.get("stock_median")
    if not isinstance(stock, Mapping) or f"{state}_band_shares" not in stock:
        return None
    return _four_finite_shares(stock[f"{state}_band_shares"], f"reference {state}")


def _feature_band_shares(segments: Mapping[str, object], state: str, label: str) -> tuple[float, ...]:
    row = segments.get(state)
    if not isinstance(row, Mapping) or "band_shares" not in row:
        raise ValueError(f"{label} final PCM evidence is missing state {state}")
    return _four_finite_shares(row["band_shares"], f"{label} {state}")


def _four_finite_shares(value: object, label: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        raise ValueError(f"{label} band shares must contain four values")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) and item >= 0.0 for item in result):
        raise ValueError(f"{label} band shares must be finite and nonnegative")
    return result


def _distance(actual: Sequence[float], target: Sequence[float]) -> float:
    return float(math.sqrt(0.25 * sum((a - b) ** 2 for a, b in zip(actual, target))))


def _finite_ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise TypeError(f"{label} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return result


def _strict_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a bool")
    return bool(value)


__all__ = ("BANDS", "WINDOWS", "compute_stage_l_reference_distance")
