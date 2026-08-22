# S12 原始录音与同步状态入库

这个入口只接收 Jovi 已经取得合法使用权的原始 WAV/FLAC 和同步状态文件。它不下载视频，不把 YouTube 音频升级成 R1，也不复制或改写原始版权媒体。

## 外部目录边界

原始文件和状态 CSV/JSON 必须位于 `E:\Claude_allow\Download`（或测试时显式传入的批准根目录）下。审计 manifest/report 可以写入仓库或其他元数据目录；Git 只保存外部路径别名、SHA-256、来源/许可凭证和派生特征，WAV/FLAC、PCM、视频和状态原件不能写入 Git。

## 最小规格

```json
[
  {
    "recording_id": "ferrari_458_full_pull_01",
    "vehicle_id": "ferrari_458",
    "scenario": "full_pull",
    "audio_path": "E:\\Claude_allow\\Download\\r1\\ferrari_458_full_pull_01.wav",
    "source_url": "https://授权页面或原始录音交付页",
    "source_kind": "controlled_raw_audio",
    "license_status": "CONFIRMED",
    "rights_evidence": "E:\\Claude_allow\\Download\\r1\\permission.pdf",
    "exact_vehicle_trim": "Ferrari 458 Italia 2010 stock",
    "stock_exhaust_confirmation": "CONFIRMED_STOCK",
    "microphone_position": "EXTERIOR_REAR",
    "recording_device_agc": "DOCUMENTED_NO_AGC",
    "raw_audio_confirmed": true,
    "state": {
      "trace_root": "E:\\Claude_allow\\Download\\r1\\state",
      "rpm_trace_path": "rpm.csv",
      "load_throttle_trace_path": "load_throttle.csv",
      "gear_shift_trace_path": "gear_shift.csv",
      "time_window": {"start_s": 0.0, "end_s": 12.345},
      "units": {
        "time_s": "s",
        "rpm": "rpm",
        "load": "fraction_0_1",
        "throttle": "fraction_0_1",
        "gear": "integer_index",
        "shift_event": "0_or_1"
      }
    }
  }
]
```

三个状态文件都必须有严格递增的 `time_s`，并覆盖 `time_window`。允许低于音频采样率的时间戳遥测；Stage R 会在不外推的前提下插值连续量（RPM、负载、油门），并对挡位/换挡事件采用离散最近点映射到音频采样网格。缺少时间列、单位不明、窗口不完整或原件在批准目录外时，记录保持非 R1。

## 执行

```powershell
python -m tools.sound_sim.s12.real_reference.raw_audio_intake `
  --spec-json "E:\Claude_allow\Download\r1\spec.json" `
  --output-root "E:\Claude_allow\Download\r1\intake-audit"
```

输出只有 `reference_manifest.json` 和中文 `R1_Reference_Intake_Report.md`。`R1_REFERENCE_PACKAGE_READY` 只表示入库合同通过；它不会启动 MATLAB、Comparator、人耳 A/B 或自动调参。后续仍须用 `prepare_r1_matlab_inputs` 生成外部临时 MAT，取得 MATLAB/MoSQITo/Stage-N 收据，再由 Jovi 完成人耳确认。

## YouTube 403 的处理边界

下载器可以在批准的外部目录中重试不同客户端或仅音频流，并记录失败/截断 SHA 与解码收据；这些文件仍是视频派生 R3。403 重试成功只说明媒体完整可解码，不能证明原厂状态、同步 RPM/负载/挡位或许可，也不能进入这个原始录音入口。
