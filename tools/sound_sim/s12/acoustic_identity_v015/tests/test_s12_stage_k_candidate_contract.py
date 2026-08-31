"""Stage-K candidate contract RED/GREEN tests.

These tests deliberately build candidates in a temporary directory.  The
loader must still bind the declared parent and reference files to the checked
out acoustic_identity_v015 package, so a candidate cannot smuggle in an
unrelated target by moving its JSON file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_profiles import (
    BASE_COMMIT,
    STAGE_K_VEHICLES,
    load_stage_k_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import render_stage_k_candidate


ROOT = Path(__file__).resolve().parents[1]
TARGET_ROOT = ROOT / "targets"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_PARENTS = {
    "hellcat": ("targets/stage_i_candidates/Hellcat_candidate_v6_C_SofterMechanical.json", "hellcat_stage_i_v6_c_softer_mechanical"),
    "c63_w204": ("targets/stage_j_candidates/c63_w204_candidate_v1.json", "c63_w204_stage_j_v1"),
    "gtr_r35": ("targets/stage_j_candidates/gtr_r35_candidate_v1.json", "gtr_r35_stage_j_v1"),
    "lfa": ("targets/stage_j_candidates/lfa_candidate_v1.json", "lfa_stage_j_v1"),
}
_PARENT_STATUSES = {
    "hellcat": "UNQUALIFIED_DIAGNOSTIC_PARENT",
    "c63_w204": "STAGE_J_CANDIDATE_PARENT",
    "gtr_r35": "STAGE_J_CANDIDATE_PARENT",
    "lfa": "STAGE_J_CANDIDATE_PARENT",
}
_REFERENCES = {
    "hellcat": "reference_database/hellcat_reference_targets.json",
    "c63_w204": "reference_database/c63_w204_reference_targets.json",
    "gtr_r35": "reference_database/gtr_r35_reference_targets.json",
    "lfa": "reference_database/lfa_reference_targets.json",
}


def _trace(duration_s: float = 0.06, sample_rate_hz: int = 8000) -> VehicleStateTrace:
    count = int(round(duration_s * sample_rate_hz)) + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    phase = np.linspace(0.0, 1.0, count)
    rpm = 900.0 + 2200.0 * phase
    load = 0.20 + 0.60 * phase
    throttle = 0.20 + 0.70 * phase
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _payload(vehicle_id: str) -> dict[str, object]:
    parent_path, parent_id = _PARENTS[vehicle_id]
    reference_path = ROOT / _REFERENCES[vehicle_id]
    parent_file = ROOT / parent_path
    return {
        "schema_version": "s12-stage-k-candidate-profile-1",
        "candidate_id": f"{vehicle_id}_stage_k_test_v1",
        "vehicle_id": vehicle_id,
        "base_commit": BASE_COMMIT,
        "parent_candidate_id": parent_id,
        "parent_candidate_path": parent_path,
        "parent_candidate_sha256": _sha(parent_file),
        "status": "Candidate",
        "hypothesis": "contract fixture only",
        "reference_target": {
            "path": _REFERENCES[vehicle_id],
            "sha256": _sha(reference_path),
            "eligible_states": ["idle", "acceleration", "afterfire"],
        },
        "canonical_trace_version": "stage-k-four-vehicle-cycle-v1",
        "source": {},
        "operating_level": {},
        "idle": {},
        "afterfire": {},
        "shift_or_transient": {},
        "loudness": {"target_lufs": -16.0, "peak_limit_dbfs": -1.5, "whole_cycle_gain_only": True},
        "locked_layers": {
            "low_frequency_body": {"unchanged": True, "fingerprint": "stage-c-low-frequency-body"},
            "rumble": {"unchanged": True, "fingerprint": "stage-c-exhaust-rumble"},
            "pre_ptr_eq": {"unchanged": True, "fingerprint": "stage-c-pre-equalization"},
            "frozen_ptr": {"unchanged": True, "fingerprint": "stage-c-frozen-ptr"},
        },
        "provenance": {
            "source_level": "C",
            "source": "synthetic",
            "calibration": "uncalibrated",
            "claim": "not OEM reproduction",
            "parent_status": _PARENT_STATUSES[vehicle_id],
        },
    }


def _write_candidate(tmp_path: Path, vehicle_id: str, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / f"{vehicle_id}_candidate.json"
    path.write_text(json.dumps(payload or _payload(vehicle_id)), encoding="utf-8")
    return path


def test_stage_k_contract_exports_four_vehicles_and_loads_parent_bound_fixture(tmp_path: Path) -> None:
    assert set(STAGE_K_VEHICLES) == {"hellcat", "c63_w204", "gtr_r35", "lfa"}
    for vehicle_id in STAGE_K_VEHICLES:
        candidate = load_stage_k_candidate(_write_candidate(tmp_path, vehicle_id, _payload(vehicle_id)))
        assert candidate.vehicle_id == vehicle_id
        assert candidate.status == "Candidate"
        assert candidate.payload["base_commit"] == BASE_COMMIT
        assert candidate.payload["parent_candidate_id"] == _PARENTS[vehicle_id][1]


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda p: p.update({"unknown": True}), "top-level"),
        (lambda p: p.__setitem__("base_commit", "0" * 40), "base_commit"),
        (lambda p: p.__setitem__("parent_candidate_sha256", "0" * 64), "parent"),
        (lambda p: p.__setitem__("status", "Approved"), "Candidate"),
        (lambda p: p.__setitem__("provenance", {"source_level": "B"}), "provenance"),
    ],
)
def test_stage_k_contract_fails_closed_on_lineage_status_and_unknown_fields(
    tmp_path: Path, mutator, match: str,
) -> None:
    payload = _payload("c63_w204")
    mutator(payload)
    with pytest.raises(ValueError, match=match):
        load_stage_k_candidate(_write_candidate(tmp_path, "bad", payload))


def test_stage_k_contract_rejects_invalid_parameter_record_and_cross_vehicle_field(tmp_path: Path) -> None:
    payload = _payload("c63_w204")
    payload["source"] = {
        "gtr_only_field": {
            "value": 1.0,
            "unit": "ratio",
            "range": [0.0, 2.0],
            "source_level": "C",
            "source": "synthetic",
            "source_scope": "fixture",
            "verification_state": "candidate_assumption",
        }
    }
    with pytest.raises(ValueError, match="unknown source"):
        load_stage_k_candidate(_write_candidate(tmp_path, "bad-cross-vehicle", payload))

    payload = _payload("c63_w204")
    payload["source"] = {
        "bark_primary_order": {
            "value": 7.5,
            "unit": "order",
            "range": [7.8, 7.2],
            "source_level": "C",
            "source": "synthetic",
            "source_scope": "fixture",
            "verification_state": "candidate_assumption",
        }
    }
    with pytest.raises(ValueError, match="value/range"):
        load_stage_k_candidate(_write_candidate(tmp_path, "bad-range", payload))


def test_candidate_none_is_stage_c_bit_identical_for_all_eight_vehicles() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful

    trace = _trace()
    all_vehicle_ids = tuple(_RENDERERS)
    assert len(all_vehicle_ids) == 8
    for vehicle_id in all_vehicle_ids:
        expected = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
        actual = render_stage_k_candidate(vehicle_id, trace, None)
        assert np.array_equal(actual.pressure, expected.pressure), vehicle_id
        assert set(actual.stems) == set(expected.stems), vehicle_id
        for name in expected.stems:
            assert np.array_equal(actual.stems[name], expected.stems[name]), f"{vehicle_id}/{name}"


def test_stage_k_candidate_diagnostics_have_explicit_usage_sets(tmp_path: Path) -> None:
    candidate = load_stage_k_candidate(_write_candidate(tmp_path, "lfa"))
    rendered = render_stage_k_candidate("lfa", _trace(), candidate)
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert set(usage) == {"requested", "read", "configured", "active", "inactive", "unused"}
    assert set(usage["requested"]) == set(usage["read"]) | set(usage["unused"])
    assert set(usage["active"]).isdisjoint(set(usage["inactive"]))
    assert set(usage["active"]) | set(usage["inactive"]) == set(usage["read"])
