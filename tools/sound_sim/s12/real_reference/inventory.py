"""Stage Q: inventory external real-reference candidates without copying audio.

The repository stores evidence about externally held recordings, never the
recordings themselves.  A downloaded/public clip is deliberately fail-closed:
without an auditable permission record, exact vehicle/stock evidence and a
synchronised state trace it cannot become an R1 calibration reference.
"""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "s12-stage-q-reference-database-v2"
DEFAULT_ADDITIONAL_MEDIA_ROOTS = (
    Path(r"E:\Claude_allow\Download\tesla-sound-research-v12"),
    Path(r"E:\Claude_allow\Download\s12-acoustic-realism-v10"),
)
ANCHOR_VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
ALL_VEHICLES = (
    "ferrari_458",
    "hellcat",
    "rx7_fd",
    "aventador_lp700",
    "c63_w204",
    "gtr_r35",
    "lfa",
    "supra_jza80",
)

VEHICLE_NAMES_ZH = {
    "ferrari_458": "法拉利 458",
    "hellcat": "道奇 Hellcat",
    "rx7_fd": "马自达 RX-7 FD",
    "aventador_lp700": "兰博基尼 Aventador LP700",
    "c63_w204": "奔驰 C63 W204",
    "gtr_r35": "日产 GT-R R35",
    "lfa": "雷克萨斯 LFA",
    "supra_jza80": "丰田 Supra JZA80",
}

# These are pointers only.  The raw files remain under the external download
# root and are never copied into this worktree.
CATALOG: tuple[dict[str, Any], ...] = (
    {
        "recording_id": "ferrari_458_accel",
        "vehicle_id": "ferrari_458",
        "relative_path": "ferrari_458_accel.wav",
        "scenario_hint": "acceleration",
        "source_url": "https://www.youtube.com/watch?v=X0yiRilcKME",
        "source_kind": "youtube_extracted",
        "source_log": "ferrari_458_accel.download.log",
        "screening_note": "公开加速候选；车型、原厂状态、视角与 RPM 未完成审计。",
    },
    {
        "recording_id": "hellcat_stock_accel",
        "vehicle_id": "hellcat",
        "relative_path": "hellcat_stock_accel.wav",
        "scenario_hint": "acceleration",
        "source_url": "https://www.youtube.com/watch?v=eyzGRhXp0do",
        "source_kind": "youtube_extracted",
        "source_log": None,
        "screening_note": "既有资料将标题车型识别为 Charger 候选，不足以绑定 Challenger Hellcat。",
    },
    {
        "recording_id": "hellcat_redeye_downshift",
        "vehicle_id": "hellcat",
        "relative_path": "hellcat_redeye_downshift.wav",
        "scenario_hint": "shift",
        "source_url": "https://www.youtube.com/watch?v=FvORN7EH2cc",
        "source_kind": "youtube_extracted",
        "source_log": None,
        "screening_note": "Redeye 换挡候选；不是已绑定 2022 Challenger 基线。",
    },
    {
        "recording_id": "hellcat_redeye_leave",
        "vehicle_id": "hellcat",
        "relative_path": "hellcat_redeye_leave.wav",
        "scenario_hint": "full_pull",
        "source_url": "https://www.youtube.com/watch?v=nnEaamqsieM",
        "source_kind": "youtube_extracted",
        "source_log": "hellcat_redeye_leave.download.log",
        "screening_note": "Redeye 离开/加速候选；工况与原厂状态未验证。",
    },
    {
        "recording_id": "hellcat_burble_tune",
        "vehicle_id": "hellcat",
        "relative_path": "hellcat_burble_tune.wav",
        "scenario_hint": "afterfire",
        "source_url": "https://www.youtube.com/watch?v=qiopd-QP2PE",
        "source_kind": "youtube_extracted",
        "source_log": "hellcat_burble_tune.download.log",
        "screening_note": "Burble tune 候选，明确不能作为原厂调音标定目标。",
    },
    {
        "recording_id": "rx7_fd_13brew",
        "vehicle_id": "rx7_fd",
        "relative_path": "rx7_fd_13brew.wav",
        "scenario_hint": "acceleration",
        "source_url": "https://www.youtube.com/watch?v=Thh69Wc5uco",
        "source_kind": "youtube_extracted",
        "source_log": "rx7_fd_13brew.download.log",
        "screening_note": "13B 双涡轮候选；具体年份、市场、原厂排气、视角与 RPM 未验证。",
    },
    {
        "recording_id": "aventador_lp700_accel",
        "vehicle_id": "aventador_lp700",
        "relative_path": "aventador_lp700_accel.wav",
        "scenario_hint": "acceleration",
        "source_url": "https://www.youtube.com/watch?v=kroFvboz7Bo",
        "source_kind": "youtube_extracted",
        "source_log": "aventador_lp700_accel.download.log",
        "screening_note": "加速候选；来源日志无车型/原厂/视角/RPM 证据。",
    },
    {
        "recording_id": "c63_w204_performance_accel",
        "vehicle_id": "c63_w204",
        "relative_path": "c63_w204_performance_accel.wav",
        "scenario_hint": "acceleration",
        "source_url": None,
        "source_kind": "local_unverified",
        "source_log": None,
        "screening_note": "本地文件但没有可审计来源、授权或车辆工况元数据。",
    },
    {
        "recording_id": "c63_w204_close_downshift",
        "vehicle_id": "c63_w204",
        "relative_path": "c63_w204_close_downshift.wav",
        "scenario_hint": "shift",
        "source_url": "https://www.youtube.com/watch?v=8GsqVnLEnwY",
        "source_kind": "youtube_extracted",
        "source_log": "c63_w204_close_downshift.download.log",
        "screening_note": "换挡候选；车型改款、原厂状态、麦克风位置与 RPM 未验证。",
    },
    {
        "recording_id": "c63_w204_headers_backfire",
        "vehicle_id": "c63_w204",
        "relative_path": "c63_w204_headers_backfire.wav",
        "scenario_hint": "afterfire",
        "source_url": None,
        "source_kind": "local_unverified",
        "source_log": None,
        "screening_note": "headers/backfire 暗示改装排气，不能作为原厂 C63 标定目标。",
    },
    {
        "recording_id": "gtr_r35_nismo_accel",
        "vehicle_id": "gtr_r35",
        "relative_path": "gtr_r35_nismo_accel.wav",
        "scenario_hint": "acceleration",
        "source_url": None,
        "source_kind": "local_unverified",
        "source_log": None,
        "screening_note": "Nismo 候选不是冻结的 2007 原厂基线，来源与权限未验证。",
    },
    {
        "recording_id": "gtr_r35_tomei_close",
        "vehicle_id": "gtr_r35",
        "relative_path": "gtr_r35_tomei_close.wav",
        "scenario_hint": "afterfire",
        "source_url": "https://www.youtube.com/watch?v=uCnpzelFwjM",
        "source_kind": "youtube_extracted",
        "source_log": "gtr_r35_tomei_close.download.log",
        "screening_note": "Tomei 改装排气近场候选，不能替代原厂 R35 参考。",
    },
    {
        "recording_id": "gtr_r35_tuned_backfire",
        "vehicle_id": "gtr_r35",
        "relative_path": "gtr_r35_tuned_backfire.wav",
        "scenario_hint": "afterfire",
        "source_url": None,
        "source_kind": "local_unverified",
        "source_log": None,
        "screening_note": "tuned backfire 候选，改装状态与来源不明。",
    },
    {
        "recording_id": "lfa_full_accel",
        "vehicle_id": "lfa",
        "relative_path": "lfa_full_accel.wav",
        "scenario_hint": "full_pull",
        "source_url": "https://www.youtube.com/watch?v=bpv7N8smafY",
        "source_kind": "youtube_extracted",
        "source_log": "lfa_full_accel.download.log",
        "screening_note": "LFA 加速候选；年份、原厂状态、视角与同步 RPM 未验证。",
    },
    {
        "recording_id": "supra_jza80_stock",
        "vehicle_id": "supra_jza80",
        "relative_path": "supra_jza80_stock.wav",
        "scenario_hint": "acceleration",
        "source_url": "https://www.youtube.com/watch?v=aVY14pGi_LY",
        "source_kind": "youtube_extracted",
        "source_log": "supra_jza80_stock.download.log",
        "screening_note": "Stock 声称候选；具体 JZA80 RZ 身份、视角与 RPM 未验证。",
    },
)

_MISSING_R1 = (
    "legal_permission",
    "exact_vehicle_trim",
    "stock_exhaust_confirmation",
    "synchronized_rpm_trace",
    "load_throttle_trace",
    "gear_shift_trace",
    "microphone_position",
    "recording_device_agc_contract",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wav_metadata(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        if wav.getcomptype() != "NONE":
            raise ValueError(f"compressed WAV is not accepted: {path}")
        frames = wav.getnframes()
        sample_rate_hz = wav.getframerate()
        return {
            "container": "WAV",
            "codec": "PCM",
            "channels": wav.getnchannels(),
            "sample_rate_hz": sample_rate_hz,
            "sample_width_bits": wav.getsampwidth() * 8,
            "frames": frames,
            "duration_s": round(frames / sample_rate_hz, 6) if sample_rate_hz else None,
        }


def _recording_record(media_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = media_root / spec["relative_path"]
    source_log = media_root / spec["source_log"] if spec.get("source_log") else None
    present = path.is_file()
    audio = None
    sha256 = None
    error = None
    if present:
        try:
            audio = _wav_metadata(path)
            sha256 = _sha256(path)
        except (OSError, ValueError, wave.Error) as exc:
            error = str(exc)
    missing = list(_MISSING_R1)
    if spec.get("source_url") is None:
        missing.append("source_url_or_controlled_alias")
    if error:
        missing.append("readable_uncompressed_pcm_wav")
    if not present:
        missing.append("raw_audio_file")
    missing = sorted(set(missing))
    return {
        "reference_id": f"q:{spec['recording_id']}",
        "recording_id": spec["recording_id"],
        "vehicle_id": spec["vehicle_id"],
        "vehicle_name_zh": VEHICLE_NAMES_ZH[spec["vehicle_id"]],
        "relative_path": spec["relative_path"],
        "external_path": str(path),
        "file_present": present,
        "sha256": sha256,
        "audio": audio,
        "read_error": error,
        "scenario": spec["scenario_hint"],
        "scenario_hint": spec["scenario_hint"],
        "scenario_confidence": "filename_or_prior_note_only",
        "provenance": {
            "source_url": spec.get("source_url"),
            "source_url_sha256": hashlib.sha256(spec["source_url"].encode("utf-8")).hexdigest() if spec.get("source_url") else None,
            "source_kind": spec["source_kind"],
            "source_log_path": str(source_log) if source_log else None,
            "source_log_sha256": _sha256(source_log) if source_log and source_log.is_file() else None,
            "legal_permission": "UNVERIFIED",
            "rights_evidence": "MISSING",
            "stock_identity": "UNVERIFIED",
            "microphone_perspective": "UNKNOWN",
            "recording_device_agc": "UNKNOWN",
            "screening_note_zh": spec["screening_note"],
            "raw_media_stored_outside_git": True,
        },
        "evidence": {
            "level": "R3",
            "use_policy": "qualitative_only",
            "r1_eligible": False,
            "r2_eligible": False,
            "automatic_tuning_eligible": False,
            "reason": "缺少可审计授权、精确车辆/原厂证据和同步状态数据；仅可作定性参考。",
        },
        "required_missing": missing,
        "analysis_contract": {
            "analysis_signal": "unaltered_analysis_signal",
            "rpm_state_status": "MISSING_RPM_STATE",
            "estimated_rpm_status": "NOT_ATTEMPTED",
            "load_throttle_status": "MISSING",
            "gear_shift_status": "MISSING",
            "channel_policy": "recorded_channels_preserved_until_explicit_review",
            "loudness_matched_audition_signal": "NOT_CREATED",
        },
    }


def _unique(items: Iterable[str]) -> list[str]:
    return sorted(set(items))


def _unmapped_external_media(
    media_root: Path,
    catalog: Iterable[dict[str, Any]],
    *,
    audit_reason: str | None = None,
) -> list[dict[str, Any]]:
    known = {str(item["relative_path"]).replace("\\", "/") for item in catalog}
    rows = []
    for path in sorted(media_root.rglob("*")) if media_root.is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in {".wav", ".flac", ".mp3", ".m4a", ".ogg"}:
            continue
        relative = path.relative_to(media_root).as_posix()
        if relative in known:
            continue
        rows.append({
            "audit_root": str(media_root),
            "relative_path": relative,
            "external_path": str(path),
            "sha256": _sha256(path),
            "media_kind": path.suffix.lower().lstrip("."),
            "status": "UNMAPPED_NOT_REGISTERED",
            "use_policy": "DO_NOT_ANALYZE_OR_TUNE",
            "reason": audit_reason or "本轮目录审计发现但没有车型/工况/授权合同，保持未登记。",
        })
    return rows


def build_evidence_matrix(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_vehicle: dict[str, list[dict[str, Any]]] = {vehicle: [] for vehicle in ALL_VEHICLES}
    for record in records:
        by_vehicle.setdefault(record["vehicle_id"], []).append(record)
    vehicles = []
    for vehicle_id in ALL_VEHICLES:
        rows = sorted(by_vehicle.get(vehicle_id, []), key=lambda item: item["recording_id"])
        vehicles.append(
            {
                "vehicle_id": vehicle_id,
                "vehicle_name_zh": VEHICLE_NAMES_ZH[vehicle_id],
                "anchor_vehicle": vehicle_id in ANCHOR_VEHICLES,
                "recording_count": len(rows),
                "present_count": sum(1 for row in rows if row["file_present"]),
                "r1_eligible_count": sum(1 for row in rows if row["evidence"]["r1_eligible"]),
                "r2_eligible_count": sum(1 for row in rows if row["evidence"]["r2_eligible"]),
                "evidence_levels": {
                    level: sum(1 for row in rows if row["evidence"]["level"] == level)
                    for level in ("R1", "R2", "R3")
                },
                "scenario_hints": sorted({row["scenario_hint"] for row in rows}),
                "missing_requirements": _unique(
                    missing for row in rows for missing in row["required_missing"]
                ),
                "status": "WAITING_FOR_REAL_REFERENCE_DATA",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "Q",
        "vehicles": vehicles,
        "qualification_rule": "只有合法授权、精确车辆/原厂证据、外部后置视角和同步 RPM/state 才能成为 R1。",
        "overall_r1_ready": all(item["r1_eligible_count"] > 0 for item in vehicles),
    }


def _normalise_external_raw_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt the raw-audio intake schema to the canonical Stage-Q record."""

    recording_id = str(record.get("recording_id") or "").strip()
    vehicle_id = str(record.get("vehicle_id") or "").strip()
    if not recording_id or vehicle_id not in ALL_VEHICLES:
        raise ValueError(f"raw reference record must name a supported vehicle: {recording_id or '<missing>'}/{vehicle_id or '<missing>'}")
    row = dict(record)
    scenario = str(record.get("scenario") or record.get("scenario_hint") or "unknown").strip()
    row["scenario"] = scenario
    row["scenario_hint"] = scenario
    row.setdefault("reference_id", f"q:{recording_id}")
    row.setdefault("vehicle_name_zh", VEHICLE_NAMES_ZH[vehicle_id])
    row.setdefault("relative_path", Path(str(record.get("external_path") or recording_id)).name)
    row.setdefault("external_path", "")
    row.setdefault("file_present", False)
    row.setdefault("sha256", None)
    row.setdefault("audio", None)
    provenance = record.get("provenance")
    row["provenance"] = dict(provenance) if isinstance(provenance, Mapping) else {}
    analysis_defaults = {
        "analysis_signal": "unaltered_analysis_signal",
        "rpm_state_status": "MISSING_RPM_STATE",
        "estimated_rpm_status": "NOT_ATTEMPTED",
        "load_throttle_status": "MISSING",
        "gear_shift_status": "MISSING",
    }
    analysis_contract = record.get("analysis_contract")
    merged_analysis = dict(analysis_defaults)
    if isinstance(analysis_contract, Mapping):
        merged_analysis.update(analysis_contract)
    row["analysis_contract"] = merged_analysis
    evidence_value = record.get("evidence")
    evidence = dict(evidence_value) if isinstance(evidence_value, Mapping) else {}
    evidence.setdefault("level", "R3")
    evidence.setdefault("r1_eligible", False)
    evidence.setdefault("r2_eligible", False)
    evidence.setdefault("automatic_tuning_eligible", False)
    evidence.setdefault("order_hard_gate", bool(evidence["r1_eligible"]))
    evidence.setdefault("reason", "外部原始录音入库记录未通过完整 Stage Q 证据门。")
    row["evidence"] = evidence
    missing = record.get("required_missing")
    if missing is None:
        missing = (evidence.get("r1_gate") or {}).get("missing", [])
    row["required_missing"] = sorted({str(item) for item in (missing or [])})
    return row


def _read_external_raw_manifests(raw_reference_manifests: Iterable[Path | Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    roots: list[str] = []
    for source in raw_reference_manifests:
        if isinstance(source, Mapping):
            payload = source
        else:
            path = Path(source)
            payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping) or not isinstance(payload.get("records"), list):
            raise ValueError("raw reference manifest must contain a records array")
        for record in payload["records"]:
            if not isinstance(record, Mapping):
                raise ValueError("raw reference manifest records must be objects")
            records.append(_normalise_external_raw_record(record))
        for key in ("allowed_download_root", "raw_media_root"):
            value = payload.get(key)
            if value and str(value) not in roots:
                roots.append(str(value))
    return records, roots


def build_inventory(
    media_root: Path,
    catalog: Iterable[dict[str, Any]] = CATALOG,
    additional_media_roots: Iterable[Path] = DEFAULT_ADDITIONAL_MEDIA_ROOTS,
    raw_reference_manifests: Iterable[Path | Mapping[str, Any]] = (),
) -> dict[str, Any]:
    media_root = Path(media_root)
    catalog = tuple(catalog)
    additional_roots = tuple(Path(root) for root in additional_media_roots if Path(root) != media_root)
    records = [_recording_record(media_root, spec) for spec in catalog]
    raw_records, raw_roots = _read_external_raw_manifests(raw_reference_manifests)
    by_id = {record["recording_id"]: record for record in records}
    by_id.update({record["recording_id"]: record for record in raw_records})
    records = list(by_id.values())
    records.sort(key=lambda item: item["recording_id"])
    matrix = build_evidence_matrix(records)
    status = "REAL_REFERENCE_DATASET_READY" if matrix["overall_r1_ready"] else "REAL_REFERENCE_DATASET_LIMITED"
    blockers: list[str] = []
    if not any(record["evidence"]["r1_eligible"] for record in records):
        blockers.append("没有任何记录同时通过合法来源、精确车型和同步状态的 R1 资格；不能执行 R1 阶次资格或自动调参。")
    if not all(item["r1_eligible_count"] > 0 for item in matrix["vehicles"]):
        blockers.append("八车型尚未全部取得至少一条 R1 参考；Stage T 锚点和其余车辆交接不能启动。")
    if not all(item["r1_eligible_count"] > 0 for item in matrix["vehicles"] if item["anchor_vehicle"]):
        blockers.append("Ferrari 458、Hellcat、RX-7 FD 三个锚点尚未全部通过 R1。")
    if any(record["evidence"]["level"] in {"R2", "R3"} for record in records):
        blockers.append("公开/改装或缺状态候选仍只能作 R2/R3 参考，不能替代原厂 R1。")
    if not blockers:
        blockers.append("无 Stage Q 阻塞项；继续执行 Stage R。")
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "Q",
        "status": status,
        "stop_state": "WAITING_FOR_REAL_REFERENCE_DATA" if status != "REAL_REFERENCE_DATASET_READY" else "READY_FOR_STAGE_R",
        "raw_media_root": str(media_root),
        "audited_external_roots": [str(media_root), *(str(root) for root in additional_roots), *raw_roots],
        "raw_audio_policy": "external_only_not_in_git",
        "vehicles": list(ALL_VEHICLES),
        "anchor_vehicles": list(ANCHOR_VEHICLES),
        "recordings": records,
        "unmapped_external_media": [
            *_unmapped_external_media(media_root, catalog),
            *(
                row
                for root in additional_roots
                for row in _unmapped_external_media(
                    root,
                    (),
                    audit_reason="额外相关目录审计发现但没有当前 Q 登记、授权或同步状态合同，保持未登记。",
                )
            ),
        ],
        "evidence_matrix": matrix,
        "blockers": blockers,
        "next_input_contract": {
            "audio": "合法原始 WAV/FLAC；保留未经增益/EQ/AGC 的分析信号。",
            "vehicle": "车型、年份、市场、配置和原厂/改装状态。",
            "state": "与音频同步的 RPM、Load/Throttle、Gear/shift 和场景边界。",
            "capture": "麦克风位置、采样率、通道、录音设备和 AGC/处理链。",
            "rights": "明确可用于本地分析、派生指标和 Jovi 听审的授权记录。",
        },
    }


def _scenario_segments(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    segments = []
    for record in inventory["recordings"]:
        duration = (record.get("audio") or {}).get("duration_s")
        state = record.get("state_bindings") or {}
        window = record.get("time_window") or state.get("time_window")
        if isinstance(window, Mapping) and window.get("start_s") is not None and window.get("end_s") is not None:
            start_s = float(window["start_s"])
            end_s = float(window["end_s"])
            status = "R1_TIMESTAMP_BOUND_WINDOW" if record["evidence"]["r1_eligible"] else "TIMESTAMP_BOUND_NOT_R1"
            source = "external_state_time_window"
            usable = bool(record["evidence"]["r1_eligible"])
        else:
            start_s = 0.0
            end_s = duration
            status = "UNQUALIFIED_COARSE_WINDOW"
            source = "filename_or_prior_note_only"
            usable = False
        segments.append(
            {
                "recording_id": record["recording_id"],
                "vehicle_id": record["vehicle_id"],
                "scenario": record["scenario_hint"],
                "start_s": start_s,
                "end_s": end_s,
                "status": status,
                "source": source,
                "usable_for_order_or_tuning": usable,
            }
        )
    return segments


def _rpm_bindings(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = []
    for record in inventory["recordings"]:
        state = record.get("state_bindings") or {}
        synced = bool(record["evidence"]["r1_eligible"]) and record.get("analysis_contract", {}).get("rpm_state_status") == "SYNCED"
        bindings.append(
            {
                "recording_id": record["recording_id"],
                "vehicle_id": record["vehicle_id"],
                "status": "SYNCED" if synced else "MISSING_RPM_STATE",
                "rpm_source": state.get("rpm_trace_path") if synced else None,
                "trace_sha256": state.get("trace_sha256") if synced else None,
                "raw_trace_sha256": state.get("raw_trace_sha256") if synced else None,
                "load_throttle_source": state.get("load_throttle_trace_path") if synced else None,
                "gear_shift_source": state.get("gear_shift_trace_path") if synced else None,
                "time_window": state.get("time_window") if synced else None,
                "qualification": "R1_SYNCED_STATE" if synced else "ESTIMATED_RPM_NOT_QUALIFIED",
            }
        )
    return bindings


def _render_report(inventory: dict[str, Any]) -> str:
    r1_count = sum(1 for record in inventory["recordings"] if record["evidence"]["r1_eligible"])
    if r1_count:
        conclusion = f"当前已有 `{r1_count}` 条 R1 记录进入 Stage Q；只有通过 Stage R MATLAB/MoSQITo 收据和 Jovi 人耳反馈后，才允许参数建议或调音。其余记录仍按 R2/R3 限制处理。"
    else:
        conclusion = "本轮只审计外部本地参考，不把公开或来源不完整的音频伪装成 R1 真实标定数据。原始音频没有复制进 Git；仓库只保存路径指针、SHA-256、音频容器信息和缺口。当前没有任何记录满足 R1，因此 Stage R 的真实阶次基线、自动参数建议和调音闭环不能启动。"
    lines = [
        "# S12 Stage Q 真实参考数据报告",
        "",
        f"状态：`{inventory['status']}` / `{inventory['stop_state']}`",
        "",
        "## 结论",
        "",
        conclusion,
        "",
        "## 车型覆盖",
        "",
        "| 车型 | 记录数 | 可读取 | R1 | R2 | 当前状态 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for vehicle in inventory["evidence_matrix"]["vehicles"]:
        lines.append(
            f"| {vehicle['vehicle_name_zh']} | {vehicle['recording_count']} | {vehicle['present_count']} | {vehicle['r1_eligible_count']} | {vehicle['r2_eligible_count']} | `{vehicle['status']}` |"
        )
    next_state = (
        "全部八车型已经有 R1 记录，可进入 Stage R；仍需逐条取得 MATLAB/MoSQITo 收据和 Jovi 人耳反馈。"
        if inventory["status"] == "REAL_REFERENCE_DATASET_READY"
        else "在所有必需 R1 资料到位之前，Stage Q 保持 `REAL_REFERENCE_DATASET_LIMITED / WAITING_FOR_REAL_REFERENCE_DATA`；不会把 R2/R3 结果升级为真实差异合格报告或修改车型参数。"
    )
    lines.extend(
        [
            "",
            "## 外部目录审计",
            "",
            "本轮已审计以下外部媒体目录；未登记音频只保留路径和 SHA-256，不进入分析、听审包或调音：",
            *[f"- `{root}`" for root in inventory.get("audited_external_roots", [])],
            "",
            "## 记录审计",
            "",
            "| 记录 | 场景提示 | 格式 | 时长 | SHA-256 前 12 位 | 证据等级 | 可用于调音 |",
            "| --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for record in inventory["recordings"]:
        audio = record.get("audio") or {}
        fmt = f"{audio.get('sample_rate_hz', '—')} Hz / {audio.get('channels', '—')} ch / {audio.get('sample_width_bits', '—')} bit" if audio else "不可读"
        duration = f"{audio.get('duration_s', 0):.3f}s" if audio.get("duration_s") is not None else "—"
        sha = record.get("sha256")
        use_policy = "Stage R 待收据" if record["evidence"]["r1_eligible"] else "否"
        lines.append(
            f"| `{record['recording_id']}` | {record['scenario_hint']} | {fmt} | {duration} | `{sha[:12] if sha else '—'}` | `{record['evidence']['level']}` | {use_policy} |"
        )
    lines.extend(
        [
            "",
            "## 不能进入 R1/R2 的原因",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in inventory["blockers"])
    lines.extend(
        [
            "",
            f"目录中另发现 `{len(inventory.get('unmapped_external_media', []))}` 个未登记音频文件；它们只记录在 manifest 的 `unmapped_external_media`，不进入分析或调音。",
        ]
    )
    lines.extend(
        [
            "",
            "## 后续必须补齐的输入",
            "",
            "1. 有权使用的真实原始录音；不得只提供公开视频链接或无法确认权限的下载文件。",
            "2. 精确车型/年份/市场/配置、原厂或改装状态及麦克风位置。",
            "3. 与音频同步的 RPM；同时提供 Load/Throttle、Gear/shift 和场景起止点。",
            "4. 录音设备、采样率、通道及 AGC/后处理说明。",
            "5. Jovi 确认允许用于本地分析、派生特征和听审的授权记录。",
            "",
            next_state,
            "",
            "边界：所有产物继续标记 `synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_stage_q_outputs(inventory: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    """Write Stage Q evidence without copying raw audio."""

    out_dir = Path(out_dir)
    database = out_dir / "reference_database_v2"
    database.mkdir(parents=True, exist_ok=True)
    _write_json(database / "reference_manifest.json", inventory)
    _write_json(database / "reference_evidence_matrix.json", inventory["evidence_matrix"])
    _write_json(database / "scenario_segments.json", _scenario_segments(inventory))
    _write_json(database / "rpm_state_bindings.json", _rpm_bindings(inventory))
    provenance_dir = database / "provenance"
    derived_dir = database / "derived_features"
    for record in inventory["recordings"]:
        _write_json(provenance_dir / f"{record['recording_id']}.json", record["provenance"] | {
            "recording_id": record["recording_id"],
            "vehicle_id": record["vehicle_id"],
            "sha256": record["sha256"],
            "external_path": record["external_path"],
        })
        _write_json(derived_dir / f"{record['recording_id']}.json", {
            "recording_id": record["recording_id"],
            "vehicle_id": record["vehicle_id"],
            "status": "NOT_COMPUTED_UNQUALIFIED",
            "reason": "没有通过 Stage Q 证据门；不会将未授权/未对齐音频的特征提升为标定目标。",
            "audio_header": record["audio"],
        })
    report_path = out_dir / "S12_Stage_Q_Real_Reference_Data_Report.md"
    report_path.write_text(_render_report(inventory), encoding="utf-8", newline="\n")
    return {
        "manifest": database / "reference_manifest.json",
        "evidence_matrix": database / "reference_evidence_matrix.json",
        "scenario_segments": database / "scenario_segments.json",
        "rpm_state_bindings": database / "rpm_state_bindings.json",
        "report": report_path,
    }


__all__ = [
    "ALL_VEHICLES",
    "ANCHOR_VEHICLES",
    "CATALOG",
    "DEFAULT_ADDITIONAL_MEDIA_ROOTS",
    "SCHEMA_VERSION",
    "build_evidence_matrix",
    "build_inventory",
    "write_stage_q_outputs",
]
