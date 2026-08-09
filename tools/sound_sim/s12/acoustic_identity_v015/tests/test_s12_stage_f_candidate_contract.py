import json
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.candidate_profiles import (
    load_stage_f_candidate,
    reference_sha256,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.render_candidate import (
    render_stage_f_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


def _trace():
    t = np.arange(0.0, 0.12, 1.0 / 48000.0)
    rpm = np.linspace(1100.0, 7600.0, t.size)
    load = np.full(t.size, 0.75)
    throttle = np.full(t.size, 0.8)
    return VehicleStateTrace(t, rpm, load, throttle, np.gradient(rpm / 60.0, t)).validate()


def _candidate(name):
    return load_stage_f_candidate(ROOT / "targets" / "stage_f_candidates" / name)


def test_stage_f_candidates_load_with_exact_contract():
    for name in ("Ferrari_candidate_v3.json", "Hellcat_candidate_v3.json", "RX7_candidate_v3.json"):
        candidate = _candidate(name)
        assert candidate.status == "Candidate"
        assert candidate.base_commit == "3c2c891b469adc7a507870c71ee94319e7125226"


def test_stage_f_rejects_unknown_override(tmp_path):
    source = ROOT / "targets" / "stage_f_candidates" / "Ferrari_candidate_v3.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["source"]["dead_parameter"] = payload["source"]["pulse_width_scale"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_stage_f_candidate(path)


def test_candidate_none_is_stage_c_bit_identical():
    from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful

    trace = _trace()
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        expected = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
        actual = render_stage_f_candidate(vehicle_id, trace, None)
        np.testing.assert_array_equal(expected.pressure, actual.pressure)
        assert set(expected.stems) == set(actual.stems)
        for name in expected.stems:
            np.testing.assert_array_equal(expected.stems[name], actual.stems[name])


def test_reference_hash_helper_is_sha256():
    path = ROOT / "reference_database" / "ferrari_458_reference_targets.json"
    assert len(reference_sha256(path)) == 64
