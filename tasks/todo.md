# 2026-07-08 固件搭建与 PRD 完善执行

> 状态: 已完成，待归档

## 2026-07-24 S12 Engine Sound Vertical Slice v0.3

> 状态：本地完成，未 push；仅离线 synthetic 声浪层，未进入 MATLAB/MCP 或实时 DSP。

- [x] 审计 v0.2 提交、产物哈希、metadata 和受保护物理边界。
- [x] 新建连续 Vehicle State Interface 与 synthetic Engine Order Model，并以 RED→GREEN 测试覆盖顶层 JSON 与非线性逐样本 RPM/load 传递。
- [x] 接入既有 synthetic source → PTR/radiation package → v0.2 design layer → 24-bit WAV 的 v0.3 编排层。
- [x] 生成两套受控 demo，验证 WAV/analysis/manifest/SHA 一致性。
- [x] 运行全量 Python 回归与 Git 范围门禁，并提交 source/test：`5d406c4 feat: add S12 synthetic engine sound vertical slice`；未 push。

### Review

- 28/28 Python tests passed; `git diff --check` passed; staged source files are all below 30 KB and contain no generated WAV/PNG, raw recording, or copyright audio.
- Final controlled outputs: `tasks/reports/runtime/s12-engine-sound-v0.3-final-r2/s12_engine_sound_demo_v03/` and `...-repeat/`; manifests and `SHA256.txt` are byte-identical. Manifest SHA-256: `3F8F03927C10E4D6ED4D7B5ADCBD0EBA624518E23C4856615B6A570B91AFA629`.
- The final bundle contains five root 48 kHz/24-bit/stereo WAVs, three load-map WAVs, top-level `vehicle_state.json`, `rpm_trace.csv`, per-case spectrum/order-map PNGs, `sound_analysis.json`, `manifest.json`, `SHA256.txt`, and the explicit boundary report. Clipping is zero; each analysis item records `engine_source_hash` and `ptr_hash`.
- Independent final review passed after correcting the top-level vehicle-state interface and replacing endpoint-only ramps with per-sample vehicle-state schedule/source trajectory propagation. FVM/HLLC/MUSCL/SSP-RK3/radiation/PTR mathematics/4D-B baseline remain untouched.

## 2026-07-24 S12 Engine Sound Vertical Slice v0.4

> 状态：本地完成，未 push；仅重构 synthetic 离线声浪的输入合同与 pre-PTR 激励链，不修改冻结物理核心。

- [x] 新增带 A/B/C 来源等级的 engine state、order 和 excitation 参数合同。
- [x] 先写拓扑、溯源、speed/acceleration 因果性、确定性和 WAV 格式测试。
- [x] 实现 Vehicle State → Excitation → PTR/radiation → fixed renderer 链路。
- [x] 生成 `v04_demo`、报告、manifest 和双构建 SHA 证据。
- [x] 完成全量回归、diff 门禁、独立审查并提交；未 push。

### Review

- `34/34` sound-simulation tests passed; v0.4-specific tests are `6/6`.
- Two controlled v0.4 bundles have byte-identical manifests and `SHA256.txt`; final manifest SHA-256 is `C6AB85B873A1CAF1544F9606D9CEB993ECC5657A865F9778DC9C32CA09A55A70`.
- `git diff --cached --check` passed before commit. Commit `cee4bed feat: refactor S12 engine excitation architecture v04` contains only seven v0.4 source/test files; no generated audio, PTR/radiation/FVM, or firmware files. Independent re-review: PASS.

## 2026-07-24 S12 Engine Sound Productization Vertical Slice v0.5

> 状态：本地完成，未 push；仅为 synthetic 离线产品化切片，未进入 MATLAB、实时 DSP 或移动端实现。

- [x] 审计 v0.4 commit、manifest、SHA、回归和受保护物理边界；保留独立 v0.3 审查报告。
- [x] 新增带 C/synthetic provenance 的 RPM×load operating-point library 与插值门禁。
- [x] 新增独立 renderer 与 JSON-only AudioParameterPackage v0.1。
- [x] 生成 `v05_demo`、未来 DSP 接口设计与双构建 SHA 证据。
- [x] 完成三项只读独立审查、全量门禁和本地提交；不 push。

### Review

- 本地提交：`1b4f06f`、`aeb8332`、`86dbdd2`、`cf7f166`、`6028802`、`fa7232c`；未 push。
- 全量 Python 声浪套件：`47/47 PASS`；包含 v0.5 的 provenance、插值、因果、48 kHz/24-bit/stereo、零削波与确定性门禁。
- 最终双构建：`s12-engine-sound-v0.5-final-r1` 与 `r2` 字节一致；manifest SHA-256 为 `3EE013DF446BB29948B1E7C1E57A6BB5DEAEAF5D9CE5FA6704521A9ED1274638`，AudioParameterPackage hash 为 `49417A181FDCB643C68640A9503A2BBDB43F44FE133267BFC87C6DB88069E356`，均绑定 `fa7232c`。
- 边界核验：`cee4bed..fa7232c` 只包含 v0.5 声音层、测试与未来接口文档；未修改 FVM、HLLC、MUSCL、Positivity、SSP-RK3、PTR/radiation 数学或 4D-B 基线。
- 三项只读独立审查均 PASS：schema/provenance/package、因果链/渲染边界、发布包/冻结物理边界；未创建 MATLAB 或 MCP 会话。
- 输出逐条 metadata 均标记 `synthetic`、`uncalibrated`、`offline`、`not_realtime_qualified`；不是 OEM 或实车复刻。未完成 OEM 标定、实车测量、Android/ESP32、CAN 和实时 DSP。

## 2026-07-26 S12 Engine Sound Runtime Simulator v0.6

> 状态：已完成；授权范围为 Python PC 连续声浪模拟与未来 App 合同，不进入 MATLAB/MCP、ESP32、I2S、手机或 CAN 硬件。

- [x] 审计 v0.5 基线、冻结物理边界和既有测试。
- [x] 新增 100 Hz synthetic vehicle-state stream 与平滑运行状态机。
- [x] 新增保持相位的 20 ms PCM runtime、无改动的 PTR/radiation 状态适配和环形缓冲模拟输出。
- [x] 新增 App JSON ingress 模拟、AudioParameterPackage v0.2 与十分钟虚拟时钟 runner。
- [x] 运行全量回归、双次十分钟确定性验证、独立审查、报告与本地提交；未 push。

### 复核（2026-07-26）

- 最终提交：`df80e94`；未修改 FVM、HLLC、MUSCL、SSP-RK3、PTR core 或 radiation boundary。
- Python 全量回归：63/63 PASS；`git diff --check` PASS。
- 两次 600 s 虚拟运行：各 30,000 帧、60,000 状态更新、48 kHz/24-bit/stereo、clipping=0、underrun=0；PCM SHA-256 一致。
- 同提交 Windows waveOut 设备烟测：1 s / 50 帧、clipping=0、underrun=0。
- 两次独立只读复审：PASS，无阻塞项。
- 保持 synthetic、uncalibrated、offline、not realtime-qualified；未进入 Android、ESP32、I2S、CAN 或手机硬件。

## 2026-07-26 S12 Runtime Vehicle Interface v0.7

> 状态：执行中；授权范围为 Python localhost Vehicle State API 与 PC PCM 流模拟，不进入 MATLAB/MCP、Android、ESP32、CAN、I2S、OBD 或车载部署。

- [x] 建立带类型、单位、范围和 C/synthetic provenance 的 Vehicle State Packet v0.1 合同。
- [x] 建立连续 synthetic 100 Hz Vehicle State Stream 与 v0.6 的两包/20 ms PCM 适配层。
- [x] 建立仅绑定 127.0.0.1 的 POST /vehicle_state 模拟接口与异常 fallback。
- [x] 输出 v0.7 demo、全包 p50/p95/p99 延迟报告、App 接口文档和确定性 PCM SHA。
- [x] 完成两次十分钟真实 100 Hz demo、独立审查与最终本地提交；不 push。

##### 当前复核

- 73/73 Python 测试通过；`git diff --check` 通过。
- 延迟合同从 server ingress（JSON 解析前）量至 PCM ready；每个 100 Hz packet 都有一条样本，首包包含等待配对包的节拍时间。

##### Review

- 功能提交 `5322a79`，延迟合同修复提交 `fcbe3d9`；未 push。两份既有未跟踪 review 文档保持原样。
- 全量 Python 回归 73/73 PASS。正式 paced r1/r2 各为 600 秒、60,000 packets、30,000 PCM frames、60,000 latency samples，p99 分别为 16.4318 ms / 16.3815 ms，clipping=0、underrun=0。
- PCM SHA-256 与 AudioParameterPackage hash 双轮一致；无 WAV/PCM/RAW。`git diff --check` 通过，PTR/radiation/FVM/HLLC/MUSCL/positivity/SSP-RK3 与 accepted baseline 未变；两次独立只读复审 PASS。

## 2026-07-26 S12 Android Vehicle Sound Controller v0.8

> 状态：已完成；仅 Android synthetic control plane → localhost WebSocket → PC Runtime，未进入 CAN、OBD、ESP32、I2S、实车或 MATLAB。

- [x] 审计 v0.7 基线：Git、73/73 回归、双 600 秒报告及确定性 hash。
- [x] 定义 v0.8 C/synthetic protocol 与仅绑定 localhost 的 WebSocket runtime server。
- [x] 构建 Start/Stop/Send Vehicle State 的最小 Android Debug-signed Demo。
- [x] 完成 100 Hz/reconnect/invalid-packet/latency 自动测试和两次 600 秒端到端 demo。
- [x] 审核冻结边界、无新增大文件/密钥/私有数据并本地提交；未 push。

##### Review

- 最终提交：`1bf88fb` (`feat: add Android vehicle state interface`)；独立审查发现的长 gap 无界回填、Android Stop 阻塞/API 26 `readNBytes` 不兼容及 Debug 签名说明均已最小修复并复审 PASS。
- Python 全量回归 84/84 PASS；离线 Android Debug 构建 PASS；`git diff --check` PASS。相对 `fcbe3d9` 的 16 个改动文件中最大仅 11,748 B，冻结 Engine Runtime/PTR/Radiation/FVM/HLLC/MUSCL/Positivity/SSP-RK3/MATLAB 路径无改动。
- 正式 paced r1/r2 各为 600.0 s、60,000 packet、30,000 PCM frame、60,000 latency sample、一次 reconnect、clipping=0、underrun=0、fallback=0；p99 为 17.7174 ms / 20.4995 ms。PCM SHA-256 与 AudioParameterPackage hash 双轮一致。
- 最终 demo：`tasks/reports/runtime/v08_android_demo/`，包含 Debug-signed APK、vehicle trace、runtime/latency JSON、PCM hash（写入 runtime report）和 README；产物不含 WAV/PCM/RAW。仍为 synthetic、uncalibrated、offline、not realtime-qualified，且未进行 Android 设备运行资格认证。

## 2026-07-26 S12 Simulink Audio Tuning Playground v0.9

> 状态：FAIL（未完成）。首次 Desktop 构建成功保存 `.slx`，但 Simulink 编译在 `Engine Excitation/Order Harmonic Transient` 失败；静态 archive 已证明 builder 错接了新 Subsystem 的默认标量 `In1 -> Out1` 旁路。修复尚未在 Desktop 中执行，任何音频/试听/SHA 均不可声称 PASS。

- [x] 读取 v0.8 基线、S12 声学/PTR 边界、MATLAB 生命周期教训及 Simulink 库门禁；确认没有活动 MATLAB/MCP/watchdog。
- [x] 创建实施计划：`prj/docs/superpowers/plans/2026-07-26-s12-simulink-sound-playground-v09.md`。
- [x] 静态确认 R2026a `dspsnks4/Audio Device Writer` 库和 48 kHz/24-bit 参数；新增隔离的 synthetic Dashboard/renderer/导出/测试脚本。旧 V6 声学重算路径未复用。
- [x] 从真实编译报错和 `.slx` archive 定位两项 builder 缺陷：Audio Device Writer 路径的字面 `\n`，以及每个新 Subsystem 未删除默认端口。两项均已加入回归契约并静态修复。
- [ ] 在安全 existing-session 控制面可用后，重建并冷重载新 `S12_Sound_Playground.slx`，确认配置端口为 Dashboard `0/1`、Vehicle `1/1`、Engine `1/2`、PTR `2/2`、Renderer `2/1`，再确认 Audio Device Writer 实际播放。
- [ ] 运行 v0.9 测试、场景导出与两次 WAV SHA；记录模型执行、无 clipping 与冻结边界审计后提交；不 push。

### v0.9 离线修复冻结（2026-07-26）

> 状态：`generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`。当前 `S12_Sound_Playground.slx`（SHA `FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0`）为 `PRE_REPAIR_INVALID_AUDIT_EVIDENCE`，不得覆盖、修改、删除或冒充修复版。

- [x] 仅离线重构为事务 builder、Port/Signal Contract、模式/场景/重置/等价合同及分层静态测试；未启动 MATLAB/MCP/Simulink，未调用 `sim`，未提交。
- [x] 已生成 v2 审计 ZIP（SHA `6B4AA3B8C99639D3B9D4DFCC4F65196BDDE12E421801E7491283845AB8EC3BB6`），包含旧失败 SLX/SHA、修复源码、合同、测试、计划与离线报告；已排除 `slprj`、cache、WAV/PCM、凭据和整个仓库。
- [ ] 只有独立审核明确 `READY_FOR_CONTROLLED_REBUILD` 后，才允许实际 MATLAB 重建、compile、simulation、audio、sensitivity 和 repeatability 阶段。
- [ ] 通过模型冷重载、声音响应、无 clipping、两次同参数 WAV SHA、一致性/冻结边界审计后提交；不 push。

### v7 离线最小收口（已完成离线范围）

> 状态：`generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`。仅修复第六次独立审计指出的未来源码合同并制作审计包；严禁 MATLAB/Simulink/MCP/SLX 操作。

- [x] 先以 v7 静态和 source-equivalent 数值门禁重现 authorization、Signal Specification、敏感性、清理及事务排序缺口。
- [x] 将 future-only authorization provenance 升级到 sixth audit v6，并补齐 Signal Specification、order-band/delta-PCM、owned-cleanup 和 lock/report 合同。
- [x] 仅运行离线 Python/static 与新鲜解压自检，生成单一源快照的 v7 ZIP；不将任何离线结果描述为运行时验证。

### v7 Review

- v3–v7 Python static suites：`73/73`；v7 的 load/acceleration 为纯 Python 的 frozen-source 等价数值检查，不是 Simulink PCM 证据。
- 新鲜解压 package self-test：PASS。`S12_Simulink_Sound_Playground_v09_audit_v7.zip` SHA-256：`BE24906EFCB9DC8FE70B4DE2CA3E8FAE7EF752F644583A37D3BBF6E91307EBEF`；163 entries；canonical source SHA-256：`8F36C84735D2DE8461F417FE00E6E811F1AB48C628590D7BA841D3A8484D2F3D`（90 files）。
- 未启动 MATLAB/Simulink/MCP，未加载、编译、运行或修改 SLX，未产生 PCM、音频、试听、仿真或重复性运行证据；v0.9 仍为 `generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`。

## 2026-07-09 Python 声浪仿真原型

> 状态: 已完成原型；待听感调参和固件移植

### 执行计划

- [x] 梳理 `docs/reference` 中可复用的声音算法参考，明确哪些进入 Python 原型，哪些暂不进入固件。
- [x] 用 TDD 先写离线声浪模型测试：速度/油门/加速度/刹车/超速 mute 到 RPM、谐波、WAV、固件参数表。
- [x] 实现 `tools/sound_sim` Python 仿真工具，使用标准库生成 `.wav`、`.csv`、`.json`，不依赖 MATLAB。
- [x] 生成一组演示工况输出到 `build/sound-sim`，作为听感和后续 MATLAB/Octave 对照基线。
- [x] 补充文档说明：怎么运行、参考来源、当前算法边界、如何移植到 ESP32。
- [x] 运行测试和仿真命令，记录 Review。

### Review

- 参考归纳：`simulating-EV-sound-main` 适合作为简单可控 EV oscillator 思路；`tesla-engine-sound-main` 的 `RpmMapper.kt` 提供速度/油门/功率到虚拟 RPM 的映射思想；`VehicleNoiseSynthesizer-main` 提供加速/减速不同音色、谐波/亮度随负载变化的设计方向。
- 已新增 `tools/sound_sim/sound_model.py`、`simulate_sound.py`、`README.md`、`tests/test_sound_model.py`。实现完全使用 Python 标准库，不依赖 MATLAB、Octave、numpy 或 scipy。
- 算法边界：当前是离线可听原型，不是最终 PRD 声浪模型；它实现速度、油门、加速度、刹车和超速 mute 到 RPM、频率、幅度、亮度、5 阶谐波的映射。
- TDD 证据：先运行测试失败，失败原因是 `ModuleNotFoundError: No module named 'sound_model'`；实现后 `python -m unittest discover -s tools\sound_sim\tests -v` 通过，`3/3`。
- 生成证据：`python tools\sound_sim\simulate_sound.py --out build\sound-sim` 生成 `jovi_ev_sound_demo.wav`、`jovi_ev_sound_trace.csv`、`jovi_sound_params_v1.json`。
- WAV 检查：`jovi_ev_sound_demo.wav` 为 mono、16-bit、44100 Hz、529200 frames、12.0 秒。
- 固件移植入口：`jovi_sound_params_v1.json` 已导出 `schema=jovi.sound_model.v1`、RPM breakpoints、frequency、amplitude、brightness、Q15 harmonic gains；下一步可移植到 `components/audio` 的固定点/轻量 float oscillator。
- 验证：`git diff --check` 通过，仅有既有 CRLF 规范化提示；本轮未修改固件运行时代码，因此未重跑 ESP-IDF build。

## 2026-07-09 IRAM 优化与公开中文文档修复

> 状态: 已完成；IRAM release gate 未关闭

### 执行计划

- [x] 采集 IRAM 归因：重跑 `size-components`，检查 `.iram0.text` 符号和 sdkconfig IRAM 相关配置。
- [x] 判断是否需要更强 MCU：先区分“芯片容量不够”还是“ESP-IDF 配置把函数放进 IRAM”。
- [x] 实施低风险 IRAM 优化：优先调整可回退配置，不改业务逻辑和 BLE/OTA UUID 契约。
- [x] 修复公开文档中文乱码：`README.md`、`docs/04-planning/01-firmware-roadmap.md`、`docs/09-backlog/01-firmware-backlog.md`。
- [x] 跑门禁：`build`、`size`、`size-components`、`openspec validate --all --strict --json`、`git diff --check`。
- [x] 写入 Review：IRAM 优化前后数据、是否建议换 MCU、文档修复范围。

### Review

- IRAM 归因：业务组件和 S7 新增组件不是主要来源；`size-components` 显示 `network`、`iot`、`ota`、`status` 组件 IRAM 均为 `0`。当前压力主要来自 ESP-IDF 底层系统、flash/cache、中断向量、wireless/PSRAM/RMT 配套路径。
- 已确认源码中没有明显 `IRAM_ATTR` / `RTC_IRAM_ATTR` 误用；不能通过移动业务常量或删除应用级 IRAM 标记快速释放预算。
- 已保留低风险配置：`# CONFIG_SPI_SLAVE_ISR_IN_IRAM is not set`，因为当前工程不使用 SPI slave。该项不会破坏 BLE/OTA UUID 契约，也不改变主功能逻辑。
- 对照实验：尝试 `CONFIG_SPI_FLASH_ROM_IMPL=y` 可降低镜像体积和部分 DIRAM，但没有降低 `idf.py size` 报告的 `IRAM 16383 / 16384`；同时会牺牲当前对 BLE/OTA 更有价值的 flash auto-suspend 策略，因此未采用。
- MCU 结论：暂不建议立刻更换更强 MCU。当前不是 app flash 或 PSRAM 明显不够，而是 ESP32-S3 + WiFi + BLE + PSRAM + RMT + OTA 组合下的 16KB 高优先级 IRAM 小窗被顶满；应先上板做 BLE/WiFi/OTA 并发压力测试，再决定是否分档功能或升级平台。
- 文档修复：已重写公开入口 `README.md`、`docs/04-planning/01-firmware-roadmap.md`、`docs/09-backlog/01-firmware-backlog.md` 的中文内容，并保留 README 中英文介绍。
- 文档扫描：`rg "鍥|绋|鐩|寰|宸|鈥|乣|�"` 对上述公开文档未命中。注意 `idf.py size-components` 表格边框在 PowerShell 中仍会出现乱码，这是终端 box-drawing 编码显示问题，不是公开 Markdown 正文乱码。
- 验证 1：`.\scripts\esp-idf.ps1 build` 通过，`tesla_simulate_vico.bin binary size 0x1121b0`，OTA app partition `0x400000`，剩余 `0x2ede50`。
- 验证 2：`.\scripts\esp-idf.ps1 size` 通过；Flash Code `851830`，Flash Data `183928`，DIRAM `98287 / 341760`，IRAM `16383 / 16384`，剩余 `1` byte。
- 验证 3：`.\scripts\esp-idf.ps1 size-components` 通过；组件级证据显示 S7 业务层 IRAM 为 `0`，IRAM release gate 仍未关闭。
- 验证 4：`openspec validate --all --strict --json` 通过，`6/6`；`git diff --check` 通过，仅有 CRLF 规范化提示。

## 2026-07-09 软件是否可以收工评估

> 状态: 阶段可收口；最终交付不可收工

### 评估结论

- 可以收工的范围：S0-S7 的“可编译固件基线 + BLE/Network/IoT/OTA 架构迁移 + 文档骨架 + GitHub 主分支同步”可以作为阶段里程碑收口。
- 不能收工的范围：产品级软件交付仍不能关闭，因为硬件验收、IRAM release gate、产品级声音算法、OTA 实机成功/失败路径、公开文档中文乱码修复仍未完成。

### 当前证据

- `.\scripts\esp-idf.ps1 build`：通过，已生成 `E:\Tesla_speed\prj\build\tesla_simulate_vico.bin`。
- `.\scripts\esp-idf.ps1 size`：通过；IRAM `16383 / 16384`，剩余 `1` byte，必须作为 release 阻塞或明确风险接受项。
- `openspec validate --all --strict --json`：通过，`6/6`。
- `git diff --check`：通过，无 whitespace error。
- `E:\Tesla_speed\prj`：`main...origin/main`，当前无 active changes。

### 必须继续完成

- 上板 `flash monitor`，记录 boot log、panic/reset、版本和分区。
- BLE 实机验收：广播 `0xfff0`/`0xffe0`，`ffe2` 读取，`ffe8` 写入/读回。
- 外设验收：SD、I2S、encoder、throttle pot、WS2812、CAN listen-only。
- S7 实机验收：WiFi join、MQTT 上下行、HTTPS OTA 成功和失败保护。
- IRAM 风险处理：降低占用或形成实机压力测试接受记录。
- S8 声音算法：速度/加速度/负载差异化声音建模，MATLAB 或等效仿真定参后再移植。
- 修复公开文档中文乱码，避免 README/roadmap/backlog 交付体验失真。

## 2026-07-09 VSCode/EIM ESP-IDF 编译日志复核

> 状态: 已完成；子模块清警告因网络超时保留为非阻断项

### 执行清单

- [x] 读取 Jovi 粘贴的 EIM/PowerShell 编译日志。
- [x] 确认 `Project build complete` 与 `tesla_simulate_vico.bin` 产物是否存在。
- [x] 区分真正阻断错误与 ESP-IDF 子模块/版本提示。
- [x] 尝试修复 ESP-IDF `micro-ecc` 子模块 out-of-date 警告。
- [x] 复跑 `scripts\esp-idf.ps1 build` 验证。
- [x] 写入 Review 和必要 lessons。

### Review

- Jovi 粘贴的日志本身已经是一次成功编译：末尾出现 `Project build complete`，并生成 `E:\Tesla_speed\prj\build\tesla_simulate_vico.bin`。
- 本机复核产物：`tesla_simulate_vico.bin` 大小 `1122736` 字节，时间 `2026-07-09 09:41:39`。
- 重新执行：`.\scripts\esp-idf.ps1 build *>&1 | Tee-Object E:\Tesla_speed\tasks\build_debug_20260709_eim_recheck.log`，exit=0，再次通过。
- 非阻断提示来源：ESP-IDF 安装目录 `E:\project\ESP_IDF_support\v5.3.2\esp-idf` 为 `v5.3.2-dirty`，`.gitmodules` 使用 ghfast 镜像，`micro-ecc` 子模块当前提交 `601bd110...`，而 ESP-IDF 期望 `24c60e24...`。
- 已尝试最小修复：`git submodule update --init --recursive -- components/bootloader/subproject/components/micro-ecc/micro-ecc`，但 ghfast 拉取超时，已停止残留进程。该警告不影响当前 build 产物生成。
- VSCode 判断口径：如果 Output/ESP-IDF 里没有 `Project build complete` 才算失败；如果有这行，说明编译已经成功，下一步应执行 flash 或处理烧录端口。

## 2026-07-09 编译失败排障

> 状态: 已修复，已提交并推送官方 main

### 执行清单

- [x] 复现当前 `E:\Tesla_speed\prj` 本地 build，并记录完整错误/警告边界。
- [x] 检查最近目录整理提交是否影响 CMake / ESP-IDF 构建输入。
- [x] 对比 VSCode ESP-IDF 扩展路径和 `scripts/esp-idf.ps1` 路径。
- [x] 形成根因判断：代码问题、构建缓存问题、ESP-IDF 环境问题或 VSCode 配置问题。
- [x] 给出可执行修复步骤，并在需要时修改仓库脚本/文档。
- [x] 写入 Review 和 lessons，避免再次把“有非阻断提示”说成无风险。

### Review

- 根因：系统 PATH 中 `D:\Python\Python3.14\Scripts\ninja.exe` 版本为 `1.13.0.git.kitware.jobserver-pipe-1`，比 ESP-IDF v5.3.2 bundled `ninja 1.12.1` 更靠前。ESP-IDF `export.ps1` 会输出 `Not using an unsupported version of tool ninja found in PATH: 1.13.0` 到 stderr；在 VSCode/日志捕获/严格 PowerShell 管道中会被提升为 `NativeCommandError`，导致用户看到“不能编译”。
- 不是代码语法或 CMake 组件错误：直接构建能生成 `tesla_simulate_vico.bin`，最近 docs 目录整理不参与固件编译输入。
- 修复：
  - `scripts\esp-idf.ps1` 在调用 ESP-IDF `export.ps1` 前，先把 ESP-IDF Python env、bundled `ninja 1.12.1`、bundled `cmake 3.30.2` 和 IDF tools 放到 PATH 前面。
  - `README.md` 增加 `unsupported ninja 1.13.0` 排障说明。
  - 本机 `.vscode/settings.json` 增加 `idf.customExtraVars.PATH`，让 VSCode ESP-IDF 扩展优先使用 ESP-IDF bundled tools；该文件被 `.gitignore` 忽略，不随仓库提交。
- 验证证据：
  - 复现失败：`.\scripts\esp-idf.ps1 build *>&1 | Tee-Object ...` 曾失败于 `NativeCommandError` / unsupported ninja。
  - 修复后同一捕获方式通过，日志 `tasks\build_debug_20260709_after_fix.log` 记录 `Project build complete`，bin size `0x1121b0`。
  - `.\scripts\esp-idf.ps1 size`：通过；IRAM 仍 `16383 / 16384`，这是既有 release 风险，不是本次编译失败根因。
  - `openspec validate --all --strict --json`：通过，`6/6` pass。
  - `git diff --check`：通过，仅 CRLF 提示，无 whitespace error。
- Git 提交/远端状态：
  - 本地提交：`21f5d7f fix: prefer bundled esp-idf build tools`。
  - 官方远端：`https://github.com/Jovifei/Tesla_Simulate_vico.git` 的 `refs/heads/main` 指向 `21f5d7f351d24274979944b1fb88f02f95c63bb5`。
  - `E:\Tesla_speed\prj` 工作树：`main...origin/main`，无 active changes；`.vscode/` 为本机 ignored 配置。

## 2026-07-09 文档目录层级与命名整理

> 状态: 已完成，已提交并推送官方 main

### 执行清单

- [x] 盘点 `E:\Tesla_speed\prj\docs` 当前目录层级、Git 跟踪范围和引用位置。
- [x] 制定统一命名：目录使用 `NN-english-kebab`，文件使用 `NN-english-kebab.md`，中文保留在标题和正文。
- [x] 重命名 docs 目录与当前交付文档，修复 `docs/README.md` / `docs/GUIDE.md` 编码损坏。
- [x] 更新 `.gitignore`、`README.md`、`PLAN.md`、OpenSpec/task 文档中的旧路径引用。
- [x] 运行引用扫描、OpenSpec 验证和 Git diff 检查。
- [x] 写入 Review：改名映射、验证证据、仍需注意的未跟踪历史资料。

### Review

- 命名规则已改为 `NN-english-kebab`：例如 `docs/04-planning`、`docs/09-backlog`。
- 已重命名当前交付文档：
  - `docs/04-PLN-计划/01-PLN-固件完成路线图.md` -> `docs/04-planning/01-firmware-roadmap.md`
  - `docs/09-TOD-待完成/01-TOD-固件待完成清单.md` -> `docs/09-backlog/01-firmware-backlog.md`
- 已新增可提交的公开文档骨架：`00-reference`、`01-architecture`、`02-requirements`、`03-protocols`、`04-planning`、`05-execution`、`06-testing`、`07-debugging`、`08-reports`、`09-backlog`、`10-learning`，每个目录有 `00-guide.md`。
- 已修复 `docs/README.md`、`docs/GUIDE.md`、根 `README.md` 的可读性和目录入口，并清理 `.gitignore` 里的乱码路径白名单。
- 验证证据：
  - 旧路径/乱码扫描：无命中。
  - `openspec validate --all --strict --json`：通过，`6/6` pass。
  - `git diff --cached --check`：通过，无 whitespace error。
  - `.\scripts\esp-idf.ps1 build`：通过，生成 `tesla_simulate_vico.bin`，binary size `0x1121b0`，OTA app partition 剩余 `0x2ede50`（约 73%）。
- 构建非阻断提示：ESP-IDF 日志仍有 `micro-ecc` submodule out-of-date 与 `fatal: Needed a single revision` 文本，但命令 exit=0，产物生成正常；该提示不是本次目录整理引入。
- 注意：`docs/superpowers` 保留为 agent 工作流目录；部分本地历史模板/旧文档仍被 `.gitignore` 忽略，未强行纳入公开交付骨架。
- Git 提交/远端状态：
  - 本地提交：`9d65f6c docs: normalize documentation layout`。
  - 官方远端：`https://github.com/Jovifei/Tesla_Simulate_vico.git` 的 `refs/heads/main` 指向 `9d65f6c73b52ce27113043d44398ec46b8e5323e`。
  - `E:\Tesla_speed\prj` 工作树：`main...origin/main`，无 active changes。

## 2026-07-08 S7 旧工程逻辑对齐执行（老工程参考路径）

> 状态: 已完成，已提交并推送官方 main

## 里程碑目标

- 在不改 BLE UUID 契约前提下，完成 “status/network/ota/iot” 分层基线：`runtime status`、`network`、`iot`、`ota`
- 参考 `wifi_esp32_ct` / `smart-controller-esp32s3` / `smart-controller-gd32f4` 的运行节奏，25ms 主循环内仅下发状态与发布，不直接执行网络重传/OTA 长任务
- 补齐 S7 设计/提案/验收文档与 OpenSpec 对齐记录

## S7 任务清单

- [x] Task0：建立 s7 变更提案与 todo 入口（`tasks/todo.md` + `openspec/changes/s7-iot-ota-architecture/*`）
- [x] Task1：创建 `components/status`（状态模型 + diagnostics JSON + copy 接口）
- [x] Task2：扩展 `RuntimeConfig` IoT 字段 + `SdConfigStore` 持久化
- [x] Task3：BLE `ffe8` 扩展为 OTA/IoT JSON（保留 `ffe8` UUID，不改协议）
- [x] Task4：创建 `components/network`，按事件组管理 WiFi 连接与重连
- [x] Task5：OTA 重构（请求模型 + `running` 状态 + 版本捕获）
- [x] Task6：创建 `components/iot`，支持 MQTT 下行 `ota_start` 与状态发布
- [x] Task7：App 注入 `network` / `iot` / `ota` / `status` 联动
- [x] Task8：BLE 诊断与设备状态位（`ffe5` + `ffea`）统一使用 `status::RuntimeStatus`
- [x] Task9：sdkconfig/CMake 与 IRAM 风控记录（`size-components` 必须重跑）
- [x] Task10：OpenSpec 与文档同步（`ble-config`、`peripherals`、`README`、`PLAN`、`docs/04-planning`、`docs/09-backlog`）
- [x] Task11：门禁复测（build / size / size-components / openspec）
- [x] Task12：硬件验收清单更新（阻塞项可见）

## 2026-07-08 S7 迁移计划复核与修复（本轮）

> 状态: 执行中

### 执行清单

- [x] 复核 S7.0 文档映射：旧工程参考、BLE UUID 不变、25ms 不阻塞、USB CDC 后移。
- [x] 复核 S7.1 状态模型与配置模型：`RuntimeStatus`、WiFi/OTA/IoT 字段、SD 旧 JSON 兼容。
- [x] 复核 S7.2 Link/WiFi：EventGroup、STA connect/reconnect/stop、BLE 写配置后不阻塞主循环。
- [x] 复核 S7.3 IoT/MQTT：上行状态/车辆/OTA，下行 `ota_start` 与错误 ack。
- [x] 复核 S7.4 OTA：后台 task、boot/config/cloud request、进度/失败/分区状态。
- [x] 复核 S7.5 App 集成：25ms tick 内不做阻塞网络/OTA，统一状态发布到 BLE。
- [x] 修复已发现缺口：文档乱码、OpenSpec 漂移、状态合并风险、构建风险。
- [x] 运行门禁：`build`、`size`、`size-components`、`openspec validate --all --strict --json`、`git diff --check`。
- [x] 写入 Review：完成项、修复项、仍需硬件验证项、提交/远端状态。

## Review

- 任务边界已锁定：硬件验证继续阻塞于 BLE 广播/连接、WiFi join、HTTPS OTA 现场验证。
- 按“无跳步”原则，本轮先把文档和接口边界打通，再做分层实现与功能扩展。
- 本轮复核修复已完成：
  - 修复 `NetworkManager::begin()` 先注册事件 handler、后创建默认 event loop 的启动风险。
  - 修复 WiFi connected bit 被 `xEventGroupWaitBits(..., pdTRUE, ...)` 清掉导致 25ms tick 重复重连的风险。
  - 修复 OTA request path 内 `g_status_lock` 重入调用 `setOtaStatus()` / `setRuntimeVersionFromRunningImage()` 的死锁/断言风险。
  - 修复 BLE `ffe8` JSON 读出 `client_id` 但写入只认 `mqtt_client_id` 的兼容问题。
  - 修复 MQTT 每 25ms tick 发布 device/vehicle/OTA JSON 的主循环压力，改为分频发布且仅 Cloud 状态发布。
  - 修复 BLE 配置更新后 Network/IoT 未同步 seed 的问题；WiFi 配置变化会清旧状态并由网络层重连。
  - 增加 OTA 目标版本和文件长度校验；MD5/hash 流式校验仍列为后续增强，不假装完成。
- 最终门禁证据：
  - `.\scripts\esp-idf.ps1 build`：通过，`tesla_simulate_vico.bin` 生成，binary size `0x1121b0`，OTA app partition 剩余 `0x2ede50`（约 73%）。
  - `.\scripts\esp-idf.ps1 size`：通过；IRAM `16383 / 16384`（99.99%，剩余 1 byte），DIRAM `98287 / 341760`（28.76%）。
  - `.\scripts\esp-idf.ps1 size-components`：通过；S7 新增 `network/iot/ota/status` 组件 IRAM 为 0，IRAM 主要来自 `libesp_system.a`、`libspi_flash.a`、`libxtensa.a`、`libesp_hw_support.a` 等底层库。
  - `openspec validate --all --strict --json`：通过，`6/6` pass（5 main specs + 1 change）。
  - `git diff --check`：通过，仅有 Windows CRLF 规范化提示，无 whitespace error。
- Git 提交/远端状态：
  - 本地提交：`2c812f0 feat: align s7 iot ota architecture`。
  - 官方远端：`https://github.com/Jovifei/Tesla_Simulate_vico.git` 的 `refs/heads/main` 指向 `2c812f01c285c1ce27b28fda4b9c877eb9caa487`。
  - `E:\Tesla_speed\prj` 工作树：`main...origin/main`，无 active changes。
- 仍未完成/仍阻塞：
  - 硬件验收未做：BLE 广播/连接/读写、WiFi join、MQTT 上下行、HTTPS OTA 成功/失败、SD/I2S/ADC/LED/CAN 实机行为。
  - IRAM release gate 未关闭：仍是 1 byte margin，只能作为明确风险进入硬件压测，不能标为 release clean。
  - OTA MD5/hash 校验未实现：当前已校验 version/file_size，hash 需要后续接入流式校验或签名策略。

## S6 里程碑收口与交付门禁

- 最新状态快照（`2026-07-08 17:00:00`）
  - OpenSpec: 从 `E:\Tesla_speed\prj` 执行 `openspec validate --all --strict --json` 通过（`5/5`）
  - IDF 构建: `.\scripts\esp-idf.ps1 build` 通过；本次验证构建版本为 `7e92ca3-dirty`，生成 `tesla_simulate_vico.bin`
  - IDF 体积: `.\scripts\esp-idf.ps1 size` 通过；IRAM `16383 / 16384`（`99.99%`），剩余 `1` byte
  - IRAM 归因: `.\scripts\esp-idf.ps1 size-components` 通过；主要压力来自框架库（`libesp_system.a`、`libesp_hw_support.a`、`libbtdm_app.a`、`libheap.a`）
  - 主线提交点：`7e92ca3`（`S4 archive + push`），当前验证工作树为 dirty 状态
- 产物基线：`E:\Tesla_speed\prj\build\tesla_simulate_vico.bin`

## S6.1~S6.4 计划清单（本轮新增）

- [x] S6.0 里程碑收口：`todo.md` 状态与同步入口更新为“已完成，待归档”，新增最新状态快照。
- [x] S6.1 BLE 运行时闭环验收：新增一份手工验收清单（不改 BLE 协议字段）。
- [x] S6.2 IRAM 风险整改：执行 `idf.py size-components`，归因主要来自框架 IRAM；完成低风险优化检查。
- [x] S6.3 PRD 与下一阶段拆解：更新 `docs/PRD/codex/PRD__prd-v20260522-codex-v4.2-current.md`。
- [x] S6.4 交付门禁与归档：形成 S6 交付凭证（openspec/build/size/硬件阻塞说明）。

## 计划清单（S5 回顾）

- [x] S5.2 BLE PRD 对齐修复：把 `0xfff0` 作为主服务、`0xffe0` 作为历史兼容服务；`ffe1..ffeE` 在 `0xfff0` 下完整可见。
- [x] S5.3 App 周期修正：`app::App::tick()` 里下推 `VehicleState` 快照到 BLE `ffe2`，并保持 25ms 周期。
- [x] S5.4 主循环节拍优化：主循环改为 25ms，LED 心跳独立 1s 周期。
- [x] S5.5 PRD 文档同步：`openspec/specs/ble-config/spec.md` 与实现一致，补齐 `ffe8..ffeE` 说明。
- [x] S5.6 验收门：`idf.py build`、`idf.py size`、`openspec validate --all --strict` 通过。

## 2026-07-08 PRD 与固件验收补齐任务（新增）

- [x] 梳理 `docs/PRD/codex/PRD__prd-v20260522-codex-v4.2-current.md` 编码损坏内容，重写为可读的「固件实施进度 PRD」：
  - 保留核心目标（CAN/listen-only、I2S、BLE、外设）；
  - 新增“已实现 / 待实现 / 阻塞”状态矩阵；
  - 增加验收门（build、spec、硬件/外围约束）。
- [x] 更新 `prj/PLAN.md` 与 `prj/README.md`，保证状态与真实实现一致（S0~S4 + S5.1~S5.6）并移除明显乱码信息点。
- [x] 输出一次完整复核记录：`tasks/todo.md` Review 补充 openspec/build 的命令与关键输出摘要。

## Review

### 里程碑更新

- BLE/主循环相关实现已与计划一致落地；`openspec validate --all --strict` 已通过。
- PRD 文件已重写为 UTF-8 可读版本并加入实现矩阵，后续仅更新该文档版本而不再维护乱码副本。
- `idf.py build` 已重新验证通过，构建版本为 `7e92ca3-dirty`，镜像大小为 `0xB3D00`。
- `idf.py size-components`/`idf.py size` 显示 IRAM 使用率在边界附近（`16383/16384`，99.99%）；风险归因主要为框架库层（`libesp_system.a`、`libesp_hw_support.a`、`libbtdm_app.a`、`libheap.a`、`libbt.a`）。
- `tasks/todo.md` 现作为该执行的单一真实状态源（请以本文件最新“状态/复核”段为准）。

### 复核记录

- `openspec validate --all --strict --json`（在 `E:\Tesla_speed\prj` 执行）：`5/5` 全部通过，详见本轮日志。
- `idf.py build` / `idf.py size` / `idf.py size-components`：通过，`tesla_simulate_vico.bin` 可在 `prj/build` 产出，并有固定化复核证据。
- BLE 运行时验收清单已形成，但因当前环境无实机，广播、建链、读写回读仍标记为 `BLOCKED`，未以推测替代证据。
- 下一步建议（已形成验收清单）：
  - [x] 增加最小 BLE 运行时验收清单（`ffe2` 读快照稳定性、`publishVehicleState` 响应）
  - [x] 规划 OTA/高级调参项并拆为 S7/S8
  - [x] 形成 IRAM 风险归因与可持续预算说明（99.99% 边界，框架占用为主）


# 2026-07-08 KiCad source route repair execution

> 状态: 已完成

## 计划清单

- [x] 去掉 root schematic 对调试模板的依赖，直接从 `gen_schematic.py` 生成干净 root sheet
- [x] 补 generator tests，锁住“无模板脏器件”和“生成结构可验证”要求
- [x] 重新跑 `pytest`、生成器、ERC、PDF/SVG/BOM/netlist 导出
- [x] 清理 `hardware_kicad`、`kicad`、`output` 中的临时/调试残留
- [x] 修正 README 和 review checklist，使文档与当前真实状态一致

## Review

- `python -m pytest tests -q`: `12 passed`
- `python scripts\gen_schematic.py`: 通过
- `.\scripts\check_erc.ps1`: 通过并产出 `output\erc.rpt`，ERC 从 `105` 降到 `24`
- `.\scripts\export_outputs.ps1`: 通过并产出 PDF/SVG/BOM/netlist
- root schematic 不再带入 `V1/R1/R2/R3/C1/VSOURCE` 模板污染，BOM 也不再含这些额外器件
- 剩余 ERC 全部是 placeholder footprint warnings，GUI 可读性检查仍待人工复核

---

# 2026-07-08 KiCad source route 5.3 completion audit

> 状态: 已完成

## 计划清单

- [x] 对照 `docs\kicad_source_route_execution_plan_for_gpt53_20260707.md` 拆验收项。
- [x] 读取工程结构、requirements、generator、tests、PowerShell 脚本和 review checklist。
- [x] 新鲜运行 Python 测试、生成器、determinism、KiCad CLI ERC/export。
- [x] 抽样读取 ERC/BOM/netlist/PDF/SVG 输出物，区分“产出存在”和“release clean”。
- [x] 输出 5.3 完成度结论、阻塞项和下一步优先级。

## Review

- 完成度结论：最小可运行闭环已完成，工程 clean release 未完成。
- 新鲜验证：`python -m pytest tests -q` 为 10 passed；`python scripts\gen_schematic.py` 可运行；二次生成 hash 一致；KiCad CLI 10.0.4 可通过 `D:\Program Files\KiCad\10.0\bin\kicad-cli.exe` 使用。
- ERC/export：`check_erc.ps1` 生成 `output\erc.rpt`，但有 105 条 violation，exit code 5；`export_outputs.ps1` 生成 PDF/SVG/BOM/netlist，exit code 0。
- 主要缺口：根图模板污染 BOM 和 ERC（`V1/R1/R2/R3/C1` 不在 YAML），存在大量临时/调试文件，README 有乱码和错误路径，GUI 可读性与 pin 约束清单尚未验收。

---

# 2026-07-07 KiCad vs 嘉立创 Pro 路线评估

> 状态: 已完成

## 计划清单

- [x] 读取用户提供的 KiCad+Codex+Python+kicad-cli 方案文本。
- [x] 盘点当前 `E:\Tesla_speed` 工程的硬件/固件/文档/自动化入口。
- [x] 对比当前工程需求与 KiCad 文本生成路线的匹配度。
- [x] 判断嘉立创 Pro / EasyEDA 是否应继续作为主画图路线或仅保留为制造/供应链路线。
- [x] 输出结论、迁移建议、风险和下一步验证门。

## Review

- 结论：之前用嘉立创 Pro / EasyEDA 不是完全错误；它适合 JLCPCB/LCSC/BOM/制造链路，但不适合作为 Codex 主自动化绘图源。
- 当前固件/系统需求本身是 EDA 工具无关的；关键约束是 `prj\components\config\include\config\pin_map.h`、PRD、终版 BOM、CAN listen-only、I2S、SD、WS2812、POT_IO1、调试/烧录路径。
- 仓库已有早期 KiCad 生成雏形：`hardware\generate_kicad_schematic.py` 和 `hardware\kicad_sch\*.kicad_sch`，但它们是 2026-05-31 的 schematic-only 输出，未证明可 ERC，且 footprint/library/PCB 还不完整。
- 本机当前未在 PATH 找到 `kicad-cli`；KiCad 路线下一步必须先安装/接通 CLI，再做单页 spike。
- EasyEDA 当前证据：`/hd-put` placement 已有验收记录，但 release 页仍是 `0 wires`；`/hd-wire` 曾被 wire create 不持久化和 500/脏状态阻塞。
- 建议路线：KiCad+Python 作为新工程 source-of-truth；EasyEDA/JLCEDA 暂保留为制造、LCSC/JLCPCB BOM/CPL/下单校验端；通过单页 KiCad spike 后再决定是否逐页迁移。

---

# 2026-07-08 KiCad v1 自动化闭环再执行（KiCad 10 安装后）

> 状态: 已完成（阻塞项：需人工 GUI 校验）

## 计划清单

- [x] 复核 `kicad-cli` 可执行文件（非 PATH）定位策略
- [x] 运行 `python -m py_compile scripts\gen_schematic.py`
- [x] 运行 `python -m pytest -q`
- [x] 运行 `python scripts\gen_schematic.py`
- [x] 运行 `.\scripts\check_erc.ps1` 并产出报告
- [x] 运行 `.\scripts\export_outputs.ps1` 并产出 PDF/SVG/BOM/netlist
- [ ] 打开 `kicad\Tesla_Sound_Simulator.kicad_sch` GUI 做阅读性复核

## Review

- KiCad 路径确认：`D:\Program Files\KiCad\10.0\bin\kicad-cli.exe`，版本 `10.0.4`（当前 PATH 仍未包含）。
- `python -m pytest -q`：通过（10 passed）
- `python scripts\gen_schematic.py`：通过（成功写入）
- `check_erc`：已执行，生成 `output\erc.rpt`，共 105 条违规（预期非零返回码）
- `export_outputs`：生成 `schematic.pdf`、`svg\*.svg`、`bom.csv`、`netlist.net`
- 结论：v1 闭环“自动生成+自动导出”已恢复；剩余工作是手工 GUI 视觉确认和逐项违规整改。

---

# 2026-06-13 嘉立创 Pro 终版原理图重绘执行

> 状态: 已重绘并验证，剩余 ESP32 官方库件 41-pin 替换为 44-pin 自定义 device

## 计划清单

- [x] 重新确认 EasyEDA bridge 和当前 6 页工程上下文。
- [x] 从终版 BOM xlsx 读取 SMT/手工-DNI 元件清单并建立页面分组。
- [x] 生成 EasyEDA API 重绘脚本，包含清页、元件搜索筛选、放置、连线和标注。
- [x] 备份当前原理图对象快照到 `tasks`。
- [x] 清理当前 6 页现有器件/导线/漂浮标注，保留图框。
- [x] 按最终硬件原理重放 6 页原理图。
- [~] 验证 44-pin ESP32、POT_IO1、IO34 未作业务 net、关键网络存在。POT_IO1/IO34/关键网络通过；官方 ESP32 component 仍为 41 pins，已绘制 44-pad 可视校验框，需后续自定义 device。
- [x] 验证 SMT BOM 不混入 C2054018/C32346/X1 等 DNI/错料项。
- [x] 输出执行报告和经验记录。

---# 2026-06-13 嘉立创 Pro 控制链路确认

> 状态: 已完成，EasyEDA bridge 与嘉立创 Pro 已接通

## 计划清单

- [x] 读取 `E:\easyeda-api-skill\SKILL.md` 和 README，确认嘉立创 Pro API 操控方式。
- [x] 检查 `E:\project\EDA_agent`，确认它是 Altium/AD MCP 链路，不是嘉立创 Pro 主入口。
- [x] 检查项目经验文档，复核历史 EasyEDA bridge 问题。
- [x] 安装 `E:\easyeda-api-skill` npm 依赖，修复 `Cannot find package 'ws'`。
- [x] 启动 EasyEDA bridge，并验证 `http://127.0.0.1:49620/health`。
- [x] 查询 `/eda-windows`，确认当前 EasyEDA 客户端尚未连接。
- [x] 找到本地 `run-api-gateway_v1.0.5.eext` 扩展包。
- [x] 输出控制链路说明文档：`docs\easyeda_control_status_v20260613.md`。
- [x] 在嘉立创 Pro 中安装/启用 `run-api-gateway.eext` 并开启外部交互权限。
- [x] `/eda-windows` 返回窗口后，执行 `eda.dmt_Project.getCurrentProjectInfo()` 验证工程上下文。

## Review

---

# 2026-07-06 Child-Claude 派发链路验证

> 状态: 已完成

## 计划清单

- [x] 读取 `C:\Users\Admin\.claude\skills\child-claude\SKILL.md`，确认本机派发方式。
- [x] 派发一个只读、单窄任务给 child-claude，禁止修改仓库。
- [x] 审核 child-claude 的 JSON/元数据返回、stderr 和 session 信息。
- [x] 记录派发链路是否可用，以及下一步是否需要调整 profile 或 schema。

## 执行原则

- Codex 负责计划、派发、审核和验收门。
- Claude Code child 只负责单个窄任务。
- 子任务必须包含路径边界、允许工具、验收标准和结构化输出字段。
- 不把 API key、profile 内容或密钥写入仓库。

## Review

- 派发命令使用 `Invoke-ChildClaude -Profile mimo-1m -AllowedTools "Read,Glob,Grep" -MaxTurns 6`。
- 结果: `Success=true`，模型为 `mimo-v2.5-pro[1m]`，stderr/raw stderr 为空。
- Child 返回了结构化字段，但包在 Markdown code fence 中；后续需要更严格要求 `Reply raw JSON only` 或使用 CLI JSON schema。
- 父级复核固件文件时间戳，确认只读任务未修改 `prj\firmware`。

## Config Update

- 已将默认 `mimo`、`mimo-1m`、`mimo-official` profile 的 `ANTHROPIC_BASE_URL` 统一为 Anthropic 兼容地址。
- 已将 profile token 改为 `MIMO_API_KEY` 环境变量引用，避免明文密钥留在 json。
- `Invoke-ChildClaude.ps1` 已增加运行时 env-ref 解析：从 User/Machine env 补到当前进程，并生成临时 settings 文件传给 Claude Code，用完删除。
- 默认 `mimo` profile 烟测通过：`Success=true`，`ModelUsed=mimo-v2.5-pro`，stderr/raw stderr 为空。

---

# 2026-07-06 Child-Claude 子 Agent 创建测试

> 状态: 已完成

## 计划清单

- [x] 重新读取 `child-claude` skill，确认派发入口和约束。
- [x] 创建一个只读 child agent，执行单个窄任务。
- [x] 审核返回结构、session、stderr/raw stderr 和模型路由。
- [x] 验证只读任务没有修改仓库文件。

## 任务边界

- 只允许 child agent 读取 `E:\Tesla_speed\prj\firmware`。
- 不允许 child agent 创建、编辑、删除、移动或格式化文件。
- 不输出或记录任何密钥。

## Review

- 第一次文件读取型 smoke test 超过外层 180 秒超时；已结束对应新 `claude` 进程并删除残留临时 settings。
- 第二次最小无工具 child agent 创建成功：`Success=true`，`Profile=mimo`，`ModelUsed=mimo-v2.5-pro`，`Turns=1`，stderr/raw stderr 为空。
- Child 返回 raw JSON 字符串，无 Markdown code fence。
- 父级复核 `prj\firmware` 文件时间戳，确认 child 没有写仓库。
- 已清理旧 Claude 临时 json 中命中的密钥痕迹，并复扫通过。

- 推荐方案：嘉立创 Pro 使用 `easyeda-api-skill` 的 HTTP/WebSocket bridge，不使用 `EDA_agent`。
- 当前 bridge 状态：`service=easyeda-bridge`、`status=ok`、`edaConnected=true`、`edaWindowCount=1`。
- 当前工程上下文已验证：Project=`1_Power`，Board=`Board1`，PCB=`PCB1`，6 页原理图可枚举。
- 注意：`ws://127.0.0.1:8765/bridge/ws` 是嘉立创 Pro MCP 面板路径，不能和 `http://127.0.0.1:49620/execute` 混用。

---
# BOM 二次审计复核任务

> 日期: 2026-06-05 | 状态: 执行中

## 计划清单

- [ ] 读取 `docs\bom\audit_tavily_20260605.md`、`Tesla_BOM_20260604_agent_all.tsv` 和本轮 Tavily BOM 输出。
- [ ] 复核对方指出的致命错误：U5/U6/U7/U8、D4/D5、J10/J11/J12、R6/R7/R8、R9。
- [ ] 联网核实关键 LCSC/JLC C 码、MPN、封装和值，不能只相信代理状态标记。
- [ ] 对认可项和反驳项分别写入新的复核报告。
- [ ] 更新 `tasks\lessons.md`，记录“跨页位号/合并 BOM 会造成错位审计”的规则。
- [ ] 做最终文件存在性、关键结论和错误扫描验证。

## 初始判断

- `Tesla_BOM_20260604_agent_all.tsv` 已发现重复 refdes 和错误保留行，不能直接作为下单 BOM。
- 对方 audit 可能正确指出了 Tavily 的错位问题，但其“以 agent_all 为基础”的最终建议需要重新审查。

---
# Tesla Speed - 设计规范文档化任务

> 日期: 2026-05-21 | 状态: ✅ 完成 (含交叉审议)

---

## 产出物

| 文件 | 行数 | 说明 |
|------|------|------|
| doc/codex/方案计划书.md | 1175 | 主方案书 (19章节, Codex+Claude合并) |
| doc/codex/research-market.md | 224 | 市场竞品调研 |
| doc/codex/research-opensource.md | ~120 | 开源项目调研 |
| doc/codex/research-canbus.md | ~280 | CAN协议调研 (含正确CAN ID) |
| doc/codex/research-hardware.md | 361 | 硬件方案调研 |

---

## Claude方案审议摘要

| 采纳 | 数量 | 内容 |
|------|------|------|
| ✅ 采纳 | 5项 | 滑动电位器、BLE变速箱配置、自动齿比、测试场景、串口格式 |
| ❌ 拒绝 | 5项 | CAN ID错误(0x2B1→0x256)、缺MCP2515、CH340G冗余、GPIO冲突、双输入过度 |

### 关键修正
- CAN ID: 0x2B1→0x256 (ESP_vehicleSpeed), 0x2B3→0x116 (DI_torque1)
- CAN硬件: 增加MCP2515控制器 (Claude方案只有收发器)
- USB: 去除CH340G (ESP32-S3原生USB-CDC)
- GPIO: KY-040从32/33改为4/5/6
- BLE: 新增ffeB-ffeE变速箱配置特性

---

# AD 原理图重建执行任务

> 日期: 2026-05-31 | 状态: 执行中

## 计划清单

- [x] 读取项目 lessons 和原理图设计规格
- [x] 确认 `eda-agent health` 可用
- [x] 在 `.mcp.json` 注册 `altium` MCP server
- [x] 备份当前 `hardware` 原理图文件
- [x] 连接或旁路调用 `eda-agent`，验证 `ping_altium`
- [x] 按规格重建 6 页原理图
- [x] 强制检查 ESP32-S3 44 pin、IO1 电位器、IO34 未接
- [x] 运行设计验证和原理图审查
- [x] 保存结果并记录 Review

## 硬性规则

- ESP32-S3-WROOM-1 N16R8 必须画全 44 个物理 pad。
- IO34 不接电位器；电位器落到 IO1。
- PCM5102A 必须包含 VCP 1uF x2，SCK 接 GND。
- CAN 仅监听，终端电阻 DNI。

## Review

- 备份目录：`E:\Tesla_speed\tasks\backup_hardware_20260531_135122`
- 执行脚本：`E:\Tesla_speed\tasks\ad_rebuild_cdx4.py` 创建 `_CDX6` 符号库，`E:\Tesla_speed\tasks\ad_place_cdx6.py` 重放 6 页原理图。
- 验证报告：`E:\Tesla_speed\tasks\ad_rebuild_validation_cdx6.json`
- AD 反查结果：组件 85 个、net label 90 个、必查网络缺失 0 个。
- ESP32-S3-WROOM-1 N16R8：`ESP32-S3-WROOM-1-N16R8-44PIN_CDX6` pin count = 44；`POT_IO1` label = 3；`GPIO34/IO34` net label = 0。
- `design_audit_schematic`：通过，overlap/wire crossing/stacked power port 均为 0。
- `design_validate`：passed=true，errors=0，warnings=822；主要是新建占位 SchLib 没有 PCB/model 映射、floating labels/power objects、duplicate nets/off-grid 信息级警告。后续进入 PCB 或生产前应补 footprint/model 并把占位 net label 收敛成真实导线连接。

---

# AD 原理图规范修复任务

> 日期: 2026-05-31 | 状态: 执行中

## 计划清单

- [x] 接受 Jovi 纠正：`_CDX6` 占位图不合格
- [x] 备份失败版本并恢复原始 12:34:47 SchDoc
- [x] 写入 lessons，禁止占位符号/floating label 冒充原理图
- [x] 确认 AD bridge 在线，`application.ping` 成功
- [x] 备份修复前硬件目录：`E:\Tesla_speed\tasks\backup_before_norm_repair_20260531_160617`
- [ ] 只读审计当前 6 页、BOM、ERC、现有 IntLib
- [ ] 以现有图为基础修复 6 页原理图
- [ ] 修复 ESP32-S3 44 pin、IO1 电位器、IO34 未接
- [ ] 清理 BOM/工程残留，不再混入 `_CDX6` 和旧重复对象
- [ ] 跑 AD audit/validate，并截图抽查 6 页
- [ ] 记录最终 Review

---

# 嘉立创 EDA 原理图实现任务

> 日期: 2026-05-31 | 状态: 执行中

## 计划清单

- [x] 接收 Jovi 指令：改用嘉立创 EDA 专业版，不继续修 AD `_CDX6` 失败图
- [x] 确认嘉立创 EDA 专业版进程在线：`lceda-pro.exe`
- [x] 备份当前嘉立创工程：`E:\Tesla_speed\tasks\backup_hardware_lc_20260531_214631`
- [ ] 定位并验证 `run-api-gateway` / `easyeda-api-skill` 自动化入口
- [ ] 打开或识别 `E:\Tesla_speed\hardware_lc\tesla_speed_lc.eprj2`
- [ ] 建立 6 页原理图：Power、MCU、CAN、Audio、Storage/LED、Test Header
- [ ] 强制检查 ESP32-S3 44 pin、IO34 未接、电位器接 IO1
- [ ] 检查关键网络、BOM 和 ERC/DRC
- [ ] 截图抽查 6 页并记录 Review

## 硬性规则

- 不导入 AD 失败页，不复用 `_CDX6` 占位符号。
- 优先使用嘉立创/LCSC 标准器件库和真实封装。
- ESP32-S3-WROOM-1-N16R8 必须完整 44 pad。
- USB-C CC1/CC2 各 5.1k 下拉。
- PCM5102A SCK 接 GND，VCP 电荷泵电容齐全。
- CAN 为监听用途，120R 标 DNI，RS 接 GND。
- 电位器为 `POT_IO1`，不得出现 `IO34` 业务连接。

## 2026-06-01 本轮执行计划

- [x] 读取 `tasks/lessons.md`，确认禁止占位图/floating label 冒充原理图。
- [x] 读取 `docs/plan/deepseek/tesla引擎系统设计总览_带参考版本.md`，提取 6 页硬件范围和关键引脚。
- [x] 读取 `docs/reference/easyeda-api-operations-guide.md`，确认 Bridge/API 可用能力与限制。
- [ ] 验证 EasyEDA Bridge Server `http://127.0.0.1:49620/health`。
- [ ] 打开 Jovi 提供的 EasyEDA Pro 工程 URL，并确认当前项目/页面列表。
- [ ] 创建或整理 6 页原理图：Power、MCU、CAN、Audio、Storage_LED、Test_Header。
- [ ] 使用 LCSC 标准器件优先放置核心器件；无法 API 创建的电源符号/端口记录为 UI 待补。
- [ ] 单个调用创建关键视觉连线，避免 `Promise.all` 批量走线。
- [ ] 验证 ESP32-S3 44 pad、`POT_IO1`、无 `IO34` 业务连接、CAN Pin 6/14、PCM5102A SCK/GND/VCP。
- [ ] 截图抽查 6 页，记录 Bridge/工程检查结果到本文件 Review。

## 2026-06-01 Chrome/Computer 复查与优化计划

- [x] 接收 Jovi 指令：用 Chrome/Computer 检查原理图并优化。
- [x] 复读 lessons：ESP32-S3 必须 44 pad，禁止占位符号/floating label 冒充原理图。
- [x] 验证 EasyEDA Bridge 在线且 `edaConnected=true`。
- [x] 用 Chrome/Computer 抽查当前 EasyEDA 页面可视状态。
- [x] 用 Bridge 审计 6 页对象数量、关键文字/网络、ESP32 pin count。
- [x] 定位不合格点并只做必要优化。
- [x] 重新验证 6 页和硬性规则。
- [x] 将最终 Review 写回本文件。

### Review - Chrome/Computer 复查与优化

- Chrome 插件连接到 `用户1` profile，但 `tabs.list()` 返回空；没有拿到当前 EasyEDA tab。
- Computer Use 可枚举窗口：Chrome 标题为 `tesla_lc_onlin | 2_MCU_Core.Schematic1 | 嘉立创EDA(专业版) - V3.2.135`；桌面版 `lceda-pro.exe` 截图显示非编辑器内容，因此最终以 Bridge 结构化审计为准。
- Bridge health 复验：`status=ok`，`edaConnected=true`。
- 优化 1：`2_MCU_Core` 清理旧对象，组件从 29 个降到 10 个，恢复单一真实 LCSC ESP32-S3 器件，并保留硬性阻塞标记。
- 优化 2：`6_Test_Header` 删除错误 64-pin header，替换为 3 个 `HDR-1X5` 器件；复验 pin count 为 `[5,5,5]`。
- 复验对象计数：
  - `1_Power`: components=10, texts=17, wires=4
  - `2_MCU_Core`: components=10, texts=21, wires=6
  - `3_CAN_Interface`: components=5, texts=15, wires=6
  - `4_Audio_Output`: components=10, texts=23, wires=10
  - `5_Storage_LED`: components=11, texts=22, wires=8
  - `6_Test_Header`: components=5, texts=21, wires=13
- 硬性规则复验：
  - `POT_IO1`: true
  - `IO34` 业务连接: false；页面含 IO34 NC 说明
  - CAN Vehicle Pin 6/14: true
  - PCM5102A SCK -> GND: true
  - Test Header: 3 个 5-pin header
  - ESP32-S3 pin count: **41**，未达到 44；EasyEDA LCSC 库器件 `70d0831675bf4b8c9d1e0e7a40906b15` 通过 API 返回 41 pins。必须后续创建/导入完整 44-pad 自定义库符号后才能进入 PCB/生产。
- DRC：`eda.sch_Drc.check()` 在本轮触发 500，因此未作为通过证据。

## 2026-06-01 继续复查与优化计划

- [x] 接收 Jovi 指令：再次用 Chrome/Computer 检查原理图并继续优化。
- [x] 尝试 Chrome/Computer 可视检查 EasyEDA 当前窗口。
- [x] 用 Bridge 复查 6 页当前状态。
- [x] 重点处理 ESP32-S3-WROOM-1 N16R8 44-pad 阻塞。
- [x] 清理明显的 UI/library follow-up 占位说明，保留真实未解决阻塞。
- [x] 保存并复验硬性规则。
- [x] 写入本轮 Review。

### Review - 继续复查与 44-pad 优化

- Chrome DevTools 本轮只枚举到 `about:blank`；结合前轮 Computer Use 已确认 Chrome EasyEDA 窗口存在，因此实际原理图检查继续以 EasyEDA Bridge 结构化对象为准。
- 创建个人库符号 `ESP32-S3-WROOM-1-N16R8-44PAD-JOVI-FINAL-121630`，符号 UUID `14e1ad084a444df7a5bc2a26603e40f0`。
- 44-pad 符号验证：`sch_PrimitivePin.getAll()` 返回 44，pin number 连续 `1..44`；左侧含 `GND, 3V3, EN, IO0..IO21`，右侧含 `IO26_NC_FLASH, IO33..IO37_NC_PSRAM, IO38..IO48, 3V3, GND`。
- 创建并放置个人库器件 `adae3e0c266d498c9fd2d752f2759d3c` 到 `2_MCU_Core`；复验 `getAllPinsByPrimitiveId()` 返回 ESP32 pin count = 44。
- 已删除旧 LCSC 41-pin ESP32 器件；MCU 页保留说明：LCSC stock symbol 报 41 pins，因此使用自定义 44-pad 符号。
- 带 LCSC footprint 的 `lib_Device.create()` 会导致 EasyEDA window disconnected；当前 44-pad 器件为 schematic-verified、`addIntoPcb=false`、footprint 为空。进入 PCB/export 前必须在 EasyEDA UI 或更稳定 API 中把 footprint/BOM 映射复核到 LCSC `C2913202` / footprint `bacdc9b3530d4b9ca5f35adac008b474`。
- 清理诊断残留：删除空白 device probe `05c94ab026474908bb695a31a0285e4a` 和临时 1-pin symbol probe `811a83a911d04b8db1e832b962db7357`；P1 复查仅 1 个图框组件，无临时 ESP32 器件。
- 6 页复查对象计数：
  - `1_Power`: components=10, texts=17, wires=4
  - `2_MCU_Core`: components=10, texts=19, wires=6, ESP32 pin count=44
  - `3_CAN_Interface`: components=5, texts=15, wires=6
  - `4_Audio_Output`: components=10, texts=23, wires=10
  - `5_Storage_LED`: components=11, texts=22, wires=8
  - `6_Test_Header`: components=5, texts=44, wires=13, header pin counts=`[5,5,5]`
- 硬性规则复验：`POT_IO1` 存在；IO34 标为 `NC/PSRAM`；CAN 页包含 `OBD2 Pin 6 = CAN-H` 与 `OBD2 Pin 14 = CAN-L`；Audio 页包含 `SCK -> GND`；Test Header 为 3 个 5-pin header。

## 2026-06-04 嘉立创下单 BOM 表计划

- [x] 确认当前原理图主目录和工程文件。
- [x] 参考本地 `hardware/BOM_and_Wiring.md` 与 EasyEDA 复查记录整理采购项。
- [x] 使用 Tavily 搜索核对关键嘉立创/LCSC 料号。
- [x] 生成带供应商名称、供应商编号、位号、数量、封装和备注的 Excel BOM。
- [x] 重新导入 `.xlsx` 检查关键范围，并扫描公式/错误值。

### Review - 嘉立创下单 BOM

---
# 2026-06-24 EasyEDA GUI pin-to-pin 布线执行

> 日期: 2026-06-24 | 状态: 执行中

## 计划清单

- [ ] 复核 `easyeda-api` / `hd-wire` 约束，确认本轮只做 GUI 布线，不新增/删除元器件与页面。
- [ ] 用 bridge 读取当前工程页列表、活动页和对象分布，确定先从已放置页面开始布线。
- [ ] 用 Computer Use 激活 EasyEDA Pro，在 GUI 中逐页进行 pin-to-pin 实际落线。
- [ ] 每完成一页，立刻用 bridge 回读 wires / net labels / components，确认不是孤立短线。
- [ ] 若页面内元件位置影响走线，可做小范围移动并记录，但不允许增删器件。
- [ ] 优先完成 `POWER`、`MCU`、`PERIPHERAL`、`INTERFACE` 中当前已具备布线条件的模块。
- [ ] 将本轮阻塞项和页面审核结果写回本文件 Review，并在需要时更新 `tasks/lessons.md`。

## 布线守则

- 本轮只做原理图 pin-to-pin 布线，不重跑 `/hd_put`。
- 单根导线必须从一个器件引脚或电气对象，连接到另一个器件引脚或电气对象；禁止画无意义孤立线段。
- 走线顺序固定：`GND -> 电源轨(+3.3V/+5V/+12V_PA/VBUS) -> 去耦/上下拉/反馈 -> 功能信号`。
- 跨模块优先使用清晰网络标签，模块内尽量短线、点对点、无长距离穿越。
- 每页布线后必须截图级自检，并做 bridge 读回验证，确认 wire 数量和关键网络都实际存在。

## 中间记录

- [x] 已复核 bridge：`edaConnected=true`，当前工程为 `codex_tesla / Board1 / Schematic1`，页面为 `PERIPHERAL / POWER / MCU / INTERFACE / POWER-DCDC`。
- [x] 已在 GUI 中成功激活嘉立创 EasyEDA Pro 窗口，并切换页面做布线前准备。
- [ ] Computer Use 在继续滚动画布前收到物理 `Esc` 中断，按工具约束本轮必须停止 GUI 自动操作，等待下一轮恢复。

## 2026-07-08 恢复执行

- [ ] 重新验证 EasyEDA bridge、当前工程、页面列表和对象快照。
- [ ] 重新激活 EasyEDA GUI 窗口，确认没有延续上次中断状态。
- [ ] 先选一个器件少、pin 坐标可确认的模块完成 GUI pin-to-pin 小样。
- [ ] 小样通过后，按页扩展到 `POWER-DCDC / POWER / MCU / PERIPHERAL / INTERFACE`。
- [ ] 每页完成后写入 wire 数、关键网络、截图/视觉检查和未解决阻塞项。

- 当前嘉立创原理图主目录：`E:\Tesla_speed\hardware_lc`。
- 当前主工程/导出包：`E:\Tesla_speed\hardware_lc\ProPrj_tesla_lc_onlin_2026-06-02.epro2`。
- `E:\Tesla_speed\hardware_lc\tesla_speed_lc.eprj2` 是早期工程壳；此前 SQLite 检查显示 schematics/components/devices 为空，不作为本轮 BOM 主源。
- 旧 AD/中间资料目录：`E:\Tesla_speed\hardware`，其中 `BOM_and_Wiring.md` 只作为初始参考，不能直接下单。
- Tavily 核实并修正的关键料号：
  - ESP32-S3-WROOM-1-N16R8：`C2913202`。
  - PCM5102APWR：`C107671`，替代旧资料 `C165924`。
  - MAX98357AETE+T：`C910544`，替代旧资料 `C97356`。
  - TPA3116D2DADR：`C50144`，封装按 32-pin HTSSOP EP。
  - WS2812B-B/W：`C114586`，替代旧资料 `C2941561`。
  - USB-C 16P：`C2906290`，替代旧资料 `C168688`。
- Tavily/网络错误记录：
  - ESP32 首次搜索 `socket hang up`，缩短查询后成功。
  - SN65HVD230 查询出现 `stream has been aborted`，保留本地 `C80547` 并标需复核。
  - LM2596 查询 TLS 连接中断，保留本地 `C15849` 并标需复核。
  - SY8088 查询返回不相关结果，保留本地 `C82257` 并标需复核。
- BOM 输出：`E:\Tesla_speed\outputs\bom_jlc_20260604\Tesla_Sound_Simulator_JLC_BOM_20260604.xlsx`。
- 验证结果：`.xlsx` 已重新导入检查 `BOM!A1:I6`，供应商名称/编号/封装列正常；错误值扫描 `#REF!/#DIV/0!/#VALUE!/#NAME?/#N/A` 为 0。
- 下单前注意：标 `待选型` 或 `需复核` 的无源件、电源保护件、连接器、电感、电容不能直接一键下单；需要在嘉立创商城按电流、耐压、封装和库存最后确认。

## 2026-06-04 MiniMax MCP 完善 BOM 计划

- [x] 发现并接入 MiniMax MCP 搜索工具：`mcp__MiniMax.web_search`。
- [x] 使用 MiniMax 复查上版 BOM 中的待选型/需复核项。
- [x] 将高可信搜索结果写入 BOM，低可信/跑偏结果只写入来源和风险说明。
- [x] 导出 MiniMax 完善版 Excel。
- [x] 重新导入 `.xlsx` 检查 MiniMax 更新项和错误值。

### Review - MiniMax MCP 完善 BOM

- MiniMax 有效更新：
  - `SY8088IAAC`：查到嘉立创EDA页面，LCSC `C479072`，封装 `SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL`。BOM 中 U2 已更新为该建议项，但备注要求 PCB 前确认其与旧 `SY8088AAAC/C82257` 的引脚和反馈参数兼容。
  - `SN65HVD230DR`：MiniMax 确认型号为 TI CAN 收发器、SOIC-8 封装；LCSC 编号仍沿用本地 `C80547`，并保留复核库存提示。
  - `LM2596`：MiniMax 补充 TI 官方参数和 TO-263/TO-220 系列信息；未查到可靠 `C15849` 对应页，因此保留复核提示。
- MiniMax 未写入为确定编号的搜索：
  - 0805 电阻/电容泛搜结果混入非 LCSC、非目标值或无供应商编号页面，未用于替换 BOM。
  - DC 5.5x2.1 电源座搜索跑偏，未用于替换 J2。
  - 1x5 2.54mm 排针未查到稳定目标页，只返回 2x5 IDC、1x3 母座等近似项，因此 J10/J11/J12 仍标待选型。
  - 2P 5.08mm 扬声器端子未查到稳定目标页，只返回 6P/8P 端子，因此 J6/J7 仍标待选型。
- BOM 输出：`E:\Tesla_speed\outputs\bom_jlc_20260604\Tesla_Sound_Simulator_JLC_BOM_MiniMax_20260604.xlsx`。
- 验证结果：重新导入 `.xlsx` 后可检索到 `C479072`、`SY8088IAAC`、`MiniMax` 更新记录；错误值扫描 `#REF!/#DIV/0!/#VALUE!/#NAME?/#N/A` 为 0。

## 2026-06-05 MiniMax MCP 二次完善 BOM 计划

- [x] 定位上一版 MiniMax BOM 和仍为 `待选型/需复核` 的物料。
- [x] 用 MiniMax 二次搜索连接器、TVS、肖特基、按键、排针、端子、阻容和 MicroSD。
- [x] 仅采纳清晰命中 EasyEDA/JLC/LCSC 编号和封装的项目。
- [x] 导出 MiniMax2 完善版 Excel。
- [x] 重新导入 `.xlsx` 检查关键料号和错误值。

### Review - MiniMax MCP 二次完善 BOM

- 有效更新：
  - D1 `SMBJ5.0A`：由旧 `C123793/需复核` 改为 `C169448`，封装 `SMB_L4.6-W3.6-LS5.3-RD`，厂家 `晶导微电子`。MiniMax/EasyEDA 结果显示库存高。
  - D4/D6 `SS34`：由旧 `C86717/需复核` 改为 `C8678`，封装 `SMA_L4.3-W2.6-LS5.2-RD`，厂家 `MDD/辰达半导体`。
  - J2 DC座：由 `待选型` 改为候选 `C16214`，名称 `DC-005 5.5-2.0MM`，封装 `DC-IN-TH_DC-005-5.5-2.0`，厂家 `BOOMELE/博穆精密`。注意它是 5.5x2.0，不是原备注 5.5x2.1，下单前必须确认电源插头兼容。
- 未采纳为确定编号：
  - `SMAJ24A`：只确认 SMA/DO-214AC 类型，未拿到可靠 LCSC 编号，继续待选型。
  - `1x5 2.54mm 排针`：MiniMax 返回 1x6、2x5 IDC、2x8 等近似件，未确认目标 1x5。
  - `2P 5.08mm 扬声器端子`：返回 5P/8P 等端子和一个非主结果近似 2P，未作为确定料号。
  - `6x6/4P 轻触按键`：搜索结果跑偏，未写入。
  - `0805 阻容`：搜索结果混入非 LCSC 和无明确 C 编号页面，未写入。
  - `MicroSD 卡座`：搜索跑到存储卡新闻，未写入。
- BOM 输出：`E:\Tesla_speed\outputs\bom_jlc_20260604\Tesla_Sound_Simulator_JLC_BOM_MiniMax2_20260605.xlsx`。
- 验证结果：重新导入 `.xlsx` 后可检索到 `C169448`、`C8678`、`C16214`；错误值扫描 `#REF!/#DIV/0!/#VALUE!/#NAME?/#N/A` 为 0。

## 2026-06-05 Tavily MCP 完善 BOM 与逐行审核计划

- [x] 梳理 MiniMax2 版 BOM 中仍为 `待选型/需复核` 的物料。
- [x] 使用 Tavily MCP 搜索 JLCPCB/LCSC/EasyEDA 页面，优先采纳可确认供应商编号和封装的结果。
- [x] 修正旧 BOM 中 `C28323` 被误作 100nF 的问题：`C28323` 实为 1uF 50V X7R 0805；100nF 改为 `C1711`。
- [x] 更新 Excel 生成器，新增 `Audit` 页逐行审核。
- [x] 导出 Tavily 完善版。
- [x] 重新导入 `.xlsx` 检查关键料号、Audit 全表和错误值。

### Review - Tavily MCP 完善 BOM 与逐行审核

- Tavily 新增/修正的高可信料号：
  - D3 `SMAJ24A`：`C113962`，MDD，`DO-214AC(SMA)`。
  - 100nF MLCC：`C1711`，Samsung `CL21B104KBCNNNC`，`C0805`。
  - 1uF MLCC：`C28323`，Samsung `CL21B105KBFNNNE`，`C0805`。
  - 10uF MLCC：`C15850`，Samsung `CL21A106KAYNNNE`，`C0805`。
  - 22uF MLCC：`C45783`，Samsung `CL21A226MAQNNNE`，`C0805`。
  - 5.1kΩ：`C27834`，UNI-ROYAL `0805W8F5101T5E`，`R0805`。
  - 1kΩ：`C17513`，UNI-ROYAL `0805W8F1001T5E`，`R0805`。
  - 10kΩ：`C17414`，UNI-ROYAL `0805W8F1002T5E`，`R0805`。
  - 120Ω DNI：`C17437`，UNI-ROYAL `0805W8F1200T5E`，`R0805`。
  - 4.7kΩ：`C17673`，多个 Tavily 返回 BOM 交叉引用指向 `0805W8F4701T5E`，但未拿到直接 LCSC 商品页，因此 Audit 标 `需复核`。
  - 轻触按键：`C115357`，ALPSALPINE `SKRKAEE020`。
  - 红色 0805 LED：`C84256`，NationStar `NCD0805R1`。
  - 绿色 0805 LED：`C84260`，NationStar `NCD0805G1`。
  - 旋转编码器：`C361165`，ALPSALPINE `EC11E1834403`，作为 KY-040 模块的裸件替代，机械和引脚需复核。
  - 1x5 2.54mm 排针：`C5156614`，ZHOURI `2.54-1*5`，需确认公母、直弯和高度。
- Tavily 错误/未采纳：
  - 27Ω、330Ω、680nF、电感、2P 5.08mm 扬声器端子、10k 电位器、6A PTC 未查到足够可靠的 JLC/LCSC 目标页，继续 `待选型`。
  - 2P 端子搜索出现 `socket hang up`，缩短查询后仍未得到可靠料号。
- 逐行审核结果：
  - BOM 总行数：44。
  - `Audit` 页覆盖：44 行全部覆盖。
  - 通过：14 行。
  - 需复核：17 行。
  - 待选型：12 行。
  - DNI/预留：1 行。
- BOM 输出：`E:\Tesla_speed\outputs\bom_jlc_20260604\Tesla_Sound_Simulator_JLC_BOM_Tavily_20260605.xlsx`。
- 验证结果：重新导入 `.xlsx` 后可检索到 Tavily 新增关键料号；`Audit!A1:G45` 完整；错误值扫描 `#REF!/#DIV/0!/#VALUE!/#NAME?/#N/A` 为 0。


---

# BOM 二次审计复核 Review

> 日期: 2026-06-05 | 状态: ✅ 完成

- [x] 读取 `docs\bom\audit_tavily_20260605.md`、`Tesla_BOM_20260604_agent_all.tsv` 和 Tavily BOM 生成脚本/输出。
- [x] 复核 U5/U6/U7/U8、D4/D5、J10/J11/J12、R6/R7/R8、R9/R10 争议点。
- [x] 联网核实关键 LCSC/JLC C 码、MPN、封装和值。
- [x] 新增复核报告：`E:\Tesla_speed\docs\bom\audit_tavily_20260605_codex_review.md`。
- [x] 更新 `tasks\lessons.md`，新增 baseline audit 规则。
- [x] 记录工具错误：Tavily MCP 查询 `C910544 MAX98357AETE+T JLCPCB` 返回 `socket hang up`，随后改用 web/LCSC/JLC 交叉验证。

## 结论摘要

- 认可对方 audit 的主结论：Tavily xlsx 高风险，不能直接下单；U5-U8、D4/D5、R6-R10 确有位号映射/重复位号风险。
- 反驳：不能以 `Tesla_BOM_20260604_agent_all.tsv` 作为可下单基础，因为它仍有重复 refdes、`C84258` 白 LED 写红 LED、ESP32 C 码错误等问题。
- 反驳：J10/J11/J12 不应绝对按 1x40 判断；当前 EasyEDA 记录为 3 个 5-pin header，`C5156614` 只是不适用于旧 1x40 截断策略。

---

# BOM 审核回应复核任务

> 日期: 2026-06-05 | 状态: 执行中

## 计划清单

- [ ] 读取 `docs\bom\audit_response_20260605.md` 和更新后的 `Tesla_BOM_20260604_agent_all.tsv`。
- [ ] 搜索核实回应中的关键断言：`C86367`、`C2934560`、`C2913202`、`C84256/C84258`、`C5884414`、`C81276`、`C13850/C134973`。
- [ ] 判断“重复位号是多页合并正常现象”是否可接受为下单 BOM 规则。
- [ ] 更新 Codex 复核文档，认可正确反驳，继续反驳危险结论。
- [ ] 更新 `tasks\lessons.md`，记录本轮 C86367 误判修正与多页位号规则。
- [ ] 做最终文件存在性和关键文本验证。

## BOM 审核回应复核 Review

> 日期: 2026-06-05 | 状态: ✅ 完成

- [x] 已读取 `audit_response_20260605.md` 和更新后的 `Tesla_BOM_20260604_agent_all.tsv`。
- [x] 已用 LCSC/JLC 页面核实 `C86367`、`C2934560`、`C2913202`、`C84258/C84256`、`C5884414`、`C81276`、`C134973`。
- [x] 新增报告：`E:\Tesla_speed\docs\bom\audit_response_20260605_codex_review.md`。
- [x] 修正旧报告中 `C86367` 未被证实的错误判断。
- [x] 更新 lessons：搜索失败不能作为 LCSC 料号不存在的负证据。
- [x] 继续反驳“重复位号是正常可接受状态”：它只能解释中间态来源，不能用于生产下单 BOM。

---

# BOM 最新 agent_all 审核任务

> 日期: 2026-06-06 | 状态: 执行中

## 计划清单

- [ ] 读取最新 `docs\bom\Tesla_BOM_20260604_agent_all.tsv`，确认对方声称的 4 处修正是否落地。
- [ ] 搜索核实 `C134973`、`C232761`、`C25900`、`C5116482`、`C5156614` 等新增/争议 C 码。
- [ ] 判断 J10/J11/J12 拆分为 1x3/1x5/1x40 是否符合当前 EasyEDA/Test Header 记录。
- [ ] 检查统计、TODO 列表、重复位号说明是否仍误导下单。
- [ ] 新增本轮审计报告并更新 lessons。
- [ ] 做最终文件与关键结论验证。

## BOM 最新 agent_all 审核 Review

> 日期: 2026-06-06 | 状态: ✅ 完成

- [x] 已读取最新 `Tesla_BOM_20260604_agent_all.tsv`，确认 4 处修正均已落地。
- [x] 已核实 `C134973`、`C232761`、`C17513`、`C101404`、`C25900`、`C5156614`、`C5116482`。
- [x] 新增报告：`E:\Tesla_speed\docs\bom\audit_agent_all_latest_20260606.md`。
- [x] 确认统计：当前 TSV 为 55 个数据行，`✅14 / ⚠️27 / ❌TODO4 / 📋10`。
- [x] 致命反驳：第 21 行 `C232761` 不是 1kΩ 0805，而是 onsemi `MB8S` 桥式整流器 SOIC-4；必须改回 `C17513` 或改正确 LIZ `C101404`。
- [x] 条件认可：`C5116482` 确认为 1x3P 排针，但 LCSC 显示 `Not available now`，不应视为已解决采购项。
- [x] 更新 lessons：库存数不能替代 C-code 的器件类型/封装验证。

---

# BOM 对 Codex 报告二次审核复核任务

> 日期: 2026-06-06 | 状态: ✅ 完成

## 计划清单

- [x] 读取 `docs\bom\audit_codex_response_20260605_codex_review.md` 和当前 `Tesla_BOM_20260604_agent_all.tsv`。
- [x] 复核对方核心断言：C84258/ESP32/C86367、C910544、C134973、C25900、C5116482/C5156614、C69851。
- [x] 判断哪些接受、哪些反驳，并形成新的复核回应文档。
- [x] 核对当前 TSV 状态统计和关键行是否已经变化。
- [x] 更新 lessons，记录库存判断不能依赖缓存/搜索摘要。

## Review

- 接受：旧 Codex 报告中 C84258/ESP32/C86367 相关判断已过时或已修正。
- 反驳：`C910544 stock=0` 与当前 LCSC 直达页不符；当前页面显示 MAX98357AETE+T 且有现货。
- 部分接受：`C5116482`/`C5156614` 型号匹配 1x3/1x5 排针，但当前分别为 `Not available now` / `Out of Stock`，不能算采购解决。
- 维持：仍缺 `1 refdes = 1 row` 干净下单 BOM，这是下单前阻塞项。
- 新增报告：`E:\Tesla_speed\docs\bom\audit_codex_response_second_review_20260606.md`。
# 2026-06-07 终版 JLCPCB 下单 BOM 修复

- [x] 将 `Tesla_BOM_20260604_agent_all.tsv` 降级为候选池，不再作为直接下单 BOM。
- [x] 复核合并报告的关键 C 码结论，尤其处理 `C32346` 与 `C72043` 新发现错料。
- [x] 生成严格 `1 refdes = 1 row` 的 `Tesla_BOM_final_order_20260607.xlsx`。
- [x] 生成 `Tesla_BOM_final_audit_20260607.md`，记录每个剔除/修正/保留项证据。
- [x] 更新 `tasks/lessons.md`，记录“待验证项可能是致命错料”的防错规则。
- [x] 运行文件级校验：供应商编号格式、无状态前缀、RefDes 唯一、手工件分离。

## Review

- 输出文件: `docs/bom/Tesla_BOM_final_order_20260607.xlsx` 和 `docs/bom/Tesla_BOM_final_audit_20260607.md`。
- 严格下单页: 69 行，供应商编号无 `✅/⚠️/📋/❌` 状态前缀，位号无重复。
- 手工/DNI 页: 21 行，包含 OBD-II、通孔件、排针裁切件、未验证经验值、封装变更风险项和 X1 模块晶振设计待确认项。
- 关键反驳: `C32346` 是 32.768kHz 晶振，不是 1mH CMC；`C72043` 是 0603 且不可用，D2 改 `C84260`。
- 二次审核: 认可 `C2054018` 是 F1 PTC 的 CRITICAL 错料，已明确写入手工/DNI；反驳 `C910544` 当前库存 CRITICAL，LCSC 直达页显示 `In-Stock: 14,897`；`C5380316/X1` 因 WROOM 模块内置 40MHz crystal 移出 SMT 页。
- 4-Agent 审核回应: 基本认可四项最终状态；`C968441` 只作为 500mA 0805 PTC 候选，不解决 2A F1；`C95572` 是 51uH/200mA CAN/FlexRay 信号线 CMC，不能直接替代 L1 的 1mH/12V 电源路径需求。
- 注意: 位号修正清单里的建议位号必须同步到 EasyEDA 原理图、PCB、CPL 后，才能真正上传 JLCPCB 贴装。
# 2026-06-07 EasyEDA PCB 元件放置

- [x] 确认 EasyEDA bridge/API 与当前工程 `tesla_lc_onlin` 可用。
- [x] 打开 PCB 文档 `PCB1` 并枚举当前 PCB 元件、封装、位号和坐标。
- [x] 对照 `Tesla_BOM_final_order_20260607.xlsx` 和原理图，判断哪些器件可自动放置、哪些需先同步原理图/PCB/CPL。
- [x] 先执行保守分区放置：电源、MCU、CAN、音频、存储/LED、测试接口分区，不做布线。
- [x] 验证 PCB 元件数量、坐标、重复位号和未放置件，输出记录。

## Review

- EasyEDA bridge: `49620`, `edaConnected=true`, active window `6d2f6595-62d8-44a3-841f-eccf1a1f4971`。
- `pcb_Document.importChanges()` 返回 `false`，改用 `lib_Device.search(C码)` + `pcb_PrimitiveComponent.create()`。
- 已按 `Tesla_BOM_final_order_20260607.xlsx` 的 `下单BOM` 创建 70 个 PCB footprint。
- 最终验证: `count=70`, `expected=70`, `missing=[]`, `duplicates=[]`, `extra=[]`, `saved=true`。
- 过程报告: `docs/bom/easyeda_pcb_placement_report_20260607.md`。
- 最新 BOM 二次审核已把 X1 移出 SMT 下单页；PCB 上已放置的 X1 footprint 需要后续在 EasyEDA 删除或标记 DNI 后重新验证。

# 2026-06-12 文档与工程版本归类整理

- [x] 盘点 `docs`、`tasks`、`hardware*`、`skills`、`outputs`、`Tesla_speedeasyeda-api-skill-temp` 的自有文档与工程状态。
- [x] 识别同类文档：PRD、方案/计划、硬件原理图规格、BOM/审核、EasyEDA/AD 经验记录、工程目录说明。
- [x] 对项目自有文档追加分类后缀和版本号，避免计划书、审核稿、终版文件混在一起。
- [x] 生成迁移映射表，记录旧文件名、新文件名、分类、版本、状态。
- [x] 新增或更新文档索引，说明当前推荐入口、历史稿、失败稿和工程目录用途。
- [x] 更新 lessons，记录“不要批量重命名第三方 reference/node_modules 或活动工程内部文件”的规则。
- [x] 验证重命名后文件存在、无重名冲突，关键终版 BOM/规格/工程索引可读。

## Review

- 重命名: 46 个项目自有文档/交付物追加 `__类别-v日期-来源-状态` 后缀。
- 映射表: `docs\DOCUMENT_RENAME_MAP_v20260612.tsv`。
- 总索引: `docs\DOCUMENT_INDEX_v20260612.md`。
- 工程说明: `hardware\README_hardware_v20260612.md`、`hardware_lc\README_hardware_lc_v20260612.md`、`hardware_lc2\README_hardware_lc2_v20260612.md`。
- 未改名: `docs\reference`、`node_modules`、EasyEDA API skill 内部文档、活动 EDA 工程文件。
- 当前入口: PRD、原理图规格、终版 BOM 均在 `DOCUMENT_INDEX_v20260612.md` 标出。
- 验证: `DOCUMENT_RENAME_MAP_v20260612.tsv` 共 46 行，缺失新路径 0，旧路径残留 0；终版 BOM xlsx 可打开，sheet 行数为 `下单BOM=69 / 手工采购_DNI=21 / 审核证据=54 / 位号修正清单=14`。

# 2026-06-13 EasyEDA 原理图优先重绘剩余页面

- [x] 读取 EasyEDA API skill、项目 lessons 和既有任务状态。
- [ ] 确认 EasyEDA bridge 连接、当前工程、当前 6 页 schematic UUID。
- [ ] 按原理图优先方式重画 `2_MCU_Core`，重点验证 ESP32-S3 44 pin、`POT_IO1`、无业务 `IO34`。
- [ ] 重画 `3_CAN_Interface`，重点验证 `CANH/CANL/CAN_RX/CAN_TX`、120R DNI、RS 接 GND。
- [ ] 重画 `4_Audio_Output`，重点验证 `PCM5102A`、`MAX98357A`、`TPA3116D2`、`I2S_*`、`MUTE`。
- [ ] 重画 `5_Storage_LED`，重点验证 `SD_*`、`LED_DATA`、`ENC_*`、`POT_IO1`。
- [ ] 重画 `6_Test_Header`，重点验证 UART/JTAG/CAN/I2S/电源测试网络。
- [ ] 全局对象审计：关键网络、错料 C 码、重复位号、视觉框残留、页面对象数。

## 当前执行规则

- 不再按 C 码硬搜第一项；必须按 MPN/名称/封装二次筛选。
- 不用大矩形/视觉 BOM 框冒充原理图；失败器件必须优先用真实符号或标阻塞。
- 每页独立执行、独立验证，避免 bridge 超时和错误页污染。

## EasyEDA 原理图优先重绘剩余页面 Review

> 日期: 2026-06-13 | 状态: 部分完成，44-pin MCU 阻塞

- [x] Bridge 验证: `http://127.0.0.1:49620/health` 返回 `edaConnected=true`，窗口数 1。
- [x] `1_Power` 已按真实库件/真实 wire 方式保留此前重画结果。
- [x] `2_MCU_Core` 已重画为真实库件网络：SY8088、USB-C、USB ESD、27R、BOOT/RST、ESP32 stock body；`POT_IO1` 存在，业务网未使用 `IO34`。
- [x] `3_CAN_Interface` 已重画：OBD2、PESD2CAN、SN65HVD230、120R DNI、CAN_RS pulldown；`CANH/CANL/CAN_RX/CAN_TX` 存在。
- [x] `4_Audio_Output` 已重画：PCM5102APWR、VCP/VNEG 1uF、MAX98357A、TPA3116D2、speaker/AUX headers；`I2S_*`、`MUTE`、speaker nets 存在。
- [x] `5_Storage_LED` 已重画并二次清理跨页残留：MicroSD、WS2812B、EC11/KY-040、POT、POT filter；无 `J10_JTAG` 残留。
- [x] `6_Test_Header` 已单页补画：JTAG/UART/CAN-I2S/Power/Signal headers；全部 `addIntoBom=false`。
- [x] 全局验证报告: `tasks\easyeda_schematic_final_verify_20260613_093726.json`。
- [x] 验证通过项: 必备网络无缺失；`badSupplierComponents=[]`；`io34WireNets=[]`；`potIo1Found=true`。
- [ ] 阻塞项: 当前 EasyEDA API 会话无个人库，工程库 `LIB_Symbol.create` 返回空，`U3_MCU` stock 器件仍为 41 pins；必须恢复库写权限或导入已验证 44-pin symbol 后再 release。

## EasyEDA 模块框与短排针视觉修复 Review

> 日期: 2026-06-13 | 状态: 完成，除 ESP32 44-pin 阻塞

- [x] 使用 EasyEDA bridge 重新为 6 页补模块框，每页框数量：Power=2、MCU=4、CAN=3、Audio=5、Storage/LED=4、Test=5。
- [x] 发现 `4_Audio_Output` / `6_Test_Header` 使用 1x40P 裁切件导致符号过长、页面不可读。
- [x] 已重画 `4_Audio_Output` 的 J5/J6/J7 为 1x4 短排针符号。
- [x] 已重画 `6_Test_Header` 为 2x5 JTAG、1x4 UART、1x6 signal、1x4 power、1x6 signal test 短符号。
- [x] 每页审核报告：`tasks\easyeda_page_audit_with_frames_20260613_100724.json`。
- [x] Computer Use 截图确认 `6_Test_Header` 不再由 1x40P 长符号撑满页面。
- [x] 关键网络审核：所有页面 `missingNets=[]`，无 `IO34` 业务 wire，无 `C2054018/C32346/C5380316` 错料组件。
- [ ] 仍阻塞：`2_MCU_Core` 的 `U3_MCU` stock 符号未按当前 ESP32-S3-WROOM-1-N16R8 官方 WROOM-1 No./Pad release truth 复核；后续不得再用旧 44-pad 口径验收，必须验证 `3V3=No.2/Pad2`、`POT_IO1=IO1/No.39` 及库符号一致性。

# 2026-06-13 EasyEDA 工业控制器风格原理图整理

> 状态: 中止并重新审计；当前自动长 rail 方案不合格

- [x] 备份当前 EasyEDA 6 页 schematic 对象快照：`tasks\easyeda_industrial_backup_20260613_164734.json`。
- [~] 按工业控制器风格重排为 POWER / MCU / PERIPHERAL / INTERFACE 发布页；当前仍为 6 个物理页，未安全合并为 4 发布页。
- [~] 修正模块框：部分页面已补黑框和标题，但未完成截图验收。
- [~] 删除重复自由文本标签，保留真实 pin 名和线上 net label；部分页面 text 对象落下异常，需恢复后重做。
- [~] 补真实蓝色导线，模块内部不再只放孤立短线；长 rail 方案触发 EasyEDA wire 自动合并/拒绝，不能验收。
- [x] 每页完成后 API 审核：已输出 `easyeda_industrial_rewire_20260613_165106.json` 和 `easyeda_industrial_repair_rails_text_20260613_165324.json`。
- [x] 记录 ESP32 44-pin 符号阻塞：`U3_MCU` 仍为 41 pin。
- [x] 更新 lessons 和执行报告：`tasks\easyeda_industrial_rewire_review_20260613.md`。

## Review

- 本轮不能声明完成。EasyEDA 会把相交/贴近 pin 的 wire 自动合并，跨全页 rail 会污染网络。
- 已停止继续批量写入，避免进一步破坏工程。
- 下一步应从对象快照或 EasyEDA 历史恢复，再先以 `3_CAN_Interface` 做点对点短线小样，通过截图和 net 集合审计后再扩展。

## 继续执行记录 - 2026-06-13 17:30

- [x] 按 Jovi 纠正继续执行，并通过 Computer Use 真实截图检查 EasyEDA 窗口。
- [x] `3_CAN_Interface` 已重做为点对点短线小样，新增 netport/netflag；截图确认框已包住器件且不再压标题栏。
- [x] `1_Power` 已改为短线连接，补齐 `VBUS_USB/+5V/GND/VBAT_12V/VIN_PROT/+12V_PA` 等关键网络，补掉 VIN_PROT 到 F3 的失败支路。
- [~] `2_MCU_Core` 已缩小模块框，但框位置仍需继续细调；`U3_MCU` 仍为 41 pin，44 pin 阻塞未解决。
- [ ] `4_Audio_Output`、`5_Storage_LED`、`6_Test_Header` 尚未按点对点短线策略重新复核。

## 页面 1/2/3 工业控制器风格复核 - 2026-06-13

- [x] 复查 `1_Power`：作为当前样张，仅做视觉/网络审核，不做大改。
- [x] 优化 `2_MCU_Core`：按参考 MCU 页重建模块框、右侧外设映射、44 pin 阻塞注记，避免框压标题栏。
- [x] 优化 `3_CAN_Interface`：保持点对点短线，调整中文模块标题、框和 net label，避免重复文本。
- [x] 用 Computer Use 截图逐页检查页面 1/2/3。
- [x] 用 EasyEDA API 输出对象数量、wire/net label/netflag/netport 集合和 ESP32 pin count。

## Review

- EasyEDA 保存成功，GUI 显示 `保存成功!`。
- 页面 1 `1_Power` 保持为当前样张：横版图纸、右下角标题栏、两个黑色模块框、电源链路左到右。
- 页面 2 `2_MCU_Core` 删除越界外设映射对象：`deletedOverflowComponents=16`、`deletedOverflowWires=20`、`overflowRemaining=[]`；中文文本反查无问号。
- 页面 3 `3_CAN_Interface` 已补齐 `CANH/CANL/CAN_RX/CAN_TX/CAN_RS/GND/+3.3V` 网络和 3 个模块框。
- 审核报告：`tasks\easyeda_page123_industrial_final_audit_20260613.md` 和 `tasks\easyeda_page123_industrial_final_audit_20260613.json`。
- 仍未 release：`U3_MCU` 仍为 41 pin stock 符号，必须替换 EasyEDA 工程内 44 pin ESP32-S3-WROOM-1-N16R8 符号后再验收。

## Jovi 二次纠正后重做 `2_MCU_Core` - 2026-06-13

- [x] 记录“不合格原因”：上一版仍是贴边映射/框图效果，不符合参考图二 MCU 页。
- [x] 备份重做前页面：`tasks\easyeda_page2_before_reference_redo_backup_20260613.json`。
- [x] 验证 `sch_PrimitiveComponent.modify` 可移动真实 U3_MCU，并将 U3_MCU 从页边移到主控区。
- [x] 清理旧 wire/netport/框/文本，按参考图二重排：左上 3V3 buck、左中复位/BOOT、左下 USB 调试、中部 MCU、右侧外设管脚映射。
- [x] 使用 Computer Use 截图复核，GUI 保存成功。
- [x] 输出最终审计：`tasks\easyeda_page2_reference_style_final_audit_20260613.md` 和 `.json`。

## Review

- 2026-06-16 Codex v1.9 计划复审任务：只读审核 DeepSeek v1.9、MIMO v4.1/v4.2、Codex v1.8 与三份错误根因记录；必要时联网核实 datasheet；正确项吸收进 Codex 计划，错误项直接反驳；不修改 `hardware` 或 Altium 库。

## 2026-06-16 Codex v1.9 复审清单

- [x] 读取本轮 DeepSeek/MIMO/Codex 计划与错误原因记录，只做文档复审，不执行 Altium/库修复。
- [x] 联网核实 TPA3116D2、MAX98357A、LM2596、SY8088 的官方 datasheet 争议点。
- [x] 更新 Codex 执行计划：吸收正确项、反驳错误项、补充 Phase 0 库符号阻塞门。
- [x] 更新 `tasks/lessons.md`：记录本轮错误根因和防复发规则。
- [x] 反向扫描 Codex 计划，确认旧错只出现在反驳/历史覆盖/阻塞语境。
- [x] 记录本轮 Review 结果和仍需执行前现场验证的项。

### 2026-06-16 Review

- 已更新 `docs/plan/codex_AD原理图整理_执行计划__plan-v20260614-codex-v1.0.md` 至 Codex v1.9 语境：新增 §25，吸收 PCM5102APW 需证据快照、ESP32 Pad->库 Pin 映射、LM2596 SS54/>=5A 二极管方向、470uF low-ESR 候选、Phase 0 库阻塞门。
- 已直接反驳：TPA3116D2 `GAIN/SLV 悬空=20dB`、MAX98357A `SD_MODE 370k`、SY8088 `Pin1=VIN/Pin4=EN`、LM2596 `470uF` 无条件化、以及任何“已修正”摘要替代现场库审计。
- 已更新 `tasks/lessons.md` 和 Codex 错误复盘，新增“Agent 摘要不能替代 datasheet 和当前库审计”规则。
- 验证：反向扫描确认危险词只出现在反驳、历史、错误原因、阻塞语境；本轮没有修改 `hardware`、`.SchLib`、`.SchDoc`，没有启动 Altium/MCP。
- `2_MCU_Core` 当前对象：components=36、wires=30、rectangles=5、中文文本 `questionTextCount=0`。
- `U3_MCU` 位置已重排到 `x=720,y=430`，右侧映射 netport 位于 `x=980`，`overflowNetports=[]`。
- 关键网络存在：`POT_IO1`、`CAN_RX/TX`、`I2S_*`、`SD_*`、`LED_DATA`、`ENC_*`、`MUTE`、`USB_DP/DN`（历史 EasyEDA 命名；当前 AD 计划统一写 `USB_D+` / `USB_D-`）。
- 仍未 release：`U3_MCU pins=41`，必须替换为 EasyEDA 工程内 44 pin 符号。

## 第 4/5 页参考风格重排 - 2026-06-13

- [x] 备份第 4/5 页重排前对象：`tasks\easyeda_page45_before_reference_redo_backup_20260613.json`。
- [x] 第 4 页 `4_Audio_Output` 按音频链路重排：I2S/DAC、MAX98357A、TPA3116D2、喇叭接口分区。
- [x] 第 4 页补齐网络：`I2S_*`、`PCM_VCP/VNEG`、`MUTE`、`AUDIO_L/R`、`SPK_*`、`PA_OUT*`、`+12V_PA/+5V/+3.3V/GND`。
- [x] 第 5 页 `5_Storage_LED` 按外设块重排：MicroSD、WS2812B、编码器、电位器。
- [x] 第 5 页补齐网络：`SD_*`、`LED_DATA/LED_DOUT2`、`ENC_*`、`POT_IO1`、`+3.3V/GND`。
- [x] 用 Computer Use 截图复核并保存，GUI 显示 `保存成功!`。
- [x] 输出审核：`tasks\easyeda_page45_reference_style_final_audit_20260613.md` 和 `.json`。

## Review

- `4_Audio_Output`: components=42、wires=33、rectangles=3、`questionTextCount=0`、`overflowNetports=[]`。
- `5_Storage_LED`: components=31、wires=23、rectangles=3、`questionTextCount=0`、`overflowNetports=[]`。
- 视觉注意：第 5 页右下 LED 区外框因 EasyEDA rectangle 坐标映射会压标题栏，已删除该框，保留模块标题、器件和短线；后续可用 GUI 手工微调外框。

# 2026-06-13 Altium Designer 工业控制器风格原理图整理

> 状态: Codex 计划书已成文，未执行 Altium；目标为 `hardware\Tesla_Sound_Simulator.PrjPcb` 下最新 6 个 Altium `.SchDoc`

## 计划清单

- [x] 读取 `tasks\lessons.md`，确认禁止占位符号、浮空标签、长线乱连、41-pin ESP32 冒充 44-pin 等历史问题。
- [x] 只读确认最新 Altium 目标文件：`hardware\1_Power.SchDoc` 到 `hardware\6_Test_Header.SchDoc`，时间戳为 2026-06-13 22:08:33。
- [x] 只读确认 Altium Designer 正在运行：`D:\Program Files\Altium\AD25\X2.EXE`。
- [x] 只读确认当前 Altium MCP 尚未连接：需要在 Altium 中运行 `Altium_API.PrjScr` 的 `StartMCPServer` 后再执行任何自动化。
- [x] 审核外部计划 `docs\plan\mimo_AD原理图整理_执行计划__plan-v20260613-mimo-v1.0.md` 和 `docs\plan\ad_use\deepseek_schematic_reorganization_plan.md`，吸收可用项并记录反驳项。
- [x] 二次审核 mimo v1.2 与“下一个 AI”汇总：确认 mimo 文件虽升级为 v1.2，但仍残留 `POT_ADC(GPIO34)`、`60-pin`、未确认功能真实落图、MCP 已运行等错误前提，不能作为执行基线。
- [x] 审核历史方案目录 `docs\plan\claude`、`docs\plan\codex`、`docs\plan\deepseek`：吸收系统级硬件目标、接口/音频/电源细节，反驳历史 GPIO、CH340、MCP2515、OBD pin、未验证 CAN ID 等不能直接落图的旧结论。
- [x] 按 Jovi 确认的方案 A 创建 Codex AD 执行计划书：`docs\plan\codex_AD原理图整理_执行计划__plan-v20260614-codex-v1.0.md`。
- [x] 本轮仅做计划书，不启动 Altium MCP、不操作 Computer Use、不修改 `hardware` 原理图。
- [x] 复审 deepseek v1.0、mimo v1.0、mimo v3.1 与 Codex v1.0 计划，同意项吸收到 Codex 执行计划，不同意项直接反驳。
- [x] 复审 AI2/AI3 更新后的 deepseek v1.0 与 mimo v3.2，同意项继续吸收到 Codex 执行计划，不同意项直接反驳。
- [x] 复审 deepseek v1.0、mimo v3.4、Codex v1.0 当前计划，同意项继续吸收到 Codex 执行计划，不同意项直接反驳。
- [x] 复审 deepseek v1.0、mimo v3.5、Codex v1.0 当前计划，同意项继续吸收到 Codex 执行计划，不同意项直接反驳。
- [x] 增加库符号引脚定义表，并复审 deepseek v1.0、mimo v3.7、Codex v1.0 当前计划，同意项继续吸收到 Codex 执行计划，不同意项直接反驳。
- [x] 复审 mimo v3.9、deepseek 最新 v1.6 内容与 Codex v1.5 冲突，裁决 PERIPHERAL 2x2/2x3、MCP2515 DNI、SY8088 引脚表、Pad/Pin 标注方式，并更新 Codex 计划书为可共同实施版本。
- [x] 复审 6-Agent 三轮审议报告、deepseek 最新 v1.7、mimo v3.9 与 Codex v1.6，吸收 ESP32 Pad2、LM2596 3.09K、占位器件 release 阻塞、MCP ping 强制门等一致结论，并把 Codex 计划升级为 v1.7。
- [x] 按 Jovi 纠正建立 `codex_` 前缀错误原因复盘文档，说明为何 Codex 反复出错，并同步修正 todo/lessons 中的旧口径残留。
- [x] 阅读 DeepSeek/MIMO/Codex 三份错误根因记录，吸收共性防错规则，修正 Codex 复盘、lessons 和 todo 中仍可能误导执行的残留口径。
- [ ] 等 Jovi 确认本计划后，使用 Computer Use 在 Altium 中启动/确认 `StartMCPServer`。
- [ ] MCP 连接成功后，立即备份 `hardware` 当前 `.PrjPcb/.SchDoc/.SchLib/.PcbLib/.BomDoc` 到 `tasks\backup_altium_industrial_YYYYMMDD_HHMMSS`。
- [ ] 对 6 页做只读对象审计：页面尺寸、元件数量、导线/网络标签、ESP32 pin count、重复位号、错料 C 码、标题栏/图框状态；不能直接相信“6 页为空白”。
- [ ] 先做 `3_CAN_Interface` 小样验证：OBD2/CAN 连接器 -> TVS/保护 -> SN65HVD230 -> 终端/DNI/RS 下拉 -> `CAN_RX/CAN_TX`；跨页业务信号必须用 `Port + 同名 NetLabel`，电源用 `Power Port`，使用短线点对点，不做全页长 rail。
- [ ] 根据小样结果整理发布页结构：`INTERFACE`、`MCU`、`PERIPHERAL`、`POWER`；复杂接口/电源 A3，MCU/外设 A4；旧 6 页仅在备份和审计后再决定移除、保留为历史页或替换为 4 发布页。
- [ ] 逐页整理布局与视觉规范：黑色模块框、中文加粗下划线标题、蓝色导线、红色网络/电源/GND/关键注释、IC/连接器浅黄色填充、右下角标题栏参数。
- [ ] 执行前确认库引用名、官方 datasheet 真值、Altium 库 pin list 与项目连接选项：尤其 ESP32-S3-WROOM-1-N16R8 必须以官方 WROOM-1 No./Pad 表为 release pin truth，`3V3=No.2/Pad2`、`POT_IO1=IO1/No.39`；TPA3116D2 `GAIN/SLV`/MUTE/SD、MAX98357A `SD_MODE/GAIN_SLOT`、SY8088/USBLC6/PESD/TVS/连接器先查 datasheet、库名和引脚表再放置。
- [ ] 按电路规则复核：去耦靠近电源脚，上拉/下拉靠近信号，DCDC 反馈靠近 FB，对外接口保护靠近连接器。
- [ ] 跑 Altium ERC/编译/设计差异检查，截图抽查每个发布页，并导出预览 PDF 作为阅读验收材料。
- [ ] 记录最终 Review：备份路径、修改页、验证报告、截图证据、仍阻塞项。

## 执行原则

- 不使用“全自动乱连”；先功能分区和元件摆放，再局部短线连接；跨页业务信号采用 `Port + 同名 NetLabel`，同页/模块内可用清晰 net label，电源用 `Power Port`。
- 不把矩形框或文字说明当作真实电路；框内必须保留真实符号、pin-level wire、net label/power port。
- 不在 MCP 未连接、未备份、未完成小样审计的情况下批量改 6 页。
- 如果 Altium MCP 或 UI 状态异常，停止并重新计划，不继续硬推。
- 电位器网络统一使用 `POT_IO1`，不得采用 `GPIO34` 或 `POT_ADC`；`IO34/IO33-37` 仍按 PSRAM/NC 风险区处理。
- CAN/OBD2、USB、AUX、调试排针等对外连接优先归入 `INTERFACE`，保护器件必须靠近连接器；不把 CAN 收发器作为普通 `PERIPHERAL` 块拆散。
- `PERIPHERAL` 当前遵循 Jovi 2026-06-15 后续裁决做 A4 2x2 网格；旧 `2x3` 只保留为未来真实外设超过 4 个功能群时的备选，不能作为当前执行原则。
- TPA3116D2 当前执行原则：增益由 `GAIN/SLV` 单脚分压决定，`AM0/AM1/AM2` 不作增益脚；`MUTE` High=mute/Hi-Z、Low=enabled；旧 `GPIO8=H 使能` 阻断。
- MAX98357A 当前执行原则：`SD_MODE` Low=shutdown，High=left，`RSMALL/RLARGE` 上拉选择 right/mix；旧 `SD_MODE->GND/100k->GND=左` 阻断。
- USB-C Standard VBUS 当前执行原则：默认 eFuse/限流开关或 1.5A PTC 候选；2A 只允许 adapter-only/DNI/重新计算 variant。WS2812B 默认每颗 100nF + 支路 10uF MLCC，不默认 22uF 钽。

## 外部计划审核

### 吸收项

- 吸收 mimo 的 P1-P10 版式原则：4 功能域、A3/A4 混用、模块黑框、左到右信号流、电源上/GND 下、颜色规范、短线+网络标签、去耦/保护器件就近、同类电路统一布局。
- 吸收 mimo/deepseek 的标题栏、坐标边框、库引用预检查、跨页网络一致性、ERC/视觉审查、预览 PDF 导出。
- 吸收 deepseek 的跨页信号表作为初始检查清单，但网络名必须按本项目最终规则改写。
- 吸收 deepseek 的“先核心 IC + 连接器，再补被动元件”节奏，避免一开始批量放全 BOM 后难以审查。
- 吸收两份计划中对 SY8088、USBLC6、PESD、TVS、USB-C、OBD2、MicroSD 等库名待确认的提醒。
- 二次吸收“下一个 AI”汇总中的具体电路细节：USB-C CC1/CC2 各 5.1k 下拉、PCM5102A VCP/VNEG 电荷泵电容、AUX L/R 耦合电容、EN RC 延迟、USB D+/D- 27R 串联、CAN 120R DNI、WS2812B DIN 330R；TPA3116D2 增益/静音网络已被 2026-06-15 v1.8 datasheet 裁决覆盖，执行时必须按 `GAIN/SLV` 与 MUTE/SD 极性复核。
- 二次吸收“先查统一项目库/本地库，再查外部 IntLib”的方向；但库名必须以 Altium 当前可查询结果为准，不能只按计划文件文字落图。
- 吸收 `claude/codex/deepseek` 三组历史方案共同确认的系统范围：ESP32-S3 N16R8、CAN 只读监听、BLE/微信小程序控制、microSD 声浪包、WS2812 状态灯、KY-040 调试输入、I2S 音频输出、MAX98357A 入门路径、PCM5102A+TPA3116D2 高功率路径、USB-C 5V 与 12V 点烟器两种供电路径。
- 吸收 Claude/DeepSeek 的“无屏幕替代”思路：WS2812 状态颜色、USB-CDC 串口 10Hz 数据流、开机自检/错误诊断文本；这些作为 MCU/INTERFACE 页注释或测试接口说明，不新增屏幕电路。
- 吸收 DeepSeek 的最终硬件引脚映射中已与当前规则一致的部分：`CAN_RX=GPIO13`、`CAN_TX=GPIO14`、`CAN_RS=GPIO38`、`I2S_BCK=GPIO6`、`I2S_LCK=GPIO7`、`I2S_DIN=GPIO12`、`SD_CLK=GPIO39`、`SD_MOSI=GPIO40`、`SD_MISO=GPIO41`、`SD_CS=GPIO45`、`WS2812B=GPIO48`、`KY040_CLK=GPIO4`、`KY040_DT=GPIO5`、`USB_D-/D+=GPIO19/20`。
- 吸收 DeepSeek 的 CAN 安全原则：原理图和注释按 listen-only / 禁止主动发送设计，`CAN_RS` 下拉/斜率控制要清楚，120R 终端默认 DNI。
- 吸收 Codex/Claude 关于 ESP32-S3 原生 USB-CDC 的结论：不放 CH340G，USB-C 数据口走 ESP32-S3 原生 USB D-/D+，并保留 CC 下拉、ESD 和 27R 串联电阻。

### 反驳项

- 反驳“StartMCPServer 已运行/已连接”的前提；当前只读探测显示 Altium 正在运行但 MCP 未响应，必须先启动并 ping 通过。
- 反驳“6 旧页已验证为空白，所以直接删除/移除”的做法；当前根目录页只是很轻，不等于可无备份删除。必须先备份和对象审计。
- 反驳 deepseek 用 `GPIO34`/`POT_ADC` 做电位器；本项目硬规则是电位器走 `POT_IO1`，`IO34` 不做业务网。
- 反驳 mimo 在 PERIPHERAL 中给 `GPIO34 PWM` 分配蜂鸣器；这同样违反 IO34/PSRAM/NC 风险区规则。
- 反驳 deepseek 把 CAN 收发器放入 PERIPHERAL 再由 INTERFACE 接 OBD2 的拆分；对外接口保护链应集中在 INTERFACE，避免保护与连接器分离。
- 反驳 deepseek 使用 `ESP-WROOM-32D.SchLib` 作为 ESP32-S3-WROOM-1 N16R8 核心符号；必须使用或创建 44-pad ESP32-S3-WROOM-1-N16R8 符号。
- 反驳 mimo 标注 MCU 为 “60-pin”；本项目 release 条件是 ESP32-S3-WROOM-1 N16R8 44 physical pads。
- 反驳 mimo/deepseek 默认新增 RS485、继电器、泵阀、Display、RTC/EEPROM、Buzzer、Flash 等未确认功能为真实电路；这些只能作为预留/DNI 或规划框，不能冒充已实现硬件。
- 二次反驳 mimo v1.2 的 `POT_ADC (GPIO34)` 跨页信号：必须改为 `POT_IO1`，且方向为外设电位器输出到 MCU `IO1`。
- 二次反驳 mimo v1.2 的 `ESP32-S3_2 (56-pin) / QFN-56` 库项作为核心 MCU：本项目是 ESP32-S3-WROOM-1-N16R8 模块，不是裸 QFN-56；必须在 Altium 中验证符号 pin count 和 pin 名。
- 二次反驳 “SY8088 一定放 POWER 页” 与 “SY8088 一定放 MCU 页” 两种绝对说法；最终按实际电源域和可读性决定：若作为全板 3.3V 源可归 POWER，若只给 MCU/近端数字域供电可归 MCU，但必须避免 3.3V 长距离噪声和重复电源定义。
- 二次反驳“页面无编号前缀/保留编号前缀”的绝对化；文件命名以 Altium 项目结构、现有引用和备份安全为准，不因外部计划偏好批量重命名 `.SchDoc`。
- 二次反驳 v1.2 仍保留的 RS485、继电器、泵阀、Display、RTC/EEPROM、Buzzer、Flash 真实落图倾向；除非 Jovi 单独确认并提供电路/BOM，否则不得进入生产原理图。
- 二次反驳任何“先更新记忆文件”的外部结论对本项目的约束力；本轮执行基线只认当前 `tasks/todo.md`、`tasks/lessons.md`、当前 Altium 工程和 Jovi 明确确认。
- 反驳 Claude/Codex 早期测试面板中电位器接 `GPIO7`、`GPIO34` 或 `POT_ADC` 的结论；当前唯一允许的电位器网络是 `POT_IO1`，落到 ESP32-S3 `IO1`。
- 反驳 Codex 早期 `KY-040 GPIO32/33` 和 Claude/DeepSeek 中任何与当前映射冲突的编码器引脚；当前只采用 `GPIO4/GPIO5`，按需另设按键/模式输入但不得占用 I2S/PSRAM 风险脚。
- 反驳 Claude/Codex 中 `CH340G USB-UART` 模块进入正式原理图；ESP32-S3 原生 USB-CDC 已覆盖调试/下载，CH340G 只能作为外部临时工具，不进 BOM/SchDoc。
- 反驳 Codex research 中“必须 MCP2515”的旧裁决作为当前原理图基线；当前设计采用 ESP32-S3 TWAI + SN65HVD230 的 CAN 接口，MCP2515 仅可作为独立备选 change，不得混入本轮 AD 整理。
- 反驳 Claude/Codex 早期 OBD2 Pin 3/11 与 DeepSeek/Codex CAN 文档之间的互相冲突被直接写死；本轮 AD 小样先按当前任务记录的 OBD2 Pin 6/14 样张和 `CANH/CANL` 标签执行，具体 CAN3/CAN6 选择只能作为可配置/待验证注释。
- 反驳将历史方案里的 CAN ID、DBC 字节位置、油门/RPM 算法当作原理图布线真值；这些属于固件/DBC 配置，不应改变 AD 原理图网络，最多作为 firmware note。
- 反驳 Claude 早期“ESP32-S3 DevKit/模块化模块”BOM直接落图；本轮 AD 需要工程内真实符号、引脚完整、连接真实，不使用开发板模块占位。

## Review

- 外部计划、后续 v1.2 汇总、以及 `claude/codex/deepseek` 历史方案已审核；本计划是当前执行基线。待 Altium 实施后继续填写执行证据。
- 2026-06-14 复审新增：`docs\plan\codex_AD原理图整理_执行计划__plan-v20260614-codex-v1.0.md` 已并入 deepseek-v1.0、mimo-v1.0、mimo-v3.1 中可用项，包括逐页 PDF/截图备份、量化验收、POWER 双行布局、pin-level connection 表、PCM5102A/TPA3116D2 关键细节、固定/ADJ 电源芯片版本检查。
- 2026-06-14 复审反驳：不接受 deepseek-v1.0 “旧页已空/已删”的当前事实前提；不接受 mimo-v1.0/v3.1 的 `POT_IO1(GPIO34)` 或 IO34 接电位器；不接受 44-pad/56-pin/Pin51 混合口径；不接受 DIODE_SMA/LED_0805 等假符号作为最终图；不接受默认放 MCP2515 DNI；不接受 2x2 作为 PERIPHERAL 默认网格。
- 2026-06-14 AI2/AI3 更新复审新增：Codex 计划升级为 v1.2，吸收 `POT_IO1 -> IO1` 固化、LED1 改离 GPIO1、C_EN 1uF、TPA MUTE 10k+33uF、AMS1117 R_LOAD 1k、OBD2 Pin16 PTC/TP/JP 默认 open、CAN6 主路径/CAN3 备选、SN65HVD230 R/RS/Vref 规则、跨页 Port 对象、MicroSD CS/MISO 优先上拉。
- 2026-06-14 AI2/AI3 更新复审反驳：不接受 AI3 把 POT_IO1 引脚重新列为待定；不接受 mimo-v3.2 残留 `POT_IO1(GPIO34)`、`R_POT -> GPIO34`、`LED1 -> GPIO1`、`StartMCPServer 已运行`、2x2 PERIPHERAL、默认 MCP2515 DNI、USB-C 物理连接器数量硬编码，以及 deepseek/AI2 “已删旧页不回头”的执行态度。
- 2026-06-14 v3.4 复审新增：Codex 计划升级为 v1.3，吸收 SN65HVD230 `TXD/D=Pin1`、`RXD/R=Pin4`、USB-C 单口供电+编程+log 目标、LED1 `GPIO21`、MicroSD MOSI/CLK 上拉 DNI、TPA3116D2 EP/PAD 接地散热注记、batch_modify 前验证属性名、逐页 PDF/截图备份。
- 2026-06-14 v3.4 复审反驳：不接受 deepseek 旧页已空/已删当前事实、DIODE_SMA 最终替代、多引脚器件 warning 可接受、44-pad/56-pin/Pin51 混用；不接受 mimo-v3.4 `StartMCPServer 已运行`、PERIPHERAL 2x2、默认 MCP2515 DNI、CAN RX/TX 默认 10k 上拉、MicroSD `R_MOSI/R_CLK` 真实上拉、固定坐标直接批量落图。
- 2026-06-14 v3.5 复审新增：Codex 计划升级为 v1.4，吸收反驳项集中前置、库符号 pin truth 作为候选核对表、SN65HVD230 `R/RXD` 推挽输出不需上拉、MicroSD MOSI/CLK 上拉 DNI、LED1 `GPIO21`、MCU 页 `+5V Port` 审计、TPA3116D2 EP/PAD 接地和输入滤波 DNI；当时的 USB-C VBUS PTC 2A 候选已被 2026-06-15 v1.8 覆盖为“非默认，仅 adapter-only/DNI/重算 variant”。
- 2026-06-14 v3.5 复审反驳：不接受 mimo-v3.5 声称 Jovi 已确认 PERIPHERAL 2x2；不接受 `StartMCPServer 已运行`、默认 MCP2515 DNI、库符号真值表直接照抄、SY8088 pin 表前后矛盾、LM2596 固定版/ADJ 分压混写、DIODE_SMA/LED_0805 release warning 可接受，以及 deepseek 的旧页已删、Pin51/56-pin、NetLabel 优于 Port 结论。
- 2026-06-14 v3.7 复审新增：Codex 计划升级为 v1.5，新增 `## 4.1 库符号引脚定义表`，吸收 mimo-v3.7 的 pin-level 表格形式、deepseek 的 `lib_get_pin_list` 查询原则，并纳入 ESP32-S3 使用脚/禁区、SN65HVD230、SY8088、LM2596、PCM5102A、TPA3116D2、MAX98357A、AMS1117、MicroSD 的候选引脚核对表。
- 2026-06-14 v3.7 复审反驳：不接受 `StartMCPServer 已运行` 当前事实、PERIPHERAL 2x2 已确认、默认 MCP2515 DNI、ESP32 `56-pin` release 口径、PCM5102A VCP Pin15/Pin16 冲突表直接照抄、DIODE_SMA/LED_0805 占位作为最终图，以及 deepseek “MIMO pin-level 表信息等价不吸收”的处理。
- 2026-06-15 v3.9/DeepSeek 最新复审新增：Codex 计划升级为 v1.6，撤回旧的 PERIPHERAL 2x3 坚持，当前默认采用 A4 2x2；允许 MCP2515 以 DNI 占位出现在 INTERFACE 页，但 TWAI+SN65HVD230 始终是默认 CAN 路径；ESP32 引脚表改为纯库 Pin# 主键，SY8088 改为 `lib_get_pin_list` 阻塞核对。
- 2026-06-15 v3.9/DeepSeek 最新复审反驳：仍不接受 `StartMCPServer` 已运行作为事实、ESP32 Pin51/56-pin 作为 release 连接、LM2596 3.3K 与 3.09K 分压执行值混写、以及 DIODE_SMA/LED_0805 仅靠 MPN 注释就作为最终 release 完成。
- 2026-06-15 6-Agent 三轮复审新增：Codex 计划升级为 v1.7，ESP32 release pin truth 改为 Espressif WROOM-1 官方模块 No./Pad 表；`3V3=No.2/Pad2`、`POT_IO1=IO1/No.39`、模块去耦 `1x10uF + 1x100nF` 紧贴 No.2；LM2596 ADJ 版锁定 `3.09K/1K 1%`；`StartMCPServer` ping 和占位器件 release 阻塞继续强化。
- 2026-06-15 6-Agent 三轮复审反驳：不接受 MIMO v3.9 残留 `Pad35/36=3V3` 与 `C13/C14` 去耦表；不接受把“44 physical pads”当成可执行编号；不接受 DeepSeek 步骤中 `DIODE_SMA/LED_0805` 占位对象作为 release 完成；不接受任何 `Pin51/56-pin` 容器字段进入发布连接。
- 2026-06-15 Jovi 纠错复盘：新增 `docs\plan\codex_AD原理图整理_错误原因复盘__review-v20260615-codex-v1.0.md`，记录 Codex 反复出错的根因：旧口径残留、库容器脚号与官方模块脚号混用、过信多 Agent 摘要、只验证新增内容不验证旧错误退出当前执行语境。同时修正本文件旧 `PERIPHERAL 2x3` 执行原则为当前 `2x2`。
- 2026-06-15 外部错误记录吸收：已阅读 `deepseek_错误根因记录_v1.0.md`、`mimo_错误原因记录.md`、Codex 复盘文档；新增防错规则到 Codex 复盘和 `tasks\lessons.md`。后续必须同步检查规则层和执行层、每个关键 IC 查 datasheet、LM2596/PCM5102A 等关键电路做计算/引脚验证、占位符号命令旁标 BLOCKING、Altium Net Identifier Scope 现场确认。
- 2026-06-15 六 Agent 两轮交叉审议吸收：Codex 计划升级为 v1.8；已把 `Port + 同名 NetLabel`、TPA3116D2 `GAIN/SLV` 与 MUTE/SD 极性、MAX98357A `SD_MODE/GAIN_SLOT`、USB-C eFuse/1.5A PTC 默认、WS2812B 每颗 100nF + 支路 10uF MLCC 写入当前执行原则。反驳 DeepSeek/MIMO 中 `SD_MODE->GND=左`、`AM0/AM1=增益`、`PTC 2A 默认`、`22uF 钽默认`、NetLabel-only 跨页。

## 2026-06-17 codex_hardware_eda / codex_hd_put Skill 创建

- [x] 创建父级 skill：`C:\Users\Admin\.codex\skills\codex_hardware_eda\SKILL.md`，作为 `/codex_hardware_eda` 入口。
- [x] 创建子级 skill：`C:\Users\Admin\.codex\skills\codex_hardware_eda\codex_hd_put\SKILL.md`，沉淀 EasyEDA/JLCEDA Pro 打开工程、设置页面、搜索器件、放置元器件、连线、模块框和逐页审核流程。
- [x] 创建经验参考：`C:\Users\Admin\.codex\skills\codex_hardware_eda\codex_hd_put\references\easyeda-jlc-pro-lessons.md`，记录 C 码错料、41/44 pin、孤立器件、框图错位、导线格式和截图审核等防错规则。
- [x] 文件级验证：父/子 `SKILL.md` 均有 frontmatter，路径可读。

### Review

- 由于系统脚手架会把 skill 名强制转换为 hyphen-case，本次按 Jovi 指定保留 `codex_hardware_eda/codex_hd_put` 下划线目录结构；未使用脚手架生成的 hyphen-case 目录替代。
- 后续执行嘉立创 Pro 原理图页面创建/元器件放置任务时，应先加载 `/codex_hardware_eda`，再进入 `codex_hd_put` 子流程。

## 2026-06-19 hardware_eda / hd_put / hd_wire Skill 优化

- [x] 读取 `skill-creator` 规范，确认标准 skill 要求：`SKILL.md` frontmatter 只放 `name/description`，正文精简，详细经验放 `references/`，推荐 `agents/openai.yaml` 而不是把 UI 元数据混入正文。
- [x] 搜索当前可读目录：`E:\Tesla_speed`、`C:\Users\Admin\.codex\skills`、`C:\Users\Admin\.agents\skills` 未找到用户描述的 `hardware_eda/hd_put`、`hardware_eda/hd_wire` 原目录。
- [x] 在 `E:\Tesla_speed\skills\hardware_eda` 生成优化版 `hd_put` / `hd_wire` 兼容目录，并额外生成标准可验证目录 `hd-put` / `hd-wire`。
- [x] 验证新 skill frontmatter、关键规则和引用文件；`hd-put`、`hd-wire` 均通过 `quick_validate.py`。
- [x] 对比 Jovi 版、Codex 旧版和本次优化版的优缺点。

### Review

- 生成文件：`E:\Tesla_speed\skills\hardware_eda\hd-put\SKILL.md`、`E:\Tesla_speed\skills\hardware_eda\hd-wire\SKILL.md` 及各自 `AGENTS.md`/`references`。
- 验证证据：`quick_validate.py E:\Tesla_speed\skills\hardware_eda\hd-put` 与 `quick_validate.py E:\Tesla_speed\skills\hardware_eda\hd-wire` 均返回 `Skill is valid!`。
- 注意：`hd_put` / `hd_wire` 下划线目录保留为兼容副本，但不符合 Codex skill 标准命名；真正建议同步到 skill 根目录的是 `hd-put` / `hd-wire`。

## 2026-06-19 Claude hardware_eda /hd_put /hd_wire 原地优化

- [x] 备份 `C:\Users\Admin\.claude\skills\hardware_eda\hd_put` 与 `hd_wire` 到 `backup_before_codex_opt_20260619_171945`。
- [x] 原地重写 `hd_put\SKILL.md`：加入计划书驱动、页面创建、A3/A4、四功能域、工业控制器放置原则、元件搜索核验、模块框和 placement audit gate。
- [x] 原地重写 `hd_wire\SKILL.md`：加入 placement gate、真实短线、net label 策略、四页面连线模板、必查 net、wiring audit gate 和 stop conditions。
- [x] 新增/更新 references：`industrial-controller-schematic-style.md`、`component-placement-audit.md`、`industrial-controller-wiring-style.md`、`wiring-audit.md`。
- [x] 编码验证：两个 `SKILL.md` 前三字节均为 `45,45,45`，即无 BOM `---` frontmatter。
- [x] 规则覆盖检查：`INTERFACE/MCU/PERIPHERAL/POWER`、`A3/A4`、黑色模块框、加粗下划线中文标题、左到右信号流、电源上/GND下、浅黄色 IC/连接器、接口保护靠近连接器、2x3 外设、真实短线、`POT_IO1`/禁止 `IO34` 均已写入。

### Review

- Codex `quick_validate.py` 对 Claude 目录的 `hd_put`、`hd_wire` 报 hyphen-case 命名错误，这是命名规范差异，不是 frontmatter/内容失败。若要迁移到 Codex 标准 skill，目录和 `name` 应改为 `hd-put`、`hd-wire`。

## 2026-06-19 hd_put / hd_wire 仅追加 EDA 原则

- [x] 按 Jovi 要求使用 `skill-creator` 标准审计，但不改动现有流程步骤。
- [x] 备份 Claude skill 到 `C:\Users\Admin\.claude\skills\hardware_eda\backup_before_principles_only_20260619_172953`。
- [x] 在 `/hd_put` 追加 `EDA Placement Principles From Industry Practice`，加入 2x3/2x2 弹性网格、ERC/BOM/netlist、栅格连接、NC 标记、电源入口保护、DCDC、混合信号、接口保护等原则。
- [x] 在 `/hd_wire` 追加 `EDA Wiring Principles From Industry Practice`，加入真实电气连接、标签作用域、漂浮 label 禁止、wire endpoint、junction/NC、net 查询、DCDC FB、接口保护链、ERC 记录等原则。
- [x] 验证新增后流程标题仍保留；仅多出两个原则段落。
- [x] 验证两个 `SKILL.md` 仍为无 BOM frontmatter，前三字节 `45,45,45`。

### Review

- 本轮没有重写 `/hd_put` 或 `/hd_wire` 的 Startup Gate、Procedure、Audit Gate、Stop Conditions 等流程步骤，只追加原则段落。

## 2026-06-19 修复 hd_wire 执行放置元件的边界错误

- [x] 事故记录：执行 `/hd_wire` 布线时错误执行了 `/hd_put` 的放置元件行为，这是 skill 边界失效。
- [x] 备份 Claude skill 到 `C:\Users\Admin\.claude\skills\hardware_eda\backup_before_wire_scope_fix_20260619_200623`。
- [x] 在 `hd_wire\SKILL.md` 增加 `Absolute Scope Boundary - Wiring Only`。
- [x] 明确禁止 `/hd_wire` 调用 `eda.lib_Device.search()`、`eda.sch_PrimitiveComponent.create()` 或任何创建/删除/移动/替换元件的操作。
- [x] 在 `/hd_wire` Startup Gate 和 Wiring Procedure 中加入 component snapshot 前后不变规则。
- [x] 在 Stop Conditions 中加入：缺 pin/符号/无源件/连接器/框/页面对象时必须退回 `/hd_put`，不得在 `/hd_wire` 里补放。
- [x] 在 `hd_put\SKILL.md` 增加 `Handoff Contract To /hd_wire`，规定 `/hd_put` 交出稳定元件快照，`/hd_wire` 不得改元件集合。
- [x] 验证关键禁令已写入，两个 `SKILL.md` 仍为无 BOM frontmatter。

### Review

- `/hd_wire` 现在是 wiring-only skill。它允许添加 wiring 相关对象：wire、net label、power/GND、junction、no-connect；不允许搜索、放置、删除、移动、替换元器件或页面结构。

## 2026-06-19 修正 hd_wire 允许移动已有元件

- [x] 按 Jovi 新裁决修正：`/hd_wire` 连线时可以移动已有同页元器件，以满足短线、可读性、模块边界、电源/GND 方向和接口保护顺序。
- [x] 备份 Claude skill 到 `C:\Users\Admin\.claude\skills\hardware_eda\backup_before_wire_allow_move_20260619_202007`。
- [x] 更新 `hd_wire\SKILL.md`：删除“移动/对齐/重排元件一律禁止”的旧句，改为禁止跨页移动、替换元件身份、改页面/模块结构；允许同页移动已有元件并记录。
- [x] 更新 `hd_wire` component snapshot 规则：component count、identity、page list、symbol pin count 必须不变；position 可变但必须记录 before/after 和原因。
- [x] 更新 `hd_put\SKILL.md` handoff：`/hd_wire` 可移动 existing same-page components，但不得 search/create/add/delete/replace/re-source 或跨页移动。
- [x] 反向搜索旧禁令，确认不再存在“同页移动既有元件即违规”的规则。

### Review

- 当前边界：`/hd_wire` 可移动已有同页元件；不可搜索、创建、添加、删除、替换、重新选型、跨页移动元件，也不可创建/删除/重命名/缩放页面或补放模块框/标题。

## 2026-06-21 hd_wire 引脚到引脚连线与 Codex skill 同步

- [x] 备份 Claude skill 到 `C:\Users\Admin\.claude\skills\hardware_eda\backup_before_pin_to_pin_and_api_20260621_004921`。
- [x] 更新 `hd_wire\SKILL.md`：明确单独一根不终止于合法电气端点的线不是连线，是 critical failure。
- [x] 更新 `hd_wire`：新增 `Wiring Order`，按 GND -> primary power rails -> power-control/support nets -> functional signals -> final net pass 的顺序连线。
- [x] 更新 `hd_wire`：要求每根线记录 source endpoint 和 destination endpoint，必须连接元器件引脚、合法 rail/node、junction、power/GND symbol 或已接触的 net label。
- [x] 更新 `hd_put\SKILL.md`：新增 A4/A3 usable bounds、标题栏排除区、黑色模块框、红色中文标题、网络标签、跨页标签/port 的 EasyEDA API 调用模板。
- [x] 同步 Claude `hd_plan/hd_put/hd_wire/hd_check` 到 Codex 顶层 hyphen-case skill：`hd-plan`、`hd-put`、`hd-wire`、`hd-check`。
- [x] 验证 Codex 四个 skill 均通过 `quick_validate.py`。
- [x] 验证 Claude/Codex `hd-put`/`hd-wire` 均为无 BOM frontmatter，前三字节 `45,45,45`。

### Review

- Jovi 反馈的核心问题已固化：`/hd_wire` 不能画“孤立单线”，必须做真实电气连接；`/hd_put` 必须负责页面内黑框/红标题/网络标签/跨页标签和 A4/A3 边界，避免框跑到纸外。

## 2026-06-20 hd_check 原理图布线审查 Skill 创建/优化

- [x] 读取 `skill-creator` 规范，确认本轮需要标准 `SKILL.md` frontmatter、可选 `agents/openai.yaml`、完成后用 `quick_validate.py` 验证。
- [x] 读取 `circuit-analyze`，提取可复用流程：视觉识别、连接表、确认、内部网表/数据模型、角色/工程加固、结构化报告。
- [x] 检查 `E:\project\EDA_agent\hd_check` 现状，确认已有初版 `SKILL.md`，本轮按原地升级处理。
- [x] 升级 `hd_check` 为原理图布线审查 skill：加入连接事实层、审查层、修复分流、EasyEDA 精确验证、报告裁决。
- [x] 根据 `hd_check` 反推优化 `/hd_put` 与 `/hd_wire`：增加交付契约和审查门，明确哪些问题回到放置、哪些问题回到连线。
- [x] 验证 `hd_check`、`hd_put`、`hd_wire` 的 frontmatter、关键规则覆盖和 validation 结果。

### Review

- 生成/更新：`E:\project\EDA_agent\hd_check\SKILL.md`、`E:\project\EDA_agent\hd_check\agents\openai.yaml`。
- 反推优化：`C:\Users\Admin\.claude\skills\hardware_eda\hd_put\SKILL.md`、`hd_put\references\component-placement-audit.md`、`C:\Users\Admin\.claude\skills\hardware_eda\hd_wire\SKILL.md`、`hd_wire\references\wiring-audit.md`。
- 备份：`E:\project\EDA_agent\backups\hd_check\SKILL.before_20260620_020000.md`；`C:\Users\Admin\.claude\skills\hardware_eda\backup_before_hd_check_contract_20260620_020000`。
- 验证：`quick_validate.py E:\project\EDA_agent\hd_check`、`quick_validate.py C:\Users\Admin\.claude\skills\hardware_eda\hd_put`、`quick_validate.py C:\Users\Admin\.claude\skills\hardware_eda\hd_wire` 均因下划线命名报 hyphen-case 错误；这是按 Jovi 指定保留 `hd_check`/`hd_put`/`hd_wire` 名称导致的规范差异，不是 frontmatter 解析失败。
- 规则覆盖：已检出 `Connection Fact Table And Confirmation`、`Repair Routing`、`Back-Propagation To /hd_put And /hd_wire`、`Handoff Contract To /hd_check`、`before/after component snapshot`、`Required net trace map`。
- 子代理只读验证：未发现阻塞问题；提出保护链归属歧义后，已修正为“已有元件接线顺序错误归 `/hd_wire`，缺件/错件/摆放差归 `/hd_put`”。

## 2026-06-20 hd_check 外部反馈筛选与反推补强

- [x] 读取外部 AI 对 `circuit-analyze` 可复用模式的建议。
- [x] 逐项判断：有用则吸收，无用或越界则反驳并不加入。
- [x] 补强 `/hd_put`：元件角色分类、匹配置信度、放置证据分层、板级一致性。
- [x] 补强 `/hd_wire`：引脚/连接置信度、前后 checkpoint、分层 wiring evidence、跨页 net 追踪。
- [x] 验证关键规则覆盖，记录 Review。

### Review

- 接纳并加入：置信度标记、后果驱动检查、分层证据输出、跨页 net 追踪、元件角色分类、元件匹配置信度、板级一致性检查。
- 调整改写：外部建议的“每阶段用户确认”改为 execution checkpoint；只有 Low-confidence、错 pin count、缺件、无法本地确认的设计假设才暂停找 Jovi。
- 反驳不加入：`/hd_wire` 做终端电阻/去耦值/保护额定区间选型。理由：`/hd_wire` 是 wiring-only，值和额定不确定应回 `/hd_put` 或 design confirmation，不能在连线 skill 里越权选型。
- 更新文件：`C:\Users\Admin\.claude\skills\hardware_eda\hd_put\SKILL.md`、`hd_put\references\component-placement-audit.md`、`C:\Users\Admin\.claude\skills\hardware_eda\hd_wire\SKILL.md`、`hd_wire\references\wiring-audit.md`。
- 备份：`C:\Users\Admin\.claude\skills\hardware_eda\backup_before_feedback_triage_20260620_feedback`。
- 验证：关键规则搜索已检出 `Component Role Taxonomy`、`Classify component match confidence`、`Layer 1: placement list`、`board-level consistency`、`Connection Confidence And Checkpoints`、`Track cross-page nets`、`Layer 1: connection table`、`Do not choose new component values`。
- `quick_validate.py` 对 `hd_put` 和 `hd_wire` 仍因下划线命名报 hyphen-case 错误；frontmatter 前 5 行人工检查正常。这是既有命名规范差异，不是本轮内容破坏。

## 2026-06-20 hd_plan Skill 头脑风暴

- [x] 使用 `brainstorming` skill，先探索上下文，不直接进入实现。
- [x] 基于会话 `019e7c87-d352-72a2-b982-5d48d961fc64` 提取边界：`/hd_put` 放置、`/hd_wire` 连线、`/hd_check` 审查。
- [x] 核对当前 `hd_put` / `hd_wire` / `hd_check` 的输入和边界。
- [x] 输出 `hd_plan` 的候选流程、推荐方案和待确认问题。
- [x] 派出不少于 4 个子 agent 讨论 `hd_plan` 阶段总结方案。
- [x] 汇总子 agent 讨论结果，形成做 skill 前的最终阶段方案。
- [x] 做两轮交叉审核，连续两轮 PASS 后再提示 Jovi 可调用 skill-creator。

### Review

- 当前仅做设计步骤，不执行 skill-creator，不创建 `hd_plan` 文件。
- 设计基线：`hd_plan` 是 `/hd_put`、`/hd_wire`、`/hd_check` 的前置计划书 skill；负责冻结需求、器件、datasheet 证据、页面结构、net map、边界和验收口径。
- 4 子 agent 讨论角色：流程/合同、EDA 计划书字段、datasheet/agent-browser 证据、QA/交叉审核门。
- Round 1 审核结果：FAIL；修正项包括 datasheet evidence manifest、UNKNOWN/blocker、pin-level intent、comparison keys、`hd_check` placement/final 分模式、禁止 `hd_plan` 执行 `/hd_check` 或声称 ERC/check pass。
- Round A2 审核结果：4/4 PASS。
- Round B 审核结果：4/4 PASS。满足连续两轮 PASS，可进入后续 skill-creator 制作阶段。

## 2026-06-20 hd_plan Skill 制作

- [x] 使用 `skill-creator`，读取规范后开始制作。
- [x] 创建 `C:\Users\Admin\.claude\skills\hardware_eda\hd_plan` skill。
- [x] 写入 `SKILL.md`：planning-only 边界、brainstorming gate、agent-browser 联网证据、计划书结构、handoff contracts、两轮交叉审核。
- [x] 写入必要 references：计划书模板、证据/审核规则。
- [x] 验证 frontmatter、命名差异、BOM/newline、关键规则覆盖。
- [x] 派发子 agent 前向/交叉审核，修正后记录结果。

### Review

- 生成目录：`C:\Users\Admin\.claude\skills\hardware_eda\hd_plan`，并保留 Codex-valid 标准副本 `C:\Users\Admin\.claude\skills\hardware_eda\hd-plan`。
- 生成文件：`SKILL.md`、`references\plan-template.md`、`references\cross-audit.md`、`agents\openai.yaml`。
- 脚手架：已运行 `init_skill.py hd-plan --path C:\Users\Admin\.claude\skills\hardware_eda --resources references`；首次因 `short_description` 长度失败，但已生成基础 `hd-plan` 目录，后续手工补齐 metadata。
- 验证：`quick_validate.py C:\Users\Admin\.claude\skills\hardware_eda\hd-plan` 返回 `Skill is valid!`。
- 预期差异：`quick_validate.py C:\Users\Admin\.claude\skills\hardware_eda\hd_plan` 返回 `Name 'hd_plan' should be hyphen-case`；这是 Jovi 指定下划线命名与 Codex validator 的规范差异。
- BOM 验证：`hd-plan\SKILL.md` 与 `hd_plan\SKILL.md` 前三字节均为 `45,45,45`。
- 关键规则覆盖：已检出 `Do not execute /hd_put, /hd_wire, or /hd_check`、`E:\Claude_allow\Download`、`two consecutive all-PASS`、`Missing brainstorming asks Jovi`、`Pin-Level Net Map`、`Comparison Keys`。
- 子 agent Round 1：4/4 PASS；Round 2：4/4 PASS。审核角度为 skill 结构、EDA 合同、datasheet/agent-browser 证据、QA/cross-audit gate。

## 2026-06-20 EasyEDA API Gate 与 hd_wire 布线纠错

- [x] 记录 Jovi 指出的 `/hd_wire` 错误模式到 `tasks/lessons.md`。
- [x] 在 `/hd_plan`、`/hd_put`、`/hd_wire`、`/hd_check` 写入唯一顺序：`hd_plan -> hd_put -> hd_wire -> hd_check`。
- [x] 在 `/hd_put`、`/hd_wire`、`/hd_check` 写入强制加载 `easyeda-api`，缺失时从官方仓库请求安装/加载许可。
- [x] 强化 `/hd_wire`：元件连元件，power/GND symbol 只放在电路边界，不再每个 GND pin 放一个 GND 端口。
- [x] 强化 `/hd_wire`：导线端点必须使用 EasyEDA Pro pin 原始浮点坐标，禁止 `Math.round()`/`parseInt()`。
- [x] 强化 `/hd_check`：审查重复 GND、同 rail 电阻、单端电容、POWER 页散落、导线端点未落 pin 等错误。
- [x] 验证关键规则覆盖、frontmatter、BOM/newline 与已知下划线命名差异。

### Review

- 更新 skill：`C:\Users\Admin\.claude\skills\hardware_eda\hd_put\SKILL.md`、`C:\Users\Admin\.claude\skills\hardware_eda\hd_wire\SKILL.md`、`C:\Users\Admin\.claude\skills\hardware_eda\hd_plan\SKILL.md`、`C:\Users\Admin\.claude\skills\hardware_eda\hd-plan\SKILL.md`、`E:\project\EDA_agent\hd_check\SKILL.md`。
- 更新 references：`hd_wire\references\wiring-audit.md`、`hd_put\references\component-placement-audit.md`、`hd_plan\references\plan-template.md`、`hd_plan\references\cross-audit.md`，并同步到 `hd-plan` 标准副本。
- 核心改动：EasyEDA 操作必须加载 `$easyeda-api`；缺失时向 Jovi 请求从 `https://github.com/easyeda/easyeda-api-skill` 安装/加载；唯一顺序为 `hd_plan -> hd_put -> hd_wire -> hd_check`。
- `/hd_wire` 新增硬规则：元件连元件/局部 rail，power/GND symbol 只作边界；禁止每个 GND pin 一个 GND 端口；禁止同 net 电阻、单端电容、POWER 页散落无链路。
- `/hd_wire` 新增坐标规则：导线端点使用 EasyEDA Pro 原始 `pin.x`/`pin.y` 或 `toFixed(6)` 精度；禁止 `Math.round()`、`parseInt()`、整数近似坐标。
- 验证：`quick_validate.py C:\Users\Admin\.claude\skills\hardware_eda\hd-plan` 返回 `Skill is valid!`。
- 预期差异：`quick_validate.py` 对 `hd_put`、`hd_wire`、`hd_plan`、`hd_check` 仍因下划线命名报 hyphen-case；frontmatter 可解析，BOM 检查前 3 字节均为 `45,45,45`。
- 规则覆盖：`rg` 已检出 `easyeda-api`、`easyeda-api-skill`、`hd_plan -> hd_put -> hd_wire -> hd_check`、`Component-To-Component Wiring Rule`、`Exact Pin Coordinate Rule`、`toFixed(6)`、`Math.round()` 禁令、`one-per-pin` 审查项。
## 2026-06-21 EasyEDA hd-put 元器件放置执行

- [x] 读取 Codex `hd-put` skill、`easyeda-api` skill、指定计划书和放置审核参考。
- [x] 读取 `tasks/lessons.md`，确认当前规则：原理图优先、工业控制器风格、hd_put 只做放置和页面结构、不做布线/PCB/CPL。
- [x] 确认 EasyEDA bridge `/health`、`/eda-windows`、当前工程和当前原理图页面。
- [x] 反查当前页面清单和对象数量，避免在错误页面或 PCB 文档上放置。
- [x] 从计划书提取四页发布结构：INTERFACE、MCU、PERIPHERAL、POWER，以及每页元器件/模块角色清单。
- [x] 逐页小批量放置元器件、模块框、红色中文标题和必要网络标签；每批完成后查询对象数量。
- [x] 清理超时导致的误页放置：删除 MCU 页误放 `CN1`、归档页误放 18 个 PERIPHERAL 器件，并在 PERIPHERAL 页重放。
- [x] 输出 placement snapshot：页面、designator、元件名/MPN/C 码、角色、位置、匹配置信度、DNI/手工状态。
- [~] 验证 A4/A3 可用区域、标题栏排除区、模块框不越界，页面可交给 `/hd-wire` 做真实引脚到引脚连线。API 未能实际切换 A3，当前四个发布页均按 A4 安全边界完成放置。

### Review

- EasyEDA bridge 保存成功：`eda.sch_Document.save() == true`。
- 发布页对象统计：POWER 25 components / 4 rectangles / 10 texts / 0 wires；MCU 39 / 5 / 7 / 0；PERIPHERAL 52 / 4 / 4 / 0；INTERFACE 12 / 3 / 8 / 0。
- 归档页 `ARCHIVE_P1_20260621_hd_put`、`ARCHIVE_P1_1_20260621_hd_put` 均只剩 1 个空白图框/标题对象，无误放 designator。
- 错料安全检查通过：发布页无 `C2054018`、`C32346` supplier id。
- 阻塞项仍存在：`U3_MCU` 当前 EasyEDA stock symbol pin count = 41，不满足 ESP32-S3-WROOM-1-N16R8 44-pad release 条件。下一步必须先做/导入 44-pad 自定义 symbol/device，不能进入最终验收。
- 证据快照：`outputs/easyeda_hd_put_20260621_snapshot.md`。

## 2026-06-21 EasyEDA hd-put 修复方案交接

- [x] 根据 Jovi 截图反馈复核当前 `/hd-put` 放置结果。
- [x] 判定当前版本不能验收：模块框与器件不对应、存在空框/压标题栏、PERIPHERAL/INTERFACE 布局混乱、重复/空白归档页容易被误当 release 页。
- [x] 采纳 Jovi 最新 ESP32 裁决：当前 ESP32 符号按 41 引脚含 EPAD 验收，不再把 `pinCount == 41` 自动标为 44-pin blocker。
- [x] 生成给 GPT-5.4/下一执行者的修复计划：`docs/plan/easyeda_hd_put_repair_plan_for_gpt54__plan-v20260621-codex-v1.0.md`。

### Review

- 本轮只制定修复方案，没有继续改 EasyEDA 工程。
- 下一步必须先执行 `/hd-put` 修复方案，收敛为 `POWER/MCU/PERIPHERAL/INTERFACE` 四个 release 页，并把其他空白/重复页归档为 `ARCHIVE_DO_NOT_RELEASE_*`。
- `/hd-wire` 仍不能启动，直到 `/hd-put` 修复后的页面通过 placement audit。

## 2026-06-21 EasyEDA hd-put 修复执行

- [x] 重新读取 `hd-put`、`easyeda-api`、`tasks/lessons.md` 与修复计划，确认本轮只做 placement repair。
- [x] 重新确认 EasyEDA bridge、active window、当前 project/page list。
- [x] 生成修复前对象快照：四个 release 页与两个 archive 页的 components/rectangles/texts/wires/designators。
- [x] 清理并重排 `MCU` 页：移除旧框/旧标题/错误 blocker 文本，按 41-pin 口径重建结构。
- [x] 清理并重排 `INTERFACE` 页：把漂浮 DNI 文本、空框和压标题栏对象收敛到正确模块区。
- [x] 清理并重排 `PERIPHERAL` 页：修正 2x2 模块框与标题栏避让，按真实 bounding box 包围元件。
- [x] 清理并重排 `POWER` 页：重建 USB-C 5V、12V+DCDC、3.3V、DNI 四区布局。
- [x] 验证四个 release 页：wire 仍为 0、无越界、无压标题栏、`U3_MCU pinCount == 41`。
- [x] 保存工程并输出修复后快照到 `outputs/`。

### Review

- EasyEDA 保存成功：`eda.sch_Document.save() == true`。
- 发布页审计文件：`outputs/easyeda_hd_put_verify_release_pages_20260621.json`；修复脚本结果：`outputs/easyeda_hd_put_repair_mcu_interface_20260621_result.json`、`outputs/easyeda_hd_put_repair_peripheral_power_20260621_result.json`。
- 当前发布页对象统计：
  - `POWER`: 25 components / 4 rectangles / 10 texts / 0 wires / 6 ports
  - `MCU`: 37 components / 5 rectangles / 7 texts / 0 wires / 17 ports / `U3_MCU pinCount=41`
  - `PERIPHERAL`: 52 components / 4 rectangles / 4 texts / 0 wires / 18 ports
  - `INTERFACE`: 12 components / 3 rectangles / 8 texts / 0 wires / 7 ports
- 四个发布页均 `outOfBoundsCount=0`、`titleRiskCount=0`。
- 两个空白重复页已归档为 `ARCHIVE_DO_NOT_RELEASE_02_EMPTY_20260621`、`ARCHIVE_DO_NOT_RELEASE_06_EMPTY_20260621`，不再作为 release 页使用。
- 已按 `/hd-put` 收敛到 placement-only；下一步应进入 `/hd-wire` 做真实元件到元件连线，当前还不能把“可读版式”误报成“可出图原理图”。

## 2026-06-21 EasyEDA hd-wire 布线执行

- [x] 重新读取 `hd-wire`、`easyeda-api`、`tasks/lessons.md`、放置修复报告，确认本轮是 wiring-only。
- [x] 记录当前工程/页面/component snapshot，并确认 wire / net label / power symbol 相关 API 可用。
- [x] 在 `POWER` 页先做一段真实点对点连线小样，验证 exact `pin.x`/`pin.y`、wire API 和边界不越权。
- [x] 重新读取 `computer-use` skill，并确认本轮会话已暴露真实 `mcp__node_repl__js` Windows automation 通道。
- [x] 复验 EasyEDA bridge 与当前工程上下文：`codex_tesla` 在线，桌面 EasyEDA 窗口可枚举。
- [ ] 完成 `POWER` 页：GND -> `VBUS_USB/+5V/+3.3V/+12V_PA` -> 支撑网络，保证 source->protection->filter->regulator->output chain 可追踪。
- [ ] 完成 `MCU` 页：USB/BOOT/RST/去耦/外设映射相关连线，保持 `IO1 -> POT_IO1`、不把 `IO34/IO33-37` 接业务网。
- [ ] 完成 `PERIPHERAL` 页：音频、MicroSD、LED、编码器/电位器模块内真实短线连通。
- [ ] 完成 `INTERFACE` 页：CAN/OBD2 与测试接口真实短线连通，保持 transceiver -> protection -> connector 阅读顺序。
- [ ] 逐页审计：wire endpoints、required nets、component snapshot 未增删替换、必要位移日志、全页截图/对象统计。
- [ ] 保存工程并输出 `/hd-wire` 证据报告到 `outputs/`。

### Review

- 已确认 `SCH_PrimitiveWire.create(line, net, color, lineWidth, lineType)` 是 bridge 暴露的 beta API，`SCH_PrimitiveWire.getAll()`、`delete()` 也可调用。
- 已记录组件快照：`outputs/easyeda_hd_wire_component_snapshot_before_20260621.json`。
- 已记录 POWER 页关键 pin dump：`outputs/easyeda_hd_wire_power_pin_dump_20260621.json`。
- 已确认一个 placement 层遗漏：`POWER` 页除主清单外还存在 `C10/R11/R12/L13` 四个器件，必须纳入 `/hd-wire` 审计。
- `computer-use` 本轮已从“只有 skill、无执行工具”变为“可执行 node_repl + sky API”，可以改走 GUI 真落线 + bridge 读回验证。
- 当前 bridge 读到的工程为 `codex_tesla`，包含 `PERIPHERAL / POWER / MCU / INTERFACE / POWER-DCDC` 共 5 个 schematic pages；后续 GUI 布线必须先确认 release 页范围，避免把 `POWER-DCDC` 误当旧归档页。
- 已用 GUI 真落线验证：通过 `Alt+W + 两次 click` 能在 EasyEDA 中实际生成 wire，bridge 可稳定读回单根短线 `320,390 -> 400,390`。
- GUI 焦点存在不稳定行为：同样的 `Ctrl+Z` / `Delete` 对 wire 的撤销和删除并不总是生效，说明 EasyEDA 当前焦点不一定落在原理图编辑面；继续整页布线前，需要先固化“canvas focus -> draw -> readback -> fallback cleanup”节奏。
- 为避免污染工程，测试 wire 已用 bridge 按 `primitiveId[]` 数组删除，当前 `wireCount` 已恢复为 `0`。
- 发现两个关键 bridge/wire blocker：
  1. `sch_PrimitiveWire.create()` 可能返回 `primitiveId`，但同一请求内和下一请求里 `getAll()` 仍返回 `0`，说明“返回对象”不能当作已落图证据。
  2. 当导线在 USB-C 引脚列附近共用坐标或在同一请求里批量创建时，bridge 可能出现 `create failed!` 或把多段错误并网。
- 当前已把 `POWER` 页导线清回 `0`，避免残留脏 wire 继续污染工程。
- 本轮阻塞不在设计逻辑，而在 EasyEDA wire beta API 的可持久化行为；若继续仅靠当前 bridge，无法负责任地声称原理图已完成布线。

---

# 2026-07-05 docs/plan/PRD 文档整理

> 状态: 已完成

## 计划清单

- [x] 读取项目记忆和 `tasks/lessons.md`，确认文档整理边界。
- [x] 扫描 `docs`、`docs\plan`、`docs\PRD`、`docs\reference` 的当前文件和时间戳。
- [x] 判定当前应保留入口、旧版本/重复审核稿、临时文件和不确定项。
- [x] 删除明确无用的临时文件和被新版本完全替代的旧版本。
- [x] 更新文档索引，说明当前入口、历史归档和 reference 边界。
- [x] 运行验证命令，证明目标目录无误删、索引可读、保留入口存在。

## 初始整理原则

- `docs\reference` 是第三方参考资料库，本轮只索引顶层项目，不批量重命名或删除内部文件。
- `docs\PRD\codex\PRD__prd-v20260522-codex-v4.2-current.md` 是当前 PRD 入口。
- `docs\plan\easyeda_hd_put_repair_plan_for_gpt54__plan-v20260621-codex-v1.0.md` 是最新 EasyEDA hd-put 修复计划入口。
- 同主题旧版本如果已被更高版本覆盖，优先删除；历史审核/根因记录若仍解释决策来源，保留但在索引中标为历史。

## Review

- 删除清单已写入 `E:\Tesla_speed\tasks\docs_cleanup_deleted_20260705.md`。
- 已删除 `docs` 根目录 5 个 `temp*.json` 临时文件。
- 已删除旧 PRD/PRD 审核稿 9 个，保留唯一当前 PRD: `docs\PRD\codex\PRD__prd-v20260522-codex-v4.2-current.md`。
- 已删除 `docs\plan\codex\__write_plan.py`、`docs\plan\codex\_header.txt` 和哈希重复的 MIMO v4.2，保留 MIMO v4.3。
- 已新增 `docs\DOCUMENT_INDEX_v20260705.md`，并在旧 `DOCUMENT_INDEX_v20260612.md` 顶部标注新索引。
- 验证结果：保留入口文件全部存在；删除候选全部缺失；`docs\PRD` 现为 1 个文件，`docs\plan` 现为 14 个文件，`docs\reference` 顶层仍为 13 个项目；排除旧 rename map 后未扫描到旧 temp/PRD 审核/v4.2/scratch 残留引用。
- Git 验证不可用：`E:\Tesla_speed` 当前不是 Git 仓库，`git status` 返回 `fatal: not a git repository`。

# 2026-07-07 KiCad v1 自动化闭环恢复

> 状态: 已完成

## 计划清单

- [x] 确认 `hardware_kicad` 当前状态：`kicad-cli` 已安装，旧阻塞主要在生成 root 可解析性。
- [x] 修复 `hardware_kicad\scripts\gen_schematic.py` 根图生成，避免 KiCad 10 解析失败。
- [x] 运行 `python -m pytest -q`，确认现有测试仍通过。
- [x] 运行 `python scripts\gen_schematic.py` 重建 KiCad 文件。
- [x] 运行 `scripts\check_erc.ps1`，在 `kicad-cli` 可用时得到 ERC 报告。
- [x] 运行 `scripts\export_outputs.ps1`，输出 PDF/SVG/BOM/Netlist。
- [x] 复核关键输出文件存在性与内容，更新 `docs\review_checklist.md`。
- [x] 将“KiCad 10 安装后可恢复闭环”的状态回写本条目。

## Review

- 2026-07-07 续：在 `D:\Program Files\KiCad\10.0\bin\kicad-cli.exe` 可用后完成闭环恢复。
- `python -m pytest -q` 通过：`10 passed`。
- `python scripts\gen_schematic.py` 成功重建 `kicad\Tesla_Sound_Simulator.kicad_sch`，并保持两次运行输出一致（无语义抖动）。
- `scripts\check_erc.ps1` 通过 CLI 识别工程，导出 `output\erc.rpt`（含 105 条违规）。
- `scripts\export_outputs.ps1` 成功导出 `output\schematic.pdf`、`output\svg\Tesla_Sound_Simulator*.svg`、`output\bom.csv`、`output\netlist.net`。
- 根源问题已闭环：生成器改为“基于 `kicad/root_template.kicad_sch` 的模板补丁式生成”，不再需要手工替换模板文件。

---

# 2026-07-08 KiCad MCP 安装与专业原理图重绘

> 状态: 执行中

## 计划清单

- [x] 复核 `hardware_kicad` 当前状态，确认 5.4 产物是“可导出但占位式”的原理图。
- [x] 安装 `mixelpixx/KiCAD-MCP-Server` 到 `E:\AI_Tools\Other\KiCAD-MCP-Server`。
- [x] 验证 MCP server 使用 KiCad Python 10.0.4 可启动，并修正 `KICAD_PYTHON` 环境变量。
- [x] 注册 Codex MCP 配置；当前会话需重启 Codex 后才会暴露 `kicad` MCP 工具。
- [x] 用测试锁定专业图纸验收：A3/A4 横版、模块框、中文标题、核心页布局、禁止占位式 release 图纸。
- [x] 改造 `scripts\gen_schematic.py`，生成四页专业风格 KiCad 原理图。
- [x] 运行 pytest、生成器、ERC、PDF/SVG/BOM/netlist 导出。
- [x] 做 PDF/SVG 文件级和视觉结构级复核，更新 `hardware_kicad\docs\review_checklist.md`。

## Review

- 安装验证发现 MCP 默认会走系统 Python 3.14，导致 `pcbnew` 校验失败；已改为显式 `KICAD_PYTHON=D:\Program Files\KiCad\10.0\bin\python.exe`。
- 本轮验收重点从“输出物存在”提升到“PDF 四页具备工程图纸阅读性”。
- `python -m pytest tests -q`: `15 passed`。
- `python scripts\gen_schematic.py`: 成功。
- `.\scripts\check_erc.ps1`: 生成 `output\erc.rpt`，结果为 `0` errors / `24` footprint warnings。
- `.\scripts\export_outputs.ps1`: 生成 `output\schematic.pdf`、`output\svg\*.svg`、`output\bom.csv`、`output\netlist.net`。
- `output\netlist.net` 当前包含 `24` 个 component entries；`output\bom.csv` 当前包含 `24` 个元件行。
- PDF 已渲染为 `hardware_kicad\output\visual_review\schematic_page-*.png` 并抽查四个子页：POWER、INTERFACE、MCU、PERIPHERAL 均非空且有功能分区。
- 颜色边界：KiCad CLI 对直接写入 child sheet 的 S-expression 颜色字段不稳定；已保留默认蓝色图元和浅黄色符号填充，显式红/蓝样式作为 GUI/MCP 二次精修项记录。

## Correction Follow-up (2026-07-08)

- Jovi 指出 PDF 中芯片/器件像单脚或 P1/P2 假符号；复核确认根因是生成器只从 `nets.endpoints` 反推 pin，没有显式 pin table。
- 已新增显式 pin table：ESP32-S3、CAN transceiver、USB-C、MicroSD、WS2812、I2S DAC、audio amp、regulator、connector/protection symbols。
- 已隐藏非必要 BOM 字段，避免 `MPN/LCSC/TBD/Assembly/Source` 堆叠在符号上方。
- 已新增回归测试：核心符号必须包含真实 pin 名，不能退化成 endpoint fallback。
- 最新验证：`python -m pytest tests -q` 为 `17 passed`；ERC 为 `0` errors / `24` footprint warnings；PDF/SVG/BOM/netlist 已重新导出。
`n## 2026-07-08 EasyEDA pin-to-label 布线恢复记录`n`n- [x] 已确认 Jovi 验收样式：组件 pin 或模块边界先拉短线，再贴红色网络标签，禁止漂浮标签。`n- [x] 已更新 hd-wire 规则，加入 pin -> short stub -> net label 强制模板。`n- [x] EasyEDA bridge server 可访问，但当前 edaConnected=false；继续用 GUI 处理并记录验证边界。`n- [ ] 恢复 run-api-gateway 扩展连接，重新获得 pin 坐标读回。`n- [ ] MCU 页 44 pin ESP32 符号仍是 release 阻塞项；未确认 44 pin 前不得宣称 MCU 布线通过。`n- [ ] 逐页把跨模块信号改成 pin/stub/label 样式，并用截图复核。`n

- [x] 2026-07-08 API 复核：MCU 页 U3_MCU pinCount=41，未达到 ESP32-S3 44 pin，MCU release 布线阻塞。
- [x] INTERFACE/CAN 小样已用 API 创建真实 wire，并修复 CANL 误经过 +5V netflag 的路径。

- [x] PERIPHERAL 小样完成：MicroSD 的 SD_MISO/SD_MOSI/SD_CLK/SD_CS/+3.3V/GND 已从 netport 拉到 J9 pin；WS2812B 的 LED_DATA/LED_DOUT/+5V/GND 已布线。
- [x] PERIPHERAL 坐标复核：新增目标线未经过无关 netport/netflag 坐标；已修复 LED_DATA 与 +5V y=205 重叠合并问题。
- [x] EasyEDA 保存成功：eda.sch_Document.save() 返回 true。
- [ ] 剩余：POWER/POWER-DCDC 缺少必要 netport/label，属于 hd_put 范围；MCU 仍需 44 pin 符号后再进入 hd_wire。
- [ ] 剩余：POWER/POWER-DCDC 缺少必要 netport/label，属于 hd_put 范围；MCU 仍需 44 pin 符号后再进入 hd_wire。

---

# 2026-07-08 ESP-IDF firmware delivery audit

> 状态: 执行中

## 计划清单

- [x] 核对 `E:\Tesla_speed\prj` git 状态、HEAD、远端和 `7e92ca3` 提交是否存在。
- [x] 盘点 ESP-IDF 工程结构、组件、OpenSpec main specs 和 VSCode/ESP-IDF 配置。
- [x] 新鲜运行可行的构建/检查命令，确认 `tesla_simulate_vico.bin` 产物证据。
- [x] 对照 S0-S4 交付表检查功能边界和仍需人工验证的烧录/硬件项。
- [x] 将结论、风险和下一步建议写入本 Review。

## Review

- Git 状态确认：`E:\Tesla_speed\prj` 当前 `HEAD = 7e92ca3`，同时也是 `origin/main` 和 `origin/HEAD`；`git status --porcelain` 为空。远端配置为 `https://ghfast.top/https://github.com/Jovifei/Tesla_Simulate_vico.git`。
- OpenSpec 确认：`openspec validate --all --strict` 通过，5 个 main specs 均 pass：`audio-engine`、`ble-config`、`can-frame-parser`、`peripherals`、`twai-can-source`。
- VSCode/ESP-IDF 配置确认：`.vscode/settings.json` 指向 `E:\project\ESP_IDF_support\v5.3.2\esp-idf`、`E:\project\ESP_IDF_support\tools`、目标 `esp32s3`、build path `${workspaceFolder}/build`。普通 PowerShell 需要先设 `$env:IDF_TOOLS_PATH='E:\project\ESP_IDF_support\tools'` 再执行 `export.ps1`，否则 `export.ps1` 会找不到工具链注册版本。
- 新鲜构建验证：`$env:IDF_TOOLS_PATH='E:\project\ESP_IDF_support\tools'; & 'E:\project\ESP_IDF_support\v5.3.2\esp-idf\export.ps1'; idf.py build` 通过，exit=0，重新生成 `build\tesla_simulate_vico.bin`。
- 产物证据：`build\tesla_simulate_vico.bin` = 735024 bytes，更新时间 2026-07-08 13:55:09；`build\tesla_simulate_vico.elf` = 9306828 bytes，更新时间 2026-07-08 13:55:09。
- Size 证据：`idf.py size` 通过；app image `0xb3730` bytes，最小 app partition `0x400000` bytes，剩余 `0x34c8d0` bytes，约 82% free。
- 功能核对：CAN 使用 `TWAI_MODE_LISTEN_ONLY`，解析 `0x256`/`0x116`；audio 使用 ESP-IDF I2S standard TX；BLE 使用 ESP-IDF NimBLE GATT `ffe0` + `ffe1..ffe7`；S4 外设包含 SD JSON、Encoder、ThrottlePot、WS2812，并已接入 `app::App`。
- 仍需注意：`README.md` 和 `PLAN.md` 仍含旧状态文字（如 pending、S1 next、S3 `ffe1-ffeE`），与 S4 已 archived 的真实状态不一致，应作为下一次文档同步修复。
- 仍需注意：`twai-can-source` spec 写 TX queue depth 应为 0，但当前实现用 `TWAI_GENERAL_CONFIG_DEFAULT(...)`；安全边界仍由 `TWAI_MODE_LISTEN_ONLY` 和无 transmit API 保证，但严格规格一致性建议后续显式设置或修正文档。
- 仍需注意：若在普通 shell 构建，必须显式设置 `IDF_TOOLS_PATH`；VSCode ESP-IDF 插件按 settings 应能找到同一工具目录。
- 证明边界：本轮完成编译、OpenSpec、静态功能和产物验证；未做 `idf.py flash`、串口 monitor、BLE 手机连接、真实 CAN/SD/ADC/RMT/I2S 硬件验证。

---

# 2026-07-08 S5.1 audio volume pipeline

> 状态: 执行中

## 计划清单

- [x] 参考 `docs\reference` 与当前 S4 交付，确认下一步最小软件增量为 `audio_volume_pct -> AudioEngine -> I2S sample amplitude`。
- [x] TDD RED：新增音量契约编译测试，先证明当前 `AudioEngine`/`I2sAudioEngine` 没有音量接口或缩放 helper。
- [x] GREEN：实现 `AudioEngine::setVolumePercent()`、音量 clamp/helper、`I2sAudioEngine` 样本缩放、`StubAudioEngine` 测试替身状态。
- [x] GREEN：在 `app::App` 中启动后应用已加载音量，并在编码器修改音量时立即下发到 audio。
- [x] 更新 `openspec/specs/audio-engine/spec.md` 与 `openspec/specs/peripherals/spec.md`，让规格描述匹配真实配置闭环。
- [x] 运行新测试、`idf.py build`、`idf.py size`、`openspec validate --all --strict`，记录证据和硬件验证边界。

## Review

- 选型依据：`docs\reference` 的侧翼分析建议下一大块做 minimal audio timbre v0；本轮先做更小的 S4 闭环修复，因为 `audio_volume_pct` 已被 SD/encoder 修改但尚未作用到 I2S 输出。
- TDD RED：新增 `components/audio/test/test_audio_volume_contract.cpp` 后，先运行 `xtensa-esp32s3-elf-g++ ... -c components/audio/test/test_audio_volume_contract.cpp`，失败于缺少 `audio/AudioVolume.h`，证明测试先于实现。
- 实现：新增 `components/audio/include/audio/AudioVolume.h`，提供 `clampVolumePercent()` 与 `volumeGain()`；扩展 `AudioEngine::setVolumePercent(std::uint8_t)`；`I2sAudioEngine::render()` 使用 `AMPLITUDE * volumeGain(volume_pct_)` 缩放样本；`StubAudioEngine` 记录 volume 供契约测试；`App::begin()` 和 encoder volume 变化时立即调用 `audio_.setVolumePercent(...)`。
- 文档/spec：更新 `openspec/specs/audio-engine/spec.md` 的 runtime volume requirement；更新 `openspec/specs/peripherals/spec.md` 的 SD-loaded volume 和 encoder volume 应用场景；同步 `README.md` 与 `PLAN.md` 的旧状态文字。
- 验证 1：音量契约编译测试通过，exit=0。
- 验证 2：`openspec validate --all --strict` 通过，5 specs passed / 0 failed。
- 验证 3：`idf.py build` 通过，exit=0，生成 `build\tesla_simulate_vico.bin`。
- 验证 4：`idf.py size` 通过；`tesla_simulate_vico.bin binary size 0xb37a0 bytes`，最小 app partition `0x400000`，剩余 `0x34c860`，约 82% free；bin 文件大小 735136 bytes，更新时间 2026-07-08 14:04:04。
- 仍需硬件验证：实际 PCM5102A 声压变化、编码器旋转即时音量变化、SD JSON 加载音量后的上电效果尚未上板验证。
- 推荐下一步：S5.2 minimal audio timbre v0，在不引入 Arduino audio libs、不做 SD WAV streaming 的前提下，把单正弦升级为确定性的基础谐波/燃烧脉冲/负载增益模型。

---

# 2026-07-08 ESP-IDF build helper script

> 状态: 已完成

## 计划清单

- [x] 检查 `E:\Tesla_speed\prj` 当前工作树和现有脚本约定，确认没有已有 PowerShell build helper。
- [x] 新增 `scripts\esp-idf.ps1`，固化 ESP-IDF v5.3.2 本机路径和工具路径。
- [x] 用新脚本执行 `build`，证明普通 PowerShell 中可自编译。
- [x] 用新脚本执行 `size`，证明脚本能透传 `idf.py` 参数。
- [x] 更新 `README.md` 的 Build / Flash & Monitor 使用方式。

## Review

- 新增脚本：`E:\Tesla_speed\prj\scripts\esp-idf.ps1`。
- 脚本设置：`IDF_PATH=E:\project\ESP_IDF_support\v5.3.2\esp-idf`、`IDF_TOOLS_PATH=E:\project\ESP_IDF_support\tools`、`IDF_PYTHON_ENV_PATH=E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env`。
- 用法：普通 PowerShell 中在 `E:\Tesla_speed\prj` 运行 `.\scripts\esp-idf.ps1 build`；传参示例 `.\scripts\esp-idf.ps1 size`、`.\scripts\esp-idf.ps1 -p COMx flash monitor`。
- 验证 1：`& E:\Tesla_speed\prj\scripts\esp-idf.ps1 build` 通过，exit=0，生成 `build\tesla_simulate_vico.bin`。
- 验证 2：`& E:\Tesla_speed\prj\scripts\esp-idf.ps1 size` 通过，exit=0，报告 `tesla_simulate_vico.bin binary size 0xb37a0 bytes`，最小 app partition `0x400000`，剩余 `0x34c860`，约 82% free。
- 非阻断输出：完整重配时 BLE GATT sentinel initializer 有 `-Wmissing-field-initializers` warnings；ESP-IDF 自身 `micro-ecc` submodule 提示 out-of-date；二者本轮未阻断编译。

---

# 2026-07-08 PRD software progress audit

> 状态: 已完成

## 计划清单

- [x] 定位当前 PRD：`docs\PRD\codex\PRD__prd-v20260522-codex-v4.2-current.md`。
- [x] 对照 PRD 的 P0/P1/P2 软件功能，核对 `prj` 当前源码、OpenSpec main specs 和已完成交付阶段。
- [x] 运行轻量验证：ESP-IDF build、OpenSpec strict validate、关键静态检索、git status。
- [x] 记录 PRD 完成度、关键差距和下一步优先级。

## Review

- 新鲜验证：`& E:\Tesla_speed\prj\scripts\esp-idf.ps1 build` 通过，`tesla_simulate_vico.bin binary size 0xb37a0 bytes`，最小 app partition `0x400000`，剩余约 82%。
- 新鲜验证：`openspec validate --all --strict` 通过，5 specs passed / 0 failed。
- 当前固件工程骨架进度较高：S0-S4 已形成可编译链路，包含 CAN listen-only、基础 CAN parser、I2S 单正弦音频、NimBLE GATT、SD JSON、encoder、throttle pot、WS2812；S5.1 已补上音量配置到 I2S 幅度的闭环。
- 按 PRD V1 产品化软件进度看，整体仍是 MVP 核心链路阶段，约 30%-35%；P0 功能约 35%，P1 功能约 15%-20%，P2 功能约 15%-25%。
- 关键差距 1：PRD 当前写 Tesla CAN speed/throttle 为 `0x257` / `0x118 byte[4]`，当前 OpenSpec 和代码仍为 `0x256` / `0x116`，需要先确定真实车端/DBC 来源后统一。
- 关键差距 2：PRD 要求音频响应 <50ms、4-layer mix、6 个 WAV 声浪；当前 `main.cpp` 每 1000ms tick 一次，音频为单正弦合成，不满足 PRD 产品化声浪要求。
- 关键差距 3：PRD BLE 服务为 `0000fff0` 且特征覆盖 `ffe1` 到 `ffeE`；当前实现为 `ffe0` 服务 + `ffe1..ffe7`，属于早期配置骨架，未对齐小程序协议。
- 关键差距 4：PRD 要求 DBC -> 标准 OBD-II PID -> 离线模拟的数据源自适应；当前只有 TWAI listen-only 加本地油门电位器 fallback，没有 PID 降级/状态上报/5s 自动切换。
- 关键差距 5：WiFi OTA、虚拟 gearbox、物理 mute GPIO8、完整 self-test、10Hz 串口/JSON 测试面板、SD 声浪包管理尚未实现。
- 推荐下一步：先做 PRD/OpenSpec 对齐决策（CAN ID、BLE UUID 表），再做 S5.2 FreeRTOS 高频任务与队列，把 1s app tick 拆成 CAN/audio/control 的低延迟闭环；随后实现 PRD BLE map 和 minimal 4-layer timbre v0。
# 2026-07-08 S6.5 + S7 WiFi OTA 执行

> 状态: 部分完成，阻塞中（代码/文档/门禁已落地；IRAM 与硬件验收未关闭）

## 计划清单

- [x] S6.5 基线加固：梳理 dirty worktree 边界，完成一次 IRAM 缩减尝试并记录结果
- [x] 扩展 `RuntimeConfig` / `SdConfigStore`，加入 WiFi OTA 持久化字段
- [x] 改造 BLE 配置链路：`ffe8` 承载 OTA JSON，BLE 写入形成待应用配置，不再只写私有 blob
- [x] 新增 `ota` component：WiFi STA、HTTPS OTA、版本/分区/错误状态
- [x] 接入 `App`：启动时同步配置，tick 中消费 BLE 待更新配置，按需持久化，后台一次性 OTA 检查
- [x] 更新分区表、OpenSpec、README/PLAN/PRD 与交付证据
- [x] 跑 `build` / `size` / `size-components` / `openspec validate --all --strict --json`

## 执行原则

- 复用现有 BLE UUID 契约，不新增服务 UUID
- `ffe8` 仅保存 OTA 配置，默认下次启动执行 OTA，不在 BLE 写入时立即升级
- 实机 BLE / WiFi / OTA 验收若当前环境无法完成，明确记录为硬件阻塞

## Review

- 代码侧已落地 S7 OTA baseline：新增 `components/ota/`、OTA 分区表、`RuntimeConfig` OTA 字段、SD JSON 持久化、`ffe8` OTA JSON 配置链路，以及 `App` 启动时的一次性 OTA 检查触发。
- BLE 契约保持不扩 UUID：主服务仍为 `0xfff0`，兼容服务仍为 `0xffe0`；`ffe8` 现承载 OTA 设置 JSON，`ffe5` 返回 OTA/WiFi 诊断 JSON，`ffea` 保持 live status。
- 文档与规格已同步：`prj/README.md`、`prj/PLAN.md`、`docs/PRD/codex/PRD__prd-v20260522-codex-v4.2-current.md`、`docs/record/*`、`prj/openspec/specs/ble-config/spec.md`、`prj/openspec/specs/peripherals/spec.md` 已对齐当前实现与阻塞状态。
- 新鲜验证 1：`E:\Tesla_speed\prj` 下执行 `.\scripts\esp-idf.ps1 build` 通过；当前 app image 为 `0x11db70` bytes，最小 app partition `0x400000`，剩余 `0x2e2490` bytes（约 `72%` free）。
- 新鲜验证 2：`.\scripts\esp-idf.ps1 size` 通过；IRAM 仍为 `16383 / 16384`（`99.99%`），剩余 `1` byte，S6.5 release-hardening gate 仍未关闭。
- 新鲜验证 3：`.\scripts\esp-idf.ps1 size-components` 通过；IRAM 主要压力仍来自框架库，头部包括 `libesp_system.a`、`libesp_hw_support.a`、`libheap.a`、`libbtdm_app.a`、`libfreertos.a`、`libnewlib.a`。
- 新鲜验证 4：`openspec validate --all --strict --json` 通过，`5/5` pass；`peripherals` 仅有一条“requirement text is very long”的 `INFO`，无失败项。
- 阻塞结论：当前可以证明“OTA baseline 已实现且可编译”，不能证明“OTA 已可交付”。剩余阻塞是 IRAM headroom 仍卡边界，以及 BLE / WiFi join / OTA swap 尚无实机验收证据。

---

# 2026-07-08 S6.5/S7 路线1：定向 IRAM 缩减

> 状态: 已执行，仍需硬件验收；`idf.py size` 的 16KB IRAM 小窗仍为风险项

## 计划清单

- [x] 复核当前 IRAM 证据：`idf.py size` 为 `16383 / 16384`，剩余 `1` byte。
- [x] 用 map/nm/objdump 和子 agent 只读分析确认：项目源码无本地 `IRAM_ATTR` / `RTC_IRAM_ATTR` / `ESP_INTR_FLAG_IRAM` 误用。
- [x] 第一轮低风险配置：切换 `CONFIG_COMPILER_OPTIMIZATION_SIZE`、关闭 NimBLE 5.0 feature、启用 FreeRTOS flash placement，并修复 `-Os` 暴露的 OTA WiFi 字段拷贝告警。
- [x] 第二轮低风险配置：启用 heap flash placement、关闭 IRAM event posting、关闭 SPI master/bus-lock IRAM 默认项，避免非硬实时路径继续塞进 IRAM。
- [x] 第三轮对照配置：启用 `CONFIG_BT_CTRL_RUN_IN_FLASH_ONLY` 并配套 `CONFIG_SPI_FLASH_AUTO_SUSPEND`，把 BLE controller 从 IRAM/DIRAM 压力中移出。
- [x] 运行 `build` / `size` / `size-components` / `openspec validate --all --strict --json`。
- [x] 记录最终 IRAM headroom、运行风险和下一步决策。

## Review

- 第一轮验证：`.\scripts\esp-idf.ps1 build` 通过；`.\scripts\esp-idf.ps1 size` 仍显示 IRAM `16383 / 16384`，说明 release-size 优化减少 flash/DIRAM，但没有解除 IRAM 悬崖。
- 修复项：`components\ota\OtaManager.cpp` 的 WiFi SSID/password 写入改为固定缓冲区 bounded copy，避免 `-Os` 下 `snprintf` truncation 被 `-Werror` 阻断。
- 第二轮结果：`CONFIG_HEAP_PLACE_FUNCTION_INTO_FLASH`、关闭 `CONFIG_ESP_EVENT_POST_FROM_IRAM_ISR`、关闭 SPI master/bus-lock IRAM 默认项后，`libheap.a`、`libesp_event.a`、`libesp_driver_spi.a` 在 `size-components` 中不再贡献 IRAM；但总 IRAM 仍为 `16383 / 16384`。
- 第三轮结果：启用 `CONFIG_BT_CTRL_RUN_IN_FLASH_ONLY=y` 后，`size-components` 显示 `libbtdm_app_flash.a` 的 IRAM 为 `0`；配套开启 `CONFIG_SPI_FLASH_AUTO_SUSPEND=y`，降低 flash erase/write 期间 BLE 中断风险。
- 最终验证 1：`.\scripts\esp-idf.ps1 build` 通过，`tesla_simulate_vico.bin binary size 0x109330`，最小 OTA app partition `0x400000`，剩余 `0x2f6cd0`（约 `74%` free）。
- 最终验证 2：`.\scripts\esp-idf.ps1 size` 通过；Flash Code `829498`，Flash Data `173040`，DIRAM `92263 / 341760`（`27.0%`），IRAM 仍 `16383 / 16384`（`99.99%`，剩余 `1` byte）。
- 最终验证 3：`.\scripts\esp-idf.ps1 size-components` 通过；IRAM 头部仍主要来自 `libesp_system.a`、`libesp_hw_support.a`、`libspi_flash.a`、`libxtensa.a`、`libnewlib.a` 等底层必驻/flash/cache/中断路径。
- 最终验证 4：`openspec validate --all --strict --json` 通过，`5/5` specs passed；`git diff --check` 通过，仅有 CRLF 规范化提示。
- 运行风险：`CONFIG_BT_CTRL_RUN_IN_FLASH_ONLY` 会把 BLE controller 代码放入 flash，ESP-IDF 文档提示擦写 flash 期间 BLE 性能可能下降；当前已启用 auto-suspend，但必须实机验证 BLE 广播/连接、BLE 写 `ffe8`、WiFi OTA 期间 BLE 不崩溃。
- 阻塞结论：路线1已把 DIRAM 从本轮前的约 `120671` 降到 `92263`，并清掉 heap/event/SPI/BLE controller 的组件级 IRAM 压力；但 `idf.py size` 的 16KB IRAM 小窗仍为 `1` byte free，S6.5 不能标记为“无 IRAM 风险”，只能带明确风险进入硬件验收。

---

# 2026-07-08 firmware short handoff

> 状态: 已完成

## 计划清单

- [x] 交叉核对当前 PRD、README、PLAN、OpenSpec 和 `tasks/todo.md`，整理当前固件交付真相。
- [x] 明确短期交接文件边界：只写当前工程状态、阻塞项和下一步，不覆盖 PRD。
- [x] 新增 `docs\record\firmware_short_handoff__record-v20260708-s7.md`。
- [x] 复核交接文件中的已实现/未实现/下一步与当前源码、验证证据一致。

## Review

- 交接文档目标已锁定：为后续继续推进 S6.5/S7/S8 的开发者提供单页状态快照，避免把“可编译 baseline”误判为“产品级功能完成”。
- 当前必须明确写入交接文件的边界包括：IRAM release gate 仍未关闭、BLE/WiFi/OTA 仍缺硬件运行证据、音频仍是 RPM 单正弦占位、速度/加速度差异化声浪算法尚未建模，更没有 MATLAB 定参后的固件移植。
- 已新增 `docs\record\firmware_short_handoff__record-v20260708-s7.md`，将 PRD 目标、当前已实现、未完成项、验证快照和建议下一步统一收口为单页交接材料。
- 复核结论：交接文件与当前 README/PLAN/PRD 口径一致，并且与源码事实一致；尤其音频部分仍应定义为“RPM 单正弦 baseline”，不能对外表述为已完成速度/加速度差异化声浪算法。

---

# 2026-07-08 README bilingual detail update

> 状态: 已完成

## 计划清单

- [x] 核对当前 `prj\README.md` 内容与 GitHub 官方远端状态。
- [x] 将 README 改为中文 / English 可选择阅读，并扩展项目介绍、功能状态、构建方式、验证边界。
- [x] 运行 README 相关 diff/格式检查，确认没有明显 Markdown/空白问题。
- [x] 提交并 push 到官方 `Jovifei/Tesla_Simulate_vico` 的 `main` 分支。

## Review

- 当前 README 是英文短版，缺少中文入口，也没有把“已实现 baseline / 未完成硬件验收 / 声浪算法边界 / OTA 风险”讲完整。
- 已将 README 改为顶部语言导航：中文介绍 / English Overview；两种语言都包含项目目标、硬件目标、工程结构、已实现功能、未完成项、构建验证、BLE 合约、安全边界和下一步。
- 格式检查：`git diff --check -- README.md` 通过，仅有 LF/CRLF 提示，无 whitespace error。
- GitHub 官方主分支已更新：commit `5fd6598 Expand bilingual README`，远端 `refs/heads/main` 指向 `5fd6598c81e9e4c529bf019052a5ca3d346c6360`。

---

# 2026-07-08 PRD completion phase plan docs

> 状态: 已完成

## 计划清单

- [x] 读取 `prj\docs` 目录结构、计划/待完成阅读指引、当前 `PLAN.md`、README、PRD 和短交接记录。
- [x] 新增 `prj\docs\04-planning\01-firmware-roadmap.md`，写明从当前 baseline 到最初设计需求的阶段路线。
- [x] 新增 `prj\docs\09-backlog\01-firmware-backlog.md`，按模块分点列出待完成项、优先级、验收证据。
- [x] 新增/更新 `prj\docs\README.md`，作为文档入口并指向计划与待完成清单。
- [x] 运行文档格式检查并记录 Review。

## Review

- 当前 `prj\docs` 已整理为 `NN-english-kebab` 路径，当前路线图入口为 `04-planning`，待完成清单入口为 `09-backlog`。
- 旧架构文档仍有 Arduino/MQTT/旧 GPIO 等历史口径；本轮不扩改旧架构文档，计划以当前 ESP-IDF PRD、README、OpenSpec、交接记录为准。
- 已新增三份文档：`docs\04-planning\01-firmware-roadmap.md`、`docs\09-backlog\01-firmware-backlog.md`、`docs\README.md`。
- 因 `prj\.gitignore` 原本忽略整个 `docs/`，已最小放行上述三份新文档，旧阅读指引和历史文档仍保持忽略状态，避免一次性引入旧口径文档。
- 检查结果：`git diff --cached --check` 通过；占位词扫描未命中 `TBD/TODO/implement later/fill in details` 等红旗文本。
- 已提交并 push 到官方主分支：commit `32a800e Document firmware completion roadmap`；远端 `refs/heads/main` 指向 `32a800eaf04a4303f3ad85c9c028f04632617a51`。

---

# 2026-07-09 S8 Python 声浪仿真核实

> 状态: 已完成；可作为第一版离线仿真基线

## 计划清单

- [x] 检查 `prj/tools/sound_sim` 文件是否存在，并读取实现边界。
- [x] 检查 `E:\Tesla_speed\docs\reference` 中的声浪/EV 参考资料是否存在。
- [x] 运行 `python -m unittest discover -s tools\sound_sim\tests -v`。
- [x] 运行 `python tools\sound_sim\simulate_sound.py --out build\sound-sim`。
- [x] 核对输出 WAV/CSV/JSON 的格式、字段和可固件移植性。
- [x] 写入 Review：是否可行、风险和下一步建议。

## Review

- `tools/sound_sim` 文件存在：`sound_model.py`、`simulate_sound.py`、`README.md`、`tests/test_sound_model.py`。当前 `tools/` 是 untracked，`__pycache__/` 被 `.gitignore` 忽略。
- 参考资料存在：`simulating-EV-sound-main` 支持“简单可移植”方向，`tesla-engine-sound-main` 有 speed/pedal/power 到虚拟 RPM 的映射，`VehicleNoiseSynthesizer-main` 有 RPM/load clip bank、恒功率 crossfade 和加减速音色分离思路。
- 单测通过：`python -m unittest discover -s tools\sound_sim\tests -v`，3/3 pass。
- 仿真生成通过：`python tools\sound_sim\simulate_sound.py --out build\sound-sim`，输出 WAV/CSV/JSON 三个文件。
- WAV 核验：mono、16-bit、44100 Hz、529200 frames、12.0 s、peak 10056，非静音样本 529105。
- CSV 核验：600 行，字段包含 `time_s/rpm/frequency_hz/amplitude/brightness/muted/h1..h5`；RPM 800.0 到 2573.4，frequency 40.0 到 93.2 Hz，amplitude 0.0946 到 0.5444。
- JSON 核验：schema `jovi.sound_model.v1`，包含 4 个 RPM/frequency/amplitude/brightness breakpoint 和 Q15 harmonic gains `[32767, 15260, 9478, 4041, 2228]`，适合作为固件小表起点。
- 注意：当前 demo drive cycle 未超过 150 km/h，因此输出 CSV 的 `muted_rows=0`；overspeed mute 由单测覆盖，但 demo WAV 本身没有展示超速静音段。
- 结论：该原型可行，适合作为 S8 第一版离线听感/参数基线；还不是最终 PRD 声浪算法，下一步应根据实际听感调参，再授权移植到 `components/audio`。

---

# 2026-07-11 MATLAB / Simulink AI 工具接入

> 状态: 已完成；需新开 Codex 会话激活 MCP 工具

## 计划清单

- [x] 读取本地 MATLAB/Simulink AI 自动化参考笔记并核对官方仓库。
- [x] 确定最小官方组合：MATLAB Agentic Toolkit + Simulink Agentic Toolkit。
- [x] 确认当前 Codex 会话没有 MATLAB/Simulink MCP 工具，且本机未发现 MATLAB 命令。
- [x] 将两套官方工具包安装到 `E:\AI_Tools\Codex\data`：MATLAB `2026.07.02`、Simulink `2026.07.08`。
- [x] 在 MATLAB R2026a 中运行官方安装器，配置 Codex 全局 MCP 和 skills。
- [x] 新开 Codex 会话后验证 MATLAB 版本、已安装工具箱与 MATLAB 执行。
- [x] 按 `setup-custom-libraries` 无自定义库分支写入 `.satk/reuse-libraries.json`。
- [x] 创建最小 Simulink 模型，并用 `model_read` 与 `model_check` 完成结构验收。

## 选择边界

- 不单独安装 MATLAB MCP Server：MATLAB Agentic Toolkit 会安装并配置官方 MATLAB MCP Core Server。
- 不安装第三方 `wzyn20051216/matlab-agent-skills` 作为主工具链，避免与官方 skills、MCP 配置重复。
- 不安装 Agent Skills Playground；它是示例项目，不是日常工程依赖。
- 不额外寻找独立的“Simulink Skills”；Simulink Agentic Toolkit 已提供建模、查询、编辑和测试所需的 MCP 工具与技能。

## Review

- 官方 MATLAB Agentic Toolkit 支持 Codex，负责 MATLAB 脚本执行、测试、静态检查、工具箱识别和通用工程技能。
- 官方 Simulink Agentic Toolkit 需要 MATLAB R2023a+ 与 Simulink，覆盖 `.slx` 建模、仿真、诊断与测试，符合 Tesla Speed 后续声浪和嵌入式建模路线。
- R2026a 官方安装器已完成：MATLAB MCP Server Toolbox、MATLAB Agentic Toolkit `2026.07.02`、Simulink Agentic Toolkit `2026.07.08` 已安装，Codex 已配置为全局现有会话模式。
- `satk_initialize` 已在当前 MATLAB 会话运行并通过安装检查：Simulink、7 个工具入口、MCP binary 和连接器端口 `31516` 均显示 PASS。
- 当前 Codex 会话在配置前创建，无法热加载新的 MCP namespace；新开会话后必须实际调用 `detect_matlab_toolboxes` / `evaluate_matlab_code`，并运行一个最小 Simulink 模型后才可关闭最终验证项。
- 2026-07-11 验收会话已真实调用 MCP：MATLAB R2026a、Simulink license=1、端口 31516 与 7 个 Simulink 专用入口均已通过。无自定义库确认后，API 已生成 `.satk/reuse-libraries.json`（`libraries=[]`, `confirmed_none=true`）；按工具包 API 的无库格式，块策略和知识索引不需要创建。
- 最小模型验收已闭环：`mcp_minimal_acceptance.slx` 已保存到项目根目录（38,993 bytes）。专用 `model_edit` 创建 `InputAmplitude(Constant) -> Kp_SpeedFactor(Gain) -> OutputScope(Scope)`；`model_read` 回读了 3 个块和 2 条连接；`model_check(checks=["all"])` 返回 `status: healthy`，无未连接端口、悬空线或 Stateflow lint 问题。

---

# 2026-07-11 Codex 控制 MATLAB / Simulink 分享文档

> 状态: 已完成

## 计划清单

- [x] 汇总本机已验证的 MATLAB MCP、Simulink 工具、skills 与最小模型验收信息。
- [x] 编写可独立转发的 Obsidian 文档：官方地址、安装、配置、初始化、验证、指令示例与排障。
- [x] 校对命令、配置路径、MCP 地址解释和敏感信息边界。

## Review

- 已新增 Obsidian 分享文档：`2026-07-11-Codex控制MATLAB与Simulink-MCP完整配置与验收.md`。
- 文档以本机 R2026a / Codex 验收为事实基础，明确区分 stdio MCP、MATLAB 本地连接器端口、全局配置与每次会话初始化。
- 完成 Markdown 围栏、关键配置字段、官方链接和敏感信息扫描；3 个官方 GitHub 地址可访问，文档不含 token 或其他 MCP 配置。

---

# 2026-07-11 Tesla Speed Obsidian 项目知识库本地对齐

> 状态: 进行中；以 `E:\Tesla_speed` 当前文件与可复核证据为准，不把历史计划当作当前事实

## 计划清单

- [x] 读取有效目录、`docs` 现行索引、当前 PRD、交接记录、工程入口与任务账本，区分现行资料、历史资料和参考仓库。
- [x] 使用受限 child-claude 对文档树做只读交叉盘点；由 Codex 审核结论并回读关键原文。
- [x] 重写 Obsidian `tesla-speed` 项目概览、总体计划、当前进度、关键决策、工作流与参考索引，统一 UTF-8 编码和本地链接。
- [x] 校验知识库文件编码、链接目标、状态/风险/下一步与仓库现状一致，并记录 Review。

## Review

- 有效工程范围已区分：`prj` 是当前 ESP-IDF 固件仓库，`hardware_kicad` 是当前硬件 v1 原理图真源；根目录旧 EasyEDA/AD 资料、BOM 审计和第三方 `docs\reference` 均不作为当前实现完成证明。
- 当前软件状态已按源码、`prj\README.md`、`PLAN.md`、活跃 roadmap/backlog 与 2026-07-08 固件记录交叉核对：S0-S7 代码 baseline 存在，S7.6 仍卡在 IRAM 1 byte 余量和硬件验收。
- `prj` 当前存在未提交的 README、路线图、backlog、`sdkconfig.defaults` 与 `tools/` 改动；本轮未重跑 ESP-IDF 门禁，因此知识库明确标为“历史验证记录，不覆盖当前工作树”。
- child-claude 只读文档盘点按 `Read,Glob,Grep` 启动，但约 124 秒未返回；按 skill 规则丢弃其结果且不重试，最终由 Codex 直接读取本地证据完成。
- 已更新 `E:\AI_Tools\Obsidian\data\notes-personal\codex_memory\03-项目记忆\tesla-speed` 下 5 个 Tesla Speed 页面；6 个 Markdown 文件均通过严格 UTF-8 解码，10 个索引路径均存在。
# 2026-07-11 MATLAB 经典车型声浪仿真（第一批）

> 状态: 执行中；第一批范围为 Hellcat、R35 GT-R、W204 C63

## 执行清单

- [x] 核验并下载许可证清晰、算法可复用的最新声浪参考工程。
- [x] 更新 `docs/reference/index.md`，记录来源、许可证、用途和禁止直接复用边界。
- [x] 形成统一混合声浪模型：发动机阶次、RPM/负载音色、增压器、回火与换挡事件层。
- [x] 在 MATLAB 中实现 Hellcat、R35 GT-R、W204 C63 三个参数档案和标准工况。
- [x] 生成每款车型 WAV、波形/频谱图、参数表和可重复运行入口。
- [x] 使用 Child Claude 做窄范围资料提炼或独立审查，由 Codex 复核结论。
- [x] 运行 MATLAB 仿真与自动验收，记录听感调参入口和后续五款车型扩展方式。

## Review

- 新增参考快照：`engine-sim-main` 固定到 `85f7c3b`（MIT）；`Granular-Synthesis-for-Engine-Audio-main` 固定到 `d27967b`（无许可证，仅供研究）。下载先落到 `E:\Claude_allow\Download`，再以不含 `.git` 的源码快照归档。
- `docs/reference/index.md` 已从乱码正文重写为 UTF-8 索引，明确可复用、仅供研究和音频素材禁止直接分发边界。
- MATLAB 公共模型位于 `prj/tools/sound_sim/matlab`，三个车型共享连续发动机层、独立增压层、换挡层和收油回火事件层，仅参数档案不同。
- 批量输出位于 `prj/build/sound-sim/matlab-classics`：每款车均有 48 kHz/mono/16-bit/16 s WAV、100 Hz trace CSV、参数 JSON 和分析 PNG。
- 产物检查：Hellcat RMS `0.2907`、21 次回火；GT-R RMS `0.2564`、27 次回火；C63 RMS `0.2900`、15 次回火；三者 peak 均为 `0.96`。
- MATLAB Code Analyzer：5 个新增 `.m` 文件均为 0 issue。MATLAB Unit Test：`3 Passed, 0 Failed, 0 Incomplete`。
- Child Claude 的本轮 4 文件审查在 60 秒预算内超时，按 skill 规则未重试、未采用不完整结果；此前窄范围 ESP32 参考分析成功并已由 Codex 复核。
- 当前完成的是可重复的第一版声学仿真，不代表品牌听感已经验收；下一步由 Jovi 试听三份 WAV，并按回火密度、低频厚度、增压器存在感和高转尖锐度反馈后调参。
# 2026-07-11 三车型真实参考校准与声浪重构

> 状态: 执行中；推翻第一版共享回火音色，保留可复用的文件接口和自动验收

## 执行清单

- [x] 为 Hellcat、R35 GT-R、W204 C63 分别锁定原厂加速和明确改装回火参考。
- [x] 下载参考音频到 `E:\Claude_allow\Download`，不把版权音频纳入仓库或交付物。
- [x] 用 MATLAB 提取波形、STFT/阶次特征、回火包络和换挡切火时序。
- [x] 建立 0 起步、1-2-3 挡换挡的车辆速度/RPM/负载状态机。
- [x] 为三款车实现不同的点火/排气共振、增压器、换挡和回火模型。
- [x] 生成第二版 WAV、分析图和车型差异度报告。
- [x] 运行 MATLAB 静态检查、单元测试和产物验收，等待 Jovi 试听。

## Review

- 真实音频：6 条公开参考仅下载到 `E:\Claude_allow\Download\tesla-sound-research`，覆盖三款车的加速和明确状态的降挡/改装回火；原始音频未进入仓库或合成产物。
- MATLAB 参考分析：`analyze_reference_audio.m` 输出 6 张 STFT/瞬态图、`reference_summary.csv` 和 `reference_events.csv`，用于频带与事件结构校准。
- GitHub 参数证据：新增 `Engine-Sim-Engines-main` 快照 `f95625e`（无许可证，仅供研究）。VR38 使用精确配置；M156 使用精确配置；Hellcat 点火/排气结构以第三代 HEMI 6.4 近似并单独加入机械增压层。
- 声音核心：按 720 度工作循环生成逐缸脉冲，按车型点火顺序路由到左右缸组，再经过不同排气共振器。三款回火分别为 `low_boom`、`metallic_crackle`、`amg_bang`。
- 工况：从 `0 km/h` 起步，使用各车型真实前三挡与终传比，完成两次升挡和 RPM 回落；三挡红线速度约 Hellcat `147`、GT-R `156`、C63 `166 km/h`。
- 第二版输出：`prj/build/sound-sim/matlab-classics-v2`，每款含完整 WAV、回火 solo、增压/进气 solo、trace CSV、JSON 和分析 PNG，并有 `backfire_feature_comparison.csv`。
- 频带校准：Hellcat 生成回火 `20-250 Hz` 占比 `0.924`（参考 `0.943`）；GT-R `250-1000 Hz` 占比 `0.952`（参考 `0.795`）；C63 `250-1000 Hz` 占比 `0.816`（参考 `0.703`）。受录音设备、风噪和排气改装影响，仅作为校准约束，不宣称录音重建。
- 验证：6 个新增/修改 MATLAB 文件 Code Analyzer 均为 0 issue；MATLAB Unit Test `4 Passed, 0 Failed, 0 Incomplete`；9 个 WAV 均为 mono、16-bit、48 kHz、18 秒且非静音。
- Child Claude：本轮窄范围 Engine Sim 配置分析在启动器清理子进程时失败，未重试、未采用残缺结果；Codex 已直接按文件字段复核。
- 当前边界：结构、频带和车型差异度已自动验收；是否足够贴近真实车辆仍必须由 Jovi 试听主 WAV 和三份回火 solo 后确认。
# 2026-07-11 三车型 V3 真实回火反演与换挡优化

> 状态: 执行中；目标是用真实事件派生参数替代手工回火模板

## 执行清单

- [x] 搜索并下载每款车更干净的近排气口回火、降挡和换挡参考。
- [x] 自动检测后人工复核真实回火事件，排除说话、关门、风噪和剪辑点。
- [x] 用 MATLAB 反演每款车的包络、频谱残差、共振峰、cluster 间隔和短 FIR。
- [x] 将派生校准参数写入可追溯 JSON，不保存或分发原始音频片段。
- [x] 重构三款车型专用回火生成器，使其消费校准参数而非手工固定音色。
- [x] 将线性换挡改为 ZF 8HP、GR6 DCT、AMG MCT 三种独立换挡状态曲线。
- [x] 生成 V3 主 WAV、回火 solo、换挡 solo、分析图和 V2/V3 对照数据。
- [x] 运行 MATLAB 静态检查、单元测试、产物检查并等待 Jovi 试听。

## Review

- 新增 4 条近排气口参考音频，连同原有 6 条音频仅保存在 `E:\Claude_allow\Download\tesla-sound-research`；原始录音未进入仓库或合成结果。
- `calibrate_backfire_references.m` 使用局部背景扣除、6 dB 事件对比度门限、车型频带包络和分离峰检测，输出 `jovi.backfire_calibration.v1` JSON；最终运行无警告。
- 派生差异：Hellcat `119.15 ms / 5` 连爆、GT-R `6.79 ms / 5` 连爆、C63 `2.26 ms / 8` 连爆；三者的 65 tap FIR 和五个主要共振峰也各不相同。
- 合成器已删除三套手工固定回火模板，改为消费派生 FIR、共振峰、attack/decay 和 cluster 间隔；仍保留车型独立触发与非线性失真方式。
- 换挡采用独立状态曲线：ZF `25/45/90 ms, min 0.10`，GR6 DCT `8/15/30 ms, min 0.45`，AMG MCT `15/50/70 ms, min 0.05`；RPM 回落改为半余弦过渡。
- V3 输出位于 `prj/build/sound-sim/matlab-classics-v3`，共 12 个 48 kHz/mono/16-bit/18 s WAV，包含主轨、回火、进气/增压和换挡 solo；所有轨道非静音。
- V2/V3 三个主 WAV 的 SHA-256 均不同；`v2_v3_backfire_comparison.csv` 保存数值对照，V2 产物未覆盖。
- MATLAB Code Analyzer：6 个文件均为 0 issue；MATLAB Unit Test：`5 Passed, 0 Failed, 0 Incomplete`。
- `docs/reference/index.md` 已恢复为严格 UTF-8，并补齐本轮参考来源、用途和版权边界。
- 自动验收只能证明结构、差异和信号有效；车型贴近程度仍以 Jovi 对主轨、回火 solo 和换挡 solo 的试听为最终判据。
# 2026-07-11 八车型 V4 动力学换挡、非平稳回火与可调 Simulink

> 状态: 执行中；目标是修正 V3 听感问题并完成 8 车型统一可调基线

## 执行清单

- [x] 定位 V3 中段嘶哑、C63 噪声和换挡“呲声”的具体图层与时间段。
- [x] 重构换挡：由主轨扭矩、RPM、燃烧脉冲和重新接合产生顿挫，弱化独立音效层。
- [x] 将回火扩展为升挡、收油减速和持续 burble 三类非平稳事件。
- [x] 核对 Supra、RX-7、LFA、Ferrari 458、Aventador 的发动机、点火/转子、缸组和传动参数。
- [x] 实现 Hellcat、GT-R、C63、Supra、RX-7、LFA、458、Aventador 八个档案。
- [x] 生成八车型 V4 主轨、回火 solo、换挡观察轨、trace、JSON 和分析图。
- [x] 建立可由用户打开并修改参数的 MATLAB 调音入口与 Simulink harness。
- [x] 更新工程内经验/调参文档和 Obsidian 项目知识库。
- [x] 完成静态检查、单元测试、音频属性、分层噪声和产物验收。

## Review

- V3 C63 的沙哑来源是自然吸气层持续宽带随机 roar；V4 改为 RPM 驱动阶次谐波，随机纹理仅由 `texture_noise_gain` 低电平混入。C63 6–12 秒中段频谱平坦度由 `0.00911` 降至接近 `0`。
- 换挡工况改为 `1→2→3→2→1`。C63 升挡主轨增益 `0.28→1.12`，降挡 `0.55→1.17`；独立 shift detail 在换挡窗口仅占主轨 RMS 约 `0.01%–0.03%`，不再承担顿挫主体。
- 回火事件区分 `upshift`、`downshift`、`overrun`。持续 overrun 随时间降低强度、拉长间隔，并逐次改变音高、扫频、相位和短延迟。
- 新增并复核 2JZ-GTE、13B-REW、1LR-GUE、F136 F、L539 五套发动机/传动参数；八车型均有不同点火/转子事件、共振、进气、变速箱和回火风格。
- 新增五条真实加速参考，只保存在 `E:\Claude_allow\Download\tesla-sound-research`；八车型反演 JSON 共包含 8 个独立 65 tap FIR 与共振参数档案。
- V4 输出位于 `prj/build/sound-sim/matlab-classics-v4`：32 个 WAV 均为 mono、16-bit、48 kHz、22 秒且非静音；八个主轨 SHA-256 均不同。
- MATLAB Code Analyzer 10 个文件合计 0 issue；单元测试 `5 Passed`。单车型调音入口已真实生成 C63 tuning preview。
- Simulink 模型 `classic_sound_tuner.slx` 已由专用工具创建并回读，11 个块、10 条预期连接，`model_check` 为 `healthy`；真实仿真输出 `5163.27 RPM / 0.650 load / gear 2`。
- 工程内新增两份 UTF-8 调试文档，Obsidian 新增 `06-MATLAB声浪仿真与调参经验.md`；三份文档均严格 UTF-8 且无替换字符。
- Child Claude 的五文件摘录在 90 秒超时，按 skill 规则未重试；随后两个只读 explorer 分担五车型参数提取，由 Codex 复核并落地。
- 自动门禁已经完成；八车型是否达到目标真实感仍需 Jovi 逐车试听 V4 主轨与回火轨后确认。
# 2026-07-11 发动机布局同工况试听对比

> 状态: 执行中；隔离换挡和回火，直接比较 V8、直六涡轮、V10、V12 的基础音色

## 执行清单

- [x] 在线核对四类发动机的经典代表车型，并复核本地 Engine Sim 参数。
- [x] 新增 C6 Corvette LS3 美式自然吸气 V8 档案。
- [x] 建立统一归一化 RPM/油门拉转工况，关闭回火与换挡干扰。
- [x] 生成四条独立试听、纯排气层和连续对比试听带。
- [x] 输出脉冲频率、频谱重心和高低频占比对照表。
- [x] 运行 MATLAB 静态检查、单元测试和 WAV 验收。

## Review

- 新增 `corvette_ls3`：LS3 十字曲轴 V8，点火 `1-8-7-2-6-5-4-3`，前三挡 `2.97/2.07/1.43`，终传 `3.42`，红线 `6500 rpm`。
- 对比工况统一为 14 秒归一化拉转，并关闭换挡与回火；避免车辆加速度、齿比和事件层掩盖发动机布局差异。
- 输出 4 条 demo、4 条 exhaust solo、4 条 induction solo 和 1 条 59.2 秒连续试听带，共 13 个 WAV。
- 数值差异：LS3 V8 频谱重心 `192 Hz`、低频占比 `67.6%`；2JZ `516 Hz`；LFA V10 `592 Hz`；Aventador V12 最大燃烧事件频率 `768 Hz`。
- 13 个 WAV 均为 mono、16-bit、48 kHz 且非静音；MATLAB Code Analyzer 4 个相关文件 0 issue，单元测试 `5 Passed`。
- Child Claude 未触发：任务是小范围参数落地与本地渲染，直接执行成本低于派发和复核成本。

# 2026-07-11 MATLAB R2026a 启动崩溃修复

## 执行清单

- [x] 收集崩溃转储、安装日志和安全启动结果。
- [x] 备份并重置 R2026a 用户偏好与工具箱缓存。
- [x] 验证 MATLAB 桌面启动及新增物理建模工具箱可见性。

## Review

- MPM 确认 46 个产品已安装，新增的 7 个物理建模产品与自动依赖 Symbolic Math Toolbox 均在清单中。
- MATLAB 在清空用户偏好、忽略用户 Java、软件 OpenGL、单计算线程等启动条件下仍于 GTP 线程访问冲突而退出；兼容模式未开启。
- 结论：停止对现有安装做增量修补，改走精简产品集的干净重装；保留偏好备份目录以便需要时恢复。

# 2026-07-11 重装后 MATLAB MCP 与声浪仿真恢复

> 状态: 已完成；以当前 MATLAB 桌面会话完成 MCP 重连，并重新生成既有八车型 V4 仿真产物

## 执行清单

- [x] 核对 Codex MCP 配置、MATLAB MCP Server Toolbox 与当前 MATLAB 会话。
- [x] 刷新 existing-session 会话凭据并以真实 MCP 工具探测 R2026a 工具箱。
- [x] 运行 MATLAB 声浪单元测试与八车型 V4 批处理。
- [x] 验收新生成 WAV、trace、参数文件及 Simulink 调音模型。
- [x] 记录本轮恢复结果与剩余边界。

## Review

- Codex MCP 配置保持在 `C:\\Users\\Admin\\.codex\\config.toml`：existing session、Simulink extension、600 秒超时与 `WINDIR` 均已启用。
- 当前 MATLAB 的 `sessionDetails.json` 曾残留失效 PID `46900`；重新执行 `shareMATLABSession` 后已更新为当前连接器 PID `29752` 和端口 `31516`，随后 `detect_matlab_toolboxes` 真实返回 R2026a 及所需工具箱。
- 重装后 Simulink extension 默认不在 MATLAB path；运行 `satk_initialize` 后其 7 个入口均通过安装检查。新增 `C:\\Users\\Admin\\Documents\\MATLAB\\startup.m`，后续新 MATLAB 会话会自动初始化该工具包。
- MATLAB 单元测试：`5 Passed, 0 Failed, 0 Incomplete`（4.98 秒）。
- 八车型 V4 已在 23:32 重新生成：32 个 WAV，全部为 mono / 16-bit / 48 kHz / 22 s，另有每车 trace、JSON、分析图及回火特征对照。八个主轨 SHA-256 均不同。
- 重新生成四类布局对比：美式 NA V8、直六涡轮、V10、V12；其结果位于 `prj\\build\\sound-sim\\engine-layout-comparison`。
- Simulink `classic_sound_tuner.slx`：`model_read` 回读 11 个块和全部 9 条数据连接，`model_check(["all"])` 为 `healthy`；真实仿真最终值为 `5163.27 RPM / 0.650 load / gear 2`。
- 边界：本轮完成的是重新安装后的配置、可运行性与合成产物验收。品牌听感仍应由 Jovi 试听主轨、回火 solo、换挡 solo 后决定下一轮参数优化。

# 2026-07-11 物理声学发动机建模升级调研

> 状态: 已完成；已如实核对 V4 覆盖边界，并形成基于 MATLAB/Simulink 的物理声学与自动拟合升级路线

## 执行清单

- [x] 审核 V4 与 Simulink harness 实际覆盖的模型层级。
- [x] 搜索 MathWorks、公开研究和开源工程的发动机燃烧、排气波动、传递函数及音频拟合能力。
- [x] 将可用的本地工具箱、缺少的数据和每一阶段的 Simulink 结构对应起来。
- [x] 给出不改代码的参数扩展提案，以及高频机械纹理/高频回火的验证方法。
- [x] 列出所有当前可独立试听的生成音频。

## Review

- V4 实际是确定性的脉冲列、两缸组延迟、固定二阶共振器、进气/增压层、换挡增益曲线和从参考录音派生的回火 FIR/模态；不是气缸 blowdown 或管道压力波模型。`classic_sound_tuner.slx` 仅将速度、齿比、油门、档位和换挡增益映射到 RPM/有效负载/档位，故可调参数很少。
- 当前 V4 没有使用 Simscape、Simscape Driveline、Powertrain Blockset、System Identification、Simulink Design Optimization、Model-Based Calibration 或 Audio Toolbox 参与声学求解；它实际使用的是基础 MATLAB、Signal Processing 例程和核心 Simulink harness。
- 真实可用的本地工具箱路径已验证：Simscape Driveline 的 `SI Combustion Cylinder` / `Spark Ignition Engine`，Simulink Design Optimization 的 `sdo.optimize`，DSP 的 `dsp.TransferFunctionEstimator`，Audio Toolbox 的 `audioFeatureExtractor`，Signal Processing 的 `orderspectrum`。Powertrain Blockset 的 SI Controller 可从扭矩/RPM生成节气门、喷油脉宽、点火提前角、废气门和凸轮相位指令。
- 提议的 V5 分层：燃烧/ECU状态（扭矩、点火、AFR、DFCO、排温）→ 排气压力脉冲 → 低阶热声学数字波导（歧管、汇流器、催化器、消声器、尾管的反射和温度相位）→ 车外/座舱/扬声器传递函数 → 与实录对齐的多目标参数估计。对真实气体波动的工程级 1D 基准，GT-SUITE 或 Realis WAVE 仍是独立的商业工具，不能由现有 MATLAB 工具箱替代性宣称。
- 高频建议保留但须可校准：以 3--10 kHz 的 RPM/负载门控机械纹理和 2--12 kHz 的回火 crack 支路实现，并以参考录音的谱平坦度、谱通量、瞬态起音和分频带误差作为验收，不采用恒定白噪声。
- 当前独立试听清单：V4 八车每车主轨、回火、进气/增压和换挡四轨共 32 个文件；布局对比 13 个文件，详见本轮回复。

# 2026-07-11 V6 多速率物理声学数字孪生可行性验证

> 状态: 已完成；已验证架构、工具和数据边界，未修改 V4/V5 声浪代码

## 执行清单

- [x] 用当前 MATLAB MCP 验证 V6 所需燃烧、气体、音频延迟、传递函数、阶次分析和参数优化能力。
- [x] 在线复核 MathWorks 官方能力、发动机排气波动研究和可参考开源实现。
- [x] 使用 Child Claude 对现有五个窄范围文件做独立参数面审计，由 Codex 复核结论。
- [x] 定义 V5 与 V6 的边界、模型分层、参数数量、数据来源和验收指标。
- [x] 复核当前全部试听音频路径并给出独立试听入口。

## Review

- 当前 R2026a 已实机解析并实例化 `dsp.VariableFractionalDelay`、`dsp.TransferFunctionEstimator` 和 `audioFeatureExtractor`；同时验证 `orderspectrum`、`rpmordermap`、`ordertrack`、`greyest`、`nlgreyest`、`sdo.optimize`、`surrogateopt`、`parsim`、`impzest`、`sweeptone`、`acousticRoomResponse` 与 `calibrateMicrophone` 可用。
- Simulink/Simscape 库已实机找到 `SI Combustion Cylinder`、`Spark Ignition Engine`、`Pipe (G)` 和 `SI Controller`。`sdo.optimize` 小型实算将测试参数从 `2.0` 收敛到约 `1.351`，证明参数优化不是仅有许可证入口。
- 温度传播探针：理想气体近似下 `300/600/900/1100 K` 对应声速约 `347/491/601/665 m/s`；同一管长的 96 kHz 延迟随温度明显弯曲。Farrow 分数延迟对象已对 `10.4` sample 延迟完成非零脉冲计算。
- V6 推荐为多速率混合模型：曲轴角/ECU/热力学慢层 → 排气门 blowdown 事件 → 96 kHz 温度相关数字波导与多端口反射网络 → 机械高频和回火 crack → 车外/座舱/扬声器 IR → 多工况自动拟合。Simscape Gas 用于状态和低频动态，音频级波传播由可验证的数字波导承担。
- 参数规模建议为约 `70--120` 个有来源的标量/查表项加若干 FIR/IR 数组，但每次自动拟合只释放 `15--30` 个高敏感参数；其余由官方规格、实测几何或 ECU/台架数据固定，避免不可辨识。
- V6 相比 V5 新增闭环排气背压、跨 RPM/负载的温度与损耗表、多工况联合拟合、参数边界/置信度和可部署降阶模型。V5 尚未实现，因此必须先做一辆车的 V5 物理链路验收，再扩展 V6，不能把方案版本当作已生成音频。
- 主线 V6 不需要新增 MATLAB 产品。可选 3D 座舱有限元需要当前未安装的 PDE Toolbox；可选可微神经声浪需要当前未安装的 Deep Learning Toolbox。优先实测车内/扬声器 IR 比先做 3D 有限元更直接。
- Child Claude 窄范围任务在 30.7 秒后返回 `Success=false`、无正文和 stderr；按 skill 规则未重试、未采用结果，全部结论由 Codex 通过本地代码、MATLAB MCP 和官方资料独立复核。
- 音频复核：V4 目录现有 32 个 WAV，布局对比目录现有 13 个 WAV；当前没有 V5/V6 音频产物。

# 2026-07-12 C63 V6 物理声学垂直切片

> 状态: 已完成 C63 V6.0；其余七车等待 C63 听感确认后迁移

## 执行清单

- [x] 冻结 V4，并验证原有 MATLAB 单元测试通过。
- [x] 新建 96 kHz C63 V6 profile、控制率动力/ECU/热状态与左右排气波导。
- [x] 建立 DFCO、残余燃油、排温门控的回火与 RPM/负载门控机械纹理。
- [x] 创建并运行八子系统 `engine_sound_v6.slx`，通过结构检查。
- [x] 用本地 C63 回火参考进行可追溯的 63 次受限自动拟合。
- [x] 生成主轨、独立 stem、trace、参数、候选表和分析图。
- [x] 运行 V6 单元测试、静态分析、WAV 属性与模型仿真验收。

## Review

- V6 代码位于 `prj/tools/sound_sim/matlab/v6`；V4 文件和 `matlab-classics-v4` 产物未修改。
- `iteration_03_afterfire_autofit_wideband` 为当前 C63 试听候选：96 kHz/24-bit 主母版、48 kHz/16-bit 试听版，以及排气、回火、机械、座舱和扬声器 stem。
- V6 由 M156 的 6208 cc、102.2 mm bore、94.6 mm stroke、11.3:1 compression、点火顺序和传动比为固定锚点；几何/反射/压力值均显式保存为识别初值。
- 回火拟合使用引用音频的派生特征，不复制任何原始音频。参考重心 `562 Hz`，V6 `641 Hz`；参考 250--1000 Hz 占比 `70.8%`，V6 `75.8%`。
- MATLAB Code Analyzer：V6 10 个 `.m` 文件均为 0 issue；V6 单元测试 `5 Passed`；原 V4 单元测试 `5 Passed`。
- Simulink V6：8 个子系统、`model_check(["all"]) = healthy`、0.05 s 实际仿真输出 51 个样本。
- Simscape Gas：新增 `v6_exhaust_thermal_plant.slx`，包含 900 K/250 kPa 入口、动态且带惯性的 1.15 m `Pipe (G)`、350 K/101325 Pa 出口和热参考；`model_check` healthy，真实求解到 0.100 s。
- Child Claude：按 skill 评估，V6 核心实现与父任务的模型/验收语境紧耦合，派发再审查的成本高于直接完成，故本轮未委派写代码；父代理完成全部实现和审核。
- 边界：V6 是低阶热声学数字波导，不是经台架数据验证的完整 1D CFD/GT-SUITE 模型；Simscape Gas 目前独立校准低频热状态，Powertrain Blockset 尚未闭环耦合；下一步需要 Jovi 试听 C63 的主轨、回火 stem 和换挡窗口后再迁移其他七车。

# 2026-07-12 C63 V6.1 听感回归修复与多车型隔离

> 状态: 执行中；先保存 V6.0 Git 快照，再恢复 V4 的加速与回火优势，同时建立车型独立 Simulink 参数边界。

## 执行清单

- [x] 提交 V6.0、V4 和当前工程文档的修复前 Git 快照。
- [x] 将共用 V6 求解器与 C63 专属 profile、校准、场景和测试分离。
- [x] 让回火进入排气波导，并恢复 V4 的宽带 FIR、非平稳事件序列和换挡类型差异。
- [x] 修复扭矩/负载驱动、换挡主轨动态和分层响度管理。
- [x] 增加 V4 加速响度、回火频带、事件持续时间与车型隔离回归测试。
- [x] 生成 C63 V6.1 主轨和分轨，由 Codex 独立审核全部差异。
- [x] 运行 MATLAB 单元测试、静态分析、Simulink 检查和音频指标验收。

## Review

- 修复前 Git 快照为 `bafd4f7`；MATLAB/Simulink 缓存已加入忽略规则，未纳入提交。
- Child Claude 在 60.2 秒后返回 `Success=false` 且没有文件改动；Codex 未重试，直接完成实现并审核。
- 回火使用既有 C63 派生 FIR/模态，并通过与燃烧脉冲相同的温度相关排气网络；升挡、降挡、滑行回火已区分。
- 主排气由 `torque_nm`、负载、EVO 压力、气门面积和排温共同驱动；回火不再压低加速主轨。
- 完整 demo 加速段 RMS `0.428`、峰值 `0.874`、归一化增益 `1.000`；V6.0 加速 RMS 为 `0.086`。
- 完整 demo 共 72 个回火事件；tip-out 单簇 35 个事件、跨度 `1.214 s`。
- C63 独立 profile 位于 `matlab/v6/vehicles/c63_w204`；独立模型和 `.sldd` 位于 `simulink/v6/vehicles/c63_w204`。
- MATLAB 测试：V4 `5/5`、V6.1 `8/8`；Code Analyzer `0 issue`；独立 Simulink `model_check(["all"]) = healthy`。
- 试听产物位于 `prj/build/sound-sim/matlab-classics-v6/c63_w204/iteration_04_v6_1_reviewed`。

# 2026-07-12 C63 V6.2 多录音撕裂感拟合

> 状态: 已完成两套试听候选；V6.1 回火保持不变。

## 执行清单

- [x] 验证 Child Claude 受限写入链路并保留结构化结果。
- [x] 下载并标注六条 C63 加速/回火参考，原始音轨仅保存在允许目录。
- [x] 提取 W204 加速与回火的频带、谱平坦度和谱通量中位目标。
- [x] 新增脉冲同步、RPM/负载门控的 combustion rasp 层。
- [x] 生成平衡版与强撕裂版主轨、回火、排气、机械和 rasp 分轨。
- [x] 更新 C63 独立 `.sldd`，运行 MATLAB、Simulink 和 V4 回归验收。
- [x] 更新参考索引并提交代码。

## Review

- Child Claude 简单写入验证：`Success=true`、`TimedOut=false`、`Turns=2`、stderr 为空，指定文件内容正确。
- Child Claude 独立函数任务：`Success=false`、`TimedOut=true`、`Result/Stderr=child Claude timed out after 120 seconds`、`RawStderr` 为空，未留下文件；Codex 未重试并直接实现。
- W204 五条参考的加速中位目标：1--4 kHz `11.2%`、4--12 kHz `1.37%`、谱通量 `0.0645`；W205 C63s 仅作对照，不进入聚合目标。
- V6.2 rasp 来自排气非线性残差、带限低电平纹理和脉冲同步抖动；低 RPM/低负载强门控，不是持续白噪声。
- 平衡版加速 1--4 kHz `4.16%`、4--12 kHz `0.113%`；强版为 `11.52%`、`0.481%`。
- V6.1、V6.2 平衡版和强版回火 stem 均为 RMS `0.0291`、peak `0.4538`，确认回火没有被本轮改动削弱。
- MATLAB 测试：V4 `5/5`、V6.2 `9/9`；Code Analyzer `0 issue`；独立 C63 Simulink `healthy`。
- 试听目录：`iteration_05_v6_2_rasp_balanced` 与 `iteration_06_v6_2_rasp_aggressive`。

# 2026-07-12 C63 断续主声与 Hellcat 双车型仿真

> 状态: 已完成；“撕裂感”已改为点火脉冲本身的循环间不连续，并完成独立 Hellcat V6 仿真。

## 执行清单

- [x] 检索发动机排气幅度调制、循环间燃烧差异、颗粒合成和物理排气脉冲资料。
- [x] 扩展真实录音指标：调制深度、调制峰值、脉冲间幅值离散度和谐波连续性。
- [x] 重构 C63 主排气事件，使十字曲轴缸组脉冲与循环间燃烧差异产生断续撕裂。
- [x] 降低独立电子纹理占比，生成 C63 新候选并与真实录音波形对比。
- [x] 下载并标注 Hellcat 原厂、降挡、近场和改装回火参考。
- [x] 建立 Hellcat 独立 profile、场景、Simulink 模型和 `.sldd`。
- [x] 生成两车型主轨与分轨，运行 MATLAB、Simulink、真实录音指标和 Git 验收。

## Review

- C63 主排气新增逐点火事件的相关强度起伏、偶发缺口、缸间增益和曲轴角时序抖动；独立 rasp 纹理已降至低电平，回火事件和回火 stem 与 V6.1 保持逐样本一致。
- C63 真实 W204 聚合目标的脉冲幅值 CV 为 `0.505`，新候选为 `0.304`；模型已形成断续感但仍比实录整齐。Hellcat 原厂参考为 `0.559`，模型为 `0.355`，同样保留为下一轮听感拟合边界。
- Hellcat 使用独立的 6.166 L V8、点火顺序、ZF 8HP 齿比、低频排气模态、机械增压器阶次、换挡与低沉回火参数；没有复用 C63 的车型参数文件。
- 两车独立模型和 `.sldd` 均通过 `model_check(["all"]) = healthy`；MATLAB 测试为 C63 `11/11`、Hellcat `3/3`、V4 `5/5`，本轮 14 个 `.m` 文件 Code Analyzer 均为 0 issue。
- 两条主试听轨均为 mono、48 kHz、16-bit、22 s；同时保留 96 kHz 主母版和排气、回火、机械、进气、rasp、座舱、扬声器分轨。
- Child Claude 按新规则仅审计 5 个文件，90 s 后结构化返回 `Success=false`、`TimedOut=true`，stdout/stderr 为 0 字节且无清理异常；父代理据此确认启动器修复有效，并独立完成算法审核。
- 研究与调参经验已写入工程文档和 Obsidian；原始网络录音仅存放在允许下载目录，不进入 Git，也不复制进产品音频。

# 2026-07-12 S12 全物理 Simulink 1D 发动机与排气声学模型

> 状态: 执行中。停止在 V6 低阶波导上继续堆叠经验音色参数，先完成文献、参数和验证体系，再建设可检查的 Simulink/Simscape 物理模型。

## 研究与规格

- [x] 建立燃烧、缸压、排气门流量、1D 可压缩管流、歧管/催化器/消声器、辐射声学和发动机声音合成的论文证据矩阵。
- [x] 为 C63 M156 与 Hellcat 6.2 HEMI 建立参数来源表，逐项标记官方、论文、测量、识别或假设及置信度。
- [x] 定义缸压、质量流、管内压力、尾管声压、发动机阶次、频谱和真实录音的分层验收指标。
- [x] 审核 R2026a 已安装工具箱与可用 Simscape Gas/Powertrain/Audio/DSP 模块，明确自定义方程边界。
- [x] 输出模型架构、求解器、采样率、多速率接口和计算成本规格，评审后再开始结构建模。

## Simulink/Simscape 模型

- [ ] 建立逐缸四冲程曲轴角、Wiebe 放热、零维缸压与温度状态。
- [ ] 建立排气门升程/有效面积、可压缩孔口质量流与排气吹放压力脉冲。
- [ ] 建立左右缸组 1D 管段、汇流器、交叉管、催化器、消声器和尾管的面积/阻抗/反射网络。
- [ ] 建立温度相关声速、频率相关摩擦/热损耗、边界反射与尾管辐射声压。
- [ ] 闭环接入 Powertrain 扭矩、点火提前角、lambda、DFCO、换挡和离合器状态。
- [ ] 建立 C63 与 Hellcat 独立模型、数据字典、参数报告和初始化脚本。

### 当前实现进度

- [x] 建立 C63 单缸曲柄连杆容积与绝热压缩参考模型，完成 TDC/BDC 解析测试。
- [x] 将缸径、冲程、压缩比、连杆识别区间、参考压力和参考 gamma 保存为带证据说明的 `Simulink.Parameter`。
- [x] 在参考模型上加入闭缸质量、温度、第一定律、Wiebe 放热和 Woschni 换热动态状态。
- [x] 建立独立气门升程、有效帘幕面积、堵塞与亚临界可压缩阀口流量基准。
- [x] 新建耦合吹放模型，用 NASA 物种表和燃烧进度计算温度/组分相关 `cp/cv/R/gamma`。
- [x] 将正向阀口质量流和 `mdot*(h-u)=mdot*R*T` 闭环接入缸内质量与能量状态。
- [ ] 增加反向阀流与进气门交换，使用入口焓和缸内比内能处理反流能量。

## 拟合与交付

- [ ] 用公开参数、参考录音派生特征和可用实测数据进行多目标参数识别与敏感度分析。
- [ ] 生成启动、怠速、加速、换挡、收油、降挡和回火标准工况。
- [ ] 输出 96 kHz 主声压、分层信号、频谱/阶次图、参数来源报告和模型检查报告。
- [ ] 与 V4、V6、真实录音和 App 输出做 A/B 验收；未达到门槛不得替换当前候选。

## Review

- 研究阶段已建立核心论文矩阵、车型参数证据门禁和有限体积架构决策；不声称已读完所有付费全文。
- MATLAB MCP 现场确认 R2026a 具备 Simulink、Simscape/Fluids、Powertrain、Audio/DSP、System Identification、Optimization 与 Parallel Computing。
- M156 官方固定项已覆盖缸径、冲程、排量、压缩比和额定工况；Hellcat 官方固定项额外覆盖气门直径、最大升程及指定基准升程下的持续角。
- 连杆、凸轮事件角、阀流量系数和完整排气几何仍是待测/待识别项，已明确阻止 V6 经验值静默迁移。
- 绝热基准 `c63_cylinder_adiabatic_ref.slx` 已通过 MATLAB 行为测试、Code Analyzer 和结构检查；它只验证解析几何/压缩，第一定律由独立燃烧参考模型承载。
- 闭缸燃烧参考输出 17,223 点：峰值压力 `10.127 MPa @ 11.106 deg ATDC`、峰值温度 `3486.8 K`、放热 `2097.88 J`、正向壁面损失 `174.39 J`；高温提示常数 `cv` 仍需替换，不能作为已校准 M156 真值。
- 阀流基准在 `529 kPa` 上游得到堵塞流 `0.643469 kg/s`，在 `150 kPa` 上游得到亚临界流 `0.174970 kg/s`，两分支均与解析式在 `1e-8` 相对容差内一致。
- S12 目录回归 `3/3` 通过，三个测试文件 Code Analyzer 均为 `0 issue`，三套 Simulink 模型结构检查均为 `healthy`。
- 有效 Git 仓库 `E:\Tesla_speed\prj` 已跟踪 S12 目录并提交：`77e6466 feat: add S12 physical cylinder reference models`；Simulink 缓存保持 ignored。
- NASA 混合气表在 300--3500 K 覆盖 fresh-air `gamma 1.3985 -> 1.2796`、burned-gas `gamma 1.3703 -> 1.2369`；已燃气体 `R=290.645 J/(kg*K)`。
- 耦合吹放输出 26,667 点：峰值压力 `8.036 MPa @ 10.584 deg ATDC`、峰值温度 `2746.7 K`、EVO `0.578 MPa / 1644.7 K`、峰值排气质量流 `0.234553 kg/s`。
- 耦合模型积分排气质量与缸内状态质量损失相对误差 `2.28e-9`；S12 全目录回归提升为 `5/5`。
- S12 第二批已提交到有效仓库：`5b03460 feat: couple S12 cylinder blowdown physics`。
- Child Claude 已受限读取 4 份资料并创建 V1--V7 Obsidian 历史笔记；主 Agent审核后删除无证据的 V1--V3 细节，修正 V6 简化网络、V7 物性依赖和版本日期表述，并加入 `tesla/index.md`。
- 独立阀流基准已升级为 `Cd(lift)` 查表、双向堵塞/亚临界质量流和双向焓流，清除 MATLAB 函数缓存后新测试通过，模型结构 `healthy`。
- 首个 8 单元、0.48 m Simscape Gas primary 模型已完成结构和编译，但 5 ms 仿真运行超过 3 分钟未返回；当前仅保留 WIP，不纳入通过项或 Git 提交，需修正热边界/刚性后重新验收。
- S12 第三批已提交：`4d81977 feat: add bidirectional S12 valve flow`；该功能提交仅包含已验证的 README、阀流模型和测试，不混入 1D WIP。
- 1D WIP 随后按历史留根要求单独提交：`5654dc3 wip: checkpoint S12 primary pipe propagation`；传播测试位于 `s12/wip`，不会进入默认 `runtests('tests')`。
- [x] 修正 primary 管段初始压力单位 `MPa -> Pa`，并以 700 K 温度源替代绝对零度热参考。
- [x] 在出口储气罐前加入有限阻抗局部缩口，使出口压力波可测而非被理想大气边界钳零。
- [x] 5 ms 求解约 `4.9 s`；入口 `5.000 kPa`、出口 `3.078 kPa`、传播延迟 `0.891 ms`，传播专测通过。
- [x] 将传播测试纳入默认 S12 回归；S12 `6/6` 通过，新测试 Code Analyzer `0 issue`。
- [x] 记录 `model_check` 对 Simscape conserving-port 分支网络的 21 条误报；以编译、仿真和行为测试作为当前管路连接验收。
- [x] 审计 Git 暂存内容并提交本批修复：`e77ae4f fix: stabilize S12 primary pipe propagation`。

### S12 第五批：单管三档网格收敛

- [x] 先建立 `4/8/16` 单元传播收敛测试，并确认因缺少 `4cell` 模型正确 RED 失败。
- [x] 建立 4 单元与 16 单元 Simscape Gas 参考模型，保持总长、初始状态、热边界、激励和终端一致。
- [x] GREEN：三档传播延迟相对理论值均小于 15%，8/16 单元延迟差小于 5%，出口峰值差小于 15%。
- [x] 实测延迟 `0.868/0.891/0.895 ms`，出口峰值 `2458.88/3077.78/3133.36 Pa`；8/16 差分别约 `0.46%/1.77%`。
- [x] 三模型 `unconnected_lines` 检查为 `healthy`，新增测试 Code Analyzer `0 issue`，完整 S12 回归 `7/7`。
- [x] Child Claude 仅追加单文件 Obsidian 初稿；主 Agent 修正“模型不在路径”和“显著收敛”两处不严谨表述后复核通过。
- [x] 审计暂存文件并完成独立 Git 提交：`cae7fc2 test: verify S12 primary pipe grid convergence`。

### S12 第六批：开放端反射

- [x] 先建立开放端负压力反射测试并确认模型缺失时正确 RED 失败。
- [x] 建立 8 单元开放端模型，在距入口 0.06 m 处增加压力探针，开放端直接连接大气 Reservoir。
- [x] 首次 GREEN：入射 `+5653 Pa`、反射 `-3409 Pa`、幅值比 `0.603`、负波到达 `1.996 ms`。
- [x] 开放端节点压力扰动小于 `1 Pa`；新增测试 Code Analyzer `0 issue`，模型 `unconnected_lines=healthy`。
- [x] 完整 S12 回归提升为 `8/8`。
- [x] Child Claude 仅追加开放端 Obsidian 记录，主 Agent 对数值、边界和未完成项复核通过。
- [x] 审计暂存内容并完成独立 Git 提交：`5c0b558 test: validate S12 open-end pressure reflection`。

### S12 第七批：HLLC 界面通量核心

- [x] 先建立均匀流解析通量、静止接触间断和镜像状态测试，确认模型缺失时三项 RED 失败。
- [x] 用 Simulink MATLAB Function 块内嵌 HLLC 方程，模型外未新增算法脚本；块、端口和连线由 `model_edit` 创建。
- [x] 三项 GREEN：解析 Euler 通量、接触保持、波速次序和镜像对称均通过；模型检查 `healthy`。
- [x] 测试文件 Code Analyzer `0 issue`；块内临时导出文件仅有生成文件名与函数名不同的非源码警告。
- [x] 完整 S12 回归提升为 `11/11`。
- [x] Child Claude 仅追加 HLLC Obsidian 初稿，主 Agent 复核模型边界、数值和 MCP 工具限制表述。
- [x] 审计暂存内容并完成独立 Git 提交：`d8df5d3 feat: add S12 embedded HLLC flux core`。

### S12 第八批：周期有限体积单步

- [x] 先建立常状态保持、周期域守恒和 CFL 限制下 Sod 正性测试，确认模型缺失时三项 RED 失败。
- [x] 建立 `3×8` 守恒状态的一阶 HLLC 周期有限体积单步 Simulink 模型，核心源码嵌入 `.slx`。
- [x] 三项 GREEN：常状态保持、周期质量/动量/总能量守恒和 Sod 一步正性均通过；实际步长 `12.026756 us`。
- [x] 解析 CFL 与非零状态更新断言通过；模型检查 `healthy`，测试 Code Analyzer `0 issue`。
- [x] 完整 S12 回归提升为 `14/14`；新增 FVM 三项约 4 秒，主要耗时来自 Simscape 冷编译。
- [x] Child Claude 仅追加周期 FVM Obsidian 初稿，主 Agent 复核守恒容差、步长、正性和未完成边界。
- [x] 审计暂存内容并完成独立 Git 提交：`c8961f2 feat: add S12 conservative FVM step`。

### S12 第九批：SSP-RK3 与长时 Sod 激波管

> 状态：已完成并提交；本批只建立一阶 HLLC 空间离散上的 SSP-RK3 时间推进和长时 Sod 验证，不加入 MUSCL。

- [x] 重跑当前 S12 全量基线，确认 `14/14` 通过。
- [x] 只读审计当前 HLLC/FVM 模型、架构约束和 Obsidian 接力记录。
- [x] 将 Toro/HLLC、Davis 波速与 Batten 条件性正性权威出处补入论文矩阵。
- [x] 新增长时均匀态与 200 单元 Sod RED 测试，确认模型缺失时正确失败。
- [x] 用 `model_edit` 创建独立 SSP-RK3 模型，用 `Stateflow.EMChart.Script` 写入核心方程。
- [x] 验证 CFL、末步时间裁剪、正密度/压力、开放边界通量守恒账和 Toro 精确解误差。
- [x] 运行专项测试、Code Analyzer、模型检查和完整 S12 回归。
- [x] 更新 S12 README 与 Obsidian 历史，记录 MUSCL、正性限制器和生产边界为后续门禁。
- [x] 独立审查本批规格符合性和代码质量，修复重要问题后再提交。

#### 后续前置门禁

- MUSCL 开始前必须保留 Toro–Spruce–Speares HLLC 原始出处、Davis 外侧波速出处以及 Batten 正性结论的适用条件，禁止把当前 Davis 波速实现表述为已获无条件正性证明。
- MUSCL、正性限制器、FVM/Simscape 交叉验证、八缸网络和尾管辐射均不属于本批完成范围。

#### Review

- RED：新测试首次运行 `0 Passed / 2 Failed`，两项均因 `s12_euler_ssprk3_sod_ref.slx` 不存在而失败；测试 Code Analyzer `0 issue`。
- GREEN：未修改测试即达到专项 `2/2`；主 Agent 重新运行专项仍为 `2/2`，完整 S12 回归由 `14/14` 提升到 `16/16`。
- 模型结构：6 个 Constant、1 个 `SSPRK3Integrator` MATLAB Function、5 个 To Workspace；核心 HLLC、transmissive 边界和 SSP-RK3 均嵌入 `.slx`。
- 均匀态：119 步，最大状态误差 `2.78e-17`。
- Sod：200 单元、CFL `0.45`、终止时间 `0.2`、191 步；数值激波/接触位置 `0.855/0.680`，最小密度/压力 `0.1250000000005/0.1000000000006`，最大缩放守恒残差 `1.03e-15`。
- 验证：模型 `model_check(["all"]) = healthy`；新测试 Code Analyzer `0 issue`；独立测试审查与模型审查均为 Spec PASS / Code APPROVED。
- Child Claude 按 `Read,Glob,Grep`、4 文件、3 turns/60 s 的窄只读合同执行最终文档审计，但结构化返回 `Success=false`、`TimedOut=true`、`Turns=null`、stderr 为超时、raw stderr 为空；未重试、未接受部分结果，Codex 继续承担最终审查。
- 边界：当前仍是一阶空间格式；没有 MUSCL、正性限制器、FVM/Simscape 交叉验证或生产级排气边界，不能称为最终真实声浪。
- 有效仓库提交：`a5815ee feat: add S12 SSP-RK3 Sod validation`；仅包含 README、新 `.slx` 和新测试 3 个已验证文件。

### S12 Sprint 0.5：Numerical Benchmark Foundation

> 状态：已完成、已提交并已于 2026-07-14 推送至 `origin/main=0263fd4bc08fb046076ab6d586ea087dd34aecfa`。Architecture v1 已冻结；本批只建立 Benchmark Foundation 与 smooth periodic SSP-RK3 时间精度验证，不进入 MUSCL、正性保持或发动机扩展。

- [x] 完成只读 Library Reuse Audit；确认不存在应优先复用的项目自有 Block Library。
- [x] 通过官方 API 建立 `.satk/reuse-libraries.json` 与 `.satk/block-policy.json`，并记录空 library KG 与审计证据。
- [x] 将 Product Validation、Golden PCM、Engine Evidence A/B/C/D 纳入 `S12 Platform Architecture v1`。
- [x] RED：为 registry/profile/schema、入口分层、report-only 和 deterministic artifacts 建立失败测试。
- [x] GREEN：建立最小 Benchmark Foundation，不修改既有 HLLC/FVM/Sod 模型。
- [x] RED→GREEN：建立独立 periodic SSP-RK3 验证路径和 Smooth Periodic Entropy Wave。
- [x] 用同网格 `dt/dt/2/dt/4/dt/8` 做 Richardson 时间自收敛，并证明 requested dt 未被 CFL 截断、最细 observed order 处于合理三阶区间。
- [x] 接入现有 uniform 与长时 Sod；从一个 Canonical Result 生成 Markdown、PNG、CSV 和 JSON。
- [x] 支持单 case、分类、完整 suite、report-only；普通输出 ignored，baseline 只允许显式 promotion。
- [x] 运行专项测试、完整 S12 回归、Code Analyzer、`model_check`、Git/determinism 检查。
- [x] 更新 README、Benchmark 文档、todo/lessons 和长期有效的 Obsidian 记录。
- [x] 审计 diff，独立提交并已推送；完成后停止，不自动进入 Sprint 1。

#### Sprint 0.5 Review

- RED→GREEN：Foundation `0/4→4/4`；periodic SSP-RK3 `0/2→2/2`；Smooth Wave `0/1→1/1`；report、entrypoint 和 promotion 均先缺函数失败再转绿。
- Solver 复用：Benchmark 不含 HLLC/FVM 方程；三个 Forward-Euler stage 均调用未修改的 `s12_euler_fvm_periodic_step_ref.slx`，新模型只实现 SSP-RK3 标准凸组合。
- Full profile：uniform 最大误差 `2.7756e-17`；200-cell Sod 密度/速度/压力 L1 `0.0133237/0.0236653/0.0114884`；Smooth observed order `3.00048/3.00024`，最大缩放守恒误差 `1.90e-15`，所有 requested dt 未被 CFL 截断。
- 产物：Canonical JSON 单向生成 Markdown、两个 CSV 和三个 PNG；report-only 不重算 acceptance；固定画布并移除 PNG `tIME` 后跨目录字节一致。
- 验证：清缓存后完整 S12 `26/26`；四个 FVM/HLLC/SSP-RK3 模型 `model_check=healthy`；Code Analyzer `0 issue`；`benchmark/out/` 为 ignored。
- Library Audit：20 个 `.slx`、2 个 `.sldd`，无 `.mdl/.slxp/.mldatx`，无项目自有可复用 Block Library；90 秒 Child-Claude 审计成功返回支持 `confirmed_none=true`。
- 最终只读代码审查外派连续三次在约 90.9 秒真实超时，均未返回结构化结果；按 watchdog 上限停止委派，由主 Agent 依据代码、模型和测试证据直接完成审查。
- 实现提交：`0b95504 feat: add S12 numerical benchmark foundation`；accepted baseline 提交：`0263fd4 test: accept S12 Sprint 0.5 benchmark baseline`。两者均已推送，远端 `origin/main=0263fd4bc08fb046076ab6d586ea087dd34aecfa`。
- Baseline manifest 绑定实现 commit `0b955043c9ab309f8bc7b8c3d6b1d954def9f588` 与 MATLAB `R2026a`；显式 promotion 后，report-only 重建的 7 个 artifact SHA-256 全部与 accepted baseline 一致。

### S12 Sprint 1：Standard Numerical Benchmark Suite

> 状态：已完成并已接受。以 `0263fd4` 为 Sprint 0.5 已接受基线；Sprint 1 只扩充验证能力，未修改 HLLC、FVM、SSP-RK3、CFL 或既有边界实现。

- [x] 冻结 Lax、Shu–Osher、Woodward–Colella 的权威定义、参考类型、网格/边界及一阶耗散边界。
- [x] RED：新增三个 case、profile/registry、报告产物和报告重建契约测试，并确认缺失功能导致预期失败。
- [x] GREEN：复用现有 transmissive SSP-RK3 adapter 与 Canonical Result 接入三个 case；Woodward–Colella 使用对称延拓而非修改边界模型。
- [x] 完成 quick/full、多网格指标、失败诊断和 deterministic artifact 回归；未自动 promotion。
- [x] 运行专项测试、Benchmark contract、完整 S12、Code Analyzer、model_check、清缓存回归与 Git 审计。
- [x] 更新 S12/Benchmark README、Architecture 状态、lessons 和已验证的 Obsidian 知识；独立实现提交且未 push。
- [x] 已显式执行独立 accepted baseline promotion 提交；Sprint 1 到此停止，不进入 Sprint 2/MUSCL/Positivity。

#### Sprint 1 Review

- 权威定义冻结于 `docs/sound-simulation/S12_Sprint1_Standard_Numerical_Benchmark_Case_Definitions.md`：Lax 使用精确 Euler Riemann 参考；Shu–Osher 与 Woodward–Colella 明确为“文献定义 + 自收敛/特征指标”，未伪称不存在的外部数组为解析真值。
- Full 基线：Lax `rho/u/p` L1 为 `0.0230970/0.0206673/0.0248203`（N=`[200,400]`）；Shu–Osher 在 N=`[200,400,800]` 的最细网格激波位置为 `2.425`、峰谷幅值 `1.14075`、总变差 `2.53772`；Woodward–Colella 在 N=`[200,400]` 的最小 `rho/p` 为 `0.160225/17.6785`，无 NaN/Inf。
- 所有新 case 最大 CFL 均为 `0.45`；最大守恒残差依次为 Lax `6.46e-14`、Shu–Osher `2.77e-13`、Woodward–Colella `1.25e-12`。Lax 稀疏波前沿使用“5% 稀疏扇振幅”数值定位器，仅作一阶耗散诊断。
- 回归：新增专项 `7/7`，清缓存完整 S12 `33/33`；所有新增/修改 MATLAB 文件 Code Analyzer 为 `0` 项，四个 FVM/SSP-RK3 模型 `model_check(["all"])` 均 healthy。
- 确定性：从 Full manifest report-only 重建与 accepted baseline report-only 重建均为 `11/11` SHA-256 一致；baseline manifest SHA-256=`F4E00EDEB8E4C33556F99B101FD0BF807168A079F3591AA997306717701E9DCF`。
- 提交：实现 `2f6aaa2 feat: add S12 Sprint 1 standard benchmarks`；显式基线 `76f526b test: accept S12 Sprint 1 benchmark baseline`；均未 push。

### S12 Sprint 2：MUSCL Minmod

> 状态：实现与验证完成，已提交 `ba311ec feat: add S12 MUSCL minmod benchmark mode`，未执行 accepted baseline promotion，也未 push。Sprint 1 accepted baseline `76f526b` 已于 2026-07-14 推送到 `origin/main`。只新增可回退的一阶/`muscl_minmod` 空间重构模式；不进入 Positivity、通量回退、额外 limiter、特征变量、MUSCL--Hancock、生产边界、发动机库、排气网络或 Audio DSP。

#### 冻结设计

- 时间离散：既有 Method of Lines + SSP-RK3；同一全局 `dt` 用于三个 RK stage，CFL 仍为 `0.45`。
- 空间离散：对原始变量 `(rho,u,p)` 逐分量做 piecewise-linear `minmod(Δ-,Δ+)` 重构；界面使用左单元右侧极限与右单元左侧极限，随后调用未改写的 HLLC flux。
- 边界：transmissive 与 periodic 契约不变；transmissive 端单元斜率为零，periodic 斜率采用环绕相邻单元。
- 模式：`first_order` 保持冻结 reference model，`muscl_minmod` 使用其专用派生 reference model；同一 adapter/Benchmark 入口显式选择，默认仍为 `first_order`。不向冻结模型新增 selector 端口。
- 不是正性限制：minmod 只负责 TVD 重构；不得 clipping、不得 HLLC→HLLE/Rusanov 回退、不得把失败状态改写为通过。

#### 执行计划

- [x] 固化 Sprint 1 里程碑：工作树干净、本地/远端 `origin/main=76f526b` 一致，两个 Sprint 1 提交已推送。
- [x] 完成库复用门禁与 MUSCL/minmod 文献门禁；将 van Leer、Harten、Sweby 记录进论文矩阵。
- [x] RED：增加 mode contract、first-order fallback、minmod uniform preservation、periodic wrap、transmissive zero-slope 与 Benchmark `Reconstruction` 入口测试；确认 `4/4` 因 adapter/runner 缺少 `Reconstruction` 接口而按预期失败。
- [x] GREEN：由冻结一阶模型派生两个 MUSCL 专用模型；用 `Stateflow.EMChart.Script` 写入 minmod 重构。HLLC 函数体、SSP-RK3 系数、CFL 计算和一阶模型均不改写。
- [x] GREEN：将 `Reconstruction="first_order"|"muscl_minmod"` 贯通 adapter、六个既有 Benchmark case、Canonical Result config 与报告；默认 first-order 的数值指标与 Sprint 1 基线逐项一致。
- [x] REFACTOR：adapter 按模式选模型；不引入第二套 runner、reporter、schema 或 HLLC/FVM 外部脚本。
- [x] 验收：MUSCL 专项 `4/4`，最终两种模式 Full Benchmark 均通过；完整 S12 `37/37`、Code Analyzer `0`、四个模型 `model_check(["all"])` healthy、清缓存专项 `4/4`、report-only `11/11` SHA 一致；未自动 promotion。
- [x] 更新 README、tasks、Architecture 实施状态和已验证的 Obsidian 记录；已独立提交但未 push，并在 Sprint 2 完成后停止。

#### Sprint 2 Review

- 实现：`s12_euler_ssprk3_muscl_minmod_ref.slx` 与 `s12_euler_fvm_periodic_step_muscl_minmod_ref.slx` 是冻结一阶模型的专用派生；`first_order` 继续调用 Sprint 1 冻结模型，避免 Stateflow 新输入端口改变其动态状态尺寸传播。
- 数值：200-cell Sod 的 `rho/u/p` L1 从一阶的 `0.0133237115957/0.0236653165284/0.0114883767907` 降为 `0.00420537883454/0.00764638335433/0.00313444457714`。Lax 的 `rho/u/p` L1 从 `0.0230969955377/0.0206672840693/0.024820321647` 降为 `0.00936506958234/0.00571481250784/0.00663728213253`。
- 稳定性：Smooth Periodic observed order 为 `3.24263735191448/3.00619517258623`，最大缩放守恒误差 `1.9931972739e-15`；Shu--Osher 最细网格激波位置 `2.4`、幅值 `1.32715088136`、总变差 `5.97488142165`；Woodward--Colella 最小 `rho/p=0.152257198133/18.3821545989`，无 NaN/Inf。
- 回退：最终 first-order Full Suite 通过，和 Sprint 1 accepted baseline 的所有非运行时数值指标比较为 `0` 项漂移。
- 确定性：最终 MUSCL Full manifest SHA-256=`88C31434CADBD2F2697ACC3BA655ACC9C52268F9AEBCDF558245EB083C38C911`；report-only 重建的 11 个受控产物 SHA-256 全部一致。
- 边界：minmod 不是正性限制器。没有 clipping、HLLC→HLLE/Rusanov 回退、特征变量重构、MUSCL--Hancock 或新的生产边界。Sprint 3 仍须先实施 Zhang--Shu 风格正性保持。
- 提交与停止点（初始实现历史）：`ba311ec feat: add S12 MUSCL minmod benchmark mode`。其“未 promotion”状态已被下方 Final Qualification 的 `715f8cb` 与 `eaf6295` 两个独立提交取代；仍未 push，`origin/main` 保持 `76f526b6d8f1e82c3fc333456299fc8f3c506195`。

#### Sprint 2 Final Qualification Plan

> 状态：已完成并已接受。Final Qualification 只补充验证、诊断、schema minor 和报告能力，未改写 MUSCL/HLLC/FVM/SSP-RK3 算法；实现提交 `715f8cb`，accepted baseline 提交 `eaf6295`。Sprint 3 仍未开始。

- [x] 独立审计：Smooth cell-average 空间收敛、periodic/transmissive stencil、limiter/schema 统计、隐藏 clipping/fallback/CFL 改写与 Sprint 0.5/1 baseline 完整性；Child-Claude 两个窄范围包按 90 秒、三次上限均无结构化结果后由主 Agent 接管。
- [x] 对 `N=[50,100,200,400]` 的同一 periodic entropy wave 完成 first_order/muscl_minmod 对照；记录 `rho/u/p` L1、相邻空间阶、同网格误差比、requested/effective dt、CFL 与 end-time clipping。rho 最细阶为 `0.99956/1.93607`，MUSCL 误差比最细为 `0.01964`。
- [x] 将 Uniform、Sod、Lax、Shu--Osher、Woodward--Colella 的双模式正式网格对照、interface/limiter/守恒诊断纳入一个 Sprint 2 cross-mode Canonical Result 与同源 Markdown/PNG/CSV/JSON。
- [x] 明确强激波/RK stage 边界：Woodward--Colella 无负 cell/interface `rho/p`、无 NaN/Inf、无 invalid stage；无 clipping、flux fallback、CFL 改写或自动重试。transmissive exact-end-time clip 仅显式记录为计数，不是隐藏缩步。
- [x] 确认 MUSCL 是两个独立受控 `.slx`；冻结与派生共四个模型均执行 `model_check(["all"]) = healthy`。adapter 每次关闭并重载受控 transmissive `.slx`，避免内存旧模型污染资格证据。
- [x] 执行专项、完整、冷缓存、Code Analyzer、report-only、Git 检查；Full Canonical Result 的五个受控产物 SHA-256 一致，随后显式 promotion 到新的 Sprint 2 baseline 目录；不 push。

#### Sprint 2 Final Qualification Review

- Spatial：cell-average entropy wave 的 rho L1（N=`[50,100,200,400]`）一阶为 `[5.01334e-4,2.50997e-4,1.25591e-4,6.28151e-5]`，MUSCL/minmod 为 `[6.37171e-5,1.79840e-5,4.72043e-6,1.23358e-6]`；最细阶 `0.99956/1.93607`，requested/effective dt 均为 `[1e-3,5e-4,2.5e-4,1.25e-4]`。常值 u/p 仅有 round-off L1，不用作空间阶门禁。
- Cross-mode：200-cell Sod 的 `rho/u/p` L1 为 `0.0133237/0.0236653/0.0114884 -> 0.00420538/0.00764638/0.00313444`；Lax 为 `0.0230970/0.0206673/0.0248203 -> 0.00936507/0.00571481/0.00663728`；Shu--Osher MUSCL 最细 shock/peak-to-trough/TV 为 `2.4/1.32715/5.97488`，仍明确是文献定义加特征指标。
- Strong shock：Woodward--Colella MUSCL 最小 cell `rho/p=0.152257/18.3822`，最小 interface `rho/p=0.152257/0.01`，invalid reconstruction/stage、NaN/Inf、clipping/fallback/retry/CFL rewriting 均为零；限制器激活 `3.04673e7`，limited-cell fraction `0.753871`。`end_time_clipping_count=2` 是显式精确终止时间裁剪，非隐藏重试。
- Determinism/quality：专项 `5/5`，清缓存完整 S12 `42/42`，18 个新增/修改 MATLAB 文件 Code Analyzer `0`，四模型 healthy；report-only 的 Markdown、JSON、两份 CSV 和 PNG 共 5/5 SHA-256 一致。Full manifest SHA-256=`03CAA98167EE4238CB2E505DF6E7CDB36450D559EA99680C934C23CF022D44F3`。
- Git：实现 `715f8cb test: add S12 Sprint 2 final qualification`；accepted baseline `eaf6295 test: accept S12 Sprint 2 MUSCL baseline`；`origin/main` 仍为 `76f526b`，不 push。下一阶段固定为 Sprint 3 Positivity，尚未开始。

#### Sprint 3 Positivity Preservation Plan

> 状态：设计已冻结，待 RED。Sprint 2 accepted baseline `eaf6295` 已于 2026-07-14 普通推送；本地 `HEAD`、`origin/main` 和 accepted baseline 均为 `eaf629532d937584b8992f0de5ca86410c3ba9e6`，工作树干净。`first_order` 与 `muscl_minmod` 及 Sprint 0.5--2 历史 baseline 均冻结；不需要再做架构确认。

- [x] 里程碑固化：以非 force push 将 `ba311ec`、`715f8cb`、`eaf6295` 推送到 `origin/main`，并用 `git ls-remote` 验证三方 ref 一致。
- [x] 完成只读最小改动面审计：新模式必须使用独立的周期与 transmissive `.slx`；adapter、schema 与报告沿用现有统一管线；Sprint 2 专用 qualification/report 和冻结模型不得改写。模型修改后必须显式保存、关闭、冷重载并执行 `model_check(["all"])`。
- [x] 完成正性证据审计：Zhang--Shu 的缩放型 reconstruction limiter、Gottlieb--Shu--Tadmor 的 SSP 继承条件，以及 Einfeldt 等的低密度失败域将补入论文矩阵。当前 Davis/HLLC 组合不具备可无条件套用的全局正性结论。
- [x] 数值设计冻结：新增独立 `muscl_minmod_pp` 模式与两个独立受控 periodic/transmissive positivity `.slx`；采用 primitive slope scaling、HLLC 高阶通量、global Lax--Friedrichs 正性锚点和 Hu--Adams--Shu 共享界面保守通量限制。floor 为 `min(1e-13, initial minimum)`；`CFL_target=0.45`、`CFL_pp_hard_max=0.5`；超限只能整步从 `Un` 拒绝并用共享新 `dt` 重算，禁止 hidden clipping、局部缩步或 HLLE/Rusanov/HLLC fallback。批准原文 SHA-256=`A7CF3A4C7BBF44AD09B3B80C3F2203E54D8588E4EC6656AFDAF42FEBA536469F`。
- [x] 同步长期知识：新增 Obsidian `2026-07-14-S12-Sprint3-Positivity-Design-Freeze` 并更新索引、Sprint 2 note、论文矩阵和 lessons；只记录批准设计与已验证 Sprint 2 事实，不把 RED、实现或 qualification 写成已完成。
- [x] RED-A Reconstruction Positivity Contract：以可手算 primitive slopes、floor 和边界 stencil 覆盖共享 `theta_recon`、cell-average 不变、非法中心显式拒绝；未实现 production limiter。
- [x] RED-B Global LF Anchor Contract：固定 stage-global `alpha=max(abs(u)+c)`、一致态物理通量、`CFL<=0.5` 与越界整步拒绝合同；未实现 anchor。
- [x] RED-C Hu--Adams--Shu Flux Contract：固定 shared-interface theta、one-sided partial-state floors、守恒和 anchor-failure 拒绝合同；未实现 production flux limiter。
- [x] RED-D SSP-RK3 Positivity Contract：固定三个 stage 共享 dt、每 stage 重算、整步 discard/retry 与统计合同；RED 未创建或修改 `.slx`。
- [x] RED-E Benchmark/Schema Contract：固定 `muscl_minmod_pp` registry/adapter、schema minor、Smooth 与 double-rarefaction 结果字段及历史 baseline 不漂移合同；RED 未改 production registry/adapter/baseline。
- [x] RED Review：专项最终为 `0 Passed / 19 Failed / 0 Incomplete`，失败仅对应 Sprint 3 函数、scheme、schema 和 case 尚不存在。Child-Claude 对窄审计连续三次无结构化结果后由主 Agent 接管。

> MATLAB 执行边界已解除（2026-07-14）：终止用户授权的 MATLAB PID `30752/33180` 后仍复现；继续定位到自 2026-07-11 残留的 `MathWorksServiceHost` PID `51924`。终止该 Service Host 后，空 smoke 于 `20.1 s` 成功输出 `S12_MATLAB_SMOKE_OK`，随后 RED 正常完成。该过程未改 solver/model/baseline。
- [x] 克隆受控 MUSCL 模型并以 Stateflow chart 源码实现；每个 SSP-RK3 stage 的 `FE_pp` 重算全部 limiter，三个 stage 保持同一 global dt；模型修改后显式保存、关闭、冷重载并执行 `model_check(["all"])`。
- [x] 完成专项/完整/冷缓存回归、Code Analyzer、所有相关 `model_check`、report-only、baseline promotion、README/tasks/Obsidian 与独立提交；不 push，并在 Sprint 3 完成后停止。

#### Sprint 3 Final Qualification Review

- 实现提交：`1adf77e feat: add S12 positivity-preserving MUSCL mode`；资格提交：`d3986cf test: qualify S12 Sprint 3 positivity preservation`；accepted baseline 目录：`prj/tools/sound_sim/s12/benchmark/baselines/sprint-3`。最终 baseline 提交将在文档与 baseline 文件提交后形成；不 push。
- 新模式：`muscl_minmod_pp` 使用独立 periodic/transmissive `.slx`，不改变 `first_order` 或 `muscl_minmod` 语义；禁止 clipping、HLLC fallback、hidden CFL rewrite、stage-local dt 和静默 retry。
- Qualification：10/10 gate passed；smooth rho 最细空间阶 `1.93607`；Sod PP/MUSCL rho error ratio `0.999689164126`；Lax ratio `1.00005576734`；double-rarefaction 触发 flux PP `28` 次、最小 flux theta `0.932342353373`，无 retry/reject。
- 正性边界：所有 case 的 cell/interface/anchor/final partial rho/p 均保持 floor 以上；invalid reconstruction/stage、NaN/Inf、clipping、flux fallback 均为 0。当前结论只覆盖理想气体 Euler benchmark 域、显式 floors、global LF anchor 与 `CFL_pp_hard_max<=0.5`，不等同于未来发动机源项或生产边界的无条件正性。
- 验证：最终树清缓存完整 S12 `61/61`；4 个 qualification MATLAB 文件 Code Analyzer `0 issue`；7 个相关 `.slx` `model_check(["all"])=healthy`；Full/report-only 6 个受控产物 SHA-256 一致；accepted baseline/report-only 6 个受控产物 SHA-256 一致。
- Baseline：`baseline-approval.json` 标记 `status=accepted`，`source_git_commit=d3986cf9aaad8e193e0f11574816f84466f410cf`；`benchmark-result.json` SHA-256=`D45538BA31C65C467B8E47DACE8BC7A5BEB09434E5366B458C76A63E947ED08A`。
- Child-Claude：文档审阅窄包连续三次未给出结构化结果，按 90 秒 watchdog 与三次上限由主 Agent 接管；该失败不作为工程验收证据，只记录流程边界。
- 下一步固定为 Sprint 4：自研 FVM 与 Simscape Pipe(G)、解析 Fanno Flow 等交叉验证和报告。未进入 Engine Library、Exhaust Network、Radiation、Audio DSP 或 Tesla 实车播放。

#### Sprint 3 Design-Freeze Documentation Review

- 已从用户提供附件恢复 741 行 UTF-8 原文，而不是依据聊天截断文本推断数值授权；批准设计附件 SHA-256=`A7CF3A4C7BBF44AD09B3B80C3F2203E54D8588E4EC6656AFDAF42FEBA536469F`。
- 已记录 `muscl_minmod_pp`、global LF anchor、Hu--Adams--Shu shared-flux limiting、floor、整步 rejection/retry 与 no-clipping/no-fallback 边界；该条为设计冻结时状态，现已被上方 Sprint 3 Final Qualification Review 取代。
- 已修正 Obsidian 中 Sprint 2 推送状态为 `origin/main=eaf629532d937584b8992f0de5ca86410c3ba9e6`；`E:\Tesla_speed\prj` 复核为干净工作树，无 solver/model/source 改动。

#### Sprint 3 Release Audit and Push Review (2026-07-15)

- [x] 审计起点：`HEAD=7de6942bbcce08b40c0bb6cbd43b93cbaea4df44`、工作树干净、`origin/main=eaf629532d937584b8992f0de5ca86410c3ba9e6`、ahead 3 / behind 0；`git diff --check` 无输出。
- [x] 机器证据复核：Sprint 3 专项合同测试 `19/19`；完整 S12 回归 `61/61`；4 个 qualification MATLAB 文件 Code Analyzer `0 issue`；7 个受控模型 `model_check(["all"])=healthy`。
- [x] Smooth spatial：`muscl_minmod` 与 `muscl_minmod_pp` 的 rho 最细空间阶均为 `1.9360678883347477`，误差数组逐项一致。
- [x] Double-rarefaction：最小 cell `rho/p=0.00393242120818/0.000294365850632`；最小 reconstructed-interface `rho/p=0.00393241989855/0.000294365689271`；最小 anchor partial `rho/p=0.00385458672382/0.000287947299341`；最小 final partial `rho/p=0.003839448158/1.00000910330e-13`。reconstruction PP `0` 次，flux PP `28` 次，最小 theta=`0.932342353373`，retry/reject 均为 `0`。
- [x] 正式 PP case 最大守恒残差 `1.63780100593e-12`（Woodward--Colella），最大记录 CFL `0.467484874858`（long-time Sod）；8 个 PP 结果均 retry/reject/automatic retry=`0`，clipping/fallback/invalid stage=`0`，`cfl_changed=false`。global LF 是冻结正性锚点，不是 Rusanov/HLLE/HLLC runtime fallback。
- [x] 确定性与历史保护：Sprint 3 accepted/report-only 六个受控产物逐文件 SHA-256 一致；manifest SHA-256=`D45538BA31C65C467B8E47DACE8BC7A5BEB09434E5366B458C76A63E947ED08A`。Sprint 0.5/1/2 baseline 相对 `eaf6295` 变更文件数为 `0`。
- [x] 正常推送且未 force：`git push origin main` 将 `eaf6295..7de6942` 推送到 `origin/main`；随后本地 HEAD、remote-tracking ref 和 `git ls-remote origin refs/heads/main` 均为 `7de6942bbcce08b40c0bb6cbd43b93cbaea4df44`，工作树干净。

### S12 Sprint 4A — Fanno / Simscape Cross-Validation Foundation

> 目标：只建立 Analytical Fanno Reference 与 Simscape `Pipe (G)` 的可追溯、同物理假设交叉验证闭环；Sprint 4A 不修改或接入生产 S12 FVM，不创建 Sprint 4 accepted baseline，不进入 Engine Library、Exhaust Network 或 Audio DSP。

- [x] A. Case-definition evidence gate：用 MathWorks 官方 `Fanno Flow Gas Pipe Validation`、`Pipe (G)` 文档和 NASA/TM-2006-214086 冻结稳态、一维、等截面、绝热、calorically-perfect ideal gas、subsonic Fanno 定义；明确 Darcy/Fanning 换算、静态/总态量、摩擦与 choke margin；补入论文矩阵。
- [x] B. RED analytical contracts：新增 `tests/test_s12_fanno_reference.m`，以独立恒等式覆盖 `F(M)`、长度到 choke、亚音速单调性、质量流量/总温守恒、非法域与接近 choke 拒绝；先确认 production evaluator 不存在导致受控失败。
- [x] C. GREEN analytical reference：在 `tools/sound_sim/s12/validation/fanno/` 实现单一职责的 Fanno evaluator/inverter；不把方程复制进 benchmark case 或 report。
- [x] D. RED Simscape contract：新增 `tests/test_s12_fanno_pipe_g_cross_validation.m`，冻结 perfect-gas `R/gamma/cp`、几何、无附加局部长度、绝热壁、固定上游静态条件、下游质量流量、station 定义、steady-window 判据和 segment-count 扫描；测试先因专用模型/adapter 缺失失败。
- [x] E. GREEN matched Pipe(G) reference：用官方 Simulink/Simscape API 建立独立受控模型，结构与参数完全匹配 Fanno case；所有结构编辑遵守 `.satk` gate、`model_edit`、保存/关闭/冷重载和 `model_check(["all"])`。不复用或修改现有热脉冲管模型。
- [x] F. Benchmark integration：新增 `fanno_pipe_g_cross_validation` / `cross_validation` case，复用 registry/profile/Canonical Result/report-only 管线；JSON 保存原始 analytical/Simscape profiles 与 acceptance，CSV/PNG/Markdown 只从 Canonical Result 渲染，Report 不重算门禁。
- [x] G. Quick/Full qualification：quick 验证接口；full 覆盖 `L=1/76/156 m` 的低/中/近 choke 亚音速工况和 1/5 段 Pipe(G) 对照。解析 Fanno 是独立真值，摩擦因子按冻结的 Haaland/Darcy 定义计算。
- [x] H. Quality gates：Fanno/Benchmark 专项 `20/20`；冷环境完整 S12 `75/75`；Code Analyzer `0 issue`；两个新增模型 `model_check(["all"])=healthy`；Full/report-only 全部九个受控产物 SHA-256 一致；历史 baseline 合同通过。
- [x] I. Documentation/commit：已更新 S12/Benchmark README、Architecture 实施状态、tasks/lessons、论文矩阵及已验证的长期 Obsidian 记录；本地提交 `fcfe6de feat: add S12 Sprint 4A Fanno cross-validation`，未 push；停在 Sprint 4A，未接入 FVM。

#### Sprint 4A Qualification Review

- Full case：`L=1/76/156 m`；单段 Pipe(G) 最大相对误差 `0.0111416637`，五段最大相对误差 `0.00105168`，五段对长管精度有明确改善；最小归一化 choke margin `0.1018`，retry=`0`。
- 产物：JSON、Markdown、CSV 和 PNG 均由同一 Canonical Result 生成；Full/report-only manifest 中登记的全部九个受控产物 SHA-256 逐文件一致。
- 模型：`s12_fanno_pipe_g_ref.slx` 与 `s12_fanno_pipe_g_segmented_ref.slx` 均只使用内置 Simscape/Simulink 块，`model_check(["all"])=healthy`；分段模型每段 H 端口使用独立 Perfect Insulator，禁止共享热节点。
- 边界：Sprint 4A 未修改或调用生产 FVM；未创建 accepted baseline；三方 Analytical/Simscape/FVM 对照固定留给 Sprint 4B。
- Git：实现与资格证据已合并为本地提交 `fcfe6de`；`origin/main` 保持 Sprint 3 accepted milestone `7de6942`，本批未 push。

#### Sprint 4A Accepted-Baseline Provenance Repair and Release (2026-07-15)

- [x] 原样隔离无效候选：原 `benchmark/baselines/sprint-4a` 候选的 manifest SHA-256 为 `19200653F1187563662813D47E8A4BB3685A89A28E662030C470BD75DD136C08`，其 `source_commit=7de6942`，与 4A 实现提交 `fcfe6de` 不一致；逐文件哈希复核后迁移至 `E:\Tesla_speed\tasks\reports\artifacts\invalid-provenance\S12_Sprint4A_pre_fcfe6de_2026-07-15`，状态为 `invalid_for_acceptance_but_retained_as_audit_evidence`，并清除活动 baseline 扫描目录中的无效候选。
- [x] 从干净 `HEAD=fcfe6de` 重跑 Full 并显式提升：新的 Canonical manifest SHA-256 为 `555C03D334AA8D6B7DB8EC53C8BBB7F890714885CEF3E9E5C5B3405045C1AA8D`，`source_git_commit=fcfe6deb2175237866633ee7804cfa3be64aef23`，九个受控 Full/report-only 产物逐项 SHA-256 一致。
- [x] 提交并正常推送 Sprint 4A accepted baseline：`de29c52 test: accept S12 Sprint 4A Fanno baseline`；未 force push。发布后本地 HEAD、`origin/main` 与远端 `refs/heads/main` 均为 `de29c524cdd03dac7d202c2fc2f8e6672f33b642`，历史 Sprint 0.5--3 baseline 未变化。

### S12 Sprint 4B — FVM Fanno Three-Way Cross-Validation

> 目标：在冻结的 `muscl_minmod_pp` 双曲算子之上新增独立、可审计的 `muscl_minmod_pp_fanno` 平衡律模式，实现 Analytical Fanno ↔ Simscape Pipe(G) ↔ S12 FVM 三方验证。不得更改历史 solver、历史 baseline 或 Sprint 4A 解析/Simscape 结果；完成后本地 accepted baseline 并停止，不进入 Sprint 4C。

- [x] A. RED contracts：用小型确定性 fixture 先冻结 Darcy 摩擦精确半步、Strang 调度、validation-only characteristic inlet/outlet、source-balanced momentum、cell-average reference、schema/adapter 与 baseline 兼容合同；初始 `12/12` 失败仅来自缺失 Sprint 4B 能力，随后未重复 RED。
- [x] B. GREEN source/boundary primitives：实现 `f_D/(2D_h)` 的精确局部摩擦更新、正/反向流、`f_D=0`、非法输入拒绝；实现只用于 Fanno 验证的亚声速 `p/T` inlet 和 `mdot` outlet，保留正确的 outgoing characteristic/entropy 信息，拒绝 reverse/sonic/supersonic；当前五份合同 `12/12` 通过。
- [x] C. Independent Fanno execution path：创建受控 `s12_euler_fvm_fanno_ref.slx` 与 adapter；Strang `source(dt/2) → frozen PP hyperbolic SSP-RK3(dt) → source(dt/2)`，不复制 HLLC/MUSCL/PP 公式，不使用 clipping/fallback/隐藏热源。每次 retry 从完整 `U_n` 重启。
- [x] D. Benchmark integration：新增 Uniform Friction Decay 以及 `L=1/76/156 m` FVM Fanno case；复用 4A 工况，四档 `N=50/100/200/400` cell-average initialization/reference，机器稳态判据和冷启动 smoke；Canonical Result minor 4 扩展并保留 report-only。
- [x] E. Qualification：阈值在正式 Full matrix 前冻结；专项 `23/23`、完整 S12 `98/98`、冷缓存关键回归 `11/11`、Code Analyzer `0 issue`；19 个模型中 15 个 healthy，4 个既有 primary-pipe 模型仅保留已知 conserving-port 假阳性警告。Full/report-only 12 个受控产物逐字节一致，历史 baseline 未修改；无 NaN/Inf、clipping、HLLC/HLLE/Rusanov fallback、hidden retry/heat source。
- [x] F. Evidence/closeout：已更新 S12/Benchmark README、4B design/qualification、Architecture、参考矩阵、tasks 与已验证 Obsidian 长期知识；从干净 `c517c14` 重跑 Full，显式提升独立 Sprint 4B baseline 并提交为 `bf11f92`。未 push，未进入 Sprint 4C。

#### Sprint 4B Runtime Blocker Record (2026-07-15)

- [x] RED 已受控完成：新增五组 `test_s12_fanno_*_contract.m`，共 `12/12` 失败均为缺失的 Sprint 4B production capability，修正 fixture guard 后无 syntax/path/dimension/Test API 噪声。
- [x] 已转绿的独立基础合同：精确 Darcy friction（正/反向流、`f_D=0`、semigroup、非法输入）、`p/T` inlet、`mdot` outlet、source-balanced momentum metrics、Gauss-Legendre conservative cell averages 共 `10/10` 通过；未修改冻结 HLLC/FVM/MUSCL/PP 模型或历史 baseline。
- [x] Runtime recovery preflight：结束孤儿 `MathWorksServiceHost` PID `74192` 与 Monitor PID `53264` 后，MCP attach、`new_system`、冻结 PP one-step、新 Fanno source one-step、`model_check(["all"])` 均通过；新模型通过 `model_edit` 建立于正式 `models/fvm_ref/` 路径。该恢复与孤儿进程清理存在时间关联，但尚未证明唯一根因；blocker report 当前为 `resolved_for_current_session`。
- [x] Runtime 恢复后的 stage-level adapter、统一 Benchmark integration 与三方 Full 已完成；`blocker` 仍只标记为当前会话解除，孤儿 MathWorks 后台进程只是时间相关恢复因素，不宣称唯一根因。

#### Sprint 4B Qualification Review (2026-07-16)

- 数值模式：`balance_law_mode=fanno_constant_darcy`，`friction_source_id=darcy_wall_exact.v1`，`source_integrator_id=strang_exact_friction_ssprk3.v1`，`boundary_id=subsonic_fanno_validation.v1`。边界仅用于正向亚声速 Fanno 验证。
- Full matrix：`L=1/76/156 m`、`N=50/100/200/400` 共 12 个正式 FVM run 均达到机器稳态；最大 CFL `0.18`，retry/reject/clipping/fallback/invalid/source rho/source E/end-time clipping 均为零。
- 网格证据：76 m Mach L1 阶为 `1.99402/1.99692/1.99841`；156 m 为 `2.23751/1.98126/1.99045`。156 m、N=400 Mach L1/Linf=`1.00003e-5/0.00262612`，outlet 最大相对误差 `0.00229289`。
- 平衡与合法性：最大 state/mass-uniformity/mass-balance/energy/source-momentum/T0-spread 分别为 `0.00354480/0.00130804/0.000706240/0.000162279/0.00409980/0.0575550`；最小 reconstructed rho/p=`0.958873/80525.7`，最小 sonic margin=`0.614656`。
- 三方：Sprint 4A one/five-segment Simscape 对 analytical 最大误差保持 `0.0111417/0.00105168`；五个真实 segment-end 位置的 FVM/Simscape 最大差 `0.00129991`。Uniform Friction Decay 最大相对误差 `1.45519e-16`。
- 确定性：Full/report-only 的 1 Markdown、1 JSON、6 CSV、4 PNG 共 12 个受控产物 SHA-256 全部一致；正式 accepted baseline 必须在 qualification 提交后从干净 HEAD 重新生成，禁止提升当前 dirty-WIP provenance。
- Final audit：只读审计发现 uniform decay 的一次 end-time clip、schema 字段漂移和 `source_split_order` 歧义后，旧候选 13 个文件按哈希保留到 `tasks/reports/artifacts/rejected-qualification/`，未提交。修复提交 `c517c14` 将 uniform benchmark 改为无裁剪的一次自然 CFL 步，schema minor 4 补齐且去重，并把 order/sequence 分离；专项 `23/23`、完整 S12 `98/98`。
- Accepted baseline：`bf11f92 test: accept S12 Sprint 4B baseline`；manifest SHA-256=`8CF048C15536748719088E73E1393FE62944BE14772E44DDBCD2993F5A9F6656`，approval 绑定 `c517c14685898901d1cf93f1272f222b2f0ebcba`。Full/report-only/baseline/baseline-report-only 12/12 四方哈希一致；本地相对 `origin/main` ahead 5，不 push。

#### Sprint 4B Release Audit and Push (2026-07-16)

- [x] 只读发布审计：五个本地提交按 `a4cf502 → 77fc24d → a1cc6b1 → c517c14 → bf11f92` 连续；accepted manifest SHA-256 保持 `8CF048C15536748719088E73E1393FE62944BE14772E44DDBCD2993F5A9F6656`，approval 和 Canonical Result 均绑定 clean implementation commit `c517c14685898901d1cf93f1272f222b2f0ebcba`，Fanno FVM model SHA-256=`F2679BEBCA0F6A393CBB4FDD5A41713115A36DA619BD6EF034CB19C3485F2538`。
- [x] 复核结论：`23/23` Sprint 4B contracts、`98/98` 完整 S12、Code Analyzer `0 issue`、15 个模型 healthy（4 个冻结 primary-pipe conserving-port 假阳性警告已知且未扩大）；Full/report-only/accepted/baseline-report-only 的 12 个受控产物一致，Sprint 0.5--4A baseline 没有改动。三个长度和四档网格全部稳态，最大 CFL=`0.18`、retry=`0`、无 clipping/fallback/hidden heat source。
- [x] 正常发布：未 force 的 `git push origin main` 已将 `de29c52..bf11f92` 推送；本地 `HEAD`、`origin/main` 和远端 `refs/heads/main` 均为 `bf11f924d8c4aaf2caf8003c945228ff05bfc0a1`，`git status` 与 `git diff --check` 干净。随后进入已批准的 Sprint 4C；不重复 Sprint 4B RED、Full 或 baseline promotion。

### S12 Sprint 4C — Transient Pipe-Wave and Open-End Validation

> 目标：新增独立的瞬态直管验证路径，证明传播速度、closed-rigid 反射、ideal pressure-release open-end 反射、有限幅值与 Darcy 衰减，并以解析线性声学为主参考、Simscape Gas 为独立工具链证据、S12 FVM 为被测对象。冻结 Sprint 0.5--4B 的 solver 语义、模型与 accepted baseline；不进入 Engine Library、真实排气网络、Radiation 或 Audio DSP。

- [x] A. RED contracts：用确定性解析/fixture 覆盖声速、Gaussian 平移、arrival-time、反射系数、closed/open 边界符号、特征/ghost-state、能量窗口、schema、report-only 与 Simscape model contract；受控 RED 后已转 GREEN。
- [x] B. GREEN transient primitives：新增只服务验证的线性参考、probe/窗口指标、`closed_rigid_end`、`ideal_pressure_release_open_end`、`nonreflecting_reference_boundary`；不把 transmissive 边界称为物理开放端，不修改冻结 HLLC/SSP-RK3/MUSCL/PP/Fanno 语义。
- [x] C. 独立模型与 Benchmark：新增 FVM transient-wave 模型及 closed/open Simscape Pipe(G) 模型；统一接入 registry、profile、Canonical Result、CSV/PNG/Markdown/JSON 和 report-only，Full 前冻结误差预算与阈值。
- [x] D. Qualification：A--E case、多网格、FVM/解析/Simscape、正性、能量、Code Analyzer 和分组完整回归已通过；registry 为 11 项、schema minor 6。FVM model_check healthy；两个 Pipe(G) 模型各有 21 个已知 conserving-port inspector 假阳性，runtime/行为交叉证据保留且不伪称 healthy。
- [x] E. Baseline/documents：qualification commit=`48deed7` 后从干净树重跑 Full；manifest 由 runner 记录同一 commit 与 `working_tree_dirty=false`。Full/report-only/accepted/baseline-report-only 九个受控 artifact 全部 SHA-256 一致，explicit baseline 位于 `prj/tools/sound_sim/s12/benchmark/baselines/sprint-4c`，baseline commit=`1894b94`，manifest SHA-256=`354930D70C03C8E2C0E0D907F1A15E5EC4B3BDC2B2CFDAD64010A3F60617120D`。未将提交前 `benchmark/out/` 候选提升为 baseline，未 push，停在 Sprint 4C。

#### Sprint 4C Release Audit and Push (2026-07-16)

- [x] Exact warning governance：新增 `.satk/model-check-waivers.json` 与合同测试，R2026a 下 FVM transient 模型为 zero-warning healthy；closed/open Pipe(G) 各精确锁定 21 条 `unconnected_ports` 签名、模型 SHA-256、替代验证与 `qualified_with_exact_tool_limitation_waiver` 状态。任何模型哈希、工具 release、数量或签名漂移均失败；无全局 suppression 或 wildcard。提交：`010537a`。
- [x] 发布复核：S4C manifest 仍绑定 qualification `48deed7`、`working_tree_dirty=false`、`acceptance=passed`；9/9 Full/report-only/accepted/baseline-report-only SHA-256 一致，Sprint 0.5--4B manifest 不变。历史 `111/111` 资格证据保持，新增 waiver 后当前完整回归 `112/112`，Code Analyzer `0 issue`。
- [x] 正常 push：无 force 的 `git push origin main` 推送 `bf11f92..010537a`；local HEAD、`origin/main` 和远端 `refs/heads/main` 均为 `010537a7c427e6a28ebe0b66d62c785b449c460a`，工作树与 `git diff --check` 干净。随后进入已批准 Sprint 4D-A；不重复 Sprint 4C 数值开发，不进入 4D-B。

### S12 Sprint 4D-A — Radiation-Impedance Foundation

> 目标：只建立零平均流、圆形恒截面、无凸缘开放端、平面波范围内的频域复数辐射阻抗参考与可部署近似；复用既有 Benchmark Foundation，不接入时域 FVM。Sprint 4D-B、黏热损失、Engine Library、排气网络与 Audio DSP 均不在本 Sprint 范围内。

- [x] A. Sprint 4C Release Audit：从 accepted manifest 复核 provenance、九个 artifact 确定性、历史 baseline、111/111 回归与数值指标；为两个 Pipe(G) 模型建立精确 42-warning waiver，数量或签名漂移即失败。当前回归为 `112/112`（含 waiver 合同），而非替换历史证据。
- [x] B. 正常发布：仅在 A 全部一致后，非 force push 推送至 `010537a`，验证 local/remote HEAD 相同，并写入可审计推送证据。
- [x] C. RED/reference contract：以 Levine--Schwinger、Zorumski 与 Silva 等权威来源冻结无凸缘、零流、平面波、`exp(+jωt)`、体积速度阻抗、归一化、端部参考面、平面波有效频带、训练/验证频点和阈值；RED 受控失败只指向缺失 4D-A 能力。合同回归含 reference、benchmark 与 Foundation 共 `15/15` 通过。
- [x] D. GREEN/Benchmark：实现独立高精度 direct quadrature reference 与固定发布系数的稳定、因果、被动状态空间候选；接入既有 registry、schema minor 7、CSV/PNG/Markdown/JSON/report-only，输出但不接入 `radiation_boundary_package.v1`。80 点 Full 预资格通过，12/12 Full/report-only artifact SHA-256 一致；该 output 仅为资格证据，不能提升 baseline。
- [x] E. Qualification/baseline：已修复频域 case 被错误附加 PP solver gate 的跨类别合同问题（`721722b`）；radiation/Fanno/PP 合同 `8/8`、完整 S12 `123/123` 通过。qualification=`c3dcd9f` 后从干净 HEAD 运行 Full，manifest 记录同一 commit 与 `working_tree_dirty=false`；Full/report-only 与 accepted/report-only 各 `12/12` SHA-256 一致，历史 Sprint 0.5--4C baseline 无变化。explicit baseline 位于 `prj/tools/sound_sim/s12/benchmark/baselines/sprint-4d-a`，manifest SHA-256=`20D6007D534B967A41BC925CB86C396EAF988EFD9FFF1D8E5AD345C994CCB693`，baseline commit=`2d8c58a`。未 push，未进入 Sprint 4D-B。
- [x] F. Final Release Audit：历史 baseline verifier=`passed`/`changed=0`；FVM transient `model_check=healthy`，closed/open Pipe(G) 各为已治理的精确 21-warning waiver；Code Analyzer=0 issue。最终 `HEAD=2d8c58a`、`origin/main=010537a`、本地 ahead=`5`、`git status=clean`、`git diff --check=clean`。本 Sprint 停止点已到达。

#### Sprint 4D-A Release Audit and Push (2026-07-17)

- [x] A. 从 accepted manifest、artifact hashes、模型 waiver、Code Analyzer、历史 baseline 和 Git 重新复核 4D-A；一致后正常 `push origin main`，禁止 force。
- [x] B. 正常 push：`010537a..2d8c58a` 已推送。local HEAD、`origin/main` 与远端 `refs/heads/main` 均为 `2d8c58afb0861560d18f74837921bd08ffab3e2c`；工作树和 `git diff --check` 干净。随后开始已授权 Sprint 4D-B。

### S12 Sprint 4D-B — Causal Time-Domain Radiation Boundary

> 目标：把冻结的 4D-A `radiation_boundary_package.v1` 转为显式、可回滚、因果、稳定、被动的时域右端开放边界，并接入独立 FVM transient 验证路径。只覆盖零平均流、无凸缘圆管、平面波和小扰动；不更改冻结 Solver、4D-A package 或 Sprint 4C 的 ideal-open/closed 对照。

- [x] A. Release/design freeze：4D-A 已正常 push；已在 `S12_Sprint4DB_Time_Domain_Radiation_Boundary_Design.md` 冻结 characteristic/sign/reference-plane、增广 SSP-RK3 state、rollback 和 pole-time-step 合同。RED 用例已受控失败，仅指向缺失 4D-B stage/reference/model/schema；排除新 RED 后历史回归 `123/123` 通过。Full 前阈值仍待 quick 误差预算后写入 profile。
- [ ] B. RED：状态空间、characteristic、stage/rollback、time-domain reference、schema/report 和 baseline compatibility 的受控失败测试。
  - 进行中：boundary/reference/scheduler/model/schema/PP-step/runner 合同均已先 RED 再 GREEN；受控失败仅指向缺失 4D-B capability，未出现 fixture 或路径错误。
- [ ] C. GREEN：新增独立、受控的 radiation-boundary FVM 模型和 helpers；不复制 HLLC/MUSCL/PP，不使用 clipping/fallback/hidden state。
  - 进行中：stage/reference/SSP-RK3 helpers、radiation-stage `.slx`、最小 FVM runner 已建立；专项 `9/9`、新增模型 `model_check=healthy`、新增 helpers Code Analyzer `0 issue`。尚未达到 Benchmark/Full qualification，不能提升 baseline。
- [ ] D. Benchmark/qualification：单频、多频、脉冲、极限、幅值线性、网格/时间收敛与能量/因果性验证；统一 registry/schema/report-only。
- [ ] E. Release/baseline：专项、全量、Code Analyzer、model_check/精确 waiver、历史 baseline、clean-commit Full、report-only、explicit promotion 和独立 baseline commit；完成后不 push、不进入 4E/Engine/Audio。

#### Sprint 4D-B Runtime Recovery and Runner Evidence (2026-07-17)

- [x] MATLAB 重启后恢复门禁已复核：MCP attach、`new_system`、冻结
  `s12_euler_fvm_periodic_step_muscl_minmod_pp_ref` 单步、boundary/reference/
  SSP-RK3/PP-step 合同均通过。早先 Stateflow 编译失败只记录为前一会话的
  cache/诊断编辑相关状态，不宣称唯一根因；原 crash 证据继续保留在
  `tasks/reports/runtime/sprint-4d-b/`。
- [x] 已实现并测试 validation-only 左端小扰动 characteristic drive、single-
  tone/multisine/chirp/pulse 输入定义、Fast Restart 生命周期和 stage-time
  `c=[0,1,1/2]`；驱动 ghost 的波速已纳入 dt 预估，避免冻结 PP 对被低估 CFL
  的 `CflClipped` 拒绝。专项 runner 合同 `3/3` 通过且驱动 case retry=0。
- [!] 尚未完成 Full：外部 MATLAB loop 对每个物理步执行三次冻结 Simulink
  stage，即使 Fast Restart 也约为 `0.4 s/step`；N=25、`40 us` 最小复现
  `151` 步耗时 `62.99 s`，Quick 两档 single-tone 超过 7 分钟未产生受控结果。
  必须在不复制/修改冻结 HLLC/MUSCL/PP 公式的前提下，建立单次仿真内多步的
  受控组合模型后，才能诚实进行 N=800 Full 与 baseline promotion。

#### Sprint 4D-B Frozen PP Model Provenance Gate (2026-07-18)

- [ ] Recovery plan: audit the unique Stateflow dimension source of truth from
  versioned design/generation sources, accepted manifests, Git history and clean
  detached-worktree smoke; preserve the existing WIP and audit copies unchanged.
- [ ] If and only if HEAD is proven the unique source, restore this one PP model
  from HEAD, add a semantic-contract guard, run dual-environment smoke and all
  historical gates, then resume the existing 4D-B WIP.

- [x] Runtime recovery: MATLAB MCP attach and a temporary Constant→Outport `new_system`
  update/save smoke passed. The exact `HEAD=2d8c58a` PP binary was exported outside
  the repository and cold-load/update/default-sim passed twice, proving recovery of
  the current MATLAB runtime without relying on the working-tree PP model.
- [!] **Hard blocker:** archive/XML audit shows the working-tree frozen PP model is
  not metadata-only: `simulink/stateflow/chart_16.xml` adds `isDynamic=1` to seven
  Stateflow data entries and blockdiagram/system XML also differs. This can change
  compile-time size inference. Under the frozen-model rule it must not be restored,
  committed, or used for 4D-B qualification. Evidence is retained at
  `tasks/reports/runtime/sprint-4d-b/pp-model-binary-diff-audit/2026-07-18/`.
- [ ] Await separately scoped authorization to reconcile the PP Stateflow interface
  configuration with the accepted frozen artifact and run its independent regression.
  Until then do not proceed to radiation-stage smoke, Full matrix, qualification,
  baseline promotion, push, Sprint 4E, Engine, Exhaust, or Audio work.

#### Sprint 4D-B Recovery Confirmed (2026-07-18, takeover session)

- [x] PP model provenance resolved: working-tree PP .slx SHA-256 independently verified equal to HEAD 2d8c58a value DCD32D9C5F4D805AFDEA96CEF9320D874924AD59736E874758AABC67E784D70D; git diff HEAD on the PP model is empty. The 2026-07-18 isDynamic=1 binary diff was the pre-recovery state; the source-of-truth audit is retained.
- [x] Semantic contract guard added: tests/test_s12_pp_model_semantic_contract.m.
- [x] Recovery smoke via matlab-mcp-server connected to existing agentic MATLAB 37988 (matlab -batch crashes in mwhomesessionmanager_impl.dll; MCP evaluate_matlab_code reuses 37988): frozen PP cold-load/update/default-sim PASS; radiation-stage set_param update PASS (model healthy); Code Analyzer 2 NBRAK2 on s12_radiation_input_signal.m L14/L18 fixed.
- [x] Sprint 4D-B special contracts: 12 files / 26 tests, 26 PASSED / 0 FAILED.
- [ ] Full historical S12 regression running (runtests on 37988); result to be confirmed >= 143/143.

#### Sprint 4D-B Nightly Continuous Recovery (2026-07-18)

> Jovi 已在电脑重启后手动启动并确认唯一普通 MATLAB Desktop 稳定。本轮只允许该 Desktop 与一个 existing-session MCP；禁止 `-batch`、`-nodesktop`、第二个 MATLAB、多 MCP、自动杀 MathWorks 服务、保存冻结 PP。持续到 qualification/baseline 完成或真实硬阻塞。

### Current handoff — PP contract frozen; driver work begins

PP port/Stateflow contract completed and frozen. Next: fixed-size driver topology
and one-step harness. Do not enter Full Benchmark, Qualification, or baseline
until driver and performance gates pass.

- [x] Candidate driver semantic audit: valid untracked SLX, SHA recorded, two
  derived core scripts match source hashes, no root feedback/radiation path yet.
- [x] Fixed-size one-step harness: transactional temporary candidate, N=25/100
  compile, one-step smoke, derived-core equivalence, and no frozen PP diff.
- [ ] 2/4/8-step feedback, reset/rollback, external short-run equivalence, and
  performance gate remain after the one-step harness.

- [x] 0. 只读 Git/WIP/PP SHA 审计与当前 crash 证据归档；确认 `HEAD=origin/main=2d8c58a`、PP 无 diff。
- [x] 1. 当前唯一 Desktop 的 MCP attach preflight：记录 PID/release/path/cache/workspace；MCP、`new_system`、PP 双 cold smoke、radiation-stage smoke、专项/历史小组门禁。
- [x] 2. 一次性提取冻结 PP 的 7 In/4 Out、`pFloor`、Stateflow data 和 chart-script 合同；不修改冻结模型。
- [ ] 3. 修复 radiation WIP 的普通 `.m` 缺陷，并实现固定尺寸 one-step/discrete-feedback driver；禁止 While Iterator 与 runtime variable-size。
- [ ] 4. 运行 driver、性能（N=25/100/200）和 Sprint 4D-B 专项门禁；只有安全性能路径存在才继续 Full。
- [ ] 5. 统一 Benchmark 的 Quick、阈值冻结、Full matrix、历史回归、cache-clean rerun、Code Analyzer、model_check/report-only。
- [ ] 6. 创建 qualification commit；从干净提交运行 Full；report-only 哈希一致后显式 accepted baseline promotion 和独立 baseline commit；不 push。
- [ ] 7. 更新 4D-B 文档、Obsidian 和本 Review；确认工作树干净、PP SHA 与历史 baseline 均未变。

##### Review

- 进行中：步骤 0--2 已完成；候选 driver 静态 archive 审计 PASS，固定尺寸 one-step 单调用脚本已完成静态审查但尚未运行。任何 MATLAB crash、`new_system` 失败、clean/active HEAD PP 持续失败、无法 fixed-size 或必须改冻结 PP 时立即停止并保存证据。
- 2026-07-19 单调用门禁：调用前发现同一 Desktop 下存在 15 个 `matlab-mcp-server.exe` 根进程及 15 个 watchdog；按 FAIL-MCP 规则未调用 MATLAB、未结束任何进程，证据见 `tasks/reports/runtime/sprint-4d-b/S12_4DB_PP_Driver_MCP_Lifecycle_Blocker_2026-07-19.md`。
- 2026-07-20 手动单调用进入 driver 构建后因脚本自身 `find_system` 参数顺序和 `connect` string/char 混用失败；MATLAB PID 1788 仍存活、MCP bypass、PP SHA/diff 与 formal candidate 均未变、无 crash。当前仅做离线整类修复，证据见 `tasks/reports/runtime/sprint-4d-b/S12_4DB_PP_Driver_Manual_Run_Script_Failure_2026-07-20.md`。
- 2026-07-20 离线整类修复完成：`find_system` 2/2、`connect` 35/35、静态/mock 56/56 通过；事务 rollback、MATLAB path/file-generation cleanup 与文件打开错误路径已复核，当前状态为 `PENDING_MANUAL_RUN`，未调用 MATLAB/MCP。详见 `tasks/reports/runtime/sprint-4d-b/S12_4DB_PP_Driver_Static_Repair_Audit_2026-07-20.md`。
- [x] 2026-07-20 第二次手动单调用离线修复：RED 为 57 pass/6 fail；执行体已收进局部主函数，事务 cleanup 改为函数局部 `scopeCleanup`，并删除 R2026a 不支持的 `ToWorkspace/LimitDataPoints`。GREEN 为 63/63；冻结 PP SHA/diff、formal candidate SHA、MATLAB/crash/事务输出均已只读复核。状态为 `PENDING_MANUAL_RUN`，证据见 `S12_4DB_PP_Driver_Run_Lifecycle_API_Repair_2026-07-20.md`。
- [x] 2026-07-20 第三次手动单调用离线修复：RED 为 63 pass/4 fail；所有 Constant block 已显式 `VectorParams1D='off'`，保持 `C(1x2)*x(2x1)` 正式公式；cleanup 已改用官方 `setConfig/config` 并最后恢复 path。GREEN 为 67/67；冻结 PP、formal candidate、MATLAB/crash 与 cache 已复核。状态为 `PENDING_MANUAL_RUN`，证据见 `S12_4DB_PP_Driver_Matrix_FileGen_Repair_2026-07-20.md`。
- [x] 2026-07-20 第四次手动单调用离线修复：生成 chart source 中仅有的两处 identifier-only error 已统一补齐消息文本。RED 为 67 pass/2 fail，GREEN 为 69/69；8 个生成/嵌套函数已全量审计，identifier-only error=0，scalar-char chart assignment 保持不变；PP/candidate/crash 完整性已复核。状态为 `PENDING_MANUAL_RUN`，证据见 `S12_4DB_PP_Driver_Coder_Error_Message_Repair_2026-07-20.md`。
- [x] 2026-07-20 第五次手动单调用离线修复：根因为同一 `ambientState=[rho;rho*u;E]` 在右路径被误当 primitive。已对照正式 reference 统一通过 `primitive` 解码，并以 `rho0/p0/c0` 驱动 outgoing、small-signal 与边界重构；2% 门禁未放宽。RED 为 69 pass/8 fail，GREEN 为 77/77；零扰动 outgoing=0，左右公式、PP/candidate/crash 均已复核。状态为 `PENDING_MANUAL_RUN`，证据见 `S12_4DB_PP_Driver_Ambient_Contract_Repair_2026-07-20.md`。
- [x] 2026-07-20 fixed-size one-step integration：Jovi 在唯一 Desktop 手动执行，N=25/100 update+sim、尺寸合同与 derived-core equivalence 全部 PASS；formal candidate SHA=`A48EC97A...230054`，state error=`1.697e-14`，radiation error=`0`，冻结 PP 不变且无新 crash。证据见 `S12_4DB_Driver_OneStep_SUCCESS_2026-07-20.md` 与 one-step JSON。下一门禁为独立 `model_check`，不得直接进入 Full。

##### 2026-07-20 approved continuation plan

- [x] PowerShell-only preflight: one Desktop is healthy, but 10 MCP roots / 10 watchdogs prohibit MCP. Process tree and frozen evidence are recorded in `S12_4DB_Manual_Unified_Path_Preflight_2026-07-20.md`; continuation is a manual unified Desktop script.
- [x] Execute independent three-model `model_check` within the manual unified Desktop script; the 2026-07-21 manual run passed it after transactional candidate rebuild and the read-only integrity post-check, then reached feedback-clone construction.
- [x] Static manual path preparation: source-template/formal-output isolation is RED→GREEN (`77/8 fail` → `92/92 pass`); the unified script's path-role, feedback, cleanup, rollback, repeatability and performance contracts are `107/107 pass`. Readiness evidence: `S12_4DB_Manual_Unified_Static_Readiness_2026-07-20.md`.
- [x] 2026-07-21 candidate `model_check` warning repair: the first unified manual run stopped before feedback because the pre-existing formal candidate exposed PP1/PP2's six intentionally unused outputs as eight root warnings. The generator now consumes only those non-numerical ports with Terminators, and the unified script rebuilds and SHA-validates the candidate before independent `model_check`; frozen PP SHA/Git diff remain unchanged. This is `STATIC PASS`, pending one manual unified Desktop run.
- [x] 2026-07-21 feedback-clone topology repair: the subsequent manual run reached the rebuilt zero-warning candidate and stopped only because the clone replaced two of the eight `U0/X0` bootstrap fan-out branches before deleting the source Constants. `replaceInput` now replaces all four state and four radiation base inputs branch-by-branch, verifies each target is released, then removes `U0/X0`; RED=`64/13 fail`, GREEN=`77/77 pass`. Formal candidate/one-step JSON SHA=`2318DDA0...C605A5`; frozen PP remains unchanged. Pending one manual unified Desktop continuation.
- [x] 2026-07-21 result-collector correction: feedback construction then passed and the first matrix execution exposed invalid zero-field `repmat(struct())` preallocation. The first repair to `struct([])` was wrong and was immediately disproven by the next real MATLAB run: it is still a zero-field structure. The shared `appendStruct` collector now assigns the first scalar structure directly, checks later field compatibility, and appends it; feedback, external-equivalence and performance all use it. RED=`83/14 fail`, GREEN=`97/97 pass`; the static extractor remains exact-function anchored. No MATLAB/MCP call and no `.slx` save occurred during repair. Pending one manual unified Desktop continuation.
- [x] 2026-07-21 external-equivalence evidence gate: the next manual run passed feedback matrix, reset, export/import, package switch and retry/rollback, then stopped at the first old-runner equivalence guard. Driver right-boundary formulas were audited against the old reference and not changed; tolerance was not relaxed. The prior generic error is replaced by fail-fast N/steps plus state/radiation/dt/residual/diagnostics/probe differences. RED=`106/1 fail`, GREEN=`107/107 pass`; pending one diagnostic manual continuation.
- [x] 2026-07-21 new-session recheck: exact process-name gate still finds 10 MCP roots / 10 watchdogs, so no MCP call was made. Desktop, PP/candidate/JSON/crash evidence and both static gates remain unchanged; see the appended manual-path preflight record.
- [ ] Build and verify fixed-size 2/4/8-step feedback, reset/export-import/package switch, retry rollback, and old external short-horizon equivalence.
- [ ] Repair and prove source-template/formal-output separation with two consecutive successful runs before recording any repeatability PASS.
- [ ] Run the approved performance gate and N=800 projection only; stop before Benchmark Registry, qualification, baseline, push, Sprint 4E, PTR, Engine Library, or Audio.
- `2026-07-19` 连接门禁暂停：冻结 PP SHA 和 Git 审计正确，唯一正常 Desktop
  仍存活；但 Codex `app-server` 自动保留了六个 existing-session
  `matlab-mcp-server` 根进程，唯一一次无副作用 Gate 1 查询返回
  `Transport closed`。未重试、未运行 MATLAB/Simulink、未结束 MATLAB 或
  MathWorksServiceHost，详见
  `tasks/reports/runtime/sprint-4d-b/S12_4DB_Nightly_Preflight_2026-07-19.md`。
  必须先恢复为一个可审计的 attached MCP，才可继续步骤 1。
- Codex 重启后的复核：Gate 1、独立 cache、`satk_initialize` 与受控最小
  `new_system` update 均已通过，且冻结 PP 未变；但同一 Codex 会话在后续
  MCP 调用组中再次自动增至三个 MCP 根进程。为遵守单 MCP 门禁，已在 Gate 3
  前停止，不会尝试杀进程触发重连。
- 已确认自动增殖发生在 Codex `app-server` 的 MCP 生命周期；唯一执行 MATLAB
  的仍是第一个 root，后续 root 只有 client-session 启动日志。已准备单调用
  preflight 脚本，待新 Codex 会话中仅调用一次；工具级 `model_check` 不能在
  未验证其 P-code 入口签名时假装已经覆盖，保留为后续独立的单 MCP 门禁。
- 单调用 attempt 1：Gate 1、cache 与 `satk_initialize` 通过；Gate 2 的临时
  Outport 库引用不兼容 R2026a，尚未加载 PP/radiation 模型即停止。已最小改为
  `built-in/Outport`，同一 Codex 会话不重试，等待新的单 MCP 会话。
- 单调用 attempt 2：Gate 2 通过；PP 双 cold smoke 通过且 SHA/Git diff 保持
  冻结；radiation-stage update/sim 后只因 reset probe 参数签名过时而停止。
  已按真实 package/state 签名最小修正，未改 production helper/model；等待新
  的单 MCP 会话。
- 工具级 `model_check` attempt：由于预检已正确关闭 radiation-stage 模型，工具
  本身返回 `MODEL_NOT_FOUND`，未发生模型错误。已准备单调用脚本执行
  load→update→direct `model_check`→close(0)，并要求 `status: healthy`；新
  Codex 会话中仅运行该脚本一次。
- direct `model_check` 通过：`nargin=4`、`status: healthy`，root 的
  unconnected ports/lines 与 Stateflow lint 三项均通过；脚本已 close(0)。至此
  Gate 1--5 的当前 Desktop preflight 全部通过，可恢复 Sprint 4D-B 普通实现。
- 静态极限修复待验证：为 `A=B=C=0, D=-1` 的无状态反射极限建立了独立
  stability/reference 合同，并准备 `s12_4db_static_limit_contracts_2026_07_19.m`；
  它只运行两个纯 MATLAB 测试文件与两个 helper 的 Code Analyzer，不加载或保存
  `.slx`。因单 MCP 规则，必须在下一次新 Codex 会话中单调用执行。
- 已完成 driver candidate 的只读 archive 审计：两个复制的 Stateflow chart script
  分别与冻结 PP / SSP-RK3 source hash 一致；但候选仍只有两个 derived core，尚不
  具备 feedback、fixed-step 或 radiation-state 路径。详见
  `tasks/reports/runtime/sprint-4d-b/S12_4DB_Derived_Core_Static_Audit_2026-07-19.md`。
  下一次 MATLAB 单调用将合并静态极限合同和冻结 PP 全量 port/Stateflow contract
  JSON 提取，之后才读取 candidate 的可编辑模型结构。
- PP contract 第一次生成：静态极限合同 `6/6` 通过、两个 helper Code Analyzer
  通过、Stateflow 11 项 data metadata 已正确写入；但 `find_system` 的深度设置
  使端口数组错误地为空。冻结模型未改且已不保存关闭。已准备一个仅 port-handle
  读取的修复脚本；它要求精确 `7 In / 4 Out` 才覆盖该 JSON，未通过则停止。
- port-handle repair attempt 1：在 JSON record 的字段大小写（`scope`/`port`）
  处安全失败，未进入写入步骤；模型由 cleanup 不保存关闭。已只修正该字段名，
  不在同一 Codex 会话重试。
- port-handle repair attempt 2：已通过 `scope`/`port` 映射，但随后把 JSON record
  当作 Stateflow object 读取 `Name`；同样未进入写入步骤，模型 cleanup 不保存关闭。
  已将 name/unit 统一改为 record 字段，不在同一 Codex 会话重试。
- 在第三次重试前已静态补强：unit 兼容 `Props.Unit` / `Props.Units`，采样时间从
  port parent 读取，且任何 name/type/dimension/sample-time/unit/connectivity 元数据
  不可用都会明确失败并禁止覆盖 JSON。
- port-handle repair attempt 3：port count、name/type/dimension/sample-time/
  connectivity 均已读到；仅 Stateflow API 将 XML 已明确的 `unit=inherit` 显示为空。
  未写入 JSON，cleanup 不保存关闭；现将该空表示规范化为 `inherit`。
- port-handle repair attempt 4：所有 port 元数据读取完成，但 `sample_time` 是多元素
  string，完整性门禁误用标量 `||`；未写入 JSON，cleanup 不保存关闭。已改为 `any(...)`
  聚合判断，不在同一 Codex 会话重试。
- PP 端口合同最终通过：`s12.pp_port_stateflow_contract.v3`，精确 `7 In / 4 Out`，
  输入顺序为 `state,gamma,dx,dtRequest,cfl,rhoFloor,pFloor`，输出顺序为
  `stateNext,dtUsed,residual,diagnostics`，Stateflow data `11`，不可用字段 `0`。
  冻结 PP SHA 仍为 `DCD32D9C5F4D805AFDEA96CEF9320D874924AD59736E874758AABC67E784D70D`。
  合同 JSON 位于 `tasks/reports/runtime/sprint-4d-b/`，下一步可读取 candidate
  driver 的结构，但不得改冻结 PP。

#### Sprint 4D-B Unified Driver Continuation (2026-07-21)

- [x] 离线定位 external-equivalence 的唯一 `diagnostics=6` 失败：N=25、2 step 时 state=`3.39403e-14`，其余 radiation/dt/residual/probe 均为 0；冻结 PP SHA 与 Git diff 均无漂移。
- [x] 对照 external reference，确认生成 chart 的左非反射边界遗漏 ambient exact-fixed-point 早返回；已先用静态 RED 合同证明缺口，再补入 `all(interior == ambient)` 早返回。驱动静态合同 `93/93`、统一脚本静态合同 `115/115` 通过。
- [x] 主 Agent 复用唯一稳定 MATLAB Desktop 完成 unified run：SLX repeatability 改为 archive 语义哈希（排除已证明的 editor-only volatile 条目并统一 Windows 路径），3/3 `model_check` healthy、6 feedback、6 external-equivalence、9 performance、N=800 projection acceptable，最终 JSON 已写入；PP/baseline/crash 门禁均通过。

##### Review

- 本次仅修改 one-step driver 的生成 source、unified repeatability gate、静态合同、计划和经验记录；完整运行只复用既有 Desktop，未启动实例，未触碰冻结 PP/HLLC/MUSCL/positivity。
- 最终 candidate SHA-256：`E4876B8E2E81E4F9F42FCAA9DB086B567A1DDE5A07CA35931260356431B543AF`；冻结 PP SHA-256：`DCD32D9C5F4D805AFDEA96CEF9320D874924AD59736E874758AABC67E784D70D`；PP Git diff 为空，baseline changed=false，new crash dump=false。

#### Future Runtime Boundary — S12 Calibration → V4 PTR

- [ ] 已记录但未授权实施：S12 的离线 FVM/声学结果将导出可审计的车型参数（共振、脉冲、衰减、延迟）；V4+PTR Runtime 将消费参数化 profile。PTR 参考必须独立审计其论文/代码、实时 CPU、音频质量与许可证后再设 Sprint，不能取代 S12 物理验证或提前开始 ESP32/DSP 实现。

#### Sprint 4D-B Acceptance Handoff (2026-07-23)

- [x] Qualification source committed locally: `4afe65a67ed21822422f1eb6dbf43fdd627072d3` (`feat: integrate fixed-size S12 radiation benchmark driver`).
- [x] Clean-commit Full passed: canonical Full suite has 24 cases, the 12 required 4D-B cases, 28 controlled artifacts, `working_tree_dirty=false`, and manifest SHA-256 `A8F3594171AA06180FF47367C34B233CDB2DDB604B0FBEF8D402535F403F7CD5`.
- [x] Report-only replay passed: all 28 controlled artifact hashes match the clean Full manifest exactly.
- [x] Accepted local baseline promoted and committed: `c79c24796e77c4ef26eeeb4f457431311473c4e7` (`test: accept S12 Sprint 4D-B baseline`); no push. Frozen PP remains `DCD32D9C5F4D805AFDEA96CEF9320D874924AD59736E874758AABC67E784D70D`.
- [x] MATLAB lifecycle recovery completed without an MCP call: automatic external MATLAB MCP is disabled, stale registration was recoverably quarantined, and one normal visible Desktop is responsive. Do not re-enable the global MCP registration or start another Desktop.
- [x] Read-only Engine/PTR readiness audit completed in `tasks/reports/runtime/sprint-4d-b/S12_Engine_Sound_Vertical_Slice_Readiness_Audit.md`: no formal PTR definition or S12-to-audio integration exists; legacy Python, MATLAB, V6 and I2S paths remain separate evidence only.
- [x] Created the first formal offline-only PTR design contract at `tasks/reports/runtime/sprint-4d-b/S12_PTR_Network_Design_v1.md`; it explicitly forbids claiming vehicle calibration, real-time fitness, or a completed network before implementation and verification.
- [x] Added and independently reviewed the 4D-B acoustic-boundary audition: commits `4393451`, `dc2f342`, and `14085d3`; two chirp exports have 6/6 controlled artifact hashes equal, a 48 kHz mono native WAV, explicit source/PCM duration quantization, and `clipping_count=0`. Artifacts: `tasks/reports/runtime/s12-acoustic-demo/boundary-chirp-a` and `boundary-chirp-b`.
- [x] Jovi explicitly authorized the additive Engine/PTR/RPM/acoustic-demo source scope. Frozen PP/HLLC/MUSCL/SSP-RK3, accepted 4D-B baseline, and existing V6 assets remain untouched.
- [x] Implemented and independently reviewed the synthetic four-stroke source plus exact/bilinear RPM×Load operating-point library: commits `193d70a` and `f180613`; 9/9 Python tests passed; event rate, zero mean, amplitude bound, synthetic provenance and symmetric common-port firing-order traceability are covered.
- [x] Extended the shared trace/source contract for a time-varying RPM/load schedule, then implemented the PTR transport and low/medium/high load, RPM-ramp and load-step offline demonstrations: `171d1a9`, `c5e38f6`, `5f8cd40`; 12/12 Python discovery tests passed, two controlled demo manifests match exactly (`3EDCD9B419B59D06DF884C4A82039FF2DF17AA24B9C91C8A8D598553B86251BE`), each run contains 10 48 kHz WAVs (20 across the two runs), and clipping is zero per run. This remains synthetic, uncalibrated, offline and not real-time-qualified.

#### S12 Engine Sound Phase-2 — Synthetic Engine Sound v0.2 (2026-07-23)

- [x] Added an independent post-PTR Sound Design Layer with an explicit synthetic four-cylinder/four-stroke order profile, a versioned C/synthetic parameter ledger, continuous RPM phase accumulation, smooth load/transient crossfade, fixed global loudness gain, and 48 kHz/24-bit/stereo rendering. Commits: `8b86157`, `a8e4145`, `f2dd017`, `5114a7e`, and `b1bce86`; FVM/HLLC/MUSCL/Positivity/SSP-RK3/PTR mathematics/4D-B baseline remain untouched.
- [x] Generated five offline demo cases (`idle`, `cruise`, `acceleration`, `throttle_lift`, `high_load`) twice at `tasks/reports/runtime/s12-engine-sound-v0.2/demo-a` and `demo-b`. The root manifests are byte-identical with SHA-256 `F129A150D1BA54B18F2E8357E603441609900E39E574E626D1214F5D049ED749`; each contains exactly five WAVs, five metadata files, and `engine_sound_review.md` (11 controlled files).
- [x] Verified 23/23 Python tests, strict uniform texture rejection, final-output order projection, load 0/0.5/1 high-order/fundamental monotonicity, manifest sentinel isolation, 48 kHz stereo signed-24-bit headers, `clipping_count=0`, zero first/last PCM samples, DC/adjacent-step gates, and deterministic rebuild. `engine_sound_review.md` labels hearing output as automated proxies only; it does not claim human listening or an OEM clone.

##### Review

- Local repository audit after the baseline commit: clean working tree, `git diff --check` passed, baseline approval is `accepted`, and no push occurred.

#### Sprint 4D-B Continuous Time-Domain Radiation Qualification (2026-07-21)

- [x] 审计已授权 WIP：`main...origin/main`、8 个 tracked 修改和既有 radiation implementation/test WIP 均保留；无 cache、raw waveform、crash/log 或冻结 PP diff 混入。已冻结 unified JSON、driver candidate 和 PP SHA 作为输入证据。
- [ ] 将十二个 radiation cases、两个 category、Quick/Full profile、canonical result/schema/report-only 接入既有 S12 benchmark suite。
- [ ] 冻结独立参考、测量、能量/被动性和 Full threshold specification，并以静态合同验证。
- [ ] 编写并静态验证唯一的 `s12_4db_nightly_full_qualification_2026_07_20.m` 事务脚本；它只在最终阶段复用稳定 Desktop 一次。
- [ ] 连续完成 Quick、Full、历史回归、Code Analyzer、model checks 和 structured evidence；普通实现失败持续修复，真实数值/冻结完整性回归才停止。
- [ ] 建立 Qualification commit，随后 clean-commit Full、report-only determinism、官方 accepted baseline promotion 和独立 baseline commit。
- [ ] 更新 S12/benchmark 文档、runtime reports、`tasks/lessons.md`、Obsidian 和记忆索引；完成最终 release audit 后停止，不 push、不进入 Sprint 4E/PTR/Engine Library/Audio。

#### S12 Night Continuation — Approved Handoff Plan (2026-07-23)

> 最新授权取代上段的停止范围：完成 4D-B 后继续到最小 Engine/PTR/RPM library/offline acoustic demo；仍不 push，且不改冻结 PP/HLLC/MUSCL/SSP-RK3 语义、既有 radiation package、阈值/工况物理或已验收 baseline。

- [x] 0. 对旧 nightly runner 做只读硬门限审计：PID 44304 在 90+ 分钟内无 transaction/artifact/stage/final JSON 进展，分类 `C.STALLED_OR_PATHOLOGICAL`；已向可见 Desktop 发送一次 Ctrl+C，未终止任何进程。
- [x] 1. 旧 runner 安全退出后，已实施 4D-B 的最小 observability 与执行路径修复；官方 Quick/Full/category 走 fixed-size multi-step driver，legacy runner 仅保留 1/2/4/8-step equivalence，并保留可恢复 checkpoint、case evidence 与严格 hash identity。
- [x] 2. 静态 contracts、Quick 性能资格、Full、历史回归/Analyzer/model checks、qualification commit、clean-commit Full、report-only determinism、accepted baseline 与 acoustic-boundary demo 均已完成。
- [x] 3. 已在 4D-B clean Full 证据上完成只读 Engine/PTR readiness audit，并建立最小四冲程 source、PTR/network vertical slice、RPM/load library 和 48 kHz 离线合成 demo；所有结果明确不声称实车校准。
- [x] 4. 每个能力已独立提交并复核差异/哈希/测试；S12/Benchmark docs、Obsidian、此 Review 与 lessons 已更新；未 push。

##### Review

- 2026-07-23 当前阻塞只为安全状态：旧 MATLAB child PID 44304 在收到一次可见 Ctrl+C 后仍 busy。等待其自行响应或由 Jovi 在同一 Desktop 做一次 Stop/Interrupt；在此之前不启动第二个 MATLAB、不调用 MCP、不改源/模型/config/schema/threshold，也不将旧输出用于资格或 baseline。
- 2026-07-23 收口：旧运行已安全结束；PTR demo 只读消费 accepted radiation package，未改冻结 FVM/package。短 trace 延迟时长错误经独立复审发现后以 `5f8cd40` 修复并复审通过；最终 Python discovery 12/12、`git diff --check`、双 CLI artifact manifest 均通过，未 push。

#### S12 Engine Sound Review (2026-07-23)

> 范围：只读审核已提交的 engine/PTR 离线声学切片；不修改 FVM、PTR、radiation boundary、SSP-RK3 或声音实现。

- [x] 固定被审计提交和相对 4D-B 基线的改动范围。
- [x] 审核物理边界、参数来源和禁止性车型宣传。
- [x] 运行两次离线生成，比较 SHA，并测量 WAV 连续性、clipping、phase jump、DC offset。
- [x] 生成 `S12_engine_sound_review.md` 并复核报告结论。

##### Review

- 结论为 **FAIL**：新增 offline PTR 与“PTR 不得修改”字面门禁冲突；engine 参数缺少逐项 A/B/C 溯源；load-step 有单帧 `7.264008 Pa` 跳变，且三个固定 load WAV 完全相同。两次 manifest SHA 一致、9/9 Python 测试通过、clipping 为零、DC offset 小于 1 PCM LSB，详情见 `prj/S12_engine_sound_review.md`。

## 2026-07-26 S12 Script-Configured Simulink Audition Model v0.9 v3

> 状态：`generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`。已完成离线源码、合同、静态测试与审计包；未启动 MATLAB/Simulink/MCP，未创建、加载或修改任何 SLX。

- [x] 将 Engine/PTR/Renderer Stateflow I/O 合同改为命名的 `Inputs`/`Outputs`、固定数组尺寸和显式 reset 输入；移除未消费的可调 sample-rate 字段，冻结为 48 kHz / 960 samples / `[18,1]`。
- [x] 重写模型检查、Compile dimensions 解码、精确顶层连线集、Manual Switch 模式、PCM 日志/规范化、真实 PCM metrics gate、promotion/canonical 规划和离线静态测试。
- [x] 发现并记录工作区同名 SLX SHA 与旧审计证据 SHA 不一致；两者均只读保留，重建入口保持硬阻断。
- [x] 生成 v3 审计 ZIP，包含修复源码、合同/测试、双二进制证据、审计清单和静态结果；不含 cache、WAV/PCM、凭据或仓库历史。
- [ ] 等待第三次独立审核；只有书面 `READY_FOR_CONTROLLED_REBUILD` 且完成证据身份协调后，才可进行一次受控 Desktop rebuild。

### Review

- v3 静态合同 10/10、Python `compileall` 和 `git diff --check` 均通过；MATLAB/Simulink/MCP/SLX 操作均为未执行。
- 审计包：`E:\Tesla_speed\audit_packages\S12_Simulink_Sound_Playground_v09_audit_v3.zip`，58 files，100,070 bytes，SHA-256 `0B034F9615C6D5A5EC6958933B7872D54E47883271F9D82360076AEFDC9D5BB0`。
- 包中历史旧证据 SHA 为 `FA91...95C0`，当前工作区二进制 SHA 为 `4324...3CC5`；身份不一致已成为重新构建前的硬阻断条件。

## 2026-07-26 S12 Simulink Sound Playground v0.9 v4 offline readiness

> 状态：`generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`。本轮只允许源码、合同、静态测试和 v4 审计包；不启动 MATLAB/Simulink/MCP，不加载、创建、移动或修改 SLX，不提交、不 push。

- [x] 将历史无效证据、工作区未验证中间件、临时候选、正式修复候选、未来 canonical target 定义为独立 artifact roles，并让 package test 从 package-relative evidence 路径复算两份 SHA。
- [x] 增加显式授权转换：保留 blocked base plan，验证第四审计决定、审计报告/ZIP 文件 SHA、source tree SHA、两份证据 SHA、最小操作白名单及单次 authorization ID 后才派生 runtime plan。
- [x] 迁移 Stateflow 接口到受支持的固定 `double` API；增加 exact I/O collection/readback 检查、五个固定 `[18,1]` checkpoint、四缸/firing-order 合同、first-create quarantine rollback 和 owned-model lifecycle helpers。
- [x] 定义未来唯一 one-shot controlled rebuild orchestrator，按阶段写 fail-fast JSON；默认只返回 plan，禁止直接 builder execution。
- [x] 运行 Python 静态合同 `28/28`，`git diff --check`；未运行任何 MATLAB/Simulink/SLX/PCM/audio 操作。
- [x] 生成并从三个独立解压目录重跑 v4 audit ZIP 的 self-test；最终 ZIP 为 `E:\Tesla_speed\audit_packages\S12_Simulink_Sound_Playground_v09_audit_v4.zip`，74 entries、118,090 B、SHA `CD19E4E5D8EDC0244E20E78C2829F268F7A58D3FDF50C100C0C04F31E59A8309`；最终解压包 static/self-test 为 `28/28`，两份 evidence SHA 均匹配，ZIP 不含 cache。
- [ ] 仅等待第四次独立审核；只有其明确 `READY_FOR_CONTROLLED_REBUILD` 后才允许一次既有稳定 MATLAB Desktop 受控重建。

### Review

- 静态结果不是模型验证：Build、Load、Compile、Simulation、PCM、Audio device、Sensitivity、Repeatability 均为未执行。
- 第三次独立审核报告的声明 SHA 为 `AED9...58BC`，报告字节不在本工作区；审计包仅包含 reference descriptor，绝不伪造报告副本。
- final package source-tree identity 为 `F438CC8EF7984ADD0DE184080782FD873120D2B134E4FDB046373CB150FA396B`（61 files），与工作区同一范围的重算值一致。

## 2026-07-26 S12 Simulink Sound Playground v0.9 v5 offline readiness

> 状态：进行中；只允许源码、合同、静态测试与审计包。禁止 MATLAB/Simulink/MCP、SLX 操作、commit 与 push。

- [x] 建立 v5 TDD 计划并以 21 项合同获得 RED 证据。
- [x] 将 future transaction、authorization claim、temporary candidate 与输出目录迁移到源树外的 runtime root；source SHA 改为显式 immutable allow-list。
- [x] 新增 preflight contract、active compile/term helper、真实 `[18,1]` reshape/source layout、fail-fast evidence runner、单变量 sensitivity、双运行 repeatability、可见 cleanup 与 formal-candidate failure manifest。
- [x] 运行 v3/v4/v5 Python 静态合同：50/50 PASS；没有启动 MATLAB/Simulink/MCP 或操作 SLX。
- [x] 生成 v5 ZIP、在两个全新目录解压并运行 self-test；随后仅等待第五次独立审核。

### Review

- v5 ZIP：`E:\Tesla_speed\audit_packages\S12_Simulink_Sound_Playground_v09_audit_v5.zip`，SHA-256 `E518BC1833797018329F00A76D63E4C27A005FFA147D34915E1A79C15B3FA4B2`，143,665 B，90 staging files / 97 ZIP entries；无重复或禁入 entry。
- staging 与最终 fresh extract self-test 均 PASS；v3/v4/v5 静态合同合计 50/50 PASS；包内 immutable source tree 与工作区均为 `83BC1F18A2B4D82CECEBD66D93363B0C4F54821BD2BED5275D77BDE3C5B6207D`（76 files）。
- 仍仅为离线源码证据：Build、Load、Compile、Simulation、PCM、Audio、Direct listening、Sensitivity 与 Repeatability runtime 均未执行；状态保持 `generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`。

## 2026-07-26 S12 Simulink Sound Playground v0.9 v6 minimal offline closeout

> 状态：进行中。授权仅覆盖第五次独立审计确认的离线封包/合同修复；不启动 MATLAB、Simulink、MCP，不加载或修改 SLX，不提交、不 push。

- [x] 固定唯一 canonical source tree，并以一个冻结快照生成全部 source-SHA 声明。
- [x] 静态补齐 crash 时间线、原子全局 active-run lock、PCM artifact 调用与量化 sensitivity 合同。
- [x] 生成一个无顶层重复源/测试、slash-only ZIP entry 的 v6 审计包，并由新鲜 PowerShell 解压自检。
- [x] 仅报告离线证据；状态保持 `generated but not validated` / `NOT_READY_FOR_CONTROLLED_REBUILD`，等待第六次独立审计。

### Review

- v6 审计 ZIP：`E:\Tesla_speed\audit_packages\S12_Simulink_Sound_Playground_v09_audit_v6.zip`；immutable source SHA `B7E4543575617421D80CE8F606AD6AB7051365EA8133B87CA965ECFEC060591E`（86 files）。第五次审计报告的原始字节不在本机范围内，因此包内保留其声明 SHA 的 availability descriptor，而非伪造副本。
- Python static v3/v4/v5/v6 为 58/58；fresh-extract self-test 通过。Build/Load/Compile/Simulation/PCM runtime/Audio runtime/Sensitivity runtime/Repeatability runtime 均未执行。

## 2026-07-27 S12 Simulink Sound Playground v0.9 v8 offline closeout

> 状态：被 2026-07-27 的产品闭环连续执行授权取代；不再制作 v8 审计 ZIP。已经完成的根因定位保留为 Runtime Proof 修复输入，未执行 MATLAB/Simulink/MCP/SLX 操作。

- [x] 已完成根因静态定位：授权绑死历史审核、时变 scenario repeatability 少参、workspace signal 未 finalization、锁释放有 unlock window、final report 早于释放、preflight 进程语义含糊。
- [x] 新的连续授权明确禁止继续创建审计版本循环；本节停止，不生成 v8 ZIP。

## 2026-07-27 S12 Sound Playground to Android product closure

> 状态：最新连续执行授权已重新激活完整产品闭环，但 Runtime Proof 仍是 Phase 1 前的硬门禁。当前为 `MANUAL_RUNTIME_REQUIRED`；没有真实 PASS 前，Dashboard、Package、等价性、Android 和 calibration 均保持锁定。

- [x] 新增无 promotion/canonical migration 的 temporary-candidate Runtime Proof 编排与 source-level 合同。
- [x] 修复 scenario finalization、时变 repeatability 和 runner 双表示一致性。
- [x] 静态验证 Build/Port/Cold Reload/Update/Compile/3 scenarios/PCM/3 sensitivity/repeatability/device-smoke 阶段顺序，且不含 MATLAB launcher。
- [ ] Runtime Proof 真实 PASS 后，依次进入 Dashboard、Package v0.3、Simulink-runtime equivalence、Android closed loop 和 calibration workflow；每阶段独立自审。

### Review

- Runtime Proof 与历史 v0.9 静态合同：`85/85 PASS`；既有 PC/Android/Python 回归：`84/84 PASS`；`git diff --check` PASS。
- 当前进程仅有响应中的 `MathWorksServiceHost` / `MathWorksServiceHost-Monitor`，没有 MATLAB Desktop 或 MATLAB MCP；未启动、连接或重试 MATLAB。
- Build、Cold Reload、Update、Compile、Simulation、PCM、Sensitivity、Repeatability 与 Device Audio Smoke 均为 `NOT RUN`。当前真实状态仍为 `MANUAL_RUNTIME_REQUIRED`，不是 Runtime Proof PASS。
- Dashboard v0.10、AudioParameterPackage v0.3、Simulink-PC equivalence、Android closed loop 与 calibration workflow 均未开始；没有 commit 或 push。

## 2026-07-27 S12 Simulink Sound Playground v0.9 Runtime Proof closeout

> 当前状态：`MANUAL_RUNTIME_REQUIRED`。本节的源码收口继续作为产品闭环 Phase 0；最新连续授权规定真实 PASS 后继续后续阶段，而不是在 Runtime Proof 后停止。

- [x] 保留唯一 scenario finalization 与 round-trip，修复时变 repeatability 参数比较，固定真实 Reshape + Signal Specification `[18 1]`，runner failure 落盘后 rethrow。
- [x] 新增唯一手动入口 `s12_sound_playground_runtime_proof_once.m`；固定临时模型 `S12_Sound_Playground_RUNTIME_PROOF_TMP.slx`，输出仅位于 `tasks/reports/runtime/s12-playground-runtime-proof/<run-id>/`。
- [x] 将 Gate 明确分为 Temporary Build、Port Contract、Cold Reload、Update Diagram、Active Compile Dimension Readback、三场景、PCM、Parameter Sensitivity、Repeatability、Device Smoke、Report。
- [x] 以 RED→GREEN 验证新合同；最新 v3–v7 + Runtime Proof 静态回归 `88/88 PASS`，既有 PC/Android/Python 回归 `84/84 PASS`，`git diff --check` PASS。
- [x] 修复首次实际调用暴露的 progress 结构体字段不一致：typed empty stage-record array 使 fail-fast 记录可在首个 Gate 成功或失败时追加；新 RED→GREEN 合同已加入。
- [x] 修复第二次实际调用暴露的 JSON writer 不兼容：删除 R2026a 不存在的 `fflush`，由 `fclose` 完成 flush；新 RED→GREEN 合同已加入。
- [ ] 由 Jovi 在唯一稳定 MATLAB Desktop 中执行一次唯一手动命令；不启动 MATLAB/MCP，不自动重试。

### Review

- 当前为一个可见 MATLAB Desktop root（PID 7072）及其 Catapult child（PID 1304），没有 MATLAB MCP；首次手动调用已安全返回，但没有可用的 Build/Compile/Simulation 证据。
- Build、Port、Cold Reload、Update、Compile、Simulation、PCM/WAV、Sensitivity、Repeatability 和 Device Smoke 全部仍为 `NOT RUN`，不得写 `RUNTIME_PROOF_PASSED`。
- 没有创建新审计 ZIP、promotion、canonical migration、qualification commit、commit 或 push。
- 2026-07-27 首次手动调用在 `temporary_build` 的失败记录追加处停止：`progress=struct([])` 与带 7 字段的 stage record 不兼容，掩盖了 operation 的原始异常；该空 run 目录保留，不作为 Build 证据。修复后静态合同为 `89/89 PASS`，canonical SLX SHA 仍为 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`。本次允许只再运行一次以收集真实首个 Gate 结果。
- 2026-07-27 第二次手动调用已越过 progress 追加，说明 `temporary_build` operation 已返回；随后在 stage JSON 写入处发现 R2026a 无 `fflush`，临时 JSON 因未关闭而保留。该 run 不产生可用 stage evidence。修复后静态合同为 `90/90 PASS`，canonical SLX SHA 未变；本次允许再执行一次以取得真实 fail-fast Gate 结果。

## 2026-07-27 S12 Runtime Proof Atomic JSON writer repair and single continuation

> 当前状态：`RUNTIME_PROOF_FAILED_BEFORE_VALIDATED_BUILD`。本轮只修复 Runtime Proof 事务内 JSON 原子写入、精确 owned-temp 句柄收敛和非 Simulink 自测；不启动/连接 MATLAB，不创建新离线审计版本，不迁移 canonical，不提交或推送。

- [x] 只读审计 `runtime_proof_20260727_081025_562`，冻结为 `FAILED_AT_STAGE_EVIDENCE_WRITE`；不得复用其临时模型或 Build 结果。
- [x] 以测试先行方式完善 atomic JSON writer 的关闭、解析、SHA 与替换合同，杜绝 `fflush` 与关闭前 delete/move。
- [x] 新增仅关闭当前 Runtime Proof transaction 下 `.s12_playground_json_*.tmp` 的 owned-handle helper，并审计所有写入 helper。
- [x] 新增不加载 Simulink/不创建 SLX/不操作音频设备的 atomic-writer self-test，并让唯一入口在 Build 前 fail-fast 运行。
- [x] 运行静态回归与 `git diff --check`；验证 canonical SLX SHA 前后保持 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`。
- [ ] 静态证据合格后，由 Jovi 在当前唯一稳定 MATLAB Desktop 手动续跑一次；任一新 Gate 失败即保留首错并停止。

### Review

- 只读 transaction 审计：唯一 `.tmp` 为 1,472 B，仍被进程锁定，SHA 无法读取；stage/progress/error JSON 与 SLX 均不存在。详见 `tasks/reports/runtime/s12-playground-runtime-proof/runtime_proof_20260727_081025_562_readonly_audit.md`。
- 新 writer 只在目标目录创建临时 UTF-8 文件；写后检查字节数、显式关闭精确 file ID、解析临时 JSON、验证 SHA、同目录 atomic move 后再解析并验证目标 SHA。失败 cleanup 仅关闭其 owned file ID 后删除其 owned temporary path。
- `openedFiles` helper 仅匹配指定 transaction 下 `.s12_playground_json_*.tmp`，不使用 `fclose('all')`；唯一入口会依次清理旧 transaction 的精确泄漏、执行 writer self-test、核对 canonical SHA，再进入新 Runtime Proof。
- v3–v7、Runtime Proof 和 package 静态合同为 `94/94 PASS`；Python compileall 与 `git diff --check` 通过。Runtime Proof 尚未续跑。

## 2026-07-27 S12 Runtime Proof continuation preflight

> 状态：`BLOCKED_PENDING_MANUAL_DESKTOP_RUN`。本轮仅恢复并重新核验运行前证据；未调用 MATLAB/MCP、未创建临时模型、未重试 Runtime Proof。

- [x] 恢复唯一手动入口、fail-fast Gate 顺序与失败 run 的不可复用边界。
- [x] 新鲜运行 v3–v7、Runtime Proof 与 package 静态合同：`94/94 PASS`；`compileall` 与 `git diff --check` 通过。
- [x] 核对 canonical `S12_Sound_Playground.slx` SHA-256：`43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`；active-run lock 不存在。
- [x] Jovi 在唯一可见 MATLAB Desktop 中完成一次 `shareMATLABSession` 后运行唯一入口；它在 preflight 的 atomic-writer self-test 停止，尚未创建临时模型或进入任何 Simulink Gate。
- [x] 以 RED→GREEN 修复 `Files.createFile` 的 Java varargs 调用：显式传递空 `FileAttribute[]`，并仅对真实 name collision 重试；未知 Java 错误保留原始消息 fail-fast。静态回归更新为 `95/95 PASS`。
- [x] 通过唯一 shared Desktop 的 existing-session MCP 执行一次 `s12_sound_playground_runtime_proof_once.m`；它在 preflight 的 `publishTemporary` 停止，`java.nio.file.Paths.get` 的 varargs 签名不兼容。未创建临时模型，未进入 Build/Compile/Simulation/PCM/Audio Gate，未重试。
- [x] 停止运行后，以 RED→GREEN 将 writer 的全部 Java Path 构造收敛为唯一 `java.io.File(...).toPath` helper；MATLAB Code Analyzer 为 0 issues，静态回归更新为 `97/97 PASS`。
- [ ] 等待 Jovi 对下一次唯一 existing-session Runtime Proof 的明确授权；本次 source repair 之后不得自动重跑。

### Review

- 当前主机存在一个 MATLAB Desktop root，但同时存在 6 个 existing-session MCP roots/watchdogs；因此本轮不经 MCP 运行 Runtime Proof。
- 最新一次实际调用的首错为 `reserveTemporaryPath`，根因是遗漏 `Files.createFile(Path, FileAttribute...)` 的空 varargs；该失败不是 Build、Load、Compile、Simulation、PCM 或 Audio 证据。
- 唯一 MCP 续跑后，writer 成功越过 temporary reservation，却在 publish 的 `Paths.get` 再次停止；根因升级为所有 Java `Paths.get` varargs 的 MATLAB 兼容性。对应 self-test 目录保留为失败证据，未清理。
- Runtime Build、Port、Cold Reload、Update、Compile、三场景、PCM、Sensitivity、Repeatability、Device Smoke 与 Report 仍均为 `NOT RUN`；不得写 `RUNTIME_PROOF_PASSED`。

## 2026-07-27 S12 Runtime Proof full source audit and agent execution

> 状态：`RUNTIME_PROOF_FAILED`。两次受控 Runtime Proof 均已由 Agent 在唯一共享 Desktop 执行并按首错停止；当前授权的两次上限已耗尽，尚无 Build/Compile/Simulation/PCM/Audio 通过证据。

- [x] 保存并保留历史失败 transaction；canonical SLX SHA 保持 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`。
- [x] 统一 SHA scalar helper，清零 Playground/tests 中的直接 SHA `==`/`~=`；条件审计 56/56，无已知非标量风险。
- [x] 以共享 Desktop 运行 MATLAB helper suite：16/16 PASS、0 failed、0 incomplete；writer self-test 包含 100 次连续写入。
- [x] Code Analyzer：87 files / 0 issues；Python Playground static：101/101 PASS；compileall、git diff --check 通过。
- [x] 生成 `tasks/reports/runtime/s12-playground-runtime-proof/S12_Runtime_Proof_PreExecution_Audit.md`。
- [x] Agent 通过唯一 existing-session Desktop 执行首轮 Runtime Proof；新 transaction `runtime_proof_20260727_235314_781` 的 atomic writer self-test 通过，但 `temporary_build` 以 `MATLAB:badformat_mx` 停止。无候选模型、无 Simulink Gate 证据；transaction 已保留且不可复用。
- [x] 以 RED→GREEN 测试修复 `%#codegen` 被 `sprintf` 当作格式指令的问题；生成的 Engine/PTR/Renderer MATLAB Function 脚本均为 string scalar，16/16 MATLAB helper tests 通过。
- [x] Agent 通过唯一 existing-session Desktop 执行最后一次 Runtime Proof；新 transaction `runtime_proof_20260728_000341_503` 的 preflight 通过，`temporary_build` 以 `MATLAB:lang:DotIndexingFunctionRequiresParentheses` 停止。错误位置为 `setChartScript` 的 `sfroot.find(...)`；cleanup 已关闭临时模型/库，无 candidate SLX、无 compile/simulation/PCM/audio 证据。
- [x] 输出 `tasks/reports/runtime/s12-playground-runtime-proof/S12_Runtime_Proof_Final_Report.md`，冻结两次受控执行的完整结论与下一修复循环所需的新授权边界。

## 2026-07-28 S12 Runtime Proof Stateflow root-access recovery

> 状态：`RUNTIME_PROOF_FAILED`。本轮两个受控 Runtime Proof 均由 Agent 在唯一 existing-session MATLAB Desktop 执行并按首错停止；上限已耗尽，保持 canonical SLX 不变、无 commit/push/promotion。

- [x] 保留 `runtime_proof_20260728_000341_503` 证据，扫描 Runtime Proof 源码中所有 `sfroot` 调用并确认影响范围。
- [x] 先新增真实 MATLAB 回归：错误的未调用 root access 必须被检测；正确的 `sfroot().find` 必须可执行。
- [x] 最小修复 builder，运行 MATLAB tests、Code Analyzer、Python static、compileall、canonical SHA 与锁/句柄门禁。
- [x] 由 Agent 在唯一 shared Desktop 执行本轮首次 Runtime Proof；新 transaction `runtime_proof_20260728_203058_064` 越过 `sfroot()` 后，在 Stateflow `[18,1]` 固定尺寸 readback 的双反斜杠正则处 fail-fast。无 candidate SLX、无 Update/Compile/Simulation/PCM/Audio 证据。
- [x] 新增 fixed-size parser MATLAB RED→GREEN 回归，并只修复该 regexp；完整门禁升至 MATLAB 18/18、Code Analyzer 89/0、Python 101/101。
- [x] 由 Agent 在唯一 shared Desktop 执行本轮第二次、最后一次 Runtime Proof；新 transaction `runtime_proof_20260728_203521_183` 已越过 Stateflow root 和 fixed-size parser，在 Engine Excitation 的 `packed` 接口 readback 发现 `IsDynamic=true`（合同要求 `false`）而停止。无 candidate SLX、无 Update/Compile/Simulation/PCM/Audio 证据。
- [x] 固化最终证据到 `tasks/reports/runtime/s12-playground-runtime-proof/S12_Runtime_Proof_Final_Report.md`；未运行第三次 proof。下一轮需新的授权，且先研究 live Stateflow dynamic-property 语义与数据创建时序。

## 2026-07-28 S12 Runtime Proof compile-clean authorization

> 状态：`RUNTIME_PROOF_PASSED`。最终 transaction 为 `runtime_proof_20260728_223501_287`；13 个阶段全部通过，runtime-only unknowns 为 0。始终只使用当前 shared Desktop，未启动第二个 MATLAB，未要求 Jovi 运行命令，未 commit/push/promotion。

- [x] 保留 `runtime_proof_20260728_203521_183`，以最小 live chart 复现 `IsDynamic` 写入与 readback 语义。
- [x] 先新增失败的真实 MATLAB 回归，再实施最小 Stateflow interface 修复。
- [x] 每轮修复后运行 MATLAB helper suite、Code Analyzer、Python static、compileall、writer、句柄、锁与 canonical SHA 门禁。
- [x] 持续执行新的 fail-fast Runtime Proof，逐个解决首错，直至 Build、Update Diagram、Active Compile PASS。
- [x] 让编译通过的同一次 proof 继续完成 Simulation、PCM、Sensitivity、Repeatability、Device Smoke 与 Final Report，并按实际证据收口。

### Review

- Stateflow interface：MATLAB Function 输入端按 R2026a 的继承语义校验尺寸/类型/Scope；输出端继续强制 `IsDynamic=false`。真实 MATLAB 回归先复现 `S12:Playground:StateflowDynamic`，修复后通过。
- Compile workspace：Update/Compile 前向候选模型自己的 Model Workspace 发布固定 `[18,1]` synthetic idle 帧，读回尺寸、有限值和 scenario SHA；不保存候选模型，不污染 canonical。
- Sensitivity：RPM、Load、Acceleration pair 只改变一个目标输入，其他控制量保持常量；RPM `13.3→50 Hz`，Load RMS 增量 `0.0042676`，Acceleration delta RMS `0.00311096`。
- 最终验证：MATLAB Runtime helpers `21/21`、Code Analyzer `91 files / 0 issue`、Python static `101/101`、compileall、`git diff --check` 均通过。Atomic writer 100 次连写后临时文件/句柄均为 0。
- Runtime Proof：Build、Port、Cold Reload、Update、Active Compile、Idle/Cruise/Acceleration、PCM、三类敏感性、Repeatability、2 秒 Device Smoke、Final Report 全部 `PASSED`。
- Compile dimensions：configuration `[18,1]`、excitation `[960,1]`、pressure `[960,1]`、PCM `[960,2]`。
- 三场景均为 48 kHz、双声道、10 秒、500 帧、clipping 0、finite=true；idle 重复运行 PCM/WAV/参数/场景/metrics SHA 全部一致。
- Candidate SHA 在所有运行 Gate 前后保持 `D26CD70C231316A36B3F2ED3BFE107D0BAF2051D05897726B4AB0D0DA173BBB9`；canonical SHA 保持 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`。
- 收尾状态：candidate model、`dspsnks4`、MATLAB file handles 均为 0；active lock 不存在。删除了本轮临时诊断模型产生的唯一 autosave；历史 transaction 和正式证据均保留。

## 2026-07-28 S12 multi-configuration Engine Sound Playground v1.0

> 状态：`TECHNICALLY_VALIDATED_OFFLINE_PENDING_JOVI_AUDITION`。该平台独立于已验证 v0.9；不修改 v0.9 canonical、FVM/HLLC/MUSCL/SSP-RK3、PTR 数学核心或 Radiation Boundary。只使用当前唯一 shared MATLAB Desktop；不启动第二个 MATLAB，不 commit、push 或 promotion。

- [x] 建立 JSON-only profile truth、7 个 synthetic 内置构型、严格 provenance/schema validator，并以 RED→GREEN 覆盖非法缸数、点火顺序、RPM、数组长度、缺失来源和未知字段。
- [x] 建立固定 90 秒/4,500 帧 vehicle-cycle compiler 与确定性回火时表；验证时间连续、有限状态、高转收油窗口和 off/subtle/aggressive 分级。
- [x] 建立 profile-driven excitation、PTR/Radiation adapter、stereo renderer、48 kHz/24-bit WAV publication 与完整/分段 artifact manifest；所有输出仅进入 runtime report 根。
- [x] 建立 MATLAB API、custom-profile revalidation、JSON parameter snapshot、单变量敏感性、复现 SHA 及使用/风格对比文档。
- [x] 以 `model_edit` 建立共享 `S12_PTR_Renderer_Core_v10` 和 7 个独立顶层模型；逐一执行 Cold Reload、Update Diagram、Active Compile、`model_read`、`model_check`。
- [x] 逐构型完成 90 秒真实 simulation、PCM/WAV/analysis/manifest、repeatability 与完整测试；仅据新鲜执行证据更新最终状态。

### Review

- 入口基线：Git HEAD `1bf88fb`；v0.9 canonical `S12_Sound_Playground.slx` SHA-256 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`；workspace 无 `playground_v10`。
- v1.0 风格名称仅表达 synthetic 方向，绝不表示 OEM 数据、真实车型复刻或实车标定。人工听感仍由 Jovi 确认，Device/PCM 测试不替代听感判断。
- 交付模型：7/7 `model_read` 均确认 `Vehicle State Mode Select`、Dashboard 和 `S12_PTR_Renderer_Core_v10`；7/7 `model_check` healthy；7/7 Cold Reload + Update Diagram 通过。
- 模型仿真：每个构型两次完整 90 秒、4,500 个 `[960,2]` PCM frame，finite、peak<1、block-boundary 连续且每个构型内 PCM SHA 一致。
- WAV 发布：7 个 profile 各两份完整 package，PCM 与 `SHA256.txt` 清单逐 profile 完全一致；输出仅在 `tasks/reports/runtime/s12-engine-sound-v10`。
- 成品 WAV 检查：7/7 `full_drive_cycle.wav` 均为 48 kHz、24-bit、stereo、90.0 s，finite 且 clipping=0。
- 新增 MATLAB 测试 `33/33`、Python static `3/3`、18 个新增 MATLAB 源 Code Analyzer `0` issue、文本 trailing whitespace `0`、`git diff --check` 通过。v0.9 canonical SHA 仍为 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`。
- 未提交、未 push、未 promotion；下一人工步骤仅为 Jovi 试听和选择后续调音方向。
# 2026-07-29 S12 八车型声纹仿真与回火重构 v1.1

> 状态：`PASS_OFFLINE_AUDIO / PASS_SIMULINK_BUILD_COMPILE / SIMULINK_90S_SIMULATION_NOT_AUTHORED`。隔离工作树：`E:\Tesla_speed\worktrees\s12-v11`，分支：`feature/s12-v11`。不得修改 v0.9 canonical、v1.0、FVM/HLLC/MUSCL/SSP-RK3、PTR core 或 Radiation Boundary；不得提交或推送。

- [x] 八车型 JSON parameter provenance 与 loader 真值消费的静态实现；所有 render-affecting 参数为 A/B/C record，未确认 OEM 事实保持 synthetic/pending。
- [x] deterministic stateful pre-PTR afterfire 的静态实现：整周期/refractory、thermal/lift/derivative eligibility、非等间隔簇和 profile/scenario seed。
- [x] Hellcat、C63 W204、Ferrari 458 试点与其余五车的离线源码、分析、API 与模型合同静态实现；fresh v1.1 Python static contracts `85/85 PASS`。
- [x] 八个独立模型已由唯一 existing-session Desktop 生成；8/8 Build、Cold Reload、Update Diagram、compiled `[960,2]`、`model_check(["all"])` healthy。
- [x] 八车型各生成两轮完整 90 秒离线 PCM/WAV package；每车 12 个文件，48 kHz、24-bit、stereo、4,320,000 samples、finite、peak<1、clipping=0，完整 `SHA256.txt` 两轮一致。
- [x] Runtime 修复：兼容 R2026a JSON 数组方向、Windows `copyfile` 目录语义、cycle scalar struct、Dashboard/HMI 参数类型、Interpreted MATLAB Fcn `Output1D`、Model Reference Inport 维度、builder 重建幂等性及 compiled-dimension 编码；PTR wrapper 只缓存冻结 adapter 的已验证路径/SHA，未修改 PTR/Radiation 数学。
- [x] 新鲜回归：Python static `85/85 PASS`；MATLAB provenance/analysis/afterfire/cycle/firing-map/JSON/pilot behavior/model tests `67 PASS + 1 intentional filtered`；pilot 完整发布合同由真实双次 Hellcat package 和逐字相同 SHA 清单独立证明；`git diff --check` PASS。
- [ ] v1.1 源码仍没有 `sim(..., 90s)` 或等价 90 秒 Simulink Simulation 验收入口；不得把离线 90 秒 WAV 或 Update Diagram/Compile 描述成 90 秒 Simulink simulation。
- [ ] 人工听感仍待 Jovi 试听确认；当前全部为 `synthetic / uncalibrated / offline / not OEM clone`。
- [ ] 2026-07-29 受控 runtime preflight：清理重复 MATLAB MCP/watchdog 后仅剩一个 watchdog；唯一 existing-session 的只读健康探测返回 `Transport closed`。MATLAB Desktop 与 MathWorksServiceHost 均存活，未进入 MATLAB、未创建 SLX/WAV/PCM/runtime 目录；按 fail-fast 规则不自动重试。
- [ ] 2026-07-29 MCP transport repair plan: (1) read-only trace Codex config, process ownership and logs; (2) identify the exact transport boundary that closes; (3) apply only one reversible bridge repair after evidence; (4) re-check one existing-session connection; (5) only then execute one fail-fast v1.1 run.
- [ ] 2026-07-29 repair result: `[mcp_servers.matlab]` remains `--matlab-session-mode=existing` and Desktop still listens on `127.0.0.1:31516`; a single Codex-owned MATLAB MCP root/watchdog group is live. Desktop UI refresh is blocked by Windows `0x80070005`, and the one fresh-root read-only probe again returned `Transport closed`. This is a Codex↔MCP stdio blocker, not a MATLAB crash; no further automatic retry, model run, or artifact creation is allowed pending an app-level bridge recovery.
- [ ] 仅在明确授权下处理 `tools/sound_sim/s12/tests/__pycache__/` 的 15 个被忽略 `.pyc`；当前 Hygiene=`NOT_PASS/P2`。

## Review

- 八车首轮输出：Hellcat 位于 `task3_contract_20260729_212325_222`，其余七车位于 `v11_all8_20260729`；第二轮分别位于对应 `_repeat` 目录。
- 八车 PCM SHA：Hellcat `1239a62b...fd4a1`、GT-R `068e9d3c...ce80f`、C63 `5bbefdf8...274e`、Supra `8e3b1caf...36d60`、RX-7 `1a497279...c411e0`、LFA `90d29788...05fbf`、Ferrari 458 `94bfe5b0...7389d`、Aventador `698ec471...c453e`。
- v0.9 canonical SHA 复核仍为 `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5`；未 commit、未 push、未 promotion。

# 2026-07-30 S12 八车型原厂声纹逼近 v1.2

> 状态：`IN_PROGRESS`。分支：`feature/s12-v12-reference-calibration`；worktree：`E:\Tesla_speed\worktrees\s12-v12`；基线：`0c8ae6a`。目标为八车原厂 stock、车外尾部、参考声纹引导的 synthetic offline 声浪，不修改 v0.9/v1.0/v1.1 或冻结物理核心。

- [x] 量化 v1.1 声纹不足：91 个渲染参数中 60 个完全相同；Hellcat/Supra 与 Ferrari/Aventador 的最小合成特征距离虽超过旧 `0.05` 门限，但仍不足以保证可听区别。
- [x] 完成官方车型资料、SAE 阶次/排气研究和开源方法审计；所有未测量的 OEM 阶次、点火相位和 afterfire 参数仍保持 synthetic/pending。
- [x] 精确清理 v1.1 untracked SDD scratch、过期乱码 handoff、过期忽略计划和 15 个 ignored Python cache；未删除 runtime 证据、v1.0/v1.1 或冻结物理文件。
- [x] 从 `0c8ae6a` 创建隔离 v1.2 worktree。
- [x] 建立 R1/R2/R3 原厂参考录音清单和 reference-analysis 合同：25/25 静态测试及独立只读审查通过。R1 目标仅由完整清单绑定的瞬态 PCM 重算；当前尚无真实媒体或最终 acoustic target。
- [x] 完成八车首轮公开候选筛选并写入 `playground_v12/common/reference_analysis/REFERENCE_SCREENING_V12.md`：所有候选均明确保留为 R2/listening-only 或 R3/rejected；零个 R1，零个校准 target。
- [x] Task 2 静态实现及独立复核：阶次合同统一为 0.5–18；JSON Schema、Python 语义预检和 MATLAB 验证器均覆盖范围/拓扑/有限标量；RX-7 固定为 2 rotor / 3 chamber / 3:1，且消除了 rotor loop 的事件率重复计数；显式路由为 `source [960,2] → bank mixer → pre-PTR [960,1]`，未改 PTR/Radiation。2026-07-30 全部 v1.2 静态门禁 35/35、`compileall`、`git diff --check` 通过；独立复核 PASS（仅静态）。
- [x] Task 2 MATLAB source-core 门禁：唯一可见 Desktop + 单一 existing-session MCP 下，4 个 v1.2 MATLAB 源 Code Analyzer 均为 0 issue；新增真实 MATLAB 测试并完成 RED→GREEN，3/3 PASS，覆盖三款试点 profile、`[960,1]` pre-PTR、有限值、确定性、跨帧状态和 RX-7 比率拒绝。
- [ ] Task 2 PTR/Radiation 接入门禁：4D-B 是已接受的时域 Radiation Boundary 基线；现有 Python `RuntimePtrAdapter` 是冻结二状态边界包加确定性延迟/损耗的轻量音频适配器，不是完整 FVM/PTR 网络。先以包 SHA、来源提交、连续状态和因果测试锁定最小接入，不得把 v1.1 的 synthetic audition adapter 或该轻量适配器宣传成完整物理 PTR。
- [x] Task 2 最小 Radiation adapter：新增 MATLAB 等价适配器，锁定 4D-B package SHA `0f4b2c...d2d6f` 和 source commit `4afe65a...`; MATLAB 6/6 source→radiation 因果/分块/状态测试通过，Python/MATLAB 1920 样本交叉摘要仅有浮点运算次序量级差异。诊断固定 `full_fvm_ptr_network=false`。
- [x] Task 2 试点 Simulink 运行门禁：共享 `S12_Frozen_Radiation_Adapter_v12` 与 Hellcat/Ferrari 458/RX-7 三个顶层模型完成磁盘 cold reload、结构 healthy、Update Diagram、Active Compile；compiled source `[960,1]`、radiation `[960]`、PCM `[960,2]`。三车 0.20 s 真实 simulation 均为 `[960,2,11]`、finite、peak<1；Hellcat 重复数组逐元素相同。
- [x] Task 3 三车试点 90 秒驾驶循环与发布：三款 synthetic scenario 均有 C 级 provenance；4500 帧完整 source 回放和离散 transient 边界通过。三车真实 Simulink 90 秒均为 4500 帧、`4,320,000 x 2` samples、finite、clipping=0，并发布 48 kHz/24-bit/stereo full/idle/acceleration/deceleration/afterfire WAV。
- [x] Task 3 三车试点重复性：两轮完整 Simulink→WAV 重建 SHA 一致。Hellcat `2e58346b...c24c406`；Ferrari 458 `8a939d5e...dfb13e`；RX-7 `0905034b...e1f664a`。
- [ ] Task 4 八车扩展与 reference fitting：其余 GT-R/C63/Supra/LFA/Aventador 尚未建立 v1.2 source/model/WAV；当前仍无 R1 参考音频，因此三车也尚无 acoustic target、reference distance 或真实原厂拟合证据。
- [ ] 先完成 Hellcat/Ferrari 458/RX-7 reference-guided fitting，再扩展余下五车。
- [ ] 逐车执行真实 Simulink 90 s simulation、WAV publication、SHA repeatability、reference-distance 和 Jovi 盲听。

### Review

- 当前没有任何 v1.2 reference audio、target、model、WAV 或 runtime validation 证据；不得提前写 PASS、calibrated 或 OEM clone。
- 2026-07-30 三车试点已新增 model/WAV/runtime evidence，上句“没有任何 model/WAV”仅适用于该句记录时点；当前仍没有 R1 reference audio、acoustic target、reference distance 或 calibration 证据。
- 原始研究媒体只可位于 `E:\Claude_allow\Download\tesla-sound-research-v12`，Git 只保存 URL、片段时间、SHA 和派生指标。
- Task 1 复核（2026-07-30）：`python -m unittest tools.sound_sim.s12.tests.test_s12_engine_sound_v12_reference_analysis -v` 为 25/25；独立复核确认完整 R1 清单绑定、转义 URL/媒体拒绝、事件簇时间边界和本地 RPM + 60% 持续 formant。该证据只覆盖合同，不证明公开媒体的真实原厂属性。
- 2026-07-30：Hellcat、458、RX-7 的公开候选仅已外置下载用于后续人工审核；Hellcat 因候选标题为 Charger 而非目标 Challenger，已降为 R3/rejected；458 与 RX-7 仍为 R2/listening-only。三者均未提升为 R1、未生成 acoustic target、未参与数值拟合或写入 Git。
- 2026-07-30：Jovi 授权后已只停止 10 个 `matlab-mcp-server.exe`/watchdog；MATLAB Desktop PID 43768/52368 与 MathWorksServiceHost 未触碰，复核 MCP=0。当前 Codex 会话的 existing-session stdio transport 因清理而 closed；一次只读版本/PWD health check 在 MATLAB 执行前 fail-fast 为 `Transport closed`，未重试、未运行脚本/模型。必须重建单一 Codex transport 后才可进入 MATLAB gate。
- 2026-07-30 Codex 重启后单一 existing-session 恢复；本轮末识别并只停止 14:19:57 产生的重复 MCP 组 `48768/28656`，保留原组 `70808/8728`。MATLAB `43768/52368` 与两个 MathWorksServiceHost 始终响应，未终止或重启。

# 2026-07-30 S12 v1.2 声源级与加速瞬态分层修复

> 状态：`PASS_OFFLINE_AUDIO / PASS_SIMULINK_RUNTIME / PENDING_JOVI_AUDITION`。范围仅限 `E:\Tesla_speed\worktrees\s12-v12` 与本任务记录；不修改冻结版本，不提交、不推送。公开视频仅作 R2 听感参考，不作标定或真实性声明。

## 实施清单

- [x] 核验 MATLAB MCP 控制面：一次只读工具箱探测成功连接现有 R2026a Desktop；未启动或停止 MATLAB、MCP 或 watchdog。
- [x] RED：新增恒定加速度回归测试，并在旧实现取得失败证据：起始 transient energy `6.0466`，连续四帧后反增至 `17.8476`。
- [x] GREEN：`s12_v12_render_source_frame.m` 仅将加速层改为加速度变化触发、每帧内指数衰减；稳态 source level 继续由燃烧、负荷、节气门和阶次层组成。
- [x] 扩展测试：新增相同负荷/节气门下 2500→8000 RPM 的稳态源级上限；旧实现 `2.939 dB` 失败，新实现 `0.378 dB` 通过。瞬态静态衰减、重触发和既有源帧合同均通过。
- [x] 在同一已有 MATLAB Desktop 中运行 v1.2 离线 MATLAB 测试，并重导出 Hellcat、Ferrari 458、RX-7 三个完整驾驶循环；生成独立的固定线性试听增益 `×8`，无自动增益或限幅。
- [x] 复核准确 diff、测试输出和生成音频；运行时证据见下方 Review。

## Review

- `test_s12_v12_source_core_matlab.m`：有效 RED 后，fresh-cache MATLAB `11/11 PASS`；`s12_v12_render_source_frame.m` 与测试文件 Code Analyzer 均为 `0 issue`。
- Python v1.2 reference/source/profile contracts `35/35 PASS`，`git diff --check` PASS。未提交、未推送；worktree 既有 `.gitignore` 修改与既有 untracked v1.2 文件均保留。
- 三车真实 Simulink 90 秒输出位于 `tasks/reports/runtime/s12-engine-sound-v12/source_level_decoupled_20260730`：均为 48 kHz、24-bit、stereo、4,320,000 samples、finite、clipping=0。SHA：Hellcat `aa4da110...127b388`；Ferrari 458 `0337917e...3d00cc9`；RX-7 `cc926277...9df78de`。
- Ferrari 458 独立重复渲染 SHA 仍为 `0337917e...3d00cc9`。固定试听增益 `×8` 全程 WAV 位于 `source_level_decoupled_gain_x8_20260730`；输出峰值 Hellcat `0.231908`、458 `0.344893`、RX-7 `0.275273`，均未削波。
- Jovi 提供的 Ferrari 812 GTS Novitec POV 已登记为跨车型、改装、近舱 R2 听感参考；不用于 458 或任一 stock v1.2 车型的数值拟合。

# S12 Engine Identity Acoustic Model v0.14 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task with RED→GREEN evidence.

**Goal:** 为 Hellcat、Ferrari 458、RX-7 FD 在冻结 PTR/Radiation 前新增 synthetic、uncalibrated 的 Engine Identity Layer，并发布可试听的身份 demo。

**Architecture:** 每车独立 `engine_identity_profile.json` 经过严格 provenance validator 和 loader，生成 PTR 前的双 bank `[960,2]` identity excitation。该帧与现有 combustion/order/exhaust source 合成后继续走原有 bank mixer、frozen PTR/Radiation 和 renderer；PCM 接口仍为 `[960,2]`。

**Tech Stack:** MATLAB R2026a、Simulink、JSON Schema Draft 2020-12、Python unittest/jsonschema、现有唯一 visible MATLAB Desktop。

## Global Constraints

- 仅修改 `E:\Tesla_speed\worktrees\s12-v12` 的 v1.2 声源侧和任务/运行报告；不改 v0.9/v1.0/v1.1、FVM、PTR core、Radiation boundary、runtime latency 或 Android protocol。
- 全部 identity 参数为 `A`/`B`/`C` provenance record；本轮均为 `C / synthetic / uncalibrated`，禁止写 OEM measured、calibrated 或 OEM clone。
- 保持 48 kHz、960 sample source frame、bank mixer 输入和所有 Simulink 端口不变；不在 renderer/PTR 后追加 EQ、limiter 或 synthesis。
- 只复用当前唯一 existing-session MATLAB Desktop；不得启动第二个 MATLAB，不 commit、不 push。

### Task 1: Identity profile schema and validation

**Files:** create `common/schemas/engine_identity_profile_v04.schema.json`, `common/s12_v12_validate_engine_identity_profile.m`, `common/s12_v12_load_engine_identity_profile.m`, three `vehicles/<profile>/engine_identity_profile.json`; test `tests/test_s12_engine_identity_v014.{m,py}`.

- [x] Write schema/loader RED tests requiring the exact v0.4 fields, C/synthetic provenance and rejection of an unprovenanced numeric parameter; run them and retain the expected missing-function/profile failure.
- [x] Implement strict JSON Schema plus MATLAB loader/validator; fill three synthetic profiles for flat-plane V8, supercharged cross-plane V8 and twin-rotor turbo.
- [x] Run Python static profile tests and fresh-cache MATLAB tests; confirm profiles validate and malformed provenance is rejected.

### Task 2: PTR-pre identity excitation

**Files:** create `common/s12_v12_render_engine_identity_frame.m`; modify `common/s12_v12_render_source_frame.m`; test `tests/test_s12_engine_identity_v014.m`.

- [x] Write RED tests requiring Ferrari 2k→9k high-frequency identity energy to rise continuously, Hellcat whine energy to rise with load, and RX-7 rotary pulse/turbo diagnostics to expose nonzero time-structure events.
- [x] Implement the smallest identity renderer: Ferrari flat-plane high-order sharp excitation; Hellcat separate V8 exhaust and load-gated supercharger whine; RX-7 rotor pulse train plus deterministic turbo spool/turbine texture.
- [x] Wire the finite `[960,2]` identity banks before the existing bank mixer/PTR handoff; preserve existing frame and source API contracts.
- [x] Run fresh-cache MATLAB RED→GREEN tests and Code Analyzer for every new/modified MATLAB source.

### Task 3: Separation metrics and listening demos

**Files:** create `common/s12_v12_publish_identity_demo.m`; modify `common/s12_v12_publish_pilot_audio.m`; test `tests/test_s12_engine_identity_v014.m`; create runtime report.

- [x] Write RED test at 3000 RPM that calculates spectral centroid, order energy and harmonic ratio for all three profiles and requires pairwise identity separation.
- [x] Implement metrics and demo publisher; publish `idle`/`acceleration`/`lift`/`full_pull` plus exact `hellcat_identity_v01.wav`, `ferrari_identity_v01.wav`, `rx7_identity_v01.wav` names.
- [x] In the existing Desktop run all three 90-second Simulink models and verify 48 kHz/24-bit/stereo/finite/no clipping.

### Task 4: Audit report and final verification

**Files:** create `tasks/reports/runtime/s12-engine-identity-v014/S12_Engine_Identity_v014_Report.md`; modify `tasks/todo.md`.

- [x] Produce the report with exact code/profile boundaries, measured separation metrics, published SHA values, runtime gates, and required synthetic/uncalibrated limitations.
- [x] Run all v1.2 Python tests, identity MATLAB tests, `git diff --check`, and graph impact/review after the write watcher updates; record only fresh evidence.
- [x] Stop after the report and audition files exist; do not commit or push.

## Plan Review

- Spec coverage: independent schema, three required identity mechanisms, separation measurements, four listening segments, exact named WAVs, report and all frozen-boundary restrictions are covered by Tasks 1–4.
- Design boundary: identity is generated before the existing source-to-PTR handoff; no post-PTR tone/EQ path is introduced.
- Status: `COMPLETE_SYNTHETIC_UNCALIBRATED` — all requested implementation, verification, report, and audition artifacts exist; no commit or push.

## v0.14 Review

- New profile schema/validator/loader, three C/synthetic/uncalibrated identity profiles, and an explicit pre-PTR `[960,2]` identity renderer were added only inside the v1.2 worktree.
- Ferrari high-frequency energy rises continuously through 9000 rpm; Hellcat exposes independent exhaust and load-gated whine; RX-7 exposes rotary events and turbo/turbine state. Identity RMS is normalized by load/throttle so RPM changes timbre and event rate rather than steady source loudness.
- Fresh MATLAB verification: identity plus existing source-core `19/19 PASS`; fresh Python v1.2/profile/source/reference contracts `37/37 PASS`; Code Analyzer returned 0 issue for all seven changed/new MATLAB sources.
- Fresh 90-second Simulink WAV packages exist under `tasks/reports/runtime/s12-engine-identity-v014`; each of the three cars has total/idle/acceleration/lift/full-pull artifacts, 48 kHz/24-bit/stereo, finite samples, and clipping=0.
- No commit, push, promotion, FVM/PTR/Radiation modification, runtime-latency change, or Android-protocol change occurred.

# S12 Engine Acoustic Identity v0.15 Continuous Execution

> 状态：`IN_PROGRESS`。批准架构为三套独立 Python offline authoritative source + shared post-source infrastructure。设计：`tasks/plans/S12_Engine_Acoustic_Identity_v015_Design.md`；计划：`tasks/plans/S12_Engine_Acoustic_Identity_v015_Implementation_Plan.md`。

- [x] Phase 1：真实车辆声学研究数据库、目标 JSON 与严格 provenance 合同。具体视频及配置限制已落盘；12/12 focused PASS；独立审查 APPROVE。
- [x] Phase 2：Ferrari flat-plane、Hellcat supercharged HEMI、RX-7 rotary turbo 三套独立声源 RED→GREEN。29/29 focused PASS；独立审查 APPROVE。
- [x] Phase 3：40–200 Hz causal engine-body/exhaust-pressure/mechanical-weight resonance，证明不是标量增益。37/37 focused PASS；独立审查 APPROVE。
- [x] Phase 4：bundle-level fixed loudness gain、LUFS/RMS/peak/dynamic range、headroom cap。双声道能量求和回归通过；无逐段 AGC。
- [x] Phase 5：车辆特定 identity metrics、stereo spectrogram、dynamic order map。50/50 focused PASS；独立审查 APPROVE_TASK4。
- [x] Phase 6：同 RPM/load/acceleration/duration、单位 RMS 分析副本与统一 master loudness A/B 比较。三对 correlation/order-distance 均 PASS。
- [x] Phase 7：生成 `identity_v02` 五段试听、图、metrics 与审核报告。正式目录含 15/15 WAV、6/6 PNG、逐车 metrics、同状态比较、3 份报告与 28 项非自引用 manifest。
- [x] Phase 8：修复速度耦合响度、固定墙钟机械音、Ferrari 非因果 metallic、final/pre-PTR 域混用与旧发布布局；未降低门限。15/15 WAV 回读均 >= -30 LUFS、峰值 <= -1 dBFS、零削波，三对 final-PCM A/B 均 PASS。
- [x] 最终：完整回归、冻结边界与两轮独立只读审查全部 PASS。状态为 `AUTOMATED_IDENTITY_PASS / HUMAN_BLIND_AUDITION_PENDING_JOVI`；未 commit、未 push。

### v0.15 Review

- 正式发布目录：`tasks/reports/runtime/s12-engine-acoustic-identity-v015`；29 个磁盘文件，manifest 覆盖除自身外的 28 项且 SHA-256 全匹配，最终 manifest SHA-256 为 `3c851c082e0010fa64e784feaa0f097175c886ec1777ec6fc25e56bfdc4bb9b4`。精确要求的 `S12_Engine_Acoustic_Identity_v015_Report.md` 存在，旧短名不存在。
- Fresh 回归：既有 v1.2 Python 合同 `35/35 PASS`；精确命名后 v0.15 完整套件 `58/58 PASS`；`compileall` 与 `git diff --check` PASS。
- v0.14 `playground_v12` 44 文件树 SHA-256 仍为 `63222b75c7b5a3c6fc85db3fb89ac5dbaf6cd4cfda869a10de622ea00f8daed3`；冻结 runtime PTR adapter SHA-256 仍为 `fdb594838ada4e2867f0ee1d2ea64a53788c1feb6593f7f37c5caf7bae494cb5`；未修改 MATLAB、Simulink、Runtime、Android、PTR core、FVM 或 Radiation boundary。
- 独立最终复审结论：`APPROVE_TASK5`；精确报告命名重发后的复审为 `APPROVE_EXACT_NAME`，无 P1/P2。
- 自动指标只证明候选分离与音频健康；最终人耳身份结论必须由 Jovi 盲听，当前不得写完整 perceptual PASS。
# 2026-08-02 S12 Engine Acoustic Realism Calibration v1.0

> 状态：`AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`。代码仅限 `E:\Tesla_speed\worktrees\s12-v12\tools\sound_sim\s12\acoustic_identity_v015`；输出仅限 `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10`。保持 `synthetic / uncalibrated / not OEM reproduction`，不修改 MATLAB、Simulink、FVM、PTR core、Radiation、Runtime 或 Android，不 commit/push。

- [x] 建立可审计真实声学参考数据库：保留 A/R2/C provenance、录音与改装风险、RPM/工况置信度、STFT/order/transient 方案；公开视频只作 qualitative/listening-only，不提升为 OEM 标定。
- [x] 以 RED→GREEN 增加怠速循环波动和机械层，三车 idle 时间结构已可测分离且与 engine phase 锚定。
- [x] 将低频层升级为状态驱动的 pressure pulse → exhaust coupling → body resonance → radiation；Hellcat 40–200 Hz fraction=`0.8830`，Ferrari=`0.4161`，RX-7=`0.3474`。
- [x] 增加由高 RPM、closed throttle、load/thermal proxy 共同触发的 deterministic afterfire，并增强 Hellcat blower 与 RX-7 spool/boost/BOV 状态。
- [x] 建立 realism metrics 和同工况 A/B；发布四段试听 WAV、图、JSON、比较/真实性报告，完成 v1.0 `8/8`、v0.15 `58/58` 与冻结边界核验。
- [ ] Jovi 人工盲听：确认 Ferrari 高转金属/NA、Hellcat 低频/whine、RX-7 rotary/turbo 是否首次试听即可明确识别；自动 PASS 不替代此结论。

### v1.0 Review

- `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10\manifest.json` 已逐项复算：24 个签名产物和 12 个 48 kHz/stereo/PCM24 WAV 全部通过。
- 同工况 final-PCM 三对 A/B 均 PASS；不把该结果写成 OEM 或人耳 PASS。
- 未 commit、未 push；工作树仅包含本阶段声源、分析、数据库、测试改动。
- 2026-08-04：保留原 3 秒包，另行发布 `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10-30s`。12 段均为 48 kHz/stereo/PCM24、`30.000020833 s`（含一个端点采样）、固定 `-16 LUFS`；24 个签名产物、v1.0 `8/8` 与 A/B 全部 PASS。

## 2026-08-04 S12 complete drive-cycle audition reissue

> Status: `COMPLETE_SYNTHETIC_AUDITION_CANDIDATE / HUMAN_AUDITION_PENDING`. Scope is only the isolated Python offline acoustic source/publisher. No FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, or Simulink modification.

- [x] Reproduced the audition defect: the supplied `full_pull.wav` keeps throttle open, so the state-dependent afterfire gate correctly remains inactive.
- [x] Defined one continuous 30-second review trajectory per vehicle: `idle → acceleration → full pull → high-RPM lift/afterfire → coast → idle`; lift happens at 18 s and has a closed throttle event.
- [x] Wrote and observed the RED regression contract; it failed on the missing drive-cycle publisher, then passed after the minimal continuous state renderer was added.
- [x] Published three standalone 48 kHz/stereo/PCM24 `drive_cycle.wav` files with plots, JSON metrics, SHA manifest, and an explicit timing/event report at `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10-complete-drive-cycle-30s`.
- [x] Re-ran v1.0 `9/9` and v0.15 `58/58`; every final WAV is `1,440,001` frames / `30.000020833 s`, finite and unclipped. Afterfire counts are Ferrari `43`, Hellcat `38`, RX-7 `30`; the 13-entry manifest recomputes exactly; frozen adapter SHA remains `fdb594838ada4e2867f0ee1d2ea64a53788c1feb6593f7f37c5caf7bae494cb5`; protected-path diff is empty and `git diff --check` passes.

### Review

- The new review link must be the continuous drive-cycle WAV, never `full_pull.wav` alone. The artifact remains synthetic, uncalibrated, and not an OEM reproduction; human audition is still the acceptance gate.

## 2026-08-04 S12 acoustic realism phase-review package

> Status: `REVIEW_PACKAGE_COMPLETE / HUMAN_AUDITION_PENDING`. This is a documentation/audit handoff only; no source parameter, runtime, physics, Android, MATLAB, or Simulink behavior changed.

- [x] Read the live formal artifacts, current worktree, S12 task ledger, relevant Obsidian v0.15 reuse record, source/layer parameters, and Git state.
- [x] Wrote a detailed reviewer report with completed work, exact parameters, formal metrics, reflection, pending work, evidence limits, real blockers, and authorization-gated next options.
- [x] Packaged the three 30-second PCM24 WAVs, per-car JSON/plots, formal report/manifest, source/layer/test snapshots, task plans/ledger and Obsidian context into `E:\Tesla_speed\tasks\reports\runtime\S12_Acoustic_Realism_Phase_Review_2026-08-04.zip`.
- [x] Re-opened the ZIP and verified all 42 manifest members by SHA-256; the archive contains all three expected WAVs (`25,920,150` bytes total), no raw media/cache, and a matching SHA-256 receipt `d0232c1e773ae47d90eb0526aad0d28d2f946b447929e7d3a5bbec730564c781`.

### Review

- Jovi feedback recorded: Hellcat low-frequency character is partially convincing, but the actual playback level is still too low. This is an audition calibration gap, not proof that the engine source or the current fixed digital master should be blindly amplified.
- Next action awaits Jovi's review of the package and authorization for a narrowly bounded Hellcat fixed-master A/B or a source-level low-frequency articulation experiment.
# S12 Stage C Deep Realism Integration (2026-08-09)

- [x] Phase 0: record `c08eb4c` baseline tests and three-anchor old-pipeline audition.
- [x] Phase 1: add eight-vehicle realism profiles and RED contracts.
- [x] Phase 2: implement pre-equalization, pressure-coupled rumble, shift dynamics, and deterministic afterfire refactor.
- [x] Phase 3: integrate `_render_stateful`, extend drive cycles and metrics to eight vehicles.
- [x] Phase 4: generate before/after/A-B and eight-vehicle review artifacts.
- [x] Phase 5: run full verification, write report/lessons, and make local commits only; Stage C evidence was preserved and Stage D remains on the same local branch.

Review: focused Stage C, realism, identity, deep-realism, and Track-P gates are green; full regression and local commit split are complete.

## S12 Stage D Human Listening Deep Realism Calibration (2026-08-09)

- [x] D0：锁定 `a5d0481` 基线、参考 target/manifest SHA、Stage C 试听包和 fresh test evidence。
- [x] D1：以 TDD 建立 Stage-D candidate schema、typed loader、candidate renderer 和 `candidate=None` bit-identical 合同。
- [x] D2：实现 Ferrari idle/metallic、Hellcat PTR 前 transient peak shaping、RX-7 rotary/turbo candidate overlay。
- [x] D3：建立 final-PCM reference-distance evaluator，修复 RX-7 target/manifest 可用状态一致性并执行 30% improvement gate（结果 PARTIAL，未降低门禁）。
- [x] D4：建立两轮 15 题匿名盲听包、sealed answer key、response validator、confusion matrix 和 3 组 60 秒 full-cycle A/B 附加包。
- [x] D5：生成三份 candidate JSON、试听包和自动报告；停止等待 Jovi 答卷。
- [ ] D6：按答卷进行最多三轮窄范围候选迭代；不伪造人耳结果，不降低门禁。
- [x] D7：写入 Stage-D 报告并同步 Obsidian 项目影子知识库；Stage-D local commits 已完成，Stage-E 在独立分支继续。

Review：Stage D 的自动指标、身份 confusion matrix 和人耳真实性偏好是三个独立证据层；没有 Jovi 答卷时只能标记 `WAITING_FOR_JOVI_AUDITION`。

# S12 Stage E Human Audition Calibration (2026-08-09)

- [x] E0：从本地 Stage D `4e363c6` 建立独立 Stage E worktree；记录远端仍为 `a5d0481`，不把本地 8 个提交写成已推送。
- [x] E1：以 TDD 修复 Candidate 参数可达性、Candidate overlay 位于公共 Pre-PTR EQ 之前，以及 Hellcat steady blower 不被 transient shaper 压缩。
- [x] E2：建立 Stage E Candidate v2 schema、参数 usage diagnostics、正确的双轮 scorer、播放环境校验和防泄漏试听包。
- [x] E3：生成三车 Candidate v2、final-PCM reference distance、listener ZIP、sealed key、SHA256 清单；没有答卷时停止等待。
- [ ] E4：收到 Jovi 答卷后固化 SHA、校验 30/30 与三组 A/B，读取 sealed key 并输出分轮 confusion/realism 结果。
- [ ] E5：最多三轮只修改失败车型及对应层；另两车 PCM SHA 必须保持不变。
- [x] E6：记录 Stage E 自动回归、Track-P guard、reference distance 和人耳结果；当前状态为 WAITING_FOR_JOVI_AUDITION。
- [x] E7：更新 Obsidian 并生成 cleanup inventory；本轮不删除任何文件。

Review: Stage E candidate v2 and anonymous listener package are generated. Focused Stage E `11 passed`; Stage C realism `9 passed`; identity `58 passed / 78 subtests`; full regression `440 passed / 232 subtests`; Track-P guard `21/21`. No Jovi response has been supplied, so no confusion matrix or human realism PASS is claimed. Cleanup inventory is review-only with `approved=false`.

## 2026-08-10 S12 Stage F human audition qualification

- [x] F0：从 Stage E `3c2c891b` 建立独立 `agent/s12-stage-f-audition-qualification` worktree，保持 Stage E v2 证据只读。
- [x] F1：新增 Stage-F vehicle-specific candidate contract、source/idle/layer parameter usage diagnostics、RX-7 rotary pulse-width/release reachability。
- [x] F2：新增 final-PCM band-distance helpers；参考门禁仍需以实际 v3 evidence 重新测量，不能沿用历史 PARTIAL 数字。
- [x] F3：新增 v3 listener package builder，生成匿名双轮模板和三组真实 A/B 文件；首次包交付后停止等待 Jovi。
- [x] F4：新增 fail-closed response validator、sealed-role scorer 和分轮人耳门禁。
- [ ] F5：收到 Jovi 真实答卷后最多 v3→v4→v5 窄范围迭代；当前无答卷，禁止执行。
- [ ] F6：自动+人耳同时通过后生成 ProfileFreezeCandidate；当前 `NOT_PERFORMED`。
- [x] F7：完成 Stage-F 全套回归、Obsidian frontmatter 修复和知识库同步；生成 v3 报告、证据清单与本地待提交变更。

Review：Stage F fresh full regression、完整 v3 试听包和 Obsidian 同步已完成；reference-distance 保持 `PARTIAL / AUTOMATED_GATE_FAIL`，人耳答卷尚未返回。在 Jovi 返回三份真实输入前，最终状态只能是 `WAITING_FOR_JOVI_AUDITION`。

## S12 Stage G automatic qualification closure and blind audition v4 (2026-08-10)

- [x] G0：核验 Stage F `e38fe62f`、工作树 clean、Stage F v3/Stage E source manifest/候选/报告/Obsidian SHA；标记 v3 historical/unscored，不修改旧字节。
- [x] G1：新增 state-specific reference target loader；每个车型三状态独立读取，SHA 和 availability fail-closed。
- [x] G2：输出 labelled final PCM reference evidence；同一 60 秒 trace、明确窗口、extractor provenance、双跑确定性。
- [x] G3：新增 Stage G candidate contract、v4 profiles、逐参数 requested/consumed/unused 和单参数扰动证据。
- [x] G4：修正 final-PCM band-distance 域，执行 9 状态、identity、Hellcat、RX-7、Ferrari 自动门禁；结果为 `PARTIAL / AUTOMATED_GATE_FAIL`，未降低门禁。
- [x] G5：新增严格 Stage G response validator/scorer；答卷缺失时保持等待，不读 sealed。
- [x] G6：生成匿名 v4 listener/answer-key ZIP、三组连续 60 秒 A/B、预填 30/3 表、SHA256SUMS，并完成防泄漏扫描。
- [x] G7：首次包交付后硬停止；当前没有真实答卷，不执行评分/调音/ProfileFreezeCandidate。
- [x] G8：运行 focused/full/Track-P/diff 验证，生成仓库报告和 Obsidian 更新，只提交本地。

### Stage G review

- Base commit：`e38fe62f423b1fb220e9daedf5f4ef291bcc5849`。
- Branch/worktree：`agent/s12-stage-g-qualification-closure` / `E:\Tesla_speed\worktrees\s12-stage-g-qualification-closure`。
- Current status：`WAITING_FOR_JOVI_AUDITION`；自动参考距离为 `PARTIAL / AUTOMATED_GATE_FAIL`，mean improvement `-0.2459%`。
- Tests：Stage-G focused `17 passed`；package contract `2 passed`；Stage-C realism `9 passed`；Identity `58 passed / 78 subtests`；full S12 `474 passed / 232 subtests`；Track-P `21/21`。
- Package：30 anonymous clips、6 full-cycle A/B WAV、listener ZIP `031520b7...567f64`、answer-key ZIP `038e06ae...a96dd5`；sealed key 未读取，confusion matrix 未生成。
- Reference evidence：9/9 state available，但 mean improvement 未达到 30%，因此没有 ProfileFreezeCandidate。
- 禁止：读取 sealed key、虚构答卷、删除历史/缓存、push、merge、rebase、进入 Approved/Simulink/Runtime/Android。

## 2026-08-10 S12 Stage H Hellcat perceptual calibration

- [x] H0：从 Stage G `60bca7c` 建立独立工作树，冻结 Stage G v4 字节和 SHA；匿名 P01/P02/P03 反馈保持未映射。
- [x] H1：补充 Hellcat 双螺杆/旁通公开事实与 B/R2 合成目标，所有调音参数保持 C/synthetic。
- [x] H2：以 TDD 实现确定性的负载/增压耦合 whine、sideband、bypass release 和 Stage-H Candidate v5。
- [x] H3：执行 Hellcat 专属阶次、侧带、whine/load、低频和峰值门禁；不替换 Stage-G 30% reference gate。
- [x] H4：生成具名工程试听包，明确每个 WAV 的绝对路径，并停止等待 Jovi 具名反馈。
- [ ] H5：收到具名反馈后最多三轮，只修改失败车型，另外两车 PCM SHA 保持不变；当前尚未收到反馈。
- [ ] H6：具名校准通过后再生成 Stage-H 匿名盲听/A-B 包；没有三份正式答卷前不解封评分。
- [x] H7：完成实际测试、报告、知识库同步和本地提交准备；禁止 push/merge/rebase/Simulink。

### Stage H review

- Base commit：`60bca7cccac91c520a12c0b058f3f70d56dcf4b8`；branch/worktree：`agent/s12-stage-h-hellcat-perceptual-calibration` / `E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration`。
- Current status：`WAITING_FOR_JOVI_NAMED_CALIBRATION`；Stage G sealed key 未读取，匿名 P01/P02/P03 未映射。
- Tests：Stage-H focused `14 passed`；Stage-G focused `12 passed`；Stage-C realism/identity `67 passed / 78 subtests`；full S12 `488 passed / 232 subtests`；Track-P `21 passed`；guard script OK。
- Named package：`E:\Tesla_speed\review_packages\s12-stage-h-hellcat-perceptual-calibration-v1\`；first automatic-fail render preserved separately as `...-v1-r1-automated-fail`。
- Final PCM reference distance：Hellcat average improvement `8.479%`，未达到 30%，所以自动状态仍为 `PARTIAL / AUTOMATED_GATE_FAIL`；这不阻止具名试听，但不允许 Profile Freeze。
- Review：Stage H 首次执行目标是 `WAITING_FOR_JOVI_NAMED_CALIBRATION`，不是 Human PASS、Approved 或 Profile Freeze。

## 2026-08-11 S12 Stage I Hellcat whine voicing planning

- [x] I-P0：核对 Stage H `6ee4b1a`、干净 Git 状态、自动指标、试听包、任务账本和 Obsidian 当前状态。
- [x] I-P1：把 Jovi 的 Hellcat 不像、目标“滋滋哟”、第 2 个高频刺耳/低频很好、第 3 个很好但可优化拆成明确车型目标与未绑定编号反馈。
- [x] I-P2：检索 Stellantis/Dodge 官方资料和 SAE 增压器 NVH/进气传播资料，明确 2.36:1、14,600 rpm、电子旁通以及“排气轰鸣 + blower whine”的证据边界。
- [x] I-P3：生成 Stage I 详细执行计划，限定为 Hellcat Track-S 音色/遮蔽/时序校准；Ferrari/RX-7 在 file_id 绑定前保持 SHA 冻结。
- [x] I0：收到 Jovi“执行此计划”授权后，从 `6ee4b1a` 建立独立 Stage I 工作树并冻结证据；Stage H focused `9 passed`、Track-P `21 passed`。
- [x] I1：以 RED/GREEN 测试修正 attack/release/bypass 和纯音集中度的可观测性，并生成绑定 response probe 证据。
- [x] I2：实现 deterministic phase ripple、order cluster、intake/casing voicing 和 boost-history bypass。
- [x] I2-R1：关闭独立审查的 strict bool gate、probe/profile/PCM SHA 绑定、顺序低内存 60 秒渲染、四图进入 ZIP、requested/read/active 参数诊断等问题。
- [x] I3：执行有界候选搜索并输出 A/B/C 三种诊断取向；三者 `all_pass=false`，没有硬门合格候选、没有自动选择，不得把诊断取向写成合格候选。
- [x] I4：正式 builder 已改为默认 fail-closed；因 A/B/C 均未合格，只生成 `UNQUALIFIED_DIAGNOSTIC_ONLY / PARTIAL / AUTOMATED_GATE_FAIL` 诊断包，正式人耳门未解锁。
- [ ] I5：收到具名反馈后最多三轮 v6→v7→v8；没有反馈不继续。
- [ ] I6：具名门禁通过后才生成匿名包；自动 30% reference gate 失败时仍不得 Profile Freeze。

### Stage I review

- Base/branch/worktree：`6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2` / `agent/s12-stage-i-hellcat-whine-voicing` / `E:\Tesla_speed\worktrees\s12-stage-i-hellcat-whine-voicing`。
- Current status：`PARTIAL / AUTOMATED_GATE_FAIL`。当前只有未合格诊断包，不存在 `WAITING_FOR_JOVI...` 的正式人耳状态。
- Candidate qualification：A/B/C 的 `all_pass` 均为 false；参考距离平均改善分别为 `-17.5046% / -13.5205% / -18.9879%`；未自动选中候选，未生成 Profile Freeze Candidate。
- Fresh tests：Stage I focused `108 passed / 56.34 s`；regression isolation `3 passed`；full S12 `596 passed / 232 subtests / 740.41 s`；Track-P guard script PASS（`180 files / 2 symbols`），Track-P guard pytest `21/21 passed / 1.23 s`。旧 `583/232` 仅是 pre-P1 审查过程历史。
- Current diagnostic package：`E:\Tesla_speed\review_packages\s12-stage-i-hellcat-whine-voicing-v1-unqualified-diagnostic`，27 files / 223.35 MiB；ZIP SHA-256 `98fcdc21d5208b7a43c1522a08ba063ee855023c134203e1389587dc23e507bc`；SHA sums `26/26`。
- Historical invalid package：旧 `f6997bab...45f5d7` 包已移动到 `E:\Tesla_speed\review_packages\_invalid_s12-stage-i-hellcat-whine-voicing-v1_pre-p1-review`，只可恢复审计，不是当前交付。
- Evidence boundary：sealed key 未读取；Stage G 第 2/第 3 条编号反馈仍未绑定车型；Ferrari/RX-7 冻结不变；所有输出为 `synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction`。
- Next：Jovi 可以用显式 `file_id` 提供诊断反馈，但该反馈不构成正式人耳门。I5/I6 保持未完成；必须先关闭自动资格失败，才可发布正式人耳包，且不得自行进入匿名盲听、Profile Freeze、Simulink、Runtime 或 Android。
# S12 Stage J execution ledger (2026-08-11)

- [x] J0: freeze d8b8c245 baseline and evidence; Stage I focused 108 passed, Track-P 21/21, guard 180 files/2 symbols
- [x] J1: reconcile C63/GT-R/LFA references and target matrix; target JSON remains numeric authority, official Nissan/Lexus facts recorded
- [x] J2: candidate schema, loaders, renderer, and usage diagnostics; Stage J focused contract tests 5 passed
- [x] J3: independent C63, GT-R, and LFA source models; source tests 8+11+9 passed
- [x] J4: final-PCM qualification and identity separation; fixed bands/windows measured, automatic status remains PARTIAL where 30% is unmet
- [x] J5: louder named review package and SHA evidence; 3×60 s pairs plus 12 s diagnostics, review request +1.9382 dB, peak-safe applied gain recorded; ZIP SHA `2c2054dcdd8e96eab6cabc9724ed9a1edc7ff72e5632fcf5051ed13fbd94ac38`
- [ ] J6: real Jovi feedback iterations (maximum v1→v2→v3)
- [x] J7: reports, Obsidian handoff, local commits, final verification; full S12 `321 passed / 114 subtests`, full acoustic identity `314 passed / 118 subtests`

## Stage J review (2026-08-11)

- Worktree: `E:\Tesla_speed\worktrees\s12-stage-j-three-vehicle-identity`; branch `agent/s12-stage-j-three-vehicle-identity`; base `d8b8c24530eafc354d420c95e1ff071034e51707`.
- Stage J focused suite: `39 passed / 27.99 s`; Stage I focused: `108 passed / 55.98 s`; realism/identity: `67 passed, 78 subtests / 137.64 s`; Track-P pytest `21 passed`, guard `180 files / 2 symbols`.
- Full regression: `tools/sound_sim/s12/tests` = `321 passed, 114 subtests / 138.82 s`; `acoustic_identity_v015/tests` = `314 passed, 118 subtests / 626.50 s`.
- External package: `E:\Tesla_speed\review_packages\s12-stage-j-three-vehicle-identity-v1\`; state `PARTIAL / AUTOMATED_GATE_FAIL` plus `WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW`; no answer or feedback was invented.
- Review copy requested `1.25x` (`+1.9382002601611283 dB`). C63 and GT-R pair peaks were already headroom-limited at `-1.5 dBFS`; actual applied gain is recorded as approximately `1.0x`. LFA applied approximately `1.2475x`. Formal `-16 LUFS / -1.5 dBFS` policy was not changed.
- Reference-distance means: C63 `19.68%`, GT-R `-210.88%`, LFA `14.05%`; none reaches the 30% automatic gate, so no Profile Freeze or Human PASS claim is allowed.

# S12 Stage K four-vehicle perceptual repair (2026-08-11)

- [x] K0-Task1：冻结 Stage J `b78b6c3`、新 Stage K 分支、Jovi 具名反馈和两个视频页面的证据边界；未下载或提交原始媒体。
- [x] K1：建立 Stage K candidate schema、父候选 lineage、`candidate=None` Stage C bit-identical 回归和 requested/read/configured/active/inactive/unused 诊断。
- [x] K2：新增只依赖 load/throttle 的 operating-state trim；验证低负载略增、高负载略减、RPM 不直接控制响度、事件 stem 不被 trim。
- [x] K3：重建 Hellcat twin-screw whine v4/v7；修复 sideband 隐式倍率、真实 attack/release、进气/壳体传递和 boost-history bypass。
- [x] K4：重建 C63 bark v3；保留低频排气，降低事件驱动的高频 roughness，不使用宽带噪声或全局增益。
- [x] K5：重建 GT-R 并行双涡轮 v3；两套 shaft state 同时建立，BPF 由 shaft phase 驱动，保留 V6 三事件/转结构。
- [x] K6：新增 LFA 专属 ASG 换挡、进气重开和 V10 overrun/lift 层；替换通用深切与固定 70 Hz boom。
- [x] K7：建立车型专属指标、有界候选搜索、最终 PCM reference-distance 和四车具名试听包；自动失败时保持诊断状态。
- [x] K8：执行 focused/分组回归/Track-P，生成报告与 Stage K Obsidian handoff；完整盲听资格和后续 v1→v2→v3 迭代仍等待 Jovi 具名反馈。

Review：Task 1 已记录 Jovi 的明确车型反馈，但尚未产生任何候选资格、人耳 PASS 或 Profile Freeze 结论。视频页面的可访问性不等同于音轨可测量性；若音轨不可审计，必须保持 `NOT_AVAILABLE`。

## Stage K review (2026-08-12)

- Base/current：Stage J `b78b6c3031269eae1a0b917ce7bbaaed2af81c76`；Stage K `4261bbfe34b11980fcb15a0a9b01bd6d5f75c9e6`；branch `agent/s12-stage-k-four-vehicle-perceptual-repair`。
- Focused：Stage K `84 passed / 18.10 s`；Stage J C63/GTR/LFA `8/11/9 passed`；Stage C realism `7 passed`；Track-P pytest `21 passed`。
- Identity：58 个测试按研究/源、body/loudness、metrics、publication 分组均通过（合计 `58 passed / 78 subtests`）；整文件 Windows 进程运行曾在输出末端被中止，因此不将该一次性命令写成单次 PASS。
- Package：四车 60 s + 场景/诊断 WAV、ZIP SHA `d81bc9e77276bf6066c73bf3444239800067f1a1545f43460061c37bd88fdeef`；状态 `PARTIAL / AUTOMATED_GATE_FAIL` + `WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW`；sealed key 未读取。
- Reference distance：Hellcat `4.2019%`、C63 `-209.1852%`、GT-R `-64.6546%`、LFA `18.5617%` 平均改善，均未达到 30%；不得进入 Profile Freeze。
- Remaining：真实 Jovi 具名 CSV 反馈、最多三轮窄范围调音、匿名盲听和 Profile Freeze 均未开始；禁止 Human PASS、Approved、OEM reproduction、Simulink/Runtime/Android。

# S12 Stage K 三车 Round‑2 经验迁移（2026-08-15）

- [x] R2-K0：冻结 C63 W204、GT‑R R35、LFA 当前 candidate profile、Stage K v1 package 与 Track‑P 边界；保留所有既有未跟踪文件。
- [x] R2-K0：创建 `tasks/plans/2026-08-15-s12-stage-k-three-vehicle-round2-propagation.md`，明确三车专属声源边界、事件窗口和最终 PCM 证据规则。
- [x] R2-K1：先补 RED：真实数组/事件窗口、aggregate/pressure 单次会计、三车隔离、最终 PCM/Comfort 与 receipt/ZIP 来源绑定。
- [x] R2-K2：最小 GREEN：只增加三车 Round‑2 证据/指标契约，不修改公共层、Hellcat v9 或 Track‑P。
- [x] R2-K3：按车型顺序做 8–12 s bounded probe：C63 bark/body、GT‑R twin‑turbo/V6、LFA V10 ASG/lift；每车最多九个完整快照。
- [x] R2-K4：只在 hard gates 与包完整性通过后生成不覆盖的 `s12-stage-k-three-vehicle-round2-v3`；自动门未全过，状态保持 `UNQUALIFIED_DIAGNOSTIC_ONLY`。
- [x] R2-K5：执行三车 focused、Stage K/J、Track‑P、冻结 SHA 与 diff 验证并本地提交；不读取 CSV，不进入 Profile Freeze。

Progress (2026-08-15): R2-K1 actual-array/event-window/pressure/vehicle-isolation tests are green; R2-K2 source metrics now include bands, clock coherence, spectral distance and array-derived event/afterfire CV/centroid/decay; R2-K3 vehicle-specific trace-gated seed overlays and bounded coordinate ranking are implemented. The 30 s real seed probe is recorded in `tasks/reports/runtime/s12-stage-k-three-vehicle-round2/stage_k_round2_seed_probe.json`. Final v3 package is published at `E:\Tesla_speed\review_packages\s12-stage-k-three-vehicle-round2-v3`; v1/v2 remain historical and were not overwritten. Fresh evidence: Round‑2 `19 passed / 1 deselected`, compatibility plus package `77 passed`, boundary suite `11 passed`, Track‑P `21 passed` and guard `180 files / 2 symbols`; independent v3 package validation reports zero errors. Status remains `PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY` pending Jovi audition; no CSV was read.

### R2-K review (2026-08-15)

- Scope: C63 W204, GT‑R R35, and LFA only. Hellcat/Stage L, public layers, Frozen PTR, loudness manager, MATLAB/Simulink, Android, and Track‑P remain untouched.
- Actual evidence: event windows are trace-derived; source metrics declare `actual_arrays_and_trace` and `diagnostics_claims_used=false`; LFA's historical aggregate alias is reconciled in the Round‑2 view before pressure accounting.
- Package: 3 vehicles × (parent/baseline/candidate/comfort + 4 source-domain diagnostics), 24 WAV, 28 SHA entries, 29 ZIP members; all PCM headers/frames/receipt hashes/Comfort input SHA/ZIP CRC independently match.
- Historical v3 semantic receipts recorded LFA `asg_metallic_event` and therefore failed its wrong-condition gate. Current code fixes that defect by measuring `lfa_shift_exhaust_reengagement` against actual ASG shift alignment; v3 remains historical and is not silently rewritten. Existing Stage-K afterfire remains separately labelled and keeps its closed-throttle history rule.
- Human/qualification boundary: `human_pass=false`, `csv_content_read=false`, no OEM claim, no Profile Freeze or Approved status. Await Jovi's explicitly labelled audition feedback before another round.

# S12 八车型 Round-2 完成与项目落地（2026-08-15）

- [x] R2-8-0：盘点八车型覆盖与 Obsidian 漂移，确认剩余 Ferrari 458、RX-7 FD、Supra JZA80、Aventador LP700 四车。
- [x] R2-8-1：修复 LFA 将连续 metallic 误判为 ASG event 的资格根因，并冻结真实 shift-array 回归；12 s actual render 为 3 个 shift / 0 wrong-condition / eligible=true。
- [x] R2-8-2：补齐 Ferrari/RX-7 与 Supra/Aventador 独立 Round‑2 source、trace window、event qualification 与 pressure accounting；四车 source/package 契约与回归已绿。
- [x] R2-8-3：建立八车统一 final-PCM/Comfort 与可信 manifest/SHA/ZIP 包；三车 v4 与剩余四车 v1 均为新根，不覆盖历史包。
- [x] R2-8-4：运行跨阶段、八车冻结与 Track-P 验证；22 项 Round‑2 回归、Track-P 21/21、180 文件/2 符号 guard 与双包独立验收均通过。
- [x] R2-8-5：读取并同步 Obsidian 当前仓库 tip、包、测试、已完成项与未完成资格门；未读取 CSV，仍保留诊断-only 边界。

Round‑2 completion evidence: `tasks/reports/runtime/s12-stage-k-eight-vehicle-round2/`.
The LFA fix is `e9aa9b6`; the remaining-four implementation and package contract
are in `c6ce1cf`. All packages remain `PARTIAL / AUTOMATED_GATE_FAIL /
UNQUALIFIED_DIAGNOSTIC_ONLY`; no human or OEM qualification is inferred.

## S12 Round-2 documentation and GitHub publication (2026-08-21)

- [x] Add the public `docs/08-reports/01-s12-stage-k-eight-vehicle-round2.md` milestone entry and link it from `docs/README.md`.
- [x] Append the GitHub branch and publication receipt to the runtime completion report.
- [x] Push `agent/s12-stage-k-four-vehicle-perceptual-repair` to the project GitHub remote without merging into `main`.
- [x] Update the five local Obsidian project/context pages with the same branch, package, status, and report links.

## S12 Stage M Eight-Vehicle Round-2 Qualification (2026-08-21)

> Status: `IN_PROGRESS`; scope is only `E:\Tesla_speed\worktrees\s12-stage-m-round2-qualification`. No Simulink, Runtime, Android, merge, push, or PR.

- [x] M0 baseline audit against `5e316934...` and `origin/main c08eb4c...`.
- [x] M1 fresh test/package/WAV/SHA/CRC replay: 45 focused, 131 Stage-K, 21 Track-P; 52 ZIP WAVs and both CRC/SHA receipts passed.
- [x] M2 qualification call graph, source-domain and gate-source matrices; confirmed reference distance is not a required Round-2 hard gate.
- [x] M3 eight-vehicle automatic-gate attribution, including C63/GT-R internal negative-delta routing, LFA ASG 3/0 verification, named remaining-four sources, and independent Hellcat Stage-L v9 diagnostic scope.
- [x] M4 unaltered-final-PCM comparator evidence: contracts, preprocessing, bounded alignment, spectral/order/psychoacoustic/transient metrics, explicit synthetic-parent uncertainty, seven schemas, and self-tests.
- [x] M5/M7 named-feedback validator, empty receipt, parameter recommendations withheld by missing reference contract, fail-closed gate matrix, and local eight-vehicle A/B review package.
- [x] M6/M8 automated closure: no calibration round is run without a lawful state/RPM-bound target; status is `AUTOMATED_CLOSURE_COMPLETE` / `WAITING_FOR_JOVI_NAMED_REVIEW` / `NOT_PROFILE_FREEZE_READY`.
- [x] Review correction pass: M2 ten-answer evidence, M3 32 vehicle/scenario records and `stage_m_eight_vehicle_failure_attribution.json`, comparator runtime subdirectory, and manifest-SHA feedback binding are regenerated. Final evidence: Stage-M/comparator `31 passed`; Round-2 focused `42 passed / 599.40s`; Stage-K `131 passed / 826.22s`; full S12 `336 passed / 114 subtests / 142.35s`; Track-P `21 passed / 1.09s` plus 180 files/2 symbols guard; original ZIP CRC/SHA and 52 WAV reopen checks plus 24 Stage-M audition WAV/binding checks passed. No feedback content read, push, merge, or PR.

## S12 Stage N Professional Acoustic Comparator (2026-08-21)

> Status: `IN_PROGRESS`; worktree `E:\Tesla_speed\worktrees\s12-stage-n-professional-comparator`, branch `agent/s12-stage-n-professional-comparator`, baseline `ec10ea6`. No vehicle sound-source, Simulink, Runtime, Android, merge, push, or PR changes are authorized.

- [x] N0: Established isolated worktree and current-state preflight. MATLAB Desktop is absent, while six pre-existing `matlab-mcp-server.exe` processes are active; do not stop/reconnect/start MATLAB. Current project Python has no MoSQITo, Essentia, MATLAB Engine, or librosa import.
- [x] N0: Saved detailed implementation plan at `docs/superpowers/plans/2026-08-21-s12-stage-n-professional-comparator.md`.
- [x] N1: Added a closed-status, per-function capability matrix and validation contract; only actual versioned fixture receipts can become `VALIDATED`.
- [x] N2: Added MATLAB order/psychoacoustic source adapters and static fixture contracts. Runtime is truthfully `BLOCKED`: no `MATLAB.exe`/safe existing session was available, and the six pre-existing MCP processes were not touched.
- [x] N3: Created `E:\AI_Tools\Other\S12StageN\mosqito-venv`, locked MoSQITo `1.2.1`, and ran its real fixture functions. Gain/loudness, high-frequency/sharpness, fast-AM/roughness, and protruding-tone/tonality directions passed. MATLAB cross-tool trend remains `CROSS_TOOL_COMPARISON_BLOCKED`.
- [x] N4: Added Essentia optional subprocess detection and official-build-only ViSQOL scope validation. Essentia and ViSQOL remain `OPTIONAL_NOT_INSTALLED`; no source vendor or `pip install visqol` was used.
- [x] N5: Cloned official webMUSHRA upstream only to `E:\Claude_allow\Download\webMUSHRA-stage-n` at `8c353f7...`; exported new v1 study package, served config/audio through a temporary Docker container at `127.0.0.1:18081`, exercised PHP fixture export, SHA/file-ID imported it as `FIXTURE_IMPORT_ONLY_NOT_HUMAN_FEEDBACK`, then removed the confirmed temporary container.
- [x] N6: Published unified eight-vehicle results, withheld recommendations, required Stage-N reports, deterministic artifact manifest, and fresh verification evidence. No vehicle-source path changed and no human feedback was claimed.
- [x] N2a: Bound all eight Stage-M candidate WAVs to their original Stage-K/Stage-L receipts and canonical state traces. Added a non-overwriting MATLAB MAT-input generator plus manual Desktop-session runner; the generated inputs are local artifacts, not source-controlled results.
- [x] N2b: With Jovi's explicit existing-Desktop authorization, ran real MATLAB R2026a Signal Processing Toolbox fixture plus all eight hash-bound candidate inputs. `rpmordermap`, `rpmfreqmap`, `orderspectrum`, and `ordertrack` are fixture-validated; each candidate order map executed with its original bound RPM/state trace. The external-reference boundary remains `REFERENCE_RPM_UNAVAILABLE` / `ORDER_COMPARISON_NOT_QUALIFIED`.
- [x] N2c: Ran real MATLAB R2026a Audio Toolbox fixture plus all eight hash-bound candidates. `acousticLoudness`, `acousticSharpness`, `acousticRoughness`, `acousticFluctuation`, `acousticToneToNoiseRatio`, and `acousticProminenceRatio` are fixture-validated, digital-domain relative only. MATLAB and MoSQITo agree on common gain/loudness, high-frequency/sharpness, fast-AM/roughness, and prominent-tone trends.

### Stage N review

- Current status: `PROFESSIONAL_COMPARATOR_TOOLCHAIN_PARTIAL` / `PROFESSIONAL_TOOLCHAIN_VALIDATED_ON_FIXTURES` (MATLAB Signal Processing Toolbox, MATLAB Audio Toolbox, MoSQITo, and webMUSHRA fixture scope) / `PROJECT_CANDIDATES_ANALYZED` / `REAL_REFERENCE_ORDER_COMPARISON_BLOCKED` / `WAITING_FOR_JOVI_HUMAN_FEEDBACK` / `NOT_PROFILE_FREEZE_READY`.
- Fresh execution evidence: MATLAB R2026a fixture and 8/8 project-data receipts passed independent immutable-input/path validation; order fixture ridge errors for 0.5/1/4/6 are all below `0.003` against a `0.08` tolerance; all five Audio Toolbox direction gates passed; MATLAB/MoSQITo common-trend validation passed; Stage-N runtime artifact manifest verification is zero-error. The earlier full-S12 regression record (`343 passed, 114 subtests passed in 445.42s`) predates this audit correction; no full-S12 result is claimed for the current diff.
- Boundary: generated MATLAB inputs and execution maps are reproducible local artifacts and deliberately ignored; committed runtime receipts retain SHA/path evidence. A real external reference must still carry lawful raw waveform provenance plus matching RPM/state metadata. After a SHA/file-ID-bound Jovi CSV or webMUSHRA result, use a separate sound-fix branch; do not change vehicle sources here.

## S12 Stage N comparator evidence correction (2026-08-21)

- [x] N2d: Replaced the earlier same-intent cross-tool fixture claim with a non-overwriting 3-second MAT fixture. MATLAB R2026a and MoSQITo now bind the identical fixture manifest SHA `2aef9843...02f077` and MAT SHA `2a1b2d1e...6d04e0`; all four common trends pass. The first row-vector MATLAB output and first MoSQITo tonality interpretation are preserved under separate suffixes and are not promoted.
- [x] N6b: Exported a non-overwriting webMUSHRA v3 package, launched the external official checkout locally, opened `s12-stage-n-webmushra-v3.yaml` in a browser, and imported one SHA/file-ID-bound raw PHP fixture row. The container was then removed; this is fixture evidence only, not human feedback.
- [x] N8: Expanded unified comparator results to all available Stage-M scenarios (`full_cycle`, `idle`, `acceleration`, `lift_afterfire`, `shift`) for every vehicle. Scenario PCM/reference absences and order qualification remain explicit.
- [x] N9: Added a no-source-change, evidence-bound recommendation rule engine. Without confirmed Jovi feedback every recommendation remains `WITHHELD`; future eligible recommendations retain residual, parameter group, direction, evidence, confidence, side-effect risk, and a separate-branch promotion block.
- [x] N10: Added SHA/file-ID confirmation flow, identity confusion matrix, and objective-residual binding. The current `feedback_closure.json` is `WAITING_FOR_JOVI_HUMAN_FEEDBACK`; no feedback content was created or promoted.
- [x] Review: Focused Stage-N suite is green after the correction; artifact manifest verification is zero-error. No vehicle-source, Simulink, Runtime, Android, merge, push, or PR change was made.
- [x] Verification: `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015/stage_n tools/sound_sim/s12/acoustic_comparator` and the two Stage-N test modules passed (`19 passed in 8.21s`); MATLAB Code Analyzer reported no issues for the changed adapter.
- [ ] Verification note: the expanded all-S12 pytest invocation was not claimed as passing. Its controller detached output, then its single remaining process tree continued past the bounded completion window and was stopped after exact PID/command verification; no test failure was observed, but no exit code was recovered.

## S12 Stage N specification completion audit (2026-08-21)

- [x] N0–N7 audit: capability matrix includes the three industry-reference `INDUSTRY_REFERENCE_NOT_INSTALLED` rows; live MATLAB/MoSQITo receipts retain the eight-candidate and same-MAT fixture evidence; Audio Test Bench, Essentia and ViSQOL remain honestly blocked/optional.
- [x] N6 correction: added official `mushra.csv` + `lss.csv` joining in `webmushra_import.py`, including SHA/file-ID binding, required-dimension completeness, and identity-guess validation. A new non-overwriting v5 package was opened in the external official Docker checkout and its paired fixture files imported as `FIXTURE_IMPORT_ONLY_NOT_HUMAN_FEEDBACK`.
- [x] N6 contract: documented participant-settable full-clip loop range and upstream sample-accurate fade behavior. The future-candidate slot is explicitly `INACTIVE_NOT_GENERATED_NO_SOURCE_CHANGE_AUTHORIZED`; no placeholder audio or source mutation was substituted.
- [x] N9 deliverable correction: emitted the spec-named `stage_n_parameter_recommendations.json` alongside the backward-compatible `parameter_recommendations.json`, with identical hash-bound content.
- [x] Audit evidence: direct requirement script passed (`15` tool records, `8` vehicles, five scenarios), and `test_s12_acoustic_comparator_core.py` plus both Stage-N suites passed (`30 passed in 8.47s`). Artifact manifest verification is zero-error.

## S12 Stage O human-feedback calibration (2026-08-21)

- [x] O0: Created this worktree from exact Stage-N tip `e0cf90dc7d10f5bb36d8953ae93eb068ab4382c6`; the inherited Track-P false positive was repaired with a precise Track-S allowlist (`fef513e`) without changing the 180-file/2-symbol frozen content.
- [x] O0 evidence: governance-repaired full S12 `827 passed / 232 subtests / 1710.50s`; final current tree including Stage-O entry tests `830 passed / 232 subtests / 1746.77s`; Stage-N focused `19 passed`; Track-P guard pytest `32 passed`; independent guard `180 files / 2 symbols`; Stage-N artifact manifest, WAV reopen/finite/clipping and SHA binding checks passed.
- [x] O1 entry gate: added strict real-feedback intake for paired official `mushra.csv`/`lss.csv` or named CSV, requiring package/candidate/file/test/row/identity/listener binding plus playback device, Windows volume, endpoint, environment and system EQ metadata. Fixture/synthetic inputs are rejected and no input paths currently exist.
- [x] Waiting-state artifacts: published `tasks/reports/runtime/s12-stage-o-human-feedback-calibration/` with exact-tip receipt, entry receipt, empty confusion/metric/parameter/round outputs, gate matrix and artifact manifest. Current state is `STAGE_N_ACCEPTED / WAITING_FOR_JOVI_FEEDBACK / NOT_PROFILE_FREEZE_READY`.
- [x] Boundary review: no vehicle source/profile, idle/afterfire/shift/body parameter, Runtime, Android, MATLAB receipt, MoSQITo receipt, Stage-N comparator core or frozen Track-P content changed; no push, merge or PR was performed.

## S12 Stage P independent system acceptance (2026-08-22)

> Status: `SYSTEM_ACCEPTANCE_PASSED / READY_FOR_JOVI_UAT / HUMAN_FEEDBACK_PENDING / NOT_PROFILE_FREEZE_READY`; local-only Stage-P branch.

- [x] P0 exact Stage-O baseline audit: `38d84f3540081636b7ea78636ba2479a0afe170e`, parent/origin/main/branch/worktree and protected hashes recorded.
- [x] P1 fresh full regression (`830 passed / 232 subtests`) plus Stage-N/O/comparator/Track-P/Stage-P focused tests, compileall, diff and artifact manifest.
- [x] P2 Stage-N receipts, 8 candidates, SHA/schema/finite/tool enum, MATLAB/MoSQITo constraints and same-fixture cross-tool binding validated.
- [x] P3 8-vehicle × 5-scenario comparator replay with no truth/absolute SPL/real-reference promotion.
- [x] P4 official upstream webMUSHRA Docker/PHP and named browser full fixture run generated/imported `mushra.csv + lss.csv`; hidden reference is synthetic parent, not real recording.
- [x] P5 15 negative security cases fail closed; P6 two persistent independent package rebuilds match audio inventory/SHA and refuse overwrite.
- [x] P7 Jovi UAT START/OPEN/IMPORT/CHECK/STOP package; P8 fixture-only Stage-O receipt/confusion/metric outputs and explicit fixture rejection at Stage-O entry.

### Review

- A–G gates PASS; H remains `HUMAN_FEEDBACK_PENDING`; no real Jovi content was read and no source/profile/tuning change was made.
- Final evidence: `tasks/reports/runtime/s12-stage-p-system-acceptance/`; UAT package: `E:\Tesla_speed\review_packages\s12-stage-p-jovi-uat-v1`.
- No push, merge, PR, or profile freeze was performed.

### Stage P specification-alignment correction (2026-08-22)

- [x] Re-audited the pasted Stage-P deliverable list against the current tree; added the exact report aliases `S12_Stage_P_System_Acceptance_Report.md`, `stage_p_tool_receipt_validation.json`, `stage_p_feedback_security_tests.json`, and `stage_p_uat_manifest.json`.
- [x] Added recursive `SHA256SUMS`, package-local `normalized_import_result.json`, explicit `README_JOVI.md` listening/setup hand-off, expected result paths, Docker/port/config checks, complete-trial status, and importer SHA/accepted/rejected diagnostics.
- [x] Re-ran Stage-P acceptance (`5 passed`), compileall, diff check, Track-P frozen guard, package/UAT checksum ledgers, and the official Docker/PHP UAT START/CHECK/IMPORT/STOP smoke (`32` MUSHRA rows, `80` LSS rows, fixture import `8 accepted / 24 rejected`, SHA binding PASS). Docker service was left stopped.

Review: canonical final state is `SYSTEM_ACCEPTANCE_PASSED / READY_FOR_JOVI_UAT / HUMAN_ACOUSTIC_QUALIFICATION_PENDING / NOT_PROFILE_FREEZE_READY`; H remains `PENDING`, and no source/profile/tuning or GitHub push/merge/PR was performed.

## S12 Stage Q–T real-reference closed loop (2026-08-22)

> Status: `R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED / WAITING_FOR_JOVI_HUMAN_FEEDBACK`; independent worktree `E:\Tesla_speed\worktrees\s12-stage-q-real-reference-calibration`, branch `agent/s12-stage-q-real-reference-calibration`. Branch push is authorized and verified; no merge, PR, Profile Freeze, Android, ESP32, CAN, or vehicle deployment.

- [x] Q0: Created the Stage Q worktree from the exact Stage P HEAD and recorded clean starting state.
- [x] Q1/Q2: Audited the external `E:\Claude_allow\Download\tesla-sound-research` media root; cataloged 15 WAV pointers across all eight vehicles without copying raw audio into Git.
- [x] Q3/Q4: Added `tools/sound_sim/s12/real_reference/` fail-closed inventory tooling, Stage Q manifest schema, Chinese report generation, provenance/SHA pointers, scenario-window placeholders, and RPM/state binding placeholders.
- [x] Q gate: Regenerated `tasks/reports/runtime/s12-stage-q-real-reference/` from the current worktree. All 15 present recordings remain R3/qualitative-only; R1=0, R2=0; no automatic tuning eligibility.
- [x] R gate: Added R1 qualification checks and generated a fail-closed waiting result, withheld parameter recommendations, and Chinese difference-report template under `tasks/reports/runtime/s12-stage-r-real-sound-difference/`.
- [x] R2 path: Added an authorised-R2 limited comparator adapter. It permits only spectrum/loudness/psychoacoustic/subjective-transient evidence and always disables order hard gates and automatic tuning authority.
- [x] R execution entry: Added an unaltered PCM-WAV reader, fail-closed R2 limited comparison/report writer, and R1 MATLAB/Stage-N execution-plan builder. The R1 plan names the required MATLAB/Audio Toolbox functions and receipts but does not execute without qualified real inputs.
- [x] R1 input preparation: Added a fail-closed CSV/JSON state loader and SHA-bound external MAT input package for the existing MATLAB order/psychoacoustic runners plus the MoSQITo project-input entrypoint. It preserves unaltered analysis data, records channel/time/unit policy, and never starts MATLAB or grants tuning authority.
- [x] Public-license intake: After Jovi explicitly authorized web search/download, downloaded two Wikimedia Commons CC references and one Freesound CC0 Supra chassis-dyno reference to `E:\Claude_allow\Download\s12-web-authorized-20260822`, plus one CC rotary mechanical demo (R3 qualitative only); raw media stayed outside Git and provenance/derived WAV SHA-256 entries were committed.
- [x] R2 execution: Ran the existing fail-closed R2 comparator on Ferrari 458 acceleration, Hellcat launch proxy, and Supra full-pull dyno preview with explicit sample-rate/conversion metadata. All three cases are `R2_LIMITED_COMPARISON_COMPLETE`; order hard gate, automatic tuning, parameter recommendations, and human feedback remain withheld.
- [x] S gate: Added the Chinese listening-study contract and feedback gate under `tasks/reports/runtime/s12-stage-s-human-calibration/`; no placeholder audio or fixture feedback is materialized.
- [x] T gate: Added the blocked Profile Candidate handoff under `tasks/reports/runtime/s12-stage-t-profile-candidate/`; no candidate files, Profile Freeze, or product handoff are generated.
- [x] Final waiting audit: Generated `tasks/reports/runtime/S12_Real_Sound_Closed_Loop_Final_Report.md` with per-stage/per-vehicle status, metric limits, feedback/tuning counts, Track-P boundary, commits, and the verified branch-push state.
- [ ] R/S/T execution: R1 MATLAB/MoSQITo baseline, human feedback, and parameter modification still require synchronized RPM/state/capture metadata and a real SHA/file-ID-bound listening receipt. R2 output is diagnostic-only and cannot close S/T.

### Stage Q review

- `python -m pytest tools/sound_sim/s12/tests/test_s12_stage_q_real_reference.py -q`: `5 passed` (including the explicit web-authorized R2 manifest contract).
- `python -m tools.sound_sim.s12.real_reference.cli --media-root E:\\Claude_allow\\Download\\tesla-sound-research --out-dir tasks\\reports\\runtime\\s12-stage-q-real-reference`: `REAL_REFERENCE_DATASET_LIMITED`, `WAITING_FOR_REAL_REFERENCE_DATA`, 15 records, 0 R1.
- Q/R/S/T gate tests cover unqualified-reference rejection, withheld recommendations, Chinese dimensions, no placeholder audio, and no profile candidate materialization.
- R2 limited adapter and waiting final-report test pass; old Stage-G B/R2 derived numbers were not reused as current HEAD real-reference results.
- R execution/input tests: `7 passed`; full S12 focused suite: `48 passed`; `compileall` and `git diff --check` pass.
- Raw audio remains outside Git; only external paths, SHA-256, WAV headers, source pointers, and missing-evidence state are recorded.

### Web-authorized R2 review（2026-08-22）

- Ferrari 458 CC BY-SA 3.0 source: `R2_LIMITED_COMPARISON_COMPLETE`; spectral log residual `0.574775`, loudness residual `+2.7001 dB`; order `NOT_QUALIFIED_R2_NO_SYNCHRONIZED_RPM`.
- Hellcat CC BY-SA 4.0 source: `R2_LIMITED_COMPARISON_COMPLETE`; spectral log residual `0.503287`, loudness residual `+0.4530 dB`; local file is a synthetic launch proxy and order remains `NOT_QUALIFIED_R2_NO_SYNCHRONIZED_RPM`.
- Supra CC0 chassis-dyno preview: `R2_LIMITED_COMPARISON_COMPLETE`; spectral log residual `0.854657`, loudness residual `-6.4747 dB`; source page describes a full-throttle dyno run but exact JZA80 generation and synchronized RPM/state are not verified.
- RX-7 FD: no legally usable full-throttle/dyno vehicle recording found in this search. `Wankel3.ogv` is CC BY-SA 2.5 Mazda 13B mechanical demonstration and is registered only as R3 qualitative rotary texture.
- No overall similarity percentage, no automatic parameter recommendation, no source/profile edit, and no Jovi hearing result was produced.

### Q additional external-root audit（2026-08-22）

- [x] 将 `tesla-sound-research-v12` 与 `s12-acoustic-realism-v10` 纳入 Q 目录审计；新增 6 个外部 WAV 指针，只记录 `audit_root`、路径和 SHA-256。
- [x] 额外目录媒体保持 `UNMAPPED_NOT_REGISTERED / DO_NOT_ANALYZE_OR_TUNE`，不把旧 manifest 的 R2/R3 标签提升为当前 R1/R2 资格。
- [x] 更新 Stage Q schema、CLI、报告和 manifest；原始本地基线为 15 条登记候选、18 条未登记外部媒体、R1=0/R2=0；后续 web-authorized overlay 另加 3 条 R2。

### 浏览器中文展示修正（2026-08-22）

- [x] 将 webMUSHRA 研究包的可见标题、说明、评分维度和提交字段统一为中文；机器协议键保留英文以兼容官方导出格式。
- [x] 提供可审计、可重复应用的上游固定按钮中文覆盖；未应用覆盖前不得声称浏览器界面已全中文。
- [x] 外部 webMUSHRA 中文 UI 实测：应用 NLS 补丁并用 `language: zh` 最小配置通过浏览器快照验证“播放、暂停、下一页”等中文控件和音频加载；仅验证界面，不写入听审结果。
- [x] 运行导出包配置测试，确认中文配置不会改变真实参考、SHA/file-ID 绑定或反馈门禁。

### 公开同步数据检索与报告修正（2026-08-22）

- [x] 复核 F1Audio：页面声明同步 RPM/挡位/油门，但 Zenodo 文件受限访问且车辆不是八个锚点；不下载、不升级为 R1。
- [x] 复核 Procedural Engine Sounds：RPM/扭矩通道属于程序化合成扩增，不是真实车辆原始录音；不升级为 R1。
- [x] 复核 CC BY 4.0 的 Sounds of Vehicle Internal Combustion Engines：真实声样本可作一般 R2 线索，但页面未提供本项目锚点所需同步状态和采集合同，本轮不下载 8.1 GB 非目标资料。
- [x] 将 Q/R/总报告的“两个公开参考”“仅 Ferrari/Hellcat”旧口径修正为三条 R2（Ferrari/Hellcat/Supra），并增加 R3/R2 计数与检索边界。
- [x] 增加本轮报告复核后的 lessons；不把 R2 诊断、浏览器听审入口或合成数据称为已完成闭环。

### 公开同步数据检索复核

- 当前组合状态仍为 `R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED / WAITING_FOR_JOVI_HUMAN_FEEDBACK`。
- 最新验证：完整 S12 测试 `371 passed, 114 subtests passed`；Q/R/S/T 重点测试 `21 passed`；`compileall` 和 `git diff --check` 通过。
- R1/S/T 未完成的唯一真实缺口仍是：合法原始录音与同步 RPM、Load/Throttle、Gear/shift、麦克风/AGC 采集合同，以及 Jovi 的 SHA/file-ID 绑定听审反馈。
- [x] 记录三条可采购的三锚点候选（Ferrari 458、Hellcat、RX-7 FD）及其公开页面声称的同步 take/steady RPM/gearshift 元数据；明确它们仍需购买/授权和数值状态验收，不能预先升级为 R1。
- [x] 下载并审计一条 CC0 Pontiac G8 测功机视频：完成 WebM→PCM WAV 解码、SHA/采样信息和抽帧检查；登记为非目标 R3 流程样本，未进入八车型比较或调音。
- [x] YouTube 403 对照探针：使用无账号 Cookie 的 Node.js EJS，分别验证默认代理与 `--proxy ""`；页面挑战可解析，但签名媒体请求仍为 HTTP 403，失败日志和 SHA 收据保留在仓库外，未把截断物升级为媒体。
- [ ] 取得 Jovi 授权的商业原始包或等价自录包后，逐段验收 RPM/Load/Throttle/Gear/shift/麦位/AGC/授权，并重新生成 R1 manifest；未取得前不启动阶次自动调参。

### Jovi 网址输入入口（2026-08-22）

- [x] 新增 `tools/sound_sim/s12/real_reference/url_intake.py`：网址校验、外部目录下载、视频/音频 SHA-256、ffprobe 元数据、无增益 PCM 抽取和中文审计报告。
- [x] 入口默认 fail-closed：无许可为 R3；有许可但无同步状态最多 R2；视频压缩派生音频不会自动升级为 R1。
- [x] 增加可选抽帧/OCR 状态线索；没有 Tesseract 时仍保留帧 SHA，OCR 数字统一标记 `ESTIMATED_FROM_VIDEO_NOT_QUALIFIED`。
- [x] 支持 JSON 批量网址规格：每个网址可单独绑定车型、工况、许可和状态合同，避免多车型批处理时共用错误元数据。
- [x] 新增 `URL_INTAKE_GUIDE.md` 和 4 项 URL intake 回归测试；不修改 MATLAB、Runtime、Simulink、Android 或 Track-P。
- [x] 新入口接入后完整 S12 Python 回归：`376 passed, 114 subtests passed in 239.72s`；`compileall` 与 `git diff --check` 通过。
- [x] 用已核验 CC0 测功机网址完成一次真实端到端冒烟：`URL_INTAKE_COMPLETE`、1 条记录、网页视频→PCM WAV→中文 manifest/report；因 Opus 派生音频和缺少同步状态正确保持 `R2`。
- [x] 追加抽帧冒烟：4 个 JPEG 帧、`OCR=NOT_AVAILABLE_TESSERACT_MISSING`、`RPM_STATUS=MISSING_RPM_STATE`；结果仍为 `R2`，未产生阶次资格。
- [ ] 等待 Jovi 提供车辆网址；收到后逐条下载、抽音频、检查画面状态并绑定车辆/工况。

## 项目本地瘦身（2026-08-22）

- [ ] 盘点当前 worktree 的源码、报告、测试、音频/视频、缓存、构建物和历史方案文档，先形成删除候选清单。
- [ ] 保留当前需求、有效报告、可重建工具、测试、审计 manifest、外部原始录音指针，以及其他 worktree；不删除 `E:\\Claude_allow\\Download` 下的原始媒体。
- [ ] 只删除证据明确无用的项目内生成物/缓存，并记录每个删除路径与理由；不使用 `git clean`、`git reset` 或宽范围递归删除。
- [ ] 清理后运行 `git diff --check`、关键测试和路径存在性检查，记录清理前后 Git 状态与可恢复边界。

### 清理评审记录

- 盘点范围：当前 `s12-stage-q-real-reference-calibration` worktree；其他 worktree、`E:\\Claude_allow\\Download` 原始媒体和 MATLAB/Simulink 资产未纳入删除。
- 明确保留：当前 S12 Q/R/S/T 报告、计划、测试、manifest、8 个仍被 R2 元数据引用的 `*_ab.wav`、历史审计 ZIP 及其校验记录。
- 删除候选：37 个被 `.gitignore` 排除的 `__pycache__`/`.pytest_cache` 目录，共 445 个文件、5,149,580 bytes；这些目录确认为可重建缓存。
- 删除结果：安全策略拒绝了递归删除操作；未使用替代命令绕过，故本轮实际删除 `0` 个文件，候选仍保留待后续受控清理。

## S12 Stage Q 真实车辆来源库下载与比较诊断（2026-08-22）

> 状态：`COMPLETE_DIAGNOSTIC_ONLY_R3 / R1=0 / R2=0 / WAITING_FOR_JOVI_HUMAN_AB`；原始媒体仅在 `E:\\Claude_allow\\Download`，未进入 Git。

- [x] 校验用户压缩包 SHA-256 `139A7EC28DE65CF446096A230C6ACBE95D0BD9F902F00A913A57D993305CD375`，安全解压 3 个文档并按每车 3 条选择 24 个来源。
- [x] 为 YouTube 403/SABR 增加默认客户端→Android→Node.js `web_embedded`/`mweb` 客户端回退；首轮 1/24 的不完整目录和日志保留，组合库通过 3 条替代 URL 达到 24/24 可读视频/WAV/SHA。
- [x] 对原始 3 条失败 URL 进行 Node.js/Web 重试并执行 `ffprobe` + `ffmpeg` 媒体体完整性校验：`yXw_35i3RMM` 完整，`XWEjZHFQ5lc` 与 `GQ0972wohFs` 明确保持 `INCOMPLETE_MEDIA_BODY`；结果写入外部 `retry_js_20260822/youtube_retry_js_manifest_v1.json`，不进入比较或 A/B。
- [x] 针对上述两条截断视频追加 `web_embedded` 仅音频格式回退：`XWEjZHFQ5lc`/`140-9` 与 `GQ0972wohFs`/`140-8` 均完整解码，转出外部 WAV 并写入 `audio_format_retry_20260822/youtube_retry_audio_manifest_v2.json`；完整音频为 `3/3`，完整视频仍为 `1/3`，三条继续保持 `R3`、不进入 R2/调参。
- [x] 复核系统代理导致的媒体直链 403，并在全新外部目录以 `--proxy ""`、Node.js EJS 和 `web_embedded → android_vr → tv_embedded → mweb` 回退重试原始 24 条 URL；完整可解码音频为 `24/24`。清单 `retry_direct_20260822_v1/youtube_retry_direct_audio_manifest_v1.json` SHA-256 `45DDB25441D3F09A35D6875011A8CBF2726DD03D921069F013B1E94385F4FD3F`，`decode_validation_v1.json` SHA-256 `C881F8790B52426F5C9F6FF5CF8A57EF76670C5A651FCE32AAB0DEF3AECA7CE4`；视频完整率不改写为 24/24，24 条继续保持 R3。
- [x] 将原始 24 条 URL 音频无增益解码为外部 PCM WAV，并用现有 `analyze_downloaded_sources.py` 生成 `24/24` 特征、`24/24` Comparator、8 车参数诊断和中文 R3 差异报告；外部收据 `analysis_r3_direct_v1/direct_analysis_receipt_v1.json` SHA-256 `A007C99EAC91D3A875EF3EDEF4E2A6433EBF6AC18BF1F724D9DD89D46F778876`，不进入 R2/R1 或自动调参。
- [x] 筛选 Zenodo CC BY 4.0 发动机声数据集：Petrol ZIP 官方 MD5 与本地一致，137 个编号 WAV 无车型/同步元数据；记录外部 `s12-public-vehicle-engine-ccby4-20260822/screening_manifest.json`，结论 `NOT_TARGET_BINDABLE_NO_MODEL_OR_STATE`，不进入目标车型比较。
- [x] 完成 8 张车型接触表人工视觉复核；车型身份仅标为 `VISUAL_IDENTITY_SUPPORT_ONLY`，原厂排气全部保持 `NOT_CONFIRMED`，变体/测功机/赛道风险逐条记录。
- [x] 新增 `tools/sound_sim/s12/real_reference/analyze_downloaded_sources.py`：校验外部 WAV SHA、生成 72 个低置信工况候选窗口、派生频谱/响度/心理声学/瞬态特征，并对 8 个本地 synthetic 候选做 24 条 R3 Comparator 诊断。
- [x] 生成外部 `analysis_20260822_v1` 的来源 manifest、派生特征、Comparator、中文 A/B 清单和带四分位数/范围的不确定性诊断建议；自动调参/Profile 更新保持禁止。
- [x] 增加中文报告 `tasks/reports/runtime/s12-stage-q-real-reference/S12_Stage_Q_YouTube_Intake_Analysis_20260822.md`，明确区分已完成链路与授权/同步状态/人耳反馈阻塞。
- [x] 复核三锚点商业同步录音候选的官方商品页、许可页和曲目单；只下载网页/PDF，不下载版权原始音频。外部候选审计 `E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\candidate_source_audit_v1.json` SHA-256 `082bc43c24ba1aa84f9450fe826244376925bb58c040999ea032396077f8c636`；三项均保持 `PROCUREMENT_CANDIDATE_NOT_R1`。
- [x] 验证：URL intake、Comparator、Stage-Q 重点测试 `22 passed`；新分析脚本实际跑完 `24/24`；`py_compile` 和 `git diff --check` 通过。
- [x] 解析三份商业候选曲目单 PDF 的状态字段并固化外部收据 `tracklist_state_screening_v1.json`（SHA-256 `eb185ddcfffe142c97988fe45a4524fecb26bf52a62c81c49a3a3b2d30dffb37`）：三项均无数值 RPM trace、Load/Throttle 字段或 state trace 文件，标签不能升级为 R1。
- [x] 针对 YouTube 初始 `1/24` 与代理 403 新建外部 `retry_tools_20260822_v2`，启用直接网络、Node.js EJS、`web_embedded` 渐进式格式及两条 `134 + 140` 分流回退；24/24 最终媒体通过严格 ffmpeg 全流解码。`strict_decode_manifest_v3.json` SHA-256 `E029D78938C6B21DB7FD612E8693362A25BED122A0DF73602F0E87CB92F7208E`，`download_recovery_receipt_v2.json` SHA-256 `A5D49E871505A7FAEF6EBEF316191356F06976AB18E8A2830B4BE82355914DF4`；旧截断物保留，全部原始媒体仍在 Git 外。
- [x] 按 Jovi 要求用当前 `yt-dlp` 独立复试原先 403 的 `XWEjZHFQ5lc`/`GQ0972wohFs`：默认客户端复现 403；`web_embedded + Node.js EJS` 的渐进式短头部被严格 `ffmpeg -xerror` 拒绝，随后 `134 + 140-9/140-8` 分流均通过完整解码。外部收据 `retry_yt_dlp_current_20260822/yt_dlp_node_web_embedded_retry_receipt_v2.json` SHA-256 `52996AB90C3145B292E0E2964560B70A2A2F46443283C0C79ED90458A94E5BF8`；原始媒体和残留不完整物仍在 Git 外。
- [x] 用仓库 `url_intake.py` 入口再次复现并恢复上述两条 403：默认客户端失败、Android 残片被拒绝，Node.js + `web_embedded` 自动选出完整 XWE MKV 与 GQ WebM；外部收据 `E:\Claude_allow\Download\s12-url-intake-repro-20260822\url_intake_repro_receipt_v2.json` SHA-256 `4F6CF1E7D81ECDB5CF47C9E363D40B6D0FF35D8ECC783AC93F00FF64C58E19B6`。两条仍为 YouTube 派生 R3，不进入 MATLAB/R1。
- [x] 加固 R1 资格门禁：要求非视频派生原始 PCM/FLAC、来源指针与授权证据、车型/工况、采样率、原厂排气确认；即使视频容器声明 PCM 或手工 raw receipt，YouTube/视频抽取仍不得升级。新增拒绝路径测试；完整 S12 回归 `377 passed, 114 subtests`，Stage Q/R/URL 重点 `16 passed`，Track-P guard `32 passed`。
- [x] 公开同步数据复核：F1Audio（受限/F1）、Visual-Acoustic（Lincoln MKS）和 HL-CEAD（非锚点固定 RPM）均排除为三个锚点 R1；Ferrari 458/Hellcat/RX-7 专业库保持未购买候选。证据清单 `tasks/reports/runtime/s12-stage-q-real-reference/public_sync_reference_search_audit_20260822.json`（SHA-256 `FB0660B24699791BB4613A4E45C5A492471C1DDF515638AA5BDBB1ADEB796B43`），没有下载版权原始音频。
- [x] 本轮最终验证：完整 S12 `377 passed, 114 subtests`；Stage Q/R/URL 重点 `16 passed`；Track-P guard pytest `32 passed`；独立冻结守卫 `180 files / 2 symbols`；`git diff --check` 通过。R1 仍为 0，未启动 MATLAB 阶次或调参；本轮提交后的最终 SHA 以 Git/远端复核为准。
- [x] 从上述 24 条最终完整视频重新抽取无增益 PCM WAV，并以 `intake_manifest_final_video_v1.json`（SHA-256 `2432218DFEF56CAE8A4FA4B475A1A7AEBB43BAB4BA9EBEC7459A4346611881CF`）绑定现有 Comparator；外部分析收据 `final_video_analysis_receipt_v1.json` SHA-256 `62492F2CABE3BBDF6606E7E1C16CAC4FE1703F784E4185D25D8C5D28841C1175`，中文差异报告 SHA-256 `60EAC35526ECF922EC50605EDF320F2A2BFCCD2CD06DA6BC38BF41054FD8F71D`，结果为 24/24、8 车各 3 条、R3 诊断，不进入 MATLAB/调参。
- [x] 2026-08-23 独立复试 YouTube 24 条：默认 `yt-dlp --proxy ""` 路径为 `2/24` 完整、`22/24 HTTP 403`；`Node.js + EJS + android` 回退补齐后，`ffprobe` 与 `ffmpeg -xerror` 全流/音频严格解码为 `24/24 COMPLETE_MEDIA_AND_AUDIO`，生成 `24/24` 外部 WAV。合并回执 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\youtube_retry_combined_receipt_20260823.json` SHA-256 `0DAB94BFB99A4AEDC4855929A39EA211D958A4EAA6C3B9F3ADCE98F065363EEE`；严格回执 `strict_decode_receipt_20260823.json` SHA-256 `C120BFE16B0CEF5B80C68FC47E4FB2BB6198CE94BAE8EE1BF9243B04A965C782`。原始/派生媒体均未进入 Git，YouTube 资格仍为 R3。
- [x] 2026-08-23 按 Jovi 最新要求做独立单条复测：对 `hellcat_01 / cKx-cb0fzeo` 的默认 403，`yt-dlp + Node.js EJS + android` 取得 3,749,435 字节 MP4；`ffprobe`、`ffmpeg -xerror` 全流校验与 48 kHz 双声道 WAV 完整解码均通过。外部收据 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v2_probe\download_receipt_hellcat_01.json` SHA-256 `7BF6CC011DBDCE68FA26A8F68F2EF10B4513AC7535269FFA42ED9802603317DE`；仍保持 YouTube `R3`，原始/派生媒体不入 Git。
- [x] 2026-08-23 重新核验两条明确许可的 R2 锚点：Wikimedia Ferrari 458 与 Dodge Challenger SRT Hellcat 外部 OGG/WAV 通过 `ffprobe`、`ffmpeg -xerror`，Stage R R2 Comparator 复跑成功且结果与既有基线一致；外部 manifest SHA-256 `16BB249DEDF7760AB02BB995B9F46953BCCDC4F62340B576AF7D177DC233340F`，R2 收据 SHA-256 `1E470FD6AABB54A7ADAF629FCEDD140B9B15082DD3A77EC4AE594DF98A26C0C1`。两案仍无同步 RPM/state，R1=0，自动调参关闭。
- [x] 2026-08-23 将上述最新 24 条 WAV 重新绑定并运行 R3 诊断链：`24` 条特征、`72` 个低置信切片、`24` 条 Comparator、`24` 条中文 A/B 试次和参数诊断均生成；外部收据 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\r3_analysis_receipt_20260823.json` SHA-256 `18bea83f660d773b81b138a6982f01012a64cac9fcef8605c0d660dab3bdefc0`。清单仍明确 `R1=0/R2=0/R3=24`、A/B 等待 Jovi，禁止阶次/自动调参，原始与派生媒体不入 Git。
- [x] 2026-08-23 为三锚点生成中文 A/B 外部包：Ferrari 458、Hellcat、RX-7 FD 各 3 个试次，共 18 个 5 秒试听片段；manifest SHA-256 `dc5bb05c24b338485f567b4e4107620aff76f8d210204b6cccae61eb4c4f6052`，receipt SHA-256 `fbcb0ccc701b4edfb20b371a13478ad8e2ac2172e3203bffb78e6ec15ff6ba6e`。`ffprobe`/SHA 校验通过，反馈字段为空，状态保持 `WAITING_FOR_JOVI_HUMAN_FEEDBACK`，不进入自动调参。
- [x] 2026-08-23 补齐中文离线 A/B 页面：`E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1\index.html` 可直接双击打开，固定绑定 9 个试次/18 个片段 SHA，支持中文评分、备注、进度和反馈 JSON 下载；页面 SHA-256 `5C495F4FA900F99A1B90C613E818C61249B58A2D239C60F1A2C09BFD956A869F`。Node 脚本语法、18 个片段 manifest/SHA 校验通过；页面不自动调参，状态仍为 `WAITING_FOR_JOVI_HUMAN_FEEDBACK`。
- [x] 审计一条 Freesound CC0 Ferrari 458 Italia GT3 现场录音：页面、MP3 预览和 PCM 派生 WAV 的 SHA 已绑定到 `freesound_ferrari_458_gt3_cc0_audit_20260822.json`；因同一文件混合多辆赛车且无分段时间/RPM/state，登记为 `R2_CANDIDATE_NOT_COMPARISON_READY`，未进入比较或调参。
- [ ] 取得可审计授权、精确原厂/Trim/排气资料、同步 RPM/Load/Throttle/Gear/shift、麦位/AGC 合同后，重新资格化 R2/R1；在 Jovi 提交绑定 SHA 的中文 A/B 反馈前不得调参。

## S12 MATLAB R2 专业指标复核（2026-08-23）

- [x] 核验现有 MATLAB R2026a Audio Toolbox：`rpmordermap`、`ordertrack`、`orderspectrum`、`rpmfreqmap` 及六个心理声学函数均可用。
- [x] 新增 `tools/sound_sim/s12/real_reference/run_r2_matlab_psychoacoustic_audit.m`，复用仓库现有 `s12_psychoacoustic_analysis`，对 Ferrari 458、Hellcat、RX-7 FD 各一组 R2 参考/本地 synthetic 代理执行 5 秒共同窗口相对测量。
- [x] MATLAB 运行收据：`E:\Claude_allow\Download\s12-r2-matlab-psychoacoustic-audit-20260823-v3\matlab_r2_psychoacoustic_audit.json`，SHA-256 `523C8264F6A83EE23640A166FDFA15E76771880EFBFE914A4FA79C161AABB70A`；3/3 案例成功，状态 `R2_LIMITED_COMPARISON_COMPLETE`。
- [x] 复核边界：无同步 RPM/Load/Throttle/Gear/shift，因此没有运行 `rpmordermap`/阶次资格、自动调参、参数写回或 Profile Candidate；Jovi 人耳反馈仍为 0。
- [x] 当前 worktree 全量回归：`877 passed, 232 subtests passed in 1605.13s`；Stage Q/R/S 聚焦 `31 passed`；Track-P pytest `32 passed`；独立冻结守卫 `180 files / 2 symbols`；`git diff --check` 与 `compileall` 通过。

### Review

- 成功证据：外部组合 intake `URL_INTAKE_COMPLETE`、24 条唯一 URL、24 个 WAV SHA、72 个切片记录、24 条 Comparator 记录、8 车诊断汇总。
- 诚实边界：所有公开视频是有损派生音频；法律、原厂排气和同步状态未核验，所以没有真实身份分数、阶次图、自动调参或 Profile Candidate。
- 下载完整性补充：直接无代理路径恢复了原始 24 条 URL 的可解码音频，但仅证明媒体传输/解码完整；不能替代授权、原厂状态或同步 RPM/状态数据。
- 当前 R3 补充基线：已使用原始 URL 重试结果重算现有 Comparator；逐车中位数和不确定性报告只作为听审排序，不输出真实性百分比。
- Git 范围：仅入口代码、测试/计划修改和中文报告；`git ls-files '*.mp4' '*.webm' '*.wav'` 不新增本轮版权媒体，原始/派生下载物仍在外部目录。
- 中文听审交接：Jovi 可双击外部 `anchor_ab_zh_v1\index.html` 完成 9 个 R3 试次；反馈 JSON 回传后，先复核监听人编号、试次/片段 SHA 和完整性，再决定是否进入后续人工评审。页面反馈不能替代 R1 原始录音、同步状态或 MATLAB 阶次资格。

## S12 原始录音 R1 入库与低速率状态绑定（2026-08-23）

### 执行计划

- [x] 审计当前 Q/R 门禁和分支状态，保持 YouTube 派生音频为 R3，不将下载完整性改写成原厂 R1。
- [x] 以 TDD 新增原始 WAV/FLAC + 同步 RPM/Load/Throttle/Gear/shift 的外部入库合同；输出仅为 manifest/report，不复制原始媒体。
- [x] 实现批准目录、来源/授权、车型/原厂排气、单位、时间窗口、递增时间戳和原始 SHA-256 的 fail-closed 校验；不完整状态不得进入 R1 或自动调参。
- [x] 实现 Stage R 对带时间戳低速率遥测的非外推网格绑定：连续量线性插值，挡位/换挡事件离散映射；增加无重采样 FLAC 外部临时输入支持。
- [x] 将 raw intake manifest 接入 Stage Q canonical `reference_database_v2` 合并入口，生成 evidence matrix、时间窗口切片、RPM/state bindings、provenance 和派生特征指针，并用 JSON Schema 验证。
- [x] 将已审计授权 R2 manifest 接入同一 Stage Q canonical 合并入口；入口重新核验外部音频 SHA-256，登记 Ferrari/Hellcat/Supra 各一条及 RX-7sim 五条 R2 指针，不复制原始媒体。
- [x] 2026-08-23 审计 RX-7sim 作者录音：确认 1993 Mazda RX-7 页面/仓库与 `CC BY-NC-SA 4.0`，外部 OGG/WAV SHA 与 `ffprobe` 元数据绑定；5 条进入 R2，R1 仍因缺同步 RPM/state、精确 trim、原厂排气和 AGC 合同而关闭。
- [x] 2026-08-23 对 RX-7sim `exhaust/revLong01` 的 `full_pull` 运行 Stage R R2 Comparator；结果 `spectral_log_distance=0.662500`、`loudness_delta=-0.1404 dB`、`order=not_evaluated_without_rpm_trace`，无参数建议。其余 4 条因缺语义匹配候选未比较，禁止跨工况复用代理。
- [x] 修复 Stage R 参考 SHA 校验的大小写兼容性，并新增回归测试；大写清单 SHA 与 `hashlib` 小写输出现在按十六进制等价比较。
- [x] 更新中文入口指南、Q/闭环报告和本任务接力记录；明确当前真实资料仍为 `R1=0`。
- [x] 验证完整 S12、Track-P、独立冻结守卫、compileall 和 diff 门禁；仅在验证通过后提交并推送本分支。

### Review

- 原始入库/Stage Q/R/S/T 历史重点测试：`26 passed`；本轮完整 S12：`386 passed, 114 subtests passed`；本轮 Stage S/R 聚焦：`11 passed`；Track-P pytest `32 passed`，冻结守卫仍为 180 个冻结文件、2 个冻结符号。
- 独立守卫：`180` 个冻结文件、`2` 个冻结符号均未改动；`git diff --check` 干净；未启动 MATLAB、未生成 MATLAB/MoSQITo 收据、未改变 Runtime/Android/ESP32/CAN/Simulink/Track-P。
- 结果边界：入口和合同已完成，真实 R1 数据、MATLAB 阶次比较、人耳 A/B、参数建议和 Profile Candidate 仍等待 Jovi 提供合法原始录音及同步状态；不得据此宣称闭环完成。
- 本轮新增验证：Stage Q canonical 为 23 条记录，其中 8 条授权 R2、15 条 R3、R1=0；授权 R2 SHA 完整性、大小写兼容和错哈希拒绝路径均有回归覆盖。RX-7sim Stage R 单案结果保留 `R2_LIMITED_COMPARISON_COMPLETE`，不提升为 R1。

## S12 Stage S RX-7sim 中文 R2 A/B 交接（2026-08-23）

> 状态：`R2_LIMITED_COMPARISON_ONLY / WAITING_FOR_JOVI_HUMAN_FEEDBACK`；只写仓库内元数据和收据，原始/试听音频均在 `E:\\Claude_allow\\Download`。

- [x] 修复中文 A/B 构建器对参考/候选 SHA 的大小写敏感问题，并新增回归测试；不会放宽 SHA、路径或音频完整性门禁。
- [x] 为唯一语义匹配的 RX-7sim `exhaust/revLong01` `full_pull` 生成外部中文离线 A/B 页面：`E:\\Claude_allow\\Download\\s12-rx7sim-human-ab-zh-20260823\\package\\index.html`。
- [x] 固化 `test_id=s12-stage-s-r2-ab-20260822`、研究清单 SHA `68D525669E7789AF2A3570BE90E01FCD6AB571DEA0EA4866ACB2AE7DDB2FC428`、反馈绑定 SHA `4ABF650DFED136A327A8828F9B1710417A3051437F7F85435DFBF8CE5FA4BD26`、中文页面 SHA `586322EE697AACDD0ED429A36DCB4531A1BDA01E4D9598C84A6AC590A25EF6BB`、中文说明 SHA `AF2C91F1B3E5ED1B02A02F8FF9B44E8AB149C24C93ECB3178365E65B284C1EBA` 及参考/候选/试听副本 SHA。
- [x] 写入 `tasks/reports/runtime/s12-stage-s-human-calibration/rx7sim-20260823/` 元数据收据和中文交接报告；4 条无语义匹配候选的 RX-7sim 录音不进入 A/B。
- [ ] 等待 Jovi 返回带 `test_id`、研究清单 SHA、案例 ID、参考/候选 SHA、监听设备和中文评分的反馈 JSON；在此之前调音轮次为 `0`，不生成 Profile Candidate。

### Review

- 页面只导出反馈，不自动调参；试听副本明确不用于 Comparator 指标。
- R2 仍无同步 RPM/state，阶次为 `not_evaluated_without_rpm_trace`；R1 仍为 `0`。

## S12 Stage S 反馈绑定修订与 YouTube 403 独立复试（2026-08-23）

### 执行计划

- [x] 先以 TDD 为页面与反馈导入合同写出失败测试，再实现中文页面和 fail-closed 校验。
- [x] 页面补齐监听人、播放设备、系统音量、输出端点、系统音效、机器维度键、案例 SHA 和中文标签；导出不授予自动调音/Profile 权限。
- [x] 新增 `feedback_import.py` 与 CLI：校验 study/binding/feedback SHA、test_id、案例集合、参考/候选 SHA、R2 状态和播放元数据；重复/缺失案例拒绝。
- [x] 用全新外部目录 `E:\Claude_allow\Download\s12-rx7sim-human-ab-zh-20260823-v3\package` 可重建生成中文 A/B 包，原始和试听音频不进 Git。
- [x] 对 Ferrari 458 的 YouTube 403 用 `web_safari`、`android+bestaudio`、`android+best` 做独立复试；最后一条通过严格 `ffmpeg -xerror`，写入外部回执。
- [x] 完成全量 S12、Stage S/R 聚焦、Track-P pytest、冻结守卫、compileall、Node 页面脚本和外部 WAV/SHA 检查。
- [ ] 等待 Jovi 返回完整真实听审 JSON；在 R1 同步录音和反馈到位前，不启动 MATLAB 阶次、自动调音或 Profile Candidate。

### Review

- 最新全量 S12：`391 passed, 114 subtests passed in 148.81s`；Stage S/R 聚焦：`16 passed`；Track-P：`32 passed`。
- 外部 v3 包：研究清单 SHA `2BF26029B68DCAC80C7A9896DC570C18BC3D9F52B5F07C500F38C9A865CE501C`，中文页面 SHA `65B43B200E4C4A2771CFF8E35A375A3DC62EFFC9B49029CA043F3A004D192A7D`，Node `--check` 通过，试听 WAV 可打开。
- YouTube 单条复试：`ferrari_01` 最终媒体 SHA `6576BFCEC095E4FD27DD437FA5D32D05319995599F6319A9695545AF62040B40`，`143.058141 s`，H.264/AAC，全流解码通过；仍是 YouTube 派生 `R3_DIAGNOSTIC_ONLY`。
- 真实闭环仍未完成：`R1=0`、反馈行数 `0`、调音轮次 `0`、Profile Candidate 未生成；下载完整性不等于授权、原厂状态或同步 RPM/state。

## S12 三锚点 R1 入库模板（2026-08-23）

- [x] 新增 `tasks/reports/runtime/s12-stage-q-real-reference/r1_intake_request_v1.json`，固定 Ferrari 458、Hellcat、RX-7 FD 的 R1 必填字段、状态单位、时间戳与 fail-closed 接受门。
- [x] 模板明确原始 WAV/FLAC、RPM/Load/Throttle/Gear/shift 状态和授权文件只放仓库外；Git 只保存路径别名、SHA、来源和派生特征指针。
- [x] 模板验证通过：`r1_intake_request=PASS bytes=2954`；当前仍无任何真实 R1 记录，不启动 MATLAB 阶次、Comparator 资格调参或 Profile Candidate。
- [ ] 等待 Jovi/许可方提供三锚点合法原始音频与同步状态；填充模板后再运行 `raw_audio_intake`、MATLAB 阶次、Comparator 和中文人耳 A/B。

## S12 YouTube 403 回退与导入探针去重审计（2026-08-23）

- [x] 独立复测 `c63_03 / vIbiUABVZO4`：默认 `yt-dlp` 返回 `HTTP 403`，切换 `Node.js + EJS + android`、`format=best` 成功下载 10,340,349 字节 MP4；`ffprobe`、`ffmpeg -xerror` 全流解码和 21,422,158 字节 PCM WAV 再解码均通过。
- [x] 固化外部回执 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v4_probe\probe_receipt_c63_03_v2.json`，SHA-256 `C1E39775BB97B2A833DA915B67F0481CA3702F85B6F476750CACF887EF748DE5`；原始媒体、WAV、日志和不完整探针结果均留在 `E:\Claude_allow\Download`，不进入 Git。
- [x] 审计 `E:\Claude_allow\Download\s12-rx7sim-q-import-probe-20260823-v2`：无原始媒体；canonical manifest SHA 为 `D317D2E10193D12B6607B59A714ABF4A55DCEE78A94C30ED96070F6D2DBC3E46`，探针元数据/派生文件逐文件相同，23 条外部路径均为既有记录；不重复合并、不改变 `R1=0/R2=8/R3=15`。
- [x] 复核中文 A/B 包 `s12-rx7sim-human-ab-zh-20260823-v3`：反馈模板仍为空，`feedback_binding.status=WAITING_FOR_JOVI_HUMAN_FEEDBACK`；不把模板当作人耳反馈，不启动 Stage S 调音。
- [x] 2026-08-23 重新核对 Ferrari 458、Hellcat、RX-7 商业录音库的车型、同步 take、录音链和许可边界；写入 `tasks/reports/runtime/s12-stage-q-real-reference/procurement_candidate_revalidation_20260823.json`。三者均保持 `PROCUREMENT_CANDIDATE_NOT_R1`：未购买/未取得书面许可，且页面未提供数值同步 RPM/Load/Throttle/Gear 文件；未下载版权原始音频。
- [x] 修复 Track-P guard 对 Stage-Q/R `run_r2_matlab_psychoacoustic_audit.m` 的保守 `matlab` 路径假阳性：按 Baseline v3 §3.3 仅加入精确 Track-S allowlist，不改变 180 个冻结文件或 2 个冻结符号；guard 与聚焦回归重新通过（`69 passed`）。
- [x] 修正 R1 资格门对采集链的过窄假设：麦位不再限定 `EXTERIOR_REAR`，AGC 不再限定 `DOCUMENTED_NO_AGC`；只要明确记录即可，UNKNOWN/空值仍拒绝。新增测试覆盖 `INTERIOR_CABIN_DASH`、`DOCUMENTED_AGC_ON_WITH_LEVEL_TRACE` 和未知值；R1 计数仍为 0。
- [x] 当前 HEAD `10a78bc2` 最终回归：S12 核心 `394 passed, 114 subtests`（147.48s）+ Track-P pytest `32 passed`（1.21s），合计 `426 passed, 114 subtests`；独立冻结守卫 `180 files / 2 symbols PASS`，compileall、JSON 包校验和 `git diff --check` 通过。
- [ ] 仍需合法原始 R1 录音、同步 RPM/Load/Throttle/Gear/shift 和 Jovi 绑定 SHA 的中文反馈；在输入到位前保持 `WAITING_FOR_REAL_REFERENCE_DATA`，不运行 MATLAB 阶次或自动调参。
- [x] 公开同步数据候选复筛：Lincoln MKS、HL-CEAD 和 Dodge 同步记录功能均不满足三锚点 R1；记录在 `public_synchronized_source_screening_20260823.json`，未下载不合格或未授权原始媒体。

## S12 Stage Q-R1 Pilot Acquisition and R2 Human Feedback Closure（2026-08-23）

- [x] A 线校验 `anchor_ab_zh_v1`：manifest/receipt/page 通过，9 个试次、18 个试听片段 SHA 全部匹配；收据位于 `tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1/anchor_ab_validation.json`。
- [x] A 线新增 anchor 导出 JSON 的 fail-closed 适配器：严格绑定 package SHA、试次/试听 SHA、评分、偏好、备注和问题分类；没有反馈时保持 `WAITING_FOR_JOVI_HUMAN_FEEDBACK`，有限建议为空且 `parameter_changes=0`。
- [x] B 线新增 Hellcat 默认供应方/车主联系模板、OBD/CAN 与音频同步采集说明、spec/rights/三状态 CSV/SHA 空模板；模板树不含任何原始媒体。
- [x] B 线新增 rights scope、逐文件 SHA、时间戳单调性/窗口覆盖和既有 raw_audio_intake 汇总预检；完整 fixture 可达 `R1_PILOT_READY`，但仍关闭自动调参和 Profile Candidate。
- [x] 当前真实外部目录 `E:\Claude_allow\Download\s12-r1-pilot\hellcat_full_pull_01` 尚不存在；已生成等待态 `S12_R1_Pilot_Acquisition_Report.md`、`r1_pilot_preflight.json`、`rights_scope_validation.json`、`state_sync_validation.json`、`comparison_results.json`、`parameter_recommendations.json` 和 `feedback_gate.json`，状态 `WAITING_FOR_R1_PILOT_DELIVERY`。
- [x] 当前 focused TDD：anchor/A 线 `8 passed`；模板 `4 passed`；R1 preflight `7 passed`；端到端等待态 `2 passed`。真实文件到位前不调用 MATLAB、不运行 Order hard gate、不修改声源。
- [ ] 等待 Jovi 提供完整反馈 JSON 和 Hellcat（或指定车型）R1 试点目录；收到后按 `raw_audio_intake → Stage Q → MATLAB/MoSQITo → Comparator → 中文 A/B → 有界调音 → 回归` 顺序推进。

## S12 Professional Comparison Dashboard v1 + R2 Diagnostic Tuning（2026-08-23）

- [x] Phase 1：按 `anchor_ab_zh_v1` 实际 manifest 审计 9 对/18 个片段；reference/candidate 文件、时长、SHA、file-ID 和 Order 未资格边界已写入 `S12_Professional_Comparison_Dashboard_v1/clip_integrity.json`。
- [x] Phase 2：MATLAB R2026a Audio Toolbox 对 18 条 exact clip 真实执行六项心理声学指标；隔离 MoSQITo 1.2.1 对同一 18 条执行；两者分别绑定 reference/candidate SHA，MoSQITo 不支持的 fluctuation 列明确为 null，不用 Proxy 冒充。
- [x] Phase 3：生成 `professional_pair_metrics.json`、`professional_plain_language_diagnosis.json` 和中文 `S12_Professional_Comparison_Report.md`；三类域分列，没有总相似度百分比。
- [x] Phase 4：生成中文 `S12_Professional_Comparison_Dashboard_v1/index.html`；显示播放器、canplaythrough/时长/SHA 门、R3/麦位不确定性、MATLAB/MoSQITo/Proxy、8 频带、频谱/残差、诊断和简化 Jovi 反馈导出。
- [x] Phase 5：三锚点各一个参数组、每组 64 个有界规格；`r2_diagnostic_candidate_results.json` 明确 `SPECIFICATIONS_ONLY_NOT_RENDERED`，不修改 source、不运行 Order、不生成 Profile Freeze。
- [x] Dashboard 静态合同、0-duration/SHA/file-ID 门、Playwright Chromium 音频加载 smoke、Node 语法、JSON 校验已通过。
- [x] Jovi 已提交长窗口 `Jovi_Guided_Feedback.json`；完成 SHA/file-ID/音频门校验并按确认的问题组生成 R2 有界复核收据。

## S12 Professional Long-Window Extension（2026-08-23）

- [x] 发现旧页面候选 WAV 只有 6.25 秒；未循环拼接或静音补齐，保留 5 秒 exact 基线不变。
- [x] 外部生成 60 秒本地完整循环（怠速→加速→全负荷→收油/减速→巡航→怠速），目录 `E:\Claude_allow\Download\s12-professional-long-window-candidate-v1`，不进入 Git。
- [x] 从真实长 reference 和 60 秒本地循环生成 15/30 秒派生窗口：18 对（15 秒 9 对、30 秒 9 对），目录 `E:\Claude_allow\Download\s12-professional-long-window-v1`；只做时间切片，无增益/EQ/AGC/重采样。
- [x] 长窗口 Legacy Proxy、MATLAB R2026a、MoSQITo 1.2.1 均已执行；长窗口 Order 仍为 `ORDER_COMPARISON_NOT_QUALIFIED`。
- [x] 新增长窗口页面 `S12_Professional_Comparison_Dashboard_v1/long_window.html`，5 秒基线页面保留；长窗口 Guided Feedback 模板为 `Jovi_Guided_Feedback_Long_Window.json`。
- [x] Jovi 已完成 15 秒/30 秒长窗口车型聚合反馈；反馈仍保持 R3 诊断边界，不执行自动参数修改。

## Dashboard Feedback UX 修复（2026-08-23）

- [x] 将原生 `select multiple` 改为可直接点击的 `.problem-chip` 标签，不再要求 Ctrl 多选。
- [x] 将反馈粒度从 18 个试次改为每车型一行；三辆车各完成一次身份/真实感/问题/偏好/备注后，用一个“提交全部车型反馈”按钮导出。
- [x] 增加“已听完本车型当前窗口”确认；浏览器验证了三车型填写后按钮从禁用变为可提交，空反馈仍 fail-closed。
- [x] Guided Feedback v2 导入器支持车型聚合 rows，并继续校验 SHA/file-ID、音频门和自动调音/Profile 禁止。
- [x] 收到 `C:\Users\Admin\Downloads\Jovi_Guided_Feedback.json` 后完成 v2 导入；未修改声源。

## S12 Dashboard 长窗口反馈导入与 R2 有界复核（2026-08-23）

- [x] 复现并定位浏览器 number input 导出为字符串导致的导入失败；新增纯整数字符串规范化，仍拒绝小数、越界、空值和布尔值；Dashboard 导出改为整数并加 `step=1`。
- [x] 实际反馈文件通过长窗口 metrics：3 个车型、18 对窗口、每车 6 个 pair/file/SHA、音频提交门 `PASS`；验证收据 `Jovi_Guided_Feedback_Long_Window_Validation.json`。
- [x] 生成 `long_window_parameter_recommendations.json`：Ferrari 与 Hellcat 各保留一个 64 规格参数组；RX-7 因人声污染阻塞；回火/换挡/转速事件保持不调。
- [x] 更新 `S12_Professional_Long_Window_Report.md`，记录评分、偏好、问题分类、备注摘要和 R1/R2/R3 边界。
- [x] 聚焦反馈回归 `5 passed`；待执行长窗口 Dashboard smoke、JSON/Node/compileall、全量 S12 与 Track-P 冻结守卫后提交推送。

### Review

- Jovi 反馈输入 SHA-256：`acfbcbab2022612621aba2cec8a73a5dbc193e0a142f247989f81b00356b673d`；长窗口 manifest SHA 保持 `ecbe8dc92fa63ed00a76e1554a37a1ff452aaa6af0eff5b3bd3edbadcd64c2a1`。
- 当前结果：`R2_DIAGNOSTIC_REVIEW_READY / NOT_R1_QUALIFIED`；`parameter_changes=0`、`automatic_tuning_eligible=false`、`profile_candidate_ready=false`。

## S12 主题化听审与 RX-7 清洁参考 R2（2026-08-23）

- [x] 设计并提交 `docs/superpowers/specs/2026-08-23-s12-rx7-topic-aware-r2-design.md` 与实施计划；保留历史 R3 页面和外部原始音频边界。
- [x] Dashboard 两套页面新增中文 `focus_topics`：怠速、加速、减速/收油、换挡、回火/爆音、转速变化、音色/机械感；新导出为 v3，每车至少选一个主题；v1/v2 旧反馈仍可导入。
- [x] 修复 MoSQITo 长窗口收据对非 15/30 秒 native 窗口的硬编码，改为从 manifest 推导窗口时长。
- [x] 外部构建 `E:\Claude_allow\Download\s12-rx7-topic-r2-v4`：5 条作者 R2 参考、5 条有界 RX-7 候选，原生时长 `7.658208/7.679917/14/16.5 s`；参考为字节一致外部副本，未循环/补静音/处理参考。
- [x] RX-7 候选只改 `rotary_housing_turbo_distribution` 一组参数，并以一次固定候选增益留出 `-1.5 dBFS` 余量；source/PTR/Radiation 未改，`parameter_changes=1` 仅表示候选版本已渲染。
- [x] MATLAB R2026a 已在打开会话中逐条执行 `10` 个信号；批处理一次性循环曾触发 `0xc0000005`，未采用崩溃收据；MoSQITo 1.2.1 隔离环境执行 `10` 个信号；MATLAB/MoSQITo/Proxy SHA 交叉校验通过。
- [x] 生成独立中文页面 `rx7_topic_r2.html`、数据 `rx7_topic_r2_results.json` 和报告 `rx7_topic_r2_report.md`；旧 R3 Dashboard 不覆盖。
- [x] 当前聚焦测试：主题/反馈/RX-7/专业收据 `32 passed`；统一证据矩阵测试通过；RX-7 页面 Playwright smoke PASS；全量 S12 `455 passed, 114 subtests`；5 秒、15/30 秒和 RX-7 页面 smoke 均 PASS；Track-P `32 passed`，独立守卫 `180 files / 2 symbols`。

## S12 Stage U — True Comparator-Driven Acoustic Regression（2026-08-23）

> 分支：`agent/s12-stage-u-true-comparator-calibration`；基线：`b1d500c7c37a71728020c39e6dc115a0cd6743d5`。

- [x] 创建隔离工作树并核验 exact HEAD、分支和 Track-P 基线；初始完整 S12 回归 `455 passed, 114 subtests`。
- [x] U0/U1：输出基线审计、Silero VAD/人工污染标志、SHA/时长/场景/麦克风合同和 Reference→Trace 场景匹配矩阵；11条目标参考中10条通过，`ferrari_03_15s` 因连续讲话 `3.1s` 标记 `REFERENCE_SPEECH_CONTAMINATED` 并排除。
- [x] U2：接入 MATLAB audioFeatureExtractor、AudioCommons timbral_models、可选 OpenL3 和有界 DTW；MATLAB 已对 RX-7 raw WAV 真实执行，timbral_models/OpenL3 因项目未维护的依赖问题明确标为 `PROJECT_UNMAINTAINED_NOT_AVAILABLE / NOT_HARD_GATE`。
- [x] U3：对 Ferrari/Hellcat/RX-7 的实际 renderer 参数做单变量可达性探针；15个 Stage-U source 控制均 `PARAMETER_REACHABILITY_PASS`，没有 unused，目标 stem 变化和非目标泄漏阈值均通过；RX-7 新网格禁用旧 `rotary_pulse_width_scale`，改用 `rotary_amplitude_scale` 与 housing/turbo 控制。
- [ ] U4：以同一 synthetic trace 渲染 Reference/Parent/Candidate，最多 64 候选/车；绑定 WAV/PCM/trace/stem/usage/health SHA。
- [ ] U5/U6：运行 Reference↔Parent、Reference↔Candidate、Parent↔Candidate 专业三方比较；基于中位改善/最坏回归选择或明确拒绝。
- [ ] U7：构建三播放器 + B/C 随机 ABX 中文页面，所有专业结果和听审文件绑定相同 SHA。
- [ ] U8：Stage U/Stage N/Q/R/S/full S12/Track-P/WAV-ZIP-SHA/diff 验证并推送。
