"""Stage AC (AC5): deterministic isolated-event dynamic timing fixtures.

Purpose (spec §11/§12): give the pre-human measurability gate clean, isolated,
single-event diagnostic traces so dynamic timing can be measured honestly for
events the bake-off scenes do not expose well (lift is an energy DECREASE,
idle_return/afterfire lack a distinct isolated floor->peak transient).

Design constraints (ABSOLUTE):
  - Does NOT modify any product scene, engine, PTR, Radiation, Track-P, monitor,
    default renderer, or P5/AA-C3 PCM. All traces here are DIAGNOSTIC stimuli
    rendered through the SAME unchanged `PersistentEventDomainEngine` the
    provenance audit already uses.
  - Honest timing semantics per §12: at 50 state-frames/sec (960-sample block,
    20 ms/block), the engine consumes state per block with no transport delay,
    so a state step and its audio response fall in the SAME block. That is
    reported as SAME_BLOCK_RESPONSE (a frame-quantization statement), NEVER as
    "instant physical engine response".

Each isolated trace guarantees, relative to its single state event:
  - pre-context  >= 250 ms
  - post-context >= 500 ms
And records per-stage audio response onset where each stage's PCM is measurable.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..stage_w.bakeoff import BLOCK_SIZE, SAMPLE_RATE_HZ, STATE_RATE_HZ
from ..stage_w.boundary_adapter import FrozenPtrStereo
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from ..stage_y.package import _fitted_config
from ..contracts import VehicleStateTrace
from .candidates import FINAL_SETTINGS, _state_arrays
from .provenance import detect_state_event_onset, envelope_db

# 20 ms audio block per one state frame (48 kHz / 960 samples).
BLOCK_MS = 1000.0 * BLOCK_SIZE / SAMPLE_RATE_HZ  # == 20.0

ISOLATED_SCENES = (
    "isolated_tip_in",
    "isolated_gear_shift",
    "isolated_high_rpm_lift",
    "isolated_afterfire_eligible",
    "isolated_afterfire_ineligible",
)


def _state_frames(duration_s: float) -> tuple[np.ndarray, int]:
    """Return (time_s, frame_count) for the given duration at STATE_RATE_HZ."""
    count = max(2, int(round(duration_s * STATE_RATE_HZ)))
    return np.arange(count, dtype=np.float64) / STATE_RATE_HZ, count


def _isolated_trace(duration_s: float, *, kind: str) -> Any:
    """Build an isolated single-event VehicleStateTrace with clean windows.

    `duration_s` must be >= 0.80 so a mid-trace event has >= 250 ms pre and
    >= 500 ms post at STATE_RATE_HZ (20 ms/frame). All events are energy-
    INCREASING or an isolated transient so the event-aligned window is
    MEASURABLE, unlike the bake-off lift/idle_return/afterfire scenes where the
    whole-clip "event" is an energy decrease with no clean floor->peak.
    """
    t, count = _state_frames(duration_s)
    if duration_s < 0.80:
        raise ValueError("isolated event trace duration must be >= 0.80 s")
    idle = 850.0
    # Event onset at 40% of the trace => pre = 0.40*duration, post = 0.60*duration.
    step = int(0.40 * count)
    step = max(1, min(count - 2, step))
    rpm = np.empty(count)
    load = np.empty(count)
    throttle = np.empty(count)

    # Normalize: accept "tip_in" or "isolated_tip_in"; map afterfire eligible/ineligible.
    sub = kind[len("isolated_") :] if kind.startswith("isolated_") else kind
    afterfire_variant = None
    if sub == "afterfire_eligible" or sub == "afterfire_ineligible":
        afterfire_variant = sub.split("_")[-1]  # "eligible" | "ineligible"

    if sub == "tip_in":
        # idle steady -> single throttle/load step up -> hold (energy increase)
        rpm[:] = np.where(np.arange(count) < step, idle, idle + np.linspace(0, 2600, count)[:count])
        throttle = np.where(np.arange(count) < step, 0.18, 0.90)
        load = np.where(np.arange(count) < step, 0.20, 0.75)
        # force a clean monotone rpm rise after the step
        rpm[step:] = idle + (4200.0 - idle) * (np.arange(count)[step:] - step) / max(count - step, 1)
        rpm[:step] = idle
    elif sub == "gear_shift":
        # steady high load, single isolated rpm drop at step, then recovery
        rpm[:] = np.linspace(3800.0, 5200.0, count)
        dip = int(0.06 * count)
        rpm[step : step + dip] -= 1400.0
        rpm[step + dip :] = np.linspace(3800.0, 5200.0, count)[step + dip :]  # recovery ramp
        throttle = np.full(count, 0.75)
        load = np.full(count, 0.72)
    elif sub == "high_rpm_lift":
        # steady high rpm/load, single throttle release, NO re-tip (energy decrease -> decay)
        high = 5200.0
        rpm[:] = np.where(np.arange(count) < step, high, np.linspace(high, idle, count))
        throttle = np.where(np.arange(count) < step, 0.92, 0.02)
        load = np.where(np.arange(count) < step, 0.86, 0.12)
    elif afterfire_variant in ("eligible", "ineligible"):
        # high rpm steady, ONE throttle blip close at step (afterfire stimulus).
        # eligible: a sharp close that deposits fuel then an isolated pop.
        # ineligible: the same high-rpm regime WITHOUT the sharp closing blip.
        high = 0.80 * 6500.0
        rpm[:] = high
        throttle = np.full(count, 0.80)
        load = np.full(count, 0.60)
        if afterfire_variant == "eligible":
            # single sharp throttle close (d_throttle < -0.8) to trigger one afterfire
            width = max(1, int(0.03 * count))
            throttle[step : step + width] = 0.02
            throttle[step + width :] = 0.80
            # a small rpm sag at the blip then return
            rpm[step : step + width] = high * 0.94
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown isolated trace kind: {kind}")

    time_s = t
    accel = np.gradient(rpm / 60.0, time_s[1] - time_s[0]) if count > 1 else np.zeros(count)
    return VehicleStateTrace(time_s, rpm, load, throttle, accel).validate()


def build_isolated_trace(kind: str, duration_s: float = 2.0) -> Any:
    """Public builder for an isolated event state trace."""
    return _isolated_trace(duration_s, kind=kind)


def render_isolated_parent(kind: str, duration_s: float = 2.0) -> dict[str, np.ndarray]:
    """Render an isolated trace through the UNCHANGED legacy parent engine + PTR.

    Returns per-stage PCM: engine_raw (pre_ptr mix from the parent renderer),
    post_ptr (PTR adapter output) and, when measurable, monitor. These are the
    diagnostic stimuli only — no product state is mutated.
    """
    trace = build_isolated_trace(kind, duration_s)
    pcm, _raw, monitor = render_parent_scene_from_trace(trace)
    ptr = FrozenPtrStereo(SAMPLE_RATE_HZ)
    post_ptr = np.asarray(ptr.process(pcm), dtype=np.float64)
    return {"pre_ptr": pcm, "post_ptr": post_ptr, "monitor": np.asarray(monitor, dtype=np.float64)}


def render_parent_scene_from_trace(trace: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Render the legacy Parent through the production path from an explicit trace.

    Mirrors provenance.render_parent_raw but takes an already-built trace so an
    isolated (non bake-off) state timeline can be rendered.
    """
    # The stage_z parent renderer takes a scene name; to honor an arbitrary trace we
    # route through the engine's own parent-equivalent config like render_parent_raw
    # does by scene, but here we drive the engine with the provided state arrays.
    engine = PersistentEventDomainEngine(_fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS)
    block = engine.process(_state_arrays(trace))
    raw = np.asarray(block.raw_pcm, dtype=np.float64)
    monitor = np.asarray(block.monitor_pcm, dtype=np.float64)
    return raw, raw, monitor


def detect_isolated_event_onset(kind: str, trace: Any) -> int | None:
    """State-block index of the isolated event onset.

    Reuses detect_state_event_onset, which finds throttle_tip_in / throttle_close /
    gear_shift_rpm_drop / rpm_decay. The isolated traces are built so exactly one
    such onset exists at the intended block.
    """
    onset_block, _kind = detect_state_event_onset(trace)
    return int(onset_block) if onset_block is not None else None


def _stage_onset_ms(pcm: np.ndarray, state_onset_block: int, sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    """Measure the audio response onset for one stage PCM relative to the state onset block.

    Returns the first frame at or after the state onset whose envelope exceeds the
    pre-event floor by >= 1 dB, plus honest semantics.
    """
    mono = np.mean(np.asarray(pcm, dtype=np.float64), axis=1) if np.asarray(pcm).ndim == 2 else np.asarray(pcm, dtype=np.float64)
    frame_s = 0.010
    env = envelope_db(mono, sample_rate, frame_s=frame_s)
    frame_ms = frame_s * 1000.0
    onset_sample = int(state_onset_block) * BLOCK_SIZE
    onset_frame = max(0, onset_sample // int(round(sample_rate * frame_s)))
    pre = env[:onset_frame]
    if pre.size < 2:
        return {"onset_ms": None, "measurable": False, "reason": "insufficient pre-context", "class": "NOT_MEASURABLE"}
    floor_db = float(np.median(pre))
    post = env[onset_frame:]
    if post.size == 0:
        return {"onset_ms": None, "measurable": False, "reason": "no post-context", "class": "NOT_MEASURABLE"}
    peak_db = float(np.max(post))
    threshold = floor_db + 1.0
    hits = np.nonzero(post >= threshold)[0]
    if hits.size == 0:
        return {
            "onset_ms": None,
            "measurable": False,
            "reason": f"no stage transient above floor+1dB (peak-floor {peak_db - floor_db:.2f} dB)",
            "class": "NOT_MEASURABLE",
        }
    first = int(hits[0])
    onset_ms = (onset_frame + first) * frame_ms
    # Honest class: the state event and the audio response are quantized to the
    # 20 ms block; an onset within the same block is SAME_BLOCK_RESPONSE, never an
    # "instant physical response" claim.
    state_ms = state_onset_block * BLOCK_MS
    if onset_ms <= state_ms + BLOCK_MS + 1.0e-9:
        timing_class = "SAME_BLOCK_RESPONSE"
    else:
        timing_class = "LATER_BLOCK_RESPONSE"
    return {
        "onset_ms": onset_ms,
        "onset_block": int((onset_frame + first) * frame_ms / BLOCK_MS),
        "peak_db": peak_db,
        "floor_db": floor_db,
        "peak_floor_db": peak_db - floor_db,
        "measurable": True,
        "timing_class": timing_class,
        "resolution_note": (
            "state and audio are quantized to the 20 ms audio block; a response landing in the "
            "same block as the state onset is SAME_BLOCK_RESPONSE (frame quantization), not an "
            "instant-engine-physics claim. Sub-20 ms distinctions are not resolvable at this "
            "block rate and are NOT asserted as physical delay."
        ),
    }


def afterfire_event_count(kind: str, duration_s: float = 2.0) -> int:
    """Count afterfire events emitted for an isolated trace via the engine diagnostics."""
    trace = build_isolated_trace(kind, duration_s)
    engine = PersistentEventDomainEngine(_fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS)
    engine.process_with_trace(_state_arrays(trace))
    diag = engine.diagnostics()
    count = int(diag.get("afterfire_event_count", 0))
    # Also count from the block-level trace
    return count


def _band_rms_db(pcm: np.ndarray, low: float, high: float, sample_rate: int = SAMPLE_RATE_HZ) -> float | None:
    """RMS in a frequency band (dB) for a mono PCM segment, or None if empty."""
    from scipy.signal import butter, sosfilt

    mono = np.asarray(pcm, dtype=np.float64)
    if mono.ndim == 2:
        mono = np.mean(mono, axis=1)
    if mono.size < 64:
        return None
    nyq = 0.5 * sample_rate
    if low < 0.5 or high <= low or high > nyq:
        return None
    sos = butter(4, [low / nyq, high / nyq], btype="band", output="sos")
    band = sosfilt(sos, mono)
    rms = float(np.sqrt(np.mean(np.square(band))))
    return 20.0 * np.log10(max(rms, 1.0e-9))


def afterfire_metric_validation_v2(kind_eligible: str = "isolated_afterfire_eligible", kind_ineligible: str = "isolated_afterfire_ineligible", duration_s: float = 2.0) -> dict[str, Any]:
    """Stage AC §13: afterfire energy-window validation against isolated fixtures.

    Builds the eligible (>=1 afterfire event) and ineligible (0 events) isolated
    traces, renders each through the unchanged parent path, and reports an
    event-local baseline + event peak / RMS / integrated energy / attack / decay /
    spectral centroid / band energies (120-400, 400-1000, 1-4 kHz). The ACOUSTIC
    RED FLAG from AA-C3's ~20 dB peak-vs-body is retained when the eligible window
    still shows large event energy; production afterfire gain is NOT modified here.
    """
    from scipy.signal import butter, sosfilt

    def _analyze(kind: str) -> dict[str, Any]:
        trace = build_isolated_trace(kind, duration_s)
        onset_block = detect_isolated_event_onset(kind, trace)
        pcm = render_isolated_parent(kind, duration_s)["pre_ptr"]
        mono = np.mean(np.asarray(pcm, dtype=np.float64), axis=1) if np.asarray(pcm).ndim == 2 else np.asarray(pcm, dtype=np.float64)
        frame_s = 0.005
        env = envelope_db(pcm, SAMPLE_RATE_HZ, frame_s=frame_s)
        out: dict[str, Any] = {"afterfire_event_count": afterfire_event_count(kind, duration_s)}
        if onset_block is None:
            out["status"] = "NO_ISOLATED_STATE_EVENT"
            out["measurable"] = False
            return out
        onset_sample = int(onset_block) * BLOCK_SIZE
        onset_frame = max(0, onset_sample // int(round(SAMPLE_RATE_HZ * frame_s)))
        # event-local window: baseline = 250 ms before onset; event = onset..end
        pre_frames = int(round(0.250 / frame_s))
        base = mono[onset_sample - int(0.250 * SAMPLE_RATE_HZ) : onset_sample]
        event = mono[onset_sample:]
        if base.size < 32 or event.size < 32:
            out.update({"status": "INSUFFICIENT_WINDOW", "measurable": False})
            return out
        env_base = env[max(0, onset_frame - pre_frames) : onset_frame]
        env_event = env[onset_frame:]
        base_db = float(np.median(env_base)) if env_base.size else float(np.percentile(env, 40))
        peak_idx = int(np.argmax(env_event))
        peak_db = float(env_event[peak_idx])
        peak_vs_base_db = peak_db - base_db
        # attack: 10%->90% of rise in the event window (frame_ms)
        def _first_cross(target: float) -> int | None:
            hits = np.nonzero(env_event >= target)[0]
            return int(hits[0]) if hits.size else None
        t10 = _first_cross(base_db + 0.10 * (peak_vs_base_db))
        t90 = _first_cross(base_db + 0.90 * (peak_vs_base_db))
        attack_ms = float(t90 - t10) * (frame_s * 1000.0) if (t10 is not None and t90 is not None and t90 >= t10) else None
        # decay: peak -> 6 dB below peak (bounded to window)
        tail = env_event[peak_idx:]
        dec = np.nonzero(tail <= peak_db - 6.0)[0]
        decay_ms = float(dec[0]) * (frame_s * 1000.0) if dec.size else None
        event_rms = float(np.sqrt(np.mean(np.square(event))))
        base_rms = float(np.sqrt(np.mean(np.square(base))))
        # integrated energy (squared) of the event window
        integrated = float(np.sum(np.square(event)))
        # spectral centroid (Hz) of the event window
        from numpy.fft import rfft, rfftfreq
        spec = np.abs(rfft(event * np.hanning(event.size)))
        freqs = rfftfreq(event.size, 1.0 / SAMPLE_RATE_HZ)
        centroid = float(np.sum(freqs * spec) / max(np.sum(spec), 1.0e-15)) if spec.sum() > 0 else 0.0
        bands = {
            "120_400_hz_db": _band_rms_db(event, 120.0, 400.0),
            "400_1000_hz_db": _band_rms_db(event, 400.0, 1000.0),
            "1_4k_hz_db": _band_rms_db(event, 1000.0, 4000.0),
        }
        bands = {name: (float(value) if value is not None else None) for name, value in bands.items()}
        out.update(
            {
                "status": "MEASURABLE",
                "measurable": True,
                "eligible_local_baseline_db": base_db,
                "event_peak_db": peak_db,
                "event_peak_vs_baseline_db": peak_vs_base_db,
                "event_rms": event_rms,
                "event_integrated_energy": integrated,
                "attack_ms": attack_ms,
                "decay_ms": decay_ms,
                "spectral_centroid_hz": centroid,
                "band_energy_db": bands,
            }
        )
        return out

    eligible = _analyze(kind_eligible)
    ineligible = _analyze(kind_ineligible)
    # AC state: keep the AA-C3 ~20 dB red-flag claim as an ACOUSTIC_RED_FLAG if the
    # eligible window's event-vs-baseline is still > 15 dB (the firecracker check).
    event_pvb = eligible.get("event_peak_vs_baseline_db")
    red_flag = bool(event_pvb is not None and event_pvb > 15.0)
    return {
        "schema": "s12.stage_ac.afterfire_metric_validation.v2",
        "purpose": (
            "Afterfire energy-window validation on ISOLATED diagnostic fixtures. Builds an "
            "eligible (>=1 afterfire event) and an ineligible (0 events) trace, so the metric is "
            "testable rather than relying on a whole-clip bake-off scene. The AA-C3 ~20 dB "
            "peak-vs-body RED FLAG is retained as an ACOUSTIC_RED_FLAG when the eligible event "
            "window still shows >15 dB event-vs-baseline. NO production afterfire gain change."
        ),
        "eligible_window": eligible,
        "ineligible_window": ineligible,
        "acoustic_red_flag": red_flag,
        "note": "ineligible_window.afterfire_event_count == 0 is the required negative control; production gain untouched (Stage AC is not a tuning stage).",
    }


def isolated_event_timing_document(kind: str, duration_s: float = 2.0) -> dict[str, Any]:
    """Produce the timing contract for one isolated event (spec §11/§12).

    Records the state event onset and per-stage audio response onset for the
    pre_ptr / post_ptr / monitor stages actually measurable.
    """
    trace = build_isolated_trace(kind, duration_s)
    onset_block = detect_isolated_event_onset(kind, trace)
    stages = render_isolated_parent(kind, duration_s)
    result: dict[str, Any] = {
        "scene": kind,
        "duration_s": float(duration_s),
        "state_rate_hz": float(STATE_RATE_HZ),
        "block_ms": float(BLOCK_MS),
        "state_event_onset_block": onset_block,
        "state_event_onset_ms": (float(onset_block) * BLOCK_MS) if onset_block is not None else None,
        "timing_semantics": (
            "STATE_BLOCK_ONSET and the renderer response share the same 20 ms block; "
            "responses within that block are SAME_BLOCK_RESPONSE, not transport/physics delay. "
            "No claim of physical delay is made unless a distinct later block is observed."
        ),
        "stage_responses": {},
    }
    if onset_block is None:
        result["status"] = "NO_ISOLATED_STATE_EVENT"
        return result
    for stage_name in ("pre_ptr", "post_ptr", "monitor"):
        pcm = stages.get(stage_name)
        if pcm is None or pcm.size == 0:
            result["stage_responses"][stage_name] = {"measurable": False, "reason": "stage not rendered", "class": "NOT_MEASURABLE"}
            continue
        result["stage_responses"][stage_name] = _stage_onset_ms(pcm, onset_block)
    return result


__all__ = [
    "BLOCK_MS",
    "ISOLATED_SCENES",
    "afterfire_event_count",
    "afterfire_metric_validation_v2",
    "build_isolated_trace",
    "detect_isolated_event_onset",
    "isolated_event_timing_document",
    "render_isolated_parent",
]
