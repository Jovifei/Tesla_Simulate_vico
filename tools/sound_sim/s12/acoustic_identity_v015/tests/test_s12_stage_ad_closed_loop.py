from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.candidates import render_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_ad.aa_c3_search import (
    AA_C3_SOURCE_CAUSAL_PARAMETERS,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ad.closed_loop import (
    ClosedLoopPolicy,
    reference_audio_from_caseset,
    run_closed_loop,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.package import _fitted_config


def _write_pcm16(path: Path, sample_rate: int = 48000, duration_s: float = 0.1) -> None:
    count = int(round(sample_rate * duration_s))
    t = np.arange(count, dtype=np.float64) / sample_rate
    audio = 0.1 * np.sin(2.0 * np.pi * 220.0 * t)
    pcm = np.clip(np.round(audio * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _caseset(path: Path) -> dict:
    return {
        "reference_evidence_level": "R2",
        "selection_reference_count": 1,
        "cases": [
            {
                "status": "BOUND",
                "scenario": "hot_idle",
                "reference_id": "hellcat:test:hot_idle:0-0.1",
                "recording_session_id": "session-a",
                "source_id": "source-a",
                "audio_path": str(path),
                "evidence_level": "R2",
                "rights_status": "R2_RELATIVE_REVIEW_ONLY",
                "start_s": 0.0,
                "end_s": 0.1,
                "segment_sha256": "test-segment",
                "speech_music_contamination": {"speech_contaminated": False},
            }
        ],
    }


def test_reference_audio_from_caseset(tmp_path: Path) -> None:
    wav = tmp_path / "reference.wav"
    _write_pcm16(wav)
    reference_audio, independent_count = reference_audio_from_caseset(_caseset(wav))
    assert independent_count == 1
    assert sorted(reference_audio) == ["hot_idle"]
    assert reference_audio["hot_idle"]["sample_rate"] == 48000
    assert reference_audio["hot_idle"]["metadata"]["evidence_level"] == "R2"
    assert reference_audio["hot_idle"]["audio"].ndim == 1


def test_closed_loop_uses_fixed_reference_distance_for_stop(tmp_path: Path) -> None:
    wav = tmp_path / "reference.wav"
    _write_pcm16(wav)
    distances = iter((0.40, 0.12))

    def fake_search(output_root: Path, reference_audio: dict, **kwargs: object) -> dict:
        del reference_audio
        output_root.mkdir(parents=True, exist_ok=True)
        distance = next(distances)
        parameter = kwargs["parameters_override"][0]  # type: ignore[index]
        return {
            "best": {
                "objective": -distance,
                "absolute_reference_distance": distance,
                "reference_objective": 0.01,
                "parameter_consumed": True,
                "overrides": {parameter.name: float(parameter.baseline)},
                "scene_results": {},
            }
        }

    policy = ClosedLoopPolicy(
        max_iterations=3,
        coarse_count=2,
        refine_count=0,
        target_reference_distance=0.15,
        minimum_reference_distance_gain=0.001,
    )
    summary = run_closed_loop(
        tmp_path / "loop",
        _caseset(wav),
        policy=policy,
        allowed_parameter_names=["attack_mix_120_400"],
        base_config={},
        search_fn=fake_search,
    )
    assert summary["iteration_count"] == 2
    assert summary["stop_reason"] == "TARGET_REFERENCE_DISTANCE_REACHED"
    assert summary["final_absolute_reference_distance"] == 0.12
    assert summary["automatic_profile_promotion"] is False
    assert (tmp_path / "loop" / "closed_loop_summary.json").is_file()


def test_aa_c3_config_injection_preserves_default_render() -> None:
    default = render_candidate("AA-C3", "steady_1200", 0.20)
    injected = render_candidate("AA-C3", "steady_1200", 0.20, config_override=_fitted_config())
    assert np.array_equal(default.pre_ptr_pcm, injected.pre_ptr_pcm)
    assert np.array_equal(default.raw_pcm, injected.raw_pcm)
    assert np.array_equal(default.monitor_pcm, injected.monitor_pcm)


def test_aa_c3_default_search_excludes_monitor_and_broad_mix_controls() -> None:
    assert "monitor_attack" not in AA_C3_SOURCE_CAUSAL_PARAMETERS
    assert "monitor_release" not in AA_C3_SOURCE_CAUSAL_PARAMETERS
    assert "monitor_max_makeup" not in AA_C3_SOURCE_CAUSAL_PARAMETERS
    assert "attack_mix_120_400" not in AA_C3_SOURCE_CAUSAL_PARAMETERS


def test_policy_rejects_invalid_shrink() -> None:
    policy = ClosedLoopPolicy(domain_shrink=0.0)
    try:
        policy.validate()
    except ValueError as error:
        assert "domain_shrink" in str(error)
    else:
        raise AssertionError("invalid domain shrink must fail")
