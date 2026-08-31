"""Export non-destructive, upstream-compatible webMUSHRA study packages."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

from . import loudness_matched_audition


RATING_DIMENSIONS = (
    "vehicle_identity",
    "realism",
    "low_frequency_weight",
    "mechanical_character",
    "idle_life",
    "acceleration_aggression",
    "shift_realism",
    "afterfire_naturalness",
    "synthetic_artifact_freedom",
)


# These are the visible labels used by the Chinese listening study.  The
# machine-facing dimension IDs remain stable so the official webMUSHRA CSV
# importer and the Stage-S feedback contract do not change.
CHINESE_RATING_LABELS = {
    "vehicle_identity": "车型身份",
    "realism": "真实感",
    "low_frequency_weight": "低频重量",
    "mechanical_character": "机械感",
    "idle_life": "怠速生命感",
    "acceleration_aggression": "加速攻击性",
    "shift_realism": "换挡真实感",
    "afterfire_naturalness": "回火自然度",
    "synthetic_artifact_freedom": "合成器感/伪影少",
}

CHINESE_VEHICLE_LABELS = {
    "ferrari_458": "法拉利 458",
    "hellcat": "道奇 Hellcat",
    "rx7_fd": "马自达 RX-7 FD",
    "aventador": "兰博基尼 Aventador",
    "c63_w204": "奔驰 C63 W204",
    "gtr_r35": "日产 GT-R R35",
    "lfa": "雷克萨斯 LFA",
    "supra_mk4": "丰田 Supra MK4",
}

CHINESE_SCENARIO_LABELS = {
    "full_cycle": "完整驾驶循环",
    "idle": "怠速",
    "acceleration": "加速",
    "lift_afterfire": "收油回火",
    "shift": "换挡",
}


# The upstream checkout uses a global ``nls`` object.  The generated patch is
# applied after the upstream nls.js file and supplies every key used by the
# official pages, so fixed buttons and captions are also Chinese.
CHINESE_WEBMUSHRA_NLS = {
    "nextButton": "下一页",
    "previousButton": "上一页",
    "playButton": "播放",
    "stopButton": "停止",
    "pauseButton": "暂停",
    "eliminateButton": "排除",
    "resetButton": "重置",
    "sendButton": "提交结果",
    "excellent": "非常好",
    "good": "好",
    "fair": "一般",
    "poor": "较差",
    "bad": "很差",
    "reference": "参考声音",
    "conditions": "声音条件：",
    "cond": "条件",
    "35": "低质量锚点",
    "75": "低质量锚点",
    "imperceptible": "听不出差异",
    "perceptible": "能听出，但不令人不适",
    "slightly": "略微令人不适",
    "annoying": "令人不适",
    "very": "非常令人不适",
    "quest": "哪一个是参考声音？",
    "results": "你的结果：",
    "attending": "感谢参与本次听审！",
}


def chinese_webmushra_nls_patch_text() -> str:
    """Return the upstream nls.js extension for the Chinese study."""

    lines = [
        "// S12 Stage S 中文界面覆盖；请在官方 webMUSHRA 的 nls.js 之后加载。",
        "nls['zh'] = new Object();",
    ]
    for key, value in CHINESE_WEBMUSHRA_NLS.items():
        lines.append(f"nls['zh'][{json.dumps(key)}] = {json.dumps(value, ensure_ascii=False)};")
    return "\n".join(lines) + "\n"


def apply_chinese_webmushra_patch(checkout: Path, patch_file: Path) -> dict[str, object]:
    """Install one marked, repeatable Chinese NLS patch in an external checkout."""

    checkout = Path(checkout)
    patch_file = Path(patch_file)
    index_path = checkout / "index.html"
    nls_dir = checkout / "lib" / "webmushra" / "nls"
    nls_path = nls_dir / "s12_stage_s_zh_cn.js"
    if not index_path.is_file():
        raise FileNotFoundError(f"webMUSHRA index.html not found: {index_path}")
    if not patch_file.is_file():
        raise FileNotFoundError(f"Chinese NLS patch not found: {patch_file}")
    patch_text = patch_file.read_text(encoding="utf-8")
    if "nls['zh']" not in patch_text:
        raise ValueError("patch does not define nls['zh']")
    nls_dir.mkdir(parents=True, exist_ok=True)
    nls_path.write_text(patch_text, encoding="utf-8", newline="\n")
    index_text = index_path.read_text(encoding="utf-8")
    script_tag = '<script src="lib/webmushra/nls/s12_stage_s_zh_cn.js"></script>'
    inserted = script_tag not in index_text
    if inserted:
        upstream_tag = '<script src="lib/webmushra/nls/nls.js"></script>'
        if upstream_tag not in index_text:
            raise ValueError("upstream nls.js script tag not found in index.html")
        index_text = index_text.replace(upstream_tag, upstream_tag + "\n    " + script_tag, 1)
        index_path.write_text(index_text, encoding="utf-8", newline="\n")
    return {"checkout": str(checkout), "nls_path": str(nls_path), "index_updated": inserted}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
    if channels not in {1, 2} or width not in {1, 2, 3, 4}:
        raise ValueError(f"unsupported WAV layout: {path}")
    raw = np.frombuffer(frames, dtype=np.uint8)
    if width == 1:
        value = (raw.astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        value = np.frombuffer(frames, dtype="<i2").astype(np.float64) / (1 << 15)
    elif width == 3:
        packed = raw.reshape(-1, 3)
        value = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        value = np.where(value & 0x800000, value - (1 << 24), value).astype(np.float64) / (1 << 23)
    else:
        value = np.frombuffer(frames, dtype="<i4").astype(np.float64) / (1 << 31)
    return value.reshape(-1, channels), rate


def _write_wav(path: Path, signal: np.ndarray, rate: int) -> None:
    value = np.clip(np.asarray(signal, dtype=np.float64), -1.0, 1.0 - 1.0 / (1 << 15))
    if value.ndim == 1:
        value = value[:, None]
    pcm = np.rint(value * ((1 << 15) - 1)).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(value.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def _audition_copy(source: Path, destination: Path) -> dict[str, object]:
    signal, rate = _read_wav(source)
    copy, level = loudness_matched_audition(signal)
    _write_wav(destination, copy, rate)
    return {"source_sha256": _sha256(source), "audition_sha256": _sha256(destination), "sample_rate_hz": rate, **level}


def _low_quality_anchor(source: Path, destination: Path) -> dict[str, object]:
    signal, rate = _read_wav(source)
    coarse = np.repeat(signal[::4], 4, axis=0)[: signal.shape[0]]
    copy, level = loudness_matched_audition(coarse)
    _write_wav(destination, copy, rate)
    return {"method": "four_sample_zero_order_hold_low_quality_anchor", "sha256": _sha256(destination), "sample_rate_hz": rate, **level}


def _yaml_quote(value: object) -> str:
    """Return a UTF-8 YAML scalar without exposing English UI text."""

    return json.dumps(str(value), ensure_ascii=False)


def _yaml(trials: Mapping[str, Mapping[str, object]]) -> str:
    vehicle_ids = sorted({str(record["vehicle_id"]) for record in trials.values()})
    lines = [
        "testname: " + _yaml_quote("S12 真实声浪对比与调音听审"),
        "testId: s12-stage-n-webmushra-v1",
        "language: zh",
        "bufferSize: 2048",
        "stopOnErrors: true",
        "showButtonPreviousPage: true",
        "remoteService: service/write.php",
        "pages:",
        "  - type: volume",
        "    id: playback-level",
        "    name: " + _yaml_quote("播放音量校准"),
        "    content: " + _yaml_quote("请使用指定播放端点，保持音量舒适且不失真。只有绑定合法真实参考后，结果才可用于真实声浪差异分析。"),
        f"    stimulus: {next(iter(trials.values()))['volume_path']}",
        "    defaultVolume: 0.5",
    ]
    for anonymous_id, trial in trials.items():
        scenario = CHINESE_SCENARIO_LABELS.get(str(trial["scenario"]), "当前工况")
        lines.extend([
            "  - type: mushra",
            f"    id: {anonymous_id}",
            f"    name: " + _yaml_quote(f"匿名样本 {anonymous_id} · {scenario}"),
            "    content: " + _yaml_quote("请反复播放并比较匿名声音。当前听审只在真实参考、候选 SHA、测试编号和听者信息绑定后才有效。"),
            "    showWaveform: false",
            "    showConditionNames: false",
            "    enableLooping: true",
            "    strict: true",
            f"    reference: {trial['reference_path']}",
            "    stimuli:",
            f"      stage_k_parent: {trial['parent_path']}",
            f"      stage_m_candidate: {trial['candidate_path']}",
            f"      low_quality_anchor: {trial['anchor_path']}",
        ])
        for dimension in RATING_DIMENSIONS:
            lines.extend([
                "  - type: likert_single_stimulus",
                f"    id: {anonymous_id}_{dimension}",
                f"    name: " + _yaml_quote(f"{CHINESE_RATING_LABELS[dimension]} · {anonymous_id}"),
                "    content: " + _yaml_quote(f"请只评价候选声音的“{CHINESE_RATING_LABELS[dimension]}”。0 分表示完全不符合，100 分表示非常符合。"),
                "    mustRate: true",
                "    stimuli:",
                f"      stage_m_candidate: {trial['candidate_path']}",
                "    response:",
                "      - value: 0",
                "        label: 0",
                "      - value: 25",
                "        label: 25",
                "      - value: 50",
                "        label: 50",
                "      - value: 75",
                "        label: 75",
                "      - value: 100",
                "        label: 100",
            ])
        lines.extend([
            "  - type: likert_single_stimulus",
            f"    id: {anonymous_id}_identity_guess",
            f"    name: " + _yaml_quote(f"车型猜测 · {anonymous_id}"),
            "    content: " + _yaml_quote("请选择你认为这个匿名候选声音最像的车型。"),
            "    mustRate: true",
            "    stimuli:",
            f"      stage_m_candidate: {trial['candidate_path']}",
            "    response:",
        ])
        for vehicle_id in vehicle_ids:
            lines.extend([f"      - value: {vehicle_id}", f"        label: {_yaml_quote(CHINESE_VEHICLE_LABELS.get(vehicle_id, vehicle_id))}"])
    lines.extend([
        "  - type: finish",
        "    name: " + _yaml_quote("提交听审结果"),
        "    content: " + _yaml_quote("结果会写入本地 webMUSHRA 服务。提交前请确认听者编号、播放设备、系统音量、输出端点和系统音效设置。"),
        "    showResults: false",
        "    showErrors: true",
        "    writeResults: true",
        "    questionnaire:",
        "      - type: text",
        "        label: 听者编号",
        "        name: listener_id",
        "        optional: false",
    ])
    return "\n".join(lines) + "\n"


def export_webmushra_study(
    destination: Path,
    trials: Iterable[Mapping[str, object]],
    *,
    upstream_receipt: Mapping[str, object],
    study_id: str = "s12-stage-n-webmushra-v1",
) -> dict[str, object]:
    """Create a new study directory and never overwrite a populated one."""

    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing webMUSHRA study: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    config_dir = destination / "configs"
    results_dir = destination / "results"
    audio_dir = destination / "audio"
    config_dir.mkdir()
    results_dir.mkdir()
    audio_dir.mkdir()
    results_dir.joinpath(".gitkeep").write_text("webMUSHRA result export destination\n", encoding="utf-8", newline="\n")
    records: dict[str, dict[str, object]] = {}
    config_stem = "s12-stage-n" if study_id == "s12-stage-n-webmushra-v1" else study_id
    for trial in trials:
        anonymous_id = str(trial["anonymous_id"])
        if anonymous_id in records:
            raise ValueError(f"duplicate anonymous id: {anonymous_id}")
        parent, candidate = Path(str(trial["parent"])), Path(str(trial["candidate"]))
        if not parent.is_file() or not candidate.is_file():
            raise FileNotFoundError("parent and candidate WAV files are required")
        folder = audio_dir / anonymous_id
        folder.mkdir()
        reference = folder / "reference_synthetic_parent.wav"
        parent_copy = folder / "stage_k_parent.wav"
        candidate_copy = folder / "stage_m_candidate.wav"
        anchor = folder / "low_quality_anchor.wav"
        reference_receipt = _audition_copy(parent, reference)
        parent_receipt = _audition_copy(parent, parent_copy)
        candidate_receipt = _audition_copy(candidate, candidate_copy)
        anchor_receipt = _low_quality_anchor(candidate, anchor)
        records[anonymous_id] = {
            "anonymous_id": anonymous_id,
            "vehicle_id": str(trial["vehicle_id"]),
            "scenario": str(trial["scenario"]),
            "reference_role": "synthetic_parent_not_real_reference",
            "future_candidate": {"status": "NOT_GENERATED", "reason": "no source change is authorized on comparator branch"},
            "reference_path": f"configs/{config_stem}/audio/{anonymous_id}/{reference.name}",
            "parent_path": f"configs/{config_stem}/audio/{anonymous_id}/{parent_copy.name}",
            "candidate_path": f"configs/{config_stem}/audio/{anonymous_id}/{candidate_copy.name}",
            "anchor_path": f"configs/{config_stem}/audio/{anonymous_id}/{anchor.name}",
            "volume_path": f"configs/{config_stem}/audio/{anonymous_id}/{reference.name}",
            "candidate_sha256": candidate_receipt["audition_sha256"],
            "audition_receipts": {"reference": reference_receipt, "parent": parent_receipt, "candidate": candidate_receipt, "anchor": anchor_receipt},
        }
    if not records:
        raise ValueError("at least one listening trial is required")
    config_filename = f"{config_stem}.yaml"
    yaml_path = config_dir / config_filename
    yaml_path.write_text(_yaml(records).replace("testId: s12-stage-n-webmushra-v1", f"testId: {study_id}", 1), encoding="utf-8", newline="\n")
    study = {
        "schema_version": "s12-stage-n-webmushra-study-1",
        "tool": "webMUSHRA",
        "ui_locale": "zh-CN",
        "upstream_language_code": "zh",
        "requires_localization_patch": True,
        "upstream_receipt": dict(upstream_receipt),
        "hidden_reference_policy": "synthetic_parent_not_real_reference",
        "rating_dimensions": list(RATING_DIMENSIONS),
        "looping": True,
        "loop_range_policy": "participant_settable_full_clip_default",
        "fade_policy": "webMUSHRA sample-accurate switching; no analysis signal is used for audition",
        "future_candidate_policy": "INACTIVE_NOT_GENERATED_NO_SOURCE_CHANGE_AUTHORIZED",
        "trials": records,
    }
    study_path = destination / "study_manifest.json"
    study_path.write_text(json.dumps(study, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    binding = {
        "schema_version": "s12-stage-n-webmushra-package-binding-1",
        "test_id": study_id,
        "package_manifest_sha256": _sha256(study_path),
        "trials": {key: {"candidate_sha256": value["candidate_sha256"], "vehicle_id": value["vehicle_id"], "scenario": value["scenario"]} for key, value in records.items()},
        "required_result_columns": ["listener_id", "anonymous_id", "package_manifest_sha256", "candidate_sha256", "identity_guess", *RATING_DIMENSIONS],
        "result_policy": "fixture imports and raw external rows are not human feedback until explicitly submitted by Jovi",
    }
    (destination / "webmushra_package_manifest.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (destination / "webmushra_zh_cn_nls.js").write_text(chinese_webmushra_nls_patch_text(), encoding="utf-8", newline="\n")
    (destination / "LOCAL_WEBMUSHRA_SETUP.md").write_text(
        "# 本地 Stage-N webMUSHRA 中文听审设置\n\n"
        "本研究包使用官方外部 webMUSHRA 代码；官方源代码不复制进本仓库。当前隐藏参考若为合成 parent，只能用于工具联调，不能当作真实车辆录音。\n\n"
        f"1. 将 `configs/{config_filename}` 复制到 `<webMUSHRA>/configs/{config_filename}`。\n"
        f"2. 将本包的 `audio/` 目录复制到 `<webMUSHRA>/configs/{config_stem}/audio/`。\n"
        "3. 运行 `python -m tools.sound_sim.s12.acoustic_comparator.listening.apply_webmushra_zh_cn_patch --checkout <webMUSHRA> --patch webmushra_zh_cn_nls.js`；脚本只会写入一个中文 NLS 文件，并在官方 `nls.js` 之后插入一次脚本标签。\n"
        "4. 在外部 checkout 目录运行 `docker compose up --build`。\n"
        f"5. 打开 `http://127.0.0.1:8000/?config={config_filename}`；页面标题、说明、播放按钮、评分维度和提交字段应为中文。\n"
        f"6. 结果位于 `<webMUSHRA>/results/{study_id}/mushra.csv` 和 `lss.csv`。\n"
        "7. 使用 `python -m tools.sound_sim.s12.acoustic_comparator.listening.webmushra_import --input <webMUSHRA>/results/<test-id>/mushra.csv --lss-input <webMUSHRA>/results/<test-id>/lss.csv --binding webmushra_package_manifest.json --output <receipt.json>` 导入官方导出。导入器会合并两个文件、绑定包 SHA/file-ID 并拒绝缺失评分维度；在 Jovi 明确提交前，任何 fixture 或浏览器结果都不是真人反馈。\n",
        encoding="utf-8", newline="\n",
    )
    return study
