from __future__ import annotations

import hashlib
import json
import math
import numpy as np
import pytest

from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.loudness_manager import measure_loudness
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _read_pcm24_wav, _write_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.qualification import (
    qualify_stage_i_candidates,
    qualify_stage_i_source_manifest,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles import load_stage_i_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.probes import (
    array_sha256,
    build_final_pcm_source_evidence,
    candidate_profile_binding,
)


_IDS = ("I6-A Balanced", "I6-B Whine Forward", "I6-C Softer Mechanical")
_PROFILE_FILES = (
    "Hellcat_candidate_v6_A_Balanced.json",
    "Hellcat_candidate_v6_B_WhineForward.json",
    "Hellcat_candidate_v6_C_SofterMechanical.json",
)


def _full_reference_summary() -> dict[str, object]:
    target = [0.4, 0.3, 0.2, 0.1]
    actual_h = [0.5, 0.2, 0.2, 0.1]
    actual_i = [0.49, 0.21, 0.2, 0.1]
    distance_h = math.sqrt(0.25 * sum((a - t) ** 2 for a, t in zip(actual_h, target, strict=True)))
    distance_i = math.sqrt(0.25 * sum((a - t) ** 2 for a, t in zip(actual_i, target, strict=True)))
    improvement = (distance_h - distance_i) / max(distance_h, 1.0e-12)
    state = {
        "availability": "eligible",
        "target": {"band_shares": target, "spectral_centroid_hz": 500.0},
        "actual_stage_h": {"band_shares": actual_h, "spectral_centroid_hz": 510.0},
        "actual_stage_i": {"band_shares": actual_i, "spectral_centroid_hz": 505.0},
        "signed_error": [a - t for a, t in zip(actual_i, target, strict=True)],
        "absolute_error": [abs(a - t) for a, t in zip(actual_i, target, strict=True)],
        "stage_h_distance": distance_h,
        "stage_i_distance": distance_i,
        "improvement_ratio": improvement,
        "reference_provenance": {"source_level": "B", "scope": "relative features"},
    }
    candidates = {
        candidate_id: {
            "states": {
                state_id: json.loads(json.dumps(state))
                for state_id in ("idle", "acceleration", "afterfire")
            },
            "mean_improvement_ratio": improvement,
            "gates": {
                "all_required_states_available": True,
                "mean_improvement_at_least_30_percent": False,
                "no_state_worse_than_10_percent": True,
            },
            "automatic_status": "PARTIAL / AUTOMATED_GATE_FAIL",
        }
        for candidate_id in _IDS
    }
    return {
        "schema_version": "s12-stage-i-reference-distance-1",
        "vehicle_id": "hellcat",
        "domain": "final_pcm",
        "bands_hz": [[20.0, 250.0], [250.0, 1000.0], [1000.0, 4000.0], [4000.0, 12000.0]],
        "windows_s": {
            "idle": [0.0, 8.0],
            "acceleration": [8.0, 26.0],
            "afterfire": [36.0, 46.0],
        },
        "candidates": candidates,
        "automatic_status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "reference_target_sha256": "a" * 64,
        "provenance": "B/R2 relative features; uncalibrated; not OEM reproduction",
    }


def _fixture(tmp_path, sample_rate_hz: int = 48000):
    count = int(1.2 * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(2200.0, 4800.0, count)
    load = np.where(time_s < 0.30, 0.12, np.where(time_s < 0.90, 0.85, 0.30))
    throttle = load.copy()
    engine_phase = np.cumsum(rpm / 60.0) / sample_rate_hz
    shaft = 0.015 * (0.1 + load) * np.sin(2.0 * np.pi * 2.36 * engine_phase)
    lobe = 0.035 * (0.1 + load) * (
        np.sin(2.0 * np.pi * 11.8 * engine_phase)
        + 0.24 * np.sin(2.0 * np.pi * 11.66 * engine_phase)
        + 0.24 * np.sin(2.0 * np.pi * 11.94 * engine_phase)
    )
    upper = 0.006 * (0.1 + load) * np.sin(2.0 * np.pi * 23.6 * engine_phase)
    sidebands = 0.014 * (0.1 + load) * (
        np.sin(2.0 * np.pi * (11.8 + 4.0) * engine_phase)
        + np.sin(2.0 * np.pi * (11.8 - 4.0) * engine_phase)
    )
    bypass = np.zeros(count, dtype=np.float64)
    bypass[int(0.90 * sample_rate_hz):int(1.10 * sample_rate_hz)] = np.linspace(
        0.015, 0.0, int(0.20 * sample_rate_hz), endpoint=False
    )
    blower = shaft + lobe + upper + sidebands + bypass
    exhaust = 0.12 * np.sin(2.0 * np.pi * 4.0 * engine_phase)
    rumble = 0.04 * np.sin(2.0 * np.pi * 58.0 * time_s)

    def stereo(mono):
        return np.column_stack((0.7 * mono, mono))

    base_render = SourceRender(
        pressure=stereo(blower + exhaust + rumble),
        stems={
            "blower": stereo(blower),
            "blower_shaft": stereo(shaft),
            "blower_lobe_family": stereo(lobe),
            "blower_upper_family": stereo(upper),
            "blower_sidebands": stereo(sidebands),
            "blower_bypass_release": stereo(bypass),
            "exhaust": stereo(exhaust),
            "exhaust_rumble": stereo(rumble),
        },
        diagnostics={"scope": "synthetic"},
    )
    trace = VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm, time_s))
    masks = {
        "idle": time_s < 0.30,
        "acceleration": (time_s >= 0.30) & (time_s < 0.70),
        "full_pull": (time_s >= 0.70) & (time_s < 0.90),
    }
    root = Path(__file__).resolve().parents[1] / "targets" / "stage_i_candidates"
    profiles = {candidate_id: load_stage_i_candidate(root / filename) for candidate_id, filename in zip(_IDS, _PROFILE_FILES)}
    pcm_paths = {}
    renders = {}
    source_evidence = {}
    for index, candidate_id in enumerate(_IDS):
        render = SourceRender(base_render.pressure, base_render.stems, {"stage_i_candidate_id": profiles[candidate_id].candidate_id})
        path = tmp_path / f"candidate_{index}.wav"
        _write_pcm24_wav(path, (0.62 - 0.02 * index) * render.pressure)
        pcm_paths[candidate_id] = path
        renders[candidate_id] = render
        source_evidence[candidate_id] = build_final_pcm_source_evidence(candidate_id, profiles[candidate_id], render, path)
    stage_h_path = tmp_path / "stage_h.wav"
    _write_pcm24_wav(stage_h_path, 0.62 * base_render.pressure)

    command = np.zeros(800, dtype=np.float64)
    command[100:450] = 1.0
    response = np.zeros_like(command)
    response[100:200] = np.linspace(0.0, 1.0, 100, endpoint=False)
    response[200:450] = 1.0
    response[450:750] = np.linspace(1.0, 0.0, 300, endpoint=False)
    bypass_gate = np.zeros_like(command)
    bypass_gate[450:] = 1.0
    bypass_response = np.zeros_like(command)
    bypass_response[450:650] = np.linspace(1.0, 0.0, 200, endpoint=False)
    probes = {}
    for candidate_id in _IDS:
        arrays = {
            "sample_rate_hz": 1000,
            "boost_response": response,
            "boost_command": command,
            "bypass_response": bypass_response,
            "bypass_gate": bypass_gate,
        }
        probes[candidate_id] = {
            **arrays,
            "evidence": {
                "schema_version": "s12-stage-i-response-probe-evidence-1",
                "candidate_label": candidate_id,
                **candidate_profile_binding(profiles[candidate_id]),
                "probes": {
                    "boost": {"trace_sha256": "1" * 64, "render_sha256": "2" * 64, "stem_sha256": {"blower": "3" * 64, "blower_bypass_release": "4" * 64}},
                    "lift": {"trace_sha256": "5" * 64, "render_sha256": "6" * 64, "stem_sha256": {"blower": "7" * 64, "blower_bypass_release": "8" * 64}},
                },
                "array_sha256": {name: array_sha256(value) for name, value in arrays.items() if name != "sample_rate_hz"},
            },
        }
    reference = _full_reference_summary()
    return renders, trace, pcm_paths, base_render, stage_h_path, profiles, probes, source_evidence, masks, reference


def test_qualification_merges_measured_source_pcm_and_evidence_metrics(tmp_path) -> None:
    renders, trace, paths, stage_h, stage_h_path, profiles, probes, source_evidence, masks, reference = _fixture(tmp_path)
    result = qualify_stage_i_candidates(
        renders,
        trace,
        paths,
        stage_h,
        stage_h_path,
        reference,
        profiles,
        probes,
        source_evidence,
        track_p_guard_pass=True,
        regression_isolation_pass=True,
        state_masks=masks,
    )

    assert result["automatic_reference_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["reference_summary"] == reference
    expected_reference_sha = hashlib.sha256(
        json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert result["reference_summary_sha256"] == expected_reference_sha
    assert set(result["candidates"]) == set(_IDS)
    pcm = _read_pcm24_wav(paths[_IDS[0]])
    expected_loudness = measure_loudness(pcm)
    metrics = result["candidates"][_IDS[0]]["metrics"]
    assert metrics["whole_cycle_lufs"] == pytest.approx(expected_loudness.integrated_lufs)
    assert metrics["peak_dbfs"] == pytest.approx(expected_loudness.peak_dbfs)
    assert metrics["sample_rate_hz"] == 48000
    assert metrics["channels"] == 2
    assert metrics["pcm_bits"] == 24
    assert metrics["finite"] is True
    assert metrics["boost_attack_10_90_s"] == pytest.approx(0.080, abs=0.003)
    assert metrics["boost_release_90_10_s"] == pytest.approx(0.240, abs=0.003)
    assert metrics["bypass_decay_90_10_s"] == pytest.approx(0.160, abs=0.003)
    assert np.isfinite(metrics["blower_to_exhaust_ratio_acceleration_db"])
    assert np.isfinite(metrics["low_frequency_share_40_200hz"])
    assert metrics["rumble_energy"] > 0.0
    assert set(result["candidates"][_IDS[0]]["gates"]) >= {"all_pass", "track_p_guard", "regression_isolation"}
    binding = result["candidates"][_IDS[0]]["binding"]
    assert binding["candidate_id"] == profiles[_IDS[0]].candidate_id
    assert binding["response_probe_evidence"] == probes[_IDS[0]]["evidence"]
    assert binding["final_pcm_source_evidence"] == source_evidence[_IDS[0]]
    assert result["stage_h_baseline_metrics"]["whole_cycle_lufs"] == pytest.approx(expected_loudness.integrated_lufs)


def test_qualification_requires_real_response_probe_for_every_candidate(tmp_path) -> None:
    renders, trace, paths, stage_h, stage_h_path, profiles, probes, source_evidence, masks, reference = _fixture(tmp_path)
    del probes["I6-B Whine Forward"]

    with pytest.raises(ValueError, match="response probe candidate IDs"):
        qualify_stage_i_candidates(
            renders,
            trace,
            paths,
            stage_h,
            stage_h_path,
            reference,
            profiles,
            probes,
            source_evidence,
            track_p_guard_pass=True,
            regression_isolation_pass=True,
            state_masks=masks,
        )


def test_qualification_rejects_incomplete_reference_summary(tmp_path) -> None:
    renders, trace, paths, stage_h, stage_h_path, profiles, probes, source_evidence, masks, reference = _fixture(tmp_path)
    bad_reference = dict(reference)
    del bad_reference["windows_s"]
    with pytest.raises(ValueError, match="exact keys"):
        qualify_stage_i_candidates(
            renders,
            trace,
            paths,
            stage_h,
            stage_h_path,
            bad_reference,
            profiles,
            probes,
            source_evidence,
            track_p_guard_pass=True,
            regression_isolation_pass=True,
            state_masks=masks,
        )


def test_manifest_qualification_accepts_actual_multi_candidate_reference_summary(tmp_path) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, _ = _fixture(tmp_path)
    source_manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    multi_reference = _full_reference_summary()

    result = qualify_stage_i_source_manifest(
        source_manifest,
        profiles,
        probes,
        multi_reference,
        track_p_guard_pass=True,
        regression_isolation_pass=True,
    )

    assert result["automatic_reference_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert result["reference_summary"] == multi_reference
    assert result["reference_summary_sha256"] == hashlib.sha256(
        json.dumps(multi_reference, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def test_manifest_qualification_rejects_minimal_forged_multi_candidate_reference_summary(tmp_path) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, _ = _fixture(tmp_path)
    source_manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    forged = {
        "schema_version": "s12-stage-i-reference-distance-1",
        "domain": "final_pcm",
        "candidates": {
            candidate_id: {
                "mean_improvement_ratio": 0.5,
                "gates": {
                    "all_required_states_available": True,
                    "mean_improvement_at_least_30_percent": True,
                    "no_state_worse_than_10_percent": True,
                },
                "automatic_status": "PASS",
            }
            for candidate_id in _IDS
        },
        "automatic_status": "PASS",
    }

    with pytest.raises(ValueError, match="exact keys"):
        qualify_stage_i_source_manifest(
            source_manifest,
            profiles,
            probes,
            forged,
            track_p_guard_pass=True,
            regression_isolation_pass=True,
        )


def test_manifest_qualification_recomputes_reference_distances_errors_and_gates(tmp_path) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, _ = _fixture(tmp_path)
    source_manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    tampered = _full_reference_summary()
    tampered["candidates"][_IDS[0]]["states"]["idle"]["signed_error"][0] += 0.01

    with pytest.raises(ValueError, match="signed_error"):
        qualify_stage_i_source_manifest(
            source_manifest,
            profiles,
            probes,
            tampered,
            track_p_guard_pass=True,
            regression_isolation_pass=True,
        )


def test_manifest_qualification_accepts_v2_nested_profile_and_render_binding(tmp_path) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, reference = _fixture(tmp_path)
    source_manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    source_manifest["schema_version"] = "s12-stage-i-source-evidence-2"
    for candidate_id, file_id in zip(_IDS, (
        "stage_i_v6_a_balanced_60s",
        "stage_i_v6_b_whine_forward_60s",
        "stage_i_v6_c_softer_mechanical_60s",
    ), strict=True):
        entry = source_manifest["evidence"][file_id]
        binding = candidate_profile_binding(profiles[candidate_id])
        entry["profile_binding"] = {
            "candidate_id": binding["candidate_id"],
            "profile_sha256": binding["candidate_sha256"],
            "profile_file_sha256": binding["profile_sha256"],
        }
        entry["source_render_sha256"] = entry.pop("render_sha256")
        del entry["candidate_sha256"]
        del entry["profile_sha256"]

    result = qualify_stage_i_source_manifest(
        source_manifest,
        profiles,
        probes,
        reference,
        track_p_guard_pass=True,
        regression_isolation_pass=True,
    )

    assert result["candidates"][_IDS[0]]["binding"]["render_sha256"] == (
        source_manifest["evidence"]["stage_i_v6_a_balanced_60s"]["source_render_sha256"]
    )


def test_qualification_rejects_probe_or_pcm_evidence_bound_to_another_candidate(tmp_path) -> None:
    renders, trace, paths, stage_h, stage_h_path, profiles, probes, source_evidence, masks, reference = _fixture(tmp_path)
    probes["I6-A Balanced"], probes["I6-B Whine Forward"] = probes["I6-B Whine Forward"], probes["I6-A Balanced"]
    with pytest.raises(ValueError, match="candidate_label"):
        qualify_stage_i_candidates(
            renders, trace, paths, stage_h, stage_h_path, reference, profiles, probes, source_evidence,
            track_p_guard_pass=True, regression_isolation_pass=True, state_masks=masks,
        )

    renders, trace, paths, stage_h, stage_h_path, profiles, probes, source_evidence, masks, reference = _fixture(tmp_path)
    paths["I6-A Balanced"], paths["I6-B Whine Forward"] = paths["I6-B Whine Forward"], paths["I6-A Balanced"]
    with pytest.raises(ValueError, match="final PCM byte SHA"):
        qualify_stage_i_candidates(
            renders, trace, paths, stage_h, stage_h_path, reference, profiles, probes, source_evidence,
            track_p_guard_pass=True, regression_isolation_pass=True, state_masks=masks,
        )

    renders, trace, paths, stage_h, stage_h_path, profiles, probes, source_evidence, masks, reference = _fixture(tmp_path)
    source_evidence["I6-A Balanced"], source_evidence["I6-B Whine Forward"] = source_evidence["I6-B Whine Forward"], source_evidence["I6-A Balanced"]
    with pytest.raises(ValueError, match="candidate_label"):
        qualify_stage_i_candidates(
            renders, trace, paths, stage_h, stage_h_path, reference, profiles, probes, source_evidence,
            track_p_guard_pass=True, regression_isolation_pass=True, state_masks=masks,
        )


def _manifest_source_metrics(index: int, *, baseline: bool = False) -> dict[str, float]:
    if baseline:
        return {
            "shaft_order_error": 0.004,
            "lobe_order_error": 0.006,
            "blower_load_correlation": 0.90,
            "blower_to_exhaust_ratio_idle_db": -24.0,
            "blower_to_exhaust_ratio_acceleration_db": -10.0,
            "blower_to_exhaust_ratio_full_pull_db": -8.0,
            "sideband_to_main_ratio": 0.12,
            "order_cluster_width_ratio": 0.010,
            "single_ridge_concentration": 0.50,
            "upper_band_share_4_12khz": 0.006,
            "upper_band_short_time_peak": 0.008,
            "low_frequency_share_40_200hz": 0.40,
            "rumble_energy": 10.0,
        }
    return {
        "shaft_order_error": 0.004,
        "lobe_order_error": 0.006,
        "blower_load_correlation": 0.91,
        "blower_to_exhaust_ratio_idle_db": -23.8,
        "blower_to_exhaust_ratio_acceleration_db": -7.0 + 0.1 * index,
        "blower_to_exhaust_ratio_full_pull_db": -5.5,
        "sideband_to_main_ratio": 0.13 + 0.01 * index,
        "order_cluster_width_ratio": 0.014,
        "single_ridge_concentration": 0.38,
        "upper_band_share_4_12khz": 0.008,
        "upper_band_short_time_peak": 0.007,
        "low_frequency_share_40_200hz": 0.405,
        "rumble_energy": 9.8,
    }


def _source_manifest(paths, profiles, source_evidence, stage_h_path) -> dict[str, object]:
    file_ids = {
        "I6-A Balanced": "stage_i_v6_a_balanced_60s",
        "I6-B Whine Forward": "stage_i_v6_b_whine_forward_60s",
        "I6-C Softer Mechanical": "stage_i_v6_c_softer_mechanical_60s",
    }
    files = {file_id: str(paths[label]) for label, file_id in file_ids.items()}
    files["stage_h_v5_baseline_60s"] = str(stage_h_path)
    evidence = {}
    for index, label in enumerate(_IDS):
        binding = source_evidence[label]
        pcm = _read_pcm24_wav(paths[label])
        loudness = measure_loudness(pcm)
        requested = sorted(profiles[label].requested_parameters())
        inactive = ["afterfire.gain_scale"]
        evidence[file_ids[label]] = {
            "path": str(paths[label]),
            "sha256": binding["final_pcm_sha256"],
            "candidate_id": profiles[label].candidate_id,
            "candidate_sha256": binding["candidate_sha256"],
            "profile_sha256": binding["profile_sha256"],
            "render_sha256": binding["render_sha256"],
            "source_metrics": _manifest_source_metrics(index),
            "candidate_parameter_usage": {
                "requested": requested,
                "read": requested,
                "configured": requested,
                "active": sorted(set(requested) - set(inactive)),
                "inactive": inactive,
                "consumed": requested,
                "unused": [],
                "activity_verification": "MEASURED_STAGE_I_RENDER_ACTIVITY",
            },
            "health": {"sample_rate_hz": 48000, "channels": 2, "pcm": "PCM_24", "finite": True, "peak_dbfs": loudness.peak_dbfs, "clipping_count": loudness.clipping_count},
            "loudness": {"integrated_lufs": loudness.integrated_lufs, "peak_dbfs": loudness.peak_dbfs, "rms_dbfs": loudness.rms_dbfs, "crest_factor_db": loudness.crest_factor_db, "clipping_count": loudness.clipping_count},
        }
    stage_h_pcm = _read_pcm24_wav(stage_h_path)
    stage_h_loudness = measure_loudness(stage_h_pcm)
    import hashlib
    evidence["stage_h_v5_baseline_60s"] = {
        "path": str(stage_h_path),
        "sha256": hashlib.sha256(stage_h_path.read_bytes()).hexdigest(),
        "candidate_id": "hellcat_stage_h_v5",
        "render_sha256": "9" * 64,
        "source_metrics": _manifest_source_metrics(0, baseline=True),
        "health": {"sample_rate_hz": 48000, "channels": 2, "pcm": "PCM_24", "finite": True, "peak_dbfs": stage_h_loudness.peak_dbfs, "clipping_count": stage_h_loudness.clipping_count},
        "loudness": {"integrated_lufs": stage_h_loudness.integrated_lufs, "peak_dbfs": stage_h_loudness.peak_dbfs, "rms_dbfs": stage_h_loudness.rms_dbfs, "crest_factor_db": stage_h_loudness.crest_factor_db, "clipping_count": stage_h_loudness.clipping_count},
    }
    return {
        "package_id": "S12_Stage_I_Named_Source_Evidence_v1",
        "status": "SOURCE_EVIDENCE_READY",
        "sealed_key_read": False,
        "files": files,
        "evidence": evidence,
        "candidate_roles": {"a_balanced": profiles[_IDS[0]].candidate_id, "b_whine_forward": profiles[_IDS[1]].candidate_id, "c_softer_mechanical": profiles[_IDS[2]].candidate_id},
    }


def test_manifest_qualification_uses_only_frozen_metrics_and_zero_full_renders(tmp_path, monkeypatch) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, reference = _fixture(tmp_path)
    manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)

    import tools.sound_sim.s12.acoustic_identity_v015.stage_i.qualification as module
    monkeypatch.setattr(module, "compute_stage_i_perceptual_metrics", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("full render metric path used")))
    result = qualify_stage_i_source_manifest(
        manifest, profiles, probes, reference,
        track_p_guard_pass=True,
        regression_isolation_pass=True,
    )

    assert result["production_evidence"]["full_render_residency_max"] == 0
    assert result["automatic_reference_status"] == "PARTIAL / AUTOMATED_GATE_FAIL"
    assert set(result["candidates"]) == set(_IDS)
    assert result["candidates"][_IDS[0]]["metrics"]["boost_attack_10_90_s"] == pytest.approx(0.080, abs=0.003)
    assert result["candidates"][_IDS[0]]["gates"]["all_pass"] is True
    usage = result["candidates"][_IDS[0]]["candidate_parameter_usage"]
    assert "afterfire.gain_scale" in usage["inactive"]
    assert "afterfire.gain_scale" not in usage["active"]


def test_manifest_qualification_rejects_profile_probe_or_pcm_drift(tmp_path) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, reference = _fixture(tmp_path)
    manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    manifest["evidence"]["stage_i_v6_a_balanced_60s"]["profile_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="profile_sha256"):
        qualify_stage_i_source_manifest(manifest, profiles, probes, reference, track_p_guard_pass=True, regression_isolation_pass=True)

    manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    probes[_IDS[0]], probes[_IDS[1]] = probes[_IDS[1]], probes[_IDS[0]]
    with pytest.raises(ValueError, match="candidate_label"):
        qualify_stage_i_source_manifest(manifest, profiles, probes, reference, track_p_guard_pass=True, regression_isolation_pass=True)

    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, reference = _fixture(tmp_path)
    manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    paths[_IDS[0]].write_bytes(paths[_IDS[0]].read_bytes() + b"drift")
    with pytest.raises(ValueError, match="PCM byte SHA"):
        qualify_stage_i_source_manifest(manifest, profiles, probes, reference, track_p_guard_pass=True, regression_isolation_pass=True)


def test_formal_qualification_runner_uses_manifest_api(tmp_path, monkeypatch) -> None:
    _, _, paths, _, stage_h_path, profiles, probes, source_evidence, _, reference = _fixture(tmp_path)
    manifest = _source_manifest(paths, profiles, source_evidence, stage_h_path)
    manifest_path = tmp_path / "source_manifest.json"
    reference_path = tmp_path / "reference.json"
    output_path = tmp_path / "qualification.json"
    import json
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    reference_path.write_text(json.dumps(reference), encoding="utf-8")

    from tools.sound_sim.s12.acoustic_identity_v015.scripts.qualify_stage_i_named_sources import (
        run_stage_i_named_source_qualification,
    )
    by_profile_id = {profile.candidate_id: probes[label] for label, profile in profiles.items()}
    result = run_stage_i_named_source_qualification(
        manifest_path,
        {label: profile.path for label, profile in profiles.items()},
        reference_path,
        output_path,
        track_p_guard_pass=True,
        regression_isolation_pass=True,
        probe_builder=lambda label, profile: by_profile_id[profile.candidate_id],
    )

    assert result["production_evidence"]["full_render_residency_max"] == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "s12-stage-i-manifest-qualification-1"


def test_formal_qualification_script_supports_direct_help_invocation() -> None:
    import subprocess
    import sys
    script = Path(__file__).resolve().parents[1] / "scripts" / "qualify_stage_i_named_sources.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[5],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--source-manifest" in completed.stdout
