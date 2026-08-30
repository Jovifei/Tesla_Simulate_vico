from __future__ import annotations

import hashlib
import copy

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import (
    PARAMETER_REACHABLE,
    apply_parameters,
    hellcat_search_parameters,
    run_parameter_reachability,
)


def _sha(pcm: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(pcm, dtype=np.float64).tobytes()).hexdigest()


def _render(config, architecture: str, scene: str, duration_s: float = 2.0):
    trace = build_hellcat_bakeoff_trace(scene, duration_s)
    settings = {
        "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"},
        "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"},
    }[architecture]
    engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **settings)
    return engine.process_with_trace(
        {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}
    )


def test_crank_inertia_changes_post_ptr_sha_on_idle() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"crank_inertia": 0.24}, parameters)
    high = apply_parameters(base, {"crank_inertia": 0.44}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert a.post_ptr_raw is not None and b.post_ptr_raw is not None
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_idle_governor_changes_post_ptr_sha_on_idle() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"idle_governor": 0.15}, parameters)
    high = apply_parameters(base, {"idle_governor": 0.29}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_primary_attenuation_spread_changes_post_ptr_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"primary_attenuation_spread": 0.75}, parameters)
    high = apply_parameters(base, {"primary_attenuation_spread": 1.25}, parameters)
    a = _render(low, "P2H", "full_load_acceleration", 2.0)
    b = _render(high, "P2H", "full_load_acceleration", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)
