from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.render_candidate import render_stage_h_candidate


def test_ferrari_and_rx7_remain_bit_identical_when_hellcat_stage_h_changes() -> None:
    count = 12001
    time_s = np.arange(count, dtype=np.float64) / 48000.0
    phase = time_s / time_s[-1]
    trace = VehicleStateTrace(time_s, 900.0 + 4000.0 * phase, 0.2 + 0.6 * phase, 0.2 + 0.7 * phase, np.zeros(count)).validate()
    for vehicle in ("ferrari_458", "rx7_fd"):
        expected = _render_stateful(_RENDERERS[vehicle], vehicle, trace)
        actual = render_stage_h_candidate(vehicle, trace, None)
        np.testing.assert_array_equal(expected.pressure, actual.pressure)
