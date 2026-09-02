"""Stage-AB AB1: AA-C3 gain/source provenance audit tooling.

Diagnostic-only. This module does NOT change AA-C0..AA-C3 behavior, Final
Settings, the frozen PTR, Radiation, Track-P, or any default renderer. It
re-uses the exact Stage-AA candidate transform formulas (candidates.py:90-108)
as explicit, individually toggleable factors so the AA-C3 metric improvements
can be attributed factor by factor.

Provenance variants (P-set):
  P0  = Stage-Z / AA-C0 baseline (no factor)
  P1  = broad pre-PTR state scaling only            base * (2 + 2*load)
  P2  = event-body 120-400 Hz injection only
  P3  = forced-carrier >1200 Hz suppression only
  P4  = event-body + carrier suppression, NO broad scale
  P5  = broad + event-body + carrier (must equal AA-C3 bit-exact)
  P6  = combustion-difference local state scaling (source-causal diagnostic;
        NOT an audition winner before Jovi feedback)
  P7/P8 = remaining factorial corners (broad+event / broad+carrier) so the
        three factors form a complete 2^3 design for exact Shapley attribution.

The combustion difference signal is defined as
    combustion_part = pre_ptr(full config) - pre_ptr(combustion event energy 0)
which is an exact causal difference decomposition (no linearity assumption).
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.signal import butter, sosfilt

from ..stage_w.bakeoff import BLOCK_SIZE, OUTPUT_SCALE, SAMPLE_RATE_HZ, build_hellcat_bakeoff_trace
from ..stage_w.boundary_adapter import FrozenPtrStereo
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from ..stage_y.package import _fitted_config
from ..stage_z.method_ablation import render_parent_scene
from .candidates import EVENT_BODY_FILTER, FORCED_CARRIER_FILTER, FINAL_SETTINGS, SCENE_NAMES, _state_arrays

PROVENANCE_SCHEMA = "s12.stage_ab.provenance.v1"

# Stage-AB energy-gain taxonomy categories (section 6 of the Stage-AB contract).
ENERGY_GAIN_TAXONOMY = (
    "MASTER_OUTPUT_GAIN",
    "MONITOR_GAIN",
    "BROAD_PRE_PTR_GAIN",
    "STATE_DEPENDENT_BROAD_PRE_PTR_GAIN",
    "STEM_LOCAL_GAIN",
    "SOURCE_EVENT_ENERGY",
    "PATH_TRANSFER_GAIN",
    "COLLECTOR_TRANSFER_GAIN",
    "FORCED_INDUCTION_GAIN",
    "TRANSIENT_GAIN",
    "FILTER_REBALANCE",
)

# Explicit stems a Round-2 raw candidate gain is allowed to target.
ROUND2_ALLOWED_STEM_TARGETS = (
    "combustion_event",
    "pressure_ac",
    "mechanical",
    "forced_induction",
    "afterfire",
    "body_path",
)

# Names of engine-captured layers usable for before/after per-stem accounting.
CAPTURED_STEM_LAYERS = (
    "bank_collector",
    "central_collector",
    "forced_induction",
    "mechanical",
    "pre_transients",
    "transients",
    "dp_dc",
    "pre_ptr",
)

PROVENANCE_SCENES = (
    "hot_idle",
    "steady_1200",
    "steady_2000",
    "steady_3000",
    "tip_in",
    "full_load",
    "gear_shift",
    "lift",
    "afterfire",
    "idle_return",
    "complete_cycle",
)

ANALYSIS_BANDS_HZ = (
    (20.0, 80.0),
    (80.0, 120.0),
    (120.0, 250.0),
    (250.0, 400.0),
    (400.0, 1000.0),
    (1000.0, 2000.0),
    (2000.0, 4000.0),
    (4000.0, 8000.0),
)

LF_GUARD_BANDS_HZ = (
    (20.0, 60.0),
    (60.0, 90.0),
    (90.0, 120.0),
    (120.0, 180.0),
    (180.0, 250.0),
    (250.0, 400.0),
)


@dataclass(frozen=True)
class ProvenanceVariant:
    variant_id: str
    hypothesis: str
    broad_scale: bool = False
    event_body: bool = False
    carrier_suppression: bool = False
    combustion_local_scale: bool = False


PROVENANCE_VARIANTS = (
    ProvenanceVariant("P0", "Stage-Z / AA-C0 baseline; no candidate factor"),
    ProvenanceVariant("P1", "only broad pre-PTR state scaling base*(2+2*load)", broad_scale=True),
    ProvenanceVariant("P2", "only event-derived 120-400 Hz body injection", event_body=True),
    ProvenanceVariant("P3", "only forced-carrier >1200 Hz suppression", carrier_suppression=True),
    ProvenanceVariant("P4", "event body + carrier suppression without broad scale", event_body=True, carrier_suppression=True),
    ProvenanceVariant("P5", "broad scale + event body + carrier suppression (= AA-C3)", broad_scale=True, event_body=True, carrier_suppression=True),
    ProvenanceVariant("P6", "combustion-difference local state scaling (source-causal diagnostic)", combustion_local_scale=True),
    ProvenanceVariant("P7", "broad scale + event body (factorial corner)", broad_scale=True, event_body=True),
    ProvenanceVariant("P8", "broad scale + carrier suppression (factorial corner)", broad_scale=True, carrier_suppression=True),
)

VARIANT_BY_ID = {item.variant_id: item for item in PROVENANCE_VARIANTS}

AA_C3_BROAD_IDLE_SCALE = 2.0
AA_C3_BROAD_LOAD_SCALE = 2.0
AA_C3_EVENT_BODY_MIX = 4.0
AA_C3_CARRIER_REDUCTION = 1.0


def classification_for_candidate(candidate_id: str) -> dict[str, Any]:
    """Taxonomy classification of an existing Stage-AA candidate parameter."""
    classified: dict[str, dict[str, Any]] = {
        "AA-C0": {
            "parameters": {},
            "gain_scope": "none",
            "affected_stems": [],
            "location_in_chain": "n/a",
            "state_dependency": "none",
            "is_broad_mix_scaling": False,
            "physical_interpretability": "baseline",
            "taxonomy_categories": [],
        },
    }
    broad = {
        "parameters": {
            "pressure_idle_scale": "entire pre_ptr mix scaled by pressure_idle_scale + pressure_load_scale * load (candidates.py:94-96)",
            "pressure_load_scale": "see pressure_idle_scale",
            "event_body_mix": "adds band-limited combustion_event layer content (stem-derived additive)",
            "forced_carrier_reduction": "subtracts high-passed forced_induction layer content (stem-derived subtractive)",
        },
        "gain_scope": "BROAD_PRE_PTR (multiplicative) + stem-derived additive/subtractive rebalance",
        "affected_stems": ["bank_collector", "central_collector", "forced_induction", "mechanical", "transients", "dp_dc chain output"],
        "location_in_chain": "post transfer_ir, pre PTR (the entire layers['pre_ptr'] output)",
        "state_dependency": "load-dependent: scale = pressure_idle_scale + pressure_load_scale * load",
        "is_broad_mix_scaling": True,
        "physical_interpretability": (
            "NOT a source-pressure-AC repair. layers['pre_ptr'] is the full mix of combustion, forced induction, "
            "mechanical, cycle-sync, transient and dp_dc/transfer-IR chain output (persistent_engine.py:694-708), so "
            "base*(2+2*load) scales all of it. Classified STATE_DEPENDENT_BROAD_PRE_PTR_SCALING."
        ),
        "taxonomy_categories": [
            "STATE_DEPENDENT_BROAD_PRE_PTR_GAIN",
            "FILTER_REBALANCE",
        ],
    }
    for candidate_id_in in ("AA-C1", "AA-C2", "AA-C3"):
        classified[candidate_id_in] = dict(broad)
    try:
        return classified[candidate_id]
    except KeyError:
        raise ValueError(f"unknown Stage AA candidate: {candidate_id}") from None


def energy_gain_taxonomy_document() -> dict[str, Any]:
    """Full taxonomy mapping for every Stage-AA candidate parameter (section 6)."""
    return {
        "schema": "s12.stage_ab.energy_gain_taxonomy.v1",
        "categories": ENERGY_GAIN_TAXONOMY,
        "hard_gate_extension_required": [
            "gain_scope",
            "affected_stems",
            "location_in_chain",
            "state_dependency",
            "is_broad_mix_scaling",
            "physical_interpretability",
        ],
        "candidate_mapping": {
            "AA-C0": classification_for_candidate("AA-C0"),
            "AA-C1": classification_for_candidate("AA-C1"),
            "AA-C2": classification_for_candidate("AA-C2"),
            "AA-C3": classification_for_candidate("AA-C3"),
        },
        "notes": [
            "global_gain_changed=False (no constant master gain) does NOT imply stem-local: the AA-C1..C3 "
            "pressure scales multiply the whole pre_ptr mix with a load-dependent factor.",
            "event_body_mix and forced_carrier_reduction are stem-derived (combustion_event / forced_induction "
            "layers) and therefore map to FILTER_REBALANCE, not to BROAD_PRE_PTR_GAIN.",
        ],
    }


def _zero_combustion_config() -> dict[str, Any]:
    config = copy.deepcopy(_fitted_config())
    node = config["combustion_event"]["event_energy"]
    if isinstance(node, dict) and "value" in node:
        node["value"] = 0.0
    else:
        config["combustion_event"]["event_energy"] = 0.0
    return config


def render_scene_layers(scene: str, duration_s: float = 1.0) -> dict[str, Any]:
    """Render the shared source realization for one scene once, reuse across variants."""
    trace = build_hellcat_bakeoff_trace(SCENE_NAMES.get(scene, scene), duration_s)
    engine = PersistentEventDomainEngine(_fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS)
    _block, layers = engine.process_with_layer_trace(_state_arrays(trace))
    no_combustion_engine = PersistentEventDomainEngine(
        _zero_combustion_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS
    )
    _nc_block, no_combustion_layers = no_combustion_engine.process_with_layer_trace(_state_arrays(trace))
    base = np.asarray(layers["pre_ptr"], dtype=np.float64)
    no_combustion = np.asarray(no_combustion_layers["pre_ptr"], dtype=np.float64)
    return {
        "trace": trace,
        "layers": layers,
        "base_pre_ptr": base,
        "no_combustion_pre_ptr": no_combustion,
        "combustion_part": base - no_combustion,
    }


def _load_column(trace: Any) -> np.ndarray:
    return np.repeat(np.asarray(trace.load, dtype=np.float64), BLOCK_SIZE)[:, None]


def _apply_broad_scale(base: np.ndarray, trace: Any) -> np.ndarray:
    pressure_scale = AA_C3_BROAD_IDLE_SCALE + AA_C3_BROAD_LOAD_SCALE * _load_column(trace)
    return base * pressure_scale


def _apply_event_body(result: np.ndarray, layers: dict[str, np.ndarray]) -> np.ndarray:
    event = np.mean(np.asarray(layers["combustion_event"], dtype=np.float64), axis=1)
    event = event - float(np.mean(event))
    body = sosfilt(EVENT_BODY_FILTER, event)
    return result + AA_C3_EVENT_BODY_MIX * np.column_stack((body, body))


def _apply_carrier_suppression(result: np.ndarray, layers: dict[str, np.ndarray]) -> np.ndarray:
    forced = np.asarray(layers["forced_induction"], dtype=np.float64)
    carrier = np.column_stack(
        (
            sosfilt(FORCED_CARRIER_FILTER, forced[:, 0]),
            sosfilt(FORCED_CARRIER_FILTER, forced[:, 1]),
        )
    )
    return result - AA_C3_CARRIER_REDUCTION * carrier


def render_provenance_variant(
    variant: str | ProvenanceVariant,
    scene: str,
    duration_s: float = 1.0,
    scene_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render one provenance variant for one scene.

    Returns raw/monitor/pre_ptr PCM plus the per-stem before/after accounting.
    Mirrors candidates.render_candidate post-PTR and monitor handling exactly.
    """
    spec = VARIANT_BY_ID[variant] if isinstance(variant, str) else variant
    data = scene_data if scene_data is not None else render_scene_layers(scene, duration_s)
    trace = data["trace"]
    layers = data["layers"]
    base = data["base_pre_ptr"]
    load_col = _load_column(trace)

    if spec.combustion_local_scale:
        combustion_part = data["combustion_part"]
        rest = data["no_combustion_pre_ptr"]
        scale = AA_C3_BROAD_IDLE_SCALE + AA_C3_BROAD_LOAD_SCALE * load_col
        pre_ptr = combustion_part * scale + rest
        stem_accounting = {
            "combustion_part_rms_before": _rms(combustion_part),
            "combustion_part_rms_after": _rms(combustion_part * scale),
            "non_combustion_rms_before": _rms(rest),
            "non_combustion_rms_after": _rms(rest),
            "scale_mean": float(np.mean(scale)),
            "scale_min": float(np.min(scale)),
            "scale_max": float(np.max(scale)),
        }
        route = {"target": "combustion_event", "kind": "STEM_LOCAL_GAIN", "state_dependency": "load"}
    elif spec.broad_scale:
        pre_ptr = _apply_broad_scale(base, trace)
        stem_accounting = {
            "scale_mean": float(np.mean(AA_C3_BROAD_IDLE_SCALE + AA_C3_BROAD_LOAD_SCALE * load_col)),
            "scale_min": float(np.min(AA_C3_BROAD_IDLE_SCALE + AA_C3_BROAD_LOAD_SCALE * load_col)),
            "scale_max": float(np.max(AA_C3_BROAD_IDLE_SCALE + AA_C3_BROAD_LOAD_SCALE * load_col)),
        }
        route = {"target": "entire_pre_ptr_mix", "kind": "STATE_DEPENDENT_BROAD_PRE_PTR_GAIN", "state_dependency": "load"}
    else:
        pre_ptr = base.copy()
        stem_accounting = {}
        route = {"target": "none", "kind": "none", "state_dependency": "none"}

    if spec.event_body:
        pre_ptr = _apply_event_body(pre_ptr, layers)
    if spec.carrier_suppression:
        pre_ptr = _apply_carrier_suppression(pre_ptr, layers)
    if not np.all(np.isfinite(pre_ptr)):
        raise ValueError(f"variant {spec.variant_id} generated non-finite pre-PTR PCM")

    ptr = FrozenPtrStereo(SAMPLE_RATE_HZ)
    post_ptr = ptr.process(pre_ptr)
    monitor_engine = PersistentEventDomainEngine(
        _fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS
    )
    monitor_trace = monitor_engine.monitor_diagnostic_trace(
        [post_ptr[index : index + BLOCK_SIZE] for index in range(0, post_ptr.shape[0], BLOCK_SIZE)]
    )
    raw = post_ptr * OUTPUT_SCALE
    monitor = monitor_trace.monitor_pcm * OUTPUT_SCALE
    stem_accounting["pre_ptr_rms_before"] = _rms(base)
    stem_accounting["pre_ptr_rms_after"] = _rms(pre_ptr)
    stem_accounting["per_layer_rms_before"] = {name: _rms(np.asarray(layers[name], dtype=np.float64)) for name in CAPTURED_STEM_LAYERS if name in layers}
    return {
        "variant_id": spec.variant_id,
        "scene": scene,
        "duration_s": float(duration_s),
        "raw_pcm": raw,
        "monitor_pcm": monitor,
        "pre_ptr_pcm": pre_ptr,
        "route": route,
        "stem_accounting": stem_accounting,
        "hypothesis": spec.hypothesis,
    }


def _rms(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=np.float64)
    return float(np.sqrt(np.mean(np.square(array)))) if array.size else 0.0


def _sha256_pcm(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values, dtype=np.float64).tobytes()).hexdigest()


def band_rms(values: np.ndarray, sample_rate: int, low_hz: float, high_hz: float) -> float:
    sos = butter(2, (max(low_hz, 1.0), min(high_hz, sample_rate / 2.0 - 1.0)), btype="bandpass", fs=sample_rate, output="sos")
    mono = np.mean(np.asarray(values, dtype=np.float64), axis=1) if values.ndim == 2 else np.asarray(values, dtype=np.float64)
    return _rms(sosfilt(sos, mono))


def pcm_metrics(render: dict[str, Any], sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    from ..stage_x.multi_reference_comparator import raw_dynamic_metrics, timbre_metrics

    raw = render["raw_pcm"]
    dynamic = raw_dynamic_metrics(raw, sample_rate)
    timbre = timbre_metrics(np.mean(raw, axis=1), sample_rate)
    return {
        "raw_sha256": _sha256_pcm(raw),
        "monitor_sha256": _sha256_pcm(render["monitor_pcm"]),
        "pre_ptr_sha256": _sha256_pcm(render["pre_ptr_pcm"]),
        "rms_dbfs": float(dynamic["rms_dbfs"]),
        "peak_dbfs": float(dynamic["peak_dbfs"]),
        "crest_db": float(dynamic["crest_db"]),
        "dynamic_range_db": float(dynamic["dynamic_range_db"]),
        "transient_event_density_per_s": float(dynamic["transient_event_density_per_s"]),
        "spectral_centroid_hz": float(timbre["spectral_centroid_hz"]),
        "roughness_proxy": float(timbre["roughness_proxy"]),
        "sharpness_proxy": float(timbre["sharpness_proxy"]),
        "tonality_proxy": float(timbre["tonality_proxy"]),
        "persistent_tone_ratio": float(timbre["persistent_tone_ratio"]),
        "band_rms": {
            f"{low:g}-{high:g}Hz": band_rms(raw, sample_rate, low, high) for low, high in ANALYSIS_BANDS_HZ
        },
        "stem_accounting": render["stem_accounting"],
        "route": render["route"],
    }


def envelope_db(values: np.ndarray, sample_rate: int, frame_s: float = 0.010) -> np.ndarray:
    mono = np.mean(np.asarray(values, dtype=np.float64), axis=1) if values.ndim == 2 else np.asarray(values, dtype=np.float64)
    frame = max(32, int(round(sample_rate * frame_s)))
    count = mono.size // frame
    if count == 0:
        return np.array([_rms(mono)])
    framed = mono[: count * frame].reshape(count, frame)
    rms = np.sqrt(np.mean(np.square(framed), axis=1) + 1.0e-12)
    return 20.0 * np.log10(np.maximum(rms, 1.0e-9))


def dynamic_preservation_metrics(scene_pcm: dict[str, np.ndarray], sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    """Scene-envelope dynamics on RAW PCM (no per-clip loudness normalization).

    scene_pcm maps scene name -> stereo/mono raw PCM for the variant being audited.
    Definitions are engineering proxies and are recorded in the output.
    """
    def _db(values: np.ndarray) -> float:
        return 20.0 * float(np.log10(max(_rms(values), 1.0e-9)))

    def _peak_db(values: np.ndarray) -> float:
        array = np.abs(np.asarray(values, dtype=np.float64))
        return 20.0 * float(np.log10(max(float(np.max(array)) if array.size else 0.0, 1.0e-9)))

    result: dict[str, Any] = {}
    idle = scene_pcm["hot_idle"]
    wot = scene_pcm["full_load"]
    result["idle_to_wot_rms_delta_db"] = _db(wot) - _db(idle)
    result["idle_to_wot_peak_delta_db"] = _peak_db(wot) - _peak_db(idle)

    def _attack(scene: str) -> tuple[float, float]:
        env = envelope_db(scene_pcm[scene], sample_rate)
        peak_index = int(np.argmax(env))
        peak_db = float(env[peak_index])
        floor_db = float(np.percentile(env, 10))
        onset_threshold = floor_db + 0.10 * (peak_db - floor_db)
        onset_candidates = np.nonzero(env[:peak_index] <= onset_threshold)[0]
        onset_index = int(onset_candidates[-1]) if onset_candidates.size else 0
        attack_db = peak_db - floor_db
        attack_ms = (peak_index - onset_index) * 10.0  # 10 ms envelope frames
        return attack_db, attack_ms

    result["tip_in_attack_db"], result["tip_in_attack_ms"] = _attack("tip_in")
    result["shift_attack_db"], _ = _attack("gear_shift")

    def _decay_ms(scene: str) -> float:
        env = envelope_db(scene_pcm[scene], sample_rate)
        peak_index = int(np.argmax(env))
        peak_db = float(env[peak_index])
        below = np.nonzero(env[peak_index:] <= peak_db - 6.0)[0]
        return float(below[0] * 10.0) if below.size else float((env.size - peak_index) * 10.0)

    result["shift_decay_ms"] = _decay_ms("gear_shift")

    def _decay_db_per_s(scene: str) -> float:
        env = envelope_db(scene_pcm[scene], sample_rate)
        peak_index = int(np.argmax(env))
        tail = env[peak_index:]
        if tail.size < 3:
            return 0.0
        x = np.arange(tail.size, dtype=np.float64) * 0.010
        slope = float(np.polyfit(x, tail, 1)[0])
        return slope

    result["lift_decay_db_per_s"] = _decay_db_per_s("lift")

    def _idle_return_ms() -> float:
        env = envelope_db(scene_pcm["idle_return"], sample_rate)
        final_db = float(np.median(env[-max(3, env.size // 5):]))
        peak_index = int(np.argmax(env))
        settled = np.nonzero(env[peak_index:] <= final_db + 3.0)[0]
        return float(settled[0] * 10.0) if settled.size else float((env.size - peak_index) * 10.0)

    result["idle_return_time_ms"] = _idle_return_ms()

    def _afterfire_peak_vs_body() -> float:
        env = envelope_db(scene_pcm["afterfire"], sample_rate)
        peak_db = float(np.max(env))
        body_db = float(np.percentile(env, 60))
        return peak_db - body_db

    result["afterfire_peak_vs_engine_body_db"] = _afterfire_peak_vs_body()

    env = envelope_db(scene_pcm["complete_cycle"], sample_rate)
    result["complete_cycle_envelope_range_db"] = float(np.percentile(env, 95) - np.percentile(env, 10))
    result["definitions"] = {
        "envelope_frame_s": 0.010,
        "attack": "10th-percentile floor to peak; onset at floor + 10% of range",
        "decay_ms": "time from peak to peak-6 dB",
        "idle_return": "time from peak to within 3 dB of final-quintile median",
        "afterfire_peak_vs_body": "peak frame dB minus 60th-percentile body dB",
        "loudness_normalization": "NONE (raw PCM, dynamic review domain)",
    }
    return result


def blower_carrier_metrics(
    forced_layer: np.ndarray,
    post_ptr: np.ndarray,
    rpm: np.ndarray,
    load: np.ndarray,
    boost: np.ndarray,
    sample_rate: int = SAMPLE_RATE_HZ,
    block_size: int = BLOCK_SIZE,
) -> dict[str, Any]:
    """Blower provenance: is the >1200 Hz content Hellcat blower identity or electronic carrier artifact?"""
    from numpy.fft import rfft, rfftfreq

    mono = np.mean(np.asarray(forced_layer, dtype=np.float64), axis=1) if forced_layer.ndim == 2 else np.asarray(forced_layer, dtype=np.float64)
    spectrum = np.abs(rfft(mono))
    freqs = rfftfreq(mono.size, 1.0 / sample_rate)
    high = freqs >= 1200.0
    if not np.any(high) or float(np.max(spectrum[high])) <= 0.0:
        return {"carrier_present": False}
    high_spec = spectrum[high]
    high_freqs = freqs[high]
    peak_index = int(np.argmax(high_spec))
    peak_freq = float(high_freqs[peak_index])
    local_median = float(np.median(high_spec)) + 1.0e-15
    carrier_peak_prominence_db = 20.0 * float(np.log10(max(float(high_spec[peak_index]), 1.0e-15) / local_median))

    top = np.sort(high_spec)[-5:]
    carrier_energy = float(np.sum(np.sort(high_spec)[-int(max(1, high_spec.size // 50)):]))
    sideband_band = (high_spec > 0) & (
        (np.abs(high_freqs - peak_freq - 120.0) < 100.0) | (np.abs(high_freqs - peak_freq + 120.0) < 100.0)
    )
    sideband_energy = float(np.sum(high_spec[sideband_band]))
    sideband_to_carrier = sideband_energy / max(carrier_energy, 1.0e-15)
    tonal = float(np.sum(top)) + 1.0e-15
    broadband_to_tonal = float(np.sum(high_spec)) / tonal

    n = block_size
    frames = mono.size // n
    env = np.sqrt(np.mean(np.square(mono[: frames * n].reshape(frames, n)), axis=1)) + 1.0e-12
    # State traces are per-block (one value per engine block): align lengths.
    count = min(env.size, np.asarray(rpm).size, np.asarray(load).size, np.asarray(boost).size)
    env = env[:count]
    rpm_frames = np.asarray(rpm, dtype=np.float64)[:count]
    load_frames = np.asarray(load, dtype=np.float64)[:count]
    boost_frames = np.asarray(boost, dtype=np.float64)[:count]

    def _tracking_error(reference: np.ndarray) -> float | None:
        if reference.size < 2 or np.allclose(reference, reference[0]):
            return None
        correlation = float(np.corrcoef(env, reference)[0, 1])
        if not np.isfinite(correlation):
            return None
        return float(1.0 - correlation)

    result = {
        "carrier_present": True,
        "carrier_peak_freq_hz": peak_freq,
        "carrier_peak_prominence_db": carrier_peak_prominence_db,
        "sideband_to_carrier": sideband_to_carrier,
        "broadband_to_tonal": broadband_to_tonal,
        "rpm_tracking_error": _tracking_error(rpm_frames),
        "load_tracking_error": _tracking_error(load_frames),
        "boost_tracking_error": _tracking_error(boost_frames),
        "definitions": {
            "carrier_peak_prominence_db": "peak >1200 Hz magnitude vs local median magnitude",
            "sideband_to_carrier": "energy within +/-100 Hz around peak-120 Hz offsets vs top 2% bins",
            "tracking_error": "1 - corr(envelope, state trace); null when the trace is constant or correlation is undefined",
        },
    }
    del post_ptr
    return result


def lf_body_guard_metrics(scene_pcm: dict[str, np.ndarray], sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    """LF body overshoot audit: engine body vs boom/boom-persistence (section 12)."""
    output: dict[str, Any] = {}
    for scene, pcm in scene_pcm.items():
        mono = np.mean(np.asarray(pcm, dtype=np.float64), axis=1) if pcm.ndim == 2 else np.asarray(pcm, dtype=np.float64)
        total_rms = _rms(mono)
        bands: dict[str, Any] = {}
        for low, high in LF_GUARD_BANDS_HZ:
            band = _bandpassed(mono, low, high, sample_rate)
            env = envelope_db(band, sample_rate)
            persistent_ratio = float(np.mean(env > (float(np.percentile(env, 50)))))
            bands[f"{low:g}-{high:g}Hz"] = {
                "band_rms": _rms(band),
                "band_ratio": _rms(band) / max(total_rms, 1.0e-12),
                "persistent_energy_ratio": persistent_ratio,
            }
        output[scene] = {
            "total_rms": total_rms,
            "bands": bands,
            "boom_risk": _boom_risk(bands),
        }
    output["interpretation"] = (
        "boom_risk=HIGH when 20-90 Hz persistent-energy ratio is high AND its band ratio is elevated; "
        "a fixed bass boost or steady sinusoid would appear as high persistent ratio with low attack variance."
    )
    return output


def _bandpassed(mono: np.ndarray, low: float, high: float, sample_rate: int) -> np.ndarray:
    sos = butter(2, (max(low, 1.0), min(high, sample_rate / 2.0 - 1.0)), btype="bandpass", fs=sample_rate, output="sos")
    return sosfilt(sos, mono)


def _boom_risk(bands: dict[str, Any]) -> str:
    low_persistent = float(np.mean([bands[name]["persistent_energy_ratio"] for name in ("20-60Hz", "60-90Hz")]))
    low_ratio = float(np.mean([bands[name]["band_ratio"] for name in ("20-60Hz", "60-90Hz")]))
    if low_persistent > 0.75 and low_ratio > 0.35:
        return "HIGH"
    if low_persistent > 0.6:
        return "ELEVATED"
    return "OK"


def route_is_stem_local(route: dict[str, Any]) -> bool:
    """Round-2 raw-candidate hard gate: gains must target explicit stems or transfer stages."""
    target = str(route.get("target", ""))
    kind = str(route.get("kind", ""))
    if kind == "none":
        return True
    if kind.endswith("_TRANSFER_GAIN") or target.startswith("transfer:"):
        return True
    return target in ROUND2_ALLOWED_STEM_TARGETS and kind == "STEM_LOCAL_GAIN"


def assert_no_broad_mix_gain_in_round2_raw_candidate(route: dict[str, Any], raw_pcm: np.ndarray, monitor_pcm: np.ndarray) -> dict[str, Any]:
    """Architectural + routing + numeric scan (not a parameter-name grep)."""
    stem_local = route_is_stem_local(route)
    raw_monitor_separated = not np.array_equal(np.asarray(raw_pcm), np.asarray(monitor_pcm))
    return {
        "route": route,
        "route_is_stem_local": bool(stem_local),
        "raw_monitor_separated": bool(raw_monitor_separated),
        "passed": bool(stem_local and raw_monitor_separated),
    }


def render_parent_raw(scene: str, duration_s: float = 1.0) -> np.ndarray:
    """Legacy Parent raw PCM (un-normalized) for dynamic/LF audits."""
    pcm, _raw, _monitor = render_parent_scene(SCENE_NAMES.get(scene, scene), duration_s)
    return np.asarray(pcm, dtype=np.float64)


__all__ = [
    "ANALYSIS_BANDS_HZ",
    "CAPTURED_STEM_LAYERS",
    "ENERGY_GAIN_TAXONOMY",
    "LF_GUARD_BANDS_HZ",
    "PROVENANCE_SCENES",
    "PROVENANCE_VARIANTS",
    "ROUND2_ALLOWED_STEM_TARGETS",
    "VARIANT_BY_ID",
    "assert_no_broad_mix_gain_in_round2_raw_candidate",
    "band_rms",
    "blower_carrier_metrics",
    "classification_for_candidate",
    "dynamic_preservation_metrics",
    "energy_gain_taxonomy_document",
    "envelope_db",
    "lf_body_guard_metrics",
    "pcm_metrics",
    "render_parent_raw",
    "render_provenance_variant",
    "render_scene_layers",
    "route_is_stem_local",
]
