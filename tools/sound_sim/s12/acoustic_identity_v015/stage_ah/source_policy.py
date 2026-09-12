"""Small source-local AH hypotheses, not an OEM acoustic model.

No downloaded samples or upstream code. See the accompanying source-adoption
report. Default EngineAcoustics has no policy and remains byte-identical.
Only the added fixed-frequency body branch is damped. Only explicitly scheduled
afterfire events are changed; ignition/gear/BOV scheduling is not inferred.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

import numpy as np
from scipy import signal

from .output_guard import (
    LEGACY_CLIP_V1,
    LINKED_SOFT_CEILING_V1,
    OUTPUT_GUARD_RECEIPT_SCHEMA,
    GuardConfig,
    ceiling_run_metrics,
    linked_soft_ceiling,
)

VARIANTS = ("r1_baseline", "body_damping", "afterfire_pressure", "combined")
OUTPUT_POLICIES = (LEGACY_CLIP_V1, LINKED_SOFT_CEILING_V1)


@dataclass(frozen=True)
class EventShape:
    attack_s: float
    decay_s: float
    tail_s: float
    noise_low_hz: float
    noise_high_hz: float


# Deliberately bounded engineering hypotheses, NOT measured engine parameters.
EVENT_SHAPES = {
    "hellcat": EventShape(.0009, .0060, .022, 450., 4800.),
    "ferrari_458": EventShape(.0006, .0035, .014, 700., 6500.),
    "lfa": EventShape(.0006, .0038, .015, 750., 6500.),
    "gtr_r35": EventShape(.0008, .0050, .019, 500., 5200.),
}


def signature(vehicle: str, variant: str, output_policy: str = LEGACY_CLIP_V1) -> dict:
    if vehicle not in EVENT_SHAPES or variant not in VARIANTS:
        raise ValueError("unknown AH vehicle or variant")
    if output_policy not in OUTPUT_POLICIES:
        raise ValueError(f"unknown AH output policy: {output_policy}")
    return {
        "schema": "s12.stage_ah.source_policy.v1",
        "source_variant": variant,
        "variant": variant,
        "event_shape": asdict(EVENT_SHAPES[vehicle]),
        "body_ring_idle_scale": .72,
        "body_ring_wot_scale": 1.,
        "pressure_event_energy_fraction": .04,
        "event_schedule": "EXPLICIT_EVENTS_UNCHANGED_NO_EXTRA_POPS",
        "output_policy": output_policy,
        "parent_denominator_policy": "PARENT_SCENE_PEAK_LOCKED_NO_CANDIDATE_RENORMALIZATION",
        "output_guard": (
            {"policy_id": LINKED_SOFT_CEILING_V1, "knee_linear": .90,
             "ceiling_linear": .94,
             "stereo_link": "instantaneous_frame_peak_common_gain"}
            if output_policy == LINKED_SOFT_CEILING_V1
            else {"policy_id": LEGACY_CLIP_V1, "ceiling_linear": .94}
        ),
        "rights": "ORIGINAL_IMPLEMENTATION_NO_THIRD_PARTY_ASSETS",
        "qualification": "ENGINEERING_HYPOTHESIS_NOT_HUMAN_VALIDATED",
    }


def validate_events(events, duration: float) -> list[tuple[float, float]]:
    result = []
    for event in events or []:
        if len(event) != 2:
            raise ValueError("afterfire event must be (seconds, nonnegative intensity)")
        time_s, intensity = map(float, event)
        if not np.isfinite(time_s) or not np.isfinite(intensity):
            raise ValueError("non-finite afterfire event")
        if time_s < 0 or intensity < 0 or time_s > duration:
            raise ValueError("afterfire event outside trace/intensity domain")
        result.append((time_s, intensity))
    return result


def pressure_events(vehicle: str, events, n: int, sr: int, seed: int) -> np.ndarray:
    """Biphasic pressure front + short colored tail, no sustained tone.

    A deterministic unit-energy pressure kernel and *expected* noise energy set
    the fixed event scale. There is no per-event peak measurement/rescaling and
    no track normalization. Energy budget derives from the old 60 ms noise law,
    with an explicit conservative 4% source-energy fraction. This is a
    source budget hypothesis, NOT a fitted loudness or a master-gain correction. Near-end events are
    clipped to the output window, not discarded. Independent RNG leaves the
    renderer's combustion/air/induction random streams unchanged.
    """
    if vehicle not in EVENT_SHAPES or n < 2 or sr < 16_000:
        raise ValueError("unsupported vehicle/shape/sample rate")
    events = validate_events(events, n / sr)
    shape = EVENT_SHAPES[vehicle]
    size = max(8, int(.16 * sr))
    t = np.arange(size, dtype=np.float64) / sr
    pressure = -np.expm1(-t / shape.attack_s) * np.exp(-t / shape.decay_s)
    front = np.diff(pressure, prepend=0.)
    front /= np.sqrt(np.sum(front * front))
    envelope = -np.expm1(-t / shape.attack_s) * np.exp(-t / shape.tail_s)
    sos = signal.butter(2, [shape.noise_low_hz, shape.noise_high_hz],
                        btype="bandpass", fs=sr, output="sos")
    impulse = np.zeros(size)
    impulse[0] = 1.
    impulse = signal.sosfilt(sos, impulse)
    # Expected variance of filtered unit-variance white noise.
    noise_norm = np.sqrt(np.sum(impulse * impulse) * np.sum(envelope * envelope))
    energy = .04 * 2.5**2 * np.sum(np.exp(-2. * np.linspace(0., 6., int(.06 * sr))))
    result = np.zeros(n, dtype=np.float64)
    vehicle_id = tuple(EVENT_SHAPES).index(vehicle)
    for index, (time_s, intensity) in enumerate(events):
        offset = int(time_s * sr)
        available = min(size, n - offset)
        if available <= 0 or intensity == 0:
            continue
        rng = np.random.default_rng(np.random.SeedSequence([int(seed), vehicle_id, index]))
        noise = signal.sosfilt(sos, rng.standard_normal(size)) * envelope / noise_norm
        pulse = intensity * np.sqrt(energy) * (np.sqrt(.75) * front + .5 * noise)
        result[offset:offset + available] += pulse[:available]
    return result


class SourcePolicy:
    """Per-render observer/policy. Not a streaming or concurrent DSP object."""

    def __init__(self, vehicle: str, variant: str, *, seed: int,
                 parent_peak: float | None = None, collect: bool = False,
                 output_policy: str = LEGACY_CLIP_V1, sample_rate: int = 48_000):
        signature(vehicle, variant, output_policy)  # validate even unused combinations
        if parent_peak is not None and (not np.isfinite(parent_peak) or parent_peak <= 0):
            raise ValueError("parent_peak must be finite and positive")
        self.vehicle, self.variant, self.seed = vehicle, variant, int(seed)
        self.output_policy = output_policy
        self.sample_rate = int(sample_rate)
        self.parent_peak, self.collect = parent_peak, bool(collect)
        self.begin_render()

    def begin_render(self):
        self.stems = {}
        self.receipt = {
            "receipt_schema": (
                OUTPUT_GUARD_RECEIPT_SCHEMA
                if self.output_policy == LINKED_SOFT_CEILING_V1
                else "s12.stage_ah.output_guard_receipt.v1"
            ),
            "source_variant": self.variant,
            "variant": self.variant,
            "output_policy": self.output_policy,
            "ceiling_samples": 0,
        }
        self._channel = 0
        self._event_source = None

    def observe(self, name, values):
        if self.collect:
            self.stems[name] = np.array(values, dtype=np.float64, copy=True)

    def afterfire_input(self, engine, legacy, events, n):
        self.observe("afterfire_legacy_input", legacy)
        self.receipt["events"] = [list(event) for event in events]
        if self.variant not in ("afterfire_pressure", "combined") or not events:
            return legacy
        self._event_source = pressure_events(self.vehicle, events, n, engine.sr, self.seed)
        self.observe("afterfire_pressure_input", self._event_source)
        return np.zeros_like(legacy)

    def afterfire_output(self, engine, n):
        if self._event_source is None:
            return np.zeros(n), np.zeros(n)
        # Reuse the selected IR BYTES with a causal crop on the new event branch.
        # Do not change combustion convolution or silently enable numeric flags.
        dry = signal.sosfilt(signal.butter(1, 10., "highpass", fs=engine.sr,
                                          output="sos"), self._event_source)
        wet = signal.fftconvolve(dry, engine.ir * engine.ir_volume, mode="full")[:n]
        out = .12 * dry + .88 * wet
        from ..stage_ad.engine_sim_acoustics import causal_fractional_delay
        left = causal_fractional_delay(out, engine.exhaust_length / 343. * engine.sr)
        right = causal_fractional_delay(left, 16.)
        self.observe("afterfire_causal_left", left)
        self.observe("afterfire_causal_right", right)
        return left, right

    def channel_sources(self, body, wet, direct, air, throttle, sr):
        suffix = ("left", "right")[self._channel]
        self._channel += 1
        self.observe("ir_wet_" + suffix, .88 * wet)
        self.observe("direct_" + suffix, .12 * direct)
        self.observe("turbulence_modulator_" + suffix, air)
        self.observe("body_ring_before_" + suffix, body)
        if self.variant in ("body_damping", "combined"):
            # 15 ms causal smoothing; no new oscillator, notch or output EQ.
            level = signal.lfilter([1. - np.exp(-1. / (.015 * sr))],
                                   [1., -np.exp(-1. / (.015 * sr))],
                                   np.clip(throttle, 0., 1.),
                                   zi=[float(np.clip(throttle[0], 0., 1.)) *
                                       np.exp(-1. / (.015 * sr))])[0]
            body = body * (.72 + .28 * level)
        self.observe("body_ring_after_" + suffix, body)
        return body

    def output_peak(self, actual, stereo):
        self.receipt["pre_saturation_peak"] = float(actual)
        self.observe("pre_saturation", stereo)
        used = self.parent_peak if self.parent_peak is not None else actual
        self.receipt["normalization_denominator"] = float(used)
        return used

    def finish(self, stereo):
        if self.output_policy == LINKED_SOFT_CEILING_V1:
            guarded, metrics = linked_soft_ceiling(
                stereo, GuardConfig(), sample_rate=self.sample_rate
            )
            self.receipt.update(metrics)
            # Preserve the AH legacy field as the pre-guard input count.
            self.receipt["ceiling_samples"] = metrics[
                "legacy_ceiling_input_exceedance_samples"
            ]
            self.receipt["guard_applied"] = True
            return guarded
        legacy_metrics = ceiling_run_metrics(stereo, sample_rate=self.sample_rate)
        legacy_count = legacy_metrics["ceiling_input_exceedance_samples"]
        self.receipt.update({
            "legacy_ceiling_input_exceedance_samples": legacy_count,
            "legacy_transfer_pre_guard_peak": float(np.max(np.abs(stereo))),
            "pre_guard_peak": float(np.max(np.abs(stereo))),
            "post_guard_peak": float(np.max(np.abs(stereo))),
            "post_guard_ceiling_exceedance_samples": 0,
            "pre_guard_exceedance_longest_run": legacy_metrics["exceedance_longest_run"],
            "emergency_clip_count": 0,
            "emergency_clip_error": 0.0,
            "guard_applied": False,
        })
        if self.variant == "r1_baseline":
            return stereo
        # Never wrap int16 on an unexpectedly high transient. A nonzero count
        # is a numerical-review blocker, not an automatic limiter qualification.
        self.receipt["ceiling_samples"] = legacy_count
        return np.clip(stereo, -.94, .94)


def pcm_sha256(pcm: np.ndarray) -> str:
    """Decoded signed little-endian PCM bytes, distinct from WAV-file SHA."""
    return hashlib.sha256(np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest()
