"""RED tests for the immutable frozen PTR/Radiation output stage."""

from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.boundary_adapter import FrozenPtrStereo
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import (
    PersistentEventDomainEngine,
)


def test_boundary_adapter_preserves_the_frozen_runtime_contract() -> None:
    adapter = FrozenPtrStereo(48000)
    assert adapter.provenance()["adapter"] == "RuntimePtrAdapter"


def test_persistent_engine_exposes_distinct_post_ptr_raw_and_provenance() -> None:
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, ptr_enabled=True)
    state = {"rpm": np.array([850.0]), "load": np.array([0.2]), "throttle": np.array([0.2]), "acceleration_mps2": np.array([0.0])}
    block = engine.process(state)
    assert block.post_ptr_raw is not None
    assert block.post_ptr_raw.shape == block.raw_pcm.shape
    assert np.all(np.isfinite(block.post_ptr_raw))
    assert not np.array_equal(block.post_ptr_raw, block.raw_pcm)
    assert block.diagnostics["ptr_status"] == "FROZEN_RUNTIME_PTR_ADAPTER"
    assert block.diagnostics["ptr_provenance"]["radiation_source_commit"] == "4afe65a67ed21822422f1eb6dbf43fdd627072d3"


def test_frozen_ptr_state_is_preserved_across_blocks_and_snapshot_restore() -> None:
    config = load_config("hellcat_v1")
    first = PersistentEventDomainEngine(config, 48000, 960, ptr_enabled=True)
    state = {"rpm": np.array([850.0]), "load": np.array([0.2]), "throttle": np.array([0.2]), "acceleration_mps2": np.array([0.0])}
    first.process(state)
    snapshot = first.snapshot_state()
    expected = first.process(state).post_ptr_raw
    first.process(state)
    first.restore_state(snapshot)
    replay = first.process(state).post_ptr_raw
    assert np.array_equal(expected, replay)
