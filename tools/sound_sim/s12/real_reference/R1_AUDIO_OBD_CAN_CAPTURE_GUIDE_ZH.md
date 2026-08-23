# S12 R1 音频与 OBD/CAN 同步采集说明

本说明用于 Hellcat 单车试点，也适用于 Jovi 指定的精确原厂车型。目标不是得到“听起来像”的视频，而是得到可以绑定到音频采样时间轴的真实状态证据。

## 音频采集

- 使用 WAV/FLAC 原始录音；保留采样率、位深、通道和录音机原始元数据。
- 记录麦克风位置、距离、方向、风噪处理和是否车内/发动机舱/排气尾部。
- 明确前置增益、AGC、限幅、降噪、EQ、混音和任何后处理；未知或未记录会拒绝 R1。
- 录音前后保留开始/停止事件，避免只交付从视频抽出的音轨。

## 共同时间基准

优先级从高到低：

1. 音频记录器和 OBD/CAN 记录器共享硬件时钟或同一触发脉冲；
2. 两台记录器都记录可追溯的 UTC/单调时间戳，并给出时钟偏差校准；
3. 录音开始时同时记录可审计的声学/电气 marker（例如拍手、蜂鸣或灯光触发），并提供 marker 时间；
4. 只有文件名、视频画面猜测、稳态 RPM 标签或手工对齐不接受为同步证据；不能猜测任何同步状态。

## OBD/CAN 状态

至少导出三类文件：

```text
rpm.csv            time_s,rpm
load_throttle.csv  time_s,load,throttle
gear_shift.csv     time_s,gear,shift_event
```

要求：

- `time_s` 严格递增、单位明确、不能有空值或非数值；
- RPM、负载、油门覆盖音频 `time_window`，不能静默外推；
- 连续量可以在覆盖窗口内插值；挡位和换挡事件必须离散映射；
- 说明每个字段的 OBD PID/CAN 信号、单位、采样率、丢帧和滤波；
- 不要把速度、挡位标签或文件名当作 RPM；不要猜测 load/throttle/gear。

## 场景模板

每条录音在 `spec.json` 中登记一个场景，例如 `idle`、`steady_mid`、`full_pull`、`shift` 或 `lift_afterfire`，并写出 `time_window.start_s/end_s`。第一批每辆锚点车建议覆盖 3–5 个独立来源，而不是把同一段复制为多个来源。

## 采集后检查

```text
原始音频 SHA
→ 三个状态文件 SHA
→ time_s 单调性与窗口覆盖
→ 采样率/通道/设备/AGC
→ 精确原厂状态和授权范围
→ raw_audio_intake fail-closed
```

任何检查失败都保留失败原因，但不进入 MATLAB 阶次、自动调参或 Profile Candidate。
