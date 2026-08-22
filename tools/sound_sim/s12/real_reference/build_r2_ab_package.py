"""Build an external, Chinese R2 A/B audition package.

The package contains only loudness-matched presentation copies.  It keeps the
unaltered source WAV outside Git and binds each audition file to the original
source SHA-256.  It is a listening hand-off, not a tuning or Profile update.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import wave
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.listening import loudness_matched_audition
from tools.sound_sim.s12.real_reference.stage_r_execute import read_unaltered_pcm_wav


ALLOWED_DOWNLOAD_ROOT = Path(r"E:\Claude_allow\Download")
SCHEMA_VERSION = "s12-stage-s-r2-ab-package-v1"
DIMENSIONS = (
    "vehicle_identity",
    "realism",
    "low_frequency_weight",
    "mechanical_character",
    "idle_life",
    "acceleration_aggression",
    "shift_realism",
    "afterfire_naturalness",
    "synthetic_artifact_freedom",
    "preference",
)
DIMENSION_LABELS_ZH = {
    "vehicle_identity": "车型身份",
    "realism": "真实感",
    "low_frequency_weight": "低频重量",
    "mechanical_character": "机械感",
    "idle_life": "怠速生命感",
    "acceleration_aggression": "加速攻击性",
    "shift_realism": "换挡真实感",
    "afterfire_naturalness": "回火自然度",
    "synthetic_artifact_freedom": "合成器感/伪影少",
    "preference": "偏好",
}


def write_chinese_ab_page(output_root: Path, study: Mapping[str, Any]) -> Path:
    """Write a self-contained Chinese A/B page with complete Stage-S bindings.

    The page materializes only relative audition paths.  It exports machine
    dimension IDs (while displaying Chinese labels) plus the playback metadata
    required by ``feedback_binding.json``.  It never exports tuning authority.
    """

    output_root = Path(output_root)
    cases = list(study.get("cases", []))
    dimensions = [
        (str(item.get("id")), str(item.get("label_zh", DIMENSION_LABELS_ZH.get(str(item.get("id")), item.get("id", "")))))
        for item in study.get("dimensions", [])
        if isinstance(item, Mapping) and item.get("id")
    ]
    if not dimensions:
        dimensions = [(key, DIMENSION_LABELS_ZH[key]) for key in DIMENSIONS]
    page_data = {
        "test_id": str(study.get("test_id", "")),
        "package_manifest_sha256": str(study.get("package_manifest_sha256", "")),
        "dimensions": dimensions,
        "cases": [
            {
                "case_id": str(case["case_id"]),
                "vehicle_id": str(case["vehicle_id"]),
                "scenario": str(case["scenario"]),
                "reference_sha256": str(case["reference"].get("source_sha256", "")),
                "candidate_sha256": str(case["candidate"].get("source_sha256", case["candidate"].get("candidate_sha256", ""))),
                "reference_audition_sha256": str(case["reference"].get("audition_sha256", "")),
                "candidate_audition_sha256": str(case["candidate"].get("audition", {}).get("audition_sha256", "")),
                "reference_audio": f"audio/{case['case_id']}/reference_audition.wav",
                "candidate_audio": f"audio/{case['case_id']}/candidate_audition.wav",
            }
            for case in cases
        ],
    }
    embedded = json.dumps(page_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = output_root / "index.html"
    page.write_text(
        """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>S12 中文真实声浪 A/B 听审</title>
<style>
body{margin:0;background:#f4f7fb;color:#172033;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.55}
main{max-width:960px;margin:auto;padding:20px 14px 48px}.card{background:#fff;border:1px solid #d9e0ea;border-radius:12px;padding:18px;margin:12px 0;box-shadow:0 2px 9px #17203310}
h1{font-size:25px;margin:0 0 8px}h2{font-size:19px;margin:0 0 10px}.notice{background:#fff1e8;border-left:5px solid #a44a00;padding:10px 12px;border-radius:7px}
label{display:block;font-weight:700;margin:10px 0 4px}input,select,textarea{width:100%;box-sizing:border-box;border:1px solid #b9c4d4;border-radius:7px;padding:8px;font:inherit;background:#fff}
.audio{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.audio div{border:1px solid #d9e0ea;border-radius:8px;padding:12px}.ref{border-top:4px solid #16794b}.cand{border-top:4px solid #175cd3}audio{width:100%;margin-top:8px}
.scores{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:14px}.score{background:#f8fafc;padding:8px;border:1px solid #d9e0ea;border-radius:7px}.score label{margin:0 0 4px;font-weight:600}
button{border:0;border-radius:7px;padding:10px 14px;background:#175cd3;color:white;font:inherit;font-weight:700;cursor:pointer;margin:8px 8px 0 0}button.gray{background:#5f6b7a}pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;padding:10px;border-radius:7px}.muted{color:#5f6b7a;font-size:13px}
</style></head><body><main>
<section class="card"><h1>S12 中文真实声浪对比听审</h1>
<p>请先听 A（有许可的真实录音参考），再听 B（本地合成候选），保持同一耳机、系统音量和播放端点。</p>
<div class="notice"><strong>边界：</strong>这是第二级（R2）有限相对比较，不是第一级（R1）阶次资格，不会自动调参，也不会更新车型配置。试听副本只用于听审。</div>
<p class="muted">测试编号：<code id="test-id"></code><br>研究清单 SHA-256：<code id="manifest-sha"></code></p>
<label for="listener_id">监听人编号（必填）</label><input id="listener_id" placeholder="例如：Jovi-20260823-A">
<label for="playback_device">播放设备（必填）</label><input id="playback_device" placeholder="例如：耳机型号或扬声器">
<label for="windows_volume">系统音量（必填）</label><input id="windows_volume" placeholder="例如：Windows 40%">
<label for="playback_endpoint">输出端点（必填）</label><input id="playback_endpoint" placeholder="例如：USB 耳机 / HDMI">
<label for="system_audio_effects">系统音效（必填）</label><input id="system_audio_effects" placeholder="例如：关闭均衡器、响度增强和自动增益">
<p id="progress" class="muted"></p></section>
<div id="cases"></div>
<section class="card"><button id="export">生成反馈 JSON</button><button id="copy" class="gray">复制 JSON</button><button id="clear" class="gray">清空</button><p id="status" class="muted">尚未导出。</p><pre id="preview"></pre></section>
</main><script>
(function(){"use strict";var STUDY=__STUDY__;var root=document.getElementById("cases");
document.getElementById("test-id").textContent=STUDY.test_id;document.getElementById("manifest-sha").textContent=STUDY.package_manifest_sha256;
function id(caseId,dim){return "score-"+caseId+"-"+dim}function esc(value){return String(value).replace(/[&<>"']/g,function(c){return c==='&'?'&amp;':c==='<'?'&lt;':c==='>'?'&gt;':c===String.fromCharCode(34)?'&quot;':'&#39;'})}
function addSelect(parent,selectId){var s=document.createElement("select");s.id=selectId;s.innerHTML='<option value="">请选择</option><option value="1">1：明显不匹配</option><option value="2">2：偏差较大</option><option value="3">3：基本接近</option><option value="4">4：较接近</option><option value="5">5：高度匹配</option><option value="uncertain">不确定</option>';s.onchange=progress;parent.appendChild(s);}
STUDY.cases.forEach(function(c){var card=document.createElement("section");card.className="card";card.innerHTML='<h2>案例：'+esc(c.vehicle_id)+' / '+esc(c.scenario)+'</h2><p class="muted">不要把该候选扩展到其他车型或工况。</p><div class="audio"><div class="ref"><strong>A：真实来源参考</strong><audio controls preload="metadata" src="'+esc(c.reference_audio)+'"></audio><p class="muted">原始 SHA：<code>'+esc(c.reference_sha256)+'</code><br>试听副本 SHA：<code>'+esc(c.reference_audition_sha256)+'</code></p></div><div class="cand"><strong>B：本地合成候选</strong><audio controls preload="metadata" src="'+esc(c.candidate_audio)+'"></audio><p class="muted">候选原始 SHA：<code>'+esc(c.candidate_sha256)+'</code><br>试听副本 SHA：<code>'+esc(c.candidate_audition_sha256)+'</code></p></div></div><div class="scores"></div><label>整体偏好</label><select class="preference"><option value="">请选择</option><option>参考声音更好</option><option>候选声音更好</option><option>两者接近</option><option>无法判断</option></select><label>备注：最明显的差异</label><textarea class="notes" rows="3" placeholder="例如：候选低频偏轻、转子事件感不足……"></textarea>';var scores=card.querySelector(".scores");STUDY.dimensions.forEach(function(d){var wrap=document.createElement("div");wrap.className="score";var label=document.createElement("label");label.textContent=d[1]+"匹配度";wrap.appendChild(label);addSelect(wrap,id(c.case_id,d[0]));scores.appendChild(wrap)});card.dataset.caseId=c.case_id;card.querySelector(".preference").onchange=progress;root.appendChild(card)});
function completeCase(card){var ok=true;STUDY.dimensions.forEach(function(d){if(!document.getElementById(id(card.dataset.caseId,d[0])).value)ok=false});if(!card.querySelector(".preference").value)ok=false;return ok}
function complete(){var fields=["listener_id","playback_device","windows_volume","playback_endpoint","system_audio_effects"];return fields.every(function(k){return document.getElementById(k).value.trim()})&&Array.prototype.every.call(root.children,completeCase)}
function progress(){var done=0;Array.prototype.forEach.call(root.children,function(card){if(completeCase(card))done++});document.getElementById("progress").textContent="已完成 "+done+" / "+STUDY.cases.length+" 个案例；听审元数据需全部填写。"}
function payload(){var cases=[];Array.prototype.forEach.call(root.children,function(card){var c=STUDY.cases.filter(function(x){return x.case_id===card.dataset.caseId})[0],scores={};STUDY.dimensions.forEach(function(d){scores[d[0]]=document.getElementById(id(c.case_id,d[0])).value||null});cases.push({case_id:c.case_id,vehicle_id:c.vehicle_id,scenario:c.scenario,reference_sha256:c.reference_sha256,candidate_sha256:c.candidate_sha256,scores:scores,preference:card.querySelector(".preference").value||null,notes_zh:card.querySelector(".notes").value.trim()||null})});return {schema_version:"s12-stage-s-human-feedback-zh.v1",test_id:STUDY.test_id,package_manifest_sha256:STUDY.package_manifest_sha256,exported_at_utc:new Date().toISOString(),listener_id:document.getElementById("listener_id").value.trim()||null,playback_device:document.getElementById("playback_device").value.trim()||null,windows_volume:document.getElementById("windows_volume").value.trim()||null,playback_endpoint:document.getElementById("playback_endpoint").value.trim()||null,system_audio_effects:document.getElementById("system_audio_effects").value.trim()||null,evidence_level:"R2",package_status:complete()?"READY_FOR_REVIEW":"DRAFT_INCOMPLETE",automatic_tuning_eligible:false,profile_update:"FORBIDDEN",cases:cases}}
function show(){var t=JSON.stringify(payload(),null,2);document.getElementById("preview").textContent=t;return t}document.getElementById("export").onclick=function(){var p=payload();if(!complete()){alert("请先填写监听元数据并完成全部案例评分");return}var t=show(),u=URL.createObjectURL(new Blob([t],{type:"application/json;charset=utf-8"})),a=document.createElement("a");a.href=u;a.download="jovi_s12_r2_feedback_"+Date.now()+".json";a.click();URL.revokeObjectURL(u);document.getElementById("status").textContent="已导出完整反馈 JSON。"};document.getElementById("copy").onclick=function(){if(!complete()){alert("请先填写监听元数据并完成全部案例评分");return}var t=show();if(navigator.clipboard){navigator.clipboard.writeText(t);document.getElementById("status").textContent="已复制反馈 JSON。"}};document.getElementById("clear").onclick=function(){if(!confirm("确定清空所有填写内容吗？"))return;["listener_id","playback_device","windows_volume","playback_endpoint","system_audio_effects"].forEach(function(k){document.getElementById(k).value=""});root.querySelectorAll("select,textarea").forEach(function(x){x.value=""});document.getElementById("preview").textContent="";progress()};progress()})();
</script></body></html>""".replace("__STUDY__", embedded),
        encoding="utf-8",
        newline="\n",
    )
    return page


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_pcm16(path: Path, signal: np.ndarray, sample_rate_hz: int) -> None:
    value = np.asarray(signal, dtype=np.float64)
    if value.ndim == 1:
        value = value[:, None]
    if value.ndim != 2 or value.shape[1] not in {1, 2}:
        raise ValueError("audition WAV must be mono or stereo")
    pcm = np.rint(np.clip(value, -1.0, 1.0 - 1.0 / (1 << 15)) * ((1 << 15) - 1)).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(int(value.shape[1]))
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate_hz))
        handle.writeframes(pcm.tobytes())


def _make_audition(source: Path, destination: Path) -> dict[str, Any]:
    signal, rate, header = read_unaltered_pcm_wav(source)
    audition, level = loudness_matched_audition(signal)
    _write_pcm16(destination, audition, rate)
    return {
        "source_path_alias": str(source),
        "source_sha256": str(header["sha256"]),
        "audition_path": str(destination),
        "audition_sha256": _sha256(destination),
        "sample_rate_hz": int(rate),
        "channels": int(header["channels"]),
        "frames": int(header["frames"]),
        "level": level,
        "analysis_signal": "unaltered_source_wav",
        "audition_signal": "loudness_matched_audition_signal_separate",
    }


def _under_download(path: Path) -> Path:
    resolved = path.resolve()
    root = ALLOWED_DOWNLOAD_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"output must stay under {root}: {resolved}")
    return resolved


def _write_csv(path: Path, cases: list[Mapping[str, Any]], package_sha256: str) -> None:
    columns = [
        "package_manifest_sha256",
        "test_id",
        "case_id",
        "vehicle_id",
        "scenario",
        "reference_sha256",
        "candidate_sha256",
        "listener_id",
        "playback_device",
        "windows_volume",
        "playback_endpoint",
        "system_audio_effects",
        *DIMENSIONS,
        "notes_zh",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "package_manifest_sha256": package_sha256,
                    "test_id": "s12-stage-s-r2-ab-20260822",
                    "case_id": case["case_id"],
                    "vehicle_id": case["vehicle_id"],
                    "scenario": case["scenario"],
                    "reference_sha256": case["reference"]["source_sha256"],
                    "candidate_sha256": case["candidate"]["source_sha256"],
                    "notes_zh": "请由 Jovi 填写；空白行不能导入为反馈。",
                }
            )


def build_package(manifest_path: Path, candidate_spec_path: Path, output_root: Path) -> dict[str, Any]:
    output_root = _under_download(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite populated package: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_spec = json.loads(candidate_spec_path.read_text(encoding="utf-8"))
    candidates = {str(row["recording_id"]): dict(row) for row in candidate_spec["cases"]}
    output_root.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    for recording in manifest.get("recordings", []):
        recording_id = str(recording.get("recording_id"))
        candidate = candidates.get(recording_id)
        if candidate is None:
            continue
        reference_path = Path(str(recording["external_path"]))
        candidate_path = Path(str(candidate["candidate_path"]))
        if not reference_path.is_file() or not candidate_path.is_file():
            raise FileNotFoundError(f"missing R2 A/B source for {recording_id}")
        expected_reference_sha = str(recording["sha256"])
        actual_reference_sha = _sha256(reference_path)
        if actual_reference_sha.lower() != expected_reference_sha.lower():
            raise ValueError(f"reference SHA-256 mismatch for {recording_id}")
        expected_candidate_sha = str(candidate.get("candidate_sha256") or _sha256(candidate_path))
        actual_candidate_sha = _sha256(candidate_path)
        if actual_candidate_sha.lower() != expected_candidate_sha.lower():
            raise ValueError(f"candidate SHA-256 mismatch for {recording_id}")
        case_id = recording_id.removeprefix("web_")
        ref_dest = output_root / "audio" / case_id / "reference_audition.wav"
        candidate_dest = output_root / "audio" / case_id / "candidate_audition.wav"
        reference_receipt = _make_audition(reference_path, ref_dest)
        candidate_receipt = _make_audition(candidate_path, candidate_dest)
        cases.append(
            {
                "case_id": case_id,
                "recording_id": recording_id,
                "reference_id": recording["reference_id"],
                "vehicle_id": recording["vehicle_id"],
                "scenario": recording["scenario"],
                "scenario_identity": recording.get("scenario_identity"),
                "license": recording["provenance"]["license"],
                "source_url": recording["provenance"]["source_url"],
                "reference": reference_receipt,
                "candidate": {
                    **candidate,
                    "source_sha256": actual_candidate_sha,
                    "audition": candidate_receipt,
                },
                "qualification": "R2_LIMITED_COMPARISON_ONLY",
                "order_hard_gate": False,
                "automatic_tuning_eligible": False,
                "feedback_status": "WAITING_FOR_JOVI",
            }
        )
    if not cases:
        raise ValueError("candidate spec selected no R2 manifest records")
    study = {
        "schema_version": SCHEMA_VERSION,
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "language": "zh-CN",
        "test_id": "s12-stage-s-r2-ab-20260822",
        "study_type": "paired_A_B",
        "source_policy": "raw_source_wav_stays_external; only audition copies are materialized in this external package",
        "analysis_policy": "do_not_use_audition_copy_for_metrics",
        "instructions_zh": [
            "每个案例先听 A（真实参考）再听 B（本地 synthetic 候选），保持同一播放设备和系统音量。",
            "不要把视频标题、车标或网页描述当作原厂排气证明；当前是 R2 相对比较。",
            "请记录车型身份、真实感、低频重量、机械感、加速攻击性、合成器伪影和偏好。没有 SHA 绑定的记录不导入。",
        ],
        "dimensions": [{"id": key, "label_zh": DIMENSION_LABELS_ZH[key], "scale": [0, 25, 50, 75, 100]} for key in DIMENSIONS],
        "cases": cases,
        "missing_anchor_cases": [
            {
                "vehicle_id": "rx7_fd",
                "status": "NOT_INCLUDED_R3_ONLY",
                "reason": "当前只有 CC BY-SA 旋转机械演示，不是 RX-7 FD 整车参考；不会把它当作 R2。",
            }
        ],
    }
    study_path = output_root / "study_manifest.json"
    study_path.write_text(json.dumps(study, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    study_sha = _sha256(study_path)
    write_chinese_ab_page(output_root, {**study, "package_manifest_sha256": study_sha})
    binding = {
        "schema_version": SCHEMA_VERSION,
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "test_id": study["test_id"],
        "study_manifest_sha256": study_sha,
        "required_binding": [
            "study_manifest_sha256",
            "test_id",
            "case_id",
            "reference_sha256",
            "candidate_sha256",
            "listener_id",
            "playback_device",
            "windows_volume",
            "playback_endpoint",
            "system_audio_effects",
            *DIMENSIONS,
        ],
        "cases": {case["case_id"]: {"vehicle_id": case["vehicle_id"], "scenario": case["scenario"], "reference_sha256": case["reference"]["source_sha256"], "candidate_sha256": case["candidate"]["source_sha256"]} for case in cases},
    }
    binding_path = output_root / "feedback_binding.json"
    binding_path.write_text(json.dumps(binding, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    template_path = output_root / "feedback_template.csv"
    _write_csv(template_path, cases, study_sha)
    readme = output_root / "README_中文.md"
    readme.write_text(
        "# S12 R2 中文 A/B 听审包\n\n"
        "状态：`WAITING_FOR_JOVI_HUMAN_FEEDBACK`。本包只有外部 R2 合法参考的响度匹配试听副本；未校准 WAV 仍只用于分析，不能用试听副本计算指标。\n\n"
        "1. 依次播放 `audio/<case_id>/reference_audition.wav`（A）和 `candidate_audition.wav`（B）。\n"
        "2. 固定播放设备、Windows 音量、输出端点和系统音效；不要使用增强、EQ 或自动增益。\n"
        "3. 把反馈写入 `feedback_template.csv`，每一行必须填 listener_id、设备、音量、端点、系统音效和全部中文维度。\n"
        "4. 反馈必须保留 `study_manifest_sha256`、案例 ID、参考 SHA 和候选 SHA；空白模板不是真人反馈。\n\n"
        "本页面只包含已绑定案例；其他车型或工况不得复用候选。页面只导出反馈，不自动调参。\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": study["status"],
        "study_manifest": str(study_path),
        "study_manifest_sha256": study_sha,
        "feedback_binding": str(binding_path),
        "feedback_template": str(template_path),
        "chinese_page": str(output_root / "index.html"),
        "case_count": len(cases),
        "cases": [case["case_id"] for case in cases],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成仓库外中文 R2 A/B 听审包")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate-spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = build_package(args.manifest.resolve(), args.candidate_spec.resolve(), args.output_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
