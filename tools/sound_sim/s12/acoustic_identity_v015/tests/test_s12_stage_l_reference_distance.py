from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _write_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance import (
    WINDOWS,
    _target_band_shares,
    compute_stage_l_reference_distance,
)


TRACE_VERSION = "stage_l_canonical_cycle_v1"
TRACE_SHA256 = "ab" * 32
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PROFILE = PACKAGE_ROOT / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
PRODUCTION_TARGET = PACKAGE_ROOT / "reference_database" / "hellcat_reference_targets.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _evidence(
    tmp_path: Path,
    *,
    identity_ratio: float = 0.05,
    isolation_pass: bool = True,
    track_p_pass: bool = True,
) -> dict[str, object]:
    trace = _json(tmp_path / "trace_evidence.json", {
        "schema_version": "s12-stage-l-trace-evidence-1",
        "status": "PASS",
        "trace_version": TRACE_VERSION,
        "trace_sha256": TRACE_SHA256,
    })
    identity = _json(tmp_path / "identity_evidence.json", {
        "schema_version": "s12-stage-l-identity-evidence-1",
        "status": "PASS" if identity_ratio <= 0.10 else "FAIL",
        "stage_c_identity_regression_ratio": identity_ratio,
    })
    isolation = _json(tmp_path / "isolation_evidence.json", {
        "schema_version": "s12-stage-l-isolation-evidence-1",
        "status": "PASS" if isolation_pass else "FAIL",
        "seven_non_hellcat_pcm_sha_unchanged": isolation_pass,
    })
    track_p = _json(tmp_path / "track_p_evidence.json", {
        "schema_version": "s12-stage-l-track-p-evidence-1",
        "status": "PASS" if track_p_pass else "FAIL",
        "passed": 21 if track_p_pass else 20,
        "total": 21,
        "frozen_files": 180,
        "frozen_symbols": 2,
        "unchanged": track_p_pass,
    })
    return {
        "trace_version": TRACE_VERSION,
        "expected_trace_sha256": TRACE_SHA256,
        "trace_evidence_path": trace,
        "expected_trace_evidence_sha256": _sha(trace),
        "identity_evidence_path": identity,
        "expected_identity_evidence_sha256": _sha(identity),
        "isolation_evidence_path": isolation,
        "expected_isolation_evidence_sha256": _sha(isolation),
        "track_p_evidence_path": track_p,
        "expected_track_p_evidence_sha256": _sha(track_p),
    }


def _inputs(tmp_path: Path, **evidence_overrides: object) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    stage_k = _write_pcm24_wav(tmp_path / "stage_k.wav", np.zeros((8_000, 2)))
    stage_l = _write_pcm24_wav(tmp_path / "stage_l.wav", np.zeros((8_000, 2)))
    target = PRODUCTION_TARGET
    profile = PRODUCTION_PROFILE
    kwargs: dict[str, object] = {
        "profile_path": profile,
        "expected_stage_k_wav_sha256": _sha(stage_k),
        "expected_stage_l_wav_sha256": _sha(stage_l),
        "expected_target_sha256": _sha(target),
        "expected_profile_sha256": _sha(profile),
        **_evidence(tmp_path, **evidence_overrides),
    }
    return stage_k, stage_l, target, profile, kwargs


def _features(shares: list[float]) -> dict[str, object]:
    return {"segments": {
        state: {"band_shares": shares, "spectral_centroid_hz": 500.0}
        for state in WINDOWS
    }}


def test_reference_distance_reopens_hash_bound_pcm24_and_uses_fixed_formula(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    target_shares = json.loads(target.read_text(encoding="utf-8"))["stock_median"]["idle_band_shares"]
    baseline = [target_shares[0] + 0.1, target_shares[1] - 0.1, *target_shares[2:]]
    candidate = [target_shares[0] + 0.05, target_shares[1] - 0.05, *target_shares[2:]]

    def fake_extract(path: Path, *, segments):
        assert dict(segments) == WINDOWS
        return _features(baseline if path.name == "stage_k.wav" else candidate)

    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        fake_extract,
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)
    row = result["states"]["idle"]
    expected_k = math.sqrt(0.25 * (0.1**2 + (-0.1) ** 2))
    expected_l = math.sqrt(0.25 * (0.05**2 + (-0.05) ** 2))
    assert result["domain"] == "final_pcm24_reopened_bytes"
    assert result["windows_s"] == {name: list(bounds) for name, bounds in WINDOWS.items()}
    assert row["stage_k_distance"] == pytest.approx(expected_k)
    assert row["stage_l_distance"] == pytest.approx(expected_l)
    assert row["improvement_ratio"] == pytest.approx(0.5)
    assert result["trace_binding"] == {
        "trace_version": TRACE_VERSION,
        "trace_sha256": TRACE_SHA256,
        "trace_evidence_sha256": kwargs["expected_trace_evidence_sha256"],
    }
    assert set(result["hashes"]) == {
        "stage_k_wav_sha256", "stage_l_wav_sha256", "reference_target_sha256",
        "candidate_profile_sha256", "trace_evidence_sha256", "identity_evidence_sha256",
        "isolation_evidence_sha256", "track_p_evidence_sha256",
    }
    assert set(result) == {
        "schema_version", "candidate_id", "domain", "bands_hz", "windows_s", "formula", "trace_binding",
        "states", "missing_states", "mean_improvement_ratio",
        "stage_l_max_eligible_4_12khz_share", "gates", "status", "hashes",
        "protection_evidence", "reference_provenance",
    }
    assert set(row) == {
        "availability", "target", "actual_stage_k", "actual_stage_l", "signed_error",
        "absolute_error", "stage_k_distance", "stage_l_distance", "improvement_ratio",
    }
    serialized = json.dumps(result).lower()
    assert "reference_lufs" not in serialized
    assert "reference_rms" not in serialized
    assert result["protection_evidence"]["identity"]["status"] == "PASS"


def test_reference_distance_fails_closed_on_any_bound_hash_drift(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    kwargs["expected_stage_k_wav_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)


def test_missing_reference_is_na_and_never_zero_filled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _target_band_shares({"stock_median": {}}, "afterfire") is None


@pytest.mark.parametrize(
    ("evidence_overrides", "gate"),
    (
        ({"identity_ratio": 0.11}, "stage_c_identity_regression_at_most_10_percent"),
        ({"isolation_pass": False}, "seven_non_hellcat_isolation_pass"),
        ({"track_p_pass": False}, "track_p_guard_pass"),
    ),
)
def test_formal_auxiliary_gates_are_derived_from_bound_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    evidence_overrides: dict[str, object],
    gate: str,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path, **evidence_overrides)
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        lambda path, *, segments: _features([0.4, 0.3, 0.2, 0.01]),
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["gates"][gate] is False


def test_final_pcm_upper_share_gate_uses_stage_l_eligible_state_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)

    def extract(path: Path, *, segments):
        upper = 0.07 if path.name == "stage_l.wav" else 0.04
        return _features([0.4, 0.3, 0.3 - upper, upper])

    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        extract,
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)
    assert result["stage_l_max_eligible_4_12khz_share"] == pytest.approx(0.07)
    assert result["gates"]["stage_l_4_12khz_share_at_most_0_06"] is False


def test_wrong_wav_format_is_rejected_before_feature_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    with wave.open(str(stage_k), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(44_100)
        stream.writeframes(b"\0" * 6_000)
    kwargs["expected_stage_k_wav_sha256"] = _sha(stage_k)
    called = False

    def forbidden_extract(path: Path, *, segments):
        nonlocal called
        called = True
        return _features([0.4, 0.3, 0.2, 0.1])

    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        forbidden_extract,
    )
    with pytest.raises(ValueError, match="48 kHz stereo PCM24"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)
    assert called is False


def test_trace_binding_mismatch_is_rejected(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    kwargs["expected_trace_sha256"] = "cd" * 32
    with pytest.raises(ValueError, match="trace"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)


@pytest.mark.parametrize("kind", ("identity", "isolation", "track_p"))
def test_protection_evidence_hash_drift_and_unknown_schema_are_rejected(
    tmp_path: Path, kind: str,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    kwargs[f"expected_{kind}_evidence_sha256"] = "00" * 32
    with pytest.raises(ValueError, match="SHA-256"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)

    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path / "schema")
    evidence_path = Path(kwargs[f"{kind}_evidence_path"])
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    _json(evidence_path, payload)
    kwargs[f"expected_{kind}_evidence_sha256"] = _sha(evidence_path)
    with pytest.raises(ValueError, match="exact schema"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)


def test_free_boolean_protection_claims_are_not_accepted(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    with pytest.raises(TypeError):
        compute_stage_l_reference_distance(
            stage_k, stage_l, target, **kwargs, non_hellcat_isolation_pass=True,
        )


def test_unrelated_profile_and_altered_target_are_rejected(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    profile_payload = json.loads(profile.read_text(encoding="utf-8"))
    profile_payload["vehicle_id"] = "ferrari_458"
    unrelated = _json(tmp_path / "unrelated_profile.json", profile_payload)
    kwargs["profile_path"] = unrelated
    kwargs["expected_profile_sha256"] = _sha(unrelated)
    with pytest.raises(ValueError, match="vehicle_id"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)

    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path / "target_case")
    altered_payload = json.loads(target.read_text(encoding="utf-8"))
    altered_payload["vehicle"] = "rx7_fd"
    altered = _json(tmp_path / "target_case" / "altered_target.json", altered_payload)
    kwargs["expected_target_sha256"] = _sha(altered)
    with pytest.raises(ValueError, match="target"):
        compute_stage_l_reference_distance(stage_k, stage_l, altered, **kwargs)


@pytest.mark.parametrize(
    ("candidate_low_delta", "candidate_mid_delta", "expected_low", "expected_mid"),
    (
        (0.03, -0.02, True, True),
        (0.05, -0.02, False, True),
        (0.03, -0.04, True, False),
    ),
)
def test_acceleration_low_and_mid_reference_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate_low_delta: float,
    candidate_mid_delta: float,
    expected_low: bool,
    expected_mid: bool,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    stock = json.loads(target.read_text(encoding="utf-8"))["stock_median"]
    target_shares = stock["acceleration_band_shares"]
    baseline = [
        target_shares[0] + 0.04,
        target_shares[1] - 0.04,
        target_shares[2],
        target_shares[3],
    ]
    candidate = [
        target_shares[0] + candidate_low_delta,
        target_shares[1] + candidate_mid_delta,
        target_shares[2],
        target_shares[3],
    ]

    def extract(path: Path, *, segments):
        return _features(baseline if path.name == "stage_k.wav" else candidate)

    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        extract,
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)
    assert result["candidate_id"] == "hellcat_stage_l_v8"
    assert result["gates"]["acceleration_20_250hz_absolute_error_non_expansion"] is expected_low
    assert result["gates"]["acceleration_250_1000hz_absolute_error_strict_shrink"] is expected_mid
