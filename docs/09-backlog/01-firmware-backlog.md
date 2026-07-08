# Tesla Simulate Vico 固件待完成清单

日期：2026-07-09

本清单用于 S7 之后持续追踪。它不是“全部已经完成”的证明；当前优先级是先完成 BLE / WiFi / IoT / OTA 架构迁移与门禁，再做硬件验收和声浪算法。

## P0 必须完成

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| P0-01 | 实机烧录与 boot log | 高 | 待实机 | `flash monitor` 无 panic/reset loop |
| P0-02 | BLE 广播服务可见 | 高 | 待实机 | 扫描到 `0xfff0` / `0xffe0` |
| P0-03 | BLE `ffe2` 状态读取稳定 | 高 | 待实机 | 多次读取字段稳定 |
| P0-04 | BLE `ffe8` 配置写入与读回 | 高 | 代码迁移中 | 写入 JSON 后 SD/读回一致 |
| P0-05 | SD JSON 实机读写 | 高 | 待实机 | 插卡保存/重启读回，无卡可启动 |
| P0-06 | I2S 硬件输出 | 高 | 待实机 | 听感或示波器波形 |
| P0-07 | encoder 音量调节 | 高 | 待实机 | 旋转后音量变化并保存 |
| P0-08 | throttle pot ADC 输入 | 高 | 待实机 | ADC 稳定并影响 throttle/RPM |
| P0-09 | WS2812 状态灯 | 高 | 待实机 | boot/running/muted/fault 可区分 |
| P0-10 | CAN listen-only 安全证明 | 高 | 待实机 | 代码无 transmit API，CAN 分析仪无发帧 |

## S7 BLE / WiFi / IoT / OTA

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| S7-01 | 统一运行状态镜像 | 高 | 代码迁移中 | `ffe5` 包含 WiFi/IoT/OTA/版本/分区/错误 |
| S7-02 | RuntimeConfig WiFi/OTA/IoT 字段 | 高 | 代码迁移中 | 旧 JSON 缺字段仍可加载，新字段可保存 |
| S7-03 | NetworkManager WiFi 状态机 | 高 | 代码迁移中 | 未配置、连接中、已连接、失败/重连状态可见 |
| S7-04 | IotManager MQTT 上线 | 高 | 代码迁移中 | 上报 device info / vehicle state |
| S7-05 | MQTT 下行 `ota_start` | 高 | 代码迁移中 | accepted/rejected ack，accepted 转 OTA request |
| S7-06 | HTTPS OTA 成功路径 | 高 | 待实机 | 下载、切分区、重启后版本变化 |
| S7-07 | HTTPS OTA 失败路径 | 高 | 待实机 | 坏 URL/坏镜像不损坏当前固件 |
| S7-08 | BLE 写配置不阻塞主循环 | 高 | 代码迁移中 | 写 `ffe8` 不在回调内执行 OTA |
| S7-09 | App 25 ms 主循环不阻塞 | 高 | 待验证 | build + 代码审查 + 实机观察 |

## 内存与 Release Hardening

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| MEM-01 | 复测 `idf.py size` | 高 | 持续复测 | 记录 IRAM/DIRAM/Flash |
| MEM-02 | 复测 `idf.py size-components` | 高 | 持续复测 | 记录 top IRAM consumers |
| MEM-03 | IRAM 1 byte margin 处理 | 高 | 阻塞 | 降低 margin 风险或形成接受记录 |
| MEM-04 | BLE controller flash placement 压测 | 中 | 待实机 | BLE/WiFi/OTA 同时运行不崩溃 |

## 声浪算法

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| AUD-01 | 声浪目标与听感样例 | 高 | 待开始 | idle/加速/巡航/减速/overspeed 场景 |
| AUD-02 | acceleration/dynamics 设计 | 高 | 待开始 | 速度差分、滤波、边界定义 |
| AUD-03 | MATLAB 或等价仿真 | 高 | 待开始 | 曲线、波形、参数、听感记录 |
| AUD-04 | 多层音色模型接口 | 高 | 待开始 | base/harmonic/load/noise 或 pulse layer |
| AUD-05 | 固件单元/编译测试 | 中 | 待开始 | 边界输入、overspeed mute、CPU/heap 安全 |
| AUD-06 | I2S bench listening | 高 | 待实机 | 真实输出听感或录音 |

## 文档与交付

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| DOC-01 | `PLAN.md` 状态同步 | 中 | 持续维护 | 每次阶段完成后更新 |
| DOC-02 | OpenSpec 同步 | 高 | 持续维护 | `openspec validate --all --strict --json` 通过 |
| DOC-03 | 硬件验收记录 | 高 | 待开始 | `docs/06-testing` 有实测记录 |
| DOC-04 | 最终交付报告 | 中 | 待开始 | build/size/hardware/release 全部记录 |
| DOC-05 | GitHub README 保持真实 | 中 | 持续维护 | 不夸大完成度 |

## 推荐执行顺序

1. 先关 S7 代码和文档门禁。
2. 再做 P0-01 到 P0-10 的硬件 bring-up。
3. 关闭 S7-01 到 S7-09 的 BLE/WiFi/MQTT/OTA 实机验收。
4. 处理 MEM-01 到 MEM-04 的 IRAM release gate。
5. 单独启动 AUD-01 到 AUD-06 的声浪算法建模与固件集成。
6. 每个阶段结束都同步 README、PLAN、OpenSpec、测试记录和本清单。
