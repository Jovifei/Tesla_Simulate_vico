# Tesla Simulate Vico 固件待完成清单

日期: `2026-07-08`
状态: 当前清单用于 S7 之后继续追踪，不代表所有功能已经实现。
对应计划: `docs/04-PLN-计划/01-PLN-固件完成路线图.md`

---

## 1. P0 必须完成

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| P0-01 | 实机烧录与 boot log 验收 | 高 | 待开始 | `flash monitor` 日志、无 panic/reset loop | 需要 ESP32-S3 实物 |
| P0-02 | BLE 广播服务可见 | 高 | 待开始 | 扫描到 `0xfff0` / `0xffe0` | 需要手机或 BLE scanner |
| P0-03 | BLE `ffe2` 状态读取稳定 | 高 | 待开始 | 多次读取 JSON 稳定、字段完整 | 需要实机连接 |
| P0-04 | BLE 可写特征读写回环 | 高 | 待开始 | 写入后读取一致 | 至少验证 1 个非 OTA 可写项 |
| P0-05 | SD JSON 配置实机读写 | 高 | 待开始 | 插卡保存/重启读回、无卡可启动 | 需要 SD 卡和串口日志 |
| P0-06 | I2S 音频硬件输出 | 高 | 待开始 | 听感或示波器波形 | 需要 PCM5102A / 音频链路 |
| P0-07 | 编码器调音量实机验证 | 高 | 待开始 | 旋转后音量即时变化并可保存 | 依赖 I2S 或日志状态 |
| P0-08 | 油门电位器 ADC 输入验证 | 高 | 待开始 | ADC 值稳定，能影响 throttle/virtual RPM | 需要电位器接线 |
| P0-09 | WS2812 状态灯验证 | 高 | 待开始 | 不同状态有可见变化 | 需要板级电源稳定 |
| P0-10 | CAN listen-only 安全证明 | 高 | 待开始 | 代码无 transmit API，实机不发帧 | 最好用 CAN 分析仪验证 |

## 2. S7 OTA 与联网

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| S7-01 | BLE `ffe8` 写入 WiFi/OTA 配置 | 高 | 代码已实现，待实机 | 写入 JSON 后 SD/状态可读回 | 需要 BLE client |
| S7-02 | WiFi join 成功路径 | 高 | 待开始 | 串口日志 + `ffe5` 诊断显示 connected | 需要可用 WiFi |
| S7-03 | WiFi join 失败路径 | 中 | 待开始 | 错误密码有 `last_error`，设备不崩溃 | 需要错误凭据测试 |
| S7-04 | HTTPS OTA 成功升级 | 高 | 待开始 | 新镜像下载、切分区、重启后版本变化 | 需要 OTA server 和证书 |
| S7-05 | HTTPS OTA 失败/非法镜像保护 | 高 | 待开始 | 旧固件可继续启动，错误可读 | 需要构造坏 URL/坏镜像 |
| S7-06 | OTA 期间 BLE/WiFi 稳定性 | 中 | 待开始 | OTA 过程中无 panic，升级后 BLE 可用 | 与 IRAM/flash placement 相关 |
| S7-07 | OTA 版本/分区诊断完善 | 中 | 代码有 baseline | `ffe5` 返回 version、partition、last result | 需实机确认 |

## 3. 内存与 release hardening

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| MEM-01 | 复测 `idf.py size` | 高 | 待复测 | 最新 IRAM/DIRAM/Flash 记录 | 每次功能合入后都要记录 |
| MEM-02 | 复测 `idf.py size-components` | 高 | 待复测 | 组件级 IRAM 归因 | 当前 IRAM 曾为 `16383 / 16384` |
| MEM-03 | IRAM 1 byte margin 处理 | 高 | 阻塞 | 不再卡 1 byte，或形成风险接受记录 | 不可静默跳过 |
| MEM-04 | BLE controller flash placement 风险验证 | 中 | 待实机 | BLE/WiFi/OTA stress 通过 | 关联 `CONFIG_BT_CTRL_RUN_IN_FLASH_ONLY` |
| MEM-05 | 禁止新增热路径 heap allocation | 中 | 待代码审查 | audio render path 无动态分配 | 声浪算法阶段尤其重要 |

## 4. 声浪算法

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| AUD-01 | 明确声浪目标与听感样例 | 高 | 待开始 | 场景表：idle/加速/巡航/减速/overspeed | 需要 Jovi 决策目标风格 |
| AUD-02 | 增加 acceleration / dynamics 设计 | 高 | 待设计 | 速度差分、滤波、边界定义 | 当前 `VehicleState` 无 acceleration |
| AUD-03 | MATLAB 或等价仿真建模 | 高 | 待开始 | 曲线、参数、波形、听感记录 | 未建模前不能宣称完成差异化声浪 |
| AUD-04 | 多层音色模型固件接口 | 高 | 待设计 | base/harmonic/load/noise 或 pulse layer 定义 | 要控制 CPU 和内存 |
| AUD-05 | 音频单元/编译测试 | 中 | 待新增 | 边界输入测试、overspeed mute 测试 | 先测试后实现 |
| AUD-06 | I2S bench listening test | 高 | 待开始 | 真实输出听感或录音 | 需要音频硬件 |
| AUD-07 | SD 声浪包/参数包策略 | 中 | 待设计 | 是否支持 SD 参数或波表，格式冻结 | 不建议早于算法定型 |

## 5. CAN 与车辆状态

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| CAN-01 | 确认最终 Tesla CAN ID/DBC 来源 | 高 | 待确认 | PRD/OpenSpec/代码三者一致 | 历史记录中出现过 ID 差异 |
| CAN-02 | CAN 实机或回放输入验收 | 高 | 待开始 | `0x256`/`0x116` 输入后状态变化正确 | 需要车端、CAN log 或模拟器 |
| CAN-03 | CAN timeout / invalid state 策略 | 中 | 待完善 | 信号丢失后状态衰减或 fallback 明确 | 防止音频状态卡死 |
| CAN-04 | OBD-II PID fallback 评估 | 中 | 待决策 | 是否纳入 S8/S9 范围 | 最初设计提过多数据源适配 |

## 6. BLE / 配置 / 诊断

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| BLE-01 | 完整 `ffe1..ffee` 行为矩阵 | 中 | 部分已实现 | 每个特征读写/notify 行为表 | 便于小程序/工具对接 |
| BLE-02 | BLE payload 边界测试 | 中 | 待补强 | oversize/invalid JSON 不崩溃 | 包括 `ffe8` |
| BLE-03 | `ffe5` diagnostics 字段冻结 | 中 | baseline 已有 | 字段名、单位、错误码文档化 | 避免客户端漂移 |
| BLE-04 | 配置保存时机和错误回报 | 中 | 待实机 | SD 失败时 BLE/LED 有状态 | 防止静默失败 |

## 7. USB CDC / 高级调参

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| CDC-01 | USB CDC 是否进入本期范围 | 中 | 待决策 | S7 完成后决策记录 | 不建议早于 OTA 验收 |
| CDC-02 | 命令 schema 冻结 | 中 | 待设计 | `GET_STATUS`, `GET_CONFIG`, `SET_CONFIG` 等 | 先只读后写入 |
| CDC-03 | Host 读状态工具 | 低 | 待开始 | Windows 下串口读状态稳定 | 可作为调参工具基础 |
| CDC-04 | 调参参数读写保存 | 中 | 待开始 | 参数可 set/read/save/reboot persistence | 与声浪模型参数绑定 |

## 8. 文档与交付

| ID | 待完成项 | 优先级 | 当前状态 | 验收证据 | 阻塞/备注 |
|---|---|---|---|---|---|
| DOC-01 | 更新 `PLAN.md` 阶段状态 | 中 | 需要持续维护 | 每次阶段完成后同步 | 防止 README/PLAN/PRD 漂移 |
| DOC-02 | 更新 OpenSpec main specs | 高 | 需要持续维护 | `openspec validate --all --strict --json` 通过 | 每次行为变更必须同步 |
| DOC-03 | 编写硬件验收记录 | 高 | 待开始 | `docs/06-TST-测试` 中有实测记录 | 不能用推测替代证据 |
| DOC-04 | 编写最终交付报告 | 中 | 待开始 | build/size/hardware/release 全部记录 | S10 输出 |
| DOC-05 | GitHub README 保持当前真相 | 中 | 已改善，需维护 | README 不夸大完成度 | 尤其声浪算法边界 |

## 9. 当前推荐执行顺序

1. `P0-01` 到 `P0-10`: 先做硬件 bring-up 和最小功能实机证明。
2. `S7-01` 到 `S7-07`: 关闭 BLE/WiFi/OTA 硬件验收。
3. `MEM-01` 到 `MEM-04`: 处理 IRAM release gate。
4. `AUD-01` 到 `AUD-06`: 单开声浪算法建模和固件集成。
5. `CDC-01` 到 `CDC-04`: 再做 USB CDC 和高级调参。
6. `DOC-01` 到 `DOC-05`: 每个阶段结束同步文档，不集中拖到最后。

## 10. 完成定义

可以认为“达到最初设计需求”的最低条件：

- P0 硬件 bring-up 全部有实机证据。
- S7 OTA 成功和失败路径都有证据。
- IRAM 风险被解决或正式接受。
- 声浪算法不再只是 RPM 单正弦，而是有速度/加速度/负载差异化模型和 bench 验证。
- BLE/SD/USB 或工具链能完成基础配置、读回和诊断。
- README、PLAN、OpenSpec、测试记录和交付报告与代码一致。
