from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import weakref

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _write_pcm24_wav
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
            "low_band_pulse_crest_db": crest_db,
            "roughness_20_300_hz": source["roughness_20_300_hz"],
            "review_requested_gain_db": 0.0,
            "review_actual_gain_db": 0.0,
            "headroom_limited": False,
        },
    }


def _parent_metrics(*, crest_db: float = 8.0, upper_share: float = 0.05) -> dict[str, object]:
    pcm = _perceptual(crest_db=crest_db, upper_share=upper_share)["final_pcm24"]
    return {
        "schema_version": "s12-stage-k-parent-comparison-metrics-1",
        "domain": "reopened PCM24 values comparable across Stage-K and Stage-L",
        "final_pcm24": pcm,
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
            name: {
                "schema_version": "s12-stage-l-repository-protection-evidence-1",
                "status": "PASS", "source_artifact": f"repo/{name}",
                "source_artifact_sha256": _sha(f"{name}-source"),
                "derivation": "validated existing repository artifact",
            }
            for name in ("identity", "isolation", "track_p")
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
            "trace_evidence_sha256": _sha("trace-evidence"),
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
        "formal_final_audio_provenance": {
            "status": "AVAILABLE",
            "producer_binding": {
                "schema_version": "s12-stage-l-formal-final-audio-producer-binding-1",
                "producer_artifact_sha256": _sha("producer"),
                "candidate_profile_sha256": _sha("profile"),
                "trace_sha256": _sha("trace"),
                "final_wav_sha256": _sha("candidate"),
            },
        },
    }


def test_search_derives_exact_hard_gates_from_nested_evidence_and_is_deterministic() -> None:
    a = _record("a", pass_all=True, delta=0.2)
    b = _record("b", pass_all=True, delta=0.1)
    bad = _record("bad", pass_all=False, delta=0.0)
    parent = _parent_metrics()
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
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics(),
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
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics(),
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
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics(),
    )
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"


@pytest.mark.parametrize("parameters", ({}, {"wrong.x": 0.1}))
def test_parameters_are_bound_exactly_to_actual_requested_usage(parameters: dict[str, float]) -> None:
    row = _record("parameter-drift", pass_all=True)
    row["parameters"] = parameters
    with pytest.raises(ValueError, match="requested|parameter"):
        qualify_stage_l_candidates(
            [row], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics(),
        )


def test_vehicle_specific_error_is_derived_from_actual_evidence_with_breakdown() -> None:
    better = _record("better", pass_all=True, delta=0.2)
    worse = _record("worse", pass_all=True, delta=0.1)
    worse["metrics"]["source_domain"]["shaft_ratio_error"] = 0.009
    result = qualify_stage_l_candidates(
        [worse, better], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics(),
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
    result = qualify_stage_l_candidates([candidate], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics())
    assert result["selected_candidate_id"] is None
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    evaluated = result["evaluated"][0]
    assert evaluated["hard_gates"]["low_band_pulse_crest_improves_parent"] is False
    assert result["candidate_file_update_performed"] is False
    assert json.dumps(candidate, sort_keys=True) == before


def test_missing_formal_final_audio_provenance_is_a_hard_gate() -> None:
    candidate = _record("all-measured-gates-pass", pass_all=True)
    candidate["formal_final_audio_provenance"] = {
        "status": "NOT_AVAILABLE",
        "reason": "no exact producer/profile/trace/final-WAV cross-binding",
    }

    result = qualify_stage_l_candidates(
        [candidate], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics(),
    )

    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["selected_candidate_id"] is None
    assert result["evaluated"][0]["hard_gates"]["formal_produced_final_audio"] is False


def test_auxiliary_crest_roughness_and_reference_band_gates_are_hard() -> None:
    parent = _parent_metrics()
    crest = _record("crest", pass_all=True)
    crest["metrics"]["final_pcm24"]["low_band_pulse_crest_db"] = 11.5
    rough = _record("rough", pass_all=True)
    rough["metrics"]["final_pcm24"]["roughness_20_300_hz"] = 1.40
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
    parent_profile = package / "targets/stage_k_candidates/hellcat_candidate_v7.json"
    target = package / "reference_database/hellcat_reference_targets.json"
    stage_k = tmp_path / "stage_k.wav"
    stage_l = tmp_path / "stage_l.wav"
    _write_pcm24_wav(stage_k, np.zeros((480, 2), dtype=np.float64))
    _write_pcm24_wav(stage_l, np.zeros((480, 2), dtype=np.float64))
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({
        "schema_version": "s12-stage-l-trace-evidence-1", "status": "PASS",
        "trace_version": "stage_l_canonical_cycle_v1", "trace_sha256": _sha("reference-trace"),
    }), encoding="utf-8")
    trace_sha = _sha("reference-trace")

    def audio_entry(
        wav: Path, profile_path: Path, profile_id: str, artifact_kind: str,
    ) -> dict[str, object]:
        del profile_path, profile_id, artifact_kind
        return _file_receipt(wav)

    payload = {
        "schema_version": "s12-stage-l-qualification-manifest-1",
        "probe_duration_s": 10.0,
        "search_parent_profile": _file_receipt(parent_profile),
        "stage_k_final_wav": audio_entry(stage_k, parent_profile, "hellcat_stage_k_v7", "stage_k_final_pcm24"),
        "reference_target": _file_receipt(target),
        "reference_trace": {
            "version": "stage_l_canonical_cycle_v1", "trace_sha256": trace_sha,
            "evidence": _file_receipt(trace),
        },
        "candidates": [{
            "candidate_profile": _file_receipt(profile),
            "stage_l_final_wav": audio_entry(stage_l, profile, "hellcat_stage_l_v8", "stage_l_final_pcm24"),
        }],
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


def test_runner_rejects_nonexistent_producer_receipt_scheme(tmp_path: Path) -> None:
    manifest, payload = _runner_manifest(tmp_path)
    payload["stage_k_final_wav"]["production_receipt"] = {
        "path": "forged.json", "sha256": "0" * 64,
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="exact keys"):
        qualifier.run_stage_l_qualification_manifest(
            manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(),
        )


def test_runner_rejects_fabricated_producer_api_before_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, payload = _runner_manifest(tmp_path)
    payload["candidates"][0]["stage_l_final_wav"]["producer_api"] = (
        "stage_l.named_review.render_stage_l_candidate_pcm24"
    )
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(qualifier, "render_stage_k_candidate", lambda *_: pytest.fail("must fail before render"))

    with pytest.raises(ValueError, match="exact keys"):
        qualifier.run_stage_l_qualification_manifest(
            manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(),
        )


def test_runner_uses_distinct_stage_k_parent_loader_and_renderer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, payload = _runner_manifest(tmp_path)
    repo_root = Path(__file__).resolve().parents[5]
    stage_k_profile = (
        repo_root / "tools/sound_sim/s12/acoustic_identity_v015/targets/stage_k_candidates"
        / "hellcat_candidate_v7.json"
    )
    payload["search_parent_profile"] = _file_receipt(stage_k_profile)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(
        qualifier, "load_stage_k_candidate",
        lambda path: calls.append(f"load-k:{Path(path).name}") or object(),
    )
    monkeypatch.setattr(
        qualifier, "render_stage_k_candidate",
        lambda vehicle_id, trace, profile: calls.append(f"render-k:{vehicle_id}") or object(),
    )
    monkeypatch.setattr(
        qualifier, "load_stage_l_candidate",
        lambda path: calls.append(f"load-l:{Path(path).name}") or pytest.fail("stop after distinct loaders"),
    )

    with pytest.raises(pytest.fail.Exception, match="stop after distinct loaders"):
        qualifier.run_stage_l_qualification_manifest(
            manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(),
        )
    assert calls[:2] == ["load-k:hellcat_candidate_v7.json", "load-l:hellcat_candidate_v8.json"]


def test_nonexistent_producer_api_is_not_exposed() -> None:
    assert not hasattr(qualifier, "_bind_production_audio_receipt")


def test_upper_band_increment_over_parent_is_a_hard_gate() -> None:
    parent = _parent_metrics(upper_share=0.048)
    row = _record("upper-increment", pass_all=True)
    row["metrics"]["final_pcm24"]["band_shares"][3] = 0.059
    row["metrics"]["final_pcm24"]["band_shares"][2] = 0.121

    result = qualify_stage_l_candidates(
        [row], parent_parameters={"source.x": 0.0}, parent_metrics=parent,
    )

    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["evaluated"][0]["hard_gates"]["final_pcm_upper_share_increment"] is False


def test_runner_measures_source_render_residency_instead_of_reporting_a_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = 0
    observed_max = 0

    class _Render:
        def __init__(self) -> None:
            nonlocal live, observed_max
            live += 1
            observed_max = max(observed_max, live)
            weakref.finalize(self, _released)

    def _released() -> None:
        nonlocal live
        live -= 1

    monkeypatch.setattr(qualifier, "render_stage_l_candidate", lambda *_: _Render())
    monkeypatch.setattr(qualifier, "_apply_current_frozen_layers", lambda *_args, **_kwargs: _Render())
    residency = qualifier._RenderResidency()
    rendered = qualifier._render_pre_ptr(object(), object(), residency)
    assert isinstance(rendered, _Render)
    assert observed_max == 2
    assert residency.maximum == observed_max


def test_real_stage_k_parent_and_stage_l_candidate_metrics_are_executable(
    tmp_path: Path,
) -> None:
    """Exercise both production renderers; Stage-K must not enter the Stage-L stem validator."""
    package = Path(__file__).resolve().parents[1]
    trace = qualifier.build_drive_cycle_trace("hellcat", duration_s=1.0)
    parent_profile = qualifier.load_stage_k_candidate(
        package / "targets/stage_k_candidates/hellcat_candidate_v7.json"
    )
    candidate_profile = qualifier.load_stage_l_candidate(
        package / "targets/stage_l_candidates/hellcat_candidate_v8.json"
    )
    parent_render = qualifier.render_stage_k_candidate("hellcat", trace, parent_profile)
    candidate_render = qualifier._render_pre_ptr(
        trace, candidate_profile, qualifier._RenderResidency()
    )

    def write_reopened_pcm(path: Path, render: object) -> Path:
        pressure = np.asarray(render.pressure, dtype=np.float64)
        peak = max(float(np.max(np.abs(pressure))), 1.0e-12)
        return _write_pcm24_wav(path, 0.25 * pressure / peak)

    parent_metrics = qualifier.compute_stage_k_parent_metrics(
        parent_render, trace, write_reopened_pcm(tmp_path / "stage_k.wav", parent_render)
    )
    candidate_metrics = qualifier.compute_stage_l_perceptual_metrics(
        candidate_render, trace, write_reopened_pcm(tmp_path / "stage_l.wav", candidate_render)
    )

    assert parent_metrics["schema_version"] == "s12-stage-k-parent-comparison-metrics-1"
    assert set(parent_metrics) == {"schema_version", "domain", "final_pcm24"}
    assert candidate_metrics["schema_version"] == "s12-stage-l-perceptual-metrics-1"
    assert candidate_metrics["source_domain"]["shaft_ratio_error"] >= 0.0


def test_real_stage_l_pre_ptr_reports_raw_and_final_render_coexistence() -> None:
    package = Path(__file__).resolve().parents[1]
    trace = qualifier.build_drive_cycle_trace("hellcat", duration_s=1.0)
    profile = qualifier.load_stage_l_candidate(
        package / "targets/stage_l_candidates/hellcat_candidate_v8.json"
    )
    residency = qualifier._RenderResidency()

    rendered = qualifier._render_pre_ptr(trace, profile, residency)

    assert rendered.pressure.shape[0] == trace.time_s.shape[0]
    assert residency.maximum == 2


def test_actual_runner_renders_stage_k_and_stage_l_and_completes_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, payload = _runner_manifest(tmp_path)
    samples = np.arange(48_000, dtype=np.float64) / 48_000.0
    for key, frequency in (("stage_k_final_wav", 120.0), ("stage_l_final_wav", 180.0)):
        wav_entry = (
            payload["stage_k_final_wav"] if key == "stage_k_final_wav"
            else payload["candidates"][0]["stage_l_final_wav"]
        )
        wav = Path(wav_entry["path"])
        mono = 0.05 * np.sin(2.0 * np.pi * frequency * samples)
        _write_pcm24_wav(wav, np.column_stack((mono, mono)))
        wav_entry["sha256"] = hashlib.sha256(wav.read_bytes()).hexdigest()
    payload["probe_duration_s"] = 8.0
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_l.reference_distance.extract_reference_features",
        lambda *_args, **_kwargs: {
            "segments": {
                state: {"band_shares": [0.40, 0.35, 0.20, 0.05]}
                for state in ("idle", "acceleration", "afterfire")
            }
        },
    )

    result = qualifier.run_stage_l_qualification_manifest(
        manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )

    assert result["full_render_residency_max"] > 1
    assert result["status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["selected_candidate_id"] is None
    assert result["formal_final_audio_provenance"]["status"] == "NOT_AVAILABLE"
    assert result["evaluated"][0]["hard_gates"]["one_full_source_render_resident"] is False
    assert result["evaluated"][0]["hard_gates"]["non_hellcat_isolation"] is False


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

    def fake_metrics(render, trace, wav_path):
        events.append(f"metrics:{Path(wav_path).name}")
        return _perceptual(
            crest_db=9.0,
            wav_sha256=payload["candidates"][0]["stage_l_final_wav"]["sha256"],
            requested=requested,
        )

    def fake_parent_metrics(render, trace, wav_path):
        events.append(f"metrics:{Path(wav_path).name}")
        result = _parent_metrics()
        result["final_pcm24"]["wav_sha256"] = payload["stage_k_final_wav"]["sha256"]
        return result

    def fake_reference(*args, **kwargs):
        events.append("reference")
        result = _reference(pass_all=True, candidate_id="hellcat_stage_l_v8")
        result["hashes"].update({
            "stage_k_wav_sha256": payload["stage_k_final_wav"]["sha256"],
            "stage_l_wav_sha256": payload["candidates"][0]["stage_l_final_wav"]["sha256"],
            "reference_target_sha256": payload["reference_target"]["sha256"],
            "candidate_profile_sha256": payload["candidates"][0]["candidate_profile"]["sha256"],
            "trace_evidence_sha256": payload["reference_trace"]["evidence"]["sha256"],
        })
        result["trace_binding"] = {
            "trace_version": payload["reference_trace"]["version"],
            "trace_sha256": payload["reference_trace"]["trace_sha256"],
            "trace_evidence_sha256": payload["reference_trace"]["evidence"]["sha256"],
        }
        return result

    monkeypatch.setattr(qualifier, "render_stage_l_candidate", fake_render)
    monkeypatch.setattr(
        qualifier, "render_stage_k_candidate",
        lambda vehicle_id, trace, profile: events.append(f"render-k:{profile.candidate_id}") or _Render(),
    )
    monkeypatch.setattr(qualifier, "_apply_current_frozen_layers", fake_layers)
    monkeypatch.setattr(qualifier, "compute_stage_k_parent_metrics", fake_parent_metrics)
    monkeypatch.setattr(qualifier, "compute_stage_l_perceptual_metrics", fake_metrics)
    monkeypatch.setattr(qualifier, "compute_stage_l_reference_distance", fake_reference)
    result = qualifier.run_stage_l_qualification_manifest(
        manifest, hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )
    assert result["qualification_input_receipt"]["schema_version"] == "s12-stage-l-qualification-manifest-1"
    assert result["full_render_residency_max"] == 1
    assert events == [
        "render-k:hellcat_stage_k_v7", "metrics:stage_k.wav",
        "render:hellcat_stage_l_v8", "layers:hellcat_stage_l_v8", "metrics:stage_l.wav", "reference",
    ]
    assert set(result["artifact_receipts"]) == {
        "search_parent_profile", "stage_k_final_wav", "reference_target", "trace_evidence",
        "candidate_profiles", "stage_l_final_wavs",
    }
    assert result["formal_final_audio_provenance"]["status"] == "NOT_AVAILABLE"


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda row: row.update({"surprise": True}), "exact keys"),
        (lambda row: row.update({"vehicle_specific_error": 0.0}), "exact keys"),
        (lambda row: row["metrics"].update({"hard_gates": {name: True for name in REQUIRED_HARD_GATES}}), "exact keys"),
        (lambda row: row["reference_distance"]["protection_evidence"]["isolation"].update({"seven_non_hellcat_pcm_sha_unchanged": 1}), "exact keys"),
        (lambda row: row.update({"full_render_residency_max": True}), "integer"),
        (lambda row: row["reference_distance"].update({"mean_improvement_ratio": 0.99}), "reference summary"),
    ],
)
def test_search_rejects_unknown_missing_non_boolean_or_self_asserted_evidence(mutator, match: str) -> None:
    row = _record("x", pass_all=True)
    mutator(row)
    with pytest.raises(ValueError, match=match):
        qualify_stage_l_candidates([row], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics())


def test_search_rejects_unbounded_or_non_probe_inputs() -> None:
    with pytest.raises(ValueError, match=str(MAX_CANDIDATES)):
        qualify_stage_l_candidates([_record(str(index), pass_all=True) for index in range(MAX_CANDIDATES + 1)], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics())
    bad = _record("long", pass_all=True)
    bad["probe_duration_s"] = 12.1
    with pytest.raises(ValueError, match="8.*12"):
        qualify_stage_l_candidates([bad], parent_parameters={"source.x": 0.0}, parent_metrics=_parent_metrics())


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
