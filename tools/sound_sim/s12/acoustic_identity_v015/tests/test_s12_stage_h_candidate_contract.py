from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.candidate_profiles import load_stage_h_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.render_candidate import render_stage_h_candidate


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = _ROOT / "targets" / "stage_h_candidates" / "Hellcat_candidate_v5.json"


def _trace(duration_s: float = 0.8, sample_rate_hz: int = 48000) -> VehicleStateTrace:
    count = int(duration_s * sample_rate_hz) + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    phase = time_s / duration_s
    rpm = 900.0 + 5000.0 * phase
    load = 0.15 + 0.80 * phase
    throttle = 0.15 + 0.83 * phase
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def test_stage_h_candidate_is_strict_and_reference_bound() -> None:
    candidate = load_stage_h_candidate(_CANDIDATE)
    assert candidate.vehicle_id == "hellcat"
    assert candidate.status == "Candidate"
    assert candidate.requested_parameters()


def test_stage_h_unknown_vehicle_and_unknown_parameter_fail_closed(tmp_path: Path) -> None:
    candidate = load_stage_h_candidate(_CANDIDATE)
    payload = dict(candidate.payload)
    payload["vehicle_id"] = "ferrari_458"
    bad = tmp_path / "bad.json"
    import json

    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_stage_h_candidate(bad)


def test_stage_h_none_is_stage_c_bit_identical() -> None:
    trace = _trace()
    from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful

    expected = _render_stateful(_RENDERERS["hellcat"], "hellcat", trace)
    actual = render_stage_h_candidate("hellcat", trace, None)
    np.testing.assert_array_equal(actual.pressure, expected.pressure)
    assert actual.stems.keys() == expected.stems.keys()
    for name in expected.stems:
        np.testing.assert_array_equal(actual.stems[name], expected.stems[name])


def test_stage_h_candidate_vehicle_mismatch_fails_closed() -> None:
    candidate = load_stage_h_candidate(_CANDIDATE)
    with pytest.raises(ValueError):
        render_stage_h_candidate("rx7_fd", _trace(), candidate)
