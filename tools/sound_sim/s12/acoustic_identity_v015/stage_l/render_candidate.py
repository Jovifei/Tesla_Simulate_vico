"""Stage-L L1 parent isolation and primitive contributor assembly."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import numpy as np

from ..acoustic_layers import (
    apply_afterfire, apply_exhaust_rumble, apply_idle_dynamics,
    apply_low_frequency_body, apply_pre_ptr_equalization,
)
from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import manage_bundle_loudness
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip
from ..sources.hellcat_crossplane_combustion_v2 import render_hellcat_crossplane_combustion_v2
from ..stage_f.reference_distance import final_pcm_band_shares
from ..sources.supercharged_hemi_source import render_hellcat
from ..sources.supercharger_whine_v4 import render_supercharger_whine_v4
from ..stage_k.candidate_profiles import load_stage_k_candidate
from ..stage_k.render_candidate import render_stage_k_candidate
from ..stage_k.source_level import OperatingLevelTrim, apply_source_operating_trim
from ..tuning.state_band_shaper import _inject_state_spectral_targets
from .candidate_profiles import PARENT_CANDIDATE_PATH, StageLCandidateProfile
from .crank_clock import HellcatCrankClock, build_hellcat_crank_clock


_SAMPLE_RATE_HZ = 48000
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_HEMI_CONTRIBUTORS = (
    "hemi_exhaust_left", "hemi_exhaust_right", "hemi_blowdown_body",
    "hemi_structure_shock", "hemi_mechanical_torque_ripple",
)
_BLOWER_CONTRIBUTORS = (
    "blower_shaft", "blower_rotor_family", "blower_gear_casing", "blower_sidebands",
    "blower_intake_voicing", "blower_bypass_release",
)
_CONTRIBUTORS = _HEMI_CONTRIBUTORS + _BLOWER_CONTRIBUTORS
_AGGREGATES = ("exhaust", "hemi_exhaust", "hemi_combustion_and_blowdown", "blower")


def render_stage_l_parent(trace: VehicleStateTrace) -> SourceRender:
    """Render the exact hash-bound Stage-K Hellcat v7 parent."""
    trace.validate()
    parent = load_stage_k_candidate(_PACKAGE_ROOT / PARENT_CANDIDATE_PATH)
    return render_stage_k_candidate("hellcat", trace, parent)


def render_legacy_hellcat_raw_with_clock(
    trace: VehicleStateTrace, clock: HellcatCrankClock, sample_rate_hz: int = _SAMPLE_RATE_HZ,
) -> SourceRender:
    """Validate the shared clock contract, then call the unchanged legacy raw HEMI renderer."""
    contract = _validate_shared_clock(trace, clock, sample_rate_hz)
    rendered = render_hellcat(trace, sample_rate_hz=sample_rate_hz, apply_state_shaping=False)
    if rendered.pressure.shape[0] != clock.engine_phase_cycles.shape[0]:
        raise ValueError("legacy HEMI output violates shared crank clock sample contract")
    diagnostics = dict(rendered.diagnostics)
    diagnostics["shared_crank_clock_contract"] = {
        **contract,
        "consumer": "legacy_raw_hemi_adapter",
        "phase_and_sample_contract_validated": True,
        "legacy_internal_event_schedule_from_shared_clock": False,
        "l2_event_consumption_status": "PENDING",
    }
    return replace(rendered, diagnostics=diagnostics).validate()


def render_stage_k_v4_blower_with_clock(
    trace: VehicleStateTrace, clock: HellcatCrankClock, sample_rate_hz: int = _SAMPLE_RATE_HZ,
) -> SourceRender:
    """Render the frozen v4 blower using the validated shared phase array by identity."""
    contract = _validate_shared_clock(trace, clock, sample_rate_hz)
    count = clock.engine_phase_cycles.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    stage_k_parent = load_stage_k_candidate(_PACKAGE_ROOT / PARENT_CANDIDATE_PATH)
    blower_overrides = {
        name: float(record["value"])
        for name, record in stage_k_parent.payload["source"].items()
    }
    rendered = render_supercharger_whine_v4(
        rpm, load, throttle, clock.engine_phase_cycles, sample_rate_hz, overrides=blower_overrides,
    )
    diagnostics = dict(rendered.diagnostics)
    diagnostics["shared_crank_clock_contract"] = {
        **contract,
        "consumer": "stage_k_v4_blower_adapter",
        "phase_and_sample_contract_validated": True,
        "engine_phase_array_passed_by_identity": True,
    }
    return replace(rendered, diagnostics=diagnostics).validate()


def render_crossplane_combustion_l2_with_clock(
    trace: VehicleStateTrace,
    clock: HellcatCrankClock,
    overrides: dict[str, float],
    sample_rate_hz: int = _SAMPLE_RATE_HZ,
) -> SourceRender:
    """Render L2 from the exact shared clock's gates, indices and bank labels."""
    contract = _validate_shared_clock(trace, clock, sample_rate_hz)
    count = clock.engine_phase_cycles.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rendered = render_hellcat_crossplane_combustion_v2(
        np.interp(time_s, trace.time_s, trace.rpm),
        np.interp(time_s, trace.time_s, trace.load),
        np.interp(time_s, trace.time_s, trace.throttle),
        clock,
        sample_rate_hz,
        overrides,
    )
    diagnostics = dict(rendered.diagnostics)
    diagnostics["shared_crank_clock_contract"] = {
        **contract,
        "consumer": "cross_plane_combustion_l2",
        "clock_object_shared": True,
        "event_gates_consumed": True,
        "event_sample_indices_consumed": True,
        "bank_labels_consumed": True,
        "internal_event_scheduling": "ACTIVE_L2_SHARED_CLOCK",
    }
    return replace(rendered, diagnostics=diagnostics).validate()


def render_stage_l_candidate(trace: VehicleStateTrace, candidate: StageLCandidateProfile) -> SourceRender:
    """Assemble the L1 source contract; L2-L4 controls remain explicit unused stubs."""
    trace.validate()
    if not isinstance(candidate, StageLCandidateProfile):
        raise TypeError("candidate must be a validated StageLCandidateProfile")
    if candidate.vehicle_id != "hellcat":
        raise ValueError("Stage-L candidate vehicle_id must be hellcat")
    clock = build_hellcat_crank_clock(trace, _SAMPLE_RATE_HZ)
    combustion_overrides = {
        name: float(record["value"])
        for name, record in candidate.payload["combustion_and_blowdown"].items()
    }
    combustion = render_crossplane_combustion_l2_with_clock(
        trace, clock, combustion_overrides, _SAMPLE_RATE_HZ,
    )
    blower = render_stage_k_v4_blower_with_clock(trace, clock, _SAMPLE_RATE_HZ)
    stems = {name: np.asarray(combustion.stems[name], dtype=np.float64) for name in _HEMI_CONTRIBUTORS}
    stems.update({name: np.asarray(blower.stems[name], dtype=np.float64) for name in _BLOWER_CONTRIBUTORS})
    contract = {"contributors": list(_CONTRIBUTORS), "diagnostic_aggregates": list(_AGGREGATES)}
    diagnostics = dict(combustion.diagnostics)
    diagnostics.update(blower.diagnostics)
    diagnostics["pressure_stem_contract"] = contract
    pressure = sum((stems[name] for name in _CONTRIBUTORS), np.zeros_like(combustion.pressure))
    raw = SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()
    shaped = _inject_state_spectral_targets(raw, "hellcat", trace, sample_rate_hz=_SAMPLE_RATE_HZ)
    shaped_stems = {name: np.asarray(shaped.stems[name], dtype=np.float64) for name in _CONTRIBUTORS}
    shaped_stems["exhaust"] = shaped_stems["hemi_exhaust_left"] + shaped_stems["hemi_exhaust_right"]
    shaped_stems["hemi_exhaust"] = shaped_stems["exhaust"]
    shaped_stems["hemi_combustion_and_blowdown"] = sum(
        (shaped_stems[name] for name in _HEMI_CONTRIBUTORS), np.zeros_like(shaped.pressure)
    )
    shaped_stems["blower"] = sum(
        (shaped_stems[name] for name in _BLOWER_CONTRIBUTORS), np.zeros_like(shaped.pressure)
    )
    shaped_pressure = sum(
        (shaped_stems[name] for name in _CONTRIBUTORS), np.zeros_like(shaped.pressure)
    )
    requested = sorted(candidate.requested_parameters())
    combustion_parameters = sorted(
        f"combustion_and_blowdown.{name}" for name in combustion_overrides
    )
    unused = sorted(set(requested) - set(combustion_parameters))
    final_diagnostics = dict(shaped.diagnostics)
    final_diagnostics.update(
        {
            "pressure_stem_contract": contract,
            "stage_l_candidate_id": candidate.candidate_id,
            "stage_l_candidate_status": candidate.status,
            "stage_l_parent_candidate_id": candidate.payload["parent_candidate_id"],
            "stage_l_phase": "L2_CROSSPLANE_COMBUSTION_BLOWDOWN",
            "candidate_parameter_usage": {
                "requested": requested, "read": combustion_parameters,
                "configured": combustion_parameters, "active": combustion_parameters,
                "inactive": [], "unused": unused,
            },
            "crank_clock_firing_order": tuple(candidate.payload["crank_clock"]["firing_order"]),
            "crank_clock_event_count": len(clock.event_sample_indices),
            "shared_clock_consumers": {
                "cross_plane_combustion_l2": {
                    "adapter": "render_crossplane_combustion_l2_with_clock",
                    "clock_object_shared": True,
                    "phase_sha256": _array_sha256(clock.engine_phase_cycles),
                    "sample_count": int(clock.engine_phase_cycles.shape[0]),
                    "sample_rate_hz": _SAMPLE_RATE_HZ,
                    "contract": "event_gates_sample_indices_and_bank_labels_consumed",
                    "event_gates_consumed": True,
                    "event_sample_indices_consumed": True,
                    "bank_labels_consumed": True,
                    "internal_event_scheduling": "ACTIVE_L2_SHARED_CLOCK",
                },
                "stage_k_v4_blower": {
                    "adapter": "render_stage_k_v4_blower_with_clock",
                    "clock_object_shared": True,
                    "phase_sha256": _array_sha256(clock.engine_phase_cycles),
                    "sample_count": int(clock.engine_phase_cycles.shape[0]),
                    "sample_rate_hz": _SAMPLE_RATE_HZ,
                    "contract": "engine_phase_array_consumed_by_identity",
                    "internal_event_scheduling": "ACTIVE_V4_PHASE_INPUT",
                },
            },
            "stage_l_l2_event_consumption": "ACTIVE",
            "pipeline_order": (
                "shared_hellcat_crank_clock", "cross_plane_combustion_blowdown_source",
                "twin_screw_intake_case_source", "state_spectral_targets_once",
                "source_operating_trim", "idle_dynamics", "deterministic_afterfire",
                "frozen_common_low_frequency_body", "frozen_exhaust_rumble",
                "hellcat_shift_load_transient", "hellcat_named_peak_budget",
                "frozen_common_pre_ptr_equalization", "frozen_ptr", "edge_fade",
                "fixed_whole_cycle_gain", "pcm24",
            ),
            "implemented_pipeline_stop": "state_spectral_targets_once_after_l2_combustion_blowdown",
            "post_frozen_ptr_added_energy": 0.0,
            "stage_l_scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        }
    )
    return SourceRender(shaped_pressure, shaped_stems, final_diagnostics).validate()


def render_stage_l_final_pcm_probe(
    trace: VehicleStateTrace, candidate: StageLCandidateProfile,
) -> dict[str, object]:
    """Measure L2 and its Stage-K parent through all currently available frozen layers."""
    trace.validate()
    source = render_stage_l_candidate(trace, candidate)
    operating = candidate.payload["operating_level"]
    trim = OperatingLevelTrim(
        low_load_gain_db=float(operating["low_load_gain_db"]["value"]),
        high_load_gain_db=float(operating["high_load_gain_db"]["value"]),
        blend_load=(
            float(operating["blend_load_low"]["value"]),
            float(operating["blend_load_high"]["value"]),
        ),
        smoothing_s=float(operating["smoothing_s"]["value"]),
    )
    continuous = tuple(name for name in _CONTRIBUTORS if name != "blower_bypass_release")
    render = apply_source_operating_trim(
        source, trace, stem_names=continuous, trim=trim, sample_rate_hz=_SAMPLE_RATE_HZ,
    )
    stems = dict(render.stems)
    stems["exhaust"] = stems["hemi_exhaust_left"] + stems["hemi_exhaust_right"]
    stems["hemi_exhaust"] = stems["exhaust"]
    stems["hemi_combustion_and_blowdown"] = sum(
        (stems[name] for name in _HEMI_CONTRIBUTORS), np.zeros_like(render.pressure)
    )
    stems["blower"] = sum(
        (stems[name] for name in _BLOWER_CONTRIBUTORS), np.zeros_like(render.pressure)
    )
    render = replace(render, stems=stems).validate()
    render = apply_idle_dynamics(render, "hellcat", trace, _SAMPLE_RATE_HZ)
    render = apply_afterfire(render, "hellcat", trace, _SAMPLE_RATE_HZ)
    render = _scale_event_stem(
        render, "afterfire", float(candidate.payload["afterfire"]["gain_scale"]["value"])
    )
    render = apply_low_frequency_body(render, "hellcat", trace, _SAMPLE_RATE_HZ)
    render = apply_exhaust_rumble(render, "hellcat", trace, _SAMPLE_RATE_HZ)
    render = apply_pre_ptr_equalization(render, "hellcat", trace, _SAMPLE_RATE_HZ)
    parent = render_stage_l_parent(trace)
    pre_gain = {
        "parent": _edge_fade(_apply_frozen_ptr(parent.pressure)),
        "candidate": _edge_fade(_apply_frozen_ptr(render.pressure)),
    }
    managed = manage_bundle_loudness(
        pre_gain, _SAMPLE_RATE_HZ,
        target_lufs=float(candidate.payload["loudness"]["target_lufs"]),
        peak_limit_dbfs=float(candidate.payload["loudness"]["peak_limit_dbfs"]),
    )
    parent_pcm = _pcm24_roundtrip(managed.segments["parent"])
    candidate_pcm = _pcm24_roundtrip(managed.segments["candidate"])
    parent_shares = final_pcm_band_shares(parent_pcm, _SAMPLE_RATE_HZ)
    candidate_shares = final_pcm_band_shares(candidate_pcm, _SAMPLE_RATE_HZ)
    target = _load_acceleration_target()
    return {
        "pipeline_order": (
            "source_operating_trim", "idle_dynamics", "deterministic_afterfire",
            "frozen_common_low_frequency_body", "frozen_exhaust_rumble",
            "l4_transient_pending_pass_through", "frozen_common_pre_ptr_equalization",
            "frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24",
        ),
        "l4_transient_status": "PENDING_PASS_THROUGH",
        "one_fixed_whole_cycle_gain_db": managed.gain_db,
        "parent_pcm_sha256": _array_sha256(parent_pcm),
        "candidate_pcm_sha256": _array_sha256(candidate_pcm),
        "parent_80_250_rms": _band_rms(parent_pcm, 80.0, 250.0),
        "candidate_80_250_rms": _band_rms(candidate_pcm, 80.0, 250.0),
        "parent_80_250_crest": _band_crest(parent_pcm, 80.0, 250.0),
        "candidate_80_250_crest": _band_crest(candidate_pcm, 80.0, 250.0),
        "parent_band_shares": parent_shares,
        "candidate_band_shares": candidate_shares,
        "target_band_shares": target,
        "parent_band_abs_error": tuple(abs(value - target[index]) for index, value in enumerate(parent_shares)),
        "candidate_band_abs_error": tuple(abs(value - target[index]) for index, value in enumerate(candidate_shares)),
    }


def _scale_event_stem(render: SourceRender, name: str, scale: float) -> SourceRender:
    if name not in render.stems or scale == 1.0:
        return render
    old = np.asarray(render.stems[name], dtype=np.float64)
    new = scale * old
    stems = dict(render.stems)
    stems[name] = new
    return replace(render, pressure=np.asarray(render.pressure) + new - old, stems=stems).validate()


def _load_acceleration_target() -> tuple[float, float, float, float]:
    import json

    payload = json.loads((_PACKAGE_ROOT / "reference_database" / "hellcat_reference_targets.json").read_text(encoding="utf-8"))
    return tuple(float(value) for value in payload["stock_median"]["acceleration_band_shares"])


def _band_signal(value: np.ndarray, low_hz: float, high_hz: float) -> np.ndarray:
    mono = np.mean(np.asarray(value, dtype=np.float64), axis=1)
    spectrum = np.fft.rfft(mono)
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / _SAMPLE_RATE_HZ)
    spectrum[(frequencies < low_hz) | (frequencies >= high_hz)] = 0.0
    return np.fft.irfft(spectrum, n=mono.size)


def _band_rms(value: np.ndarray, low_hz: float, high_hz: float) -> float:
    signal = _band_signal(value, low_hz, high_hz)
    return float(np.sqrt(np.mean(np.square(signal))))


def _band_crest(value: np.ndarray, low_hz: float, high_hz: float) -> float:
    signal = _band_signal(value, low_hz, high_hz)
    trim = min(int(0.1 * _SAMPLE_RATE_HZ), max(0, signal.size // 4))
    if trim:
        signal = signal[trim:-trim]
    return float(np.max(np.abs(signal)) / max(np.sqrt(np.mean(np.square(signal))), 1.0e-30))


def _validate_shared_clock(
    trace: VehicleStateTrace, clock: HellcatCrankClock, sample_rate_hz: int,
) -> dict[str, object]:
    if not isinstance(clock, HellcatCrankClock):
        raise TypeError("clock must be a HellcatCrankClock")
    expected = build_hellcat_crank_clock(trace, sample_rate_hz)
    array_names = (
        "engine_phase_cycles", "cycle_phase_cycles", "firing_event_gate",
        "left_bank_event_gate", "right_bank_event_gate", "torque_ripple_envelope",
    )
    if any(not np.array_equal(getattr(clock, name), getattr(expected, name)) for name in array_names):
        raise ValueError("HellcatCrankClock engine phase/sample contract does not match trace")
    if clock.event_sample_indices != expected.event_sample_indices or clock.bank_labels != expected.bank_labels:
        raise ValueError("HellcatCrankClock event/sample contract does not match trace")
    return {
        "sample_rate_hz": sample_rate_hz,
        "sample_count": int(clock.engine_phase_cycles.shape[0]),
        "engine_phase_sha256": _array_sha256(clock.engine_phase_cycles),
    }


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


__all__ = (
    "render_crossplane_combustion_l2_with_clock", "render_legacy_hellcat_raw_with_clock",
    "render_stage_k_v4_blower_with_clock",
    "render_stage_l_candidate", "render_stage_l_final_pcm_probe", "render_stage_l_parent",
)
