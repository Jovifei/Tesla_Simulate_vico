"""Hellcat Stage Y layer audition package (synthetic, uncalibrated)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..event_domain.config_schema import load_config
from ..stage_v.io import write_json, write_pcm24_wav
from ..stage_w.bakeoff import OUTPUT_SCALE, SAMPLE_RATE_HZ, BLOCK_SIZE, _render_architecture, build_hellcat_bakeoff_trace
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from .fixture_cycles import synthesize_hellcat_cycle_bank
from .harmonic_map_fit import fit_harmonic_map

SCENES = (
    "hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm",
    "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift",
    "afterfire_eligible", "afterfire_ineligible", "idle_return",
)
STEMS = ("parent", "y1_event", "y2_map", "y3_p4", "y4_transients", "y5_dp", "monitor")
FORBIDDEN_NAMES = ("gta", "fivem", "gtav", "five_m")


def _safe_pcm(audio: np.ndarray) -> np.ndarray:
    scaled = np.asarray(audio, dtype=np.float64) * OUTPUT_SCALE
    peak = float(np.max(np.abs(scaled))) if scaled.size else 0.0
    if peak >= 0.99:
        scaled = scaled * (0.98 / peak)
    return scaled


def _fitted_config() -> dict[str, Any]:
    config = load_config("hellcat_v1")
    mapped = fit_harmonic_map(synthesize_hellcat_cycle_bank(SAMPLE_RATE_HZ), vehicle_id="hellcat")
    config["timbre_map"] = {
        "rpm_axis": mapped["rpm_axis"],
        "load_axis": mapped["load_axis"],
        "boost_axis": mapped["boost_axis"],
        "order_axis": mapped["order_axis"],
        "values": mapped["amplitude"],
    }
    config["require_fitted_timbre_map"] = True
    return config


def _render_y5(trace) -> tuple[np.ndarray, np.ndarray]:
    config = _fitted_config()
    engine = PersistentEventDomainEngine(
        config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True,
        path_model="waveguide_v1", forced_induction_model="timbre_map_v1",
        transient_model="state_v1", audio_chain="dp_v1",
    )
    result = engine.process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    post = result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm
    return post, result.monitor_pcm


def _render_y2(trace) -> np.ndarray:
    config = _fitted_config()
    engine = PersistentEventDomainEngine(config, SAMPLE_RATE_HZ, BLOCK_SIZE, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1")
    result = engine.process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    return result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm


def build_hellcat_layer_package(root: str | Path, long_window: bool = False, duration_s: float = 8.0) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    parent_bytes = b""
    candidate_bytes = b""
    files: dict[str, str] = {}
    for scene in SCENES:
        scene_duration = 20.0 if long_window and scene == "hot_idle_20s" else float(duration_s)
        trace = build_hellcat_bakeoff_trace(scene, scene_duration)
        _p1_raw, p1_post, _p1_mon, _ = _render_architecture("P1", trace)
        _p2h_raw, p2h_post, _p2h_mon, _ = _render_architecture("P2H", trace)
        y2 = _render_y2(trace)
        _p4_raw, p4_post, _p4_mon, _ = _render_architecture("P4", trace)
        _p5_raw, p5_post, _p5_mon, _ = _render_architecture("P5", trace)
        y5_post, y5_mon = _render_y5(trace)
        stems = {
            "parent": p1_post,
            "y1_event": p2h_post,
            "y2_map": y2,
            "y3_p4": p4_post,
            "y4_transients": p5_post,
            "y5_dp": y5_post,
            "monitor": y5_mon,
        }
        scene_dir = root / scene
        scene_dir.mkdir(parents=True, exist_ok=True)
        for name, audio in stems.items():
            receipt = write_pcm24_wav(scene_dir / f"{name}.wav", _safe_pcm(audio), SAMPLE_RATE_HZ)
            files[f"{scene}/{name}.wav"] = receipt.sha256
        parent_bytes += np.asarray(p1_post).tobytes()
        candidate_bytes += np.asarray(y5_post).tobytes()
    manifest = {
        "schema": "s12.stage_y.layer_package.v1",
        "vehicle_id": "hellcat",
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        "formal_status": "FORMAL_R1_REFERENCE_MISSING",
        "parent_sha256": hashlib.sha256(parent_bytes).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "scenes": list(SCENES),
        "stems": list(STEMS),
        "files": files,
        "long_window": bool(long_window),
        "duration_s": float(duration_s),
    }
    write_json(root / "package_manifest.json", manifest)
    (root / "AUDITION_GUIDE_ZH.md").write_text(
        "# Stage Y Hellcat 分层试听\n\n"
        "状态：`FORMAL_R1_REFERENCE_MISSING`。合成、未标定、车辆启发，不是 OEM 复刻。\n\n"
        "## Timbre（音色）\n\n"
        "先听 `y2_map` 对 `parent`：谐波表是否让怠速/2000 rpm 更像机械而不是公式啸叫。\n\n"
        "## Dynamic（动态）\n\n"
        "再听 `y4_transients` 与 `y5_dp`：tip-in、换挡、收油是否有事件，而不是一直平涂。Monitor 仅用于听感，不作为物理真值。\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def validate_layer_package(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("formal_status") != "FORMAL_R1_REFERENCE_MISSING":
        errors.append("formal_status")
    if "OEM" in json.dumps(manifest):
        errors.append("oem_claim")
    if manifest.get("parent_sha256") == manifest.get("candidate_sha256"):
        errors.append("parent_equals_candidate")
    for path in root.rglob("*"):
        lowered = path.name.lower()
        if any(token in lowered for token in FORBIDDEN_NAMES):
            errors.append(f"forbidden_name:{path.name}")
    for scene in SCENES:
        for stem in STEMS:
            wav = root / scene / f"{stem}.wav"
            if not wav.is_file():
                errors.append(f"missing:{scene}/{stem}.wav")
    return errors
