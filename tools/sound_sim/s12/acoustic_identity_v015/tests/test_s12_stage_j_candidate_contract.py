"""Stage-J candidate contract and pipeline RED/GREEN tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_j.candidate_profiles import (
    BASE_COMMIT,
    STAGE_J_VEHICLES,
    load_stage_j_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_j.render_candidate import render_stage_j_candidate


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT / "targets" / "stage_j_candidates"


def _trace(duration_s: float = 0.35, sample_rate_hz: int = 8000) -> VehicleStateTrace:
    count = int(round(duration_s * sample_rate_hz)) + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    phase = np.linspace(0.0, 1.0, count)
    rpm = 900.0 + 4500.0 * phase
    load = 0.20 + 0.70 * phase
    throttle = 0.20 + 0.75 * phase
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def test_three_stage_j_candidates_load_and_use_exact_base_commit() -> None:
    assert set(STAGE_J_VEHICLES) == {"c63_w204", "gtr_r35", "lfa"}
    for vehicle_id in STAGE_J_VEHICLES:
        path = CANDIDATE_ROOT / f"{vehicle_id}_candidate_v1.json"
        candidate = load_stage_j_candidate(path)
        assert candidate.vehicle_id == vehicle_id
        assert candidate.payload["base_commit"] == BASE_COMMIT
        assert candidate.status == "Candidate"
        assert candidate.requested_parameters()


def test_unknown_parameter_and_reference_drift_fail_closed(tmp_path: Path) -> None:
    source = CANDIDATE_ROOT / "c63_w204_candidate_v1.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["source"]["unknown"] = payload["source"]["bank_phase_offset_deg"]
    bad = tmp_path / source.name
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_stage_j_candidate(bad)


def test_candidate_none_is_stage_c_compatible_and_candidate_changes_output() -> None:
    trace = _trace()
    for vehicle_id in STAGE_J_VEHICLES:
        baseline = render_stage_j_candidate(vehicle_id, trace, None)
        candidate = load_stage_j_candidate(CANDIDATE_ROOT / f"{vehicle_id}_candidate_v1.json")
        rendered = render_stage_j_candidate(vehicle_id, trace, candidate)
        assert baseline.pressure.shape == rendered.pressure.shape
        assert np.all(np.isfinite(rendered.pressure))
        assert not np.array_equal(baseline.pressure, rendered.pressure)
        usage = rendered.diagnostics["candidate_parameter_usage"]
        assert usage["requested"] == usage["consumed"]
        assert usage["unused"] == []


def test_parameter_perturbation_changes_the_requested_vehicle_only() -> None:
    trace = _trace()
    baseline_sha: dict[str, str] = {}
    for vehicle_id in STAGE_J_VEHICLES:
        baseline = render_stage_j_candidate(vehicle_id, trace, None)
        baseline_sha[vehicle_id] = hashlib.sha256(np.asarray(baseline.pressure, dtype=np.float64).tobytes()).hexdigest()
    for vehicle_id in STAGE_J_VEHICLES:
        candidate = load_stage_j_candidate(CANDIDATE_ROOT / f"{vehicle_id}_candidate_v1.json")
        first = candidate.requested_parameters()[0]
        section, name = first.split(".", 1)
        entry = candidate.payload[section][name]
        midpoint = (entry["range"][0] + entry["range"][1]) / 2.0
        modified_value = entry["range"][1] if float(entry["value"]) == midpoint else midpoint
        modified = candidate.with_parameter(section, name, modified_value)
        changed = render_stage_j_candidate(vehicle_id, trace, modified)
        assert np.any(np.abs(changed.pressure - render_stage_j_candidate(vehicle_id, trace, candidate).pressure) > 0.0)
        for other in STAGE_J_VEHICLES:
            if other == vehicle_id:
                continue
            other_render = render_stage_j_candidate(other, trace, None)
            assert hashlib.sha256(np.asarray(other_render.pressure, dtype=np.float64).tobytes()).hexdigest() == baseline_sha[other]


def test_pipeline_diagnostics_keep_new_energy_before_frozen_ptr() -> None:
    render = render_stage_j_candidate("lfa", _trace(), load_stage_j_candidate(CANDIDATE_ROOT / "lfa_candidate_v1.json"))
    assert render.diagnostics["candidate_overlay_position"] == "before_pre_ptr_equalization_and_frozen_ptr"
    assert "pre_ptr_equalization" in render.diagnostics["pipeline_order"]
    assert render.diagnostics["post_frozen_ptr_added_energy"] == 0.0
