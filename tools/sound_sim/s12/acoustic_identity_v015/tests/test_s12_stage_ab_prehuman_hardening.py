"""Stage AB-R tests: pre-human validation hardening (semantics, math, evidence).

Covers:
  - P6 reclassification (COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE, not STEM_LOCAL_GAIN)
  - source_causal_eligibility contract + OFF/ON event_energy probe
  - LF boom-guard v2 math (fixes v1 ~0.5-by-construction defect) on synthetic
    sine / burst / AM / noise / silence
  - blower audit v2 (source/audible/contribution, unbiased 600-4000 Hz scan,
    900-1500 Hz cutoff sensitivity; no `del post_ptr` defect)
  - dynamic event-aligned windows v2 (pre>=250 ms, post>=500 ms, NOT_MEASURABLE)
  - metric_definition_registry (Stage-AA DR != complete-cycle envelope DR)
  - provenance_v2 evidence: P5/AA-C3 PCM SHA parity with the v1 evidence
  - AB-R0 remote-truth receipts
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.provenance import (
    ENERGY_GAIN_TAXONOMY,
    assert_no_broad_mix_gain_in_round2_raw_candidate,
    blower_audible_metrics,
    detect_state_event_onset,
    dynamic_preservation_metrics_v2,
    energy_gain_taxonomy_document,
    event_aligned_dynamic_metrics,
    lf_band_v2_metrics,
    lf_body_guard_metrics_v2,
    metric_definition_registry_document,
    probe_source_local_off_on,
    render_provenance_variant,
    render_scene_layers,
    route_is_stem_local,
    source_causal_eligibility_document,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
AB_RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-ab"
HARDENING_DIR = AB_RUNTIME / "pre_human_hardening"
V1_DIR = AB_RUNTIME / "provenance"
V2_DIR = AB_RUNTIME / "provenance_v2"

SAMPLE_RATE = 48000
CUTOFF_SWEEP = (900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1500.0)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _stereo(mono: np.ndarray) -> np.ndarray:
    return np.column_stack((mono, mono))


def _assert_finite_numbers(node: object) -> None:
    if isinstance(node, dict):
        for value in node.values():
            _assert_finite_numbers(value)
    elif isinstance(node, list):
        for value in node:
            _assert_finite_numbers(value)
    elif isinstance(node, float):
        assert math.isfinite(node), "non-finite number in artifact"


# ---------------------------------------------------------------------------
# AB-R0: remote truth receipts
# ---------------------------------------------------------------------------


def test_remote_truth_receipt_and_scope_audit() -> None:
    receipt = _json(HARDENING_DIR / "remote_truth_receipt.json")
    assert receipt["schema"] == "s12.stage_ab.pre_human_hardening.remote_truth_receipt.v1"
    assert receipt["actual_origin_main"]["head_sha"] == "f7ba35b7e3dff8da3e8860532f7592bb7c4e8fff"
    assert receipt["pr_status"]["conclusion"] == "MAIN_ADVANCED_TO_STAGE_AB_WITHOUT_PR"
    assert receipt["ci_status"]["workflow_runs_for_f7ba35b"] == 0
    assert receipt["sound_engine_state"]["default_sound_changed"] is False
    assert receipt["sound_engine_state"]["frozen_paths_changed"] is False
    assert receipt["history_integrity"]["historical_receipts_rewritten"] is False
    scope = _json(HARDENING_DIR / "f7ba_scope_audit.json")
    assert scope["conclusion"] == "F7BA_ANALYSIS_ONLY_CONFIRMED"
    assert scope["summary"]["production_sound_engine_changed"] == 0
    assert scope["summary"]["default_sound_changed"] is False
    assert scope["summary"]["frozen_paths_changed"] is False
    _assert_finite_numbers(receipt)


# ---------------------------------------------------------------------------
# P6 reclassification + Round-2 gate
# ---------------------------------------------------------------------------


def test_p6_reclassified_counterfactual_residual_scale() -> None:
    data = render_scene_layers("full_load", 0.25)
    p6 = render_provenance_variant("P6", "full_load", 0.25, scene_data=data)
    route = p6["route"]
    assert route["target"] == "counterfactual_combustion_residual"
    assert route["kind"] == "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE"
    assert route["source_causal_eligible"] is False
    assert "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE" in ENERGY_GAIN_TAXONOMY
    doc = energy_gain_taxonomy_document()
    assert doc["route_classifications"]["P6"]["route_kind"] == "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE"
    assert doc["route_classifications"]["P6"]["source_causal_eligible"] is False


def test_p6_no_longer_passes_round2_gate_but_genuine_stem_local_does() -> None:
    data = render_scene_layers("full_load", 0.25)
    p6 = render_provenance_variant("P6", "full_load", 0.25, scene_data=data)
    p1 = render_provenance_variant("P1", "full_load", 0.25, scene_data=data)
    genuine = {"target": "combustion_event", "kind": "STEM_LOCAL_GAIN", "state_dependency": "load"}
    assert assert_no_broad_mix_gain_in_round2_raw_candidate(genuine, p6["raw_pcm"], p6["monitor_pcm"])["passed"]
    assert not assert_no_broad_mix_gain_in_round2_raw_candidate(p6["route"], p6["raw_pcm"], p6["monitor_pcm"])["passed"]
    assert not assert_no_broad_mix_gain_in_round2_raw_candidate(p1["route"], p1["raw_pcm"], p1["monitor_pcm"])["passed"]
    assert route_is_stem_local(genuine)
    assert not route_is_stem_local(p6["route"])
    assert not route_is_stem_local(p1["route"])


# ---------------------------------------------------------------------------
# source-causal eligibility probe
# ---------------------------------------------------------------------------


def test_source_causal_probe_first_changed_layer_at_source() -> None:
    probe = probe_source_local_off_on("full_load", 0.5)
    assert probe["first_changed_layer"] == "combustion_event"
    assert probe["probe_result"] == "SOURCE_LOCAL_MODULATION_DEMONSTRATED"
    rows = {row["layer"]: row for row in probe["per_layer"]}
    assert rows["combustion_event"]["category"] == "CHANGED"
    assert rows["combustion_event"]["rel_rms_change"] == pytest.approx(1.0, abs=1e-6)
    # shared-state coupling: forced_induction must NOT be bit-identical but <= 5% (practical).
    assert rows["forced_induction"]["category"] == "UNCHANGED_PRACTICALLY"
    assert rows["forced_induction"]["rel_rms_change"] <= 0.05


def test_source_causal_eligibility_contract_document() -> None:
    probe = probe_source_local_off_on("full_load", 0.5)
    doc = source_causal_eligibility_document(probe)
    assert doc["schema"] == "s12.stage_ab.source_causal_eligibility.v1"
    assert "first changed captured layer" in doc["criterion"]
    assert doc["status"] == "SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE"
    assert doc["candidates"]["AA-C1/AA-C2/AA-C3"]["source_causal_eligible"] is False
    assert doc["candidates"]["P6"]["classification"] == "COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE"
    assert doc["candidates"]["P6"]["source_causal_eligible"] is False
    assert doc["candidates"]["event_energy (+3 dB source-local demonstration)"]["source_causal_eligible"] is True


# ---------------------------------------------------------------------------
# LF boom-guard v2 (synthetic validation)
# ---------------------------------------------------------------------------


def _lf_band20(scene_pcm: dict[str, np.ndarray]) -> dict:
    out = lf_body_guard_metrics_v2(scene_pcm)
    return out["s"]


@pytest.fixture()
def lf_signals() -> dict[str, np.ndarray]:
    sr = SAMPLE_RATE
    t = np.arange(int(sr * 2.0)) / sr
    sine40 = 0.5 * np.sin(2.0 * np.pi * 40.0 * t)
    rng = np.random.default_rng(0)
    return {
        "sine40": sine40,
        "burst": np.where((t % 1.0) < 0.12, sine40, 0.0),
        "am": sine40 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 4.0 * t)),
        "noise": rng.normal(0.0, 0.05, t.size),
        "silence": np.zeros(t.size),
    }


def test_lf_v2_sine_is_steady_and_boom_high(lf_signals: dict[str, np.ndarray]) -> None:
    scene = _lf_band20({"s": _stereo(lf_signals["sine40"])})
    band = scene["bands"]["20-60Hz"]
    assert scene["boom_risk"] == "HIGH"
    assert band["presence"] == "MEASURABLE"
    assert band["envelope_crest_db"] < 4.0
    assert band["envelope_contiguity_ratio"] > 0.85


def test_lf_v2_burst_and_am_not_boom(lf_signals: dict[str, np.ndarray]) -> None:
    for name in ("burst", "am"):
        scene = _lf_band20({"s": _stereo(lf_signals[name])})
        assert scene["boom_risk"] in ("OK", "ELEVATED"), name
        assert scene["bands"]["20-60Hz"]["presence"] == "MEASURABLE"


def test_lf_v2_noise_not_boom(lf_signals: dict[str, np.ndarray]) -> None:
    scene = _lf_band20({"s": _stereo(lf_signals["noise"])})
    assert scene["boom_risk"] in ("OK", "ELEVATED")
    # the noise envelope is not contiguous -> the v2 metric discriminates it from a tone
    assert scene["bands"]["20-60Hz"]["envelope_contiguity_ratio"] < 0.85


def test_lf_v2_silence_not_measurable(lf_signals: dict[str, np.ndarray]) -> None:
    scene = _lf_band20({"s": _stereo(lf_signals["silence"])})
    assert scene["boom_risk"] == "NOT_MEASURABLE"
    assert scene["bands"]["20-60Hz"]["presence"] == "NOT_MEASURABLE"
    assert scene["bands"]["60-90Hz"]["presence"] == "NOT_MEASURABLE"


def test_lf_v1_ratio_was_by_construction_and_v2_discriminates(lf_signals: dict[str, np.ndarray]) -> None:
    """Regression-style demonstration of the v1 math defect and its v2 fix."""
    from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.provenance import envelope_db

    for name in ("sine40", "noise"):
        mono = lf_signals[name]
        env = envelope_db(mono, SAMPLE_RATE, frame_s=0.010)
        v1_ratio = float(np.mean(env > float(np.percentile(env, 50))))
        # The old metric hugs 0.5 by construction for continuous envelopes.
        assert 0.35 <= v1_ratio <= 0.65, (name, v1_ratio)
    sine_band = lf_band_v2_metrics(lf_signals["sine40"], 20.0, 60.0, SAMPLE_RATE)
    noise_band = lf_band_v2_metrics(lf_signals["noise"], 20.0, 60.0, SAMPLE_RATE)
    assert sine_band["envelope_contiguity_ratio"] > 0.85
    assert noise_band["envelope_contiguity_ratio"] < 0.85


# ---------------------------------------------------------------------------
# blower audit v2
# ---------------------------------------------------------------------------


def _blower_synthetic(carrier_hz: float | None, add_harmonic: bool = False, noise_scale: float = 1.0e-4) -> np.ndarray:
    sr = SAMPLE_RATE
    t = np.arange(int(sr * 2.0)) / sr
    rng = np.random.default_rng(1)
    signal = rng.normal(0.0, noise_scale, t.size)
    if carrier_hz is not None:
        signal = signal + 0.1 * np.sin(2.0 * np.pi * carrier_hz * t)
        if add_harmonic:
            signal = signal + 0.1 * np.sin(2.0 * np.pi * 2.0 * carrier_hz * t)
    return _stereo(signal)


def test_blower_v2_wideband_scan_and_corner_sensitivity() -> None:
    x = _blower_synthetic(1234.0)
    rpm = np.full(80, 3000.0)
    load = np.full(80, 0.8)
    boost = np.full(80, 0.6)
    result = blower_audible_metrics(x, x, x, rpm, load, boost)  # no `del post_ptr` NameError
    src = result["source_carrier"]
    assert src is not None
    assert abs(src["peak_freq_hz"] - 1234.0) <= 10.0
    assert result["cutoff_sensitivity"]["suppression_corner_hz"] == 1200.0
    assert len(result["cutoff_sensitivity"]["per_cutoff"]) == len(CUTOFF_SWEEP)
    assert result["carrier_verdict"] == "FILTER_CORNER_ARTIFACT_SUSPECTED"
    assert result["cutoff_sensitivity"]["pinned_near_suppression_corner"] is True
    _assert_finite_numbers({k: v for k, v in result.items() if not isinstance(v, (str, dict, list))})


def test_blower_v2_genuine_carrier_and_pure_noise() -> None:
    rpm = np.full(80, 3000.0)
    load = np.full(80, 0.8)
    boost = np.full(80, 0.6)
    genuine = blower_audible_metrics(*([_blower_synthetic(2200.0)] * 3), rpm, load, boost)
    assert genuine["carrier_verdict"] == "GENUINE_CARRIER_CANDIDATE"
    assert abs(genuine["source_carrier"]["peak_freq_hz"] - 2200.0) <= 10.0
    noise = blower_audible_metrics(*([_blower_synthetic(None)] * 3), rpm, load, boost)
    assert noise["carrier_verdict"] in ("NO_DISTINCT_CARRIER", "AMBIGUOUS")


# ---------------------------------------------------------------------------
# dynamic event-aligned windows v2
# ---------------------------------------------------------------------------


def _attack_pcm(onset_s: float) -> np.ndarray:
    sr = SAMPLE_RATE
    size = sr
    pcm = np.zeros((size, 2))
    start = int(onset_s * sr)
    tail = size - start
    ramp_up = np.linspace(1.0e-3, 0.5, min(4000, tail // 2))
    ramp_down = np.linspace(0.5, 2.0e-3, tail - ramp_up.size)
    seg = np.concatenate([ramp_up, ramp_down])
    if seg.size < tail:
        seg = np.concatenate([seg, np.zeros(tail - seg.size)])
    pcm[start:, 0] = seg[:tail]
    pcm[start:, 1] = seg[:tail]
    return pcm


def test_dynamic_v2_event_windows_measurable_and_guards() -> None:
    pcm = _attack_pcm(0.35)
    ok = event_aligned_dynamic_metrics(pcm, onset_sample=int(0.35 * SAMPLE_RATE))
    assert ok["status"] == "MEASURABLE"
    assert ok["measurable"] is True
    for key in ("latency_ms", "rise_ms", "settling_ms", "peak_vs_pre_db"):
        assert ok[key] is not None
    # spec section 21 field set: event/acoustic onsets, rise, onset-to-peak, overshoot
    for key in ("event_onset_ms", "acoustic_onset_ms", "onset_to_peak_ms", "peak_overshoot_db", "resolution_note"):
        assert key in ok, f"missing AB-R dynamic field {key}"
    # pre-context too short (50 ms < 250 ms) -> NOT_MEASURABLE
    early = event_aligned_dynamic_metrics(pcm, onset_sample=int(0.05 * SAMPLE_RATE))
    assert early["status"] == "NOT_MEASURABLE"
    # no declared onset -> NOT_MEASURABLE
    none = event_aligned_dynamic_metrics(pcm)
    assert none["status"] == "NOT_MEASURABLE"


def test_dynamic_v2_zero_latency_carries_resolution_semantics() -> None:
    # latency_ms == 0.0 is legal ONLY as a frame-quantization statement: the
    # acoustic 50% crossing fell inside the same 10 ms analysis frame as the
    # state onset. It must never mean "no data" (that is NOT_MEASURABLE) and
    # must always carry the resolution_note so it cannot be read as an
    # instantaneous-engine-physics claim.
    pcm = _attack_pcm(0.35)
    ok = event_aligned_dynamic_metrics(pcm, onset_sample=int(0.35 * SAMPLE_RATE))
    if ok["latency_ms"] == 0.0:
        assert "resolution_note" in ok and "NOT" in ok["resolution_note"]
        assert ok["latency_frames"] == 0
        assert ok["acoustic_onset_ms"] is not None
    # and the invalid cases never report a 0 ms latency:
    for bad in (
        event_aligned_dynamic_metrics(pcm),
        event_aligned_dynamic_metrics(pcm, onset_sample=int(0.05 * SAMPLE_RATE)),
    ):
        assert bad["status"] == "NOT_MEASURABLE"
        assert "latency_ms" not in bad


def test_dynamic_v2_runs_on_named_scene_map_and_adds_events() -> None:
    rng = np.random.default_rng(5)
    pcm = rng.normal(0.0, 0.05, size=(SAMPLE_RATE, 2))
    scenes = {name: pcm for name in ("hot_idle", "full_load", "tip_in", "gear_shift", "lift", "idle_return", "afterfire", "complete_cycle")}
    events = {"tip_in": 16800, "gear_shift": 26400, "lift": 19200, "idle_return": 21600, "afterfire": 19200}
    result = dynamic_preservation_metrics_v2(scenes, events)
    assert "events" in result and "definitions_v2" in result
    assert "afterfire_red_flag" in result
    for scene in events:
        assert result["events"][scene]["status"] in ("MEASURABLE", "NOT_MEASURABLE")
    _assert_finite_numbers({k: v for k, v in result.items() if k not in ("definitions", "definitions_v2", "events")})


def test_detect_state_event_onset_contract() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.candidates import SCENE_NAMES
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace

    tip = build_hellcat_bakeoff_trace(SCENE_NAMES["tip_in"], 1.0)
    block, kind = detect_state_event_onset(tip)
    assert kind == "throttle_tip_in" and block is not None and block > 0
    steady = build_hellcat_bakeoff_trace("steady_1200rpm", 1.0)
    block, kind = detect_state_event_onset(steady)
    assert block is None


# ---------------------------------------------------------------------------
# metric definition registry
# ---------------------------------------------------------------------------


def test_metric_registry_dr_not_equivalent_to_cycle_envelope() -> None:
    registry = metric_definition_registry_document()
    metrics = registry["metrics"]
    assert "dynamic_range_db" in metrics and "complete_cycle_envelope_range_db" in metrics
    assert "complete_cycle_envelope_range_db" in metrics["dynamic_range_db"]["not_equivalent_to"]
    assert "dynamic_range_db" in metrics["complete_cycle_envelope_range_db"]["not_equivalent_to"]
    assert "dynamic_range_db_vs_complete_cycle_envelope_range_db" in registry["equivalence_warnings"]
    for name in ("lf_envelope_crest_db_v2", "blower_carrier_peak_freq_hz_v2", "event_latency_ms_v2", "afterfire_peak_vs_engine_body_db"):
        assert name in metrics and metrics[name]["definition"]


# ---------------------------------------------------------------------------
# provenance_v2 evidence (generated by run_provenance_audit_v2)
# ---------------------------------------------------------------------------


def test_provenance_v2_p5_sha_parity_with_v1() -> None:
    v1 = _json(V1_DIR / "variant_metrics.json")
    v2 = _json(V2_DIR / "variant_metrics.json")
    for scene in v1["P5"]:
        assert v1["P5"][scene]["raw_sha256"] == v2["P5"][scene]["raw_sha256"], f"P5 raw SHA parity broken at {scene}"
        assert v1["P5"][scene]["pre_ptr_sha256"] == v2["P5"][scene]["pre_ptr_sha256"], f"P5 pre_ptr SHA parity broken at {scene}"
    assert v2["_meta"]["p5_pcm_sha_parity_with_v1"], "v2 meta must record parity"


def test_provenance_v2_artifacts_structure() -> None:
    expected_files = {
        "energy_gain_taxonomy.json",
        "variant_metrics.json",
        "aa_c3_metric_attribution.json",
        "source_causal_eligibility.json",
        "lf_body_guard_v2.json",
        "dynamic_preservation_audit_v2.json",
        "blower_audible_provenance.json",
        "metric_definition_registry.json",
        "AA_C3_Provenance_Audit_V2.md",
    }
    present = {path.name for path in V2_DIR.glob("*") if path.is_file()}
    assert expected_files <= present
    elig = _json(V2_DIR / "source_causal_eligibility.json")
    assert elig["status"] == "SOURCE_LOCAL_PARAMETER_NOT_AVAILABLE"
    assert elig["probe"]["first_changed_layer"] == "combustion_event"
    lf = _json(V2_DIR / "lf_body_guard_v2.json")
    assert "v1_supersession" in lf
    for variant in ("P0", "P5"):
        assert lf[variant]["hot_idle"]["boom_risk"] in ("OK", "ELEVATED", "HIGH", "NOT_MEASURABLE")
    blower = _json(V2_DIR / "blower_audible_provenance.json")
    for scene in ("hot_idle", "full_load", "complete_cycle"):
        assert blower["per_scene"][scene]["carrier_verdict"] in (
            "NO_DISTINCT_CARRIER",
            "AMBIGUOUS",
            "AMBIGUOUS_NEAR_CORNER",
            "GENUINE_CARRIER_CANDIDATE",
            "FILTER_CORNER_ARTIFACT_SUSPECTED",
        )
    dyn = _json(V2_DIR / "dynamic_preservation_audit_v2.json")
    assert dyn["P5"]["events"]["tip_in"]["status"] == "MEASURABLE"
    assert dyn["P5"]["afterfire_red_flag"]["red_flag"] is True
    registry = _json(V2_DIR / "metric_definition_registry.json")
    assert "dynamic_range_db_vs_complete_cycle_envelope_range_db" in registry["equivalence_warnings"]


def test_afterfire_red_flag_retained_in_v2_evidence() -> None:
    dyn = _json(V2_DIR / "dynamic_preservation_audit_v2.json")
    flag = dyn["P5"]["afterfire_red_flag"]
    assert flag["red_flag"] is True
    assert flag["peak_vs_engine_body_db"] > 15.0
    assert "firecracker" in flag["note"].lower()
