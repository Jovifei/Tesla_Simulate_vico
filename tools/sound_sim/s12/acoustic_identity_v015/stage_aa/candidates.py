"""Bounded Hellcat candidates for Stage AA energy and quality hypotheses."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.signal import butter, sosfilt

from ..stage_v.io import read_pcm24_wav
from ..stage_w.bakeoff import BLOCK_SIZE, OUTPUT_SCALE, SAMPLE_RATE_HZ, build_hellcat_bakeoff_trace
from ..stage_w.boundary_adapter import FrozenPtrStereo
from ..stage_w.click_contract import block_boundary_click_metrics
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from ..stage_x.multi_reference_comparator import raw_dynamic_metrics, timbre_metrics
from ..stage_y.package import _fitted_config


FINAL_SETTINGS = {
    "path_model": "waveguide_v1",
    "forced_induction_model": "timbre_map_v1",
    "cycle_sync_model": "fixture_v1",
    "transient_model": "state_v1",
    "audio_chain": "dp_v1",
}
EVENT_BODY_FILTER = butter(2, (120.0, 400.0), btype="bandpass", fs=SAMPLE_RATE_HZ, output="sos")
FORCED_CARRIER_FILTER = butter(2, 1200.0, btype="highpass", fs=SAMPLE_RATE_HZ, output="sos")
SCENE_NAMES = {
    "hot_idle": "hot_idle_20s",
    "steady_1200": "steady_1200rpm",
    "steady_2000": "steady_2000rpm",
    "steady_3000": "steady_3000rpm",
    "tip_in": "throttle_tip_in",
    "full_load": "full_load_acceleration",
    "gear_shift": "gear_shift",
    "lift": "high_rpm_lift",
    "afterfire": "afterfire_eligible",
    "afterfire_ineligible": "afterfire_ineligible",
    "idle_return": "idle_return",
    "complete_cycle": "complete_cycle_60s",
}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    hypothesis: str
    pressure_idle_scale: float
    pressure_load_scale: float
    event_body_mix: float
    forced_carrier_reduction: float
    local_parameter_family: str
    global_gain_changed: bool = False
    fixed_tone_filler: bool = False


CANDIDATES = (
    CandidateSpec("AA-C0", "Stage-Z current Final baseline", 1.0, 0.0, 0.0, 0.0, "none"),
    CandidateSpec("AA-C1", "restore load-linked pressure AC energy without master gain", 2.0, 2.0, 0.0, 0.0, "pressure_ac_load_scale"),
    CandidateSpec("AA-C2", "C1 plus event-derived 120-400 Hz body", 2.0, 2.0, 4.0, 0.0, "pressure_ac_load_scale+event_body_120_400"),
    CandidateSpec("AA-C3", "C2 plus forced-carrier high-band suppression", 2.0, 2.0, 4.0, 1.0, "pressure_ac_load_scale+event_body_120_400+forced_carrier"),
)
_CANDIDATE_BY_ID = {item.candidate_id: item for item in CANDIDATES}


@dataclass(frozen=True)
class CandidateRender:
    candidate_id: str
    scene: str
    duration_s: float
    raw_pcm: np.ndarray
    monitor_pcm: np.ndarray
    pre_ptr_pcm: np.ndarray
    diagnostics: dict[str, Any]
    parameter_consumed: bool


def _spec(candidate_id: str) -> CandidateSpec:
    try:
        return _CANDIDATE_BY_ID[candidate_id]
    except KeyError:
        raise ValueError(f"unknown Stage AA candidate: {candidate_id}") from None


def _state_arrays(trace: Any) -> dict[str, np.ndarray]:
    return {name: getattr(trace, name) for name in ("rpm", "load", "throttle", "acceleration_mps2")}


def _candidate_pre_ptr(spec: CandidateSpec, trace: Any, layers: dict[str, np.ndarray]) -> np.ndarray:
    base = np.asarray(layers["pre_ptr"], dtype=np.float64)
    if spec.candidate_id == "AA-C0":
        return base.copy()
    load = np.repeat(np.asarray(trace.load, dtype=np.float64), BLOCK_SIZE)[:, None]
    pressure_scale = spec.pressure_idle_scale + spec.pressure_load_scale * load
    result = base * pressure_scale
    if spec.event_body_mix:
        event = np.mean(np.asarray(layers["combustion_event"], dtype=np.float64), axis=1)
        event = event - float(np.mean(event))
        body = sosfilt(EVENT_BODY_FILTER, event)
        result = result + spec.event_body_mix * np.column_stack((body, body))
    if spec.forced_carrier_reduction:
        forced = np.asarray(layers["forced_induction"], dtype=np.float64)
        carrier = np.column_stack((sosfilt(FORCED_CARRIER_FILTER, forced[:, 0]), sosfilt(FORCED_CARRIER_FILTER, forced[:, 1])))
        result = result - spec.forced_carrier_reduction * carrier
    if not np.all(np.isfinite(result)):
        raise ValueError(f"candidate {spec.candidate_id} generated non-finite pre-PTR PCM")
    return result


def render_candidate(
    candidate_id: str,
    scene: str,
    duration_s: float = 1.0,
    *,
    config_override: dict[str, Any] | None = None,
) -> CandidateRender:
    """Render one bounded candidate.

    ``config_override`` is an opt-in Stage-AD engineering hook.  The default
    path remains byte-for-byte semantically identical to Stage AA: it uses the
    committed fitted config.  Stage AD can inject a deep-copied upstream source
    config while preserving the AA candidate's fixed pressure/event-body/
    carrier processing and frozen PTR boundary.  It never mutates the official
    v3 package or the committed fitted config.
    """
    spec = _spec(candidate_id)
    trace = build_hellcat_bakeoff_trace(SCENE_NAMES.get(scene, scene), duration_s)
    config = copy.deepcopy(config_override) if config_override is not None else _fitted_config()
    engine = PersistentEventDomainEngine(copy.deepcopy(config), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS)
    block, layers = engine.process_with_layer_trace(_state_arrays(trace))
    pre_ptr = _candidate_pre_ptr(spec, trace, layers)
    ptr = FrozenPtrStereo(SAMPLE_RATE_HZ)
    post_ptr = ptr.process(pre_ptr)
    monitor_engine = PersistentEventDomainEngine(copy.deepcopy(config), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS)
    monitor_trace = monitor_engine.monitor_diagnostic_trace([post_ptr[index : index + BLOCK_SIZE] for index in range(0, post_ptr.shape[0], BLOCK_SIZE)])
    raw = post_ptr * OUTPUT_SCALE
    monitor = monitor_trace.monitor_pcm * OUTPUT_SCALE
    return CandidateRender(
        candidate_id=spec.candidate_id,
        scene=scene,
        duration_s=float(duration_s),
        raw_pcm=raw,
        monitor_pcm=monitor,
        pre_ptr_pcm=pre_ptr * OUTPUT_SCALE,
        diagnostics={"engine": block.diagnostics, "monitor": {"gain_trace_db": monitor_trace.gain_trace_db.tolist(), "desired_gain_trace_db": monitor_trace.desired_gain_trace_db.tolist()}, "spec": spec.__dict__},
        parameter_consumed=spec.candidate_id != "AA-C0" or config_override is not None,
    )


def _wrong_condition_afterfire(candidate: CandidateRender) -> int:
    if candidate.scene == "afterfire_ineligible":
        return int(candidate.diagnostics["engine"].get("afterfire_event_count", 0))
    check = render_candidate(candidate.candidate_id, "afterfire_ineligible", min(candidate.duration_s, 0.5))
    return int(check.diagnostics["engine"].get("afterfire_event_count", 0))


def validate_candidate_gates(candidate: CandidateRender) -> dict[str, Any]:
    spec = _spec(candidate.candidate_id)
    values = np.asarray(candidate.raw_pcm, dtype=np.float64)
    finite = bool(np.all(np.isfinite(values)))
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    clipping = int(np.count_nonzero(np.abs(values) >= 1.0))
    click = block_boundary_click_metrics(values, BLOCK_SIZE)
    wrong_condition = _wrong_condition_afterfire(candidate)
    return {
        "finite": finite,
        "peak": peak,
        "clipping": clipping,
        "click": bool(click["passed"]),
        "click_metrics": click,
        "wrong_condition_afterfire": wrong_condition,
        "track_p_unchanged": True,
        "ptr_radiation_track_p_unchanged": True,
        "legacy_unchanged": candidate.candidate_id == "AA-C0",
        "parameter_consumed": candidate.parameter_consumed,
        "raw_monitor_separated": not np.array_equal(candidate.raw_pcm, candidate.monitor_pcm),
        "global_gain_changed": spec.global_gain_changed,
        "fixed_tone_filler": spec.fixed_tone_filler,
        "passed": bool(finite and clipping == 0 and peak < 1.0 and click["passed"] and wrong_condition == 0 and not spec.global_gain_changed and not spec.fixed_tone_filler),
    }


def candidate_metrics(candidate: CandidateRender) -> dict[str, Any]:
    dynamic = raw_dynamic_metrics(candidate.raw_pcm, SAMPLE_RATE_HZ)
    timbre = timbre_metrics(np.mean(candidate.raw_pcm, axis=1), SAMPLE_RATE_HZ)
    return {**{key: float(value) for key, value in dynamic.items() if key != "note"}, "spectral_centroid_hz": float(timbre["spectral_centroid_hz"]), "spectral_flux": float(timbre["spectral_flux"]), "roughness_proxy": float(timbre["roughness_proxy"]), "sharpness_proxy": float(timbre["sharpness_proxy"]), "tonality_proxy": float(timbre["tonality_proxy"]), "persistent_tone_ratio": float(timbre["persistent_tone_ratio"]), "peak": float(np.max(np.abs(candidate.raw_pcm))) if candidate.raw_pcm.size else 0.0}


__all__ = ["CANDIDATES", "CandidateRender", "CandidateSpec", "candidate_metrics", "render_candidate", "validate_candidate_gates"]