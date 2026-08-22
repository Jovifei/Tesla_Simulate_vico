# S12 网址真实声浪输入入口

Jovi 提供网址后，使用这个入口把视频下载到 `E:\Claude_allow\Download`，并生成外部审计目录。原始视频、抽取 WAV、下载日志和 `intake_manifest.json` 不进入 Git。

如果已经拿到合法原始 WAV/FLAC 和同步 CSV/JSON，请改用同目录的 [`RAW_AUDIO_INTAKE_GUIDE.md`](RAW_AUDIO_INTAKE_GUIDE.md)；视频下载结果永远不能凭网址直接进入 R1。

## 直接网址

```powershell
python -m tools.sound_sim.s12.real_reference.url_intake `
  --url "https://example.com/video" `
  --vehicle-id ferrari_458 `
  --scenario full_pull `
  --scan-frames
```

可重复指定多个 `--url`。如果来源有明确许可，才填写：

```powershell
--license-status CONFIRMED --rights-evidence "https://来源页面或授权收据"
```

没有许可证据时，入口保持 `R3`；有许可、车型和场景但没有同步状态时，最多为 `R2`。即使手工传入 `--raw-audio-confirmed`，只要来源类型是视频抽取（包括 YouTube），仍不能成为 `R1`；`R1` 必须单独提供原始 PCM/FLAC 收据、来源指针、授权证据和原厂排气确认。

如果一批网址属于不同车型/工况，可使用 JSON 数组（每项至少有 `url`，其余字段可逐项覆盖）：

```json
[
  {"url": "https://example.com/ferrari", "vehicle_id": "ferrari_458", "scenario": "full_pull", "license_status": "CONFIRMED", "rights_evidence": "授权页面或收据"},
  {"url": "https://example.com/hellcat", "vehicle_id": "hellcat", "scenario": "shift"}
]
```

`license_status` 也可写成内部字段 `legal_permission`；只有同时提供可审计许可证据时才会进入 R2，网址视频本身不会自动取得 R1 资格。

```powershell
python -m tools.sound_sim.s12.real_reference.url_intake `
  --spec-json "E:\Claude_allow\Download\s12-url-spec.json" `
  --scan-frames
```

## 同步状态合同

如果网址同时提供了合法的同步状态文件，可以通过 JSON 传入状态合同：

```json
{
  "rpm_state_status": "SYNCED",
  "load_throttle_status": "SYNCED",
  "gear_shift_status": "SYNCED",
  "trace_paths": {
    "rpm": "rpm.csv",
    "load_throttle": "load.csv",
    "gear_shift": "gear.csv"
  }
}
```

```powershell
--state-contract-json "E:\Claude_allow\Download\某次录音\state-contract.json"
```

这仍不会绕过 Stage Q/R1 验收；必须另外核对原始音频、精确车型/原厂状态、麦克风、设备/AGC、时间轴、单位和 SHA-256。视频压缩音频默认是派生信号，不能凭网址直接成为 R1。入口还会拒绝“容器声称 PCM、但来源仍是 video_extracted”的手工升级，避免把视频中的无损封装或短头部残片当作原始录音。

## 运行前提和输出

- 需要 `yt-dlp` 和 `ffmpeg/ffprobe` 在 PATH 中。
- 抽取过程不做增益、EQ、AGC 或响度匹配；试听副本与分析信号分离。
- `--scan-frames` 会按间隔抽取画面；若本机有 Tesseract 会尝试 OCR。OCR 数字只记录为 `ESTIMATED_FROM_VIDEO_NOT_QUALIFIED`，不能替代同步 CSV/MAT，也不能开启阶次硬门。
- 输出目录默认类似 `E:\Claude_allow\Download\s12-url-intake-YYYYMMDD-HHMMSS`。
- 结果报告为 `URL_Intake_Report.md`；任何 `R2` 结果仍不能启动阶次自动调参。
