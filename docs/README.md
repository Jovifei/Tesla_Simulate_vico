# Tesla Simulate Vico 文档入口

本目录用于记录 `Tesla Simulate Vico` 的需求、架构、协议、计划、执行、测试、调试、报告、待完成事项和学习资料。

当前重点入口：

- [整体阶段计划](04-PLN-计划/01-PLN-固件完成路线图.md)
- [固件待完成清单](09-TOD-待完成/01-TOD-固件待完成清单.md)
- [文档编写指南](GUIDE.md)
- [系统架构](01-ARC-架构/02-ARC-系统架构.md)

## 当前项目状态

- 已完成：ESP-IDF baseline、CAN listen-only、基础 CAN parser、I2S RPM baseline、BLE GATT、SD JSON、编码器、油门电位器、WS2812、OTA baseline 代码骨架。
- 待证明：实机 boot、BLE 广播/读写、WiFi join、HTTPS OTA 成功/失败路径、I2S 真实输出、SD/ADC/LED/编码器硬件行为。
- 待实现：速度/加速度/负载差异化声浪算法、MATLAB 或等价仿真定参、USB CDC/高级调参、最终交付报告。
- 风险项：IRAM 最新记录仍接近上限，不能把当前 `1` byte margin 当作已解决。

## 文档目录说明

| 目录 | 用途 | 当前建议 |
|---|---|---|
| `00-REF-参考` | 芯片手册、参考工程、外部资料 | 放原始资料和链接，不写结论 |
| `01-ARC-架构` | 系统架构、模块关系 | 后续需同步当前 ESP-IDF 实现，替换旧 Arduino/MQTT 口径 |
| `02-REQ-需求` | 产品需求、验收标准 | 建议补一份当前 PRD 摘要 |
| `03-COM-协议` | BLE/CAN/USB/OTA 协议 | 建议补 BLE `ffe1..ffee` 行为矩阵 |
| `04-PLN-计划` | 总体路线、阶段规划 | 当前重点看 `01-PLN-固件完成路线图.md` |
| `05-WORK-执行` | 执行步骤、移植记录 | 后续记录烧录、OTA server、调参流程 |
| `06-TST-测试` | 测试计划、测试报告 | 下一步优先补硬件验收记录 |
| `07-DBG-调试` | 问题排查、bug 分析 | 记录上板问题、WiFi/OTA/BLE crash |
| `08-RPT-报告` | 开发记录、阶段报告 | S10 输出最终交付报告 |
| `09-TOD-待完成` | 待完成事项、技术债 | 当前重点看 `01-TOD-固件待完成清单.md` |
| `10-STUD-学习` | 学习资料和调研过程 | 可放 MATLAB/声浪建模学习记录 |

## 下一步最短路径

1. 按 `09-TOD-待完成/01-TOD-固件待完成清单.md` 先完成 P0 硬件 bring-up。
2. 关闭 S7 BLE/WiFi/OTA 实机验收。
3. 处理 IRAM release gate。
4. 单开声浪算法建模和固件集成阶段。
5. 每完成一个阶段，同步 `PLAN.md`、OpenSpec、测试记录和本目录索引。
