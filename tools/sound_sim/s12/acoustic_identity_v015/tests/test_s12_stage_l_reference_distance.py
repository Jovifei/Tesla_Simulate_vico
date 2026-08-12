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
    **_ignored: object,
) -> dict[str, object]:
    trace = _json(tmp_path / "trace_evidence.json", {
        "schema_version": "s12-stage-l-trace-evidence-1",
        "status": "PASS",
        "trace_version": TRACE_VERSION,
        "trace_sha256": TRACE_SHA256,
    })
    return {
        "trace_version": TRACE_VERSION,
        "expected_trace_sha256": TRACE_SHA256,
        "trace_evidence_path": trace,
        "expected_trace_evidence_sha256": _sha(trace),
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
        "candidate_profile_sha256", "trace_evidence_sha256",
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
    assert result["protection_evidence"]["identity"]["status"] == "NOT_AVAILABLE"
    assert result["protection_evidence"]["isolation"]["status"] == "NOT_AVAILABLE"
    assert result["protection_evidence"]["track_p"]["status"] == "PASS"
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


def test_reference_distance_fails_closed_on_any_bound_hash_drift(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    kwargs["expected_stage_k_wav_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)


def test_missing_reference_is_na_and_never_zero_filled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _target_band_shares({"stock_median": {}}, "afterfire") is None


def test_unavailable_pcm_state_window_is_na_but_eligible_mean_remains_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    stock = json.loads(target.read_text(encoding="utf-8"))["stock_median"]

    def fake_extract(path: Path, *, segments):
        rows: dict[str, object] = {}
        for state in WINDOWS:
            target_shares = stock[f"{state}_band_shares"]
            baseline = [target_shares[0] + 0.1, target_shares[1] - 0.1, *target_shares[2:]]
            candidate = [target_shares[0] + 0.05, target_shares[1] - 0.05, *target_shares[2:]]
            if state == "afterfire":
                continue
            rows[state] = {"band_shares": baseline if path.name == "stage_k.wav" else candidate}
        return {"segments": rows}

    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        fake_extract,
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)

    assert result["states"]["afterfire"] == {
        "availability": "N/A", "target": None, "actual_stage_k": None,
        "actual_stage_l": None, "signed_error": None, "absolute_error": None,
        "stage_k_distance": None, "stage_l_distance": None, "improvement_ratio": None,
    }
    assert result["mean_improvement_ratio"] == pytest.approx(0.5)
    assert result["gates"]["mean_improvement_at_least_30_percent"] is True
    assert result["gates"]["all_required_states_available"] is False
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


def test_protection_gates_are_derived_only_from_existing_repository_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        lambda path, *, segments: _features([0.4, 0.3, 0.2, 0.01]),
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["gates"]["stage_c_identity_regression_at_most_10_percent"] is False
    assert result["gates"]["seven_non_hellcat_isolation_pass"] is False
    assert result["gates"]["track_p_guard_pass"] is True


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
    wrapper = _json(tmp_path / f"{kind}.json", {"status": "PASS"})
    kwargs[f"{kind}_evidence_path"] = wrapper
    kwargs[f"expected_{kind}_evidence_sha256"] = _sha(wrapper)
    with pytest.raises(ValueError, match="caller-generated"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)


def test_free_boolean_protection_claims_are_not_accepted(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    with pytest.raises(TypeError):
        compute_stage_l_reference_distance(
            stage_k, stage_l, target, **kwargs, non_hellcat_isolation_pass=True,
        )


def test_missing_identity_and_isolation_evidence_is_partial_not_fabricated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    for name in (
        "identity_evidence_path", "expected_identity_evidence_sha256",
        "isolation_evidence_path", "expected_isolation_evidence_sha256",
        "track_p_evidence_path", "expected_track_p_evidence_sha256",
    ):
        kwargs.pop(name, None)

    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        lambda *_args, **_kwargs: _features([0.4, 0.4, 0.15, 0.05]),
    )
    result = compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)

    assert result["status"].startswith("PARTIAL")
    assert result["protection_evidence"]["identity"]["status"] == "NOT_AVAILABLE"
    assert result["protection_evidence"]["isolation"]["status"] == "NOT_AVAILABLE"


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


def test_old_standalone_pass_protection_json_is_rejected(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    old = _json(tmp_path / "standalone_identity.json", {
        "schema_version": "s12-stage-l-identity-evidence-1",
        "status": "PASS", "stage_c_identity_regression_ratio": 0.05,
    })
    kwargs["identity_evidence_path"] = old
    kwargs["expected_identity_evidence_sha256"] = _sha(old)

    with pytest.raises(ValueError, match="caller-generated"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)


def test_protection_receipt_rejects_bound_repository_source_hash_drift(tmp_path: Path) -> None:
    stage_k, stage_l, target, profile, kwargs = _inputs(tmp_path)
    source = PACKAGE_ROOT.parents[3] / "tasks/reports/runtime/s12-stage-k-four-vehicle-repair-v1/stage_k_test_evidence.json"
    receipt = _json(tmp_path / "isolation_receipt.json", {
        "schema_version": "s12-stage-l-produced-isolation-evidence-1",
        "producer": "stage_l.regression_isolation.reference_gate",
        "source_artifact": str(source), "source_artifact_sha256": "0" * 64,
        "status": "PASS", "seven_non_hellcat_pcm_sha_unchanged": True,
    })
    kwargs["isolation_evidence_path"] = receipt
    kwargs["expected_isolation_evidence_sha256"] = _sha(receipt)

    with pytest.raises(ValueError, match="caller-generated"):
        compute_stage_l_reference_distance(stage_k, stage_l, target, **kwargs)

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
