from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import read_pcm24_wav
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import BLOCK_SIZE, SAMPLE_RATE_HZ, build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.package import _fitted_config


def _state(trace):
    return {name: getattr(trace, name) for name in ("rpm", "load", "throttle", "acceleration_mps2")}


def test_layer_trace_exposes_existing_signal_chain_without_changing_output() -> None:
    trace = build_hellcat_bakeoff_trace("hot_idle_20s", 0.25)
    settings = {
        "path_model": "waveguide_v1",
        "forced_induction_model": "timbre_map_v1",
        "cycle_sync_model": "fixture_v1",
        "transient_model": "state_v1",
        "audio_chain": "dp_v1",
    }
    traced = PersistentEventDomainEngine(_fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **settings)
    traced_block, layers = traced.process_with_layer_trace(_state(trace))
    plain = PersistentEventDomainEngine(_fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **settings)
    plain_block = plain.process_with_trace(_state(trace))
    required = {
        "vehicle_state",
        "combustion_event",
        "forced_induction",
        "per_cylinder_path",
        "waveguide",
        "bank_collector",
        "central_collector",
        "pre_transients",
        "transients",
        "dp_dc",
        "pre_ptr",
        "post_ptr_raw",
        "monitor",
    }
    assert required <= set(layers)
    expected_shape = (trace.rpm.size * BLOCK_SIZE, 2)
    assert all(value.shape == expected_shape for value in layers.values())
    assert np.array_equal(traced_block.raw_pcm, plain_block.raw_pcm)
    assert np.array_equal(traced_block.post_ptr_raw, plain_block.post_ptr_raw)
    assert np.all(np.isfinite(np.concatenate(list(layers.values()), axis=0)))
