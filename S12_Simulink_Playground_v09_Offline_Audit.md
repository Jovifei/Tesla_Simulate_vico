# S12 Simulink Sound Playground v0.9 — Offline Audit

- 审核日期：2026-07-26
- 审核方式：只读源码、审计包、SLX ZIP/XML 和 Git 工作树检查。
- 未调用 MATLAB、Simulink MCP 或 Simulink；未启动 MATLAB 进程；未运行 Update Diagram、Compile、Simulation 或 Audio Device Writer。
- 当前模型 SHA-256：`FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0`（与审计包内错误二进制一致）。

## Overall: FAIL

```text
v0.9 = INCOMPLETE
current model = generated but not validated; structurally known-invalid
compile = FAIL
simulation = NOT RUN
audio = NOT RUN
rebuild disposition = NOT_READY_FOR_REBUILD
```

| 审核项 | 状态 |
| --- | --- |
| Current SLX validity | FAIL |
| Builder validity | FAIL |
| Port contract validity | FAIL |
| Signal dimension validity | FAIL |
| Test coverage validity | FAIL |
| Transaction/idempotence validity | FAIL |

本结论不表示任何修复已实施，也不表示 v0.9 已完成。

## 审核输入与编译证据

已审阅任务指定的 SLX、builder、parameters/scenarios/excitation/PTR/render/run helpers、MATLAB test、v0.9 implementation plan、现有审计报告和 `compile_error.txt`。

`compile_error.txt` 是 Jovi 提供的 Command Window/Diagnostic Viewer 摘录，而非完整 diary。它记录 `Engine Excitation/Order Harmonic Transient` 中 `packed(2)` 越界，且该输入被推导为仅含一个元素的一维向量；这是 **Compile FAIL**，不构成 Update Diagram、仿真、PCM 或播放证据。

## 1. 当前 SLX 的真实只读结构

### 顶层 block inventory

| 顶层 block | XML PortCounts |
| --- | ---:|
| Dashboard | 1 in / 2 out |
| Vehicle State | 2 in / 2 out |
| Engine Excitation | 2 in / 3 out |
| PTR Radiation Tuning Adapter | 3 in / 3 out |
| Audio Renderer | 3 in / 2 out |
| Audio Device Writer | 1 in |
| PCM To Workspace | 1 in |

这与设计合同 `0/1, 1/1, 1/2, 2/2, 2/1` 不一致。

### 顶层实际连线与端口

```text
Dashboard/out1 (default In1→Out1 scalar bypass)
  → Vehicle State/in1 (default bypass)
  → Vehicle State/out1
  → Engine Excitation/in1 (default bypass)
  → Engine Excitation/out1
  → PTR Adapter/in1 (default bypass)
  → PTR Adapter/out1
  → Audio Renderer/in1 (default bypass)
  → Audio Renderer/out1
  → Audio Device Writer/in1
  └→ PCM To Workspace/in1

Engine Excitation/out2 (named Excitation) → PTR Adapter/in2 (named Excitation)
PTR Adapter/out2 (named Pressure) → Audio Renderer/in2 (named Pressure)
```

未接出的设计端口如下：

- Dashboard/out2 `Configuration`：内部 Mux 的唯一配置向量输出，但顶层未连接；
- Vehicle State/in2 `Configuration In` 与 out2 `Vehicle State Out`：顶层未连接；
- Engine Excitation/in2 `State` 与 out3 `State Out`：未连接；
- PTR Adapter/in3 `State` 与 out3 `State Out`：未连接；
- Audio Renderer/in3 `State` 与 out2 `PCM`：未连接。

因此 Audio Device Writer 和 To Workspace 接收的是 **Audio Renderer 默认 bypass out1**，不是名为 `PCM` 的 renderer chart 输出 out2。当前模型既不是有效 PCM 链路，也不是单纯 To Workspace/WAV 导出；它同时存在 Audio Device Writer 与 To Workspace，但两者都接错端口。SLX 内没有 Audio File Writer 或 SLX 内 WAV export block；`audiowrite` 只存在于独立 MATLAB helper `s12_sound_playground_run_case.m`。

### subsystem 内部残留旁路

每个 builder 创建的 subsystem 都仍包含默认 `In1` 和 `Out1` 及其直连：

| Subsystem | 残留默认 line | 设计端口状态 |
| --- | --- | --- |
| Dashboard | `In1 → Out1` | Mux → `Configuration` (Port 2)，未接到顶层。 |
| Vehicle State | `In1 → Out1` | `Configuration In` → `Vehicle State Out` (Port 2)，未接。 |
| Engine Excitation | `In1 → Out1` | chart 由 `State` (Port 2) 驱动，输出 `Excitation`/`State Out` (Port 2/3)。 |
| PTR Adapter | `In1 → Out1` | chart 使用 `Excitation`/`State` (Port 2/3)，输出 `Pressure`/`State Out` (Port 2/3)。 |
| Audio Renderer | `In1 → Out1` | chart 使用 `Pressure`/`State` (Port 2/3)，输出 `PCM` (Port 2)。 |

这与已知根因一致：顶层按第一个端口连线时选中了自动生成的 scalar bypass，不是设计信号。

### MATLAB Function block 与静态接口

SLX 包含三个 Stateflow MATLAB Function chart：

| Chart | 脚本接口 | 静态维度 |
| --- | --- | --- |
| Engine Excitation | `fcn(packed) -> [excitation, packedOut]`，索引 `packed(1:13)` | `packed`、`excitation`、`packedOut` 都是 `size=-1` / inherited。 |
| PTR Adapter | `fcn(excitation, packed) -> [pressure, packedOut]`，索引 `packed(14:17)` | 所有 data 均 `size=-1` / inherited。 |
| Audio Renderer | `fcn(pressure, packed) -> pcm`，索引 `packed(18)` | 所有 data 均 `size=-1` / inherited。 |

没有 `Signal Specification`、固定 MATLAB Function data size、固定数据类型或固定 frame-size 声明。实际 XML 因此支持“packed 为 1 元素”这一已捕获编译错误，不支持 `[19,1]` 合同。

### Sample time、frame 与 audio 输出

- 模型 solver 是 `FixedStepDiscrete`，fixed step 为 `0.02 s`；这可对应 48 kHz 下的 960 samples/frame。
- Audio Device Writer 静态配置为 48,000 Hz、24-bit integer、两声道映射 `1:2`。
- 但 chart 输出没有显式 `960×1` 或 `960×2` 尺寸，Audio Renderer `PCM` 没有与 writer 相连，且内部 `packed` 是 inherited-size。
- 因此 `48000 Hz + 0.02 s` 只是配置意图，**不是已证明的 960×2 PCM 运行合同**。

## 2. 尺寸合同审核

### Dashboard packed vector

Dashboard 有 13 个 Mux input port；其中 firing order 和 order gains 各自是四元素 Constant。概念上的展平顺序应为 19 元素：

| 元素 | 含义 | 当前 consumer |
| ---:| --- | --- |
| 1 | RPM | Engine |
| 2 | Load | Engine |
| 3 | Acceleration | Engine |
| 4 | Throttle | Engine |
| 5 | Cylinder Count | Engine |
| 6–9 | Firing Order | Engine |
| 10–13 | Order Gains | Engine |
| 14 | Pipe Length | PTR Adapter |
| 15 | Area | PTR Adapter |
| 16 | Reflection | PTR Adapter |
| 17 | Damping | PTR Adapter |
| 18 | Gain dB | Audio Renderer |
| 19 | Sample Rate | **无 consumer**；renderer 与 helpers 均硬编码/参数化为 48,000。 |

实际 SLX 没有固定 `[19,1]`、`[19, 1]` 或等价固定宽度声明。配置 port 也未连接；当前 Engine chart 获得 default scalar，故 `packed(2)` 已证实越界。不得用 `(:)`、可变尺寸或隐式广播掩盖这一合同；应先声明和验证固定列向量。

### 各层设计与实际差异

- **Vehicle State：FAIL。** 设计要求 configuration → fixed vehicle state；当前仅有命名 port 的直接 pass-through，且顶层未接。没有固定 vehicle-state 尺寸、字段布局或 sample time。
- **Engine Excitation：FAIL。** helper 在独立 MATLAB 路径中返回 `960×1`，但 SLX chart 的 input/output size 全继承，且其正确 State input 未连接。
- **PTR Adapter：FAIL。** helper 可接受 excitation frame 和 tuning values，但 chart 的 `packed` state input 未接；其 output shape 未声明。
- **Audio Renderer：FAIL。** 静态脚本表达 `[pressure, pressure]`，理论目标为 `960×2`，但 pressure size、PCM size 和端口 2 都未固定/未接。没有证明 mono-to-stereo 的行/列约定正确。

## 3. Builder 静态审核

当前 source 与审计包 source SHA 一致；它包含 source-only `createEmptySubsystem` 修复，但该修复尚未生成新 binary。静态能力如下：

| Builder 检查 | 状态 | 证据 |
| --- | --- | --- |
| 创建后删除默认 In1/Out1 | PARTIAL | `delete_block(path + "/In1")` / `Out1` 存在。 |
| 删除默认 line / 检查 dangling line | FAIL | 无显式 `delete_line`、`find_system` 或 line contract assertion。删除 block 通常会删除相连 line，但 builder 没有把该行为作为可验证门禁。 |
| 覆盖嵌套 subsystem | FAIL | 只清理五个外层 subsystem；未对嵌套层建立通用清理/断言。 |
| 显式创建设计端口 | PASS | 命名 Inport/Outport 已创建。 |
| 显式 Port 编号 | FAIL | 除旧二进制的 XML 外，source 未给任何新设计 port 设置 `Port` 参数；依赖创建顺序。 |
| 显式端口尺寸 / frame size | FAIL | 无 `[19,1]`、`960×1`、`960×2` Signal Specification 或 Stateflow data-size 设置。 |
| 显式 sample time | FAIL | 仅设置 root fixed step；子系统、chart port、Constant 与 frame contract 未显式设置。 |
| 创建后立即验证 port contract | FAIL | 无 `get_param(...,"Ports")` 或等价断言。 |
| 顶层连线前验证 source/destination | FAIL | 直接以字符串 port number `add_line`，无验证。 |
| 保存前完整结构检查 | FAIL | 无 unconnected port、line、dimensions、chart data 或 Audio Writer contract 检查。 |
| 失败不覆盖正式 SLX | PARTIAL | 已有目标时拒绝覆盖；但不产生可验证 candidate，也不能修复现有错误 binary。 |
| 临时模型事务性生成 | FAIL | 直接 `new_system(modelName)`，不是临时 candidate/验证/提升流程。 |
| cleanup 安全、close without save | FAIL | 无 `onCleanup` / `try-catch`；任意失败会留下已加载 dirty model。 |
| 重复执行幂等性 | FAIL | 已存在文件或 loaded model 即报错，属于防覆盖，不是幂等重建。 |

结论：source 中“删除默认端口”是必要修复，但缺少结构、尺寸与事务性证据，且无法对现有错误 `.slx` 执行受控再生成。因此它不足以满足 `READY_FOR_CONTROLLED_REBUILD`。

## 4. 当前测试真实性与覆盖分类

| 类别 | 状态 | 当前实际覆盖 |
| --- | --- | --- |
| A. 源码字符串检查 | PARTIAL | Audio Device Writer path、Stateflow script assignment 的 `fileread`/`contains`。 |
| B. 文件存在检查 | PARTIAL | 检查 `.slx` 存在、parameters helper。 |
| C. SLX 静态结构检查 | PARTIAL | `load_system` 后读取 Ports、block name、writer sample rate；不检查 line 端口顺序、default bypass、尺寸或 unconnected ports。当前二进制应使 designed port-count assertion 失败。 |
| D. Update Diagram | NONE | 无 `set_param(model,"SimulationCommand","update")` 或等价。 |
| E. Compile | NONE | 无编译调用；当前仅有失败诊断。 |
| F. Simulation | NONE | 无 `sim` / start-stop / scenario model execution。 |
| G. PCM 输出 | PARTIAL, OFFLINE ONLY | `s12_sound_playground_render_case` 直接调用 MATLAB helpers，不经过 SLX。 |
| H. Audio Device | NONE | 仅检查 block 存在/配置；没有设备播放、underrun 或音频回调证据。 |
| I. 参数敏感性 | PARTIAL, OFFLINE ONLY | helper 可接受 override；测试不证明 Simulink 中 RPM/load/acceleration/PTR/dashboard 敏感性。 |
| J. Repeatability | PARTIAL, OFFLINE ONLY | `audiowrite` helper 的双 SHA；没有 rebuild/cold-load/compiled-model PCM/WAV repeatability。 |

有误导风险的测试名称：`testSubsystemsExposeOnlyTheirDesignedDataPorts` 和 `testModelHasTheRequiredSignalOrder` 只 load/inspect model，不执行 Update、compile 或 simulation；`testSyntheticRendererIsContinuousAndDeterministic` 与 `testWavExportHasStableSha` 都是直接 helper 路径，不测试 `.slx` 或 Audio Device Writer。

## 5. 预测下一轮 MATLAB 验证风险

在不运行 MATLAB 的前提下，修复当前 bypass 后仍最可能出现的门禁如下：

1. **Port number/order：**未显式编号会让创建顺序或残留端口再次改变顶层连接。
2. **Packed size/orientation：**Mux 的 13 input 与概念 19 values、row/column 方向、`packed(6:9)` 和 `packed(10:13)` 的固定形状必须先固定；元素 19 还没有 consumer。
3. **MATLAB Function type inference：**三个 chart 的全部 data 仍是 `size=-1` / inherited，`disableImplicitCasting=1` 下更容易暴露 dimension/type 推导错误。
4. **Frame and sample time：**需证明每个 tick 是 `960×1` pressure/excitation 和 `960×2` PCM、sample time `0.02 s`；root solver 配置本身不够。
5. **Mono/stereo 与 Audio Device Writer：**writer 必须接 renderer PCM port，且该 port 必须是 two-column frame；当前接的是 default scalar bypass。
6. **External helper resolution：**chart 调用的 `s12_sound_playground_*_step` 依赖 builder `addpath(root)`；模型没有 callback/Model Workspace 路径合同，冷重载后可能出现未定义函数。
7. **State persistence/reset：**excitation/PTR helper 有 persistent state；需要验证 first frame reset、scenario 切换、rebuild/cold-load 后的 deterministic 初始化。
8. **DSP toolbox/device runtime：**静态 library reference 不证明可用许可、默认设备、buffer/underrun 或实时播放。
9. **To Workspace logging shape：**Array logging要验证多个 frame 的保存语义、PCM dimensions 和 sample-time，不能把 block 存在当作 PCM artifact。
10. **Model callbacks/workspace：**没有 model callback、Model Workspace 参数或 solver/sample-time preflight；helper path、data typing 和 constants 应显式验证。
11. **Algebraic/multirate/unconnected diagnostics：**当前图无意图反馈，但重接 ports 后必须执行 Update/compile 检查代数环、多速率、未连接 port 和 dangling line。

## Critical findings

1. **Critical — 当前 SLX 端口与连线合同错误。** 所有外层 subsystem 的 default scalar bypass 仍存在并被顶层第 1 端口使用；真实 configuration 与 PCM ports 都未连接。已捕获的 `packed(2)` 越界是该错误的直接结果。
2. **Critical — 当前 Audio Output 无效。** Audio Device Writer/To Workspace 接 Audio Renderer default `out1`，真正 chart PCM 是未连接 `out2`；不存在可归因的 SLX PCM 或 audio evidence。

## Major findings

1. **Major — 固定尺寸合同未实现。** `[19,1]` packed、`960×1` excitation/pressure、`960×2` PCM、data type、orientation 和 sample time 均未显式声明。
2. **Major — builder 无结构验证及事务性。** source-only default-port removal 没有 line/port/size assertion，不能 transactionally build, validate, close-without-save and promote candidate。
3. **Major — 测试不覆盖 Update/compile/simulation/device。** 当前 offline helper PASS 不能用于证明 SLX、Audio Device Writer 或当前二进制。
4. **Major — 现有 v0.9 文档用“click Run”“Audio Device Writer uses...”描述可操作流程，但当前 binary compile FAIL；文档必须保持 generated-but-not-validated 状态，直到运行时证据存在。**

## Minor findings

1. Sample-rate packed element 19 未被 chart consumer 使用，48 kHz 也在 helpers/Audio Writer 中独立硬编码。
2. Vehicle State 是 named pass-through，不是明确固定布局的 vehicle-state transformer。
3. `To Workspace` 设置 `SampleTime=-1`，没有 PCM logging schema/length assertion。
4. 编译错误缺少完整 MATLAB diary/diagnostic export；目前只能依据 Jovi 提供摘录和静态 XML 归因。

## Required patch list

以下是下一次受控重建前必须完成并静态复核的 patch 项；本审核未实施它们。

1. 为 Dashboard、Vehicle、Engine、PTR、Renderer 建立单一可验证的 port contract：清理所有默认 block 和 line，创建后显式设定每个 `Port` 编号，并断言 input/output count 与端口名称。
2. 将 Dashboard 输出改为明确的固定 `double [19×1]` 配置向量；用 Signal Specification/固定 chart data sizes 将 `packed` 固定为 `[19×1]`，禁止 variable-size/inherited shape。
3. 写入并断言 19 个元素的索引表；处理 element 19（明确 consumer 或从合同删除），不能同时硬编码与假装可配置。
4. 定义 Vehicle State 的固定布局，Engine output `960×1`，PTR output `960×1`，Renderer output `960×2`；所有相关端口/Stateflow data 明确 double、column/frame 和 `0.02 s`。
5. 把 `Audio Renderer/PCM` 的正确 port 接到 Audio Device Writer 和 logging；对 Audio Device Writer 的 channels/frame/sample rate 建立静态合同。
6. 改为临时模型 candidate：build → static structure check → save candidate → close without save/reopen → Update/compile 后才在获得明确授权时提升；失败路径 cleanup 必须关闭且不保存。
7. 让 cold load 可定位 helpers（受控 model callback 或显式 preflight），并为 persistent state reset、toolbox/license 和 default device 增加 fail-fast checks。
8. 更新 v0.9 文档，将当前 SLX 标为编译失败、未验证；禁止用可播放/可导出措辞描述当前 binary。

## Required new tests

1. 纯 SLX archive 或 `load_system` 静态测试：每个 subsystem 的 PortCounts、Port numbers、所有顶层 source/destination、无 `In1`/`Out1` 默认 block、无默认 bypass line、无 unconnected design port。
2. 固定尺寸测试：Dashboard `[19,1]`；Engine/PTR `[960,1]`；Renderer `[960,2]`；double、nonvariable、sample time `0.02`。
3. Update Diagram test：断言 zero error-severity diagnostics，且不能把 load-only 当成 update success。
4. Compile test：独立记录编译 success、compiled dimensions/data types/sample times；失败时保留完整 diary/diagnostic。
5. Simulation tests：idle/cruise/acceleration/lift，包含 state reset、no NaN、no clipping、DC/discontinuity、RPM/order、load/harmonic、acceleration/transient 敏感性。
6. PCM/device tests：renderer `960×2` 消费路径、To Workspace log shape、Audio Device Writer device preflight/underrun；device playback 属于独立 runtime evidence。
7. Transaction/repeatability tests：candidate build twice、save/close/cold-load、相同 model + scenario 的 PCM/WAV SHA 及 parameter snapshot 一致。

## Expected MATLAB validation sequence

以下只是未来验证顺序，未在本审核中执行：

1. 在 Jovi 已确认的唯一可见 Desktop 中，先记录模型/源码哈希、DSP toolbox/license、helper path、Audio Device Writer device preflight；不得启动第二个 MATLAB 或 MCP。
2. 仅构建临时 candidate，执行 archive/model structure contract；失败则 close without save，正式错误 `.slx` 不覆盖。
3. cold-load candidate，运行 Update Diagram 并保留完整 diagnostics；通过后才进入 Compile。
4. Compile 后记录 compiled port dimensions、types、sample times，特别是 `[19,1]`、`960×1`、`960×2` 和 writer input。
5. 先无设备短仿真并检查 PCM/logging，再运行四个场景的 simulation、参数敏感性和 audio quality gates。
6. 最后单独验证 Audio Device Writer playback/underrun，并在两个隔离目录生成相同输入的 WAV/PCM SHA。
7. 所有门禁有独立证据前，v0.9 始终为 `INCOMPLETE`；任何单项失败都不能推进至完成、提交或发布。

## Rebuild disposition

```text
NOT_READY_FOR_REBUILD
```

原因：当前 binary 已知错误；builder 未提供足以静态证明 default-line 清理、显式端口/尺寸/sample-time、结构检查、事务 cleanup 或 idempotence 的条件。只有完成 required patch list 并获得新静态审计通过后，才能考虑 `READY_FOR_CONTROLLED_REBUILD`.

