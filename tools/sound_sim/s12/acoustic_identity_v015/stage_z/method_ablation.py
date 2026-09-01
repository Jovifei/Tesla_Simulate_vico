"""Executable Stage Z method traceability and PCM ablation evidence."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
from pathlib import Path
import time
import tracemalloc
from typing import Any

import numpy as np

from ..event_domain.config_schema import load_config
from ..stage_v.io import sha256_file
from ..stage_w.bakeoff import BLOCK_SIZE, OUTPUT_SCALE, SAMPLE_RATE_HZ, build_hellcat_bakeoff_trace
from ..stage_w.click_contract import block_boundary_click_metrics
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from ..stage_x.multi_reference_comparator import raw_dynamic_metrics, timbre_metrics
from ..stage_y.package import _fitted_config

REPO_ROOT = Path(__file__).resolve().parents[5]
STAGE_W_ROOT = REPO_ROOT / "tasks/reports/runtime/s12-stage-w"
FINAL_SETTINGS = {
    "path_model": "waveguide_v1",
    "forced_induction_model": "timbre_map_v1",
    "cycle_sync_model": "fixture_v1",
    "transient_model": "state_v1",
    "audio_chain": "dp_v1",
}
SCENE_TRACE_NAMES = {"complete_cycle": "complete_cycle_60s"}
DEFAULT_ABLATION_DURATION_S = 0.75
TARGET_DELTA_FLOOR = 1.0e-4
CATALOG_RECEIPT = "tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json"


def _entry(
    source_id: str,
    method_id: str,
    method_name: str,
    adoption_status: str,
    implementation_files: list[str],
    runtime_call_path: str,
    tests: list[str],
    ablation_scenario: str | None,
    target_metric: str | None,
    *,
    source_license: str,
    code_license_status: str,
    asset_rights_status: str,
    commercial_runtime_status: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "method_id": method_id,
        "method_name": method_name,
        "source_license": source_license,
        "code_license_status": code_license_status,
        "asset_rights_status": asset_rights_status,
        "commercial_runtime_status": commercial_runtime_status,
        "adoption_status": adoption_status,
        "implementation_files": implementation_files,
        "runtime_call_path": runtime_call_path,
        "tests": tests,
        "ablation_scenario": ablation_scenario,
        "target_metric": target_metric,
        "evidence_receipt": CATALOG_RECEIPT if ablation_scenario else "docs/research/engine-audio-ecosystem/source_evidence_receipts.json",
        "copied_source_code": False,
        "copied_audio_asset": False,
        "copied_model_weight": False,
        "notes": notes,
    }


METHOD_CATALOG = (
    _entry(
        "engine-sim", "engine_sim_event_pressure", "cylinder event and chamber pressure packet", "IMPLEMENTED_CLEAN_ROOM",
        ["tools/sound_sim/s12/acoustic_identity_v015/event_domain/event_scheduler.py", "tools/sound_sim/s12/acoustic_identity_v015/event_domain/chamber_event.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> schedule_events -> render_event_packet -> _place",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py"], "complete_cycle", "roughness_proxy",
        source_license="MIT", code_license_status="PINNED_METHOD_REFERENCE_ONLY", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="OFF sets only the synthetic combustion event energy to zero; no global gain or PTR change.",
    ),
    _entry(
        "engine-sim", "engine_sim_path_waveguide", "per-cylinder exhaust path and propagation delay", "IMPLEMENTED_CLEAN_ROOM",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/waveguide.py"],
        "PersistentEventDomainEngine._process_frame -> WaveguideNetwork.process -> StatefulWaveguide.process",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py", "tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py"], "complete_cycle", "spectral_centroid_hz",
        source_license="MIT", code_license_status="PINNED_METHOD_REFERENCE_ONLY", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="OFF selects the existing delay_lpf_v1 path; ON selects the existing stateful waveguide path.",
    ),
    _entry(
        "engine-sim", "engine_sim_collector_network", "bank and collector combination", "IMPLEMENTED_CLEAN_ROOM",
        ["tools/sound_sim/s12/acoustic_identity_v015/event_domain/collector_network.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> collector assignment -> bank/central collector lines",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_package.py"], "afterfire_eligible", "spectral_centroid_hz",
        source_license="MIT", code_license_status="PINNED_METHOD_REFERENCE_ONLY", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="OFF collapses to the central-first topology; ON retains the committed two-bank-then-central topology.",
    ),
    _entry(
        "engine-sim", "engine_sim_forced_induction_state", "forced-induction state and shaft phase", "IMPLEMENTED_CLEAN_ROOM",
        ["tools/sound_sim/s12/acoustic_identity_v015/event_domain/forced_induction.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> _advance_boost -> render_timbre_map/render_forced_induction",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_timbre_map.py"], "steady_3000rpm", "sharpness_proxy",
        source_license="MIT", code_license_status="PINNED_METHOD_REFERENCE_ONLY", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="OFF uses the existing harmonic_v1 branch; ON uses the committed fitted timbre map.",
    ),
    _entry(
        "engine-sim", "engine_sim_persistent_block_state", "persistent block state across 20 ms frames", "IMPLEMENTED_CLEAN_ROOM",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine.process_with_trace -> _process_frame (single engine instance)",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py"], "throttle_tip_in", "dynamic_range_db",
        source_license="MIT", code_license_status="PINNED_METHOD_REFERENCE_ONLY", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="OFF recreates the same engine for every state frame; ON keeps one persistent instance.",
    ),
    _entry(
        "engine-sim", "engine_sim_pressure_audio_chain", "pressure-domain to audio-chain handoff", "IMPLEMENTED_CLEAN_ROOM",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> PressureAudioChain.process -> FrozenPtrStereo.process",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py"], "full_load_acceleration", "spectral_centroid_hz",
        source_license="MIT", code_license_status="PINNED_METHOD_REFERENCE_ONLY", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="OFF disables only dp_v1; the frozen PTR boundary remains identical.",
    ),
    _entry(
        "dasetwas-enginesound", "dasetwas_waveguide_lifecycle", "stateful waveguide warmup and continuity", "IMPLEMENTED_EQUIVALENT",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_w/waveguide.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py"],
        "PersistentEventDomainEngine._process_frame -> WaveguideNetwork/PressureAudioChain persistent state",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py", "tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py"], "complete_cycle", "spectral_flux",
        source_license="MIT plus separate notices", code_license_status="EQUIVALENT_CLEAN_ROOM", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="Shares the Engine-Sim path ablation; no Rust source, presets or example audio are imported.",
    ),
    _entry(
        "vehicle-noise-synthesizer", "vehicle_noise_state_crossfade", "state scheduling, latch/re-arm and equal-power crossfade", "IMPLEMENTED_EQUIVALENT",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_y/state_transients.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> StateTransientMixer.render_block/equal_power_crossfade",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_transients.py"], "throttle_tip_in", "roughness_proxy",
        source_license="MIT code; recordings separate", code_license_status="EQUIVALENT_CLEAN_ROOM", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="No Unity code, recordings or NWH assets are copied.",
    ),
    _entry(
        "ignis", "ignis_pressure_domain_equivalent", "pressure/DC/dP/filter lifecycle", "IMPLEMENTED_EQUIVALENT",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> PressureAudioChain.process",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_dp_chain.py"], "full_load_acceleration", "spectral_centroid_hz",
        source_license="NONE_FOUND", code_license_status="CONCEPT_ONLY_SOURCE_NOT_COPIED", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="Equivalent clean-room method only; Ignis has no tracked LICENSE and is not ported.",
    ),
    _entry(
        "markeasting-engine-audio", "markeasting_state_layer_equivalent", "state/layer authoring separation", "IMPLEMENTED_EQUIVALENT",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_y/package.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_y/state_transients.py"],
        "build_stage_z_package -> cumulative layer records -> PersistentEventDomainEngine",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_package.py"], "throttle_tip_in", "roughness_proxy",
        source_license="MIT", code_license_status="RESEARCH_CODE_NOT_COPIED", asset_rights_status="UNVERIFIED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="Repository MIT and individual audio rights are separate; no public WAV/recording is used.",
    ),
    _entry(
        "eone", "stage_y_fitted_timbre_map", "RPM/load/boost lookup timbre map", "IMPLEMENTED_EQUIVALENT",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_y/harmonic_map_fit.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py"],
        "PersistentEventDomainEngine._process_frame -> render_timbre_map",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py"], "steady_3000rpm", "sharpness_proxy",
        source_license="CC BY-NC-ND paper; product data proprietary", code_license_status="EQUIVALENT_CLEAN_ROOM", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="Synthetic committed fixture only; no paper dataset or private weight is used.",
    ),
    _entry(
        "qnx-ese", "monitor_playback_separation", "authoring/runtime and monitor/raw separation", "IMPLEMENTED_EQUIVALENT",
        ["tools/sound_sim/s12/acoustic_identity_v015/event_domain/audition_monitor.py", "tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py"],
        "PersistentEventDomainEngine._process_frame -> _monitor_step; raw/post_ptr remain analysis outputs",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py"], "hot_idle_20s", "rms_dbfs",
        source_license="QNX custom license", code_license_status="EQUIVALENT_CLEAN_ROOM", asset_rights_status="EXCLUDED", commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
        notes="Only the public separation concept is used; no QNX runtime or profile is imported.",
    ),
    _entry(
        "ensim4", "ensim4_teacher_reduced", "CFD teacher to reduced pressure response", "REFERENCE_TEACHER_ONLY",
        ["tools/sound_sim/s12/acoustic_identity_v015/stage_w/teacher_response.py"],
        "PersistentEventDomainEngine._process_frame -> ReducedCfdTeacherResponse.process (explicit non-candidate path)",
        ["tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py"], None, None,
        source_license="MIT", code_license_status="TEACHER_REFERENCE_ONLY", asset_rights_status="EXTERNAL_RECEIPT_ONLY", commercial_runtime_status="NOT_A_RUNTIME_CANDIDATE",
        notes="Teacher-vs-reduced evidence is diagnostic; CFD binary/audio stays external and is never a Runtime candidate.",
    ),
)


@dataclass(frozen=True)
class AblationRender:
    off_pcm: np.ndarray
    on_pcm: np.ndarray
    target_metric_name: str
    target_metric_before: float
    target_metric_after: float
    off_guard_metric: dict[str, Any]
    on_guard_metric: dict[str, Any]
    runtime_seconds: dict[str, float]
    memory_bytes: dict[str, int]
    global_gain_changed: bool
    off_diagnostics: dict[str, Any]
    on_diagnostics: dict[str, Any]


def _trace(scene: str, duration_s: float):
    return build_hellcat_bakeoff_trace(SCENE_TRACE_NAMES.get(scene, scene), duration_s)


def _state_arrays(trace: Any) -> dict[str, np.ndarray]:
    return {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}


def _metric(audio: np.ndarray, name: str) -> float:
    dynamic = raw_dynamic_metrics(audio, SAMPLE_RATE_HZ)
    if name in dynamic:
        return float(dynamic[name])
    timbre = timbre_metrics(np.mean(audio, axis=1), SAMPLE_RATE_HZ)
    return float(timbre[name])


def _guard(audio: np.ndarray) -> dict[str, Any]:
    click = block_boundary_click_metrics(audio, BLOCK_SIZE)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return {"finite": bool(np.all(np.isfinite(audio))), "peak": peak, "clipping": int(np.count_nonzero(np.abs(audio) >= 1.0)), "click": click, "passed": bool(np.all(np.isfinite(audio)) and peak < 1.0 and click["passed"])}


def _render_engine(config: dict[str, Any], settings: dict[str, Any], trace: Any, *, reset_each_frame: bool = False) -> tuple[np.ndarray, dict[str, Any], float, int]:
    started = time.perf_counter()
    tracemalloc.start()
    outputs: list[np.ndarray] = []
    diagnostics: dict[str, Any] = {}
    if reset_each_frame:
        for index in range(trace.rpm.size):
            engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **settings)
            state = {name: np.asarray([values[index]], dtype=np.float64) for name, values in _state_arrays(trace).items()}
            result = engine.process_with_trace(state)
            outputs.append(result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm)
            diagnostics = result.diagnostics
    else:
        engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **settings)
        result = engine.process_with_trace(_state_arrays(trace))
        outputs.append(result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm)
        diagnostics = result.diagnostics
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    audio = np.concatenate(outputs, axis=0) * OUTPUT_SCALE
    return audio, diagnostics, time.perf_counter() - started, int(peak)


def render_final_scene(scene: str, duration_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], float, int]:
    trace = _trace(scene, duration_s)
    config = _fitted_config()
    raw, diagnostics, elapsed, memory = _render_engine(config, FINAL_SETTINGS, trace)
    monitor_engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **FINAL_SETTINGS)
    monitor_result = monitor_engine.process_with_trace(_state_arrays(trace))
    monitor = monitor_result.monitor_pcm * OUTPUT_SCALE
    return raw, raw, monitor, diagnostics, elapsed, memory


def render_parent_scene(scene: str, duration_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from ..event_domain.audition_monitor import render_audition_monitor
    from ..sources.supercharged_hemi_source import render_hellcat
    from ..stage_w.boundary_adapter import FrozenPtrStereo

    trace = _trace(scene, duration_s)
    source = np.asarray(render_hellcat(trace).pressure, dtype=np.float64)
    target = trace.rpm.size * BLOCK_SIZE
    if source.shape[0] < target:
        source = np.pad(source, ((0, target - source.shape[0]), (0, 0)))
    source = source[:target]
    post = FrozenPtrStereo(SAMPLE_RATE_HZ).process(source) * OUTPUT_SCALE
    monitor = render_audition_monitor(post, SAMPLE_RATE_HZ).audio
    return post, post, monitor


def _variant(method_id: str) -> tuple[dict[str, Any], dict[str, Any], bool, str]:
    config = _fitted_config()
    settings = dict(FINAL_SETTINGS)
    reset_each_frame = False
    target = next(item for item in METHOD_CATALOG if item["method_id"] == method_id)["target_metric"]
    if method_id == "engine_sim_event_pressure":
        config["combustion_event"]["event_energy"]["value"] = 0.0
    elif method_id == "engine_sim_path_waveguide":
        settings["path_model"] = "delay_lpf_v1"
    elif method_id == "engine_sim_collector_network":
        config["collector_assignment"]["value"] = "central_first"
    elif method_id == "engine_sim_forced_induction_state":
        settings["forced_induction_model"] = "harmonic_v1"
        config["require_fitted_timbre_map"] = False
    elif method_id == "engine_sim_persistent_block_state":
        reset_each_frame = True
    elif method_id == "engine_sim_pressure_audio_chain":
        settings["audio_chain"] = "off"
    elif method_id in {"dasetwas_waveguide_lifecycle", "sive_waveguide_equivalent"}:
        settings["path_model"] = "delay_lpf_v1"
    elif method_id in {"vehicle_noise_state_crossfade", "markeasting_state_layer_equivalent"}:
        settings["transient_model"] = "off"
    elif method_id == "ignis_pressure_domain_equivalent":
        settings["audio_chain"] = "off"
    elif method_id == "stage_y_fitted_timbre_map":
        settings["forced_induction_model"] = "harmonic_v1"
        config["require_fitted_timbre_map"] = False
    else:
        raise ValueError(f"unsupported ablation method: {method_id}")
    return config, settings, reset_each_frame, str(target)


def render_ablation_case(method_id: str, scene: str, duration_s: float = DEFAULT_ABLATION_DURATION_S) -> AblationRender:
    if method_id == "monitor_playback_separation":
        _raw, final, monitor, diag, elapsed, memory = render_final_scene(scene, duration_s)
        off = final
        on = monitor
        target = "rms_dbfs"
        off_diag = diag
        on_diag = {**diag, "monitor_source": "PersistentEventDomainEngine.monitor_pcm"}
        off_runtime = on_runtime = elapsed
        off_memory = on_memory = memory
    else:
        config_off, settings_off, reset_off, target = _variant(method_id)
        config_on = _fitted_config()
        trace = _trace(scene, duration_s)
        off, off_diag, off_runtime, off_memory = _render_engine(config_off, settings_off, trace, reset_each_frame=reset_off)
        on, on_diag, on_runtime, on_memory = _render_engine(config_on, FINAL_SETTINGS, trace)
    return AblationRender(
        off_pcm=off,
        on_pcm=on,
        target_metric_name=target,
        target_metric_before=_metric(off, target),
        target_metric_after=_metric(on, target),
        off_guard_metric=_guard(off),
        on_guard_metric=_guard(on),
        runtime_seconds={"off": float(off_runtime), "on": float(on_runtime)},
        memory_bytes={"off": int(off_memory), "on": int(on_memory)},
        global_gain_changed=False,
        off_diagnostics=off_diag,
        on_diagnostics=on_diag,
    )


def _catalog_by_id() -> dict[str, dict[str, Any]]:
    return {item["method_id"]: dict(item) for item in METHOD_CATALOG}


def build_method_adoption_matrix() -> list[dict[str, Any]]:
    registry_path = REPO_ROOT / "docs/research/engine-audio-ecosystem/source_registry.json"
    coverage_path = REPO_ROOT / "docs/research/engine-audio-ecosystem/source_coverage_matrix.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    coverage = {item["id"]: item for item in json.loads(coverage_path.read_text(encoding="utf-8"))["entries"]}
    explicit = list(METHOD_CATALOG)
    represented = {item["source_id"] for item in explicit}
    rows = list(explicit)
    for source in registry["sources"]:
        source_id = source["id"]
        if source_id in represented:
            continue
        entry = coverage.get(source_id, {})
        coverage_status = entry.get("coverage", "REFERENCE_ONLY")
        if coverage_status == "BLOCKED_BY_LICENSE":
            adoption = "BLOCKED_CODE_LICENSE"
        elif source.get("kind") == "commercial":
            adoption = "BLOCKED_COMMERCIAL_RUNTIME"
        else:
            adoption = "REFERENCE_WORKFLOW_ONLY"
        rows.append(_entry(
            source_id,
            f"{source_id}_research_boundary",
            str(source.get("mapping", "research boundary")),
            adoption,
            list(entry.get("s12_artifacts", [])),
            "not executed in S12; research/rights boundary only",
            [], None, None,
            source_license=str(source.get("license", "unknown")),
            code_license_status="NOT_EXECUTED",
            asset_rights_status="EXCLUDED_OR_UNVERIFIED",
            commercial_runtime_status="NOT_A_RUNTIME_DEPENDENCY",
            notes="No source, media, preset, binary or weight is copied; matrix row records the explicit boundary.",
        ))
    return sorted(rows, key=lambda item: (item["source_id"], item["method_id"]))


def build_teacher_vs_reduced_response() -> dict[str, Any]:
    teacher = json.loads((STAGE_W_ROOT / "ensim4_teacher_response_receipt.json").read_text(encoding="utf-8"))
    reduction = json.loads((STAGE_W_ROOT / "teacher_reduction_v1/teacher_reduction_receipt.json").read_text(encoding="utf-8"))
    trace = _trace("full_load_acceleration", 0.75)
    config = load_config("hellcat_v1")
    reduced, diagnostics, elapsed, memory = _render_engine(config, {"path_model": "reduced_cfd_teacher_v1", "forced_induction_model": "harmonic_v1"}, trace)
    reduced_dynamic = raw_dynamic_metrics(reduced, SAMPLE_RATE_HZ)
    reduced_timbre = timbre_metrics(np.mean(reduced, axis=1), SAMPLE_RATE_HZ)
    cfd_on = teacher["cfd_on"]
    cfd_off = teacher["cfd_off"]
    finite = all(np.isfinite(float(value)) for value in (cfd_on["rms"], cfd_off["rms"], cfd_on["spectral_centroid_hz"], cfd_off["spectral_centroid_hz"], reduced_dynamic["rms_dbfs"], reduced_timbre["spectral_centroid_hz"]))
    return {
        "schema": "s12.stage_z.teacher_vs_reduced_response.v1",
        "status": "REFERENCE_TEACHER_ONLY",
        "teacher_source_receipt": "tasks/reports/runtime/s12-stage-w/ensim4_teacher_response_receipt.json",
        "reduction_receipt": "tasks/reports/runtime/s12-stage-w/teacher_reduction_v1/teacher_reduction_receipt.json",
        "teacher_vs_reduced": {
            "pressure_response": {"teacher_cfd_on_rms": cfd_on["rms"], "teacher_cfd_off_rms": cfd_off["rms"], "reduced_raw_rms_dbfs": reduced_dynamic["rms_dbfs"], "finite": finite},
            "arrival_timing": {"teacher_cfd_on_centroid_hz": cfd_on["spectral_centroid_hz"], "teacher_cfd_off_centroid_hz": cfd_off["spectral_centroid_hz"], "reduced_centroid_hz": reduced_timbre["spectral_centroid_hz"], "finite": finite, "note": "centroid proxy; no synchronized teacher waveform is promoted"},
            "decay": {"reduction_smoothing_ratio": reduction["models"]["reduced_cfd_teacher_v1"]["metrics"]["diagnostics"]["teacher_response"]["smoothing_from_cfd_on_off_centroid_ratio"], "finite": finite},
            "spectral_envelope": {"teacher_on_centroid_hz": cfd_on["spectral_centroid_hz"], "reduced_centroid_hz": reduced_timbre["spectral_centroid_hz"], "reduced_sharpness_proxy": reduced_timbre["sharpness_proxy"], "finite": finite},
        },
        "runtime_approximation": {"model": "ReducedCfdTeacherResponse", "runtime_candidate": False, "retained_capability": "causal two-channel smoothing derived from teacher metrics", "render_seconds": elapsed, "peak_python_allocation_bytes": memory, "cpu_cost_status": "local reduced-model measurement only"},
        "external_audio_embedded": False,
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }


def score_ablation(method_id: str, scene: str, duration_s: float = DEFAULT_ABLATION_DURATION_S) -> tuple[dict[str, Any], AblationRender]:
    spec = _catalog_by_id()[method_id]
    result = render_ablation_case(method_id, scene, duration_s)
    off_sha = hashlib.sha256(np.ascontiguousarray(result.off_pcm).tobytes()).hexdigest()
    on_sha = hashlib.sha256(np.ascontiguousarray(result.on_pcm).tobytes()).hexdigest()
    delta = result.target_metric_after - result.target_metric_before
    regression = not (result.off_guard_metric["passed"] and result.on_guard_metric["passed"])
    status = "PROVEN_CONTRIBUTION" if off_sha != on_sha and abs(delta) > TARGET_DELTA_FLOOR and not regression else "REGRESSION" if regression else "NO_MEASURABLE_CONTRIBUTION"
    return {
        "method_id": method_id,
        "scene": scene,
        "off_pcm_sha": off_sha,
        "on_pcm_sha": on_sha,
        "target_metric": result.target_metric_name,
        "target_metric_before": result.target_metric_before,
        "target_metric_after": result.target_metric_after,
        "delta": delta,
        "guard_metric_before": result.off_guard_metric,
        "guard_metric_after": result.on_guard_metric,
        "regression": regression,
        "runtime_cost": result.runtime_seconds,
        "memory_cost": result.memory_bytes,
        "status": status,
        "runtime_call_path": spec["runtime_call_path"],
        "global_gain_changed": result.global_gain_changed,
        "evidence_boundary": "synthetic; uncalibrated; no global gain/PTR/Radiation/Track-P change",
    }, result


__all__ = [
    "AblationRender",
    "METHOD_CATALOG",
    "build_method_adoption_matrix",
    "build_teacher_vs_reduced_response",
    "render_ablation_case",
    "render_final_scene",
    "render_parent_scene",
    "score_ablation",
]
