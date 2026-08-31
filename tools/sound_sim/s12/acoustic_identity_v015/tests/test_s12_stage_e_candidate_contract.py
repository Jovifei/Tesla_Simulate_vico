import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_e.candidate_profiles import load_stage_e_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.render_candidate import render_stage_e_candidate
from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
import numpy as np
from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful


ROOT = Path(__file__).resolve().parents[1]


def test_stage_e_profiles_load_and_record_parent():
    for name in ("Ferrari_candidate_v2.json", "Hellcat_candidate_v2.json", "RX7_candidate_v2.json"):
        profile = load_stage_e_candidate(ROOT / "targets" / "stage_e_candidates" / name)
        assert profile.payload["status"] == "Candidate"
        assert profile.payload["parent_candidate_id"]


def test_stage_e_rejects_unknown_fields(tmp_path):
    source = ROOT / "targets" / "stage_e_candidates" / "Ferrari_candidate_v2.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["unexpected"] = 1
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_stage_e_candidate(path)


def test_stage_e_requires_matching_base_commit(tmp_path):
    source = ROOT / "targets" / "stage_e_candidates" / "Ferrari_candidate_v2.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["base_commit"] = "0" * 40
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="base_commit"):
        load_stage_e_candidate(path)


def test_none_candidate_is_stage_c_bit_identical():
    t = np.linspace(0.0, 0.04, 5)
    trace = VehicleStateTrace(t, np.full(5, 3000.0), np.full(5, .6), np.full(5, .6), np.zeros(5))
    expected = _render_stateful(_RENDERERS["ferrari_458"], "ferrari_458", trace)
    actual = render_stage_e_candidate("ferrari_458", trace, None)
    assert np.array_equal(expected.pressure, actual.pressure)
    assert all(np.array_equal(expected.stems[name], actual.stems[name]) for name in expected.stems)
