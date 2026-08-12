from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.scripts import qualify_stage_l_hellcat as qualifier
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_search import (
    MAX_CANDIDATES,
    REQUIRED_HARD_GATES,
    qualify_stage_l_candidates,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _perceptual(
    *, crest_db: float, upper_share: float = 0.05, wav_sha256: str | None = None,
    requested: list[str] | None = None,
) -> dict[str, object]:
    source = {
        name: 0.0 for name in (
            "shaft_ratio_error", "shaft_max_rpm", "intake_whine_load_correlation",
            "intake_to_exhaust_ratio_db", "gear_to_aero_ratio", "intake_transfer_energy_ratio",
            "bypass_event_count", "boost_attack_10_90_s", "boost_release_90_10_s",
            "bypass_decay_90_10_s", "order_ridge_continuity", "tone_prominence_ratio",
            "firing_event_angle_error_samples", "bank_interval_pattern_error", "fourth_order_presence",
            "20_80_hz_share", "80_160_hz_share", "160_250_hz_share", "250_1000_hz_share",
            "low_band_pulse_crest_db", "low_band_envelope_cv", "fluctuation_below_20_hz",
            "roughness_20_300_hz", "modulation_peak_hz", "bank_to_bank_delay",
        )
    }
    source.update({
        "shaft_ratio_error": 0.005, "shaft_max_rpm": 14_396.0,
        "shaft_anchor_max_rpm": 14_396.0,
        "intake_whine_load_correlation": 0.90, "bank_interval_pattern_error": 0.0,
        "low_band_pulse_crest_db": crest_db,
        "roughness_20_300_hz": 1.0 if crest_db == 8.0 else (1.20 if crest_db > 8.0 else 0.80),
    })
    requested = ["source.x"] if requested is None else requested
    return {
        "schema_version": "s12-stage-l-perceptual-metrics-1",
        "domains": {
            "source_domain": "actual SourceRender arrays and detected events",
            "pre_ptr": "actual named transient arrays before common Pre-PTR EQ",
            "final_pcm24": "reopened PCM24 WAV bytes",
        },
        "source_domain": source,
        "pre_ptr": {
            "shift_dip_db": 3.0, "shift_settling_s": 0.2, "shift_overshoot_db": 0.5,
            "named_transient_energy": 1.0, "named_transient_event_count": 3,
            "domain": "actual named transient arrays before common Pre-PTR EQ",
            "candidate_parameter_usage": {
                "requested": requested, "read": requested, "configured": requested,
                "active": requested, "inactive": [], "unused": [],
            },
            "all_requested_parameters_reachable": True,
        },
        "final_pcm24": {
            "wav_sha256": wav_sha256 or _sha("candidate" if crest_db != 8.0 else "parent"),
            "sample_rate_hz": 48_000,
            "channels": 2,
            "pcm_bits": 24,
            "finite": True,
            "final_pcm_lufs": -16.0,
            "final_pcm_peak_dbfs": -1.6,
            "clipping_count": 0,
            "band_shares": [0.40, 0.42, 0.13, upper_share],
            "review_requested_gain_db": 0.0,
            "review_actual_gain_db": 0.0,
            "headroom_limited": False,
        },
    }


def _reference(*, pass_all: bool = True, candidate_id: str = "candidate") -> dict[str, object]:
    improvement = 0.31 if pass_all else 0.29
    target = [0.4, 0.35, 0.2, 0.05]
    stage_k = [0.5, 0.25, 0.2, 0.05]
    scale = 1.0 - improvement
    stage_l = [b + scale * (a - b) for a, b in zip(stage_k, target)]
    distance_k = (0.25 * sum((a - b) ** 2 for a, b in zip(stage_k, target))) ** 0.5
    distance_l = (0.25 * sum((a - b) ** 2 for a, b in zip(stage_l, target))) ** 0.5
    signed = [a - b for a, b in zip(stage_l, target)]
    state = {
        "availability": "eligible", "target": target,
        "actual_stage_k": stage_k, "actual_stage_l": stage_l,
        "signed_error": signed, "absolute_error": [abs(value) for value in signed],
        "stage_k_distance": distance_k, "stage_l_distance": distance_l,
        "improvement_ratio": improvement,
    }
    gates = {
        "all_required_states_available": True,
        "mean_improvement_at_least_30_percent": pass_all,
        "no_state_worse_than_10_percent": True,
    }
    return {
        "schema_version": "s12-stage-l-reference-distance-1",
        "candidate_id": candidate_id,
        "domain": "final_pcm24_reopened_bytes",
        "bands_hz": [[20.0, 250.0], [250.0, 1000.0], [1000.0, 4000.0], [4000.0, 12000.0]],
        "windows_s": {"idle": [0.0, 8.0], "acceleration": [8.0, 26.0], "afterfire": [36.0, 46.0]},
        "formula": "sqrt(0.25 * sum((actual_share - target_share)^2))",
        "states": {name: dict(state) for name in ("idle", "acceleration", "afterfire")},
        "missing_states": [], "mean_improvement_ratio": improvement,
        "stage_l_max_eligible_4_12khz_share": stage_l[3],
        "trace_binding": {"trace_version": "canonical-v1", "trace_sha256": _sha("trace"), "trace_evidence_sha256": _sha("trace-evidence")},
        "protection_evidence": {
            "identity": {"schema_version": "s12-stage-l-identity-evidence-1", "status": "PASS", "stage_c_identity_regression_ratio": 0.05},
            "isolation": {"schema_version": "s12-stage-l-isolation-evidence-1", "status": "PASS", "seven_non_hellcat_pcm_sha_unchanged": True},
            "track_p": {"schema_version": "s12-stage-l-track-p-evidence-1", "status": "PASS", "passed": 21, "total": 21, "frozen_files": 180, "frozen_symbols": 2, "unchanged": True},
        },
        "gates": {
            **gates,
            "stage_c_identity_regression_at_most_10_percent": True,
            "stage_l_4_12khz_share_at_most_0_06": stage_l[3] <= 0.06,
            "acceleration_20_250hz_absolute_error_non_expansion": True,
            "acceleration_250_1000hz_absolute_error_strict_shrink": True,
            "seven_non_hellcat_isolation_pass": True,
            "track_p_guard_pass": True,
        },
        "status": "PASS" if pass_all else "PARTIAL / AUTOMATED_GATE_FAIL",
        "hashes": {
            "stage_k_wav_sha256": _sha("parent"), "stage_l_wav_sha256": _sha("candidate"),
            "reference_target_sha256": _sha("target"), "candidate_profile_sha256": _sha("profile"),
            "trace_evidence_sha256": _sha("trace-evidence"), "identity_evidence_sha256": _sha("identity-evidence"),
            "isolation_evidence_sha256": _sha("isolation-evidence"), "track_p_evidence_sha256": _sha("track-p-evidence"),
        },
        "reference_provenance": {
            "source": "B/R2 relative features", "boundary": "uncalibrated; not OEM reproduction",
            "absolute_loudness_comparison": False,
        },
    }


def _record(candidate_id: str, *, pass_all: bool, delta: float = 0.1) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "parameters": {"source.x": delta},
        "probe_duration_s": 10.0,
        "full_render_residency_max": 1,
        "metrics": _perceptual(crest_db=9.0 if pass_all else 7.0),
        "reference_distance": _reference(pass_all=pass_all, candidate_id=candidate_id),
    }


def test_search_derives_exact_hard_gates_from_nested_evidence_and_is_deterministic() -> None:
    a = _record("a", pass_all=True, delta=0.2)
    b = _record("b", pass_all=True, delta=0.1)
    bad = _record("bad", pass_all=False, delta=0.0)
    parent = _perceptual(crest_db=8.0)
    first = qualify_stage_l_candidates([a, bad, b], parent_parameters={"source.x": 0.0}, parent_metrics=parent)
    second = qualify_stage_l_candidates([b, bad, a], parent_parameters={"source.x": 0.0}, parent_metrics=parent)
    assert first == second
    assert first["selected_candidate_id"] == "b"
    assert first["status"] == "PASS"
    assert set(first["evaluated"][0]["hard_gates"]) == set(REQUIRED_HARD_GATES)
    assert first["full_render_residency_max"] == 1


def test_search_accepts_real_extractor_band_shares_with_out_of_band_energy() -> None:
    row = _record("real-band-domain", pass_all=True)
    row["metrics"]["final_pcm24"]["band_shares"] = [0.38, 0.34, 0.12, 0.05]
    result = qualify_stage_l_candidates(
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0),
    )
    assert result["selected_candidate_id"] == "real-band-domain"


def test_actual_reachability_false_is_partial_not_self_asserted_pass() -> None:
    row = _record("unreachable", pass_all=True)
    usage = row["metrics"]["pre_ptr"]["candidate_parameter_usage"]
    usage["read"] = []
    usage["configured"] = []
    usage["active"] = []
    usage["unused"] = ["source.x"]
    row["metrics"]["pre_ptr"]["all_requested_parameters_reachable"] = False
    result = qualify_stage_l_candidates(
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0),
    )
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["evaluated"][0]["hard_gates"]["exact_contract_and_reachability"] is False


def test_missing_reference_actual_na_schema_is_accepted_as_partial() -> None:
    row = _record("missing-reference", pass_all=True)
    row["reference_distance"]["states"]["afterfire"] = {
        "availability": "N/A", "target": None, "actual_stage_k": None, "actual_stage_l": None,
        "signed_error": None, "absolute_error": None, "stage_k_distance": None,
        "stage_l_distance": None, "improvement_ratio": None,
    }
    row["reference_distance"]["missing_states"] = ["afterfire"]
    row["reference_distance"]["gates"]["all_required_states_available"] = False
    row["reference_distance"]["status"] = "PARTIAL / AUTOMATED_GATE_FAIL"
    result = qualify_stage_l_candidates(
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0),
    )
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


@pytest.mark.parametrize("parameters", ({}, {"wrong.x": 0.1}))
def test_parameters_are_bound_exactly_to_actual_requested_usage(parameters: dict[str, float]) -> None:
    row = _record("parameter-drift", pass_all=True)
    row["parameters"] = parameters
    with pytest.raises(ValueError, match="requested|parameter"):
        qualify_stage_l_candidates(
            [row], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0),
        )


def test_vehicle_specific_error_is_derived_from_actual_evidence_with_breakdown() -> None:
    better = _record("better", pass_all=True, delta=0.2)
    worse = _record("worse", pass_all=True, delta=0.1)
    worse["metrics"]["source_domain"]["shaft_ratio_error"] = 0.009
    result = qualify_stage_l_candidates(
        [worse, better], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0),
    )
    assert result["selected_candidate_id"] == "better"
    records = {item["candidate_id"]: item for item in result["evaluated"]}
    assert set(records["better"]["vehicle_specific_error_components"]) == {
        "reference_mean_stage_l_distance", "shaft_ratio_error", "whine_correlation_shortfall",
        "upper_share_excess", "crest_regression",
    }
    assert records["better"]["vehicle_specific_error"] < records["worse"]["vehicle_specific_error"]


def test_full_mix_crest_regression_is_partial_and_input_is_not_mutated() -> None:
    candidate = _record("v8", pass_all=False)
    before = json.dumps(candidate, sort_keys=True)
    result = qualify_stage_l_candidates([candidate], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0))
    assert result["selected_candidate_id"] is None
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    evaluated = result["evaluated"][0]
    assert evaluated["hard_gates"]["low_band_pulse_crest_improves_parent"] is False
    assert result["candidate_file_update_performed"] is False
    assert json.dumps(candidate, sort_keys=True) == before


def test_auxiliary_crest_roughness_and_reference_band_gates_are_hard() -> None:
    parent = _perceptual(crest_db=8.0)
    crest = _record("crest", pass_all=True)
    crest["metrics"]["source_domain"]["low_band_pulse_crest_db"] = 11.5
    rough = _record("rough", pass_all=True)
    rough["metrics"]["source_domain"]["roughness_20_300_hz"] = 1.40
    low = _record("low", pass_all=True)
    low["reference_distance"]["gates"]["acceleration_20_250hz_absolute_error_non_expansion"] = False
    mid = _record("mid", pass_all=True)
    mid["reference_distance"]["gates"]["acceleration_250_1000hz_absolute_error_strict_shrink"] = False

    for row in (crest, rough, low, mid):
        with pytest.raises(ValueError, match="reference summary") if row in (low, mid) else _does_not_raise():
            result = qualify_stage_l_candidates(
                [row], parent_parameters={"source.x": 0.0}, parent_metrics=parent,
            )
            assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


class _does_not_raise:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def _file_receipt(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _runner_manifest(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    repo_root = Path(__file__).resolve().parents[5]
    package = repo_root / "tools/sound_sim/s12/acoustic_identity_v015"
    profile = package / "targets/stage_l_candidates/hellcat_candidate_v8.json"
    target = package / "reference_database/hellcat_reference_targets.json"
    stage_k = tmp_path / "stage_k.wav"
    stage_l = tmp_path / "stage_l.wav"
    stage_k.write_bytes(b"stage-k-final-pcm24-fixture")
    stage_l.write_bytes(b"stage-l-final-pcm24-fixture")
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({
        "schema_version": "s12-stage-l-trace-evidence-1", "status": "PASS",
        "trace_version": "stage_l_canonical_cycle_v1", "trace_sha256": _sha("reference-trace"),
    }), encoding="utf-8")
    identity = tmp_path / "identity.json"
    identity.write_text(json.dumps({"schema_version": "s12-stage-l-identity-evidence-1", "status": "PASS", "stage_c_identity_regression_ratio": 0.05}), encoding="utf-8")
    isolation = tmp_path / "isolation.json"
    isolation.write_text(json.dumps({"schema_version": "s12-stage-l-isolation-evidence-1", "status": "PASS", "seven_non_hellcat_pcm_sha_unchanged": True}), encoding="utf-8")
    track_p = tmp_path / "track_p.json"
    track_p.write_text(json.dumps({"schema_version": "s12-stage-l-track-p-evidence-1", "status": "PASS", "passed": 21, "total": 21, "frozen_files": 180, "frozen_symbols": 2, "unchanged": True}), encoding="utf-8")
    payload = {
        "schema_version": "s12-stage-l-qualification-manifest-1",
        "probe_duration_s": 10.0,
        "search_parent_profile": _file_receipt(profile),
        "stage_k_final_wav": _file_receipt(stage_k),
        "reference_target": _file_receipt(target),
        "reference_trace": {
            "version": "stage_l_canonical_cycle_v1", "trace_sha256": _sha("reference-trace"),
            "evidence": _file_receipt(trace),
        },
        "identity_evidence": _file_receipt(identity),
        "isolation_evidence": _file_receipt(isolation),
        "track_p_evidence": _file_receipt(track_p),
        "candidates": [{"candidate_profile": _file_receipt(profile), "stage_l_final_wav": _file_receipt(stage_l)}],
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, payload


def test_runner_rejects_legacy_self_asserted_metrics_manifest(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({
        "schema_version": "s12-stage-l-qualification-input-1",
        "candidates": [_record("forged", pass_all=True)],
        "parent_parameters": {"source.x": 0.0},
        "parent_metrics": _perceptual(crest_db=8.0),
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest|exact"):
        qualifier.run_stage_l_qualification_manifest(legacy, hashlib.sha256(legacy.read_bytes()).hexdigest())


def test_runner_rejects_profile_hash_drift_before_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, payload = _runner_manifest(tmp_path)
    payload["candidates"][0]["candidate_profile"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(qualifier, "render_stage_l_candidate", lambda *_: pytest.fail("must fail before render"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        qualifier.run_stage_l_qualification_manifest(manifest, hashlib.sha256(manifest.read_bytes()).hexdigest())


def test_runner_builds_actual_evidence_instead_of_trusting_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, payload = _runner_manifest(tmp_path)
    events: list[str] = []
    requested: list[str] = []

    class _Render:
        pass

    def fake_render(trace, profile):
        events.append(f"render:{profile.candidate_id}")
        requested[:] = list(profile.requested_parameters())
        return _Render()

    def fake_layers(render, trace, profile, *, include_l4=False):
        assert include_l4 is True
        events.append(f"layers:{profile.candidate_id}")
        return render

    metric_calls = 0

    def fake_metrics(render, trace, wav_path):
        nonlocal metric_calls
        metric_calls += 1
        events.append(f"metrics:{Path(wav_path).name}")
        is_parent = metric_calls == 1
        receipt = payload["stage_k_final_wav"] if is_parent else payload["candidates"][0]["stage_l_final_wav"]
        return _perceptual(
            crest_db=8.0 if is_parent else 9.0,
            wav_sha256=receipt["sha256"], requested=requested,
        )

    def fake_reference(*args, **kwargs):
        events.append("reference")
        result = _reference(pass_all=True, candidate_id="hellcat_stage_l_v8")
        result["hashes"].update({
            "stage_k_wav_sha256": payload["stage_k_final_wav"]["sha256"],
            "stage_l_wav_sha256": payload["candidates"][0]["stage_l_final_wav"]["sha256"],
            "reference_target_sha256": payload["reference_target"]["sha256"],
            "candidate_profile_sha256": payload["candidates"][0]["candidate_profile"]["sha256"],
            "trace_evidence_sha256": payload["reference_trace"]["evidence"]["sha256"],
            "identity_evidence_sha256": payload["identity_evidence"]["sha256"],
            "isolation_evidence_sha256": payload["isolation_evidence"]["sha256"],
            "track_p_evidence_sha256": payload["track_p_evidence"]["sha256"],
        })
        result["trace_binding"] = {
            "trace_version": payload["reference_trace"]["version"],
            "trace_sha256": payload["reference_trace"]["trace_sha256"],
            "trace_evidence_sha256": payload["reference_trace"]["evidence"]["sha256"],
        }
        return result

    monkeypatch.setattr(qualifier, "render_stage_l_candidate", fake_render)
    monkeypatch.setattr(qualifier, "_apply_current_frozen_layers", fake_layers)
    monkeypatch.setattr(qualifier, "compute_stage_l_perceptual_metrics", fake_metrics)
    monkeypatch.setattr(qualifier, "compute_stage_l_reference_distance", fake_reference)
    result = qualifier.run_stage_l_qualification_manifest(
        manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )
    assert result["qualification_input_receipt"]["schema_version"] == "s12-stage-l-qualification-manifest-1"
    assert result["full_render_residency_max"] == 1
    assert events == [
        "render:hellcat_stage_l_v8", "layers:hellcat_stage_l_v8", "metrics:stage_k.wav",
        "render:hellcat_stage_l_v8", "layers:hellcat_stage_l_v8", "metrics:stage_l.wav", "reference",
    ]
    assert set(result["artifact_receipts"]) == {
        "search_parent_profile", "stage_k_final_wav", "reference_target", "trace_evidence",
        "identity_evidence", "isolation_evidence", "track_p_evidence", "candidate_profiles",
        "stage_l_final_wavs",
    }


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda row: row.update({"surprise": True}), "exact keys"),
        (lambda row: row.update({"vehicle_specific_error": 0.0}), "exact keys"),
        (lambda row: row["metrics"].update({"hard_gates": {name: True for name in REQUIRED_HARD_GATES}}), "exact keys"),
        (lambda row: row["reference_distance"]["protection_evidence"]["isolation"].update({"seven_non_hellcat_pcm_sha_unchanged": 1}), "protection evidence status"),
        (lambda row: row.update({"full_render_residency_max": True}), "integer"),
        (lambda row: row.update({"full_render_residency_max": 2}), "one SourceRender"),
        (lambda row: row["reference_distance"].update({"mean_improvement_ratio": 0.99}), "reference summary"),
    ],
)
def test_search_rejects_unknown_missing_non_boolean_or_self_asserted_evidence(mutator, match: str) -> None:
    row = _record("x", pass_all=True)
    mutator(row)
    with pytest.raises(ValueError, match=match):
        qualify_stage_l_candidates([row], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0))


def test_search_rejects_unbounded_or_non_probe_inputs() -> None:
    with pytest.raises(ValueError, match=str(MAX_CANDIDATES)):
        qualify_stage_l_candidates([_record(str(index), pass_all=True) for index in range(MAX_CANDIDATES + 1)], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0))
    bad = _record("long", pass_all=True)
    bad["probe_duration_s"] = 12.1
    with pytest.raises(ValueError, match="8.*12"):
        qualify_stage_l_candidates([bad], parent_parameters={"source.x": 0.0}, parent_metrics=_perceptual(crest_db=8.0))


@pytest.mark.parametrize("module_mode", (False, True))
def test_qualification_cli_supports_help_and_actual_runner(tmp_path: Path, module_mode: bool) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    prefix = [sys.executable, "-m", "tools.sound_sim.s12.acoustic_identity_v015.scripts.qualify_stage_l_hellcat"] if module_mode else [
        sys.executable, str(repo_root / "tools/sound_sim/s12/acoustic_identity_v015/scripts/qualify_stage_l_hellcat.py")]
    help_run = subprocess.run([*prefix, "--help"], cwd=repo_root, capture_output=True, text=True, check=False)
    assert help_run.returncode == 0, help_run.stderr
    payload = {"schema_version": "s12-stage-l-qualification-input-1", "candidates": [_record("v8", pass_all=False)], "parent_parameters": {"source.x": 0.0}, "parent_metrics": _perceptual(crest_db=8.0)}
    source = tmp_path / "qualification.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    run = subprocess.run([*prefix, str(source), "--input-sha256", source_sha], cwd=repo_root, capture_output=True, text=True, check=False)
    assert run.returncode != 0
    assert "qualification manifest" in run.stderr
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
