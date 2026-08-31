"""Hellcat Stage Y layer audition package (synthetic, uncalibrated)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from ..event_domain.config_schema import load_config
from ..stage_v.io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from ..stage_w.bakeoff import OUTPUT_SCALE, SAMPLE_RATE_HZ, BLOCK_SIZE, build_hellcat_bakeoff_trace
from ..stage_w.boundary_adapter import FrozenPtrStereo
from ..sources.supercharged_hemi_source import render_hellcat
from ..event_domain.audition_monitor import render_audition_monitor
from ..stage_w.persistent_engine import PersistentEventDomainEngine
from .harmonic_map_fit import load_committed_fixture_timbre_map

SCENES = (
    "hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm",
    "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift",
    "afterfire_eligible", "afterfire_ineligible", "idle_return",
)
STEMS = ("parent", "y1_event", "y2_map", "y3_p4", "y4_transients", "y5_dp", "monitor")
FORBIDDEN_NAMES = ("gta", "fivem", "gtav", "five_m")
PACKAGE_SCHEMA = "s12.stage_y.layer_package.v1"
FORMAL_STATUS = "FORMAL_R1_REFERENCE_MISSING"
TIMBRE_TARGET_RMS_PROXY = 0.08
TIMBRE_STEMS = STEMS
REVIEW_PAGES = ("timbre_review.html", "dynamic_review.html")
GUIDE_NAME = "AUDITION_GUIDE_ZH.md"
SHA_MANIFEST_NAME = "sha256_manifest.json"
_LAYER_CONTRACT = {
    "parent": (),
    "y1_event": ("event_domain",),
    "y2_map": ("event_domain", "timbre_map"),
    "y3_p4": ("event_domain", "timbre_map", "cycle_sync"),
    "y4_transients": ("event_domain", "timbre_map", "cycle_sync", "transients"),
    "y5_dp": ("event_domain", "timbre_map", "cycle_sync", "transients", "dp_chain"),
    "monitor": ("event_domain", "timbre_map", "cycle_sync", "transients", "dp_chain", "monitor"),
}
_LAYER_SETTINGS = {
    "y1_event": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"},
    "y2_map": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"},
    "y3_p4": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1", "cycle_sync_model": "fixture_v1"},
    "y4_transients": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1", "cycle_sync_model": "fixture_v1", "transient_model": "state_v1"},
    "y5_dp": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1", "cycle_sync_model": "fixture_v1", "transient_model": "state_v1", "audio_chain": "dp_v1"},
}
_LAYER_FLAG_NAMES = ("event_domain", "timbre_map", "cycle_sync", "transients", "dp_chain", "monitor")


def _safe_pcm(audio: np.ndarray) -> np.ndarray:
    """Validate already-published-domain PCM without hidden normalization."""
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] == 0:
        raise ValueError("Stage-Y layer audio must be nonempty stereo")
    if not np.all(np.isfinite(values)):
        raise ValueError("Stage-Y layer audio must be finite")
    if float(np.max(np.abs(values))) >= 1.0:
        raise ValueError("Stage-Y layer audio clips; no per-scene normalization is allowed")
    return values


def _state_arrays(trace: Any) -> dict[str, np.ndarray]:
    return {
        "rpm": trace.rpm,
        "load": trace.load,
        "throttle": trace.throttle,
        "acceleration_mps2": trace.acceleration_mps2,
    }


def _render_layer(stem: str, trace: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Render one cumulative layer in the unscaled engine domain.

    The fixed publication gain is applied exactly once by the package builder,
    after all source/PTR/monitor work is complete.
    """
    if stem == "parent":
        raw = np.asarray(render_hellcat(trace).pressure, dtype=np.float64)
        target = trace.rpm.size * BLOCK_SIZE
        if raw.shape[0] < target:
            raw = np.pad(raw, ((0, target - raw.shape[0]), (0, 0)))
        elif raw.shape[0] > target:
            raw = raw[:target]
        post = FrozenPtrStereo(SAMPLE_RATE_HZ).process(raw)
        monitor = render_audition_monitor(post, SAMPLE_RATE_HZ).audio
        return raw, post, monitor, {
            "architecture": "P1",
            "source_model": "legacy_v015",
            "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER",
        }
    if stem not in _LAYER_SETTINGS:
        raise ValueError(f"unsupported Stage-Y layer: {stem}")
    config = load_config("hellcat_v1")
    settings = dict(_LAYER_SETTINGS[stem])
    if settings["forced_induction_model"] == "timbre_map_v1":
        fitted_map, fitted_table = load_committed_fixture_timbre_map()
        config["timbre_map"] = {
            "rpm_axis": fitted_table.rpm_axis.tolist(),
            "load_axis": fitted_table.load_axis.tolist(),
            "boost_axis": fitted_table.boost_axis.tolist(),
            "order_axis": fitted_table.order_axis.tolist(),
            "values": fitted_table.values.tolist(),
        }
        config["fitted_timbre_map"] = fitted_map
        config["require_fitted_timbre_map"] = True
    engine = PersistentEventDomainEngine(
        config,
        SAMPLE_RATE_HZ,
        BLOCK_SIZE,
        ptr_enabled=True,
        **settings,
    )
    result = engine.process_with_trace(_state_arrays(trace))
    post = result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm
    diagnostics = dict(result.diagnostics)
    diagnostics.update({
        "architecture": stem,
        "ptr_status": "FROZEN_RUNTIME_PTR_ADAPTER",
        "monitor_source": "PersistentEventDomainEngine.monitor_pcm",
    })
    return result.raw_pcm, post, result.monitor_pcm, diagnostics


def _rms(audio: np.ndarray) -> float:
    values = np.asarray(audio, dtype=np.float64)
    return float(np.sqrt(np.mean(np.square(values)))) if values.size else 0.0


def _safe_timbre_target(audio_by_scene: dict[str, dict[str, np.ndarray]]) -> float:
    """Choose one target RMS proxy that is safe for every matched copy."""
    headroom_targets = []
    for stems in audio_by_scene.values():
        for audio in stems.values():
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            rms = _rms(audio)
            if peak > 0.0 and rms > 0.0:
                headroom_targets.append(0.98 * rms / peak)
    if not headroom_targets:
        raise ValueError("cannot choose timbre target from empty PCM")
    target = min(float(TIMBRE_TARGET_RMS_PROXY), min(headroom_targets))
    if not np.isfinite(target) or target <= 0.0:
        raise ValueError("invalid safe timbre target")
    return target


def _timbre_match(audio: np.ndarray, target_rms: float) -> np.ndarray:
    current = _rms(audio)
    if current <= 1.0e-12:
        return np.asarray(audio, dtype=np.float64).copy()
    return np.asarray(audio, dtype=np.float64) * (float(target_rms) / current)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _aggregate_file_sha(root: Path, relatives: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in relatives:
        digest.update((root / relative).read_bytes())
    return digest.hexdigest()


def _write_review_pages(root: Path, scene_records: dict[str, Any]) -> None:
    """Write two static pages whose sources are package-relative only."""
    rows_timbre: list[str] = []
    rows_dynamic: list[str] = []
    labels = {
        "parent": "Parent",
        "y1_event": "Y1 事件域",
        "y2_map": "Y2 地图",
        "y3_p4": "Y3 P4",
        "y4_transients": "Y4 瞬态",
        "y5_dp": "Y5 dP",
        "monitor": "Monitor",
    }
    for scene in SCENES:
        timbre_controls = "".join(
            f'<div><span>{labels[stem]}</span><audio controls preload="metadata" src="timbre_review/{scene}/{stem}_matched.wav"></audio></div>'
            for stem in TIMBRE_STEMS
        )
        dynamic_controls = "".join(
            f'<div><span>{labels[stem]}</span><audio controls preload="metadata" src="{scene}/{stem}.wav"></audio></div>'
            for stem in STEMS
        )
        rows_timbre.append(f'<section><h2>{scene}</h2>{timbre_controls}</section>')
        rows_dynamic.append(f'<section><h2>{scene}</h2>{dynamic_controls}</section>')
    boundary = (
        "synthetic / uncalibrated / vehicle-inspired；非 OEM reproduction；"
        "R1 正式参考缺失。15% 指标只作诊断，不代表人耳 PASS 或资格通过。"
    )
    style = (
        "body{font-family:'Microsoft YaHei',system-ui,sans-serif;max-width:1100px;"
        "margin:auto;padding:24px;background:#111;color:#eee} section{border:1px solid #444;"
        "border-radius:8px;padding:12px;margin:12px 0} h1{font-size:22px} h2{font-size:16px}"
        "div{display:flex;align-items:center;gap:12px;margin:8px 0} span{width:120px;color:#9cf}"
        "audio{width:min(680px,100%)} .boundary{background:#382020;padding:12px;border-radius:6px}"
    )
    for filename, title, subtitle, rows, other in (
        (
            "timbre_review.html",
            "Timbre Review（音色试听）",
            "以下是独立的响度匹配副本；只用于相对音色判断，不用于动态或物理分析。",
            rows_timbre,
            "dynamic_review.html",
        ),
        (
            "dynamic_review.html",
            "Dynamic Review（动态试听）",
            "以下播放原始相对响度 PCM；不做逐场景峰值归一化，保留 idle→WOT 与瞬态比例。",
            rows_dynamic,
            "timbre_review.html",
        ),
    ):
        html = (
            "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{style}</style></head><body>"
            f"<h1>{title}</h1><p><a href='{other}'>{other}</a></p>"
            f"<p>{subtitle}</p><p class='boundary'>边界：{boundary}</p>"
            + "".join(rows)
            + "</body></html>"
        )
        (root / filename).write_text(html, encoding="utf-8", newline="\n")


def _fitted_config() -> dict[str, Any]:
    config = load_config("hellcat_v1")
    fitted_map, fitted_table = load_committed_fixture_timbre_map()
    config["timbre_map"] = {
        "rpm_axis": fitted_table.rpm_axis.tolist(),
        "load_axis": fitted_table.load_axis.tolist(),
        "boost_axis": fitted_table.boost_axis.tolist(),
        "order_axis": fitted_table.order_axis.tolist(),
        "values": fitted_table.values.tolist(),
    }
    config["fitted_timbre_map"] = fitted_map
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
    if root.exists():
        raise FileExistsError(f"refusing to overwrite Stage-Y package: {root}")
    if not np.isfinite(duration_s) or duration_s < 0.20:
        raise ValueError("duration_s must be finite and >= 0.20")
    root.mkdir(parents=True)
    rendered: dict[str, dict[str, np.ndarray]] = {}
    diagnostics: dict[str, dict[str, dict[str, Any]]] = {}
    durations: dict[str, float] = {}
    for scene in SCENES:
        scene_duration = 20.0 if long_window and scene == "hot_idle_20s" else float(duration_s)
        trace = build_hellcat_bakeoff_trace(scene, scene_duration)
        durations[scene] = float(trace.rpm.size * BLOCK_SIZE / SAMPLE_RATE_HZ)
        outputs: dict[str, np.ndarray] = {}
        scene_diagnostics: dict[str, dict[str, Any]] = {}
        for stem in STEMS:
            source_stem = "y5_dp" if stem == "monitor" else stem
            _raw, post, monitor, stage_diagnostics = _render_layer(source_stem, trace)
            audio = monitor if stem == "monitor" else post
            # OUTPUT_SCALE belongs here, exactly once, for every published stem.
            outputs[stem] = _safe_pcm(np.asarray(audio, dtype=np.float64) * OUTPUT_SCALE)
            consumed = list(_LAYER_CONTRACT[stem])
            scene_diagnostics[stem] = {
                "architecture": source_stem,
                "consumed_layers": consumed,
                "layer_flags": {layer: layer in consumed for layer in _LAYER_FLAG_NAMES},
                "fixed_gain_applications": 1,
                "fixed_gain_linear": float(OUTPUT_SCALE),
                "raw_dynamic": True,
                "monitor_derived_from": "y5_dp" if stem == "monitor" else None,
                "engine": stage_diagnostics,
            }
        rendered[scene] = outputs
        diagnostics[scene] = scene_diagnostics

    # Timbre review uses separate copies. Dynamic review always uses rendered PCM.
    target_rms = _safe_timbre_target(rendered)
    files: dict[str, str] = {}
    scene_records: dict[str, Any] = {}
    timbre_files: dict[str, str] = {}
    for scene in SCENES:
        scene_dir = root / scene
        scene_dir.mkdir(parents=True)
        stem_records: dict[str, Any] = {}
        for stem in STEMS:
            relative = f"{scene}/{stem}.wav"
            receipt = write_pcm24_wav(scene_dir / f"{stem}.wav", rendered[scene][stem], SAMPLE_RATE_HZ)
            files[relative] = sha256_file(scene_dir / f"{stem}.wav")
            stem_records[stem] = {
                "path": relative,
                "sha256": files[relative],
                "frames": int(receipt.metadata["frames"]),
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "channels": 2,
                "sample_width_bits": 24,
                "duration_s": durations[scene],
                **diagnostics[scene][stem],
            }
        scene_records[scene] = {
            "duration_s": durations[scene],
            "frames": int(round(durations[scene] * SAMPLE_RATE_HZ)),
            "stems": stem_records,
        }
        timbre_dir = root / "timbre_review" / scene
        timbre_dir.mkdir(parents=True)
        for stem in TIMBRE_STEMS:
            relative = f"timbre_review/{scene}/{stem}_matched.wav"
            matched = _safe_pcm(_timbre_match(rendered[scene][stem], target_rms))
            write_pcm24_wav(timbre_dir / f"{stem}_matched.wav", matched, SAMPLE_RATE_HZ)
            timbre_files[relative] = sha256_file(timbre_dir / f"{stem}_matched.wav")

    guide = (
        "# Stage Y Hellcat 分层试听\n\n"
        f"状态：`{FORMAL_STATUS}`。本包仅为 synthetic / uncalibrated / vehicle-inspired，明确不是 OEM reproduction。\n\n"
        "## Timbre Review（音色页）\n\n"
        "音色页播放 `timbre_review/` 下的独立响度匹配副本；所有副本使用一个共享 RMS proxy 目标与安全余量。RMS proxy 不是 LUFS，也不是绝对声压或标定结论。\n\n"
        "## Dynamic Review（动态页）\n\n"
        "动态页播放场景原始相对响度 PCM：不做逐场景峰值归一化、不做压缩或 AGC。按 Parent→Y1→地图→P4→瞬态→dP→Monitor 顺序听 idle→WOT、换挡、收油和回火。\n\n"
        "## 边界\n\n"
        "缺少 R1 正式参考；15% 指标仅作诊断。禁止据此宣称人耳 PASS、OEM 资格或 Approved Profile；本包不含第三方版权 PCM。\n"
    )
    (root / GUIDE_NAME).write_text(guide, encoding="utf-8", newline="\n")
    _write_review_pages(root, scene_records)
    review_files = {
        name: sha256_file(root / name)
        for name in (*REVIEW_PAGES, GUIDE_NAME)
    }
    all_artifacts = {**files, **timbre_files, **review_files}
    sha_manifest = {
        "schema": "s12.stage_y.sha256_manifest.v1",
        "files": all_artifacts,
    }
    write_json(root / SHA_MANIFEST_NAME, sha_manifest)
    manifest = {
        "schema": PACKAGE_SCHEMA,
        "vehicle_id": "hellcat",
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        "formal_status": FORMAL_STATUS,
        "status": "DIAGNOSTIC_ONLY",
        "selected_architecture": None,
        "human_review_status": "PENDING",
        "parent_sha256": _aggregate_file_sha(root, [f"{scene}/parent.wav" for scene in SCENES]),
        "candidate_sha256": _aggregate_file_sha(root, [f"{scene}/y5_dp.wav" for scene in SCENES]),
        "scenes": scene_records,
        "scene_names": list(SCENES),
        "stems": list(STEMS),
        "files": all_artifacts,
        "sha256_manifest": SHA_MANIFEST_NAME,
        "review_pages": list(REVIEW_PAGES),
        "long_window": bool(long_window),
        "duration_s": float(duration_s),
        "publication": {
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "channels": 2,
            "sample_width_bits": 24,
            "fixed_gain_linear": float(OUTPUT_SCALE),
            "fixed_gain_applications": 1,
            "fixed_gain_policy": "one fixed gain after engine/PTR; no dynamic normalization",
            "pcm_hash_domain": "published_pcm24_wav_file_bytes",
        },
        "timbre_review": {
            "files": timbre_files,
            "target_rms_proxy": float(target_rms),
            "metric": "shared stereo RMS proxy",
            "normalization": "rms_match_only_for_timbre_derivatives",
            "raw_dynamic_separate": True,
        },
        "dynamic_review": {
            "files": files,
            "normalization": "none",
            "signal_domain": "unaltered published PCM24 stems",
            "diagnostic_metric_limit_percent": 15,
        },
        "review_boundaries": {
            "r1_reference": "missing",
            "synthetic": True,
            "uncalibrated": True,
            "oem_reproduction": False,
            "human_pass": False,
            "approved_profile": False,
            "automatic_64_point_search": False,
        },
    }
    write_json(root / "package_manifest.json", manifest)
    return manifest


def _safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    if len(value) > 1 and value[0].isalpha() and value[1] == ":":
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts) and "/".join(parts) == value


def _strict_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))), None
    except Exception as exc:
        return None, f"invalid_json:{path.name}:{exc.__class__.__name__}"


def _all_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_all_finite(item) for item in value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return bool(np.isfinite(value))
    return False


def _has_affirmative_claim(manifest: dict[str, Any]) -> bool:
    boundaries = manifest.get("review_boundaries")
    if isinstance(boundaries, dict) and any(
        boundaries.get(key) is True
        for key in ("oem_reproduction", "human_pass", "approved_profile", "automatic_64_point_search")
    ):
        return True
    if manifest.get("selected_architecture") is not None:
        return True
    if manifest.get("status") in {"PASS", "Y6PASS", "QUALIFIED", "FORMAL_QUALIFIED"}:
        return True
    try:
        body = json.dumps(manifest, ensure_ascii=False, allow_nan=False).lower()
    except (TypeError, ValueError):
        return True
    return any(re.search(pattern, body) for pattern in (
        r"\by6[_ -]?pass\b",
        r"\bapproved[_ -]?profile\b\s*[:=]\s*(?:true|pass)",
        r"\boem[_ -]?reproduction\b\s*[:=]\s*(?:true|pass)",
        r"\bhuman[_ -]?pass\b\s*[:=]\s*(?:true|pass)",
        r"\bqualification[_ -]?status\b\s*[:=]\s*\"?pass\b",
    ))


def _has_affirmative_text(text: str) -> bool:
    """Reject affirmative qualification/OEM claims while allowing disclaimers."""
    body = str(text).lower()
    for pattern in (
        r"\by6[_ -]?pass\b",
        r"\bapproved[_ -]?profile\b",
        r"\boem[_ -]?reproduction\b",
        r"\bhuman[_ -]?pass\b",
        r"\bformal[_ -]?qualification\b",
    ):
        for match in re.finditer(pattern, body):
            prefix = body[max(0, match.start() - 50):match.start()]
            if not any(marker in prefix for marker in ("not", "no ", "non-", "非", "否", "不是", "禁止", "不代表", "不含", "without")):
                return True
    return False


def _expected_artifacts() -> set[str]:
    direct = {f"{scene}/{stem}.wav" for scene in SCENES for stem in STEMS}
    matched = {f"timbre_review/{scene}/{stem}_matched.wav" for scene in SCENES for stem in TIMBRE_STEMS}
    return direct | matched | set(REVIEW_PAGES) | {GUIDE_NAME}


def validate_layer_package(root: str | Path) -> list[str]:
    """Fail-closed validator for the published PCM/file contract."""
    root = Path(root)
    errors: list[str] = []
    if not root.is_dir():
        return ["package root missing"]
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json missing"]
    manifest, manifest_error = _strict_json(manifest_path)
    if manifest_error:
        return [manifest_error]
    if not isinstance(manifest, dict):
        return ["manifest_shape"]
    if not _all_finite(manifest):
        errors.append("nonfinite_manifest")
    if manifest.get("schema") != PACKAGE_SCHEMA:
        errors.append("schema")
    if manifest.get("formal_status") != FORMAL_STATUS:
        errors.append("formal_status")
    if manifest.get("status") != "DIAGNOSTIC_ONLY":
        errors.append("status")
    if manifest.get("human_review_status") != "PENDING":
        errors.append("human_review_status")
    if _has_affirmative_claim(manifest):
        errors.append("affirmative_claim")
    for relative in (GUIDE_NAME, *REVIEW_PAGES):
        text_path = root / relative
        if text_path.is_file():
            try:
                if _has_affirmative_text(text_path.read_text(encoding="utf-8")):
                    errors.append(f"affirmative_claim:{relative}")
            except Exception:
                errors.append(f"invalid_text:{relative}")
    if manifest.get("vehicle_id") != "hellcat":
        errors.append("vehicle_id")
    if tuple(manifest.get("scene_names", ())) != SCENES:
        errors.append("scene_inventory")
    if tuple(manifest.get("stems", ())) != STEMS:
        errors.append("stem_inventory")
    if manifest.get("parent_sha256") == manifest.get("candidate_sha256"):
        errors.append("parent_equals_candidate")
    if manifest.get("selected_architecture") is not None:
        errors.append("selected_architecture")

    expected_artifacts = _expected_artifacts()
    actual_artifacts = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path not in {manifest_path, root / SHA_MANIFEST_NAME}
    }
    if actual_artifacts != expected_artifacts:
        for relative in sorted(expected_artifacts - actual_artifacts):
            errors.append(f"missing:{relative}")
        for relative in sorted(actual_artifacts - expected_artifacts):
            errors.append(f"unexpected:{relative}")
    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlink:{path.relative_to(root).as_posix()}")
        if any(token in path.name.lower() for token in FORBIDDEN_NAMES):
            errors.append(f"forbidden_name:{path.name}")

    files = manifest.get("files")
    if not isinstance(files, dict):
        files = {}
        errors.append("files_shape")
    elif set(files) != expected_artifacts:
        errors.append("file_inventory")
    for relative in files:
        if not _safe_relative(relative):
            errors.append(f"unsafe_path:{relative}")
    sha_manifest_path = root / SHA_MANIFEST_NAME
    sha_manifest, sha_error = _strict_json(sha_manifest_path) if sha_manifest_path.is_file() else (None, f"missing:{SHA_MANIFEST_NAME}")
    if sha_error:
        errors.append(sha_error)
    sha_files = sha_manifest.get("files") if isinstance(sha_manifest, dict) else None
    if not isinstance(sha_files, dict) or set(sha_files) != expected_artifacts:
        errors.append("sha_file_inventory")
    if isinstance(sha_files, dict):
        for relative in sha_files:
            if not _safe_relative(relative):
                errors.append(f"unsafe_path:{relative}")

    scenes = manifest.get("scenes")
    if not isinstance(scenes, dict) or set(scenes) != set(SCENES):
        errors.append("scene_records")
        scenes = scenes if isinstance(scenes, dict) else {}
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("sample_rate_hz") != SAMPLE_RATE_HZ or publication.get("channels") != 2 or publication.get("sample_width_bits") != 24 or publication.get("fixed_gain_applications") != 1 or publication.get("pcm_hash_domain") != "published_pcm24_wav_file_bytes":
        errors.append("publication_contract")
    dynamic = manifest.get("dynamic_review")
    if not isinstance(dynamic, dict) or dynamic.get("normalization") != "none":
        errors.append("dynamic_normalization")
    timbre = manifest.get("timbre_review")
    target = timbre.get("target_rms_proxy") if isinstance(timbre, dict) else None
    if not isinstance(target, (int, float)) or not np.isfinite(target) or target <= 0.0:
        errors.append("timbre_target")

    parent_relatives: list[str] = []
    candidate_relatives: list[str] = []
    for scene in SCENES:
        entry = scenes.get(scene)
        if not isinstance(entry, dict):
            errors.append(f"scene_record:{scene}")
            continue
        scene_duration = entry.get("duration_s")
        expected_frames = entry.get("frames")
        if not isinstance(scene_duration, (int, float)) or not np.isfinite(scene_duration) or scene_duration <= 0.0:
            errors.append(f"duration:{scene}")
            scene_duration = 0.0
        stems = entry.get("stems")
        if not isinstance(stems, dict) or set(stems) != set(STEMS):
            errors.append(f"stem_records:{scene}")
            stems = stems if isinstance(stems, dict) else {}
        for stem in STEMS:
            relative = f"{scene}/{stem}.wav"
            record = stems.get(stem)
            if not isinstance(record, dict):
                errors.append(f"stem_record:{relative}")
                continue
            if record.get("path") != relative or record.get("sha256") != files.get(relative) or record.get("fixed_gain_applications") != 1:
                errors.append(f"stem_metadata:{relative}")
            if tuple(record.get("consumed_layers", ())) != _LAYER_CONTRACT[stem]:
                errors.append(f"layer_contract:{relative}")
            if stem == "monitor" and record.get("monitor_derived_from") != "y5_dp":
                errors.append(f"monitor_derivation:{scene}")
            wav_path = root / relative
            if not _safe_relative(relative) or not wav_path.is_file():
                errors.append(f"missing:{relative}")
                continue
            try:
                audio, metadata = read_pcm24_wav(wav_path)
                if metadata["frames"] <= 0 or metadata["channels"] != 2 or metadata["sample_width_bits"] != 24 or metadata["sample_rate_hz"] != SAMPLE_RATE_HZ or metadata["clipping"] != 0:
                    errors.append(f"wav_contract:{relative}")
                if expected_frames != metadata["frames"] or metadata["frames"] != int(round(float(scene_duration) * SAMPLE_RATE_HZ)):
                    errors.append(f"duration:{relative}")
                if not np.all(np.isfinite(audio)):
                    errors.append(f"nonfinite_wav:{relative}")
            except Exception as exc:
                errors.append(f"invalid_wav:{relative}:{exc.__class__.__name__}")
            actual_sha = sha256_file(wav_path)
            if actual_sha != files.get(relative) or actual_sha != (sha_files or {}).get(relative) or actual_sha != record.get("sha256"):
                errors.append(f"sha_mismatch:{relative}")
            if stem == "parent":
                parent_relatives.append(relative)
            if stem == "y5_dp":
                candidate_relatives.append(relative)
        # A matched derivative must be a separate file, with the same shape contract.
        for stem in TIMBRE_STEMS:
            relative = f"timbre_review/{scene}/{stem}_matched.wav"
            wav_path = root / relative
            if not wav_path.is_file():
                errors.append(f"missing:{relative}")
                continue
            try:
                audio, metadata = read_pcm24_wav(wav_path)
                if metadata["frames"] <= 0 or metadata["channels"] != 2 or metadata["sample_width_bits"] != 24 or metadata["sample_rate_hz"] != SAMPLE_RATE_HZ or metadata["frames"] != int(round(float(scene_duration) * SAMPLE_RATE_HZ)):
                    errors.append(f"timbre_wav_contract:{relative}")
                if target is not None and not _approx_equal(_rms(audio), float(target), 5.0e-4):
                    errors.append(f"timbre_target:{relative}")
            except Exception as exc:
                errors.append(f"invalid_wav:{relative}:{exc.__class__.__name__}")
            actual_sha = sha256_file(wav_path)
            if actual_sha != files.get(relative) or actual_sha != (sha_files or {}).get(relative):
                errors.append(f"sha_mismatch:{relative}")

    if parent_relatives and candidate_relatives:
        parent_sha = _aggregate_file_sha(root, parent_relatives)
        candidate_sha = _aggregate_file_sha(root, candidate_relatives)
        if parent_sha != manifest.get("parent_sha256"):
            errors.append("parent_sha256")
        if candidate_sha != manifest.get("candidate_sha256"):
            errors.append("candidate_sha256")
        for scene in SCENES:
            parent_path = root / scene / "parent.wav"
            candidate_path = root / scene / "y5_dp.wav"
            if parent_path.is_file() and candidate_path.is_file():
                try:
                    parent_audio, _ = read_pcm24_wav(parent_path)
                    candidate_audio, _ = read_pcm24_wav(candidate_path)
                    if parent_audio.shape != candidate_audio.shape or np.array_equal(parent_audio, candidate_audio):
                        errors.append(f"rebound_identical:{scene}")
                except Exception:
                    pass
    if isinstance(sha_manifest, dict) and sha_manifest.get("schema") != "s12.stage_y.sha256_manifest.v1":
        errors.append("sha_schema")
    return sorted(set(errors))


def _approx_equal(value: float, target: float, tolerance: float) -> bool:
    """Small local comparator keeps the validator independent of pytest."""
    return abs(float(value) - float(target)) <= float(tolerance)
