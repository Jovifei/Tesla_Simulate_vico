"""Build an immutable A/B/C audition package from existing governed assets.

A is the original algorithm, B is a separately identified feedback candidate,
and C is the real recording. Missing B/C evidence stays disabled in the UI.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from scipy.io import wavfile

from ..stage_af.package_integrity import canonical_json_bytes, seal_payload


SCHEMA = "s12.stage_ah.three_way.audition.v1"
MANIFEST_SCHEMA = "s12.stage_ah.three_way.artifacts.v1"
SCENE_IDS = (
    "01_afterfire", "02_full_pull", "03_hot_idle", "04_idle_return", "05_lift",
    "06_shift", "07_steady_high", "08_steady_low", "09_steady_mid", "10_tip_in",
)
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _sealed(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    checksum = value.pop("manifest_sha256", None) or value.pop("contract_sha256", None)
    if checksum != hashlib.sha256(canonical_json_bytes(value)).hexdigest():
        raise ValueError(f"sealed receipt mismatch: {path}")
    return value


def _embedded(text: str, name: str) -> Any:
    match = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*", text)
    if not match:
        raise ValueError(f"missing embedded {name}")
    return json.JSONDecoder().raw_decode(text[match.end():])[0]


def _copy_wav(source: Path, destination: Path) -> str:
    if not source.is_file():
        raise FileNotFoundError(source)
    rate, data = wavfile.read(source)
    if int(rate) != 48_000 or getattr(data, "ndim", 0) not in (1, 2):
        raise ValueError(f"governed WAV must be 48 kHz mono/stereo: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return sha256_file(destination)


def _asset(root: Path, filename: str) -> Path:
    candidates = (root / "web_audio" / filename, root / filename)
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"asset not found under {root}: {filename}")


def _load_scenes(page: Path) -> list[dict[str, Any]]:
    scenes = _embedded(page.read_text(encoding="utf-8"), "SCENES")
    if not isinstance(scenes, list) or [s.get("id") for s in scenes] != list(SCENE_IDS):
        raise ValueError(f"canonical ten-scene order required: {page}")
    return copy.deepcopy(scenes)


def render_vehicle_switcher(current: str, vehicles: Sequence[Mapping[str, Any]]) -> str:
    options = []
    for vehicle in vehicles:
        key, name = str(vehicle["key"]), str(vehicle["name"])
        status = str(vehicle.get("status", "READY"))
        selected = " selected" if key == current else ""
        options.append(f'<option value="../{key}/index.html"{selected}>{name} · {status}</option>')
    return (
        '<div class="bg-slate-900/90 border border-slate-700/80 px-3 py-1.5 rounded-lg '
        'flex items-center gap-2">'
        '<label for="vehicleSwitcher" class="text-slate-400">切换车型</label>'
        '<select id="vehicleSwitcher" onchange="if(this.value) location.href=this.value" '
        'class="bg-slate-800 text-slate-200 border border-slate-700 rounded px-2 py-1">'
        + "".join(options) + "</select></div>"
    )


TRIWAY_SCRIPT = r"""
<script>
const TRIWAY_ROLES = ['original', 'feedback', 'reference'];
let triSource = 'original';
const triBaseRender = renderSceneCards;

function triAvailable(role, scene) {
  const info = (DASHBOARD_CONTRACT.source_roles || {})[role] || {};
  const sceneInfo = (scene.role_availability || {})[role] || {};
  return Boolean(info.available && sceneInfo.available !== false && AUDIO_STORE[scene.id + '_' + role]);
}
function triLabel(role) {
  const info = (DASHBOARD_CONTRACT.source_roles || {})[role] || {};
  return info.label || ({original: 'A: 原始算法', feedback: 'B: 负反馈算法', reference: 'C: 真车原声'}[role]);
}
function triClass(role, active) {
  if (!active) return 'py-2 px-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 bg-slate-800/90 text-slate-200 border border-slate-700';
  const color = role === 'original' ? 'red' : role === 'feedback' ? 'amber' : 'emerald';
  return `py-2 px-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 bg-${color}-600 text-white shadow-lg ring-1 ring-${color}-400`;
}
function triSetHeader(scene) {
  const buttons = {original: document.getElementById('btnSourceA'), feedback: document.getElementById('btnSourceB'), reference: document.getElementById('btnSourceC')};
  TRIWAY_ROLES.forEach(role => {
    const button = buttons[role];
    if (!button) return;
    const available = triAvailable(role, scene);
    button.disabled = !available;
    button.className = available && triSource === role
      ? triClass(role, true)
      : triClass(role, false) + (available ? '' : ' opacity-40 cursor-not-allowed');
    button.textContent = available ? triLabel(role) : triLabel(role) + '（不可用）';
    button.title = available ? '' : ((scene.role_availability || {})[role] || {}).reason || ((DASHBOARD_CONTRACT.source_roles || {})[role] || {}).reason || '当前场景没有受控音频';
  });
  const badge = document.getElementById('activeBadgeSource');
  if (badge) badge.textContent = triLabel(triSource);
}
function triSetAudio(role, autoplay) {
  const scene = SCENES[currentSceneIndex];
  if (!triAvailable(role, scene)) return;
  const wasPlaying = isPlaying;
  const time = audioEl.currentTime;
  triSource = role;
  currentSource = role === 'original' ? 'candidate' : 'ref';
  audioEl.src = AUDIO_STORE[scene.id + '_' + role];
  audioEl.playbackRate = playbackSpeed;
  audioEl.loop = isLooping;
  try { if (Number.isFinite(time)) audioEl.currentTime = time; } catch (e) {}
  triSetHeader(scene);
  renderSceneCards();
  if (autoplay || wasPlaying) {
    initAudioContext();
    audioEl.play().catch(e => console.error('Playback error:', e));
  }
}
function switchTriSource(role) { triSetAudio(role, isPlaying); }
function playTriSource(index, role) {
  if (currentSceneIndex === index && triSource === role) { togglePlay(); return; }
  currentSceneIndex = index;
  triSetAudio(role, true);
}
function loadSceneTri(index, role, autoplay) {
  currentSceneIndex = index;
  const scene = SCENES[index];
  document.getElementById('activeTrackTitle').textContent = scene.title;
  document.getElementById('activeTrackDesc').textContent = scene.desc;
  document.getElementById('activeBadgeCategory').textContent = scene.category === 'idle' ? '怠速工况' : scene.category === 'acceleration' ? '加速狂飙' : scene.category === 'afterfire' ? '回火放炮' : scene.category === 'dynamics' ? '动态瞬态' : '稳态巡航';
  triSetAudio(role, autoplay);
}
loadScene = function(index, source, autoplay) { loadSceneTri(index, source === 'ref' ? 'feedback' : 'original', autoplay); };
changeScene = function(delta) { loadSceneTri((currentSceneIndex + delta + SCENES.length) % SCENES.length, triSource, true); };
selectAndPlayScene = function(index) { loadSceneTri(index, triSource, true); };
renderSceneCards = function() {
  triBaseRender();
  document.querySelectorAll('.scene-card').forEach(card => {
    const scene = SCENES.find(item => item.id === card.dataset.sceneId);
    const index = SCENES.indexOf(scene);
    const grid = card.querySelector('div.grid.grid-cols-2');
    if (!scene || !grid) return;
    grid.classList.remove('grid-cols-2');
    grid.classList.add('grid-cols-3');
    grid.innerHTML = TRIWAY_ROLES.map(role => {
      const available = triAvailable(role, scene);
      const active = available && currentSceneIndex === index && triSource === role && isPlaying;
      const text = available ? triLabel(role) : triLabel(role) + '（不可用）';
      const reason = ((scene.role_availability || {})[role] || {}).reason || ((DASHBOARD_CONTRACT.source_roles || {})[role] || {}).reason || '当前场景没有受控音频';
      return `<button ${available ? '' : 'disabled'} title="${available ? '' : reason}" onclick="playTriSource(${index}, '${role}')" class="${triClass(role, active)}${available ? '' : ' opacity-40 cursor-not-allowed'}"><span>${active ? '⏸' : '▶'}</span>${text}</button>`;
    }).join('');
    triSetHeader(SCENES[currentSceneIndex]);
  });
};
window.addEventListener('DOMContentLoaded', () => {
  triSource = 'original';
  loadSceneTri(currentSceneIndex, triSource, false);
  renderSceneCards();
});
</script>
"""


def _comparator_block() -> str:
    return """<!-- Tri-way source comparator -->
          <div class="bg-slate-900/90 p-2 rounded-xl border border-slate-800 flex items-center justify-between gap-2">
            <div class="text-xs font-semibold text-slate-400 pl-1">三路瞬时对照:</div>
            <div class="flex items-center gap-1.5">
              <button id="btnSourceA" onclick="switchTriSource('original')" class="py-2 px-2 rounded-lg text-xs font-semibold bg-red-600 text-white">A: 原始算法（未加负反馈）</button>
              <button id="btnSourceB" onclick="switchTriSource('feedback')" class="py-2 px-2 rounded-lg text-xs font-semibold bg-amber-600 text-white">B: 负反馈算法</button>
              <button id="btnSourceC" onclick="switchTriSource('reference')" class="py-2 px-2 rounded-lg text-xs font-semibold bg-emerald-600 text-white">C: 真车原声</button>
            </div>
          </div>

          <!-- Progress Bar & Scrubber -->"""


def build_page_html(template: str, key: str, title: str, subtitle: str,
                    scenes: Sequence[Mapping[str, Any]], contract: Mapping[str, Any],
                    audio_store: Mapping[str, str], vehicles: Sequence[Mapping[str, Any]],
                    parameters: Sequence[Mapping[str, Any]] = ()) -> str:
    html = re.sub(r"<title>.*?</title>", f"<title>{title} - 三路声浪试听</title>", template, count=1, flags=re.S)
    html = re.sub(r"<h1[^>]*>.*?</h1>", f'<h1 class="font-bold text-lg text-white tracking-wide">{title}</h1>', html, count=1, flags=re.S)
    html = re.sub(r'<p class="text-xs text-slate-400">.*?</p>', f'<p class="text-xs text-slate-400">{subtitle}</p>', html, count=1, flags=re.S)
    html = re.sub(r"<!-- Seamless A/B Comparator Switch -->.*?<!-- Progress Bar & Scrubber -->",
                  _comparator_block(), html, count=1, flags=re.S)
    switcher = render_vehicle_switcher(key, vehicles)
    roles = contract.get("source_roles", {})
    feedback_note = "" if roles.get("feedback", {}).get("available") else "（不可用） — " + str(roles.get("feedback", {}).get("reason", "无合格 B"))
    role_notice = ('<div id="triwayIdentityNotice" class="mb-3 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-xs text-slate-300">'
                   'A: 原始算法（未加负反馈） · B: 负反馈算法' + feedback_note + ' · C: 真车原声</div>')
    topbar = ('<div class="border-b border-slate-800 bg-[#0e1626]/90 px-4 lg:px-8 py-2">'
              '<div class="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2">'
              + role_notice + '<div class="flex justify-end">' + switcher + '</div></div></div>')
    html = html.replace("  </header>", "  </header>\n" + topbar, 1)
    html = html.replace("__SCENES_JSON__", json.dumps(list(scenes), ensure_ascii=False))
    html = html.replace("__PARAMS_JSON__", json.dumps(list(parameters), ensure_ascii=False))
    html = html.replace("__DASHBOARD_CONTRACT_JSON__", json.dumps(contract, ensure_ascii=False))
    html = html.replace("__AUDIOS_JSON__", json.dumps(dict(audio_store), ensure_ascii=False))
    return html.replace("</body>", TRIWAY_SCRIPT + "</body>", 1)


def _source_descriptor(key: str, name: str, original: Path, feedback: Path | None,
                      reference: Path, status: str, reason: str = "") -> dict[str, Any]:
    return {
        "key": key, "name": name, "status": status,
        "original_root": str(original),
        "feedback_root": str(feedback) if feedback else None,
        "reference_root": str(reference),
        "feedback_available": feedback is not None,
        "feedback_reason": reason,
    }


def _specs() -> list[dict[str, Any]]:
    rp = Path(r"E:\Tesla_speed\review_packages")
    four = rp / "s12-stage-ah-fourcar-audit-fix-20260913-v4" / "packages"
    four_a = four / "ah-fourcar-realref-s12-stage-ah-fourcar-audit-fix-20260913-v4-c0"
    four_b = four / "ah-fourcar-realref-s12-stage-ah-fourcar-audit-fix-20260913-v4-realref"
    four_names = {
        "hellcat": ("Dodge Challenger SRT Hellcat", "⚡", "DODGE HELLCAT V8"),
        "ferrari_458": ("Ferrari 458 Italia", "🐎", "FERRARI 458 ITALIA V8"),
        "lfa": ("Lexus LFA", "🦅", "LEXUS LFA V10"),
        "gtr_r35": ("Nissan GT-R R35", "🏎️", "NISSAN GT-R R35 V6"),
    }
    specs = []
    for key, (name, icon, short) in four_names.items():
        folder = f"s12-stage-ad-{key.replace('_', '-')}-closed-loop-v1"
        specs.append({"key": key, "name": name, "icon": icon, "title": short,
                      "subtitle": "A 原始算法 / B 负反馈候选 / C 真实录音（R3）",
                      "original": four_a / folder, "feedback": four_b / folder,
                      "reference": four_b / folder, "page": four_b / folder / "index.html",
                      "status": "READY"})
    c63_root = rp / "s12-stage-ah-c63-w204-20260913-v3" / "packages"
    c63_a = c63_root / "ah-c63-s12-stage-ah-c63-w204-20260913-v3-b0" / "c63_w204"
    c63_c = c63_root / "ah-c63-s12-stage-ah-c63-w204-20260913-v3-c0" / "c63_w204"
    specs.append({"key": "c63_w204", "name": "Mercedes-AMG C63 W204", "icon": "🏁",
                  "title": "MERCEDES-AMG C63 W204 V8", "subtitle": "A 原始算法 / B 暂无合格负反馈 / C R2 本地录音",
                  "original": c63_a, "feedback": None, "reference": c63_c,
                  "page": c63_a / "index.html", "status": "B_UNAVAILABLE",
                  "reason": "当前 C63 资产只有原始/保护版，没有独立负反馈候选"})
    supra_root = rp / "s12-stage-ah-supra-jza80-20260912-v2" / "packages"
    supra_a = supra_root / "ah-supra-s12-stage-ah-supra-jza80-20260912-v2-c0" / "supra_jza80"
    supra_b = rp / "s12-stage-ah-supra-real-reference-20260913-v3" / "packages" / "ah-supra-realref-s12-stage-ah-supra-real-reference-20260913-v3-c0" / "supra_jza80"
    specs.append({"key": "supra_jza80", "name": "Toyota Supra JZA80", "icon": "🔰",
                  "title": "TOYOTA SUPRA JZA80 I6", "subtitle": "A 原始算法 / B 多源反馈候选 / C R3 真实录音",
                  "original": supra_a, "feedback": supra_b, "reference": supra_b,
                  "page": supra_b / "index.html", "status": "READY"})
    rx7_root = rp / "s12-stage-ah-rx7-aventador-six-source-20260914-v5" / "packages" / "ah-remaining-s12-stage-ah-rx7-aventador-six-source-20260914-v5-c0" / "rx7_fd"
    specs.append({"key": "rx7_fd", "name": "Mazda RX-7 FD", "icon": "🌀",
                  "title": "MAZDA RX-7 FD ROTARY", "subtitle": "A 原始算法 / B 数值门禁阻塞 / C R3 真实录音",
                  "original": rx7_root, "feedback": None, "reference": rx7_root,
                  "page": rx7_root / "index.html", "status": "B_BLOCKED",
                  "reason": "09_steady_mid 的 4×峰值估计超过数值门禁"})
    loop = rp / "s12-stage-ah-reference-loop-20260914-v1"
    specs.append({"key": "aventador_lp700", "name": "Lamborghini Aventador LP700-4", "icon": "🐂",
                  "title": "LAMBORGHINI AVENTADOR V12", "subtitle": "A 原始算法 / B 真实录音反馈优化 / C R3 真实录音",
                  "original": loop / "baseline" / "aventador_lp700", "feedback": loop / "tuned" / "aventador_lp700",
                  "reference": loop / "tuned" / "aventador_lp700", "page": loop / "tuned" / "aventador_lp700" / "index.html",
                  "status": "READY"})
    return specs


def _find_reference_file(root: Path, scene: Mapping[str, Any]) -> Path | None:
    filename = str(scene.get("ref_file") or "")
    if not filename:
        return None
    try:
        return _asset(root, filename)
    except FileNotFoundError:
        return None


def build_package(output: Path, run_id: str | None = None) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    output = output.resolve()
    run_id = run_id or output.name
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / ("." + output.name + ".lock")
    lock.touch(exist_ok=False)
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix="." + output.name + "-", dir=output.parent))
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        specs = _specs()
        nav = [{"key": s["key"], "name": s["name"], "status": s["status"]} for s in specs]
        vehicles: dict[str, Any] = {}
        for spec in specs:
            scenes = _load_scenes(spec["page"])
            vehicle_root = staging / spec["key"]
            web = vehicle_root / "web_audio"
            source_sha: dict[str, dict[str, str]] = {"original": {}, "feedback": {}, "reference": {}}
            audio_store: dict[str, str] = {}
            for scene in scenes:
                scene_id = scene["id"]
                original = _asset(spec["original"], scene["candidate_file"])
                a_name = f"A_{scene_id}.wav"
                source_sha["original"][a_name] = _copy_wav(original, web / a_name)
                encoded_a = "web_audio/" + a_name
                audio_store[scene_id + "_candidate"] = encoded_a
                audio_store[scene_id + "_original"] = encoded_a
                scene["candidate_file"] = a_name
                if spec["feedback"]:
                    feedback = _asset(spec["feedback"], scene["candidate_file"].replace("A_", "", 1) if scene["candidate_file"].startswith("A_") else scene["candidate_file"])
                    b_name = f"B_{scene_id}.wav"
                    source_sha["feedback"][b_name] = _copy_wav(feedback, web / b_name)
                    encoded_b = "web_audio/" + b_name
                    audio_store[scene_id + "_ref"] = encoded_b
                    audio_store[scene_id + "_feedback"] = encoded_b
                    scene["feedback_file"] = b_name
                else:
                    scene["feedback_file"] = ""
                ref = _find_reference_file(spec["reference"], scene)
                if ref:
                    c_name = f"C_{scene_id}.wav"
                    source_sha["reference"][c_name] = _copy_wav(ref, web / c_name)
                    audio_store[scene_id + "_reference"] = "web_audio/" + c_name
                    scene["reference_file"] = c_name
                else:
                    scene["reference_file"] = ""
                scene["ref_file"] = scene["feedback_file"]
            roles = {
                "original": {"label": "A: 原始算法（未加负反馈）", "available": True,
                              "status": "ORIGINAL_NO_FEEDBACK"},
                "feedback": {"label": "B: 负反馈算法", "available": bool(spec["feedback"]),
                              "status": "FEEDBACK_CANDIDATE" if spec["feedback"] else spec["status"],
                              "reason": "" if spec["feedback"] else spec.get("reason", "没有独立负反馈候选")},
                "reference": {"label": "C: 真车原声", "available": bool(source_sha["reference"]),
                               "status": "R3/R2_REFERENCE" if source_sha["reference"] else "REFERENCE_UNAVAILABLE"},
            }
            contract = seal_payload({
                "schema": SCHEMA, "package_id": run_id + "-" + spec["key"],
                "vehicle": spec["key"], "vehicle_name": spec["name"],
                "comparison": "A_ORIGINAL_NO_FEEDBACK_VS_B_FEEDBACK_VS_C_REAL_RECORDING",
                "source_roles": roles, "source_sha256": source_sha,
                "scene_count": len(scenes), "sample_rate_hz": 48_000,
                "source_status": "SOURCE_CLEAN", "promotable": False,
                "human_status": "NOT_EVALUATED", "output_policy": "preserved_per_source_package",
            }, SCHEMA)
            _write_json(vehicle_root / "dashboard_contract.json", contract)
            html = build_page_html(template, spec["key"], spec["title"], spec["subtitle"], scenes,
                                   {**contract, "references": {
                                       name: {"available": True, "sha256": digest}
                                       for name, digest in source_sha["reference"].items()
                                   }, "candidate_pcm_sha256": source_sha["original"],
                                   "reference_sha256": source_sha["reference"]}, audio_store, nav)
            for filename in ("index.html", "index_standalone.html"):
                (vehicle_root / filename).write_text(html, encoding="utf-8")
            vehicles[spec["key"]] = {
                "vehicle": spec["name"], "status": "READY" if spec["feedback"] else spec["status"],
                "source_roles": roles, "scene_count": len(scenes),
                "source_sha256": source_sha,
                "dashboard_contract_sha256": sha256_file(vehicle_root / "dashboard_contract.json"),
            }
        summary = seal_payload({"schema": SCHEMA, "run_id": run_id, "vehicles": vehicles,
                                "vehicle_count": len(vehicles), "comparison": "A_ORIGINAL_NO_FEEDBACK_VS_B_FEEDBACK_VS_C_REAL_RECORDING",
                                "human_status": "NOT_EVALUATED", "promotable": False}, SCHEMA)
        _write_json(staging / "summary.json", summary)
        (staging / "index.html").write_text(
            '<!doctype html><meta charset="utf-8"><title>S12 三路声浪试听</title>'
            '<h1>S12 三路声浪试听工作台</h1><p>A=原始算法，B=负反馈算法，C=真车原声。</p>'
            + "".join(f'<p><a href="{v}/index.html">{v}</a></p>' for v in vehicles), encoding="utf-8")
        files = {p.relative_to(staging).as_posix(): sha256_file(p)
                 for p in staging.rglob("*") if p.is_file()}
        _write_json(staging / "ARTIFACTS.json", seal_payload({"schema": MANIFEST_SCHEMA, "files": files}, MANIFEST_SCHEMA))
        verify_package(staging)
        staging.rename(output)
        staging = None
        return summary
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def verify_package(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _sealed(root / "ARTIFACTS.json")
    files = manifest.get("files", {})
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "ARTIFACTS.json"}
    if actual != set(files):
        raise ValueError("three-way artifact inventory mismatch")
    for relative, digest in files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or sha256_file(path) != digest:
            raise ValueError(f"three-way artifact drift: {relative}")
    summary = _sealed(root / "summary.json")
    for key, row in summary["vehicles"].items():
        folder = root / key
        contract = _sealed(folder / "dashboard_contract.json")
        text = (folder / "index.html").read_text(encoding="utf-8")
        embedded = _embedded(text, "DASHBOARD_CONTRACT")
        if any(embedded.get(field) != value for field, value in contract.items()):
            raise ValueError(f"embedded contract mismatch: {key}")
        scenes = _embedded(text, "SCENES")
        store = _embedded(text, "AUDIO_STORE")
        for scene in scenes:
            for role, filename in (("original", scene["candidate_file"]), ("feedback", scene.get("feedback_file", "")), ("reference", scene.get("reference_file", ""))):
                if not filename:
                    continue
                stored = store[scene["id"] + "_" + role]
                if stored.startswith("data:"):
                    raw = base64.b64decode(stored.split(",", 1)[1], validate=True)
                elif stored.startswith("web_audio/"):
                    raw = (folder / stored).read_bytes()
                else:
                    raise ValueError(f"unsupported audio store entry: {stored}")
                if raw != (folder / "web_audio" / filename).read_bytes():
                    raise ValueError(f"embedded audio mismatch: {key}/{scene['id']}/{role}")
    return summary


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_package(args.out), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
