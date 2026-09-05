# 当前产品与声音系统需求

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

## 1. 最终用户效果

用户在车内打开 Android App，选择一个车型，App 只依赖 `speed + acceleration` 也能形成自然的虚拟发动机状态并实时播放。最终体验应满足：

- idle 有生命感，不是静态循环/合成器音；
- gentle/hard acceleration 的负载、转速和声压变化可区分；
- virtual shift 连续、无 chatter；
- lift/overrun/afterfire 有因果和时序；
- Hellcat/Ferrari/RX-7 有明显不同身份；
- 无 click/pop、明显固定电子 tone、错误回火和突兀状态跳变；
- 车内 latency/underrun/CPU/memory/thermal 达到可用水平。

## 2. 当前阶段需求 — S12 / Stage AD

- Python S12 保持 authoritative renderer；
- AA-C3 当前链保持可回归；
- Stage AD 使用 fixed-scale reference distance 做跨轮收敛；
- 参数优化默认按 `body → blower → afterfire` source-causal family；
- 不允许 master/global/broad-pre-PTR gain 伪装 source repair；
- Track-P/PTR/Radiation 不因听感偏好随意修改；
- 每轮输出 config/PCM/metrics/receipt；
- 最终必须交给 Jovi 听。

## 3. Reference requirements

- Reference 必须有来源、SHA、evidence level、rights/status、scene binding；
- speech/music contaminated case fail-closed；
- R2/R3 不能升级成 R1；
- 公网提取工具只能在明确授权时生成 R3 私人 A/B 材料，默认不得作为自动 optimizer target；
- 正式 calibration 需要 R1。

## 4. Human requirements

正式 V3 blind package 不覆盖、不提前 reveal；Stage AD 新 package 独立、非盲、diagnostic。任何 Engineering Profile promotion 都需要明确的人耳 decision 和对应 receipt。

## 5. Simulink requirements

Simulink 当前不是声音 authority。只有结构、尺寸、Update Diagram、simulation、PCM shape、Python equivalence 全部通过后，才能称 diagnostic mirror verified。

## 6. Android requirements

产品化进入条件：至少有一个 Human accepted/versioned Engineering Profile 和 Golden evidence。

Android runtime 至少需要：

- 48 kHz realtime output；
- realtime-safe callback；
- no heap/file I/O/JSON on callback；
- input/state/audio rate 解耦；
- deterministic trace replay；
- profile selector；
- lifecycle restore；
- latency/xrun/CPU/memory/thermal metrics。

## 7. 明确非目标

当前不是：ESP32 上板、Tesla CAN 强依赖、云端账号、公开 tuning marketplace、OEM reproduction claim。
