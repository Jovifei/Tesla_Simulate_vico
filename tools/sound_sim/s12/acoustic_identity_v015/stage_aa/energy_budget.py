"""Layer-by-layer diagnostic energy ledger for the Hellcat source chain."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np

from ..stage_v.io import write_json
from ..stage_w.bakeoff import BLOCK_SIZE, OUTPUT_SCALE, SAMPLE_RATE_HZ, build_hellcat_bakeoff_trace
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from ..stage_x.multi_reference_comparator import timbre_metrics, raw_dynamic_metrics
from ..stage_y.package import _fitted_config


REPO_ROOT = Path(__file__).resolve().parents[5]
ENERGY_LAYERS = (
    "vehicle_state",
    "combustion_event",
    "forced_induction",
    "per_cylinder_path",
    "waveguide",
    "bank_collector",
    "central_collector",
    "pre_transients",
    "transients",
    "dp_dc",
    "pre_ptr",
    "post_ptr_raw",
    "monitor",
)
SCENES = {
    "hot_idle": "hot_idle_20s",
    "steady_1200": "steady_1200rpm",
    "steady_2000": "steady_2000rpm",
    "steady_3000": "steady_3000rpm",
    "tip_in": "throttle_tip_in",
    "full_load": "full_load_acceleration",
    "gear_shift": "gear_shift",
    "lift": "high_rpm_lift",
    "afterfire": "afterfire_eligible",
    "idle_return": "idle_return",
}
FINAL_SETTINGS = {
    "path_model": "waveguide_v1",
    "forced_induction_model": "timbre_map_v1",
    "cycle_sync_model": "fixture_v1",
    "transient_model": "state_v1",
    "audio_chain": "dp_v1",
}
GAIN_REFERENCES = {
    "per_cylinder_path": "combustion_event",
    "waveguide": "per_cylinder_path",
    "bank_collector": "waveguide",
    "transients": "pre_transients",
    "dp_dc": "transients",
    "pre_ptr": "dp_dc",
    "post_ptr_raw": "pre_ptr",
    "monitor": "post_ptr_raw",
}


def _state_arrays(trace: Any) -> dict[str, np.ndarray]:
    return {name: getattr(trace, name) for name in ("rpm", "load", "throttle", "acceleration_mps2")}


def _band_metrics(audio: np.ndarray) -> dict[str, dict[str, float]]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    frame = max(2048, min(8192, mono.size))
    values = np.pad(mono, (0, max(0, frame - mono.size)))[:frame]
    spectrum = np.abs(np.fft.rfft(values * np.hanning(frame))) ** 2
    frequencies = np.fft.rfftfreq(frame, 1.0 / SAMPLE_RATE_HZ)
    bands = ((20, 80), (80, 120), (120, 250), (250, 400), (400, 1000), (1000, 2000), (2000, 4000), (4000, 8000))
    total = float(np.sum(spectrum[(frequencies >= 20) & (frequencies < 8000)])) + 1.0e-15
    result = {}
    for low, high in bands:
        energy = float(np.sum(spectrum[(frequencies >= low) & (frequencies < high)]))
        result[f"{low}_{high}_hz"] = {
            "power_share": energy / total,
            "rms_dbfs": 10.0 * np.log10(max(energy / max(frame, 1), 1.0e-18)),
        }
    return result


def _layer_metrics(audio: np.ndarray, *, signal_kind: str) -> dict[str, Any]:
    values = np.asarray(audio, dtype=np.float64)
    dynamic = raw_dynamic_metrics(values, SAMPLE_RATE_HZ)
    timbre = timbre_metrics(values, SAMPLE_RATE_HZ)
    mono = np.mean(values, axis=1)
    transient = float(np.sqrt(np.mean(np.square(np.diff(mono)))) if mono.size > 1 else 0.0)
    rms = float(np.sqrt(np.mean(np.square(values)))) if values.size else 0.0
    return {
        "signal_kind": signal_kind,
        "rms_dbfs": float(dynamic["rms_dbfs"]),
        "peak_dbfs": float(dynamic["peak_dbfs"]),
        "crest_db": float(dynamic["crest_db"]),
        "bands": _band_metrics(values),
        "spectral_centroid_hz": float(timbre["spectral_centroid_hz"]),
        "roughness": float(timbre["roughness_proxy"]),
        "tonality": float(timbre["tonality_proxy"]),
        "transient_energy": transient,
        "gain_ratio_vs_previous": None,
        "gain_reference": None,
        "rms_linear": rms,
    }


def _render_scene(scene: str, duration_s: float) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    trace = build_hellcat_bakeoff_trace(SCENES[scene], duration_s)
    engine = PersistentEventDomainEngine(_fitted_config(), SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, **FINAL_SETTINGS)
    block, layers = engine.process_with_layer_trace(_state_arrays(trace))
    scaled = {name: values * OUTPUT_SCALE for name, values in layers.items()}
    diagnostics = {"frames": block.diagnostics.get("frames"), "sample_count": block.diagnostics.get("sample_count"), "engine": block.diagnostics}
    return scaled, diagnostics


def build_energy_budget(*, duration_s: float = 1.0, scenes: Iterable[str] | None = None) -> dict[str, Any]:
    selected = tuple(scenes or SCENES)
    unknown = set(selected) - set(SCENES)
    if unknown:
        raise ValueError(f"unsupported energy budget scenes: {sorted(unknown)}")
    scene_payload: dict[str, Any] = {}
    for index, scene in enumerate(selected, start=1):
        print(f"[AA1 {index}/{len(selected)}] trace {scene}", flush=True)
        signals, diagnostics = _render_scene(scene, duration_s)
        layers: dict[str, Any] = {}
        for layer in ENERGY_LAYERS:
            if layer not in signals:
                raise RuntimeError(f"missing layer trace: {layer}")
            kind = "control_proxy" if layer == "vehicle_state" else "audio"
            metrics = _layer_metrics(signals[layer], signal_kind=kind)
            layers[layer] = metrics
        for layer, reference in GAIN_REFERENCES.items():
            current_rms = float(layers[layer]["rms_linear"])
            reference_rms = float(layers[reference]["rms_linear"])
            layers[layer]["gain_reference"] = reference
            if reference_rms > 1.0e-15:
                layers[layer]["gain_ratio_vs_previous"] = current_rms / reference_rms
        for metrics in layers.values():
            metrics.pop("rms_linear", None)
        scene_payload[scene] = {"duration_s": float(duration_s), "trace_scene": SCENES[scene], "layers": layers, "diagnostics": diagnostics}
    losses = []
    for scene, payload in scene_payload.items():
        names = [name for name in ENERGY_LAYERS if payload["layers"][name]["gain_ratio_vs_previous"] is not None]
        for layer in names:
            ratio = payload["layers"][layer]["gain_ratio_vs_previous"]
            losses.append({"scene": scene, "layer": layer, "gain_db": float(20.0 * np.log10(max(ratio, 1.0e-12))), "gain_ratio": ratio})
    return {
        "schema": "s12.stage_aa.energy_budget_trace.v1",
        "status": "DIAGNOSTIC_ONLY",
        "scope": "Hellcat synthetic source-domain layer taps; OUTPUT_SCALE applied uniformly for published-level comparison",
        "layers": list(ENERGY_LAYERS),
        "scenes": scene_payload,
        "largest_losses": sorted(losses, key=lambda item: item["gain_db"])[:20],
        "boundaries": {"ptr_radiation_track_p": "UNCHANGED", "master_gain_repair": False, "r1_reference": "MISSING"},
    }


def render_root_cause_report(payload: dict[str, Any], *, main_head: str) -> str:
    lines = [
        "# S12 Stage AA 能量账本与根因",
        "",
        f"- main head: `{main_head}`",
        f"- scope: `{payload['scope']}`",
        "- 本账本只记录诊断 layer taps；未修改 master gain、PTR、Radiation 或 Track-P。",
        "",
        "## 最大逐层变化（dB RMS）",
        "",
        "| Scene | Layer | Gain vs previous | Ratio |",
        "| --- | --- | ---: | ---: |",
    ]
    for item in payload["largest_losses"][:12]:
        reference = payload["scenes"][item["scene"]]["layers"][item["layer"]]["gain_reference"]
        lines.append(f"| {item['scene']} | {reference} → {item['layer']} | {item['gain_db']:.3f} dB | {item['gain_ratio']:.6g} |")
    lines.extend(["", "## 结论", ""])
    losses = payload["largest_losses"]
    if losses:
        worst = losses[0]
        lines.append(f"最严重的逐层能量变化出现在 `{worst['scene']}` 的 `{worst['layer']}`，相对前一音频层为 `{worst['gain_db']:.3f} dB`。这只是定位线索，不等于可直接调参。")
    lines.extend([
        "逐层账本必须先用于确认 event/path/collector/waveguide/transient/dP/pre-PTR/post-PTR/monitor 哪一层承担主要损失；任何候选修复都必须回到该层并同时验证低频 body、动态范围、click、afterfire 和 blower guard。",
        "当前结论仍为诊断性：没有使用全局增益补偿，也没有 R1 同步参考，不能从能量恢复本身推出声学质量提升。",
    ])
    return "\n".join(lines) + "\n"


def publish_energy_budget(*, main_head: str, tested_head: str = "unknown", duration_s: float = 1.0, log_path: str | None = None, command: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    payload = build_energy_budget(duration_s=duration_s)
    payload["main_head"] = main_head
    payload["tested_head"] = tested_head
    trace_path = repo_root / "tasks/reports/runtime/s12-stage-aa/energy_budget_trace.json"
    report_path = repo_root / "tasks/reports/runtime/s12-stage-aa/energy_budget_root_cause.md"
    write_json(trace_path, payload)
    report_path.write_text(render_root_cause_report(payload, main_head=main_head), encoding="utf-8", newline="\n")
    ended_at = datetime.now(timezone.utc)
    receipt = {
        "schema": "s12.stage_aa.energy_budget_publish_receipt.v1",
        "status": "PASS",
        "main_head": main_head,
        "tested_head": tested_head,
        "duration_s": duration_s,
        "scenes": len(payload["scenes"]),
        "trace_path": str(trace_path.relative_to(repo_root)).replace("\\", "/"),
        "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
        "report_path": str(report_path.relative_to(repo_root)).replace("\\", "/"),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "command": command or [],
        "started_at_utc": started_at.isoformat().replace("+00:00", "Z"),
        "ended_at_utc": ended_at.isoformat().replace("+00:00", "Z"),
        "exit_code": 0,
        "log_path": log_path,
        "log_sha256": hashlib.sha256(Path(log_path).read_bytes()).hexdigest() if log_path and Path(log_path).is_file() else None,
        "boundaries": payload["boundaries"],
    }
    write_json(repo_root / "tasks/reports/runtime/s12-stage-aa/receipts/aa1-energy-budget.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--duration-s", type=float, default=1.0)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_energy_budget(main_head=args.main_head, tested_head=args.tested_head, duration_s=args.duration_s, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ENERGY_LAYERS", "build_energy_budget", "publish_energy_budget", "render_root_cause_report"]
