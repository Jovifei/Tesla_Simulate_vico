# S12 Sound Product Overnight Independent Review

审计日期：2026-07-27（Asia/Shanghai）  
审计范围：仅昨夜 S12 Sound Product 交付物及其可定位证据。  
审计方式：只读；未修改被审文件，未调用 MATLAB、Simulink/MCP，未启动设备或执行测试。

## 最终判定：FAIL

阻断原因不是缺少源码，而是关键交付目标没有相应层级的可运行证据：Simulink Runtime Proof 的 13 个 stage artifact 全部缺失；Dashboard v0.10 与 AudioParameterPackage v0.3 均不存在；跨实现等价性没有任何实际比较；Android 只有 PC-hosted synthetic 协议运行，且没有 Android 设备证据。

`DEVICE_RUNTIME_NOT_VERIFIED`

以下 `PASS` 仅表示所注明的证据层级通过，绝不外推为 Simulink、真实音频设备、Android 设备或真实车型标定通过。

## 证据分层

| 层级 | 本次可接受的结论 |
|---|---|
| Git / 静态 | 可确认七个 Runtime/Android 提交未改 FVM、PTR core、radiation 或 4D-B baseline；可确认 Playground 是未跟踪静态工件。 |
| 真实 PC Python 运行 | v0.6、v0.7、v0.8 外层报告保留了 stdout、JSON 和 PCM SHA；其 sink/client 均明确为 synthetic PC simulation。 |
| Simulink 运行 | 无证据。不得由 SLX、builder、静态合约、direct renderer 或 PC Python 报告推导。 |
| Android / 设备 | 有 debug APK 文件，但没有 install、launch、logcat、设备序列号、真实网络或真实音频输出证据。 |
| 真实车型标定 | 无可授权录音、RPM 对齐、order map 或真实车型校准闭环。 |

## 分项结论

| 审核项 | 判定 | 关键证据与缺口 | 问题级别 |
|---|---|---|---|
| 1. Simulink Runtime Proof | **FAIL** | `tasks/reports/runtime/s12-playground-runtime-proof` 下实际文件数为 0；`temporary_build.json`、`update_diagram.json`、`active_compile_dimension_readback.json`、三场景 simulation、PCM、repeatability、device smoke 和最终 report 均不存在。`playground/s12_sound_playground_runtime_proof.m` 默认 `execute=false`、`MANUAL_RUNTIME_REQUIRED`。 | **Critical** |
| 2. Simulink Dashboard v0.10 | **FAIL** | 未发现 v0.10 candidate。唯一 `playground/S12_Sound_Playground.slx` 为未跟踪 v0.9 中间件，SHA-256 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`；只读 XML 检查的 `simulink_hmi`/Slider/Knob 数为 0。Dashboard 是 Constant 配置，且其 `out:1` 默认旁路接入 Vehicle State，配置所在 `out:2` 未接入算法主链。 | **Critical** |
| 3. AudioParameterPackage v0.3 | **FAIL** | 全审计范围未发现 v0.3。现有 `golden_audio_parameter_package.json` 是 **v0.2**，含 RPM/Load range、synthetic provenance、source commit、package hash 和 radiation hash；但无 model SHA、显式 units schema、v0.3 export/import snapshot、round-trip 或 backward-compatibility 实测。 | **Major** |
| 4. Simulink ↔ PC Runtime 等价 | **FAIL** | `s12_sound_playground_runtime_equivalence_contract.m` 自标 `REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION`；只列 sample/channel/max/RMS/order/phase，缺 transient metric、correlation 和 tolerance source。金标 trace 是 descriptor，未嵌入可重放状态样本；同一 package 也只是 v0.2。无 Simulink PCM、PC replay 对、比较结果或报告。 | **Critical** |
| 5. Android App → PC Runtime 闭环 | **FAIL** | 源码拓扑存在：Android vehicle state → WebSocket v0.8 → `EngineRuntimeApi` → PC PCM；Android 不直接控制内部音频参数。实际保留的是 synthetic PC client 的 v0.8 run，不是 Android App/runtime。线上的 packet 未携带 package hash；无真实 loss-rate 指标，Android `IOException` 后停止排程而非自动重连。 | **Major** |
| 6. Realism Calibration 工作台 | **FAIL**（synthetic 披露 **PASS**） | 运行参数和 package 明确 C/synthetic，未把 fixture 称为实车，这是正确边界；但未找到昨夜新增的 Realism Calibration Workbench。现有校准 JSON 缺 copyright/license/authorization、录音 SHA、RPM/RPM alignment、可审计 order-map 和真实车型标定证据；相关校准提交也早于昨夜。 | **Major** |
| 7. 冻结边界 | **PASS（仅 Git/静态）** | 对 `2fd845c^..1bf88fb` 的路径差异未见 FVM、PTR core、radiation impedance 或 4D-B baseline 变更。当前 `benchmark/baselines/sprint-4d-b/radiation-boundary-package.json` SHA-256 实测为 `0F4B2CA494CD44F79D05968513759578D04E6AB38B1EE37F7621158ABB0D2D6F`，匹配 `frozen_ptr_contract.py`，并绑定 `4afe65a67ed21822422f1eb6dbf43fdd627072d3`。v0.8 schema 自引入提交后未变，但无独立 compatibility vector/tag。 | Minor（兼容性证据不足） |
| 8. Git 与文档真实性 | **FAIL** | `HEAD=1bf88fb7475819df4afda36e250ef2b282f4c677`（2026-07-26 13:40:35 +08:00）；`git fsck --no-dangling` 通过。但当前有 116 个未跟踪文件，整棵 `tools/sound_sim/s12/playground/`、相应 tests 和报告没有 commit identity。离线报告对“未运行”本身是诚实的，不能升级为交付完成。 | **Major** |

## Runtime Proof：逐项核验

| 必需实证 | 状态 | 结论 |
|---|---|---|
| Update Diagram | NOT VERIFIED | 不存在 stage JSON 或完整诊断日志。 |
| Compile | NOT VERIFIED | 不存在 compiled-dimension readback。已有历史 `packed(2)` compile failure 不能视为通过。 |
| Idle / Cruise / Acceleration Simulink simulation | NOT VERIFIED | 三个 simulation artifact 均缺失。 |
| PCM 960×2、48 kHz、frame count、clipping | NOT VERIFIED for Simulink | 只有未来合同和 PC Python 报告；无 Simulink logged PCM。 |
| Repeatability SHA | NOT VERIFIED | 没有 cold-load/rebuild 的两份 Simulink PCM/WAV 或 SHA。 |
| Simulink device smoke | NOT VERIFIED | `device_audio_smoke.json` 缺失。 |

不得混淆的有限正面证据：

- `tasks/reports/runtime/s12-engine-sound-v0.6-final-r5/runtime_report.json` 记录 600 s synthetic PC virtual-time run、30,000 PCM frames、48 kHz / 960 samples / 2 channels / 24-bit、0 clipping、0 simulated underrun、PCM SHA `d1df7469...01cba`。它明确写明 `device_output=simulated_pc_pcm_sink`。
- `tasks/reports/runtime/s12-vehicle-interface-v0.7-paced-r2/runtime_report.json` 和 `latency_report.json` 记录 600 s paced localhost PC run、60,000 packets、30,000 PCM frames、PCM SHA `76fd1fe0...23971`、p99 16.381500 ms。它是 `localhost_http_v0.1`、`offline=true`。
- `tasks/reports/runtime/s12-android-vehicle-interface-v0.8-r2/runtime_report.json` 记录 synthetic Android-protocol client 的 600 s PC-hosted WebSocket run：60,000 packets、30,000 PCM frames、1 次受控 reconnect、0 clipping、0 simulated underrun；p99 acknowledgement 20.499500 ms。它明确是 `client_kind=synthetic_android_protocol_simulator`、`endpoint_scope=127.0.0.1 only`，不是 Android 设备运行。

这些工件证明有限的 Python/PC 仿真确实执行过；它们不证明 Simulink runtime、物理 PCM device playback、Android App 或真实车辆。

## Dashboard 审核细节

审计要求的 RPM、Load、Acceleration、Throttle、order gains、PTR 参数、master gain 和 mode selector，没有以真实 Slider/Knob/HMI 控件和已验证绑定交付：

- 唯一 SLX 内 RPM、Load、Acceleration、Throttle、Cylinder Count、Firing Order、Order Gains、Pipe Length、Area、Reflection、Damping、Gain dB 都是 Constant；无 Slider、Knob 或 mode selector。
- Dashboard 内 `In1 -> Out1` 默认旁路进入 Vehicle State；常量经 Mux 汇入 Configuration 的 `out:2`，但该端口没有进入顶层 downstream path。
- `s12_sound_playground_dashboard_contract.m` 自称 `NOT_A_VALIDATED_DASHBOARD_PLAYGROUND`，Interactive source 仍是 “script-configured constants pending HMI binding”。
- 因此无法确认 Interactive 与 Qualification 共享同一已运行算法核心。

## 参数包与等价性审核细节

- v0.2 静态包有 source commit、package hash、synthetic provenance、RPM/Load ranges 和 frozen radiation hash；这不补足目标 v0.3。
- Android v0.8 状态协议只有 timestamp、speed、acceleration、RPM、load、throttle 六字段；会话中没有 parameter-package hash，因此不能证明传输时使用同一包。
- 等价性合约中的参考 PCM SHA `76fd1fe0...23971` 可与 v0.7/v0.8 PC 输出对应，但没有 Simulink PCM 与之比较；SHA 本身不能构成等价结论。
- 未取得 frame/sample pair、frequency/order metrics、RMS、transient、correlation、tolerance source 的完整比较结果。

## Android 闭环与 APK

源码审查未见 Android 绕过 PC Runtime 而直接控制内部音频参数：`MainActivity` 以 100 Hz 发送 state JSON，PC WebSocket server 解析后交给 `EngineRuntimeApi`，后者每两包生成一帧 PCM。该结论仅为源码拓扑层。

存在 debug APK：

- 路径：`E:\Tesla_speed\prj\android_vehicle_sound_demo\app\build\outputs\apk\debug\app-debug.apk`
- 大小：18,938 B；SHA-256：`0794D5BA60F3DEFDE9852EBEFE594B62A68D753B8E85049FC3F15110B78FDA7B`
- 该路径受 `.gitignore` 忽略；没有保留的 Gradle `BUILD SUCCESSFUL` 输出、install、launch、logcat 或设备标识。

文档还明确 server 仅绑定 `127.0.0.1`，Android Emulator 用 `10.0.2.2` 映射；物理 Android 设备不可达，故不能把 APK 文件提升为闭环或设备通过。

## 已真正完成 / 证据边界

### 已真正完成

- 七个版本化 Runtime/Android 源码提交（`2fd845c` 至 `1bf88fb`）及上述三类 PC synthetic 运行报告。
- v0.2 package 的 synthetic provenance、范围、source commit、package hash 与 frozen radiation binding。
- 静态冻结边界核验：实际 radiation package hash 与冻结常量相符，相关核心得到 Git-path-level 未变证明。

### 只有源码但未运行

- Simulink Runtime Proof orchestration、stage manifest、future builder、Dashboard mode design、PCM/metrics contracts、runtime-equivalence contract。
- v0.3 package 设计目标、v0.10 Dashboard 目标和 v0.2 compatibility logic。

### 只有离线测试 / 离线仿真

- v0.9 Playground 的 static contracts、XML/SLX 检查和离线 repair reports；其文本明确标注未运行 MATLAB/Simulink。
- v0.6/v0.7/v0.8 Python PC synthetic runs；它们有实际 PC 执行证据，但没有真实音频设备、Android 设备或真实车辆意义。

### 缺少设备验证

`DEVICE_RUNTIME_NOT_VERIFIED`：无 Android 实机安装和运行、无 PC real-device audio smoke、无真实网络、无 CAN/OBD/ESP32/I2S/车辆实证。

### 缺少真实录音标定

无可授权真实录音、rights/copyright 字段、录音哈希、RPM 对齐、order-map 闭环或 OEM/车辆测量证据。当前 synthetic 标签应继续保留，不得宣称真实车型音色。

## 问题清单

- **Critical** — 没有 Simulink Update Diagram、Compile、三场景、PCM、repeatability 或 device smoke 的真实 stage artifacts。
- **Critical** — Dashboard v0.10/HMI 不存在；唯一 SLX 没有 HMI，且 Dashboard 配置未接入算法主链。
- **Critical** — Simulink ↔ PC Runtime 尚无同输入、同 package、可比较 PCM 的执行结果。
- **Major** — AudioParameterPackage v0.3、model SHA、units、round-trip 与 backward compatibility 证据不存在。
- **Major** — Android 只有 PC synthetic client；APK 构建物没有安装/运行实证，会话未绑定 package hash，丢包率/真重连未验证。
- **Major** — 真实车型标定缺授权、录音来源/哈希、RPM alignment、order map 与版权字段。
- **Major** — Playground 与 Runtime Proof 全部未跟踪，无法将当前源码、静态报告和未来运行产物绑定到不可变提交。
- **Minor** — v0.8 仅能证明引入后未变，缺跨版本 compatibility vector/tag。

## 唯一下一步建议

先将当前 Playground、v0.10 Dashboard 与 AudioParameterPackage v0.3 收敛为一个可审计、Git 绑定的候选；在该候选存在前，不进入 Simulink Runtime Proof、等价性或 Android 闭环验收。
