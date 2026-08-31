"""Deterministic offline publisher for S12 acoustic realism v1.0."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .acoustic_analysis import compare_identity_renders, compute_order_map, compute_realism_metrics, write_order_map, write_spectrogram
from .acoustic_layers import (
    apply_afterfire,
    apply_exhaust_rumble,
    apply_idle_dynamics,
    apply_low_frequency_body,
    apply_pre_ptr_equalization,
    apply_shift_dynamics,
)
from .contracts import SourceRender, VehicleStateTrace
from .loudness_manager import manage_bundle_loudness, measure_loudness
from .render_identity_v02 import _apply_frozen_ptr, _edge_fade, _health, _loudness_dict, _pcm24_roundtrip, _ptr_provenance, _read_pcm24_wav, _trace_metadata, _write_json, _write_manifest, _write_pcm24_wav
from .sources.flat_plane_v8_source import render_ferrari_458
from .sources.rotary_turbo_source import render_rx7_fd
from .sources.supercharged_hemi_source import render_hellcat
from .sources.lamborghini_v12_source import render_aventador_lp700
from .sources.mercedes_v8_source import render_c63_w204
from .sources.nissan_v6_turbo_source import render_gtr_r35
from .sources.lexus_v10_source import render_lfa
from .sources.toyota_i6_turbo_source import render_supra_jza80


_SAMPLE_RATE_HZ = 48000
_CLIPS = ("idle", "acceleration", "deceleration", "full_pull")
_RENDERERS = {
    "ferrari_458": render_ferrari_458,
    "hellcat": render_hellcat,
    "rx7_fd": render_rx7_fd,
    "aventador_lp700": render_aventador_lp700,
    "c63_w204": render_c63_w204,
    "gtr_r35": render_gtr_r35,
    "lfa": render_lfa,
    "supra_jza80": render_supra_jza80,
}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def publish_realism_v10(output_root: str | Path, scenario_duration_s: float = 3.0) -> dict[str, object]:
    """Publish one fixed-gain, stateful four-clip review bundle per vehicle."""
    if not np.isfinite(scenario_duration_s) or scenario_duration_s < 0.45:
        raise ValueError("scenario_duration_s must be finite and >= 0.45")
    root = Path(output_root)
    identity_root = root / "identity_v10"
    identity_root.mkdir(parents=True, exist_ok=True)
    ptr = _ptr_provenance()
    publication: dict[str, object] = {"scope": _SCOPE, "identity_v10_root": str(identity_root), "ptr_provenance": ptr, "vehicles": {}}
    final_pcm: dict[str, np.ndarray] = {}
    comparison_trace = _comparison_trace(scenario_duration_s)
    for vehicle_id, renderer in _RENDERERS.items():
        vehicle_root = identity_root / vehicle_id
        vehicle_root.mkdir(parents=True, exist_ok=True)
        traces = {clip: _scenario_trace(vehicle_id, clip, scenario_duration_s) for clip in _CLIPS}
        sources = {clip: _render_stateful(renderer, vehicle_id, trace) for clip, trace in traces.items()}
        ptr_audio = {clip: _edge_fade(_apply_frozen_ptr(render.pressure)) for clip, render in sources.items()}
        managed = manage_bundle_loudness(ptr_audio, _SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=-1.5)
        clips: dict[str, dict[str, object]] = {}
        for clip in _CLIPS:
            wav_path = _write_pcm24_wav(vehicle_root / f"{clip}.wav", managed.segments[clip])
            reopened = _read_pcm24_wav(wav_path)
            health = _health(reopened)
            if not health["passes"]:
                raise ValueError(f"realism publication health gate failed for {vehicle_id}/{clip}")
            clips[clip] = {
                "wav": wav_path.name,
                "scenario": _trace_metadata(traces[clip]),
                "loudness": _loudness_dict(measure_loudness(reopened)),
                "health": health,
                "source_realism": compute_realism_metrics(vehicle_id, sources[clip], traces[clip]),
            }
        bundle_audio = np.concatenate(tuple(managed.segments[clip] for clip in _CLIPS), axis=0)
        bundle_loudness = _loudness_dict(measure_loudness(bundle_audio))
        metrics = {
            "vehicle_id": vehicle_id,
            "scope": _SCOPE,
            "provenance": {"reference": "B/R2 relative cues only", "synthesis": "C/synthetic", "calibration": "uncalibrated"},
            "loudness": {"target_lufs": -16.0, "one_fixed_bundle_gain_db": managed.gain_db, "headroom_limited": managed.headroom_limited, "bundle": bundle_loudness},
            "clips": clips,
            "ptr_provenance": ptr,
        }
        _write_json(vehicle_root / "identity_metrics.json", metrics)
        full_pull = managed.segments["full_pull"]
        write_spectrogram(vehicle_root / "spectrogram.png", full_pull, _SAMPLE_RATE_HZ)
        write_order_map(vehicle_root / "order_map.png", compute_order_map(full_pull, traces["full_pull"], _SAMPLE_RATE_HZ))
        comparison_render = _render_stateful(renderer, vehicle_id, comparison_trace)
        final_pcm[vehicle_id] = _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(comparison_render.pressure)) * managed.gain_linear)
        publication["vehicles"][vehicle_id] = metrics
    comparison = compare_identity_renders(final_pcm, comparison_trace, _SAMPLE_RATE_HZ)
    if not comparison["passes"]:
        raise ValueError("same-state final-PCM realism identity gate failed")
    comparison.update({"scope": _SCOPE, "audio_domain": "final_pcm_after_frozen_ptr_and_fixed_vehicle_bundle_gain", "common_trace": _trace_metadata(comparison_trace)})
    publication["comparison"] = comparison
    _write_json(root / "comparison.json", comparison)
    _write_reports(root, publication)
    _write_manifest(root)
    return publication


def _render_stateful(renderer: object, vehicle_id: str, trace: VehicleStateTrace) -> SourceRender:
    source = renderer(trace)  # type: ignore[operator]
    idle = apply_idle_dynamics(source, vehicle_id, trace, _SAMPLE_RATE_HZ)
    afterfire = apply_afterfire(idle, vehicle_id, trace, _SAMPLE_RATE_HZ)
    body = apply_low_frequency_body(afterfire, vehicle_id, trace, _SAMPLE_RATE_HZ)
    rumble = apply_exhaust_rumble(body, vehicle_id, trace, _SAMPLE_RATE_HZ)
    shifted = apply_shift_dynamics(rumble, vehicle_id, trace, _SAMPLE_RATE_HZ)
    equalized = apply_pre_ptr_equalization(shifted, vehicle_id, trace, _SAMPLE_RATE_HZ)
    diagnostics = dict(equalized.diagnostics)
    diagnostics["realism_layer_order"] = (
        "independent_source -> idle_dynamics -> state_dependent_afterfire -> "
        "low_frequency_pressure_body -> exhaust_rumble -> shift_dynamics -> "
        "pre_ptr_equalization -> frozen_ptr"
    )
    return SourceRender(pressure=equalized.pressure, stems=equalized.stems, diagnostics=diagnostics).validate()


def _scenario_trace(vehicle_id: str, clip: str, duration_s: float) -> VehicleStateTrace:
    ranges = {
        "ferrari_458": {"idle": (1050.0, 1050.0, .14, .14), "acceleration": (3600.0, 8800.0, .48, .95), "deceleration": (7900.0, 5200.0, .90, .04), "full_pull": (2600.0, 8800.0, .42, .98)},
        "hellcat": {"idle": (820.0, 820.0, .16, .16), "acceleration": (2400.0, 6100.0, .56, .98), "deceleration": (5600.0, 3500.0, .94, .03), "full_pull": (1500.0, 6200.0, .46, 1.00)},
        "rx7_fd": {"idle": (920.0, 920.0, .15, .15), "acceleration": (3300.0, 7600.0, .46, .96), "deceleration": (6900.0, 4500.0, .90, .04), "full_pull": (2500.0, 7800.0, .42, .98)},
        "aventador_lp700": {"idle": (950.0, 950.0, .14, .14), "acceleration": (3500.0, 8500.0, .50, .98), "deceleration": (8000.0, 5500.0, .90, .04), "full_pull": (2500.0, 8700.0, .45, .99)},
        "c63_w204": {"idle": (750.0, 750.0, .16, .16), "acceleration": (2200.0, 6800.0, .55, .98), "deceleration": (6200.0, 4000.0, .92, .03), "full_pull": (1500.0, 7000.0, .45, 1.00)},
        "gtr_r35": {"idle": (1000.0, 1000.0, .15, .15), "acceleration": (3000.0, 6800.0, .50, .97), "deceleration": (6400.0, 4200.0, .90, .04), "full_pull": (2200.0, 7000.0, .45, .99)},
        "lfa": {"idle": (900.0, 900.0, .14, .14), "acceleration": (4000.0, 8800.0, .50, .99), "deceleration": (8200.0, 5500.0, .90, .04), "full_pull": (3000.0, 9000.0, .45, 1.00)},
        "supra_jza80": {"idle": (800.0, 800.0, .15, .15), "acceleration": (2500.0, 7000.0, .50, .97), "deceleration": (6500.0, 4200.0, .90, .04), "full_pull": (1800.0, 7200.0, .45, .99)},
    }[vehicle_id][clip]
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    phase = time_s / duration_s
    rpm = np.interp(phase, (0.0, 1.0), ranges[:2])
    load = np.interp(phase, (0.0, 1.0), ranges[2:])
    throttle = load.copy()
    if clip == "deceleration":
        close = phase >= 0.42
        throttle = np.where(close, ranges[3], ranges[2])
        load = np.where(close, max(ranges[3], 0.12), ranges[2])
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _comparison_trace(duration_s: float) -> VehicleStateTrace:
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    return VehicleStateTrace(time_s, np.full(count, 4800.0), np.full(count, .70), np.full(count, .70), np.zeros(count)).validate()


def _write_reports(root: Path, publication: dict[str, object]) -> None:
    comparison = publication["comparison"]
    pair_lines = [f"- `{name}`: correlation={result['absolute_waveform_correlation']:.4f}, order distance={result['log_order_cosine_distance']:.4f}, automatic={'PASS' if result['passes'] else 'FAIL'}" for name, result in comparison["pairs"].items()]
    (root / "identity_comparison_report.md").write_text("\n".join(["# S12 v1.0 Identity Comparison", "", "Same RPM/load/acceleration/duration input; fixed per-vehicle bundle gain; final PCM analysis only.", "", *pair_lines, "", f"Automatic identity separation: {'PASS' if comparison['passes'] else 'FAIL'}", "", "This is synthetic, uncalibrated, and not OEM reproduction.", ""]), encoding="utf-8")
    lines = [
        "# S12 Acoustic Realism Report v1.0",
        "",
        "## Status",
        "",
        "`AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`.",
        "",
        "The source path is `independent source → idle dynamics → state-dependent afterfire → pressure/exhaust/body/radiation → existing frozen adapter → PCM24`. FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, and Simulink were not changed.",
        "",
        "## Reference boundary",
        "",
        "`reference_database/realism_reference_manifest.json` records the external R2 media URL, SHA-256, segment intent, and recording risks. It provides relative listening/feature cues only; no item is claimed as stock verified, OEM measured, calibrated, or OEM reproduction.",
        "",
        "## Independent source and realism structures",
        "",
        "- Ferrari 458: independent flat-plane alternating-bank source, impulse-driven metallic modes, idle combustion/valvetrain/crank layers, restrained pressure body, and sparse hot-lift events.",
        "- Hellcat: independent irregular cross-plane exhaust, RPM/load/boost/bypass-state blower, belt/compressor/valvetrain layer, heavy pressure-coupled 40–200 Hz body, and hot-lift event clusters.",
        "- RX-7 FD: independent two-phase rotary source, housing excitation, primary/secondary spool plus boost onset/blow-off, lighter body coupling, and hot-lift event clusters. It does not use a piston firing order.",
        "",
        "All synthesis parameter directions are `C/synthetic`; R2-derived values remain recording-dependent `B/R2` feature context in `targets/realism_feature_targets.json`.",
        "",
        "## Per-vehicle automatic evidence",
        "",
    ]
    for vehicle_id, metrics in publication["vehicles"].items():
        loudness = metrics["loudness"]["bundle"]
        full = metrics["clips"]["full_pull"]["source_realism"]["vehicle_features"][vehicle_id]
        deceleration = metrics["clips"]["deceleration"]["source_realism"]["transients"]
        lines.extend([f"### {vehicle_id}", "", f"- Bundle: {loudness['integrated_lufs']:.2f} LUFS, {loudness['rms_dbfs']:.2f} dBFS RMS, {loudness['peak_dbfs']:.2f} dBFS peak, {loudness['crest_factor_db']:.2f} dB crest.", f"- Full-pull source features: `{json.dumps(full, ensure_ascii=False)}`.", f"- Deceleration: {deceleration['afterfire_event_count']} state-dependent afterfire events; afterfire stem energy={deceleration['afterfire_stem_energy']:.6f}.", f"- Review WAVs: `identity_v10/{vehicle_id}/idle.wav`, `acceleration.wav`, `deceleration.wav`, `full_pull.wav`; plots: `spectrogram.png`, `order_map.png`; measurements: `identity_metrics.json`.", ""])
    lines.extend(["## Listening rubric", "", "- Ferrari: high-RPM metallic NA scream with restrained low-end.", "- Hellcat: 40–200 Hz mass, mechanical pressure, and RPM/load/boost-dependent blower movement.", "- RX-7: non-piston rotary texture, turbo onset, and boost release.", "", "Human blind audition remains required. All output is synthetic, uncalibrated, and not OEM reproduction.", ""])
    (root / "S12_Acoustic_Realism_Report.md").write_text("\n".join(lines), encoding="utf-8")
