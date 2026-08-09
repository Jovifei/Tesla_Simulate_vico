from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_d.candidate_profiles import (
    BASE_COMMIT,
    load_stage_d_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_d.render_candidate import render_stage_d_candidate
from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful
from tools.sound_sim.s12.acoustic_identity_v015.acoustic_layers.transient_peak_shaping import apply_transient_peak_shaping


def _parameter(value: float, unit: str = "ratio") -> dict[str, object]:
    return {
        "value": value,
        "unit": unit,
        "range": [value - 1.0, value + 1.0],
        "source_level": "C",
        "source": "synthetic",
        "source_scope": "stage_d_test",
        "verification_state": "candidate_assumption",
    }


def _profile(vehicle_id: str = "ferrari_458") -> dict[str, object]:
    return {
        "schema_version": "s12-stage-d-candidate-profile-1",
        "candidate_id": f"{vehicle_id}_stage_d_v1",
        "vehicle_id": vehicle_id,
        "base_commit": BASE_COMMIT,
        "parent_candidate_id": None,
        "status": "Candidate",
        "hypothesis": "event-driven identity refinement",
        "reference_target": {"path": "reference_database/test.json", "sha256": "0" * 64, "eligible_states": ["idle"]},
        "canonical_trace_version": "stage-d-audition-trace-1",
        "source": {"pulse_width_scale": _parameter(1.0)},
        "idle": {"variation": _parameter(0.24), "jitter_ms": _parameter(0.45, "ms"), "mechanical_texture": _parameter(0.18)},
        "afterfire": {"gain_scale": _parameter(1.0)},
        "shift": {"impact_scale": _parameter(1.0), "recovery_scale": _parameter(1.0)},
        "loudness": {"target_lufs": -16.0, "peak_limit_dbfs": -1.5, "whole_cycle_gain_only": True},
        "locked_layers": {"low_frequency_body": {"unchanged": True}, "rumble": {"unchanged": True}, "pre_ptr_eq": {"unchanged": True}, "frozen_ptr": {"unchanged": True}},
        "provenance": {"source_level": "C", "source": "synthetic", "calibration": "uncalibrated", "claim": "not OEM reproduction"},
    }


def _trace(duration_s: float = 0.08) -> VehicleStateTrace:
    count = int(duration_s * 48000) + 1
    time_s = np.linspace(0.0, duration_s, count)
    rpm = np.linspace(1100.0, 7000.0, count)
    return VehicleStateTrace(time_s, rpm, np.full(count, 0.7), np.full(count, 0.7), np.gradient(rpm / 60.0, time_s)).validate()


def test_candidate_loader_rejects_unknown_override(tmp_path: Path) -> None:
    payload = _profile()
    payload["source"]["unknown"] = _parameter(1.0)  # type: ignore[index]
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_stage_d_candidate(path)


def test_candidate_none_replays_stage_c_bit_identically() -> None:
    trace = _trace()
    vehicle_id = "ferrari_458"
    expected = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    actual = render_stage_d_candidate(vehicle_id, trace, None)
    np.testing.assert_array_equal(actual.pressure, expected.pressure)
    assert tuple(actual.stems) == tuple(expected.stems)
    for name in expected.stems:
        np.testing.assert_array_equal(actual.stems[name], expected.stems[name])


def test_candidate_loader_rejects_wrong_base_commit(tmp_path: Path) -> None:
    payload = _profile()
    payload["base_commit"] = "1" * 40
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="base_commit"):
        load_stage_d_candidate(path)


def test_transient_shaper_is_bit_identical_for_non_hellcat() -> None:
    trace = _trace()
    vehicle_id = "ferrari_458"
    render = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    actual = apply_transient_peak_shaping(render, vehicle_id, trace, None)
    np.testing.assert_array_equal(actual.pressure, render.pressure)
    for name in render.stems:
        np.testing.assert_array_equal(actual.stems[name], render.stems[name])


def test_unknown_stage_d_vehicle_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        render_stage_d_candidate("supra_jza80", _trace(), None)


def test_candidate_overlay_records_pre_ptr_position() -> None:
    path = Path(__file__).resolve().parents[1] / "targets" / "stage_d_candidates" / "Hellcat_candidate_v1.json"
    candidate = load_stage_d_candidate(path)
    render = render_stage_d_candidate("hellcat", _trace(), candidate)
    assert render.diagnostics["stage_d_overlay_position"] == "before_frozen_ptr"
