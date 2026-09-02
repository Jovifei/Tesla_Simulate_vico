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
  P6  = combustion-difference (Y(Uc)-Y(0)) counterfactual residual scale; classified
        COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE, source_causal_eligible=False, and is
        NOT an audition winner before Jovi feedback (Stage AB-R semantic correction:
        a counterfactual total-effect residual is not a genuine source stem).
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
    # AB-R addition: a gain derived by rescaling Y(Uc)-Y(0) is a counterfactual
    # total-effect residual, NOT a genuine source stem. STEM_LOCAL_GAIN is reserved
    # for parameters whose first changed layer is an actual captured source stem.
    "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE",
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
    ProvenanceVariant(
        "P6",
        "combustion-difference (Y(Uc)-Y(0)) counterfactual residual scale - DIAGNOSTIC ONLY, "
        "NOT a genuine stem-local gain; eligibility=false (Stage AB-R reclassification)",
        combustion_local_scale=True,
    ),
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
        "route_classifications": {
            "P6": {
                "route_kind": "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE",
                "source_causal_eligible": False,
                "definition": (
                    "P6 rescales pre_ptr(full) - pre_ptr(event_energy=0) by 2+2*load. That residual "
                    "is the interventional counterfactual total effect of combustion energy on the "
                    "whole pre-PTR mix (shared processing interactions included). It is NOT a "
                    "captured source stem and no in-engine parameter implements this gain inside "
                    "the combustion stem, so STEM_LOCAL_GAIN / SOURCE_EVENT_ENERGY would be a "
                    "semantic overclaim."
                ),
            }
        },
        "notes": [
            "global_gain_changed=False (no constant master gain) does NOT imply stem-local: the AA-C1..C3 "
            "pressure scales multiply the whole pre_ptr mix with a load-dependent factor.",
            "event_body_mix and forced_carrier_reduction are stem-derived (combustion_event / forced_induction "
            "layers) and therefore map to FILTER_REBALANCE, not to BROAD_PRE_PTR_GAIN.",
            "AB-R: STEM_LOCAL_GAIN requires the gain's first changed layer to be a genuine captured source "
            "stem (probe-verified); counterfactual residuals belong to "
            "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE regardless of their nominal shape.",
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
        # AB-R semantic fix: combustion_part = Y(Uc) - Y(0) is an interventional
        # COUNTERFACTUAL TOTAL EFFECT (shared processing interactions included),
        # NOT an independent combustion stem. Scaling it is therefore classified
        # COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE with source_causal_eligible=False.
        # The only genuine source-local modulations demonstrated in this engine are
        # combustion_event.* parameters (see source_causal_eligibility probe).
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
            "source_causal_eligible": False,
            "residual_origin": "Y(Uc)-Y(0) counterfactual total effect of combustion_event.event_energy (0.6->0); NOT a captured source stem layer",
            "first_changed_layer": "pre_ptr (post-mix reconstruction in audit tool; no in-engine stem parameter carries this gain)",
        }
        route = {
            "target": "counterfactual_combustion_residual",
            "kind": "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE",
            "state_dependency": "load",
            "source_causal_eligible": False,
        }
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


# ---------------------------------------------------------------------------
# Stage AB-R: LF boom-guard v2 (fixes v1 math defect)
#
# v1 defect: persistent_energy_ratio = mean(env > percentile(env, 50)) is ~0.5
# BY CONSTRUCTION for any continuous envelope, so thresholds 0.6/0.75 were
# basically unreachable and the metric could not discriminate a sustained bass
# boom from an event-driven body.  v2 replaces it with reference-independent
# envelope-shape statistics: steady-run ratio, crest, CV, fluctuation depth and
# pulse density.  Silent bands -> NOT_MEASURABLE.
# ---------------------------------------------------------------------------

LF_PRESENCE_FLOOR_DB = -70.0
# 50 ms envelope frames: a 20-90 Hz boom tone has a period of 11-50 ms, so a 10 ms
# frame would alternate above/below its own median and defeat run/crest statistics.
LF_V2_FRAME_S = 0.050
LF_BOOM_STEADY_RUN_RATIO = 0.80
LF_BOOM_STEADY_CREST_DB = 4.0


def lf_band_v2_metrics(mono: np.ndarray, low_hz: float, high_hz: float, sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    """Reference-independent LF band statistics (v2)."""
    band = _bandpassed(np.asarray(mono, dtype=np.float64), low_hz, high_hz, sample_rate)
    band_rms_value = _rms(band)
    env_db = envelope_db(band, sample_rate, frame_s=LF_V2_FRAME_S)
    peak_db = float(np.max(env_db)) if env_db.size else -np.inf
    if peak_db < LF_PRESENCE_FLOOR_DB:
        return {
            "band_rms": band_rms_value,
            "presence": "NOT_MEASURABLE",
            "reason": f"peak envelope frame {peak_db:.1f} dB below {LF_PRESENCE_FLOOR_DB:.0f} dB floor",
        }
    env_lin = np.power(10.0, env_db / 20.0)
    mean_lin = float(np.mean(env_lin))
    cv = float(np.std(env_lin) / mean_lin) if mean_lin > 1.0e-12 else None
    crest_db = float(np.percentile(env_db, 95) - np.percentile(env_db, 50))
    median_db = float(np.median(env_db))
    # Contiguity: fraction of envelope frames within +-1.5 dB of the median.  A steady
    # tone sits on its median nearly all the time (~1.0); a burst/idle-gated signal does
    # not.  (A longest-run-above-median statistic is defeated by a near-constant
    # envelope whose tiny jitter alternates around the median.)
    contiguity_ratio = float(np.mean(np.abs(env_db - median_db) <= 1.5))
    p75 = float(np.percentile(env_db, 75))
    peaks = 0
    for index in range(1, env_db.size - 1):
        if env_db[index] >= p75 and env_db[index] >= env_db[index - 1] and env_db[index] > env_db[index + 1]:
            peaks += 1
    duration_s = env_db.size * LF_V2_FRAME_S
    pulse_density_per_s = float(peaks) / duration_s if duration_s > 0.0 else 0.0
    return {
        "band_rms": band_rms_value,
        "presence": "MEASURABLE",
        "envelope_peak_db": peak_db,
        "envelope_crest_db": float(crest_db),
        "envelope_cv_linear": cv,
        "envelope_contiguity_ratio": contiguity_ratio,
        "fluctuation_depth_db": float(np.percentile(env_db, 90) - np.percentile(env_db, 10)),
        "pulse_density_per_s": pulse_density_per_s,
        "definitions": (
            "envelope_crest_db = p95-p50 of the LF envelope (steady tone: small; hits: large); "
            "envelope_contiguity_ratio = fraction of frames within +-1.5 dB of the median (steady tone: ~1.0); "
            "fluctuation_depth_db = p90-p10; pulse_density = envelope peaks above p75 per second. "
            "v1 mean(env>median)~0.5-by-construction is superseded."
        ),
    }


def _boom_risk_v2(low_bands: dict[str, dict[str, Any]], total_rms: float) -> str:
    """v2 boom verdict from the 20-60Hz and 60-90Hz band statistics."""
    measurable = [name for name, stats in low_bands.items() if stats.get("presence") == "MEASURABLE"]
    if not measurable:
        return "NOT_MEASURABLE"
    steady_flags = [
        float(stats["envelope_crest_db"]) < LF_BOOM_STEADY_CREST_DB
        and float(stats["envelope_contiguity_ratio"]) > 0.85
        and float(stats["pulse_density_per_s"]) < 5.0
        for name, stats in low_bands.items()
        if name in measurable and stats.get("presence") == "MEASURABLE"
    ]
    ratios = [float(low_bands[name]["band_rms"]) / max(total_rms, 1.0e-12) for name in measurable]
    mean_ratio = float(np.mean(ratios)) if ratios else 0.0
    any_steady = any(steady_flags)
    all_steady = bool(steady_flags) and all(steady_flags)
    if all_steady and mean_ratio > 0.35:
        return "HIGH"
    if any_steady or mean_ratio > 0.60:
        return "ELEVATED"
    return "OK"


def lf_body_guard_metrics_v2(scene_pcm: dict[str, np.ndarray], sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    """AB-R v2 LF body guard. Validates against synthetic sine/burst/AM/noise/silence."""
    output: dict[str, Any] = {}
    for scene, pcm in scene_pcm.items():
        mono = np.mean(np.asarray(pcm, dtype=np.float64), axis=1) if np.asarray(pcm).ndim == 2 else np.asarray(pcm, dtype=np.float64)
        total_rms = _rms(mono)
        bands: dict[str, Any] = {}
        for low, high in LF_GUARD_BANDS_HZ:
            stats = lf_band_v2_metrics(mono, low, high, sample_rate)
            band_ratio = float(stats["band_rms"]) / max(total_rms, 1.0e-12)
            stats["band_ratio"] = band_ratio
            bands[f"{low:g}-{high:g}Hz"] = stats
        low_bands = {name: bands[name] for name in ("20-60Hz", "60-90Hz")}
        output[scene] = {
            "total_rms": total_rms,
            "bands": bands,
            "boom_risk": _boom_risk_v2(low_bands, total_rms),
        }
    output["interpretation"] = (
        "boom_risk=HIGH when the 20-90Hz envelope is STEADY (crest<4dB AND contiguity>0.85 AND "
        "pulse density<5/s) AND its band ratio is elevated (>0.35): a sustained resonant boom. An "
        "event-driven engine body pulses with the firing rate (high crest, low contiguity, high "
        "pulse density) and is not flagged. v1 persistent_energy_ratio (mean(env>median)~0.5 by "
        "construction) is superseded."
    )
    return output


# ---------------------------------------------------------------------------
# Stage AB-R: blower / forced-carrier audit v2
#
# v1 defect: blower_carrier_metrics only searched >=1200 Hz (biased), received a
# 'post_ptr' argument it never used then `del post_ptr`, and never separated the
# source-layer carrier from the AUDIBLE post-PTR contribution.  v2 splits
# source / audible / contribution and scans the unbiased 600-4000 Hz window with
# a 900-1500 Hz cutoff sensitivity sweep to test whether the ~1200 Hz peak is a
# filter-corner artifact.
# ---------------------------------------------------------------------------

BLOWER_SEARCH_LOW_HZ = 600.0
BLOWER_SEARCH_HIGH_HZ = 4000.0
BLOWER_SUPPRESSION_CORNER_HZ = 1200.0
BLOWER_CUTOFF_SWEEP_HZ = (900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1500.0)


def _carrier_stats(mono: np.ndarray, sample_rate: int, low_hz: float, high_hz: float) -> dict[str, Any] | None:
    from numpy.fft import rfft, rfftfreq

    if mono.size < 32:
        return None
    spectrum = np.abs(rfft(mono))
    freqs = rfftfreq(mono.size, 1.0 / sample_rate)
    band = (freqs >= low_hz) & (freqs <= min(high_hz, sample_rate / 2.0))
    if not np.any(band):
        return None
    band_spec = spectrum[band]
    if float(np.max(band_spec)) <= 0.0:
        return None
    band_freqs = freqs[band]
    peak_index = int(np.argmax(band_spec))
    local_median = float(np.median(band_spec)) + 1.0e-15
    return {
        "peak_freq_hz": float(band_freqs[peak_index]),
        "prominence_db": 20.0 * float(np.log10(max(float(band_spec[peak_index]), 1.0e-15) / local_median)),
        "tonal_share": float(np.max(band_spec)) / max(float(np.sum(band_spec)), 1.0e-15),
    }


def blower_audible_metrics(
    forced_layer: np.ndarray,
    base_pre_ptr: np.ndarray,
    post_ptr_full: np.ndarray,
    rpm: np.ndarray,
    load: np.ndarray,
    boost: np.ndarray,
    sample_rate: int = SAMPLE_RATE_HZ,
    block_size: int = BLOCK_SIZE,
    search_low_hz: float = BLOWER_SEARCH_LOW_HZ,
    search_high_hz: float = BLOWER_SEARCH_HIGH_HZ,
    suppression_corner_hz: float = BLOWER_SUPPRESSION_CORNER_HZ,
    cutoff_sweep_hz: tuple[float, ...] = BLOWER_CUTOFF_SWEEP_HZ,
) -> dict[str, Any]:
    """Blower provenance v2: source / audible / contribution split + cutoff sensitivity.

    - source:  forced_induction layer carrier content (pre-PTR), unbiased 600-4000 Hz scan.
    - audible: post-PTR interventional estimate.  base_pre_ptr is the engine's pre-PTR mix
      and forced_layer is the engine's captured forced_induction layer; because the pre-PTR
      chain (attack filter + transfer IR) is linear in the stems, PTR(base) - PTR(base -
      forced_layer) estimates the audible post-PTR forced residual.  Labeled ESTIMATE.
    - contribution: audible RMS share of the full post-PTR output, plus a band-limited share
      around the audible peak.
    - cutoff sensitivity: re-detect the peak as the low cutoff sweeps 900->1500 Hz.  A peak
      pinned at the 1200 Hz suppression corner whose prominence collapses across the sweep is
      a FILTER_CORNER_ARTIFACT_SUSPECTED, not blower identity evidence.
    """
    from numpy.fft import rfft, rfftfreq

    full = np.asarray(post_ptr_full, dtype=np.float64)
    base = np.asarray(base_pre_ptr, dtype=np.float64)
    forced = np.asarray(forced_layer, dtype=np.float64)
    mono_forced = np.mean(forced, axis=1) if forced.ndim == 2 else forced
    mono_full = np.mean(full, axis=1) if full.ndim == 2 else full

    pre_ptr_no_forced = base - forced
    ptr = FrozenPtrStereo(sample_rate)
    post_no_forced = ptr.process(pre_ptr_no_forced)
    mono_no_forced = np.mean(np.asarray(post_no_forced, dtype=np.float64), axis=1)
    audible = mono_full - mono_no_forced

    source_carrier = _carrier_stats(mono_forced, sample_rate, search_low_hz, search_high_hz)
    audible_carrier = _carrier_stats(audible, sample_rate, search_low_hz, search_high_hz)

    contribution_rms = _rms(audible) / max(_rms(mono_full), 1.0e-12)
    band_share = 0.0
    if audible_carrier is not None:
        peak = float(audible_carrier["peak_freq_hz"])
        full_spectrum = np.abs(rfft(mono_full))
        freqs = rfftfreq(mono_full.size, 1.0 / sample_rate)
        band_mask = np.abs(freqs - peak) <= 250.0
        band_share = float(np.sum(full_spectrum[band_mask])) / max(float(np.sum(full_spectrum)), 1.0e-15)

    def _spectral_broadband_ratio(mono: np.ndarray) -> float | None:
        if mono.size < 32:
            return None
        spectrum = np.abs(rfft(mono))
        tonal = float(np.sum(np.sort(spectrum)[-5:])) + 1.0e-15
        return float(np.sum(spectrum)) / tonal

    # Cutoff sensitivity sweep.
    sweep = []
    for cutoff in cutoff_sweep_hz:
        row: dict[str, Any] = {"cutoff_low_hz": float(cutoff)}
        src = _carrier_stats(mono_forced, sample_rate, cutoff, search_high_hz)
        aud = _carrier_stats(audible, sample_rate, cutoff, search_high_hz)
        row["source"] = src
        row["audible"] = aud
        sweep.append(row)
    # Search rows whose lower cutoff still admits the suppression corner itself.
    near_rows = [row for row in sweep if row["cutoff_low_hz"] <= suppression_corner_hz]
    audible_rows = [row["audible"] for row in sweep if row["audible"] is not None]
    near_peaks = [row["audible"] for row in near_rows if row["audible"] is not None]
    near_freqs = [float(row["peak_freq_hz"]) for row in near_peaks if row["peak_freq_hz"] is not None]
    near_prom = [float(row["prominence_db"]) for row in near_peaks if row["prominence_db"] is not None]
    all_prom = [float(row["prominence_db"]) for row in audible_rows if row["prominence_db"] is not None]
    pinned_in_near_rows = bool(near_freqs) and len(near_freqs) >= 2 and (max(near_freqs) - min(near_freqs)) <= 150.0 and abs(float(np.mean(near_freqs)) - suppression_corner_hz) <= 150.0
    collapse = bool(all_prom) and len(all_prom) >= 2 and (max(all_prom) - min(all_prom)) > 8.0
    stable_away = bool(near_freqs) and len(near_freqs) >= 2 and (max(near_freqs) - min(near_freqs)) <= 150.0 and abs(float(np.mean(near_freqs)) - suppression_corner_hz) > 200.0
    max_prom_db = max(all_prom) if all_prom else None

    if max_prom_db is None or max_prom_db < 10.0:
        verdict = "NO_DISTINCT_CARRIER"
    elif pinned_in_near_rows and collapse:
        # The near-corner peak is solitary: its prominence collapses by >8 dB as the
        # search window passes the corner. Classic suppression-filter corner signature.
        verdict = "FILTER_CORNER_ARTIFACT_SUSPECTED"
    elif pinned_in_near_rows:
        verdict = "AMBIGUOUS_NEAR_CORNER"
    elif stable_away:
        verdict = "GENUINE_CARRIER_CANDIDATE"
    else:
        verdict = "AMBIGUOUS"

    n = block_size
    frames = mono_full.size // n
    env = np.sqrt(np.mean(np.square(mono_full[: frames * n].reshape(frames, n)), axis=1)) + 1.0e-12

    def _tracking_error(reference: np.ndarray) -> float | None:
        count = min(env.size, np.asarray(reference).size)
        if count < 2:
            return None
        ref = np.asarray(reference, dtype=np.float64)[:count]
        env_c = env[:count]
        if np.allclose(ref, ref[0]):
            return None
        correlation = float(np.corrcoef(env_c, ref)[0, 1])
        if not np.isfinite(correlation):
            return None
        return float(1.0 - correlation)

    return {
        "method": (
            "source = forced_induction layer pre-PTR spectrum; audible = PTR(base) - PTR(base - "
            "forced_layer) linear-decomposition ESTIMATE of the post-PTR forced residual; "
            "contribution = audible RMS / full RMS"
        ),
        "source_carrier": source_carrier,
        "audible_carrier": audible_carrier,
        "audible_present": audible_carrier is not None,
        "contribution_rms_share": contribution_rms,
        "audible_peak_band_energy_share": band_share,
        "source_broadband_to_tonal": _spectral_broadband_ratio(mono_forced),
        "audible_broadband_to_tonal": _spectral_broadband_ratio(audible),
        "cutoff_sensitivity": {
            "sweep_low_hz": list(cutoff_sweep_hz),
            "per_cutoff": sweep,
            "peak_drift_hz": (max(near_freqs) - min(near_freqs)) if len(near_freqs) >= 2 else (0.0 if near_freqs else None),
            "prominence_range_db": (max(all_prom) - min(all_prom)) if len(all_prom) >= 2 else (0.0 if all_prom else None),
            "pinned_near_suppression_corner": bool(pinned_in_near_rows),
            "prominence_collapse_gt_8db": bool(collapse),
            "suppression_corner_hz": suppression_corner_hz,
        },
        "carrier_verdict": verdict,
        "rpm_tracking_error": _tracking_error(rpm),
        "load_tracking_error": _tracking_error(load),
        "boost_tracking_error": _tracking_error(boost),
        "note": (
            "v1 blower_carrier_metrics (search>=1200 Hz, unused post_ptr argument, `del post_ptr`) "
            "is superseded by this function for AB-R evidence."
        ),
    }


# ---------------------------------------------------------------------------
# Stage AB-R: dynamic attack/settling v2 (event-aligned windows)
#
# v1 defect: tip_in_attack_ms / shift_attack_db etc. measured from a whole-clip
# envelope without an isolated-event contract, so an onset at the clip edge
# reported attack=0 ms (meaningless).  v2 requires an event-aligned window with
# >=250 ms pre-event context and >=500 ms post-event context; when no isolated
# event or insufficient context exists the scene reports NOT_MEASURABLE instead
# of a fabricated number.
# ---------------------------------------------------------------------------

DYNAMIC_EVENT_PRE_GUARD_S = 0.250
DYNAMIC_EVENT_POST_GUARD_S = 0.500
DYNAMIC_EVENT_MIN_DELTA_DB = 1.0


def detect_state_event_onset(trace: Any) -> tuple[int | None, str | None]:
    """Detect the isolated event onset block index from a VehicleStateTrace."""
    throttle = np.asarray(trace.throttle, dtype=np.float64)
    rpm = np.asarray(trace.rpm, dtype=np.float64)
    rpm_drop = np.nonzero(rpm[1:] - rpm[:-1] < -500.0)[0]
    if rpm_drop.size:
        return int(rpm_drop[0]) + 1, "gear_shift_rpm_drop"
    tip_up = np.nonzero((throttle[1:] >= 0.5) & (throttle[:-1] < 0.5))[0]
    if tip_up.size:
        return int(tip_up[0]) + 1, "throttle_tip_in"
    close = np.nonzero((throttle[1:] <= 0.15) & (throttle[:-1] >= 0.6))[0]
    if close.size:
        return int(close[0]) + 1, "throttle_close"
    peak_rpm = float(np.max(rpm))
    decay = np.nonzero(rpm < 0.95 * peak_rpm)[0]
    if decay.size and int(decay[0]) > 2:
        return int(decay[0]), "rpm_decay"
    return None, None


def event_aligned_dynamic_metrics(
    pcm: np.ndarray,
    sample_rate: int = SAMPLE_RATE_HZ,
    *,
    onset_sample: int | None = None,
    pre_guard_ms: float = 250.0,
    post_guard_ms: float = 500.0,
    frame_s: float = 0.010,
) -> dict[str, Any]:
    """Per-event windowed latency/rise/settling metrics (AB-R v2)."""
    mono = np.mean(np.asarray(pcm, dtype=np.float64), axis=1) if np.asarray(pcm).ndim == 2 else np.asarray(pcm, dtype=np.float64)
    env = envelope_db(mono, sample_rate, frame_s=frame_s)
    frame_ms = frame_s * 1000.0
    if onset_sample is None:
        return {"measurable": False, "status": "NOT_MEASURABLE", "reason": "no isolated event onset declared"}
    onset_frame = max(0, int(onset_sample) // int(round(sample_rate * frame_s)))
    pre_window = env[:onset_frame]
    post_window = env[onset_frame:]
    if pre_window.size * frame_s < pre_guard_ms / 1000.0:
        return {
            "measurable": False,
            "status": "NOT_MEASURABLE",
            "reason": f"pre-event context {pre_window.size * frame_s * 1000.0:.0f} ms < {pre_guard_ms:.0f} ms",
        }
    if post_window.size * frame_s < post_guard_ms / 1000.0:
        return {
            "measurable": False,
            "status": "NOT_MEASURABLE",
            "reason": f"post-event context {post_window.size * frame_s * 1000.0:.0f} ms < {post_guard_ms:.0f} ms",
        }
    floor_window = pre_window[-int(round(0.200 / frame_s)):]
    if floor_window.size == 0:
        floor_window = pre_window
    floor_db = float(np.median(floor_window))
    peak_offset = int(np.argmax(post_window))
    peak_db = float(post_window[peak_offset])
    delta_db = peak_db - floor_db
    if delta_db < DYNAMIC_EVENT_MIN_DELTA_DB:
        return {
            "measurable": False,
            "status": "NOT_MEASURABLE",
            "reason": f"no distinct event transient (peak-floor {delta_db:.2f} dB < {DYNAMIC_EVENT_MIN_DELTA_DB:.1f} dB)",
        }

    def _first_crossing(target_db: float) -> int | None:
        hits = np.nonzero(post_window >= target_db)[0]
        return int(hits[0]) if hits.size else None

    t10 = _first_crossing(floor_db + 0.10 * delta_db)
    t50 = _first_crossing(floor_db + 0.50 * delta_db)
    t90 = _first_crossing(floor_db + 0.90 * delta_db)
    settle = np.nonzero(post_window[peak_offset:] <= floor_db + 3.0)[0]
    settled_index = int(settle[0]) if settle.size else None
    settled_within_window = settled_index is not None
    settling_ms = float(settled_index) * frame_ms if settled_index is not None else float((post_window.size - peak_offset) * frame_ms)
    acoustic_onset_ms = float(t10) * frame_ms if t10 is not None else None
    result: dict[str, Any] = {
        "measurable": True,
        "status": "MEASURABLE",
        "window": {
            "onset_frame": onset_frame,
            "pre_context_ms": float(pre_window.size * frame_ms),
            "post_context_ms": float(post_window.size * frame_ms),
            "frame_ms": frame_ms,
        },
        "event_onset_ms": float(onset_sample) / sample_rate * 1000.0,
        "acoustic_onset_ms": acoustic_onset_ms,
        "latency_ms": float(t50) * frame_ms if t50 is not None else None,
        "latency_frames": t50,
        "rise_ms": (float(t90 - t10) * frame_ms) if (t10 is not None and t90 is not None) else None,
        "onset_to_peak_ms": float(peak_offset) * frame_ms,
        "settling_ms": settling_ms,
        "settled_within_window": settled_within_window,
        "peak_overshoot_db": delta_db,
        "peak_vs_pre_db": delta_db,
        "pre_floor_db": floor_db,
        "event_peak_db": peak_db,
        "resolution_note": (
            "latency/acoustic onset are quantized to the 10 ms analysis frame; the offline renderer "
            "consumes vehicle state per 960-sample block with no transport delay, so latency_ms == 0.0 "
            "means 'acoustic 50% crossing inside the same analysis frame as the state onset' and is NOT "
            "a claim of instantaneous engine physics response"
        ),
        "definitions": (
            "event onset from state trace; acoustic_onset_ms = first frame >= floor+10% of (peak-floor); "
            "latency = onset->first frame >= floor+50%; rise = 10%->90% crossing time; "
            "onset_to_peak = onset->peak frame; settling = peak->first frame <= floor+3 dB; "
            "NOT_MEASURABLE when no isolated event, <250 ms pre or <500 ms post context, or no transient"
        ),
    }
    return result


def dynamic_preservation_metrics_v2(
    scene_pcm: dict[str, np.ndarray],
    event_onsets: dict[str, int | None] | None = None,
    sample_rate: int = SAMPLE_RATE_HZ,
    *,
    pre_guard_ms: float = 250.0,
    post_guard_ms: float = 500.0,
) -> dict[str, Any]:
    """AB-R v2 dynamic audit: v1 aggregates + event-aligned per-event windows.

    scene_pcm maps scene -> raw PCM (raw review domain, no loudness normalization).
    event_onsets maps scene -> audio sample index of the isolated event (None when the
    scene has no single isolated event, e.g. steady/cycle scenes).
    """
    base = dynamic_preservation_metrics(scene_pcm, sample_rate)
    events: dict[str, Any] = {}
    for scene in ("tip_in", "gear_shift", "lift", "idle_return", "afterfire"):
        if scene not in scene_pcm:
            continue
        events[scene] = event_aligned_dynamic_metrics(
            scene_pcm[scene], sample_rate, onset_sample=(event_onsets or {}).get(scene), pre_guard_ms=pre_guard_ms, post_guard_ms=post_guard_ms
        )
    if "afterfire_peak_vs_engine_body_db" in base:
        peak_vs_body = float(base["afterfire_peak_vs_engine_body_db"])
        base["afterfire_red_flag"] = {
            "peak_vs_engine_body_db": peak_vs_body,
            "red_flag": peak_vs_body > 15.0,
            "threshold_db": 15.0,
            "note": "event-body 120-400Hz injection lifts afterfire transient peaks far above the engine body; keep as RED FLAG for Jovi audition (firecracker check).",
        }
    base["events"] = events
    base["definitions_v2"] = {
        "event_windows": "isolated-event scenes measured in event-aligned windows: pre >= 250 ms, post >= 500 ms; otherwise NOT_MEASURABLE",
        "supersedes": "v1 tip_in_attack_ms/shift_attack_db measured from whole-clip envelope without an isolated-event contract (attack 0 ms possible)",
    }
    return base


# ---------------------------------------------------------------------------
# Stage AB-R: metric-definition registry (Stage-AA DR != complete-cycle env DR)
# ---------------------------------------------------------------------------


def metric_definition_registry_document() -> dict[str, Any]:
    """Registry of every headline metric so cross-domain comparisons are explicit.

    Key non-equivalence: Stage-AA per-clip `dynamic_range_db` (frame-percentile
    10/95 over the WHOLE clip) is NOT the same metric as Stage-AB
    `complete_cycle_envelope_range_db` (10ms envelope p10/p95 over the complete
    cycle scene).  Comparing them as 'the dynamic-range metric' was an error mode.
    """
    registry = {
        "dynamic_range_db": {
            "definition": "per-clip dynamic range from stage_x.raw_dynamic_metrics: percentile-based frame RMS spread over the WHOLE clip PCM",
            "domain": "per-clip RAW, frame-percentile (~10/95)",
            "normalization": "none (raw review domain)",
            "source_module": "stage_x.multi_reference_comparator.raw_dynamic_metrics",
            "note": "Used by Stage-AA candidate comparison; a single number per clip.",
            "not_equivalent_to": ["complete_cycle_envelope_range_db"],
        },
        "complete_cycle_envelope_range_db": {
            "definition": "p95-p10 of the 10ms envelope dB over the complete-cycle scene PCM (scene-level crest/contrast)",
            "domain": "complete_cycle scene RAW envelope",
            "normalization": "none (raw review domain)",
            "source_module": "stage_aa.provenance.dynamic_preservation_metrics",
            "note": "Scene-level envelope contrast; typically ~10 dB when per-clip DR is ~19.6 dB. Different window, different definition.",
            "not_equivalent_to": ["dynamic_range_db"],
        },
        "rms_dbfs": {"definition": "20*log10 RMS of raw PCM", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.raw_dynamic_metrics"},
        "peak_dbfs": {"definition": "20*log10 peak abs of raw PCM", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.raw_dynamic_metrics"},
        "crest_db": {"definition": "peak_dbfs - rms_dbfs", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.raw_dynamic_metrics"},
        "transient_event_density_per_s": {"definition": "per-second transient event count proxy", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.raw_dynamic_metrics"},
        "spectral_centroid_hz": {"definition": "amplitude-weighted mean frequency of the mono spectrum", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.multi_reference_comparator.timbre_metrics"},
        "sharpness_proxy": {"definition": "Aures-style sharpness proxy from timbre_metrics", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.timbre_metrics"},
        "persistent_tone_ratio": {"definition": "tonal persistence proxy from timbre_metrics", "domain": "per-clip RAW", "normalization": "none", "source_module": "stage_x.timbre_metrics"},
        "idle_to_wot_rms_delta_db": {"definition": "RMS(full_load) - RMS(hot_idle) raw PCM", "domain": "scene pair RAW", "normalization": "none", "source_module": "stage_aa.provenance"},
        "afterfire_peak_vs_engine_body_db": {
            "definition": "peak envelope frame dB minus 60th-percentile body dB in the afterfire scene",
            "domain": "afterfire scene RAW envelope",
            "normalization": "none",
            "source_module": "stage_aa.provenance",
            "note": "RED FLAG threshold >15 dB (event-body injection lifts this toward ~20 dB).",
        },
        "lf_envelope_crest_db_v2": {
            "definition": "p95-p50 of 10ms band envelope dB (v2; steady tone small, hits large)",
            "domain": "LF band envelope",
            "normalization": "none",
            "source_module": "stage_aa.provenance.lf_band_v2_metrics",
        },
        "lf_steady_run_ratio_v2": {
            "definition": "longest run of env>median / total frames (v2; NOT mean>median so not ~0.5 by construction)",
            "domain": "LF band envelope",
            "normalization": "none",
            "source_module": "stage_aa.provenance.lf_band_v2_metrics",
        },
        "blower_carrier_peak_freq_hz_v2": {
            "definition": "spectral peak within the unbiased 600-4000 Hz window",
            "domain": "source layer / audible residual spectrum",
            "normalization": "none",
            "source_module": "stage_aa.provenance.blower_audible_metrics",
        },
        "event_latency_ms_v2": {"definition": "onset -> floor+50% of (peak-floor) crossing; quantized to the 10 ms analysis frame; latency_ms==0.0 means the crossing fell inside the same analysis frame as the state onset (renderer consumes state per 960-sample block with no transport delay) and is NOT an instantaneous-engine-physics claim; missing data is reported as NOT_MEASURABLE, never as 0 ms", "domain": "event-aligned RAW envelope (pre>=250ms, post>=500ms)", "normalization": "none", "source_module": "stage_aa.provenance.event_aligned_dynamic_metrics"},
        "event_acoustic_onset_ms_v2": {"definition": "onset -> first frame >= floor+10% of (peak-floor) crossing (acoustic onset)", "domain": "event-aligned RAW envelope", "normalization": "none", "source_module": "stage_aa.provenance.event_aligned_dynamic_metrics"},
        "event_onset_to_peak_ms_v2": {"definition": "onset -> peak frame within post window", "domain": "event-aligned RAW envelope", "normalization": "none", "source_module": "stage_aa.provenance.event_aligned_dynamic_metrics"},
        "event_peak_overshoot_db_v2": {"definition": "peak minus pre-event floor, dB, within the guarded event window", "domain": "event-aligned RAW envelope", "normalization": "none", "source_module": "stage_aa.provenance.event_aligned_dynamic_metrics"},
        "event_rise_ms_v2": {"definition": "10%->90% crossing time within post window", "domain": "event-aligned RAW envelope", "normalization": "none", "source_module": "stage_aa.provenance.event_aligned_dynamic_metrics"},
        "event_settling_ms_v2": {"definition": "peak -> first frame <= floor+3 dB", "domain": "event-aligned RAW envelope", "normalization": "none", "source_module": "stage_aa.provenance.event_aligned_dynamic_metrics"},
    }
    return {
        "schema": "s12.stage_ab.metric_definition_registry.v1",
        "purpose": "Single source of truth for metric definitions so that different windows/domains are never compared as if they were the same metric.",
        "metrics": registry,
        "equivalence_warnings": {
            "dynamic_range_db_vs_complete_cycle_envelope_range_db": {
                "left": "dynamic_range_db",
                "right": "complete_cycle_envelope_range_db",
                "warning": "NOT the same metric: per-clip frame-percentile DR (Stage-AA candidate domain) vs complete-cycle envelope p95-p10 (Stage-AB scene domain). Never compare as 'the dynamic range metric'.",
            }
        },
    }


# ---------------------------------------------------------------------------
# Stage AB-R: source-causal eligibility contract + real OFF/ON source probe
# ---------------------------------------------------------------------------

SOURCE_LOCAL_PROBE_LAYERS = (
    "combustion_event",
    "per_cylinder_path",
    "forced_induction",
    "pre_transients",
    "transients",
    "dp_dc",
    "pre_ptr",
)
# Non-source stems are NOT bit-identical across an OFF/ON source probe because the
# engine shares state (phase/inertia/attack/filter memory) across stems.  A rel RMS
# change of a few percent is expected coupling; >=5% is a real change.
SOURCE_PROBE_CHANGED_REL_RMS = 0.05
SOURCE_PROBE_PRACTICALLY_UNCHANGED_REL_RMS = 0.05


def _render_layer_arrays(config: dict[str, Any], trace: Any) -> dict[str, np.ndarray]:
    engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=False, **FINAL_SETTINGS)
    _block, layers = engine.process_with_layer_trace(_state_arrays(trace))
    return {name: np.asarray(layers[name], dtype=np.float64) for name in SOURCE_LOCAL_PROBE_LAYERS if name in layers}


def probe_source_local_off_on(scene: str = "full_load", duration_s: float = 1.0) -> dict[str, Any]:
    """Real OFF/ON source-local probe: combustion_event.event_energy 0.0 (OFF) vs default (ON).

    Evidence contract (AB-R):
      - first_changed_layer is taken in CAUSAL layer order: the earliest layer whose
        rel-RMS change exceeds the coupling floor is the source stem.
      - bit-parity of non-source stems is NOT required (shared engine state couples
        them at the ~1% level); instead each layer is classified as CHANGED /
        UNCHANGED_PRACTICALLY / UNCHANGED_BIT_IDENTICAL.
      - a genuinely source-local parameter therefore shows: source layer rel change
        ~1.0, other stems <= a few percent coupling, vehicle_state unchanged.
    """
    trace = build_hellcat_bakeoff_trace(SCENE_NAMES.get(scene, scene), duration_s)
    on_arrays = _render_layer_arrays(_fitted_config(), trace)
    off_arrays = _render_layer_arrays(_zero_combustion_config(), trace)
    rows: list[dict[str, Any]] = []
    for name in SOURCE_LOCAL_PROBE_LAYERS:
        if name not in on_arrays or name not in off_arrays:
            continue
        a = on_arrays[name]
        b = off_arrays[name]
        rms_a = _rms(a)
        rel = float(np.sqrt(np.mean(np.square(a - b)))) / max(rms_a, 1.0e-12)
        identical = np.array_equal(a, b)
        if identical:
            category = "UNCHANGED_BIT_IDENTICAL"
        elif rel <= SOURCE_PROBE_PRACTICALLY_UNCHANGED_REL_RMS:
            category = "UNCHANGED_PRACTICALLY"
        else:
            category = "CHANGED"
        rows.append(
            {
                "layer": name,
                "category": category,
                "rel_rms_change": rel,
                "sha256_on": _sha256_pcm(a),
                "sha256_off": _sha256_pcm(b),
            }
        )
    first_changed = next((row["layer"] for row in rows if row["category"] == "CHANGED"), None)
    return {
        "probe": "combustion_event.event_energy OFF(0.0) vs ON(default fitted)",
        "scene": scene,
        "duration_s": float(duration_s),
        "method": "OFF/ON re-render of the full engine; per-layer rel-RMS change in causal layer order",
        "coupling_note": (
            "Non-source stems are NOT expected to be bit-identical: shared engine state (phase, "
            "inertia, filter memory) couples stems at the ~1% level. Categories: "
            "CHANGED(rel>5%) / UNCHANGED_PRACTICALLY(<=5%) / UNCHANGED_BIT_IDENTICAL."
        ),
        "first_changed_layer": first_changed,
        "per_layer": rows,
        "probe_result": (
            "SOURCE_LOCAL_MODULATION_DEMONSTRATED"
            if first_changed == "combustion_event"
            else "PROBE_UNEXPECTED"
        ),
    }


def source_causal_eligibility_document(probe: dict[str, Any] | None = None) -> dict[str, Any]:
    """AB-R source-causal eligibility contract for Round-2 raw candidates."""
    return {
        "schema": "s12.stage_ab.source_causal_eligibility.v1",
        "criterion": (
            "A Round-2 raw-candidate gain is source-causal only if it is implemented by an in-engine "
            "parameter whose first changed captured layer is a genuine source stem (combustion_event / "
            "per_cylinder_path / forced_induction / transient sources), or routed through a declared "
            "transfer stage. Post-mix broad scalings and counterfactual residuals are INELIGIBLE even "
            "when their spectral shape mimics a stem."
        ),
        "probe": probe,
        "probe_interpretation": (
            "The OFF/ON probe shows event_energy is a genuine source-local parameter: the first "
            "CHANGED layer in causal order is combustion_event (rel-RMS ~1.0); non-source stems "
            "change only through shared-engine-state coupling (<= a few percent, never bit-parity — "
            "see probe.coupling_note). This is the yardstick for source-local evidence."
        ),
        "candidates": {
            "AA-C1/AA-C2/AA-C3": {
                "implementation": "candidates.py _candidate_pre_ptr multiplies the whole layers['pre_ptr'] mix by pressure scales",
                "first_changed_layer": "pre_ptr (change applied post-engine in the candidate transform)",
                "source_causal_eligible": False,
                "classification": "STATE_DEPENDENT_BROAD_PRE_PTR_SCALING",
                "reason": "the gain's first changed layer is the full post-mix pre_ptr output, not a source stem; no in-engine source parameter carries this gain.",
            },
            "P6": {
                "implementation": "audit-only reconstruction: pre_ptr = (Y(Uc)-Y(0))*(2+2*load) + Y(0)",
                "first_changed_layer": "pre_ptr (audit reconstruction, not an engine path)",
                "source_causal_eligible": False,
                "classification": "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE",
                "reason": "the residual is the counterfactual total effect of combustion energy on the whole mix; it is not a captured source stem and no engine parameter implements it inside the stem.",
            },
            "event_energy (+3 dB source-local demonstration)": {
                "implementation": "combustion_event.event_energy source parameter",
                "first_changed_layer": "combustion_event",
                "source_causal_eligible": True,
                "classification": "SOURCE_EVENT_ENERGY",
                "reason": "OFF/ON probe evidence: first CHANGED layer in causal order is combustion_event (rel-RMS ~1.0); non-source stems see only shared-state coupling.",
            },
        },
        "status": "SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE",
        "status_detail": (
            "No source-local parameter currently carries the AA-C3 (or P6) gain: the only demonstrated "
            "source-local modulations (event_energy etc.) are NOT what AA-C3/P6 change. Round 2 must "
            "re-route gains upstream into genuine source parameters, verified by the same OFF/ON probe "
            "contract, before any STEM_LOCAL_GAIN classification is allowed."
        ),
    }



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


# ---------------------------------------------------------------------------
# Stage AB-R: synthetic validation receipts (machine-reproducible evidence)
#
# These documents encode the same synthetic-signal discriminations the test
# suite asserts (sine/burst/AM/noise/silence for LF, afterfire window for the
# dynamic red-flag), so the evidence set is self-contained rather than relying
# on a pytest run to exist.
# ---------------------------------------------------------------------------


def lf_metric_validation_document(sample_rate: int = SAMPLE_RATE_HZ) -> dict[str, Any]:
    """LF boom-guard v2 validation against synthetic sine/burst/AM/noise/silence.

    Reproduces the test fixture `lf_signals` (2 s @ SAMPLE_RATE) and runs each signal
    through `lf_body_guard_metrics_v2` on the 20-90 Hz guard bands. The discriminations
    below are the AB-R evidence that v2 envelope-shape statistics (crest / contiguity /
    pulse density / fluctuation depth) separate a sustained resonant boom from gated,
    event-driven, or stochastic low-frequency content — the thing v1's
    mean(env>median)~0.5-by-construction metric could NOT do.
    """
    sr = sample_rate
    t = np.arange(int(sr * 2.0)) / sr
    sine40 = 0.5 * np.sin(2.0 * np.pi * 40.0 * t)
    rng = np.random.default_rng(0)
    signals: dict[str, np.ndarray] = {
        "sine40": sine40,
        "burst": np.where((t % 1.0) < 0.12, sine40, 0.0),
        "am": sine40 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 4.0 * t)),
        "noise": rng.normal(0.0, 0.05, t.size),
        "silence": np.zeros(t.size),
    }

    def _guard(pcm: np.ndarray) -> dict[str, Any]:
        mono = np.asarray(pcm, dtype=np.float64)
        stereo = np.column_stack((mono, mono))
        return lf_body_guard_metrics_v2({"s": stereo}, sample_rate)["s"]

    per_signal: dict[str, Any] = {}
    for name, mono in signals.items():
        row = _guard(mono)
        band20 = row["bands"]["20-60Hz"]
        per_signal[name] = {
            "boom_risk": row["boom_risk"],
            "presence_20_60": band20["presence"],
            "envelope_crest_db": band20.get("envelope_crest_db"),
            "envelope_contiguity_ratio": band20.get("envelope_contiguity_ratio"),
            "fluctuation_depth_db": band20.get("fluctuation_depth_db"),
            "pulse_density_per_s": band20.get("pulse_density_per_s"),
            "envelope_cv_linear": band20.get("envelope_cv_linear"),
        }

    v1_ratios: dict[str, float] = {}
    for name in ("sine40", "noise"):
        mono = signals[name]
        env = envelope_db(mono, sr, frame_s=0.010)
        v1_ratios[name] = float(np.mean(env > float(np.percentile(env, 50))))

    return {
        "schema": "s12.stage_ab.lf_metric_validation.v1",
        "purpose": (
            "Synthetic-signal validation of lf_band_v2_metrics / lf_body_guard_metrics_v2 so the "
            "v2 envelope-shape statistics are proven discriminating before they are used as LF "
            "boom-guard evidence. Supersedes v1 mean(env>percentile(env,50)) ~0.5-by-construction."
        ),
        "sample_rate": sr,
        "duration_s": 2.0,
        "signal_descriptions": {
            "sine40": "continuous 40 Hz tone (sustained resonant boom analogue) -> expect boom_risk HIGH, contiguity ~1.0, crest <4 dB",
            "burst": "40 Hz tone gated 120 ms per second (event-driven body analogue) -> expect NOT HIGH (OK/ELEVATED)",
            "am": "40 Hz tone amplitude-modulated at 4 Hz (breathing boom analogue) -> expect NOT HIGH (OK/ELEVATED)",
            "noise": "white noise (stochastic low-frequency analogue) -> expect NOT HIGH, contiguity <0.85",
            "silence": "zeros -> expect NOT_MEASURABLE on both 20-60 and 60-90 Hz bands",
        },
        "per_signal": per_signal,
        "v1_ratio_reproduction": {
            "note": "Reproduces the v1 defect: mean(env>median) hugs 0.5 for continuous envelopes regardless of signal type.",
            "sine40": v1_ratios["sine40"],
            "noise": v1_ratios["noise"],
            "defect_demonstrated": all(0.35 <= v1_ratios[n] <= 0.65 for n in ("sine40", "noise")),
        },
        "assertions": {
            "sine_steady_and_high": per_signal["sine40"]["boom_risk"] == "HIGH"
            and per_signal["sine40"]["envelope_crest_db"] < 4.0
            and per_signal["sine40"]["envelope_contiguity_ratio"] > 0.85,
            "burst_not_high": per_signal["burst"]["boom_risk"] in ("OK", "ELEVATED"),
            "am_not_high": per_signal["am"]["boom_risk"] in ("OK", "ELEVATED"),
            "noise_discriminated": per_signal["noise"]["boom_risk"] in ("OK", "ELEVATED")
            and per_signal["noise"]["envelope_contiguity_ratio"] < 0.85,
            "silence_not_measurable": per_signal["silence"]["boom_risk"] == "NOT_MEASURABLE"
            and per_signal["silence"]["presence_20_60"] == "NOT_MEASURABLE",
        },
    }


def afterfire_metric_validation_document(
    dynamic: dict[str, Any],
    scene_pcm: dict[str, np.ndarray],
    event_onsets: dict[str, int | None],
    sample_rate: int = SAMPLE_RATE_HZ,
) -> dict[str, Any]:
    """Afterfire ~20 dB red-flag validation (AB-R §23).

    The afterfire peak-vs-engine-body metric is a WHOLE-CLIP aggregate (peak envelope frame
    vs 60th-percentile body dB), not an event-aligned window metric. It is retained as a RED
    FLAG (firecracker check) for the Jovi audition. This document records BOTH:
      - the whole-clip metric and its red-flag status (the retained evidence), and
      - the event-aligned window attempt, which honestly reports NOT_MEASURABLE because
        afterfire is a burst of pops without a single clean floor->peak transient — so no
        fabricated attack/latency number is emitted (§21 semantics).
    """
    afterfire_pcm = scene_pcm.get("afterfire")
    event = dynamic.get("events", {}).get("afterfire", {})
    whole_clip = {}
    if afterfire_pcm is not None:
        mono = np.mean(np.asarray(afterfire_pcm, dtype=np.float64), axis=1) if np.asarray(afterfire_pcm).ndim == 2 else np.asarray(afterfire_pcm, dtype=np.float64)
        env = envelope_db(mono, sample_rate, frame_s=0.010)
        whole_clip = {
            "peak_db": float(np.max(env)),
            "body_db": float(np.percentile(env, 60)),
            "peak_vs_engine_body_db": float(np.max(env)) - float(np.percentile(env, 60)),
            "metric_kind": "WHOLE_CLIP_AGGREGATE (peak envelope frame vs 60th-percentile body dB)",
        }
    window = {
        "measurable": bool(event.get("measurable")),
        "status": event.get("status"),
        "reason": event.get("reason"),
        "event_onset_ms": event.get("event_onset_ms"),
        "pre_context_ms": event.get("window", {}).get("pre_context_ms") if event.get("window") else None,
        "post_context_ms": event.get("window", {}).get("post_context_ms") if event.get("window") else None,
    }
    peak_vs_body = float(dynamic.get("afterfire_peak_vs_engine_body_db", float("nan")))
    red_flag = dynamic.get("afterfire_red_flag", {})
    return {
        "schema": "s12.stage_ab.afterfire_metric_validation.v1",
        "purpose": (
            "Validate the afterfire peak-vs-engine-body red flag (firecracker check) retained for "
            "the Jovi audition. The red flag is a WHOLE-CLIP aggregate (peak vs body), not an "
            "event-aligned attack metric; the event-aligned window honestly reports NOT_MEASURABLE "
            "because afterfire has no single clean transient, so no fabricated timing is emitted."
        ),
        "whole_clip_metric": whole_clip,
        "peak_vs_engine_body_db": peak_vs_body,
        "red_flag": red_flag,
        "event_aligned_window": window,
        "assertions": {
            "whole_clip_matches_dynamic": abs(float(whole_clip.get("peak_vs_engine_body_db", float("nan"))) - peak_vs_body) < 1.0e-6,
            "red_flag_raised": bool(red_flag.get("red_flag")),
            "red_flag_above_threshold": peak_vs_body > float(red_flag.get("threshold_db", 15.0)),
            "event_window_honestly_not_measurable": window.get("status") == "NOT_MEASURABLE",
        },
    }


__all__ = [
    "ANALYSIS_BANDS_HZ",
    "BLOWER_CUTOFF_SWEEP_HZ",
    "BLOWER_SEARCH_HIGH_HZ",
    "BLOWER_SEARCH_LOW_HZ",
    "BLOWER_SUPPRESSION_CORNER_HZ",
    "CAPTURED_STEM_LAYERS",
    "DYNAMIC_EVENT_POST_GUARD_S",
    "DYNAMIC_EVENT_PRE_GUARD_S",
    "ENERGY_GAIN_TAXONOMY",
    "LF_GUARD_BANDS_HZ",
    "LF_PRESENCE_FLOOR_DB",
    "PROVENANCE_SCENES",
    "PROVENANCE_VARIANTS",
    "ROUND2_ALLOWED_STEM_TARGETS",
    "SOURCE_LOCAL_PROBE_LAYERS",
    "VARIANT_BY_ID",
    "afterfire_metric_validation_document",
    "assert_no_broad_mix_gain_in_round2_raw_candidate",
    "band_rms",
    "blower_audible_metrics",
    "blower_carrier_metrics",
    "classification_for_candidate",
    "detect_state_event_onset",
    "dynamic_preservation_metrics",
    "dynamic_preservation_metrics_v2",
    "energy_gain_taxonomy_document",
    "envelope_db",
    "event_aligned_dynamic_metrics",
    "lf_band_v2_metrics",
    "lf_body_guard_metrics",
    "lf_body_guard_metrics_v2",
    "lf_metric_validation_document",
    "metric_definition_registry_document",
    "pcm_metrics",
    "probe_source_local_off_on",
    "render_parent_raw",
    "render_provenance_variant",
    "render_scene_layers",
    "route_is_stem_local",
    "source_causal_eligibility_document",
]
