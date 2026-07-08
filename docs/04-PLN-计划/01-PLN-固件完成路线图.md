# Tesla Simulate Vico 固件完成路线图

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从当前可编译 ESP-IDF baseline 推进到最初设计需求：安全 CAN 监听、可信声浪模拟、BLE/SD/OTA 配置闭环、硬件实机验收和可交付固件。

**Architecture:** 当前工程以 ESP-IDF v5.3.2 为固件基线，`App` 负责协调 CAN、domain、audio、BLE、storage、input、ui、ota 组件。后续计划先关闭硬件验收与资源风险，再独立推进声浪算法建模和调参工具，避免把“可编译”误认为“产品可交付”。

**Tech Stack:** ESP32-S3-WROOM-1-N16R8, ESP-IDF v5.3.2, ESP-IDF NimBLE, TWAI listen-only, I2S PCM5102A, SD JSON, WS2812, HTTPS OTA, OpenSpec.

---

## 1. 当前基线

| 范围 | 当前状态 | 证据 / 文件 |
|---|---|---|
| CAN listen-only | 已实现 baseline | `components/can/`, `openspec/specs/twai-can-source/spec.md` |
| Tesla frame parser | 已实现 `0x256` / `0x116` baseline | `components/can/include/can/CanFrames.h` |
| I2S 音频输出 | 已实现 RPM 单音色 baseline | `components/audio/` |
| BLE 配置/状态 | 已实现 `0xfff0` 主服务 + `0xffe0` 兼容服务 | `components/ble/` |
| SD JSON 配置 | 已实现 | `components/storage/` |
| 编码器/油门电位器/WS2812 | 已接入 | `components/input/`, `components/ui/` |
| OTA baseline | 代码已接入，硬件未证明 | `components/ota/`, `partitions.csv` |
| 构建门禁 | 已通过 | `.\scripts\esp-idf.ps1 build`, `openspec validate --all --strict --json` |
| IRAM | 仍是 release 风险 | 最新记录 `16383 / 16384` |
| 实机验收 | 未完成 | BLE/WiFi/OTA/CAN/I2S/SD 都需要上板证据 |

## 2. 总体阶段划分

| 阶段 | 目标 | 进入条件 | 完成标准 | 状态 |
|---|---|---|---|---|
| S6.6 文档与验收基线收口 | 固化当前真相，形成可执行待办 | S7 baseline 已合入 | 计划、待完成清单、验收口径可追踪 | 进行中 |
| S7.1 硬件 bring-up | 证明固件能在 ESP32-S3 板上稳定启动 | 可烧录固件、串口可读 | boot log、BLE 广播、SD/LED/ADC/I2S smoke proof | 待开始 |
| S7.2 BLE/WiFi/OTA 验收 | 关闭 OTA baseline 的硬件证明 | BLE 可连接，WiFi 参数可写入 | WiFi join、HTTPS OTA 成功、失败回滚可证明 | 待开始 |
| S7.3 IRAM release hardening | 解决或正式接受 IRAM 风险 | `size-components` 归因清楚 | IRAM 不再卡 1 byte，或有签字风险接受记录 | 阻塞 |
| S8.1 声浪算法建模 | 设计速度/加速度/负载差异化声浪 | baseline 音频链路可播放 | MATLAB/仿真参数、听感样本、固件算法接口冻结 | 待开始 |
| S8.2 声浪固件集成 | 将模型移植到 ESP-IDF 音频路径 | 模型参数已冻结 | 多层音色/动态负载/overspeed/mute 通过 bench test | 待开始 |
| S9 调试与高级调参 | 增加 USB CDC / 调参入口 | S7 硬件稳定 | host 能读写参数、导出状态、保存配置 | 待开始 |
| S10 产品化验收 | 形成可烧录可回归的交付包 | 核心功能全部验收 | release bin、测试报告、使用说明、已知风险清单 | 待开始 |

## 3. 阶段执行计划

### Task 1: S6.6 文档与计划收口

**Files:**
- Create: `docs/04-PLN-计划/01-PLN-固件完成路线图.md`
- Create: `docs/09-TOD-待完成/01-TOD-固件待完成清单.md`
- Create or modify: `docs/README.md`
- Reference: `PLAN.md`
- Reference: `README.md`
- Reference: `openspec/specs/*/spec.md`

- [ ] **Step 1: 核对当前状态源**

Run:

```powershell
cd E:\Tesla_speed\prj
git status --branch --short
openspec validate --all --strict --json
```

Expected:

- Git 工作树没有未解释的源码改动。
- OpenSpec `5/5` pass。

- [ ] **Step 2: 更新计划与待完成清单**

更新本文件和 `docs/09-TOD-待完成/01-TOD-固件待完成清单.md`，确保每个未完成项至少包含：

- 所属阶段
- 优先级
- 当前状态
- 验收证据
- 阻塞条件

- [ ] **Step 3: 提交文档变更**

Run:

```powershell
cd E:\Tesla_speed\prj
git diff --check
git add docs/04-PLN-计划/01-PLN-固件完成路线图.md docs/09-TOD-待完成/01-TOD-固件待完成清单.md docs/README.md
git commit -m "Document firmware completion roadmap"
git push origin main
```

Expected:

- 远端 `main` 指向新提交。
- GitHub 页面可以看到计划和待完成清单。

### Task 2: S7.1 硬件 bring-up

**Files:**
- Modify if needed: `docs/06-TST-测试/`
- Modify if needed: `docs/07-DBG-调试/`
- Reference: `components/config/include/config/pin_map.h`
- Reference: `scripts/esp-idf.ps1`

- [ ] **Step 1: 烧录当前 baseline**

Run:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 -p COMx flash monitor
```

Expected:

- 固件启动无 panic。
- 串口能看到 app 启动、BLE 初始化、SD 初始化、audio 初始化状态。

- [ ] **Step 2: 记录板级 smoke test**

新增测试记录到 `docs/06-TST-测试/`，至少记录：

- 硬件板卡型号
- 烧录时间
- 串口号
- 固件 commit
- boot log 摘要
- 是否有 reset loop / watchdog / brownout

- [ ] **Step 3: 外设 smoke proof**

逐项验证并记录：

- WS2812 状态灯是否亮起并按状态变化
- 编码器旋转是否影响音量配置
- 油门电位器 ADC 是否产生稳定输入
- SD 卡缺失和插入两种情况是否可启动
- I2S DAC 是否有可听输出或示波器波形

### Task 3: S7.2 BLE/WiFi/OTA 验收

**Files:**
- Modify if needed: `components/ble/`
- Modify if needed: `components/ota/`
- Modify if needed: `docs/06-TST-测试/`
- Reference: `README.md`

- [ ] **Step 1: BLE 广播验收**

Use a BLE scanner and verify:

- `0xfff0` primary service is visible.
- `0xffe0` compatibility service is visible if supported by scanner display.
- Device name and reconnect behavior are stable for at least 5 reconnects.

- [ ] **Step 2: BLE 读写验收**

Verify:

- `ffe2` read returns stable state JSON.
- One writable non-OTA characteristic can write and read back.
- `ffe8` accepts OTA settings JSON with `ssid`, `password`, `ota_url`, `auto_check`.
- Oversize or malformed `ffe8` payload is rejected without crash.

- [ ] **Step 3: WiFi join 验收**

Procedure:

1. Write WiFi/OTA settings through `ffe8`.
2. Reboot device.
3. Confirm WiFi join success from serial log and `ffe5` diagnostics JSON.

Expected:

- Wrong password produces clear `last_error`.
- Correct credentials join within the chosen timeout.

- [ ] **Step 4: HTTPS OTA 成功路径**

Procedure:

1. Host a signed/valid firmware image at configured HTTPS URL.
2. Enable `ota_auto_check`.
3. Reboot and observe OTA task.
4. Confirm boot partition changes after update.
5. Confirm reported version matches new image.

- [ ] **Step 5: HTTPS OTA 失败路径**

Verify:

- Invalid URL does not brick device.
- Invalid image does not mark app valid.
- Network failure leaves previous firmware bootable.
- `ffe5` reports `ota_last_result` and `last_error`.

### Task 4: S7.3 IRAM release hardening

**Files:**
- Modify if needed: `sdkconfig.defaults`
- Modify if needed: `components/*/CMakeLists.txt`
- Modify if needed: `docs/08-RPT-报告/`

- [ ] **Step 1: Reproduce current size**

Run:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
```

Expected:

- Record exact IRAM/DIRAM/Flash numbers.
- Identify top `.iram0.text` component consumers.

- [ ] **Step 2: Decide risk path**

Choose one path:

- Reduce IRAM until the margin is no longer `1` byte.
- Or document an explicit risk acceptance after hardware OTA/BLE stress passes.

- [ ] **Step 3: Stress test after config changes**

After any IRAM-related config change, re-run:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
```

Expected:

- Build remains green.
- BLE/WiFi/OTA hardware smoke tests are repeated if Bluetooth/WiFi placement changes.

### Task 5: S8.1 声浪算法建模

**Files:**
- Create: `docs/04-PLN-计划/02-PLN-声浪算法建模计划.md`
- Create: `docs/06-TST-测试/声浪算法验证记录.md`
- Modify later: `components/domain/`
- Modify later: `components/audio/`

- [ ] **Step 1: Define sound model inputs**

Freeze input signals:

- `speed_kph`
- `throttle`
- computed acceleration
- optional jerk
- virtual RPM
- overspeed / mute state

- [ ] **Step 2: Add acceleration state design**

Plan a firmware-friendly state extension:

```cpp
struct VehicleDynamics {
    float speed_kph;
    float acceleration_mps2;
    float throttle;
    float virtual_rpm;
};
```

Acceptance:

- Acceleration is derived from speed delta and tick interval.
- Low-pass filter behavior is defined before implementation.

- [ ] **Step 3: MATLAB or equivalent probe modeling**

Build a tuning worksheet/script that outputs:

- RPM-to-base-frequency curve
- load-to-amplitude curve
- acceleration-to-harmonic gain curve
- overspeed mute behavior
- fixed-point or bounded float parameter ranges for firmware

- [ ] **Step 4: Bench listening samples**

Generate test scenarios:

- idle
- gentle acceleration
- hard acceleration
- cruise
- deceleration
- overspeed mute

Expected:

- Each scenario has waveform and listening note.
- Parameters are small enough for ESP32-S3 real-time synthesis.

### Task 6: S8.2 声浪固件集成

**Files:**
- Modify: `components/domain/include/domain/VehicleState.h`
- Modify: `components/domain/include/domain/EngineModel.h`
- Modify: `components/audio/I2sAudioEngine.cpp`
- Modify: `components/audio/include/audio/I2sAudioEngine.h`
- Add tests under: `components/audio/test/`

- [ ] **Step 1: Add unit/compile tests for model boundaries**

Add tests that verify:

- speed delta produces bounded acceleration
- throttle gain is clamped
- overspeed mute overrides output
- invalid CAN gaps decay safely

- [ ] **Step 2: Implement minimal multi-layer synth**

Implementation target:

- base engine tone
- second harmonic layer
- acceleration/load layer
- controlled noise or pulse layer only if CPU budget allows

- [ ] **Step 3: Verify timing and CPU safety**

Acceptance:

- Audio render does not block the 25ms app tick.
- No heap allocation in hot render path.
- Build and size remain green.

### Task 7: S9 USB CDC / 调参工具

**Files:**
- Create later: `components/diagnostics/`
- Modify later: `components/app/`
- Modify later: `components/config/include/config/runtime_config.h`
- Create later: host-side tool docs in `docs/05-WORK-执行/`

- [ ] **Step 1: Freeze command schema**

Minimum commands:

- `GET_STATUS`
- `GET_CONFIG`
- `SET_CONFIG`
- `SAVE_CONFIG`
- `AUDIO_TEST`
- `REBOOT`

- [ ] **Step 2: Implement read-only status first**

Acceptance:

- Host can open CDC port.
- Device returns version, partition, CAN valid, speed, throttle, RPM, volume, OTA status.

- [ ] **Step 3: Add writable tuning parameters**

Acceptance:

- At least one audio parameter supports set/readback/save/reboot persistence.
- Invalid values are rejected and reported.

### Task 8: S10 产品化交付

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`
- Create: `docs/08-RPT-报告/最终交付报告.md`
- Create: `docs/06-TST-测试/最终验收记录.md`

- [ ] **Step 1: Final regression gate**

Run:

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
```

- [ ] **Step 2: Hardware regression gate**

Verify:

- boot
- CAN listen-only
- BLE read/write
- SD persistence
- I2S output
- encoder/pot/LED
- WiFi OTA success/failure
- USB CDC if included

- [ ] **Step 3: Release package**

Package:

- firmware `.bin`
- partition table
- bootloader
- flash command
- version/commit
- known risks
- hardware test notes

## 4. Release Gate Definition

S10 之前，不能把项目描述为“完成最初设计需求”，除非以下证据齐全：

- [ ] build/size/size-components/OpenSpec 全通过
- [ ] 实机 boot/flash/monitor 通过
- [ ] BLE 广播、连接、读写回读通过
- [ ] WiFi join 和 HTTPS OTA 成功/失败路径通过
- [ ] CAN listen-only 在真实或可信仿真输入下通过
- [ ] I2S 声音输出通过听感或示波器验证
- [ ] 声浪算法已包含速度/加速度/负载差异化，并有 MATLAB 或等价模型记录
- [ ] IRAM 风险已解决或被明确接受
- [ ] README/PLAN/OpenSpec/docs 与代码状态一致

## 5. 当前优先级建议

1. 先做 S7.1/S7.2：硬件 bring-up、BLE/WiFi/OTA 验收。
2. 同步推进 S7.3：IRAM 风险关闭或风险接受。
3. 再做 S8：声浪算法建模与固件集成。
4. 最后做 S9/S10：USB CDC、高级调参和最终交付包。

这样排的原因很直接：硬件和 OTA 不稳时，继续堆算法会让问题更难定位；先证明设备可靠，再提升声音质量，整体风险最低。
