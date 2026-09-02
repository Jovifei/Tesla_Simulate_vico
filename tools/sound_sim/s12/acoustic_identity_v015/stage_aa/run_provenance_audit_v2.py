"""Stage AB-R runner: regenerated provenance evidence set (provenance_v2/).

Diagnostic-only. Reuses the exact Stage-AA render math (so P5/AA-C3 raw PCM SHAs
are byte-identical to the v1 evidence), while emitting the AB-R corrected
diagnostics:

  - P6 route reclassified COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE
  - source_causal_eligibility.json (OFF/ON event_energy probe)
  - LF body guard v2 (fixes v1 mean(env>median)~0.5-by-construction defect)
  - blower audit v2 (source/audible/contribution + unbiased 600-4000 Hz scan +
    900-1500 Hz cutoff sensitivity)
  - dynamic event-aligned windows v2 (pre>=250ms, post>=500ms, NOT_MEASURABLE)
  - metric_definition_registry.json

Artifacts (tasks/reports/runtime/s12-stage-ab/provenance_v2/):
  energy_gain_taxonomy_v2.json     variant_metrics.json
  aa_c3_metric_attribution_v2.json source_causal_eligibility.json
  true_source_local_probe_receipt.json
  lf_body_guard_v2.json            lf_metric_validation.json
  dynamic_preservation_audit_v2.json
  blower_provenance_v2.json        blower_cutoff_sensitivity.json
  afterfire_metric_validation.json metric_definition_registry.json
  AA_C3_Provenance_Audit_V2.md
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .provenance import (
    BLOCK_SIZE,
    PROVENANCE_SCENES,
    PROVENANCE_VARIANTS,
    VARIANT_BY_ID,
    afterfire_metric_validation_document,
    blower_audible_metrics,
    detect_state_event_onset,
    dynamic_preservation_metrics_v2,
    energy_gain_taxonomy_document,
    lf_body_guard_metrics_v2,
    lf_metric_validation_document,
    metric_definition_registry_document,
    pcm_metrics,
    probe_source_local_off_on,
    render_parent_raw,
    render_provenance_variant,
    render_scene_layers,
    source_causal_eligibility_document,
)
from .run_provenance_audit import (
    ATTRIBUTION_FACTORS,
    ATTRIBUTION_TARGETS,
    CORNER_BY_SET,
    _band_ratio,
    _shapley,
    _target_value,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
V1_DIR = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-ab" / "provenance"
OUT_DIR = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-ab" / "provenance_v2"

DURATION_S = 1.0
GEAR_SHIFT_DURATION_S = 1.6  # event window needs >=500 ms post context past the 55% shift point

BLOWER_SCENES = ("hot_idle", "steady_1200", "steady_2000", "steady_3000", "full_load", "complete_cycle")
DYNAMIC_SCENES = ("hot_idle", "full_load", "tip_in", "gear_shift", "lift", "idle_return", "afterfire", "complete_cycle")
EVENT_SCENES = ("tip_in", "gear_shift", "lift", "idle_return", "afterfire")
LF_SCENES = ("hot_idle", "steady_1200", "full_load", "complete_cycle")
DYNAMIC_VARIANTS = ("P0", "P1", "P4", "P5", "P6")
LF_VARIANTS = ("P0", "P2", "P5", "P6")


def _write_json(name: str, payload: dict[str, Any]) -> None:
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[provenance_v2] wrote {path.name}", flush=True)


def _event_onsets_for(scene: str, duration_s: float) -> int | None:
    """Audio sample index of the isolated event onset for a scene/duration."""
    if scene not in EVENT_SCENES:
        return None
    from .candidates import SCENE_NAMES
    from ..stage_w.bakeoff import build_hellcat_bakeoff_trace

    trace = build_hellcat_bakeoff_trace(SCENE_NAMES.get(scene, scene), duration_s)
    onset_block, _kind = detect_state_event_onset(trace)
    if onset_block is None:
        return None
    return int(onset_block) * BLOCK_SIZE


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # --- 1) taxonomy (now includes COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE + P6 route) ---
    _write_json("energy_gain_taxonomy_v2.json", energy_gain_taxonomy_document())

    # --- 2) full P-set grid (identical render math => P5 PCM SHAs must match v1) ---
    variant_metrics: dict[str, dict[str, Any]] = {}
    raw_store: dict[str, dict[str, np.ndarray]] = {}
    grid_data: dict[str, Any] = {}
    for scene in PROVENANCE_SCENES:
        scene_started = time.time()
        data = render_scene_layers(scene, DURATION_S)
        grid_data[scene] = data
        trace = data["trace"]
        boost_proxy = np.clip(
            np.asarray(trace.load) * np.asarray(trace.throttle) * np.maximum(np.asarray(trace.rpm) - 900.0, 0.0) / 4800.0, 0.0, 1.0
        )
        grid_data[scene]["boost_proxy"] = boost_proxy
        for variant in PROVENANCE_VARIANTS:
            render = render_provenance_variant(variant, scene, DURATION_S, scene_data=data)
            metrics = pcm_metrics(render)
            variant_metrics.setdefault(variant.variant_id, {})[scene] = metrics
            raw_store.setdefault(variant.variant_id, {})[scene] = render["raw_pcm"]
        print(f"[provenance_v2] grid {scene}: {time.time() - scene_started:.1f}s", flush=True)

    # --- 3) P5/AA-C3 PCM SHA parity with the v1 evidence ---
    v1_metrics = json.loads((V1_DIR / "variant_metrics.json").read_text(encoding="utf-8"))
    parity: dict[str, Any] = {}
    for scene in PROVENANCE_SCENES:
        row = {"v1_raw_sha256": v1_metrics["P5"][scene]["raw_sha256"], "v2_raw_sha256": variant_metrics["P5"][scene]["raw_sha256"], "match": False}
        row["match"] = row["v1_raw_sha256"] == row["v2_raw_sha256"]
        parity[scene] = row
    if not all(row["match"] for row in parity.values()):
        mismatches = [scene for scene, row in parity.items() if not row["match"]]
        raise RuntimeError(f"P5 PCM SHA parity with v1 FAILED for scenes: {mismatches}")

    variant_metrics["_meta"] = {
        "schema": "s12.stage_ab.provenance.v2",
        "duration_s": DURATION_S,
        "scenes": list(PROVENANCE_SCENES),
        "variants": {v.variant_id: v.hypothesis for v in PROVENANCE_VARIANTS},
        "p5_equals_aa_c3_bit_exact": "verified in tests/test_s12_stage_ab_provenance.py",
        "p5_pcm_sha_parity_with_v1": parity,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    _write_json("variant_metrics.json", variant_metrics)

    # --- 4) exact Shapley attribution (same corners/math as v1) ---
    attribution: dict[str, Any] = {
        "schema": "s12.stage_ab.aa_c3_metric_attribution.v2",
        "method": (
            "exact Shapley attribution over the complete 2^3 factorial of factors "
            "{broad_scale, event_body, carrier_suppression}; corners P0/P1/P2/P3/P4/P5/P7/P8; "
            "per-scene Shapley values sum exactly to v(P5)-v(P0) per metric"
        ),
        "factors": list(ATTRIBUTION_FACTORS),
        "targets": list(ATTRIBUTION_TARGETS),
        "note": (
            "P6 (combustion-difference residual scaling) is NOT part of the factorial and is now "
            "classified COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE (source_causal_eligible=False)."
        ),
    }
    per_metric: dict[str, Any] = {}
    for target in ATTRIBUTION_TARGETS:
        corners: dict[frozenset[str], float] = {}
        for factors, variant_id in CORNER_BY_SET.items():
            corners[factors] = float(np.mean([_target_value(variant_metrics[variant_id][scene], target) for scene in PROVENANCE_SCENES]))
        shapley = {factor: _shapley(corners, factor) for factor in ATTRIBUTION_FACTORS}
        total_effect = corners[frozenset(ATTRIBUTION_FACTORS)] - corners[frozenset()]
        per_metric[target] = {
            "corner_values_mean_across_scenes": {"+".join(sorted(factors)) if factors else "none": value for factors, value in corners.items()},
            "shapley": shapley,
            "total_effect_p5_minus_p0": total_effect,
            "closure_sum_of_shapley": float(sum(shapley.values())),
            "broad_scale_share_of_total": (shapley["broad_scale"] / total_effect) if abs(total_effect) > 1.0e-12 else None,
        }
    attribution["per_metric"] = per_metric
    attribution["headline"] = {
        "rms_recovery_shapley_share_broad_scale": per_metric["rms_dbfs"]["shapley"]["broad_scale"],
        "rms_recovery_total": per_metric["rms_dbfs"]["total_effect_p5_minus_p0"],
    }
    _write_json("aa_c3_metric_attribution_v2.json", attribution)

    # --- 5) source-causal eligibility (OFF/ON event_energy probe) ---
    probe = probe_source_local_off_on("full_load", DURATION_S)
    _write_json("source_causal_eligibility.json", source_causal_eligibility_document(probe))
    _write_json("true_source_local_probe_receipt.json", probe)

    # --- 6) LF body guard v2 ---
    lf: dict[str, Any] = {"schema": "s12.stage_ab.lf_body_guard.v2"}
    lf_parent_pcm = {scene: (render_parent_raw(scene, DURATION_S) if scene in ("hot_idle", "steady_1200", "full_load") else None) for scene in LF_SCENES}
    # complete_cycle parent is rendered explicitly at 1 s (render_parent_raw duration)
    lf_parent_pcm["complete_cycle"] = render_parent_raw("complete_cycle", DURATION_S)
    lf["parent_legacy"] = lf_body_guard_metrics_v2({s: pcm for s, pcm in lf_parent_pcm.items() if pcm is not None})
    for variant_id in LF_VARIANTS:
        lf[variant_id] = lf_body_guard_metrics_v2({s: raw_store[variant_id][s] for s in LF_SCENES})
    lf["v1_supersession"] = {
        "superseded": "lf_body_guard.json (provenance/) v1 persistent_energy_ratio = mean(env>percentile(env,50)) ~0.5 by construction",
        "note": "v1 boom-risk conclusions (P0/P2/P5 OK) are NOT usable evidence; v2 envelope-shape metrics supersede them.",
    }
    _write_json("lf_body_guard_v2.json", lf)
    _write_json("lf_metric_validation.json", lf_metric_validation_document())

    # --- 7) dynamic preservation v2 (event-aligned windows) ---
    dynamic: dict[str, Any] = {"schema": "s12.stage_ab.dynamic_preservation.v2", "domain": "DYNAMIC_REVIEW_RAW_NO_NORMALIZATION"}
    # gear_shift dedicated 1.6 s render so the shift event has >=250ms pre / >=500ms post.
    dynamic_pcm: dict[str, dict[str, np.ndarray]] = {}
    dynamic_onsets: dict[str, int | None] = {}
    gear_data = render_scene_layers("gear_shift", GEAR_SHIFT_DURATION_S)
    dynamic_onsets["gear_shift"] = _event_onsets_for("gear_shift", GEAR_SHIFT_DURATION_S)
    for scene in DYNAMIC_SCENES:
        if scene == "gear_shift":
            continue
        dynamic_onsets[scene] = _event_onsets_for(scene, DURATION_S)
    for variant_id in ("parent_legacy", *DYNAMIC_VARIANTS):
        scene_pcm: dict[str, np.ndarray] = {}
        for scene in DYNAMIC_SCENES:
            if scene == "gear_shift":
                if variant_id == "parent_legacy":
                    scene_pcm[scene] = render_parent_raw("gear_shift", GEAR_SHIFT_DURATION_S)
                else:
                    render = render_provenance_variant(variant_id, "gear_shift", GEAR_SHIFT_DURATION_S, scene_data=gear_data)
                    scene_pcm[scene] = render["raw_pcm"]
            else:
                scene_pcm[scene] = (
                    render_parent_raw(scene, DURATION_S) if variant_id == "parent_legacy" else raw_store[variant_id][scene]
                )
        dynamic[variant_id] = dynamic_preservation_metrics_v2(scene_pcm, dynamic_onsets)
        dynamic_pcm[variant_id] = scene_pcm
    _write_json("dynamic_preservation_audit_v2.json", dynamic)
    _write_json(
        "afterfire_metric_validation.json",
        afterfire_metric_validation_document(dynamic["P5"], dynamic_pcm["P5"], dynamic_onsets),
    )

    # --- 8) blower audit v2 (source / audible / contribution + cutoff sensitivity) ---
    blower: dict[str, Any] = {"schema": "s12.stage_ab.blower_provenance.v2", "per_scene": {}}
    for scene in BLOWER_SCENES:
        data = grid_data[scene]
        trace = data["trace"]
        forced = np.asarray(data["layers"]["forced_induction"], dtype=np.float64)
        base = data["base_pre_ptr"]
        p5_raw = np.asarray(raw_store["P5"][scene], dtype=np.float64)  # AA-C3 final chain for context
        boost_proxy = data["boost_proxy"]
        audible = blower_audible_metrics(
            forced,
            base,
            p5_raw,
            np.asarray(trace.rpm, dtype=np.float64),
            np.asarray(trace.load, dtype=np.float64),
            np.asarray(boost_proxy, dtype=np.float64),
        )
        audible["final_chain_aa_c3_note"] = "audible/full contrast computed from the engine baseline mix; AA-C3 P5 raw is used as the final-chain output context."
        blower["per_scene"][scene] = audible
    blower["v1_supersession"] = {
        "superseded": "blower_provenance.json (provenance/) v1 search>=1200 Hz only, unused post_ptr argument then `del post_ptr`, no source/audible split",
        "note": "v2 searches the unbiased 600-4000 Hz window, sweeps low cutoffs 900-1500 Hz to test the 1200 Hz filter-corner hypothesis, and splits source vs audible contribution.",
    }
    _write_json("blower_provenance_v2.json", blower)
    cutoff_sensitivity: dict[str, Any] = {
        "schema": "s12.stage_ab.blower_cutoff_sensitivity.v1",
        "purpose": (
            "Cutoff-sensitivity sweep: re-detect the forced-carrier peak as the search low-cutoff "
            "sweeps 900->1500 Hz. A peak pinned at the 1200 Hz suppression corner whose prominence "
            "collapses across the sweep is FILTER_CORNER_ARTIFACT_SUSPECTED, not blower identity."
        ),
        "suppression_corner_hz": 1200.0,
        "sweep_low_hz": list((900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1500.0)),
        "per_scene": {
            scene: blower["per_scene"][scene]["cutoff_sensitivity"] for scene in BLOWER_SCENES
        },
    }
    _write_json("blower_cutoff_sensitivity.json", cutoff_sensitivity)

    # --- 9) metric definition registry ---
    _write_json("metric_definition_registry.json", metric_definition_registry_document())

    _write_markdown_audit_v2(attribution, dynamic, lf, blower, parity, probe)
    print(f"[provenance_v2] done in {time.time() - started:.1f}s -> {OUT_DIR}", flush=True)


def _fmt(value: float | None) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{value * 100:.1f}%"


def _fmt_num(value: float | None, digits: int = 3) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{value:.{digits}f}"


def _write_markdown_audit_v2(
    attribution: dict[str, Any],
    dynamic: dict[str, Any],
    lf: dict[str, Any],
    blower: dict[str, Any],
    parity: dict[str, Any],
    probe: dict[str, Any],
) -> None:
    rms = attribution["per_metric"]["rms_dbfs"]
    lines = [
        "# AA-C3 Provenance Audit v2 (Stage-AB-R Pre-Human Validation Hardening)",
        "",
        "STATUS: DIAGNOSTIC_ONLY. No audition package, AA-C0..C3 behavior, frozen PTR/Radiation/Track-P,",
        "or the legacy default renderer is changed by this evidence set.",
        "",
        "## P5/AA-C3 PCM SHA parity with v1 evidence",
        "",
        f"P5 raw PCM byte-identical to provenance/variant_metrics.json for all {len(parity)} scenes: "
        + ("YES" if all(row['match'] for row in parity.values()) else "NO - FAILED"),
        "",
        "## P6 semantic reclassification (AB-R)",
        "",
        "P6 rescales pre_ptr(full) - pre_ptr(event_energy=0) by 2+2*load. That residual is the",
        "interventional COUNTERFACTUAL TOTAL EFFECT of combustion energy on the whole pre-PTR mix;",
        "it is NOT a captured source stem. Route kind is now COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE",
        "with source_causal_eligible=False. The old STEM_LOCAL_GAIN label was a semantic overclaim.",
        "See source_causal_eligibility.json for the OFF/ON event_energy probe evidence and the",
        "SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE verdict for the AA-C3/P6 gain paths.",
        "",
        "## Source-local OFF/ON probe (event_energy)",
        "",
        f"- first_changed_layer = {probe.get('first_changed_layer')} (causal order)",
        f"- per-layer: {[(row['layer'], row['category']) for row in probe.get('per_layer', [])]}",
        "- Coupling note: non-source stems are NOT bit-identical across OFF/ON because the engine",
        "  shares state (phase/inertia/filter memory); categories CHANGED/UNCHANGED_PRACTICALLY/",
        "  UNCHANGED_BIT_IDENTICAL are defined in the probe method.",
        "- Conclusion: the engine DOES expose genuine source-local parameters (event_energy); the probe",
        "  machinery can place first_changed_layer at the source. AA-C3/P6 do not use such a placement.",
        "",
        "## Factorial attribution (exact Shapley over 2^3 corners, mean across 11 scenes)",
        "",
        f"- RMS: total effect {rms['total_effect_p5_minus_p0']:+.3f} dB; broad-scale share {_fmt(rms['broad_scale_share_of_total'])}; "
        f"event-body {_fmt_num(rms['shapley']['event_body'])} dB; carrier {_fmt_num(rms['shapley']['carrier_suppression'])} dB",
        "",
        "## LF body guard v2 (v1 superseded)",
        "",
        "v1 `persistent_energy_ratio = mean(env > percentile(env,50))` is ~0.5 BY CONSTRUCTION for any",
        "continuous envelope, so v1 thresholds 0.6/0.75 were unreachable and v1 boom-risk conclusions",
        "are NOT usable evidence. v2 uses envelope-shape statistics (steady_run_ratio, crest, CV,",
        "fluctuation depth, pulse density) validated against synthetic sine/burst/AM/noise/silence in",
        "the test suite; silent bands report NOT_MEASURABLE.",
        "",
        *[_lf_line(lf, variant) for variant in ("parent_legacy", "P0", "P2", "P5", "P6")],
        "",
        "## Blower audit v2",
        "",
        *[_blower_line(scene, blower) for scene in ("hot_idle", "full_load", "complete_cycle")],
        "",
        "v1 searched only >=1200 Hz, never split source vs audible, and contained the `del post_ptr`",
        "defect (argument unused). v2 scans the unbiased 600-4000 Hz window and sweeps the low cutoff",
        "900->1500 Hz to test whether a ~1200 Hz singleton peak is a suppression-filter corner artifact.",
        "",
        "## Dynamic preservation v2 (event-aligned windows)",
        "",
        "v1 measured attack from a whole-clip envelope without an isolated-event contract (0 ms possible).",
        "v2 requires >=250 ms pre and >=500 ms post event context per scene; scenes without a compliant",
        "isolated event report NOT_MEASURABLE instead of a fabricated number.",
        "",
        "| variant | idle->WOT RMS dB | cycle env p95-p10 dB | afterfire peak-vs-body dB | events |",
        "|---|---|---|---|---|",
        *[_dynamic_line(variant, dynamic) for variant in ("parent_legacy", "P0", "P1", "P4", "P5", "P6")],
        "",
        "Afterfire ~20 dB peak-vs-body under AA-C3 (P5) is retained as a RED FLAG (firecracker check)",
        "for the Jovi audition. See metric_definition_registry.json: dynamic_range_db (Stage-AA per-clip",
        "frame-percentile) is NOT equivalent to complete_cycle_envelope_range_db (Stage-AB scene env).",
        "",
        "Evidence files (provenance_v2/): energy_gain_taxonomy_v2.json, variant_metrics.json,",
        "aa_c3_metric_attribution_v2.json, source_causal_eligibility.json, true_source_local_probe_receipt.json,",
        "lf_body_guard_v2.json, lf_metric_validation.json, dynamic_preservation_audit_v2.json,",
        "blower_provenance_v2.json, blower_cutoff_sensitivity.json, afterfire_metric_validation.json,",
        "metric_definition_registry.json.",
        "",
    ]
    (OUT_DIR / "AA_C3_Provenance_Audit_V2.md").write_text("\n".join(lines), encoding="utf-8")
    print("[provenance_v2] wrote AA_C3_Provenance_Audit_V2.md", flush=True)


def _lf_line(lf: dict[str, Any], variant: str) -> str:
    per_scene = lf[variant]
    hot = per_scene["hot_idle"]
    full = per_scene["full_load"]
    hot_low = {name: hot["bands"][name] for name in ("20-60Hz", "60-90Hz")}
    full_low = {name: full["bands"][name] for name in ("20-60Hz", "60-90Hz")}
    def _avg_contiguity(low: dict[str, Any]) -> float:
        values = [low[n].get("envelope_contiguity_ratio") for n in low if low[n].get("presence") == "MEASURABLE"]
        return float(np.mean(values)) if values else 0.0
    return (
        f"- {variant}: hot_idle boom_risk={hot['boom_risk']} "
        f"(contiguity {_fmt_num(_avg_contiguity(hot_low), 2)}); "
        f"full_load boom_risk={full['boom_risk']}"
    )


def _blower_line(scene: str, blower: dict[str, Any]) -> str:
    row = blower["per_scene"][scene]
    src = row.get("source_carrier")
    aud = row.get("audible_carrier")
    src_txt = f"{src['peak_freq_hz']:.0f}Hz/{src['prominence_db']:.1f}dB" if src else "none"
    aud_txt = f"{aud['peak_freq_hz']:.0f}Hz/{aud['prominence_db']:.1f}dB" if aud else "none"
    return (
        f"- {scene}: source carrier {src_txt}; audible {aud_txt}; contribution RMS share "
        f"{_fmt_num(row['contribution_rms_share'] * 100.0, 1)}%; verdict={row['carrier_verdict']}"
    )


def _dynamic_line(variant: str, dynamic: dict[str, Any]) -> str:
    row = dynamic[variant]
    events = row.get("events", {})
    event_txt = "; ".join(
        f"{scene}:{('MEAS' if info.get('measurable') else 'N/M')}" for scene, info in events.items()
    )
    return (
        f"| {variant} | {row['idle_to_wot_rms_delta_db']:.2f} | {row['complete_cycle_envelope_range_db']:.2f} | "
        f"{row.get('afterfire_peak_vs_engine_body_db', float('nan')):.2f} | {event_txt} |"
    )


if __name__ == "__main__":
    main()
