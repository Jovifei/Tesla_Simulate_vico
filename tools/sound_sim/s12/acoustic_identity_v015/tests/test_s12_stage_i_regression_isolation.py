from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import (
    _RENDERERS,
    _render_stateful,
)


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = _ROOT / "targets" / "stage_i_candidates" / "Hellcat_candidate_v6.json"


def _trace(duration_s: float = 0.25) -> VehicleStateTrace:
    count = int(duration_s * 48000) + 1
    time_s = np.arange(count, dtype=np.float64) / 48000.0
    phase = time_s / duration_s
    return VehicleStateTrace(
        time_s,
        900.0 + 4000.0 * phase,
        0.2 + 0.6 * phase,
        0.2 + 0.7 * phase,
        np.zeros(count),
    ).validate()


def test_stage_i_none_is_stage_c_bit_identical_for_all_anchors() -> None:
    renderer = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.render_candidate"
    )
    trace = _trace()
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        expected = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
        actual = renderer.render_stage_i_candidate(vehicle_id, trace, None)
        np.testing.assert_array_equal(actual.pressure, expected.pressure)
        assert actual.stems.keys() == expected.stems.keys()
        for name in expected.stems:
            np.testing.assert_array_equal(actual.stems[name], expected.stems[name])


def test_stage_i_candidate_cannot_modify_other_anchors() -> None:
    profiles = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles"
    )
    renderer = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.render_candidate"
    )
    candidate = profiles.load_stage_i_candidate(_CANDIDATE)
    for vehicle_id in ("ferrari_458", "rx7_fd"):
        with pytest.raises(ValueError, match="does not match"):
            renderer.render_stage_i_candidate(vehicle_id, _trace(), candidate)


def test_stage_i_unknown_vehicle_fails_closed() -> None:
    renderer = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.render_candidate"
    )
    with pytest.raises(ValueError, match="unsupported Stage-I vehicle_id"):
        renderer.render_stage_i_candidate("unknown", _trace(), None)
