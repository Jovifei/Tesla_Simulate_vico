"""Fail-closed intake for Jovi-provided vehicle video URLs.

The URL itself is only a discovery/download input.  This module downloads
media outside Git, extracts an unaltered PCM analysis signal, records hashes
and probe metadata, and classifies the result as R2/R3 unless the caller has
also supplied the complete Stage-Q capture/state contract.  It never starts
MATLAB, runs tuning, or promotes a compressed video derivative to R1 without
an explicit raw-audio receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .qualification import qualify_r1_reference, qualify_r2_reference


SCHEMA_VERSION = "s12-stage-q-url-intake-v1"
ALLOWED_DOWNLOAD_ROOT = Path(r"E:\Claude_allow\Download")
_VIDEO_EXTENSIONS = {".avi", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
_LOSSY_AUDIO_CODECS = {"aac", "ac3", "eac3", "mp3", "opus", "vorbis"}


class UrlIntakeError(ValueError):
    """Raised when a URL intake request cannot be safely executed."""


def validate_source_url(value: str) -> str:
    """Accept only ordinary HTTP(S) URLs without embedded credentials."""

    url = str(value).strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise UrlIntakeError("source URL must use http:// or https:// and include a host")
    if parsed.username or parsed.password:
        raise UrlIntakeError("source URL must not contain embedded credentials")
    return url


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> Path:
    root_resolved = Path(root).resolve()
    path_resolved = Path(path).resolve()
    if path_resolved != root_resolved and root_resolved not in path_resolved.parents:
        raise UrlIntakeError(f"path must remain under approved download root: {path_resolved}")
    return path_resolved


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise UrlIntakeError(f"required tool is not on PATH: {name}")
    return path


def _safe_stem(index: int, url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    host = re.sub(r"[^a-z0-9]+", "-", urlparse(url).netloc.lower()).strip("-") or "source"
    return f"{index:02d}-{host[:24]}-{digest}"


def _probe(video_path: Path) -> dict[str, Any]:
    command = [
        _tool("ffprobe"),
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _audio_stream(probe: Mapping[str, Any]) -> dict[str, Any]:
    streams = [item for item in probe.get("streams", []) if item.get("codec_type") == "audio"]
    if not streams:
        raise UrlIntakeError("downloaded video has no audio stream")
    return dict(streams[0])


def _extract_wav(video_path: Path, wav_path: Path) -> None:
    command = [
        _tool("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-map",
        "0:a:0",
        "-vn",
        "-c:a",
        "pcm_s24le",
        str(wav_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _rpm_tokens(text: str) -> list[int]:
    """Return only plausible numeric OCR tokens; they remain estimates."""

    values = []
    for raw in re.findall(r"(?<!\d)(\d{3,5})(?!\d)", text):
        value = int(raw)
        if 300 <= value <= 12_000 and value not in values:
            values.append(value)
    return values[:32]


def scan_video_frames(
    video_path: Path,
    frame_root: Path,
    *,
    interval_s: float = 2.0,
    max_frames: int = 30,
) -> dict[str, Any]:
    """Sample frames and optionally OCR them without granting RPM qualification."""

    if interval_s <= 0 or max_frames < 1:
        raise UrlIntakeError("frame interval must be positive and max_frames must be >= 1")
    frame_root.mkdir(parents=True, exist_ok=True)
    pattern = frame_root / "frame-%04d.jpg"
    command = [
        _tool("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{interval_s:g}",
        "-frames:v",
        str(max_frames),
        "-q:v",
        "3",
        str(pattern),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    frames = sorted(frame_root.glob("frame-*.jpg"))
    if not frames:
        return {
            "status": "NO_FRAMES_EXTRACTED",
            "interval_s": interval_s,
            "frame_count": 0,
            "frames": [],
            "ocr_status": "NOT_ATTEMPTED",
            "ocr_text": [],
            "rpm_candidates": [],
            "rpm_status": "MISSING_RPM_STATE",
        }
    tesseract = shutil.which("tesseract")
    ocr_text: list[dict[str, Any]] = []
    if tesseract:
        for frame in frames:
            try:
                result = subprocess.run(
                    [tesseract, str(frame), "stdout", "--psm", "11"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                text = " ".join(result.stdout.split())[:500]
            except (OSError, subprocess.TimeoutExpired) as exc:
                text = f"OCR_ERROR:{type(exc).__name__}"
            ocr_text.append({"frame": str(frame), "text": text})
        candidates = _rpm_tokens(" ".join(row["text"] for row in ocr_text))
        ocr_status = "COMPLETED"
    else:
        candidates = []
        ocr_status = "NOT_AVAILABLE_TESSERACT_MISSING"
    return {
        "status": "FRAMES_EXTRACTED",
        "interval_s": interval_s,
        "frame_count": len(frames),
        "frames": [{"path": str(frame), "sha256": _sha256(frame)} for frame in frames],
        "ocr_status": ocr_status,
        "ocr_text": ocr_text,
        "rpm_candidates": candidates,
        "rpm_status": "ESTIMATED_FROM_VIDEO_NOT_QUALIFIED" if candidates else "MISSING_RPM_STATE",
        "qualification": "NOT_R1",
    }


def _find_downloaded_video(output: str, stem: str, root: Path) -> Path:
    printed = [Path(line.strip()) for line in output.splitlines() if line.strip()]
    for candidate in reversed(printed):
        if candidate.is_file() and candidate.suffix.lower() in _VIDEO_EXTENSIONS:
            return _inside(root, candidate)
    candidates = sorted(
        path
        for path in root.glob(f"{stem}.*")
        if path.is_file() and path.suffix.lower() in _VIDEO_EXTENSIONS
    )
    if not candidates:
        raise UrlIntakeError(f"yt-dlp completed but no video file was found for {stem}")
    return candidates[-1]


def _download_video(url: str, root: Path, stem: str) -> tuple[Path, Path, str]:
    yt_dlp = _tool("yt-dlp")
    template = root / f"{stem}.%(ext)s"
    log_path = root / f"{stem}.download.log"
    command = [
        yt_dlp,
        "--no-playlist",
        "--no-part",
        "--restrict-filenames",
        "--write-info-json",
        "--write-description",
        "--print",
        "after_move:filepath",
        "-f",
        "bestvideo*+bestaudio/best",
        "-o",
        str(template),
        url,
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    log_path.write_text(
        "COMMAND: " + json.dumps(command, ensure_ascii=False) + "\n\nSTDOUT:\n" + result.stdout + "\nSTDERR:\n" + result.stderr,
        encoding="utf-8",
        newline="\n",
    )
    video_path = _find_downloaded_video(result.stdout, stem, root)
    return video_path, log_path, result.stdout


def _default_state_contract() -> dict[str, Any]:
    return {
        "rpm_state_status": "MISSING_RPM_STATE",
        "estimated_rpm_status": "NOT_ATTEMPTED",
        "load_throttle_status": "MISSING",
        "gear_shift_status": "MISSING",
        "trace_paths": {},
    }


def build_video_record(
    *,
    source_url: str,
    video_path: Path,
    wav_path: Path,
    probe: Mapping[str, Any],
    download_log_path: Path | None = None,
    vehicle_id: str | None = None,
    scenario: str | None = None,
    legal_permission: str = "UNVERIFIED",
    rights_evidence: str | None = None,
    stock_identity: str = "UNVERIFIED",
    microphone_perspective: str = "UNKNOWN",
    recording_device_agc: str = "UNKNOWN",
    state_contract: Mapping[str, Any] | None = None,
    raw_audio_confirmed: bool = False,
    visual_scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an auditable record without granting tuning authority."""

    source_url = validate_source_url(source_url)
    video_path = Path(video_path)
    wav_path = Path(wav_path)
    audio = _audio_stream(probe)
    state = _default_state_contract() | dict(state_contract or {})
    visual = dict(visual_scan or {"status": "NOT_REQUESTED", "rpm_candidates": [], "rpm_status": "MISSING_RPM_STATE"})
    if visual.get("rpm_candidates") and state.get("rpm_state_status") != "SYNCED":
        state["estimated_rpm_status"] = "ESTIMATED_FROM_VIDEO_NOT_QUALIFIED"
    record = {
        "schema_version": SCHEMA_VERSION,
        "reference_id": "q:url:" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16],
        "recording_id": "url_" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16],
        "vehicle_id": vehicle_id,
        "scenario": scenario,
        "source_url": source_url,
        "video_path": str(video_path),
        "wav_path": str(wav_path),
        "video_sha256": _sha256(video_path) if video_path.is_file() else None,
        "wav_sha256": _sha256(wav_path) if wav_path.is_file() else None,
        "download_log_path": str(download_log_path) if download_log_path else None,
        "video_probe": dict(probe),
        "audio_stream": audio,
        "visual_state_scan": visual,
        "provenance": {
            "source_kind": "user_provided_url_video_extracted",
            "legal_permission": legal_permission,
            "rights_evidence": rights_evidence,
            "stock_identity": stock_identity,
            "microphone_perspective": microphone_perspective,
            "recording_device_agc": recording_device_agc,
            "raw_audio_confirmed": bool(raw_audio_confirmed),
            "raw_media_stored_outside_git": True,
        },
        "analysis_contract": {
            "analysis_signal": "unaltered_extracted_pcm_signal",
            "rpm_state_status": state.get("rpm_state_status", "MISSING_RPM_STATE"),
            "estimated_rpm_status": state.get("estimated_rpm_status", "NOT_ATTEMPTED"),
            "load_throttle_status": state.get("load_throttle_status", "MISSING"),
            "gear_shift_status": state.get("gear_shift_status", "MISSING"),
            "trace_paths": dict(state.get("trace_paths", {})),
            "loudness_matched_audition_signal": "NOT_CREATED",
        },
    }
    r1_gate = qualify_r1_reference(record | {"file_present": wav_path.is_file(), "sha256": record["wav_sha256"]})
    r2_gate = qualify_r2_reference(
        record
        | {
            "file_present": wav_path.is_file(),
            "sha256": record["wav_sha256"],
            "vehicle_id": vehicle_id,
            "scenario": scenario,
        }
    )
    lossy_derivative = str(audio.get("codec_name", "")).lower() in _LOSSY_AUDIO_CODECS
    r1_promoted = bool(r1_gate["eligible"] and raw_audio_confirmed and not lossy_derivative)
    if r1_promoted:
        level = "R1"
    elif r2_gate["eligible"]:
        level = "R2"
    else:
        level = "R3"
    record["evidence"] = {
        "level": level,
        "r1_gate": r1_gate,
        "r2_gate": r2_gate,
        "r1_eligible": r1_promoted,
        "r2_eligible": bool(r2_gate["eligible"]),
        "automatic_tuning_eligible": False,
        "order_hard_gate": False if level != "R1" else True,
        "lossy_video_audio_derivative": lossy_derivative,
        "reason": (
            "R1 已通过完整 Stage-Q 合同。"
            if r1_promoted
            else "URL 视频抽取音频默认不是原始录音；缺少完整同步状态或 raw-audio 收据时保持 R2/R3，不能进入阶次自动调参。"
        ),
    }
    return record


def render_intake_report(manifest: Mapping[str, Any]) -> str:
    """Render a Chinese, fail-closed intake report."""

    lines = [
        "# S12 URL 真实声浪输入审计",
        "",
        f"状态：`{manifest.get('status', 'UNKNOWN')}`",
        "",
        "本报告只记录 Jovi 提供的网址下载、视频探测、音频抽取和证据分级。没有明确授权、精确车型/场景和同步状态时，结果不会升级为 R1，也不会启动 MATLAB、自动调参或 Profile Freeze。",
        "",
        "| 序号 | 记录 | 车型 | 工况 | 证据等级 | 视频 | 音频 | 关键限制 |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, record in enumerate(manifest.get("records", []), start=1):
        evidence = record.get("evidence", {})
        audio = record.get("audio_stream", {})
        lines.append(
            "| {index} | `{recording}` | `{vehicle}` | `{scenario}` | `{level}` | `{video_sha}` | `{rate} Hz/{channels} ch` | {reason} |".format(
                index=index,
                recording=record.get("recording_id", "—"),
                vehicle=record.get("vehicle_id") or "未绑定",
                scenario=record.get("scenario") or "未绑定",
                level=evidence.get("level", "ERROR"),
                video_sha=(record.get("video_sha256") or "—")[:12],
                rate=audio.get("sample_rate") or "—",
                channels=audio.get("channels") or "—",
                reason=evidence.get("reason") or record.get("error") or "—",
            )
        )
        visual = record.get("visual_state_scan", {})
        lines.append(
            f"  - 画面状态扫描：`{visual.get('status', 'NOT_REQUESTED')}`；OCR：`{visual.get('ocr_status', 'NOT_ATTEMPTED')}`；RPM 候选：`{visual.get('rpm_candidates', [])}`（仅估算，不具备 R1 资格）。"
        )
    lines.extend(
        [
            "",
            "## 后续门禁",
            "",
            "- `R3`：只做声音特征和来源筛查。",
            "- `R2`：只做频谱、响度、心理声学和主观瞬态比较；不做阶次硬门或自动调参。",
            "- `R1`：必须补齐合法原始录音、精确车型/原厂状态、同步 RPM/Load/Throttle/Gear/shift、麦位、录音设备/AGC 和授权收据；视频压缩派生音频默认不满足 raw-audio 收据。",
            "",
        ]
    )
    return "\n".join(lines)


def write_intake_outputs(manifest: Mapping[str, Any], output_root: Path) -> dict[str, Path]:
    output_root = _inside(ALLOWED_DOWNLOAD_ROOT, Path(output_root))
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "intake_manifest.json"
    report_path = output_root / "URL_Intake_Report.md"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_path.write_text(render_intake_report(manifest), encoding="utf-8", newline="\n")
    return {"manifest": manifest_path, "report": report_path}


def _process_url_spec(
    spec: Mapping[str, Any],
    *,
    index: int,
    output_root: Path,
    defaults: Mapping[str, Any],
    scan_frames: bool,
    frame_interval_s: float,
    max_frames: int,
) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise UrlIntakeError("each URL spec must be a JSON object")
    merged = dict(defaults)
    merged.update({key: value for key, value in spec.items() if value is not None})
    # Keep the JSON spelling aligned with the CLI while accepting the
    # internal record field used by the qualification gate.
    if "license_status" in spec and "legal_permission" not in spec:
        merged["legal_permission"] = spec["license_status"]
    if not merged.get("url"):
        raise UrlIntakeError("each URL spec must contain a non-empty url")
    url = validate_source_url(str(merged["url"]))
    stem = _safe_stem(index, url)
    try:
        video_path, log_path, _ = _download_video(url, output_root, stem)
        probe = _probe(video_path)
        wav_path = output_root / f"{stem}.analysis.wav"
        _extract_wav(video_path, wav_path)
        visual_scan = (
            scan_video_frames(video_path, output_root / f"{stem}.frames", interval_s=frame_interval_s, max_frames=max_frames)
            if scan_frames
            else {"status": "NOT_REQUESTED", "rpm_candidates": [], "rpm_status": "MISSING_RPM_STATE"}
        )
        return build_video_record(
            source_url=url,
            video_path=video_path,
            wav_path=wav_path,
            probe=probe,
            download_log_path=log_path,
            vehicle_id=merged.get("vehicle_id"),
            scenario=merged.get("scenario"),
            legal_permission=str(merged.get("legal_permission") or "UNVERIFIED"),
            rights_evidence=merged.get("rights_evidence"),
            stock_identity=str(merged.get("stock_identity", "UNVERIFIED")),
            microphone_perspective=str(merged.get("microphone_perspective", "UNKNOWN")),
            recording_device_agc=str(merged.get("recording_device_agc", "UNKNOWN")),
            state_contract=merged.get("state_contract"),
            raw_audio_confirmed=bool(merged.get("raw_audio_confirmed", False)),
            visual_scan=visual_scan,
        )
    except (OSError, UrlIntakeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {
            "recording_id": "url_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
            "source_url": url,
            "status": "DOWNLOAD_OR_PARSE_FAILED",
            "error": str(exc),
            "evidence": {"level": "R3", "r1_eligible": False, "r2_eligible": False, "automatic_tuning_eligible": False},
        }


def intake_url_specs(
    specs: Iterable[Mapping[str, Any]],
    *,
    output_root: Path,
    defaults: Mapping[str, Any] | None = None,
    scan_frames: bool = False,
    frame_interval_s: float = 2.0,
    max_frames: int = 30,
) -> dict[str, Any]:
    """Download a batch where each URL may override vehicle/scenario metadata."""

    output_root = _inside(ALLOWED_DOWNLOAD_ROOT, Path(output_root))
    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        try:
            records.append(
                _process_url_spec(
                    spec,
                    index=index,
                    output_root=output_root,
                    defaults=defaults or {},
                    scan_frames=scan_frames,
                    frame_interval_s=frame_interval_s,
                    max_frames=max_frames,
                )
            )
        except (TypeError, UrlIntakeError) as exc:
            records.append(
                {
                    "recording_id": f"url_spec_{index:02d}",
                    "status": "URL_SPEC_INVALID",
                    "error": str(exc),
                    "evidence": {"level": "R3", "r1_eligible": False, "r2_eligible": False, "automatic_tuning_eligible": False},
                }
            )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "URL_INTAKE_COMPLETE" if all("error" not in row for row in records) else "URL_INTAKE_PARTIAL_OR_FAILED",
        "download_root": str(output_root),
        "raw_media_policy": "external_only_not_in_git",
        "records": records,
        "automatic_tuning_eligible": False,
        "profile_freeze_authorized": False,
    }
    write_intake_outputs(manifest, output_root)
    return manifest


def intake_urls(
    urls: Iterable[str],
    *,
    output_root: Path,
    vehicle_id: str | None = None,
    scenario: str | None = None,
    legal_permission: str = "UNVERIFIED",
    rights_evidence: str | None = None,
    stock_identity: str = "UNVERIFIED",
    microphone_perspective: str = "UNKNOWN",
    recording_device_agc: str = "UNKNOWN",
    state_contract: Mapping[str, Any] | None = None,
    raw_audio_confirmed: bool = False,
    scan_frames: bool = False,
    frame_interval_s: float = 2.0,
    max_frames: int = 30,
) -> dict[str, Any]:
    return intake_url_specs(
        ({"url": url} for url in urls),
        output_root=output_root,
        defaults={
            "vehicle_id": vehicle_id,
            "scenario": scenario,
            "legal_permission": legal_permission,
            "rights_evidence": rights_evidence,
            "stock_identity": stock_identity,
            "microphone_perspective": microphone_perspective,
            "recording_device_agc": recording_device_agc,
            "state_contract": state_contract,
            "raw_audio_confirmed": raw_audio_confirmed,
        },
        scan_frames=scan_frames,
        frame_interval_s=frame_interval_s,
        max_frames=max_frames,
    )


def _timestamped_output_root() -> Path:
    return ALLOWED_DOWNLOAD_ROOT / ("s12-url-intake-" + datetime.now().strftime("%Y%m%d-%H%M%S"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载 Jovi 提供的视频网址并生成中文、fail-closed 的 S12 声浪输入审计")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--url", action="append", help="视频 URL；可重复指定")
    source_group.add_argument("--spec-json", type=Path, help="JSON 数组；每项至少含 url，可覆盖车型/工况/许可字段")
    parser.add_argument("--output-root", type=Path, default=None, help="输出目录，必须位于 E:\\Claude_allow\\Download")
    parser.add_argument("--vehicle-id", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--license-status", choices=("UNVERIFIED", "CONFIRMED"), default="UNVERIFIED")
    parser.add_argument("--rights-evidence", default=None, help="许可页面或授权收据路径；不提供则保持未验证")
    parser.add_argument("--stock-identity", choices=("UNVERIFIED", "VERIFIED_EXACT_TRIM"), default="UNVERIFIED")
    parser.add_argument("--microphone-perspective", choices=("UNKNOWN", "EXTERIOR_REAR"), default="UNKNOWN")
    parser.add_argument("--recording-device-agc", choices=("UNKNOWN", "DOCUMENTED_NO_AGC"), default="UNKNOWN")
    parser.add_argument("--state-contract-json", type=Path, default=None, help="可选状态合同 JSON；不会自动把估算 RPM 升级为同步 RPM")
    parser.add_argument("--scan-frames", action="store_true", help="按固定间隔抽帧并尝试 OCR；OCR 结果只作为估算线索")
    parser.add_argument("--frame-interval-s", type=float, default=2.0)
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--raw-audio-confirmed", action="store_true", help="仅在有原始音频收据时使用；视频抽取音频默认不满足")
    args = parser.parse_args(argv)
    if args.license_status == "CONFIRMED" and not args.rights_evidence:
        parser.error("--license-status CONFIRMED requires --rights-evidence")
    state_contract = None
    if args.state_contract_json is not None:
        try:
            loaded = json.loads(args.state_contract_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"--state-contract-json cannot be read as JSON: {exc}")
        if not isinstance(loaded, dict):
            parser.error("--state-contract-json must contain a JSON object")
        state_contract = loaded
    output_root = args.output_root or _timestamped_output_root()
    defaults = {
        "vehicle_id": args.vehicle_id,
        "scenario": args.scenario,
        "legal_permission": args.license_status,
        "rights_evidence": args.rights_evidence,
        "stock_identity": args.stock_identity,
        "microphone_perspective": args.microphone_perspective,
        "recording_device_agc": args.recording_device_agc,
        "state_contract": state_contract,
        "raw_audio_confirmed": args.raw_audio_confirmed,
    }
    if args.spec_json is not None:
        try:
            specs = json.loads(args.spec_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"--spec-json cannot be read as JSON: {exc}")
        if not isinstance(specs, list):
            parser.error("--spec-json must contain a JSON array")
        manifest = intake_url_specs(
            specs,
            output_root=output_root,
            defaults=defaults,
            scan_frames=args.scan_frames,
            frame_interval_s=args.frame_interval_s,
            max_frames=args.max_frames,
        )
    else:
        manifest = intake_urls(
            args.url or [],
            output_root=output_root,
            **defaults,
            scan_frames=args.scan_frames,
            frame_interval_s=args.frame_interval_s,
            max_frames=args.max_frames,
        )
    print(f"status={manifest['status']}")
    print(f"records={len(manifest['records'])}")
    print(f"output_root={manifest['download_root']}")
    return 0 if manifest["status"] == "URL_INTAKE_COMPLETE" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "ALLOWED_DOWNLOAD_ROOT",
    "SCHEMA_VERSION",
    "UrlIntakeError",
    "build_video_record",
    "intake_urls",
    "intake_url_specs",
    "render_intake_report",
    "scan_video_frames",
    "validate_source_url",
    "write_intake_outputs",
]
