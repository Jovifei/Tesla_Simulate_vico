# Tesla Simulate Vico 文档入口

本目录用于沉淀 `Tesla Simulate Vico` 的参考资料、架构、需求、协议、计划、执行记录、测试记录、调试记录、报告、待完成清单和学习资料。

## 当前主入口

- [固件完成路线图](04-PLN-计划/01-PLN-固件完成路线图.md)
- [固件待完成清单](09-TOD-待完成/01-TOD-固件待完成清单.md)
- [文档编写指南](GUIDE.md)
- [系统架构](01-ARC-架构/02-ARC-系统架构.md)

## 当前项目状态

- 已实现：ESP-IDF baseline、CAN listen-only、基础 CAN parser、I2S RPM baseline、BLE GATT、SD JSON、encoder、throttle potentiometer、WS2812、S7 status/network/iot/ota 分层代码。
- 待证明：实机 boot、BLE 广播/连接/读写、WiFi join、MQTT 上下行、HTTPS OTA 成功/失败路径、I2S 真实输出、SD/ADC/LED/encoder 硬件行为。
- 待实现：速度/加速度/负载差异化声浪算法、MATLAB 或等价仿真定参、USB CDC/高级调参、最终交付报告。
- 风险项：IRAM 历史记录接近上限，不能把 `1` byte margin 当作已解决。

## 目录说明

| 目录 | 用途 | 当前建议 |
|---|---|---|
| `00-REF-参考` | 芯片手册、参考工程、外部资料 | 放原始资料和链接，不写最终结论 |
| `01-ARC-架构` | 系统架构、模块关系 | 后续需要继续同步当前 ESP-IDF 分层实现 |
| `02-REQ-需求` | 产品需求、验收标准 | 与 PRD 保持一致 |
| `03-COM-协议` | BLE/CAN/USB/OTA 协议 | 优先维护 BLE `ffe1..ffee` 行为矩阵 |
| `04-PLN-计划` | 总体路线、阶段规划 | 当前重点看固件完成路线图 |
| `05-WORK-执行` | 执行步骤、迁移记录 | 记录烧录、OTA server、调参流程 |
| `06-TST-测试` | 测试计划、测试报告 | 下一步补硬件验收记录 |
| `07-DBG-调试` | 问题排查、bug 分析 | 记录上板问题、WiFi/OTA/BLE crash |
| `08-RPT-报告` | 开发记录、阶段报告 | S10 输出最终交付报告 |
| `09-TOD-待完成` | 待完成事项、技术债 | 当前重点看固件待完成清单 |
| `10-STUD-学习` | 学习资料和调研过程 | 可放 MATLAB/声浪建模学习记录 |

## 下一步最短路径

1. 关闭 S7 代码门禁：`build`、`size`、`size-components`、OpenSpec。
2. 做 ESP32-S3 硬件 bring-up：flash、monitor、boot log、BLE 广播。
3. 完成 BLE/WiFi/MQTT/OTA 实机验收。
4. 处理 IRAM release gate，或在压力测试通过后形成明确风险接受记录。
5. 单独启动声浪算法建模与固件集成阶段。
