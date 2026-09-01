"""Stage Z v2 audition package built from the current main renderer."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from ..stage_v.io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from ..stage_w.click_contract import block_boundary_click_metrics
from ..stage_x.multi_reference_comparator import raw_dynamic_metrics, timbre_metrics
from .method_ablation import (
    METHOD_CATALOG,
    build_method_adoption_matrix,
    build_teacher_vs_reduced_response,
    render_final_scene,
    render_parent_scene,
    score_ablation,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
PACKAGE_SCHEMA = "s12.stage_z.audition_package.v2"
SAMPLE_RATE_HZ = 48000
SCENES = (
    "hot_idle_20s",
    "steady_1200rpm",
    "steady_2000rpm",
    "steady_3000rpm",
    "throttle_tip_in",
    "full_load_acceleration",
    "gear_shift",
    "high_rpm_lift",
    "afterfire_eligible",
    "idle_return",
    "complete_cycle",
)
REVIEW_PAGES = ("overall_review.html", "method_ablation_review.html", "answers_manifest.html")
SCOPE = "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"
FORBIDDEN_NAMES = ("gta", "fivem", "gtav", "five_m", ".mr", "recording", "preset", "asset")


def _sha_bytes(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()


def _aggregate(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _duration(scene: str, duration_s: float, hot_idle_duration_s: float | None) -> float:
    if hot_idle_duration_s is not None and scene == "hot_idle_20s":
        return float(hot_idle_duration_s)
    return float(duration_s)


def _finite_metrics(audio: np.ndarray) -> dict[str, float]:
    dynamic = raw_dynamic_metrics(audio, SAMPLE_RATE_HZ)
    timbre = timbre_metrics(np.mean(audio, axis=1), SAMPLE_RATE_HZ)
    return {
        "rms_dbfs": float(dynamic["rms_dbfs"]),
        "peak_dbfs": float(dynamic["peak_dbfs"]),
        "crest_db": float(dynamic["crest_db"]),
        "dynamic_range_db": float(dynamic["dynamic_range_db"]),
        "transient_event_density_per_s": float(dynamic["transient_event_density_per_s"]),
        "spectral_centroid_hz": float(timbre["spectral_centroid_hz"]),
        "spectral_flux": float(timbre["spectral_flux"]),
        "roughness_proxy": float(timbre["roughness_proxy"]),
        "sharpness_proxy": float(timbre["sharpness_proxy"]),
        "tonality_proxy": float(timbre["tonality_proxy"]),
        "persistent_tone_ratio": float(timbre["persistent_tone_ratio"]),
    }


def _relative_delta(after: float, before: float) -> float:
    return float(after - before)


def _objective_before_after(parent_by_scene: dict[str, np.ndarray], final_by_scene: dict[str, np.ndarray]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    metric_names = tuple(_finite_metrics(next(iter(parent_by_scene.values()))))
    for scene in SCENES:
        parent = _finite_metrics(parent_by_scene[scene])
        final = _finite_metrics(final_by_scene[scene])
        rows[scene] = {
            "parent": parent,
            "final": final,
            "delta": {name: _relative_delta(final[name], parent[name]) for name in metric_names},
            "analysis_domain": "published_pcm24_reopened; no R1 reference fit",
            "diagnostic_only": True,
        }
    aggregate = {}
    for name in metric_names:
        parent_values = [rows[scene]["parent"][name] for scene in SCENES]
        final_values = [rows[scene]["final"][name] for scene in SCENES]
        aggregate[name] = {
            "parent": float(np.mean(parent_values)),
            "final": float(np.mean(final_values)),
            "delta": float(np.mean(final_values) - np.mean(parent_values)),
        }
    return {
        "schema": "s12.stage_z.objective_before_after.v1",
        "comparison": "Legacy Parent vs current Stage Y Final main",
        "reference_status": "R1_MISSING_DIAGNOSTIC_ONLY",
        "metric_provenance": "Stage-X raw_dynamic_metrics and timbre_metrics",
        "metric_names": list(metric_names),
        "scenes": rows,
        "aggregate": aggregate,
        "diagnostic_only": True,
        "oem_or_profile_claim": False,
    }


def _page_audio(path: str, label: str) -> str:
    return f"<div><span>{html.escape(label)}</span><audio controls preload='metadata' src='{html.escape(path)}'></audio></div>"


def _write_pages(root: Path, overall: list[dict[str, Any]], ablations: list[dict[str, Any]]) -> None:
    style = (
        "body{font-family:'Microsoft YaHei',system-ui,sans-serif;max-width:1150px;margin:auto;"
        "padding:24px;background:#111;color:#eee}section{border:1px solid #444;border-radius:8px;"
        "padding:12px;margin:12px 0}h1{font-size:24px}h2{font-size:17px}div{display:flex;"
        "align-items:center;gap:12px;margin:8px 0}span{width:180px;color:#9cf}audio{width:min(760px,100%)}"
        ".boundary{background:#382020;padding:12px;border-radius:6px}.note{background:#202d38;"
        "padding:12px;border-radius:6px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #555;padding:6px;text-align:left}"
    )
    boundary = "边界：synthetic / uncalibrated / vehicle-inspired；非 OEM reproduction；R1 缺失。"
    overall_sections = []
    for item in overall:
        scene = html.escape(item["scene"])
        overall_sections.append(
            f"<section><h2>{scene}</h2>"
            + _page_audio(item["parent_path"], "Parent")
            + _page_audio(item["final_raw_path"], "Stage Y Final Raw")
            + _page_audio(item["final_monitor_path"], "Stage Y Final Monitor")
            + "</section>"
        )
    overall_html = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>Stage Z 整体试听</title>"
        f"<style>{style}</style></head><body><h1>Stage Z：Parent → Final main</h1>"
        "<p><a href='method_ablation_review.html'>开源方法 A/B</a> · <a href='answers_manifest.html'>答案页</a></p>"
        f"<p class='boundary'>{boundary}</p><p class='note'>以下只呈现当前 main 重新渲染的三路声音；objective 数值在包内 JSON，不能替代人耳判断。</p>"
        + "".join(overall_sections)
        + "</body></html>"
    )
    (root / "overall_review.html").write_text(overall_html, encoding="utf-8", newline="\n")

    ablation_sections = []
    for item in ablations:
        ablation_sections.append(
            f"<section><h2>{html.escape(item['blind_id'])} · {html.escape(item['scene'])}</h2>"
            + _page_audio(item["a_path"], "A")
            + _page_audio(item["b_path"], "B")
            + "</section>"
        )
    method_html = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>Stage Z 方法 A/B</title>"
        f"<style>{style}</style></head><body><h1>Stage Z：开源方法盲化 A/B</h1>"
        "<p><a href='overall_review.html'>整体试听</a> · <a href='answers_manifest.html'>答案页</a></p>"
        f"<p class='boundary'>{boundary}</p><p class='note'>每组只显示 A/B，方法名称与内部方向在独立答案页；A/B 没有“应当更好”的预设结论。</p>"
        + "".join(ablation_sections)
        + "</body></html>"
    )
    (root / "method_ablation_review.html").write_text(method_html, encoding="utf-8", newline="\n")

    rows = "".join(
        f"<tr><td>{html.escape(item['blind_id'])}</td><td>{html.escape(item['method_id'])}</td>"
        f"<td>{html.escape(item['source_id'])}</td><td>{html.escape(item['scene'])}</td>"
        f"<td>A=OFF</td><td>B=ON</td></tr>"
        for item in ablations
    )
    answer_html = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>Stage Z 答案页</title>"
        f"<style>{style}</style></head><body><h1>Stage Z：A/B 答案与机器收据</h1>"
        f"<p class='boundary'>{boundary}</p><p>本页仅用于审阅后揭盲；试听页默认不显示方法语义。</p>"
        "<table><thead><tr><th>盲号</th><th>method_id</th><th>source</th><th>scene</th><th>A</th><th>B</th></tr></thead>"
        f"<tbody>{rows}</tbody></table><p>详细 PCM SHA、指标、guard 和状态见 method_ablation_scorecard.json。</p></body></html>"
    )
    (root / "answers_manifest.html").write_text(answer_html, encoding="utf-8", newline="\n")


def build_stage_z_package(root: str | Path, *, duration_s: float = 8.0, hot_idle_duration_s: float | None = 20.0) -> dict[str, Any]:
    root = Path(root)
    if root.exists():
        raise FileExistsError(f"refusing to overwrite Stage-Z v2 package: {root}")
    if not np.isfinite(duration_s) or duration_s < 0.20:
        raise ValueError("duration_s must be finite and >= 0.20")
    if hot_idle_duration_s is not None and (not np.isfinite(hot_idle_duration_s) or hot_idle_duration_s < 0.20):
        raise ValueError("hot_idle_duration_s must be finite and >= 0.20")
    root.mkdir(parents=True)
    tested_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    files: dict[str, str] = {}
    overall: list[dict[str, Any]] = []
    parent_by_scene: dict[str, np.ndarray] = {}
    final_by_scene: dict[str, np.ndarray] = {}
    for scene in SCENES:
        scene_duration = _duration(scene, duration_s, hot_idle_duration_s)
        parent, _parent_post, parent_monitor = render_parent_scene(scene, scene_duration)
        _raw, final_raw, final_monitor, final_diag, elapsed, memory = render_final_scene(scene, scene_duration)
        paths = {
            "parent_path": f"overall/{scene}/parent.wav",
            "final_raw_path": f"overall/{scene}/final_raw.wav",
            "final_monitor_path": f"overall/{scene}/final_monitor.wav",
        }
        for key, audio in (("parent_path", parent), ("final_raw_path", final_raw), ("final_monitor_path", final_monitor)):
            path = root / paths[key]
            path.parent.mkdir(parents=True, exist_ok=True)
            receipt = write_pcm24_wav(path, audio, SAMPLE_RATE_HZ)
            reopened, metadata = read_pcm24_wav(path)
            if reopened.shape != audio.shape or metadata["clipping"] != 0:
                raise ValueError(f"v2 WAV reopen/clipping failed: {paths[key]}")
            files[paths[key]] = receipt.sha256
        parent_by_scene[scene] = parent
        final_by_scene[scene] = final_raw
        overall.append({
            "scene": scene,
            "duration_s": scene_duration,
            **paths,
            "parent_sha256": files[paths["parent_path"]],
            "final_raw_sha256": files[paths["final_raw_path"]],
            "final_monitor_sha256": files[paths["final_monitor_path"]],
            "final_diagnostics": {"render_seconds": elapsed, "peak_python_allocation_bytes": memory, "architecture": final_diag.get("architecture")},
        })

    objective = _objective_before_after(parent_by_scene, final_by_scene)
    write_json(root / "objective_before_after.json", objective)
    files["objective_before_after.json"] = sha256_file(root / "objective_before_after.json")

    ablations: list[dict[str, Any]] = []
    scorecard: list[dict[str, Any]] = []
    blind_index = 0
    for spec in METHOD_CATALOG:
        scene = spec.get("ablation_scenario")
        if not scene:
            continue
        blind_index += 1
        method_id = spec["method_id"]
        ablation_duration = min(4.0, _duration(scene, duration_s, hot_idle_duration_s))
        score, result = score_ablation(method_id, scene, ablation_duration)
        blind_id = f"ablation_{blind_index:02d}"
        a_path = f"ablation_review/{blind_id}/A.wav"
        b_path = f"ablation_review/{blind_id}/B.wav"
        for relative, audio in ((a_path, result.off_pcm), (b_path, result.on_pcm)):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            receipt = write_pcm24_wav(path, audio, SAMPLE_RATE_HZ)
            reopened, metadata = read_pcm24_wav(path)
            if reopened.shape != audio.shape or metadata["clipping"] != 0:
                raise ValueError(f"ablation WAV reopen/clipping failed: {relative}")
            files[relative] = receipt.sha256
        score = {**score, "source_id": spec["source_id"], "blind_id": blind_id, "ablation_duration_s": ablation_duration, "a_path": a_path, "b_path": b_path}
        scorecard.append(score)
        ablations.append({"blind_id": blind_id, "method_id": method_id, "source_id": spec["source_id"], "scene": scene, "a_path": a_path, "b_path": b_path})
    write_json(root / "method_ablation_scorecard.json", {"schema": "s12.stage_z.method_ablation_scorecard.v1", "status": "DIAGNOSTIC_ONLY", "rows": scorecard, "scope": SCOPE})
    files["method_ablation_scorecard.json"] = sha256_file(root / "method_ablation_scorecard.json")

    adoption = {"schema": "s12.stage_z.method_adoption_matrix.v2", "generated_from": "source_registry.json + source_coverage_matrix.json", "main_head": tested_head, "rows": build_method_adoption_matrix(), "scope": SCOPE}
    write_json(root / "method_adoption_matrix_v2.json", adoption)
    files["method_adoption_matrix_v2.json"] = sha256_file(root / "method_adoption_matrix_v2.json")
    teacher = build_teacher_vs_reduced_response()
    write_json(root / "teacher_vs_reduced_response.json", teacher)
    files["teacher_vs_reduced_response.json"] = sha256_file(root / "teacher_vs_reduced_response.json")

    guide = (
        "# Stage Z Hellcat v2 中文试听\n\n"
        "本包从当前 main 重新渲染，不复制 Stage Y v1。整体页先听 Parent、Final Raw、Final Monitor；方法页默认只显示 A/B，答案在独立答案页。\n\n"
        "## 场景\n\n"
        "hot idle 20 s、1200/2000/3000 rpm 稳态、tip-in、全油加速、换挡、高转收油、合格回火、怠速回落和完整周期。\n\n"
        "## 证据边界\n\n"
        "所有文件为 synthetic / uncalibrated / vehicle-inspired。objective、SHA 和 OFF/ON movement 是工程诊断，不等于人耳偏好、R1、OEM 或 Profile Freeze。包内不含第三方代码、音频、预设、权重或运行时。\n"
    )
    (root / "AUDITION_GUIDE_ZH.md").write_text(guide, encoding="utf-8", newline="\n")
    files["AUDITION_GUIDE_ZH.md"] = sha256_file(root / "AUDITION_GUIDE_ZH.md")
    _write_pages(root, overall, ablations)
    for page in REVIEW_PAGES:
        files[page] = sha256_file(root / page)

    parent_paths = [root / item["parent_path"] for item in overall]
    final_paths = [root / item["final_raw_path"] for item in overall]
    manifest = {
        "schema": PACKAGE_SCHEMA,
        "status": "DIAGNOSTIC_ONLY",
        "scope": SCOPE,
        "vehicle_id": "hellcat",
        "main_head": tested_head,
        "tested_head": tested_head,
        "scene_names": list(SCENES),
        "overall_views": overall,
        "method_ablation_views": ablations,
        "parent_sha256": _aggregate(parent_paths),
        "final_raw_sha256": _aggregate(final_paths),
        "review_pages": list(REVIEW_PAGES),
        "guide": "AUDITION_GUIDE_ZH.md",
        "objective": "objective_before_after.json",
        "method_ablation_scorecard": "method_ablation_scorecard.json",
        "method_adoption_matrix": "method_adoption_matrix_v2.json",
        "teacher_vs_reduced": "teacher_vs_reduced_response.json",
        "files": files,
        "review_boundaries": {
            "human_audition": "PENDING",
            "r1_reference": "MISSING",
            "oem_reproduction": False,
            "profile_freeze": False,
            "copied_source_code": False,
            "copied_audio_asset": False,
            "copied_model_weight": False,
            "ptr_radiation_track_p": "UNCHANGED",
        },
    }
    write_json(root / "package_manifest.json", manifest)
    write_json(root / "sha256_manifest.json", {"schema": "s12.stage_z.sha256_manifest.v1", "files": files})
    return manifest


def validate_stage_z_package(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "package_manifest.json"
    if not root.is_dir() or not manifest_path.is_file():
        return ["package_manifest.json missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid_manifest:{exc.__class__.__name__}"]
    if manifest.get("schema") != PACKAGE_SCHEMA:
        errors.append("schema")
    if manifest.get("scope") != SCOPE or manifest.get("status") != "DIAGNOSTIC_ONLY":
        errors.append("boundary")
    if manifest.get("main_head") != manifest.get("tested_head"):
        errors.append("head_binding")
    if manifest.get("review_boundaries", {}).get("copied_source_code") is not False or manifest.get("review_boundaries", {}).get("copied_audio_asset") is not False or manifest.get("review_boundaries", {}).get("copied_model_weight") is not False:
        errors.append("copy_boundary")
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    for relative, expected in files.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing:{relative}")
            continue
        if "\\" in relative or relative.startswith("/") or ".." in Path(relative).parts:
            errors.append(f"unsafe_path:{relative}")
        if sha256_file(path) != expected:
            errors.append(f"sha:{relative}")
    for path in root.rglob("*"):
        if path.is_file() and any(token in path.name.lower() for token in FORBIDDEN_NAMES):
            errors.append(f"forbidden_name:{path.name}")
    for page in REVIEW_PAGES:
        text = (root / page).read_text(encoding="utf-8") if (root / page).is_file() else ""
        if page == "overall_review.html" and not all(label in text for label in ("Parent", "Stage Y Final Raw", "Stage Y Final Monitor")):
            errors.append("overall_page_labels")
        if page == "method_ablation_review.html" and ("method_id" in text or "OFF" in text or "ON" in text):
            errors.append("ablation_page_not_blinded")
        if "E:/" in text or "E:\\" in text:
            errors.append(f"absolute_path:{page}")
    adoption_path = root / "method_adoption_matrix_v2.json"
    try:
        adoption = json.loads(adoption_path.read_text(encoding="utf-8"))
        registry = json.loads((REPO_ROOT / "docs/research/engine-audio-ecosystem/source_registry.json").read_text(encoding="utf-8"))
        if {row["source_id"] for row in adoption["rows"]} != {row["id"] for row in registry["sources"]}:
            errors.append("adoption_registry_ids")
    except Exception as exc:
        errors.append(f"adoption_json:{exc.__class__.__name__}")
    score_path = root / "method_ablation_scorecard.json"
    try:
        score = json.loads(score_path.read_text(encoding="utf-8"))
        for row in score["rows"]:
            if row["off_pcm_sha"] == row["on_pcm_sha"]:
                errors.append(f"ablation_sha:{row['method_id']}")
            if row["regression"]:
                errors.append(f"ablation_regression:{row['method_id']}")
            if row["global_gain_changed"] is not False:
                errors.append(f"ablation_gain:{row['method_id']}")
    except Exception as exc:
        errors.append(f"scorecard_json:{exc.__class__.__name__}")
    return errors


__all__ = ["build_stage_z_package", "validate_stage_z_package"]
