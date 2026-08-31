"""Stage X guided review package builder (Chinese audition UI).

Per scenario: A Reference / B Legacy / C P2H / D P3 / E P5 / F Preselection
raw / G Preselection monitor, plus loudness-matched timbre variants. Two
pages (Timbre Review / Dynamic Review), a deterministic blind A/B pair, a
Chinese feedback CSV template, and a fail-closed package validator.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..stage_v.io import read_pcm24_wav, sha256_file, write_json, write_pcm24_wav
from .reference_caseset import load_case_segment_audio

PACKAGE_SCHEMA = "s12.stage_x.review_package.v1"
SCENARIOS = (
    ("hot_idle", "hot_idle_20s", 6.0),
    ("steady_low", "steady_1200rpm", 4.0),
    ("steady_mid", "steady_2000rpm", 4.0),
    ("steady_high", "steady_3000rpm", 4.0),
    ("tip_in", "throttle_tip_in", 4.0),
    ("full_pull", "full_load_acceleration", 5.0),
    ("shift", "gear_shift", 4.0),
    ("lift", "high_rpm_lift", 4.0),
    ("afterfire", "afterfire_eligible", 4.0),
    ("idle_return", "idle_return", 4.0),
)
CANDIDATE_STEMS = ("legacy", "p2h", "p3", "p5", "presel_raw", "presel_monitor")
TIMBRE_MATCHED = ("legacy", "p2h", "p3", "p5", "presel_raw")
BOUNDARY_TEXT = "R2/R3 仅工程诊断；正式资格仍缺 R1（FORMAL_R1_REFERENCE_MISSING）；本包为 synthetic / uncalibrated / 非 OEM 复刻。"


def _loudness_match(candidate: np.ndarray, reference: np.ndarray) -> np.ndarray:
    ref_rms = float(np.sqrt(np.mean(np.square(reference.mean(axis=1))))) if reference.size else 0.0
    cand_rms = float(np.sqrt(np.mean(np.square(candidate.mean(axis=1))))) if candidate.size else 0.0
    if cand_rms <= 1e-9 or ref_rms <= 0.0:
        return candidate
    return np.clip(candidate * (ref_rms / cand_rms), -0.999999, 0.999999)


def _render_candidate(config: dict[str, Any] | None, architecture: str, scene: str, duration_s: float):
    from .candidate_search import _render_pcm

    trace_scene = scene
    return _render_pcm(config, architecture, trace_scene, duration_s)


def build_review_package(
    output_root: Path,
    caseset: dict[str, Any],
    preselection: dict[str, Any],
    *,
    vehicle_id: str = "hellcat",
) -> dict[str, Any]:
    """Render the full guided package; fail closed on any clip or empty audio."""
    from ..event_domain.config_schema import load_config

    output_root.mkdir(parents=True, exist_ok=True)
    best_architecture = preselection.get("selected_engineering_architecture")
    best_overrides = None
    if best_architecture:
        gate = preselection["preselections"][best_architecture]
        best_overrides = gate.get("best_overrides")
    base_config = load_config("hellcat_v1")
    presel_config = None
    if best_architecture and best_overrides:
        from .search_parameters import apply_parameters, hellcat_search_parameters

        presel_config = apply_parameters(base_config, best_overrides, hellcat_search_parameters())
    manifest: dict[str, Any] = {"schema": PACKAGE_SCHEMA, "vehicle_id": vehicle_id, "selected_engineering_architecture": best_architecture, "scenarios": {}, "boundary": BOUNDARY_TEXT, "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction"}
    reference_by_scenario = {case["scenario"]: case for case in caseset["cases"] if case["status"] == "BOUND"}
    rng = np.random.default_rng(20260829)
    blind_order: dict[str, dict[str, str]] = {}
    for scenario, bakeoff_scene, duration_s in SCENARIOS:
        scene_dir = output_root / scenario
        scene_dir.mkdir(exist_ok=True)
        stems: dict[str, np.ndarray] = {}
        if scenario in reference_by_scenario:
            reference_audio, _ = load_case_segment_audio(reference_by_scenario[scenario])
            stereo = np.column_stack([reference_audio, reference_audio])
            peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
            if peak > 0.999:
                stereo = stereo * (0.99 / peak)
            stems["reference"] = stereo
        for architecture, stem in (("P1", "legacy"), ("P2H", "p2h"), ("P3", "p3"), ("P5", "p5")):
            _, post, _, _, _ = _render_candidate(None, architecture, bakeoff_scene, duration_s)
            stems[stem] = post
        if presel_config is not None and best_architecture:
            raw, post, monitor, _, _ = _render_candidate(presel_config, best_architecture, bakeoff_scene, duration_s)
            stems["presel_raw"] = post
            stems["presel_monitor"] = monitor
        else:
            stems["presel_raw"] = stems.get("p3", stems["legacy"])
            stems["presel_monitor"] = stems.get("p3", stems["legacy"])
        files: dict[str, str] = {}
        metrics: dict[str, Any] = {}
        for stem, audio in stems.items():
            peak = float(np.max(np.abs(audio)))
            if peak >= 1.0:
                raise ValueError(f"{scenario}/{stem} clips at {peak}")
            receipt = write_pcm24_wav(scene_dir / f"{stem}.wav", audio, 48000)
            files[stem] = receipt.sha256
            metrics[stem] = {"peak": peak, "rms": float(np.sqrt(np.mean(np.square(audio.mean(axis=1)))))}
        if "reference" in stems:
            for stem in TIMBRE_MATCHED:
                if stem in stems:
                    matched = _loudness_match(stems[stem], stems["reference"])
                    peak = float(np.max(np.abs(matched)))
                    if peak >= 1.0:
                        matched = matched * (0.999 / peak)
                    receipt = write_pcm24_wav(scene_dir / f"{stem}_matched.wav", matched, 48000)
                    files[f"{stem}_matched"] = receipt.sha256
        if files.get("legacy") == files.get("presel_raw"):
            raise ValueError(f"{scenario}: parent and preselection PCM identical")
        first_is_preselection = bool(rng.integers(0, 2))
        blind_order[scenario] = {"X": "presel_raw" if first_is_preselection else "legacy", "Y": "legacy" if first_is_preselection else "presel_raw"}
        manifest["scenarios"][scenario] = {
            "bakeoff_scene": bakeoff_scene,
            "duration_s": duration_s,
            "reference_bound": "reference" in stems,
            "reference_id": reference_by_scenario[scenario]["reference_id"] if scenario in reference_by_scenario else None,
            "files": files,
            "metrics": metrics,
        }
    manifest["blind_order"] = blind_order
    write_json(output_root / "answer_key.json", {"blind_order": blind_order, "warning": "试听完成并提交反馈前请勿打开此文件"})
    _write_index_html(output_root, manifest, blind_order)
    _write_feedback_csv(output_root)
    _write_readme(output_root, manifest)
    all_files = {path.relative_to(output_root).as_posix(): sha256_file(path) for path in sorted(output_root.rglob("*")) if path.is_file() and path.name not in {"package_manifest.json"}}
    manifest["files"] = all_files
    write_json(output_root / "package_manifest.json", manifest)
    return manifest


def _write_index_html(root: Path, manifest: dict[str, Any], blind_order: dict[str, dict[str, str]]) -> None:
    scenarios = list(manifest["scenarios"].keys())
    rows = []
    for scenario in scenarios:
        entry = manifest["scenarios"][scenario]
        ref_cell = '<button class="play" data-src="reference.wav">A 参考 Reference</button>' if entry["reference_bound"] else '<span class="missing">参考不可用（SCENARIO_REFERENCE_UNAVAILABLE）</span>'
        timbre_cells = "".join(
            f'<button class="play" data-src="{stem}_matched.wav">{label}</button>'
            for stem, label in (("legacy", "B Legacy"), ("p2h", "C P2H"), ("p3", "D P3"), ("p5", "E P5"), ("presel_raw", "F 预选(匹配)"))
            if f"{stem}_matched" in entry["files"]
        )
        dynamic_cells = "".join(
            f'<button class="play" data-src="{stem}.wav">{label}</button>'
            for stem, label in (("legacy", "B Legacy"), ("p2h", "C P2H"), ("p3", "D P3"), ("p5", "E P5"), ("presel_raw", "F 预选 Raw"), ("presel_monitor", "G 预选 Monitor"))
            if stem in entry["files"]
        )
        rows.append(f"""
<section class="scenario" id="{scenario}">
  <h3>{scenario}</h3>
  <div class="row"><span class="tag">音色对比（响度已匹配）</span>{ref_cell}{timbre_cells}</div>
  <div class="row"><span class="tag">动态对比（保留原始响度）</span>{dynamic_cells}</div>
  <div class="row"><span class="tag">盲听 A/B</span>
    <button class="play" data-src="{blind_order[scenario]['X']}.wav">X</button>
    <button class="play" data-src="{blind_order[scenario]['Y']}.wav">Y</button>
    <span class="note">X/Y 顺序已随机；请在反馈 CSV 中填写更像参考的一方</span>
  </div>
</section>""")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>S12 Stage X 工程预选试听包 — {manifest['vehicle_id']}</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;max-width:960px;margin:0 auto;padding:24px;background:#111;color:#eee}}
h1{{font-size:20px}} h3{{font-size:15px;margin:12px 0 6px}}
.boundary{{background:#3a1f1f;border:1px solid #a33;padding:10px;border-radius:6px;font-size:13px}}
.page{{margin:16px 0}} .tabs button{{margin-right:8px;padding:6px 14px}}
.scenario{{border:1px solid #333;border-radius:8px;padding:10px;margin:10px 0}}
.row{{margin:6px 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.play{{padding:6px 12px;background:#245;border:none;color:#fff;border-radius:5px;cursor:pointer}}
.play:disabled{{background:#333;color:#777}}
.play.now{{background:#394}}
.tag{{color:#9cf;font-size:12px;min-width:170px}}
.missing{{color:#c66;font-size:12px}} .note{{color:#888;font-size:12px}}
</style>
</head>
<body>
<h1>S12 Stage X R2 工程预选试听包（{manifest['vehicle_id']}）</h1>
<div class="boundary">边界声明：{BOUNDARY_TEXT} 预选架构：{manifest.get('selected_engineering_architecture') or '无候选通过（NO_R2_ENGINEERING_CANDIDATE_IMPROVED）'}。</div>
<div class="page">
  <h2>使用说明</h2>
  <p>第一页“音色对比”所有候选已做响度匹配（RMS 对齐参考），用于判断车型音色；第二页“动态对比”保留原始相对响度，用于判断怠速可听度、加速音量、收油与回火。软件诊断结论先展示在 CSV 模板中，请以实际听感验证。</p>
  <p>每段音频需待按钮由“加载中”变为可点击（canplaythrough）后再播放。盲听 X/Y 顺序已随机，答案在 answer_key.json（请先听后看）。</p>
</div>
{''.join(rows)}
<div class="page"><h2>反馈提交</h2><p>请填写 feedback_template.csv：哪一个更像参考 / 车型身份 0-100 / 真实感 0-100 / 怠速生命感 / 低频压力 / 机械与增压音色 / 回火自然度 / 合成器伪影 / 备注。</p></div>
<audio id="player" preload="auto"></audio>
<script>
const player=document.getElementById('player');
document.querySelectorAll('.play').forEach(btn=>{{
  btn.disabled=true;btn.textContent+='…';
  const probe=new Audio(btn.dataset.src);
  probe.addEventListener('canplaythrough',()=>{{btn.disabled=false;btn.textContent=btn.textContent.replace('…','');}});
  probe.load();
  btn.addEventListener('click',()=>{{
    document.querySelectorAll('.play.now').forEach(b=>b.classList.remove('now'));
    player.src=btn.dataset.src;player.play();btn.classList.add('now');
  }});
}});
</script>
</body>
</html>"""
    (root / "index.html").write_text(html, encoding="utf-8", newline="\n")


def _write_feedback_csv(root: Path) -> None:
    header = "scenario,更像参考的一方(X/Y/无法判断),车型身份_0_100,真实感_0_100,怠速生命感,低频压力,机械与增压音色,回火自然度,合成器伪影,备注\n"
    rows = "".join(f"{scenario},,,,,,,,,\n" for scenario, _, _ in SCENARIOS)
    (root / "feedback_template.csv").write_text(
        "# S12 Stage X 工程预选反馈（Jovi）\n# 请在试听完成后填写；本包为 R2/R3 工程诊断，不是正式资格评审\n" + header + rows,
        encoding="utf-8-sig",
        newline="\n",
    )


def _write_readme(root: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# S12 Stage X R2 工程预选试听包",
        "",
        f"- 车辆：{manifest['vehicle_id']}",
        f"- 预选架构：{manifest.get('selected_engineering_architecture') or '无候选通过'}",
        f"- 场景数：{len(manifest['scenarios'])}",
        f"- 有参考场景：{sum(1 for entry in manifest['scenarios'].values() if entry['reference_bound'])}",
        "",
        "## 边界",
        f"- {BOUNDARY_TEXT}",
        "- 无 Human PASS、无 Approved Profile、无 OEM 复刻、无标定声明。",
        "- 参考音频为第三方 R2 录音，仅用于相对音色/动态诊断。",
        "",
        "## 文件",
        "- index.html：试听界面（音色页 / 动态页 / 盲听 X-Y）",
        "- feedback_template.csv：反馈模板",
        "- package_manifest.json：全部文件 SHA 与场景指标",
        "- answer_key.json：盲听答案（请最后再打开）",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def validate_review_package(root: str | Path) -> list[str]:
    """Fail-closed package gate: files, SHA, duration, boundaries, blind pair."""
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != PACKAGE_SCHEMA:
        errors.append("schema mismatch")
    for relative, expected in manifest.get("files", {}).items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing file: {relative}")
            continue
        if sha256_file(path) != expected:
            errors.append(f"sha mismatch: {relative}")
    for scenario, entry in manifest.get("scenarios", {}).items():
        for stem in ("legacy", "presel_raw"):
            if stem not in entry["files"]:
                errors.append(f"{scenario}: missing {stem}")
        if entry["files"].get("legacy") == entry["files"].get("presel_raw"):
            errors.append(f"{scenario}: parent and preselection identical")
        if not entry.get("reference_bound"):
            continue
        ref = root / scenario / "reference.wav"
        if ref.is_file():
            audio, meta = read_pcm24_wav(ref)
            if audio.shape[0] / meta.get("sample_rate", 48000) <= 0:
                errors.append(f"{scenario}: reference duration <= 0")
    if "R2" not in manifest.get("boundary", "") or "R1" not in manifest.get("boundary", ""):
        errors.append("R2/R3/R1 boundary not displayed")
    if not (root / "feedback_template.csv").is_file():
        errors.append("feedback template missing")
    if not (root / "answer_key.json").is_file():
        errors.append("answer key missing")
    return errors


__all__ = ["PACKAGE_SCHEMA", "SCENARIOS", "build_review_package", "validate_review_package"]
