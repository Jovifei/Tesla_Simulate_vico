"""Continuous 30-second audition publisher with a stateful high-RPM lift."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .acoustic_analysis import compute_order_map, compute_realism_metrics, write_order_map, write_spectrogram
from .acoustic_layers.realism_profiles import SUPPORTED_REALISM_VEHICLE_IDS
from .contracts import SourceRender, VehicleStateTrace
from .loudness_manager import manage_bundle_loudness, measure_loudness
from .render_identity_v02 import _apply_frozen_ptr, _edge_fade, _health, _loudness_dict, _ptr_provenance, _read_pcm24_wav, _trace_metadata, _write_json, _write_manifest, _write_pcm24_wav
from .render_realism_v10 import _RENDERERS, _SAMPLE_RATE_HZ, _SCOPE, _render_stateful


_LIFT_PHASE = 18.0 / 30.0
_PROFILE = {
    "ferrari_458": {"rpm": (1050.0, 1050.0, 7800.0, 9000.0, 5500.0, 1800.0, 1050.0), "load": (.14, .14, .35, .98, .12, .08, .14), "shift_drop": 920.0},
    "hellcat": {"rpm": (820.0, 820.0, 5200.0, 6200.0, 3600.0, 1300.0, 820.0), "load": (.16, .16, .35, 1.00, .12, .08, .16), "shift_drop": 780.0},
    "rx7_fd": {"rpm": (920.0, 920.0, 6500.0, 7800.0, 4800.0, 1700.0, 920.0), "load": (.15, .15, .35, .98, .12, .08, .15), "shift_drop": 860.0},
    "aventador_lp700": {"rpm": (950.0, 950.0, 7600.0, 8700.0, 5600.0, 1500.0, 950.0), "load": (.14, .14, .34, .99, .12, .08, .14), "shift_drop": 900.0},
    "c63_w204": {"rpm": (750.0, 750.0, 5600.0, 7000.0, 4200.0, 1400.0, 750.0), "load": (.16, .16, .34, .98, .12, .08, .16), "shift_drop": 700.0},
    "gtr_r35": {"rpm": (1000.0, 1000.0, 5700.0, 7000.0, 4300.0, 1450.0, 1000.0), "load": (.15, .15, .35, .99, .12, .08, .15), "shift_drop": 820.0},
    "lfa": {"rpm": (900.0, 900.0, 7700.0, 9000.0, 5700.0, 1600.0, 900.0), "load": (.14, .14, .35, .99, .12, .08, .14), "shift_drop": 880.0},
    "supra_jza80": {"rpm": (800.0, 800.0, 5600.0, 7200.0, 4300.0, 1450.0, 800.0), "load": (.15, .15, .34, .98, .12, .08, .15), "shift_drop": 760.0},
}
_PHASES = np.asarray((0.0, 4.0 / 30.0, 13.0 / 30.0, _LIFT_PHASE, 23.0 / 30.0, 26.0 / 30.0, 1.0))


def build_drive_cycle_trace(vehicle_id: str, duration_s: float = 30.0) -> VehicleStateTrace:
    """Build one continuous idle, pull, lift, coast, and idle-return state trace."""
    if vehicle_id not in SUPPORTED_REALISM_VEHICLE_IDS or vehicle_id not in _PROFILE:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    if not np.isfinite(duration_s) or duration_s < 1.0:
        raise ValueError("duration_s must be finite and >= 1.0")
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    phase = time_s / duration_s
    profile = _PROFILE[vehicle_id]
    rpm = np.interp(phase, _PHASES, profile["rpm"])
    acceleration_start = _PHASES[1] * duration_s
    acceleration_end = _PHASES[2] * duration_s
    acceleration_span = acceleration_end - acceleration_start
    centers = acceleration_start + acceleration_span * np.asarray((0.24, 0.52, 0.80), dtype=np.float64)
    half_width_s = 0.060
    for center in centers:
        distance = np.abs(time_s - center)
        rpm -= np.where(distance < half_width_s, profile["shift_drop"] * (1.0 - distance / half_width_s), 0.0)
    load = np.where(
        phase < _LIFT_PHASE,
        np.interp(phase, _PHASES[:4], profile["load"][:4]),
        np.interp(phase, _PHASES[3:], profile["load"][3:]),
    )
    throttle = np.where(
        phase < _LIFT_PHASE,
        np.interp(phase, _PHASES[:4], (.14, .14, .92, .98)),
        np.interp(phase, _PHASES[3:], (.03, .03, .03, profile["load"][-1])),
    )
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def render_drive_cycle_source(vehicle_id: str, trace: VehicleStateTrace) -> SourceRender:
    """Render a continuous stateful source and retain the lift timing for audit."""
    if vehicle_id not in _RENDERERS:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    trace.validate()
    rendered = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    return SourceRender(
        pressure=rendered.pressure,
        stems=rendered.stems,
        diagnostics={
            **rendered.diagnostics,
            "drive_cycle_lift_time_s": float(trace.time_s[-1] * _LIFT_PHASE),
            "drive_cycle_sections": "idle -> acceleration -> full_pull -> lift_afterfire -> coast -> idle_return",
            "afterfire_stem_energy": float(np.sum(np.square(rendered.stems["afterfire"]))),
        },
    ).validate()


def publish_drive_cycle_v10(
    output_root: str | Path,
    duration_s: float = 30.0,
    vehicle_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Publish continuous audition WAVs with one fixed gain per vehicle."""
    if not np.isfinite(duration_s) or duration_s < 1.0:
        raise ValueError("duration_s must be finite and >= 1.0")
    root = Path(output_root)
    cycle_root = root / "drive_cycle_v10"
    cycle_root.mkdir(parents=True, exist_ok=True)
    ptr = _ptr_provenance()
    selected = tuple(SUPPORTED_REALISM_VEHICLE_IDS if vehicle_ids is None else vehicle_ids)
    if not selected or any(vehicle_id not in _RENDERERS for vehicle_id in selected) or len(set(selected)) != len(selected):
        raise ValueError("vehicle_ids must be a non-empty tuple of supported unique vehicle IDs")
    publication: dict[str, object] = {"scope": _SCOPE, "duration_s": duration_s, "vehicle_ids": selected, "ptr_provenance": ptr, "vehicles": {}}
    for vehicle_id in selected:
        vehicle_root = cycle_root / vehicle_id
        vehicle_root.mkdir(parents=True, exist_ok=True)
        trace = build_drive_cycle_trace(vehicle_id, duration_s)
        source = render_drive_cycle_source(vehicle_id, trace)
        source_metrics = compute_realism_metrics(vehicle_id, source, trace, _SAMPLE_RATE_HZ)
        transients = source_metrics["transients"]
        if transients["afterfire_event_count"] <= 0 or transients["afterfire_stem_energy"] <= 0.0:
            raise ValueError(f"complete drive-cycle afterfire gate failed for {vehicle_id}")
        ptr_audio = _edge_fade(_apply_frozen_ptr(source.pressure))
        managed = manage_bundle_loudness({"drive_cycle": ptr_audio}, _SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=-1.5)
        wav_path = _write_pcm24_wav(vehicle_root / "drive_cycle.wav", managed.segments["drive_cycle"])
        reopened = _read_pcm24_wav(wav_path)
        health = _health(reopened)
        if not health["passes"]:
            raise ValueError(f"complete drive-cycle health gate failed for {vehicle_id}")
        metrics = {
            "vehicle_id": vehicle_id,
            "scope": _SCOPE,
            "provenance": {"synthesis": "C/synthetic", "calibration": "uncalibrated"},
            "wav": wav_path.name,
            "scenario": {
                **_trace_metadata(trace),
                "sections": _section_description(duration_s),
                "lift_time_s": source.diagnostics["drive_cycle_lift_time_s"],
            },
            "loudness": {"target_lufs": -16.0, "one_fixed_drive_cycle_gain_db": managed.gain_db, "headroom_limited": managed.headroom_limited, "drive_cycle": _loudness_dict(measure_loudness(reopened))},
            "health": health,
            "source_realism": source_metrics,
            "afterfire_gate": {"passes": True, "event_count": transients["afterfire_event_count"], "stem_energy": transients["afterfire_stem_energy"]},
            "ptr_provenance": ptr,
        }
        _write_json(vehicle_root / "identity_metrics.json", metrics)
        write_spectrogram(vehicle_root / "spectrogram.png", reopened, _SAMPLE_RATE_HZ)
        write_order_map(vehicle_root / "order_map.png", compute_order_map(reopened, trace, _SAMPLE_RATE_HZ))
        publication["vehicles"][vehicle_id] = metrics
    _write_cycle_report(root, publication)
    _write_manifest(root)
    return publication


def _write_cycle_report(root: Path, publication: dict[str, object]) -> None:
    lines = [
        "# S12 Complete Drive-Cycle Audition Report",
        "",
        "Each supplied WAV is one continuous state render, not a concatenation of independently normalised clips.",
        "",
        "## Common 30-second sequence",
        "",
        "`0–4 s idle → 4–13 s acceleration → 13–18 s full pull → 18–23 s high-RPM closed-throttle lift/afterfire → 23–26 s coast → 26–30 s idle return`.",
        "",
        "The lift changes throttle directly from loaded pull to closed throttle at 18 s. This preserves the thermal/exhaust history required by the state-dependent afterfire source; it is not random noise.",
        "",
        "## Per-vehicle automated gates",
        "",
    ]
    lines[6] = f"`{_section_description(float(publication['duration_s']))}`."
    for vehicle_id, metrics in publication["vehicles"].items():
        loudness = metrics["loudness"]["drive_cycle"]
        afterfire = metrics["afterfire_gate"]
        lines.extend((
            f"### {vehicle_id}",
            "",
            f"- Afterfire: `{afterfire['event_count']}` events; stem energy `{afterfire['stem_energy']:.6f}`; automatic gate `PASS`.",
            f"- Loudness: `{loudness['integrated_lufs']:.2f} LUFS`, `{loudness['rms_dbfs']:.2f} dBFS RMS`, `{loudness['peak_dbfs']:.2f} dBFS peak`, `{loudness['crest_factor_db']:.2f} dB crest`; fixed whole-cycle gain `{metrics['loudness']['one_fixed_drive_cycle_gain_db']:.3f} dB`.",
            f"- WAV: `drive_cycle_v10/{vehicle_id}/drive_cycle.wav`; metrics: `drive_cycle_v10/{vehicle_id}/identity_metrics.json`.",
            "",
        ))
    lines.extend((
        "## Boundary",
        "",
        "FVM, PTR core, Radiation Boundary, Runtime latency, Android, MATLAB, and Simulink were not changed. The existing frozen adapter is consumed unchanged. Output is synthetic, uncalibrated, and not an OEM reproduction. Human audition remains pending.",
        "",
    ))
    (root / "S12_Complete_Drive_Cycle_Audition_Report.md").write_text("\n".join(lines), encoding="utf-8")


def _section_description(duration_s: float) -> str:
    values = np.asarray((0.0, 4.0 / 30.0, 13.0 / 30.0, 18.0 / 30.0, 23.0 / 30.0, 26.0 / 30.0, 1.0)) * duration_s
    return (
        f"{values[0]:g}-{values[1]:g} idle; {values[1]:g}-{values[2]:g} acceleration (3 shifts); "
        f"{values[2]:g}-{values[3]:g} full pull; {values[3]:g}-{values[4]:g} lift/afterfire; "
        f"{values[4]:g}-{values[5]:g} coast; {values[5]:g}-{values[6]:g} idle return"
    )
