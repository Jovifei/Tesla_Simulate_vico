from __future__ import annotations

import hashlib
import json
import gc
from pathlib import Path
import subprocess
import sys
import weakref

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.metric_artifacts import (
    write_stage_i_metric_artifacts,
)


_IDS = ("I6-A Balanced", "I6-B Whine Forward", "I6-C Softer Mechanical")


def _fixture(sample_rate_hz: int = 48000):
    count = int(0.25 * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.linspace(2200.0, 4400.0, count)
    phase = np.cumsum(rpm / 60.0) / sample_rate_hz
    blower = 0.05 * np.sin(2.0 * np.pi * 11.8 * phase)
    exhaust = 0.12 * np.sin(2.0 * np.pi * 4.0 * phase)
    pressure = np.column_stack((0.7 * (blower + exhaust), blower + exhaust))
    render = SourceRender(
        pressure=pressure,
        stems={
            "blower": np.column_stack((0.7 * blower, blower)),
            "exhaust": np.column_stack((0.7 * exhaust, exhaust)),
        },
        diagnostics={"scope": "synthetic"},
    )
    trace = VehicleStateTrace(
        time_s=time_s,
        rpm=rpm,
        load=np.linspace(0.2, 0.9, count),
        throttle=np.linspace(0.2, 0.9, count),
        acceleration_mps2=np.ones(count),
    )
    pcm = {candidate_id: pressure * (1.0 - 0.02 * index) for index, candidate_id in enumerate(_IDS)}
    renders = {candidate_id: render for candidate_id in _IDS}
    metrics = {
        candidate_id: {
            "blower_to_exhaust_ratio_idle_db": -24.0 + index,
            "blower_to_exhaust_ratio_acceleration_db": -8.0 + index,
            "blower_to_exhaust_ratio_full_pull_db": -6.0 + index,
            "boost_attack_10_90_s": 0.07 + 0.01 * index,
            "boost_release_90_10_s": 0.22 + 0.01 * index,
            "bypass_decay_90_10_s": 0.14 + 0.01 * index,
            "sideband_to_main_ratio": 0.12 + 0.01 * index,
            "upper_band_short_time_peak": 0.005 + 0.001 * index,
        }
        for index, candidate_id in enumerate(_IDS)
    }
    baseline = {
        "candidate_id": "Stage H v5",
        "blower_to_exhaust_ratio_idle_db": -25.0,
        "blower_to_exhaust_ratio_acceleration_db": -11.0,
        "blower_to_exhaust_ratio_full_pull_db": -8.5,
        "boost_attack_10_90_s": 0.16,
        "boost_release_90_10_s": 0.40,
        "bypass_decay_90_10_s": 0.0,
    }
    return pcm, renders, trace, metrics, baseline


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_metric_artifacts_are_headless_nonempty_and_deterministic(tmp_path) -> None:
    pcm, renders, trace, metrics, baseline = _fixture()
    output = tmp_path / "metrics"

    first = write_stage_i_metric_artifacts(output, pcm, renders, trace, metrics, baseline)
    first_hashes = {name: _sha(path) for name, path in first.items()}
    second = write_stage_i_metric_artifacts(output, pcm, renders, trace, metrics, baseline)

    assert set(first) == {
        "order_map",
        "spectrogram",
        "state_ratio_map",
        "transient_response",
        "candidate_comparison_metrics",
    }
    for name in ("order_map", "spectrogram", "state_ratio_map", "transient_response"):
        assert first[name].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert first[name].stat().st_size > 1000
    assert first_hashes == {name: _sha(path) for name, path in second.items()}
    payload = json.loads(first["candidate_comparison_metrics"].read_text(encoding="utf-8"))
    assert payload["representative_candidate_id"] == "I6-A Balanced"
    assert list(payload["candidates"]) == list(_IDS)
    assert payload["scope"] == "synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction"


def test_metric_artifacts_fail_closed_before_writing_on_missing_data(tmp_path) -> None:
    pcm, renders, trace, metrics, baseline = _fixture()
    del metrics["I6-C Softer Mechanical"]["boost_release_90_10_s"]
    output = tmp_path / "must_not_exist"

    with pytest.raises(ValueError, match="boost_release_90_10_s"):
        write_stage_i_metric_artifacts(output, pcm, renders, trace, metrics, baseline)

    assert not output.exists()


def test_metric_artifacts_reject_mismatched_candidate_sets(tmp_path) -> None:
    pcm, renders, trace, metrics, baseline = _fixture()
    del renders["I6-B Whine Forward"]
    with pytest.raises(ValueError, match="candidate IDs"):
        write_stage_i_metric_artifacts(tmp_path / "out", pcm, renders, trace, metrics, baseline)


def test_metric_artifacts_preserve_unmeasured_stage_h_transients_as_na(tmp_path) -> None:
    pcm, renders, trace, metrics, baseline = _fixture()
    for key in ("boost_attack_10_90_s", "boost_release_90_10_s", "bypass_decay_90_10_s"):
        del baseline[key]

    paths = write_stage_i_metric_artifacts(tmp_path / "out", pcm, renders, trace, metrics, baseline)
    payload = json.loads(paths["candidate_comparison_metrics"].read_text(encoding="utf-8"))

    assert payload["stage_h_baseline"]["boost_attack_10_90_s"] is None
    assert payload["stage_h_baseline"]["boost_release_90_10_s"] is None
    assert payload["stage_h_baseline"]["bypass_decay_90_10_s"] is None


def test_formal_metric_runner_writes_exact_deterministic_artifacts_with_one_live_full_render(tmp_path) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.scripts.build_stage_i_metric_artifacts import (
        run_stage_i_metric_artifacts,
    )

    from tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles import load_stage_i_candidate
    from tools.sound_sim.s12.acoustic_identity_v015.stage_i.probes import candidate_profile_binding
    _, _, trace, metrics, baseline = _fixture()
    candidate_root = Path(__file__).resolve().parents[1] / "targets" / "stage_i_candidates"
    candidate_paths = {
        "I6-A Balanced": candidate_root / "Hellcat_candidate_v6_A_Balanced.json",
        "I6-B Whine Forward": candidate_root / "Hellcat_candidate_v6_B_WhineForward.json",
        "I6-C Softer Mechanical": candidate_root / "Hellcat_candidate_v6_C_SofterMechanical.json",
    }
    profiles = {label: load_stage_i_candidate(path) for label, path in candidate_paths.items()}
    qualification = {
        "schema_version": "s12-stage-i-manifest-qualification-1",
        "candidates": {
            candidate_id: {
                "metrics": metrics[candidate_id],
                "gates": {"all_pass": True},
                "binding": candidate_profile_binding(profiles[candidate_id]),
            }
            for candidate_id in _IDS
        },
        "stage_h_baseline_metrics": baseline,
    }
    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(json.dumps(qualification), encoding="utf-8")
    active = 0
    maximum = 0

    def renderer(_, profile):
        nonlocal active, maximum
        count = trace.time_s.size
        time_s = trace.time_s
        scale = 0.04 + 0.003 * list(_IDS).index(next(label for label, path in candidate_paths.items() if path == profile.path))
        blower_mono = scale * np.sin(2.0 * np.pi * 720.0 * time_s)
        exhaust_mono = 0.10 * np.sin(2.0 * np.pi * 95.0 * time_s)
        blower = np.column_stack((0.7 * blower_mono, blower_mono))
        exhaust = np.column_stack((0.7 * exhaust_mono, exhaust_mono))
        render = SourceRender(blower + exhaust, {"blower": blower, "exhaust": exhaust, "unused_full_stem": blower * 0.1}, {"stage_i_candidate_id": profile.candidate_id})
        active += 1
        maximum = max(maximum, active)
        weakref.finalize(render, lambda: _released())
        return render

    def _released():
        nonlocal active
        active -= 1

    first = run_stage_i_metric_artifacts(
        candidate_paths,
        qualification_path,
        tmp_path / "first",
        trace_builder=lambda: trace,
        renderer=renderer,
        ptr_transform=lambda audio: audio,
        edge_transform=lambda audio: audio,
    )
    gc.collect()
    first_hashes = {name: _sha(path) for name, path in first["artifacts"].items()}
    second = run_stage_i_metric_artifacts(
        candidate_paths,
        qualification_path,
        tmp_path / "second",
        trace_builder=lambda: trace,
        renderer=renderer,
        ptr_transform=lambda audio: audio,
        edge_transform=lambda audio: audio,
    )
    gc.collect()

    assert set(first["artifacts"]) == {"order_map", "spectrogram", "state_ratio_map", "transient_response", "candidate_comparison_metrics"}
    assert first_hashes == {name: _sha(path) for name, path in second["artifacts"].items()}
    assert first["max_live_full_render"] == 1
    assert second["max_live_full_render"] == 1
    assert maximum == 1
    assert active == 0


def test_formal_metric_runner_supports_direct_help() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_stage_i_metric_artifacts.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=Path(__file__).resolve().parents[5],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--qualification-json" in completed.stdout
