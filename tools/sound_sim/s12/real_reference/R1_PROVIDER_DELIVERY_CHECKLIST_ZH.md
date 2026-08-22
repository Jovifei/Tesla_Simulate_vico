# S12 R1 真实车辆录音交付清单（中文）

这份清单给车主、录音师或授权方使用。它不是购买授权，也不会把公开视频自动升级为 R1。只有“合法原始音频 + 精确车辆/原厂状态 + 同步状态数据 + 采集链说明 + 可审计授权”全部齐全，才会进入 R1。

## 第一批交付范围

先处理三个锚点，每辆车交付 3–5 个独立来源/录音：

| 锚点 | 目标来源数 | 建议工况覆盖 |
| --- | ---: | --- |
| Ferrari 458 | 3–5 | 怠速、稳态、加速拉升、换挡/收油 |
| Dodge Hellcat | 3–5 | 怠速、稳态、加速拉升、换挡/收油/增压负载 |
| Mazda RX-7 FD | 3–5 | 怠速、稳态、加速拉升、换挡/收油；注明转子与涡轮配置 |

三个锚点通过 Stage R 和 Jovi 听审后，才扩展到其余五车。不同镜位或不同工况可以是不同来源，但每一条都要单独登记，不能用同一条视频复制成多个来源。

## 每个来源必须交付的文件

建议每个来源一个目录，原始文件只放在 `E:\Claude_allow\Download\` 下：

```text
<source_id>/
├─ raw_audio.wav 或 raw_audio.flac       # 未增益、未 EQ、未 AGC 掩盖的原始音频
├─ rpm.csv                               # time_s,rpm
├─ load_throttle.csv                     # time_s,load,throttle
├─ gear_shift.csv                        # time_s,gear,shift_event
├─ spec.json                             # 车型、工况、采集链、窗口、来源指针
├─ rights_receipt.pdf 或 rights.json     # 授权/购买/车主许可
└─ sha256.txt                            # 上述每个文件的 SHA-256
```

如果状态数据来自一个完整的遥测文件，也必须拆出或明确映射 RPM、负载/油门和挡位/换挡字段；不能只给截图、估算值或文件行数。

## `spec.json` 必填内容

```json
{
  "recording_id": "ferrari_458_full_pull_01",
  "vehicle_id": "ferrari_458",
  "scenario": "full_pull",
  "audio_path": "E:\\Claude_allow\\Download\\r1\\ferrari_458_full_pull_01\\raw_audio.wav",
  "source_url": "原始录音交付页或授权页",
  "source_kind": "controlled_raw_audio",
  "license_status": "CONFIRMED",
  "rights_evidence": "E:\\Claude_allow\\Download\\r1\\ferrari_458_full_pull_01\\rights_receipt.pdf",
  "exact_vehicle_trim": "年份、市场、配置、发动机、变速箱",
  "stock_exhaust_confirmation": "CONFIRMED_STOCK",
  "microphone_position": "EXHAUST_REAR / ENGINE_BAY / INTERIOR_CABIN_DASH",
  "recording_device_agc": "明确写明 AGC、增益和后处理状态",
  "raw_audio_confirmed": true,
  "state": {
    "trace_root": "E:\\Claude_allow\\Download\\r1\\ferrari_458_full_pull_01",
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
```

麦克风位置和 AGC 不要求固定为某一个值，但必须明确、可审计；`UNKNOWN`、空值或“未说明”会拒绝 R1。所有状态文件的 `time_s` 必须严格递增，并完整覆盖 `time_window`。连续量允许低于音频采样率，Stage R 会在窗口内插值；禁止静默外推。

## 授权文字必须覆盖的范围

授权方需要明确允许：

1. 在本地项目中保存原始音频的外部路径别名和 SHA-256；
2. 计算频谱、响度、心理声学、阶次和派生特征；
3. 与本地合成声浪进行 Comparator 和 Jovi 人耳 A/B；
4. 根据差异报告提出有界调音参数建议；
5. 将派生特征、报告和参数建议放入 Git，但不把原始版权音频放入 Git。

只允许“试听”或只允许“个人播放”的许可不足以进入 R1；这类来源最多登记为 R2/R3，直到取得书面补充许可。

## 自动验收结果

| 条件 | 缺失或不合格时的结果 |
| --- | --- |
| 合法原始 WAV/FLAC | 拒绝 R1；视频抽音只能 R3 |
| 精确车型/年份/配置 | 拒绝 R1 |
| 原厂排气/改装状态 | 拒绝 R1 或降为 R2/R3 |
| RPM 时间 trace | 禁止阶次和自动调参 |
| Load/Throttle 时间 trace | 禁止完整标定 |
| Gear/shift 时间 trace | 禁止换挡瞬态标定 |
| 麦位、采样率、录音设备、AGC | 拒绝 R1；不能用默认值猜测 |
| SHA-256 与外部文件匹配 | 拒绝导入 |
| Jovi 中文听审结果 | 不得进入 Stage S/T |

## 收到文件后的执行顺序

```text
外部路径与 SHA 核对
→ raw_audio_intake.py fail-closed
→ 合并 Stage Q canonical reference_database_v2
→ 工况切片与 RPM/state 绑定
→ MATLAB rpmordermap/ordertrack/orderspectrum/rpmfreqmap
→ MATLAB 及 MoSQITo 心理声学收据
→ Stage N Comparator 差异报告
→ 中文人耳 A/B
→ 一车/一问题/一参数组，最多三轮有界调音
→ 三锚点全部通过后才允许 Stage T
```

入库命令见同目录 `RAW_AUDIO_INTAKE_GUIDE.md`。任何一项不满足时，系统必须保留记录和缺口，但继续保持 `WAITING_FOR_REAL_REFERENCE_DATA`，不生成 `APPROVED_PROFILE_CANDIDATE`。

