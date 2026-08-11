"""Stage-K regression/isolation checks for the Stage-C anchor."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_profiles import STAGE_K_VEHICLES
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import render_stage_k_candidate


def _trace() -> VehicleStateTrace:
    sample_rate_hz = 8000
    count = 241
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    phase = np.linspace(0.0, 1.0, count)
    rpm = 1000.0 + 3000.0 * phase
    load = 0.20 + 0.65 * phase
    throttle = 0.20 + 0.75 * phase
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _sha(render) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(render.pressure, dtype=np.float64).tobytes())
    for name in sorted(render.stems):
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(render.stems[name], dtype=np.float64).tobytes())
    return digest.hexdigest()


def test_all_eight_stage_c_vehicle_ids_are_explicit_and_none_path_is_unchanged() -> None:
    trace = _trace()
    assert len(_RENDERERS) == 8
    assert set(STAGE_K_VEHICLES).issubset(set(_RENDERERS))
    for vehicle_id, renderer in _RENDERERS.items():
        expected = _render_stateful(renderer, vehicle_id, trace)
        actual = render_stage_k_candidate(vehicle_id, trace, None)
        assert _sha(actual) == _sha(expected), vehicle_id


@pytest.mark.parametrize("vehicle_id", ("ferrari_458", "rx7_fd", "aventador_lp700", "supra_jza80"))
def test_non_target_vehicle_rejects_explicit_stage_k_candidate(vehicle_id: str) -> None:
    with pytest.raises(ValueError, match="unsupported Stage-K"):
        render_stage_k_candidate(vehicle_id, _trace(), object())  # type: ignore[arg-type]


def test_stage_k_unknown_vehicle_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Stage-K"):
        render_stage_k_candidate("unknown_vehicle", _trace(), None)


def test_stage_k_pipeline_declares_pre_ptr_overlay_boundary() -> None:
    # The public contract is also checked by the candidate-contract test; this
    # smoke check prevents a future facade from silently moving overlays after
    # the frozen adapter.
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import _SOURCE_RENDERERS

    assert set(_SOURCE_RENDERERS) == set(STAGE_K_VEHICLES)
