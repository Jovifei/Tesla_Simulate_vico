"""Deterministic, synthetic v0.15 identity-v02 audition publisher."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import wave

import numpy as np

from .acoustic_analysis import compare_identity_renders, compute_engine_identity_metrics, compute_order_map, write_order_map, write_spectrogram
from .acoustic_layers import apply_low_frequency_body
from .contracts import SourceRender, VehicleStateTrace
from .loudness_manager import LoudnessMetrics, manage_bundle_loudness, measure_loudness
from .sources.flat_plane_v8_source import render_ferrari_458
from .sources.rotary_turbo_source import render_rx7_fd
from .sources.supercharged_hemi_source import render_hellcat
from .tuning.loudness_compensation import apply_post_ptr_compensation, render_baseline_source


_SAMPLE_RATE_HZ = 48000
_CLIPS = ("idle", "cruise", "acceleration", "lift", "full_pull")
_RENDERERS = {"ferrari_458": render_ferrari_458, "hellcat": render_hellcat, "rx7_fd": render_rx7_fd}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"
_DEMO_ROOT = Path(__file__).resolve().parents[1] / "acoustic_demo"
if str(_DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(_DEMO_ROOT))
from runtime_ptr_adapter import RuntimePtrAdapter  # noqa: E402 - sibling frozen adapter


def publish_identity_v02(output_root: str | Path, scenario_duration_s: float = 3.0) -> dict[str, object]:
    """Publish all v0.15 listening clips and a same-state final-PCM A/B proof."""
    if not np.isfinite(scenario_duration_s) or scenario_duration_s < 0.45:
        raise ValueError("scenario_duration_s must be finite and >= 0.45")
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    identity_root = root / "identity_v02"
    identity_root.mkdir(parents=True, exist_ok=True)
    ptr = _ptr_provenance()
    publication: dict[str, object] = {"output_root": str(root), "identity_v02_root": str(identity_root), "vehicles": {}, "ptr_provenance": ptr}
    final_pcm: dict[str, np.ndarray] = {}
    comparison_trace = _comparison_trace(scenario_duration_s)
    for vehicle_id, renderer in _RENDERERS.items():
        vehicle_root = identity_root / vehicle_id
        vehicle_root.mkdir(parents=True, exist_ok=True)
        traces = {name: _scenario_trace(vehicle_id, name, scenario_duration_s) for name in _CLIPS}
        source_renders = {name: apply_low_frequency_body(renderer(trace), vehicle_id) for name, trace in traces.items()}
        # Track S post-PTR per-state loudness compensation (Task 3.1): re-land each
        # shaped clip on its pre-shaping post-PTR loudness so the frozen PTR band
        # tilt does not blow the cross-state LUFS spread. Scalar make-up gain only;
        # band shares and source-level RMS stay untouched. Hellcat/RX-7 have no
        # state EQ, so their reference equals the shaped render and the gain is 0 dB.
        reference_renders = {name: apply_low_frequency_body(render_baseline_source(renderer, trace), vehicle_id) for name, trace in traces.items()}
        ptr_renders = {}
        for name in _CLIPS:
            shaped = _edge_fade(_apply_frozen_ptr(source_renders[name].pressure))
            reference = _edge_fade(_apply_frozen_ptr(reference_renders[name].pressure))
            compensated, _ = apply_post_ptr_compensation(shaped, reference, sample_rate_hz=_SAMPLE_RATE_HZ)
            ptr_renders[name] = compensated
        managed = manage_bundle_loudness(ptr_renders, _SAMPLE_RATE_HZ, target_lufs=-18.0, peak_limit_dbfs=-1.0)
        clips: dict[str, dict[str, object]] = {}
        final_segments: dict[str, np.ndarray] = {}
        for name in _CLIPS:
            audio = managed.segments[name]
            wav_path = _write_pcm24_wav(vehicle_root / f"{name}.wav", audio)
            reopened = _read_pcm24_wav(wav_path)
            health = _health(reopened)
            if not health["passes"]:
                raise ValueError(f"publication health gate failed for {vehicle_id}/{name}")
            loudness = _loudness_dict(measure_loudness(reopened))
            if loudness["integrated_lufs"] < -30.0:
                raise ValueError(f"publication loudness gate failed for {vehicle_id}/{name}: {loudness['integrated_lufs']:.3f} LUFS")
            final_segments[name] = reopened
            clips[name] = {
                "wav": wav_path.name,
                "loudness_gain_db": managed.gain_db,
                "loudness": loudness,
                "health": health,
                "scenario": _trace_metadata(traces[name]),
            }
        full_pull = final_segments["full_pull"]
        full_pull_render = _final_domain_render(vehicle_id, source_renders["full_pull"], full_pull, managed.gain_linear)
        final_bundle_loudness = _loudness_dict(measure_loudness(np.concatenate(tuple(final_segments.values()), axis=0)))
        metrics = {
            "vehicle_id": vehicle_id,
            "scope": _SCOPE,
            "provenance": {"parameter_class": "C/synthetic", "research_use": "listening-only; not calibration evidence"},
            "vehicle_metrics": compute_engine_identity_metrics(vehicle_id, full_pull_render, traces["full_pull"]),
            "vehicle_metrics_domain": "final_pcm_after_frozen_ptr_edge_post_ptr_compensation_and_bundle_gain",
            "full_pull_final_pcm_loudness": _loudness_dict(measure_loudness(full_pull)),
            "bundle": {"gain_db": managed.gain_db, "headroom_limited": managed.headroom_limited, "metrics": final_bundle_loudness},
            "clips": clips,
            "scenarios": {name: clips[name]["scenario"] for name in _CLIPS},
            "ptr_provenance": ptr,
            "health": _health(full_pull),
            "gates": {
                "all_wav_health_pass": all(bool(clip["health"]["passes"]) for clip in clips.values()),
                "all_clip_loudness_measured": all(np.isfinite(clip["loudness"]["integrated_lufs"]) for clip in clips.values()),
                "all_clip_loudness_at_least_minus_30_lufs": all(clip["loudness"]["integrated_lufs"] >= -30.0 for clip in clips.values()),
                "one_fixed_bundle_gain": len({clip["loudness_gain_db"] for clip in clips.values()}) == 1,
                "json_finite": True,
            },
        }
        _write_json(vehicle_root / "identity_metrics.json", metrics)
        write_spectrogram(vehicle_root / "spectrogram.png", full_pull, _SAMPLE_RATE_HZ)
        write_order_map(vehicle_root / "order_map.png", compute_order_map(full_pull, traces["full_pull"], _SAMPLE_RATE_HZ))
        comparison_shaped = apply_low_frequency_body(renderer(comparison_trace), vehicle_id)
        comparison_reference_source = apply_low_frequency_body(render_baseline_source(renderer, comparison_trace), vehicle_id)
        comparison_audio = (
            apply_post_ptr_compensation(
                _edge_fade(_apply_frozen_ptr(comparison_shaped.pressure)),
                _edge_fade(_apply_frozen_ptr(comparison_reference_source.pressure)),
                sample_rate_hz=_SAMPLE_RATE_HZ,
            )[0]
            * managed.gain_linear
        )
        final_pcm[vehicle_id] = _pcm24_roundtrip(comparison_audio)
        publication["vehicles"][vehicle_id] = {"clips": clips, "metrics": metrics}
    comparison = compare_identity_renders(final_pcm, comparison_trace, _SAMPLE_RATE_HZ)
    if not comparison["passes"]:
        raise ValueError("same-state final-PCM identity comparison gate failed")
    comparison["audio_domain"] = "final_pcm_after_frozen_ptr_edge_post_ptr_compensation_and_bundle_gain"
    comparison["common_trace"] = _trace_metadata(comparison_trace)
    comparison["analysis_copy"] = "unit-RMS copies used only for correlation/order comparison; published listening WAVs unchanged"
    publication["comparison"] = comparison
    _write_json(root / "comparison.json", comparison)
    _write_reports(root, publication, comparison_trace)
    _write_manifest(root)
    return publication


def _apply_frozen_ptr(audio: np.ndarray) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float64)
    return np.column_stack((
        np.asarray(RuntimePtrAdapter(sample_rate_hz=_SAMPLE_RATE_HZ).process(samples[:, 0])),
        np.asarray(RuntimePtrAdapter(sample_rate_hz=_SAMPLE_RATE_HZ).process(samples[:, 1])),
    ))


def _final_domain_render(vehicle_id: str, source: SourceRender, final_pressure: np.ndarray, gain_linear: float) -> SourceRender:
    required = {"ferrari_458": (), "hellcat": ("blower",), "rx7_fd": ("turbo", "turbine", "lift")}[vehicle_id]
    stems = {
        name: _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(source.stems[name])) * gain_linear)
        for name in required
    }
    if not stems:
        stems = {"final_pcm_pressure": np.asarray(final_pressure, dtype=np.float64).copy()}
    return SourceRender(
        pressure=np.asarray(final_pressure, dtype=np.float64),
        stems=stems,
        diagnostics={**source.diagnostics, "analysis_domain": "final_pcm_after_linear_frozen_ptr_edge_and_bundle_gain"},
    ).validate()


def _edge_fade(audio: np.ndarray, frames: int = 240) -> np.ndarray:
    result = np.asarray(audio, dtype=np.float64).copy()
    size = min(frames, result.shape[0] // 2)
    if size:
        ramp = np.linspace(0.0, 1.0, size, endpoint=True)[:, np.newaxis]
        result[:size] *= ramp
        result[-size:] *= ramp[::-1]
    return result


def _scenario_trace(vehicle_id: str, scenario: str, duration_s: float) -> VehicleStateTrace:
    ranges = {
        "ferrari_458": {"idle": (1100, 1100, .12, .12), "cruise": (3000, 4200, .34, .46), "acceleration": (3600, 8800, .45, .94), "lift": (7600, 5200, .88, .05), "full_pull": (2600, 8800, .40, .98)},
        "hellcat": {"idle": (850, 850, .14, .14), "cruise": (1800, 3100, .32, .48), "acceleration": (2400, 6100, .52, .98), "lift": (5600, 3700, .95, .05), "full_pull": (1500, 6200, .45, 1.0)},
        "rx7_fd": {"idle": (950, 950, .14, .14), "cruise": (2800, 4300, .34, .52), "acceleration": (3300, 7600, .45, .95), "lift": (6900, 4700, .90, .04), "full_pull": (2500, 7800, .40, .98)},
    }[vehicle_id][scenario]
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    phase = time_s / duration_s
    rpm = np.interp(phase, (0.0, 1.0), ranges[:2])
    load = np.interp(phase, (0.0, 1.0), ranges[2:])
    throttle = load.copy()
    if scenario == "lift":
        throttle = np.where(phase < 0.48, ranges[2], ranges[3])
        load = np.where(phase < 0.48, ranges[2], max(ranges[3], 0.10))
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _comparison_trace(duration_s: float) -> VehicleStateTrace:
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    return VehicleStateTrace(time_s, np.full(count, 4800.0), np.full(count, .70), np.full(count, .70), np.zeros(count)).validate()


def _ptr_provenance() -> dict[str, object]:
    adapter = RuntimePtrAdapter(sample_rate_hz=_SAMPLE_RATE_HZ)
    return {
        "runtime_ptr_adapter_sha256": _sha256(_DEMO_ROOT / "runtime_ptr_adapter.py"),
        "radiation_package_sha256": adapter.package.sha256,
        "radiation_source_commit": adapter.package.source_commit,
        "adapter": "existing lightweight frozen PTR/radiation adapter; not a full FVM/PTR network",
    }


def _health(audio: np.ndarray) -> dict[str, object]:
    peak = float(np.max(np.abs(audio)))
    peak_dbfs = 20.0 * np.log10(peak) if peak else float("-inf")
    return {"sample_rate_hz": _SAMPLE_RATE_HZ, "channels": 2, "pcm": "PCM_24", "frames": int(audio.shape[0]), "finite": bool(np.all(np.isfinite(audio))), "peak_dbfs": peak_dbfs, "clipping_count": int(np.count_nonzero(np.abs(audio) >= 1.0)), "passes": bool(np.all(np.isfinite(audio)) and audio.size and peak <= 10.0 ** (-1.0 / 20.0) and np.count_nonzero(np.abs(audio) >= 1.0) == 0)}


def _loudness_dict(metrics: LoudnessMetrics) -> dict[str, object]:
    if not np.isfinite(metrics.integrated_lufs):
        raise ValueError("integrated_lufs must be finite and measured")
    if not all(np.isfinite(value) for value in (metrics.rms_dbfs, metrics.peak_dbfs, metrics.crest_factor_db)):
        raise ValueError("publication loudness metrics must be finite")
    return {
        "integrated_lufs": metrics.integrated_lufs,
        "integrated_lufs_status": "measured",
        "rms_dbfs": metrics.rms_dbfs,
        "peak_dbfs": metrics.peak_dbfs,
        "crest_factor_db": metrics.crest_factor_db,
        "clipping_count": metrics.clipping_count,
    }


def _trace_metadata(trace: VehicleStateTrace) -> dict[str, object]:
    return {"duration_s": float(trace.time_s[-1]), "rpm_start": float(trace.rpm[0]), "rpm_end": float(trace.rpm[-1]), "load_start": float(trace.load[0]), "load_end": float(trace.load[-1]), "throttle_start": float(trace.throttle[0]), "throttle_end": float(trace.throttle[-1])}


def _write_pcm24_wav(path: Path, audio: np.ndarray) -> Path:
    pcm = np.clip(np.rint(np.asarray(audio, dtype=np.float64) * 8388607.0), -8388608, 8388607).astype("<i4")
    packed = pcm.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(_SAMPLE_RATE_HZ)
        stream.writeframes(packed)
    return path


def _read_pcm24_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (_SAMPLE_RATE_HZ, 2, 3):
            raise ValueError(f"unexpected WAV format: {path}")
        raw = np.frombuffer(stream.readframes(stream.getnframes()), dtype=np.uint8).reshape(-1, 3)
    signed = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
    signed[signed & 0x800000 != 0] -= 0x1000000
    return (signed.reshape(-1, 2).astype(np.float64) / 8388607.0)


def _pcm24_roundtrip(audio: np.ndarray) -> np.ndarray:
    pcm = np.clip(np.rint(np.asarray(audio) * 8388607.0), -8388608, 8388607).astype(np.int32)
    return pcm.astype(np.float64) / 8388607.0


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_reports(root: Path, publication: dict[str, object], comparison_trace: VehicleStateTrace) -> None:
    vehicles = publication["vehicles"]
    ptr = publication["ptr_provenance"]
    comparison = publication["comparison"]
    pair_lines = [
        f"- `{name}`: correlation `{values['absolute_waveform_correlation']:.6f}` (<0.85), "
        f"log-order distance `{values['log_order_cosine_distance']:.6f}` (>0.20): {'PASS' if values['passes'] else 'FAIL'}."
        for name, values in comparison["pairs"].items()
    ]
    loudness_lines = []
    metric_lines = []
    artifact_lines = []
    for vehicle_id, details in vehicles.items():
        metrics = details["metrics"]
        clip_loudness = {name: clip["loudness"]["integrated_lufs"] for name, clip in metrics["clips"].items()}
        loudness_lines.append(
            f"- `{vehicle_id}`: one gain `{metrics['bundle']['gain_db']:.3f} dB`; bundle "
            f"`{metrics['bundle']['metrics']['integrated_lufs']:.3f} LUFS`; minimum clip "
            f"`{min(clip_loudness.values()):.3f} LUFS`; "
            + ", ".join(f"{name} `{value:.3f}`" for name, value in clip_loudness.items()) + "."
        )
        measured = metrics["vehicle_metrics"]
        identity = measured.get("ferrari") or measured.get("hellcat") or measured.get("rx7")
        metric_lines.append(
            f"- `{vehicle_id}` final PCM: centroid `{measured['spectral_centroid_hz']:.2f} Hz`, "
            f"40--400 Hz fraction `{measured['low_energy_fraction_40_400hz']:.6f}`, "
            f">1200 Hz fraction `{measured['high_energy_fraction_gt_1200hz']:.6f}`; "
            f"vehicle metrics `{json.dumps(identity, sort_keys=True, allow_nan=False)}`."
        )
        artifact_lines.append(
            f"- `{vehicle_id}`: [idle](identity_v02/{vehicle_id}/idle.wav), "
            f"[cruise](identity_v02/{vehicle_id}/cruise.wav), "
            f"[acceleration](identity_v02/{vehicle_id}/acceleration.wav), "
            f"[lift](identity_v02/{vehicle_id}/lift.wav), "
            f"[full pull](identity_v02/{vehicle_id}/full_pull.wav), "
            f"[spectrogram](identity_v02/{vehicle_id}/spectrogram.png), "
            f"[order map](identity_v02/{vehicle_id}/order_map.png), "
            f"[metrics](identity_v02/{vehicle_id}/identity_metrics.json)."
        )
    body = [
        "synthetic; uncalibrated; not OEM reproduction.",
        "",
        "## Research evidence and caveats",
        "Ferrari, Hellcat, and RX-7 architecture records come from the v0.15 A/B research database. Public-video records are listening-only: Ferrari configuration claims are unverified or modified where identified, the Hellcat uploader stock claim is unverified, and the RX-7 compilation is modified/bridgeported/antilag contrast and excluded from calibration. No video supplies OEM measurements, microphone geometry, or calibration truth.",
        "",
        "## Independent model structures",
        "Ferrari uses alternating flat-plane banks with impulse-driven metallic resonators; Hellcat uses independently resonated irregular cross-plane banks plus load-gated 2.36/11.8/23.6-order blower families; RX-7 uses two phase-offset rotary event trains, primary/secondary spool states, turbine content, and stateful lift decay. The three sources do not share an excitation generator.",
        "",
        "## C/synthetic provenance",
        "All numerical acoustic targets, gains, resonator settings, stereo placement, and listening schedules are C/synthetic engineering choices. They are deterministic candidates informed by bounded research, not measured OEM parameters.",
        "",
        "## Low-frequency components",
        "Before PTR, each source receives causal `engine_body`, `exhaust_pressure`, and `mechanical_weight` resonator components. Hellcat carries the deepest 40--120 Hz body, Ferrari a lighter higher body, and RX-7 a rotary mid-bass profile. No post-PTR EQ, limiter, AGC, order injection, or synthesis is used.",
        "",
        "## Loudness results",
        "One fixed gain is applied to all five clips for each vehicle after frozen PTR, edge formatting, and a per-clip post-PTR Track S loudness make-up that re-lands each shaped clip on its pre-shaping post-PTR loudness (the frozen PTR band tilt otherwise spreads cross-state LUFS by ~12 dB; the make-up is a scalar, so band shares and source-level RMS are untouched). Every reopened PCM clip is finite, measured, at least -30 LUFS, below -1 dBFS peak, and has zero clipping.",
        *loudness_lines,
        "",
        "## Vehicle metrics",
        "Metrics below use final PCM pressure and any required stems after the same frozen PTR, edge fade, post-PTR Track S loudness compensation, vehicle gain, and PCM_24 round trip; pre-PTR stems are not mixed with final pressure.",
        *metric_lines,
        "",
        "## Artifact links",
        *artifact_lines,
        "",
        "## Same-state final-PCM A/B",
        f"All vehicles use the identical `{comparison_trace.rpm[0]:.0f} RPM`, `{comparison_trace.load[0]:.2f}` load/throttle, `{comparison_trace.time_s[-1]:.2f} s` trace. Correlation and order-distance use unit-RMS analysis copies of final PCM only; published listening WAVs are unchanged.",
        *pair_lines,
        "",
        "## Frozen PTR boundary",
        f"The existing lightweight frozen PTR/radiation adapter is consumed unchanged, one instance per stereo channel. Adapter SHA-256: `{ptr['runtime_ptr_adapter_sha256']}`; accepted radiation package SHA-256: `{ptr['radiation_package_sha256']}`; accepted source commit: `{ptr['radiation_source_commit']}`. This adapter is not a full FVM/PTR network.",
        "",
        "## Perceptual candidate answers",
        "Ferrari is a metric-supported candidate for scream/metallic/naturally-aspirated character; Hellcat for deep V8/blower/load aggression; RX-7 for rotary/turbo/non-piston character. These are automatic candidate judgments, not a human listening verdict.",
        "",
        "## Limitations",
        "Public video is listening-only/inconclusive for calibration. Windows 30--50% is a listening objective, not hardware proof. Automatic gates may PASS, but `HUMAN_BLIND_AUDITION_PENDING_JOVI`; no full human perceptual PASS is claimed.",
    ]
    reports = {
        "identity_comparison_report.md": "# Identity Comparison Report",
        "S12_Engine_Acoustic_Identity_v015_Report.md": "# S12 Engine Acoustic Identity v0.15 Report",
        "S12_Engine_Acoustic_Identity_v015_Final_Report.md": "# S12 Engine Acoustic Identity v0.15 Final Report",
    }
    for filename, title in reports.items():
        _write_text(root / filename, [title, "", *body])


def _write_text(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(root: Path) -> None:
    files = {path.relative_to(root).as_posix(): _sha256(path) for path in sorted(root.rglob("*")) if path.is_file() and path.name != "manifest.json"}
    _write_json(root / "manifest.json", {"files": files, "scope": _SCOPE})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
