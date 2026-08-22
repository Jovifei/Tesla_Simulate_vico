# S12 网址真实声浪输入入口

Jovi 提供网址后，使用这个入口把视频下载到 `E:\Claude_allow\Download`，并生成外部审计目录。原始视频、抽取 WAV、下载日志和 `intake_manifest.json` 不进入 Git。

## 直接网址

```powershell
python -m tools.sound_sim.s12.real_reference.url_intake `
  --url "https://example.com/video" `
  --vehicle-id ferrari_458 `
  --scenario full_pull
```

可重复指定多个 `--url`。如果来源有明确许可，才填写：

```powershell
--license-status CONFIRMED --rights-evidence "https://来源页面或授权收据"
```

没有许可证据时，入口保持 `R3`；有许可、车型和场景但没有同步状态时，最多为 `R2`。

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

这仍不会绕过 Stage Q/R1 验收；必须另外核对原始音频、精确车型/原厂状态、麦克风、设备/AGC、时间轴、单位和 SHA-256。视频压缩音频默认是派生信号，不能凭网址直接成为 R1。

## 运行前提和输出

- 需要 `yt-dlp` 和 `ffmpeg/ffprobe` 在 PATH 中。
- 抽取过程不做增益、EQ、AGC 或响度匹配；试听副本与分析信号分离。
- 输出目录默认类似 `E:\Claude_allow\Download\s12-url-intake-YYYYMMDD-HHMMSS`。
- 结果报告为 `URL_Intake_Report.md`；任何 `R2` 结果仍不能启动阶次自动调参。
