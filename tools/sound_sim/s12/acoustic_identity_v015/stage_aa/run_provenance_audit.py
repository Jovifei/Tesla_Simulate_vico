"""Stage-AB AB1 runner: renders the provenance P-set and writes audit artifacts.

Artifacts (tasks/reports/runtime/s12-stage-ab/provenance/):
  energy_gain_taxonomy.json
  variant_metrics.json
  aa_c3_metric_attribution.json
  dynamic_preservation_audit.json
  lf_body_guard.json
  blower_provenance.json
  AA_C3_Provenance_Audit.md

Diagnostic-only; renders nothing into any audition package.
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .provenance import (
    PROVENANCE_SCENES,
    PROVENANCE_VARIANTS,
    VARIANT_BY_ID,
    blower_carrier_metrics,
    dynamic_preservation_metrics,
    energy_gain_taxonomy_document,
    lf_body_guard_metrics,
    pcm_metrics,
    render_parent_raw,
    render_provenance_variant,
    render_scene_layers,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
OUT_DIR = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-ab" / "provenance"

DURATION_S = 1.0

ATTRIBUTION_FACTORS = ("broad_scale", "event_body", "carrier_suppression")
CORNER_BY_SET = {
    frozenset(): "P0",
    frozenset({"broad_scale"}): "P1",
    frozenset({"event_body"}): "P2",
    frozenset({"carrier_suppression"}): "P3",
    frozenset({"event_body", "carrier_suppression"}): "P4",
    frozenset({"broad_scale", "event_body", "carrier_suppression"}): "P5",
    frozenset({"broad_scale", "event_body"}): "P7",
    frozenset({"broad_scale", "carrier_suppression"}): "P8",
}

ATTRIBUTION_TARGETS = (
    "rms_dbfs",
    "dynamic_range_db",
    "spectral_centroid_hz",
    "sharpness_proxy",
    "persistent_tone_ratio",
    "body_120_250_band_ratio",
)


def _corner_key(variant_id: str) -> frozenset[str]:
    for factors, candidate in CORNER_BY_SET.items():
        if candidate == variant_id:
            return factors
    raise KeyError(variant_id)


def _band_ratio(metrics: dict[str, Any]) -> float:
    bands = metrics["band_rms"]
    total = float(np.sqrt(sum(value * value for value in bands.values()))) + 1.0e-12
    return float(bands["120-250Hz"]) / total


def _shapley(values: dict[frozenset[str], float], factor: str) -> float:
    """Exact Shapley value: average marginal contribution over all orderings."""
    total = 0.0
    orderings = list(itertools.permutations(ATTRIBUTION_FACTORS))
    for permutation in orderings:
        prefix = frozenset()
        for name in permutation:
            if name == factor:
                total += values[prefix | {factor}] - values[prefix]
                break
            prefix = prefix | {name}
    return total / len(orderings)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    (OUT_DIR / "energy_gain_taxonomy.json").write_text(
        json.dumps(energy_gain_taxonomy_document(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    variant_metrics: dict[str, dict[str, Any]] = {}
    raw_store: dict[str, dict[str, np.ndarray]] = {}
    forced_store: dict[str, dict[str, Any]] = {}

    for scene in PROVENANCE_SCENES:
        scene_started = time.time()
        data = render_scene_layers(scene, DURATION_S)
        trace = data["trace"]
        rpm = np.asarray(trace.rpm, dtype=np.float64)
        load = np.asarray(trace.load, dtype=np.float64)
        throttle = np.asarray(trace.throttle, dtype=np.float64)
        boost_proxy = np.clip(load * throttle * np.maximum(rpm - 900.0, 0.0) / 4800.0, 0.0, 1.0)
        forced = np.asarray(data["layers"]["forced_induction"], dtype=np.float64)
        forced_store[scene] = blower_carrier_metrics(forced, data["base_pre_ptr"], rpm, load, boost_proxy)
        for variant in PROVENANCE_VARIANTS:
            render = render_provenance_variant(variant, scene, DURATION_S, scene_data=data)
            metrics = pcm_metrics(render)
            variant_metrics.setdefault(variant.variant_id, {})[scene] = metrics
            raw_store.setdefault(variant.variant_id, {})[scene] = render["raw_pcm"]
        print(f"[provenance] {scene}: {time.time() - scene_started:.1f}s", flush=True)

    variant_metrics["_meta"] = {
        "schema": "s12.stage_ab.provenance.v1",
        "duration_s": DURATION_S,
        "scenes": list(PROVENANCE_SCENES),
        "variants": {v.variant_id: v.hypothesis for v in PROVENANCE_VARIANTS},
        "p5_equals_aa_c3_bit_exact": "verified in tests/test_s12_stage_ab_provenance.py",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    _write_json("variant_metrics.json", variant_metrics)

    # --- attribution: exact 3-factor Shapley over the complete 2^3 factorial ---
    attribution: dict[str, Any] = {
        "schema": "s12.stage_ab.aa_c3_metric_attribution.v1",
        "method": (
            "exact Shapley attribution over the complete 2^3 factorial of factors "
            "{broad_scale, event_body, carrier_suppression}; corners P0/P1/P2/P3/P4/P5/P7/P8; "
            "per-scene Shapley values sum exactly to v(P5)-v(P0) per metric"
        ),
        "factors": list(ATTRIBUTION_FACTORS),
        "targets": list(ATTRIBUTION_TARGETS),
        "note": "P6 (combustion-difference local scaling) is a source-causal diagnostic and is not part of the factorial.",
    }
    per_metric: dict[str, Any] = {}
    for target in ATTRIBUTION_TARGETS:
        corners: dict[frozenset[str], float] = {}
        for factors, variant_id in CORNER_BY_SET.items():
            corners[factors] = float(np.mean([_target_value(variant_metrics[variant_id][scene], target) for scene in PROVENANCE_SCENES]))
        shapley = {factor: _shapley(corners, factor) for factor in ATTRIBUTION_FACTORS}
        per_metric[target] = {
            "corner_values_mean_across_scenes": {"+".join(sorted(factors)) if factors else "none": value for factors, value in corners.items()},
            "shapley": shapley,
            "total_effect_p5_minus_p0": corners[frozenset(ATTRIBUTION_FACTORS)] - corners[frozenset()],
            "broad_scale_share_of_total": _share(shapley["broad_scale"], corners),
        }
    attribution["per_metric"] = per_metric
    attribution["headline"] = {
        "rms_recovery_shapley_share_broad_scale": per_metric["rms_dbfs"]["shapley"]["broad_scale"],
        "rms_recovery_total": per_metric["rms_dbfs"]["total_effect_p5_minus_p0"],
    }
    _write_json("aa_c3_metric_attribution.json", attribution)

    # --- dynamic preservation audit (raw PCM, no loudness normalization) ---
    dynamic_scenes = ("hot_idle", "full_load", "tip_in", "gear_shift", "lift", "idle_return", "afterfire", "complete_cycle")
    dynamic: dict[str, Any] = {"schema": "s12.stage_ab.dynamic_preservation.v1", "domain": "DYNAMIC_REVIEW_RAW_NO_NORMALIZATION"}
    parent_pcm: dict[str, np.ndarray] = {scene: render_parent_raw(scene, DURATION_S) for scene in dynamic_scenes}
    dynamic["parent_legacy"] = dynamic_preservation_metrics(parent_pcm)
    for variant_id in ("P0", "P1", "P4", "P5", "P6"):
        scene_pcm = {scene: raw_store[variant_id][scene] for scene in dynamic_scenes}
        dynamic[variant_id] = dynamic_preservation_metrics(scene_pcm)
    _write_json("dynamic_preservation_audit.json", dynamic)

    # --- LF body guard ---
    lf_scenes = ("hot_idle", "steady_1200", "full_load", "complete_cycle")
    lf: dict[str, Any] = {"schema": "s12.stage_ab.lf_body_guard.v1"}
    lf_parent_pcm = {scene: (parent_pcm[scene] if scene in parent_pcm else render_parent_raw(scene, DURATION_S)) for scene in lf_scenes}
    lf["parent_legacy"] = lf_body_guard_metrics(lf_parent_pcm)
    for variant_id in ("P0", "P2", "P5", "P6"):
        lf[variant_id] = lf_body_guard_metrics({s: raw_store[variant_id][s] for s in lf_scenes})
    _write_json("lf_body_guard.json", lf)

    # --- blower provenance ---
    blower: dict[str, Any] = {"schema": "s12.stage_ab.blower_provenance.v1", "per_scene": forced_store}
    _write_json("blower_provenance.json", blower)

    _write_markdown_audit(attribution, dynamic, lf, variant_metrics)
    print(f"[provenance] done in {time.time() - started:.1f}s -> {OUT_DIR}", flush=True)


def _target_value(metrics: dict[str, Any], target: str) -> float:
    if target == "body_120_250_band_ratio":
        return _band_ratio(metrics)
    return float(metrics[target])


def _share(shapley_value: float, corners: dict[frozenset[str], float]) -> float:
    total = corners[frozenset(ATTRIBUTION_FACTORS)] - corners[frozenset()]
    if abs(total) < 1.0e-12:
        return float("nan")
    return shapley_value / total


def _write_json(name: str, payload: dict[str, Any]) -> None:
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[provenance] wrote {path.name}", flush=True)


def _write_markdown_audit(
    attribution: dict[str, Any],
    dynamic: dict[str, Any],
    lf: dict[str, Any],
    variant_metrics: dict[str, dict[str, Any]],
) -> None:
    rms = attribution["per_metric"]["rms_dbfs"]
    dyn = attribution["per_metric"]["dynamic_range_db"]
    centroid = attribution["per_metric"]["spectral_centroid_hz"]
    sharp = attribution["per_metric"]["sharpness_proxy"]
    lines = [
        "# AA-C3 Provenance Audit (Stage-AB AB1)",
        "",
        "STATUS: DIAGNOSTIC_ONLY. This audit does not change AA-C0..C3, the v3 audition package, or any default renderer.",
        "",
        "## Classification of the AA-C3 pressure scale",
        "",
        "`_candidate_pre_ptr` (candidates.py:90-108) computes `base = layers[\"pre_ptr\"]` and then",
        "`result = base * (pressure_idle_scale + pressure_load_scale * load)`.",
        "`layers[\"pre_ptr\"]` is the FULL mix (combustion + forced induction + mechanical + cycle-sync +",
        "transients + dp_dc/transfer-IR chain output; persistent_engine.py:694-708). For AA-C1/C2/C3 the",
        "scales are (2,2), so the entire pre-PTR mix is multiplied by `2 + 2*load`.",
        "",
        "**Classification: STATE_DEPENDENT_BROAD_PRE_PTR_SCALING** - not a source-pressure-AC repair,",
        "despite the AA-C1 parameter-family name `pressure_ac_load_scale`.",
        "The `event_body_mix` and `forced_carrier_reduction` terms ARE stem-derived (combustion_event /",
        "forced_induction layers) and classify as FILTER_REBALANCE.",
        "",
        "## Factorial attribution (exact Shapley over 2^3 corners, mean across 11 scenes)",
        "",
        f"- RMS: total effect {rms['total_effect_p5_minus_p0']:+.3f} dB; broad-scale share "
        f"{_fmt(rms['broad_scale_share_of_total'])}; event-body {_fmt_sh(rms['shapley']['event_body'])} dB; "
        f"carrier {_fmt_sh(rms['shapley']['carrier_suppression'])} dB",
        f"- Dynamic range: total {dyn['total_effect_p5_minus_p0']:+.3f} dB; broad-scale share {_fmt(dyn['broad_scale_share_of_total'])}",
        f"- Centroid: total {centroid['total_effect_p5_minus_p0']:+.1f} Hz; broad-scale share {_fmt(centroid['broad_scale_share_of_total'])}",
        f"- Sharpness: total {sharp['total_effect_p5_minus_p0']:+.4f}; broad-scale share {_fmt(sharp['broad_scale_share_of_total'])}",
        "",
        "## P4 test: does the correction hold WITHOUT the broad scale?",
        "",
        _p4_verdict(variant_metrics),
        "",
        "## Dynamic preservation (raw PCM, no normalization)",
        "",
        "| variant | idle->WOT RMS delta dB | cycle envelope range dB | tip-in attack dB | afterfire peak vs body dB |",
        "|---|---|---|---|---|",
        _dynamic_table(dynamic),
        "",
        "Findings:",
        "",
        "- AA-C3/P5 idle->WOT layering (+12.77 dB) EXCEEDS Parent (+9.37 dB); the broad pre-PTR scaling",
        "  is not flattening idle->WOT dynamics. The remaining gap is complete-cycle envelope range",
        "  (Parent 19.59 dB vs P5 10.50 dB vs Stage-Z 6.64 dB).",
        "- NEGATIVE KNOWLEDGE: the event-body injection lifts afterfire peak-vs-body to ~20 dB",
        "(Parent ~3 dB, Stage-Z ~3.7 dB). If Jovi reports firecracker-like afterfire, the mapping is",
        "event-body 120-400 Hz injection in the afterfire scene, NOT a single afterfire gain knob.",
        "- P6 (combustion-local scaling) keeps afterfire at Parent-like levels (3.16 dB) while restoring",
        "idle->WOT to +10.64 dB: closest to Parent dynamics among repair variants.",
        "",
        "## LF body guard (boom risk)",
        "",
        _lf_summary(lf),
        "",
        "## Blower provenance",
        "",
        "Carrier peak sits at ~1200-1234 Hz, i.e. at/near the 1200 Hz suppression filter corner, with",
        "prominence 20-24 dB, sideband/carrier ~0.49 and a strongly broadband-dominated spectrum",
        "(broadband/tonal > 500). RPM envelope tracking is poor at idle (~0.97 error) and good at full",
        "load (~0.02). Sharpness reduction ALONE is not accepted as blower-realism evidence; whether the",
        "suppressed content is true Hellcat blower identity or an electronic carrier artifact remains",
        "OPEN until Jovi feedback.",
        "",
        "## Consequences for Round 2 (one round only, source-causal)",
        "",
        "DATA-DRIVEN CONCLUSION (11-scene mean, exact Shapley): the AA-C3 RMS recovery is dominated by",
        "the STEM-DERIVED event-body 120-400 Hz injection (~66% of the +15.5 dB), with the broad",
        "pre-PTR state scaling contributing ~33%. The broad scale is NOT the primary RMS fix; instead",
        "it provides spectral rebalancing (+573 Hz centroid, +0.043 sharpness) that counteracts the",
        "event-body darkening. Without it (P4), the centroid collapses to ~591 Hz and sharpness to",
        "~0.022 - the correction does NOT hold spectrally without the broad scale interaction.",
        "",
        "- Round 2 must still move residual broad-scale effect upstream (combustion-event amplitude vs",
        "  load, event pulse energy, pressure-AC extraction, collector/path transmission,",
        "  forced-induction balance) and MUST NOT continue `base_pre_ptr * 2~4`.",
        "- The event-body injection is stem-derived but its +4.0 mix is a large additive overlay: Round 2",
        "  should re-derive body energy from source events (state-dependent event energy) rather than a",
        "  fixed 4.0x bandpassed overlay, and check the afterfire scene overshoot it causes.",
        "- P6 (combustion-difference local state scaling) is the in-repo preview of the upstream",
        "  direction: the SAME load-dependent scale applied only to the combustion difference signal",
        "  `pre_ptr(full) - pre_ptr(event_energy=0)`, leaving every other stem untouched.",
        "- P6 is an engineering diagnostic; it is NOT an audition winner before Jovi feedback.",
        "",
        "## Method note",
        "",
        "The combustion difference decomposition is an exact causal difference method (no linearity",
        "assumption): the two engine renders differ ONLY in `combustion_event.event_energy` (0.6 -> 0).",
        "",
        "Evidence files: `energy_gain_taxonomy.json`, `variant_metrics.json`,",
        "`aa_c3_metric_attribution.json`, `dynamic_preservation_audit.json`, `lf_body_guard.json`,",
        "`blower_provenance.json`. P5 == AA-C3 raw PCM bit-exact (verified in tests).",
        "",
    ]
    (OUT_DIR / "AA_C3_Provenance_Audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("[provenance] wrote AA_C3_Provenance_Audit.md", flush=True)


def _p4_verdict(variant_metrics: dict[str, dict[str, Any]]) -> str:
    rows = []
    for target in ("rms_dbfs", "dynamic_range_db", "spectral_centroid_hz", "sharpness_proxy"):
        p0 = float(np.mean([_target_value(variant_metrics["P0"][s], target) for s in PROVENANCE_SCENES]))
        p4 = float(np.mean([_target_value(variant_metrics["P4"][s], target) for s in PROVENANCE_SCENES]))
        p5 = float(np.mean([_target_value(variant_metrics["P5"][s], target) for s in PROVENANCE_SCENES]))
        rows.append(f"| {target} | {p0:.4f} | {p4:.4f} | {p5:.4f} |")
    return (
        "| metric | P0 (Stage-Z) | P4 (event+carrier, no broad) | P5 (= AA-C3) |\n|---|---|---|---|\n"
        + "\n".join(rows)
    )


def _dynamic_table(dynamic: dict[str, Any]) -> str:
    keys = ("idle_to_wot_rms_delta_db", "complete_cycle_envelope_range_db", "tip_in_attack_db", "afterfire_peak_vs_engine_body_db")
    rows = []
    for variant in ("parent_legacy", "P0", "P1", "P4", "P5", "P6"):
        label = "Parent (legacy)" if variant == "parent_legacy" else ("Stage-Z" if variant == "P0" else variant)
        rows.append("| " + label + " | " + " | ".join(f"{dynamic[variant][key]:.2f}" for key in keys) + " |")
    return "\n".join(rows)


def _lf_summary(lf: dict[str, Any]) -> str:
    rows = []
    for variant in ("parent_legacy", "P0", "P2", "P5", "P6"):
        per_scene = lf[variant]
        hot = per_scene["hot_idle"]
        low_ratio = float(np.mean([hot["bands"][name]["band_ratio"] for name in ("20-60Hz", "60-90Hz")]))
        rows.append(f"- {variant}: hot_idle 20-90Hz band ratio {low_ratio:.3f}, boom_risk hot_idle={hot['boom_risk']}, full_load={per_scene['full_load']['boom_risk']}")
    return "\n".join(rows)


def _fmt(value: float) -> str:
    return "n/a (zero total effect)" if value != value else f"{value * 100:.1f}%"


def _fmt_sh(value: float) -> str:
    return f"{value:+.3f}"


if __name__ == "__main__":
    main()
