# 项目总待办 / Master Backlog

更新：2026-09-05

## P0 Remote/Governance

- PR #6 current docs merge/qualification；
- PR #7 Stage AD exact-head CI/merge；
- AC8 post-merge pre-human receipt。

## P1 Stage AD local acoustic loop

- locate/verify governed Hellcat Reference；
- body closed loop；
- blower closed loop；
- afterfire loop where reference is valid；
- hard-gate review；
- monitor audition package；
- Jovi feedback。

Public extractor output = optional R3 human A/B only, not default optimizer input。

## P2 Hellcat closure

Human decision → accept candidate 或最多一轮/三个 source-causal finalists → Hellcat Engineering Profile。

## P3 Vehicle migration

Ferrari 458、RX-7 FD、multi-vehicle profile schema。

## P4 App state/product contracts

speed/acceleration conditioning、Virtual RPM/load/gear/shift/lift/overrun、AudioParameterPackage、Golden traces/PCM。

## P5 Product runtime

portable C++、Python↔C++ equivalence、Android NDK + Oboe/AAudio、vehicle selector、latency/xrun/CPU/memory/thermal/lifecycle、in-car validation。

## P6 Formal reference

R1 legal synchronized acquisition/calibration。

## Deferred

ESP32 board/BLE/WiFi/OTA/CAN-analyser/I2S external hardware chain，以及 CAN-only product dependence。

## 2026年10月4日 App 当前窄任务状态

完整根因与失败记录见[输入与循环点击经验](../07-debugging/03-vico-input-and-loop-click-lessons-20261004.md)。

- 已发布/静态安装验证：7bf34080输入质量、固定方向合同、bounded自动日志及导出；不是道路/声音通过。
- 已提交：SESSION_START最小缺口修复 3e76f0d；精确CI与设备复验单独跟踪，不能把已建tree当提交。
- 受控候选：C63低RPM四loop接缝，必须保旧reference并通过新旧层边界/同窗/事件/峰预算；全域方案的高转回退保留为负证据。
- 未解决：Supra固定gain峰预算、高转源共振与混音相消、虚拟需求/巡航、其他车型同级验收、道路与人耳。
- 每次source批次同步经验、证据identity和本入口，不因纯测试全绿提升项目里程碑或声音完成度。
