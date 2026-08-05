"""Deterministic idle-cycle and mechanical pressure layers."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_PROFILES: Mapping[str, Mapping[str, float]] = {
    # Phase 1 real-recording idle targets: crest=10.41, centroid=980Hz, 1-4kHz=0.467
    "ferrari_458": {"events_per_rev": 4.0, "seed": 1.7, "variation": 0.24, "jitter_ms": 0.45, "combustion_gain": 0.026, "combustion_decay_s": 0.030, "accessory_order": 1.65, "valve_hz": 2100.0, "crank_order": 1.0, "mechanical_texture": 0.18, "idle_crest_target": 10.41, "idle_modulation_peak_hz": 5.0},
    # Phase 1 real-recording idle targets: crest=15.91 (highest, sharp V8 pulses), centroid=290Hz, 20-250Hz=0.698
    "hellcat": {"events_per_rev": 4.0, "seed": 4.1, "variation": 0.32, "jitter_ms": 0.70, "combustion_gain": 0.085, "combustion_decay_s": 0.010, "accessory_order": 2.36, "valve_hz": 850.0, "crank_order": 0.5, "mechanical_texture": 0.22, "idle_crest_target": 15.91, "idle_modulation_peak_hz": 5.0},
    # Phase 1 real-recording idle targets: crest=2.78 (lowest, smooth rotary), centroid=156Hz, modulation@60Hz, 20-250Hz=0.968
    "rx7_fd": {"events_per_rev": 2.0, "seed": 7.3, "variation": 0.06, "jitter_ms": 0.20, "combustion_gain": 0.008, "combustion_decay_s": 0.120, "accessory_order": 1.35, "valve_hz": 1320.0, "crank_order": 1.5, "mechanical_texture": 0.08, "idle_crest_target": 2.78, "idle_modulation_peak_hz": 60.0},
    # Aventador V12: even-fire 12cyl, centroid=648Hz, low=0.24, crest=6.52 (refined, not lumpy).
    # valve_hz keeps the combustion ring (~648 Hz) for mid; valvetrain_hz lowered so the
    # high-band valvetrain comb does not over-lift the idle centroid above the 648 target.
    # Stronger combustion ring lifts the idle mid share toward the 0.638 reference.
    "aventador_lp700": {"events_per_rev": 6.0, "seed": 3.1, "variation": 0.18, "jitter_ms": 0.40, "combustion_gain": 0.050, "combustion_decay_s": 0.025, "accessory_order": 1.7, "valve_hz": 1380.0, "valvetrain_hz": 720.0, "valvetrain_gain": 0.0, "crank_order": 1.0, "mechanical_texture": 0.05, "idle_crest_target": 6.52, "idle_modulation_peak_hz": 6.0},
    # C63 V8 NA: reference idle is mid/high (centroid=687Hz, high band 0.355), not deep.
    # valve_hz~600 lifts the combustion ring (~282 Hz) for low/mid; the valvetrain ring is
    # placed at ~1300 Hz so the idle high band (0.355) is carried by idle_dynamics (idle-only,
    # no accel contamination) rather than the shared bark. valvetrain_gain trimmed from 0.003
    # so the 1300 Hz ring does not over-lift the idle centroid above the 687 target.
    "c63_w204": {"events_per_rev": 4.0, "seed": 5.9, "variation": 0.30, "jitter_ms": 4.0, "combustion_gain": 0.060, "combustion_decay_s": 0.012, "accessory_order": 2.36, "valve_hz": 520.0, "valvetrain_hz": 1300.0, "valvetrain_gain": 0.001, "crank_order": 0.5, "mechanical_texture": 0.04, "idle_crest_target": 11.57, "idle_modulation_peak_hz": 7.0},
    # GT-R V6 tt: reference idle centroid=400Hz (mid-dominant, near-zero 4k+ tail). valve_hz
    # 440 (combustion ring ~207 Hz) keeps the idle low/mid; mechanical + valvetrain high tail
    # trimmed so the 4k-12k tail does not lift the centroid above 400.
    "gtr_r35": {"events_per_rev": 3.0, "seed": 8.8, "variation": 0.20, "jitter_ms": 2.0, "combustion_gain": 0.080, "combustion_decay_s": 0.045, "accessory_order": 1.8, "valve_hz": 200.0, "valvetrain_gain": 0.0, "crank_order": 1.2, "mechanical_texture": 0.02, "idle_crest_target": 7.72, "idle_modulation_peak_hz": 5.0},
    # LFA V10: even-fire, centroid=1366Hz (highest), low=0.005, crest=7.34 (high scream, smooth).
    # Strong combustion ring + louder valvetrain ring so the idle high band (combustion ~1363 Hz,
    # valvetrain ~2900 Hz) carries the reference high=0.295 / highest=0.106 once the source low
    # component is removed.
    "lfa": {"events_per_rev": 5.0, "seed": 2.2, "variation": 0.12, "jitter_ms": 0.30, "combustion_gain": 0.080, "combustion_decay_s": 0.045, "accessory_order": 1.2, "valve_hz": 2000.0, "valvetrain_gain": 0.0, "accessory_gain": 0.001, "crank_order": 1.5, "mechanical_texture": 0.005, "idle_crest_target": 7.34, "idle_modulation_peak_hz": 8.0},
    # Supra I6 tt: reference idle centroid=118Hz, low=0.975 (deep rumble). The source exhaust
    # already delivers a deep ~53 Hz idle; idle_dynamics here adds only a very small ~28 Hz
    # combustion ring (valve_hz*0.47 = 28 Hz, in the 20-250 band) so the idle centroid lands
    # exactly on 118 Hz. Accessory/valvetrain/mechanical broadband are zeroed (idle-gated, so
    # accel bands are untouched) so no 250+ Hz tail lifts the idle.
    "supra_jza80": {"events_per_rev": 3.0, "seed": 4.4, "variation": 0.28, "jitter_ms": 3.5, "combustion_gain": 0.005, "combustion_decay_s": 0.025, "accessory_order": 1.5, "valve_hz": 60.0, "valvetrain_gain": 0.0, "accessory_gain": 0.0, "crank_order": 0.5, "mechanical_texture": 0.0, "idle_crest_target": 7.11, "idle_modulation_peak_hz": 5.0},
}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def apply_idle_dynamics(
    render: SourceRender, vehicle_id: str, trace: VehicleStateTrace, sample_rate_hz: int = 48000
) -> SourceRender:
    """Add vehicle-specific cycle fluctuation and engine-phase mechanical idle layers."""
    render.validate()
    trace.validate()
    if vehicle_id not in _PROFILES:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    profile = _PROFILES[vehicle_id]
    idle = np.clip((1850.0 - rpm) / 850.0, 0.0, 1.0)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    event_id = np.floor(phase * profile["events_per_rev"]).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    impulses = np.zeros(count, dtype=np.float64)
    variation_values: list[float] = []
    jitter_values: list[int] = []
    for sample in starts:
        cycle = event_id[sample]
        seed = profile["seed"]
        # Multi-frequency cycle variation: cylinder-to-cylinder compression difference,
        # mixture non-uniformity and ignition energy fluctuation (not a single sinusoid).
        variation = (
            np.sin(cycle * 12.9898 + seed) * 0.45
            + np.sin(cycle * 7.3137 + seed * 2.1) * 0.30
            + np.sin(cycle * 23.7173 + seed * 0.7) * 0.25
        ) * profile["variation"]
        variation = np.tanh(variation * 1.2)
        # Multi-frequency phase jitter: ECU timing micro-fluctuation + sensor noise.
        jitter = int(round((
            np.sin(cycle * 78.233 + seed * 3.0) * 0.55
            + np.sin(cycle * 137.51 + seed * 1.7) * 0.30
            + np.sin(cycle * 43.91 + seed * 5.3) * 0.15
        ) * profile["jitter_ms"] * sample_rate_hz / 1000.0))
        target = min(max(sample + jitter, 0), count - 1)
        impulses[target] += idle[sample] * (0.55 + 0.45 * load[sample]) * (1.0 + variation)
        variation_values.append(float(variation))
        jitter_values.append(jitter)
    combustion_mono = profile["combustion_gain"] * _ring(impulses, profile["valve_hz"] * 0.47, profile["combustion_decay_s"], sample_rate_hz)
    combustion = np.column_stack((combustion_mono, 0.79 * combustion_mono))
    texture = _mechanical_texture(count, sample_rate_hz, profile["mechanical_texture"], profile["seed"])
    tex_weight = profile["mechanical_texture"]
    accessory_mono = profile.get("accessory_gain", 0.006) * idle * (0.55 + load) * (
        np.sin(2.0 * np.pi * phase * profile["accessory_order"]) * (1.0 - tex_weight)
        + 0.28 * np.sin(2.0 * np.pi * phase * profile["accessory_order"] * 2.0)
        + texture * tex_weight
    )
    accessory = np.column_stack((0.70 * accessory_mono, accessory_mono))
    valvetrain_mono = profile.get("valvetrain_gain", 0.010) * idle * _ring(impulses, profile.get("valvetrain_hz", profile["valve_hz"]), 0.010, sample_rate_hz)
    valvetrain = np.column_stack((valvetrain_mono, 0.66 * valvetrain_mono))
    crank_mono = 0.010 * idle * (0.65 + 0.35 * load) * np.sin(2.0 * np.pi * phase * profile["crank_order"])
    crank = np.column_stack((0.88 * crank_mono, crank_mono))
    idle_layer = combustion + accessory + valvetrain + crank
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "idle_dynamics_model": "multi_freq_cycle_variation_broadband_mechanical_v2",
            "idle_scope": _SCOPE,
            "idle_cycle_amplitude_std": float(np.std(variation_values)) if variation_values else 0.0,
            "idle_phase_jitter_samples_peak": float(max((abs(value) for value in jitter_values), default=0)),
            "idle_event_count": int(np.count_nonzero(impulses)),
            "idle_crest_target_reference": profile["idle_crest_target"],
            "idle_modulation_peak_target_hz": profile["idle_modulation_peak_hz"],
            "idle_variation_frequencies": 3,
            "idle_mechanical_texture_weight": profile["mechanical_texture"],
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + idle_layer,
        stems={**render.stems, "idle_combustion_variation": combustion, "idle_accessory": accessory, "idle_valvetrain": valvetrain, "idle_crank": crank},
        diagnostics=diagnostics,
    ).validate()


def _ring(impulses: np.ndarray, frequency_hz: float, decay_s: float, sample_rate_hz: int) -> np.ndarray:
    radius = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    feedback = 2.0 * radius * np.cos(2.0 * np.pi * frequency_hz / sample_rate_hz)
    output = np.zeros_like(impulses, dtype=np.float64)
    for index, impulse in enumerate(impulses):
        previous = output[index - 1] if index else 0.0
        previous_two = output[index - 2] if index > 1 else 0.0
        output[index] = feedback * previous - radius * radius * previous_two + impulse * np.sin(2.0 * np.pi * frequency_hz / sample_rate_hz)
    return output


def _mechanical_texture(count: int, sample_rate_hz: int, strength: float, seed: float) -> np.ndarray:
    """Deterministic broadband mechanical friction texture (belt/pump/accessory drag).

    Low-passed pseudo-random signal that modulates the accessory carrier so the idle
    accessory layer no longer sounds like a clean sinusoidal oscillator. Deterministic
    via a seeded generator so renders stay reproducible.
    """
    if strength <= 0.0 or count < 1:
        return np.zeros(count, dtype=np.float64)
    rng = np.random.default_rng(int(abs(seed * 1e6)) % (2**32))
    samples = rng.uniform(-1.0, 1.0, size=count)
    cutoff = max(int(sample_rate_hz / 60), 1)
    kernel = np.ones(cutoff) / cutoff
    filtered = np.convolve(samples, kernel, mode="same")
    peak = float(np.max(np.abs(filtered))) or 1.0
    return filtered / peak
