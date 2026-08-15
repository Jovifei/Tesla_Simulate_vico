# S12 八车型 Round-2 完成与项目状态落地

## 目标

在不修改公共低频层、Frozen PTR、响度管理、Track-P、MATLAB/Simulink、Runtime/Android 的前提下，关闭 LFA ASG 事件资格误判，并把已在 Hellcat、C63、GT-R、LFA 验证的证据方法迁移到 Ferrari 458、RX-7 FD、Supra JZA80 与 Aventador LP700。

所有新输出继续标记为 `synthetic / uncalibrated / vehicle-inspired / not OEM reproduction`，自动或包完整性通过不构成 Human PASS、Approved Profile 或产品化证明。不得读取 CSV。

## 执行顺序

1. **LFA 资格修复**：从连续 `metallic` 载波改为实际 `lfa_shift_exhaust_reengagement` array；事件只按 trace 中真实 ASG RPM drop/recovery 与开节气门对齐资格化。既有 afterfire 继续使用热历史 + 闭节气门规则。
2. **四车独立 source/metrics**：Ferrari/RX-7 复用 Stage-G v4 baseline；Supra/Aventador 复用当前八车 Stage-C baseline。每车使用独立物理结构、参数网格、trace-derived acceleration/lift/shift 窗口和 named event，不复制 HEMI、双螺杆、C63 bark 或 LFA ASG。
3. **会计与冻结**：0–8 s baseline byte-identical；pressure 必须等于实际 primitive contributor 单次求和；明确排除诊断 aggregate/alias；指标只读 arrays/trace，不信任 diagnostics 声明。
4. **统一最终链**：八车的正式对比使用 `Frozen PTR → edge fade → one fixed whole-cycle gain → PCM24`；Comfort 只可由候选最终 PCM 追加一次受头间隙限制的静态增益。
5. **不覆盖交付**：生成一个新的八车 Round-2 diagnostic package，绑定 vehicle/profile/trace/source/final-PCM SHA、PCM24 health、SHA256SUMS 与 ZIP CRC。任何硬门未过时保持 `PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY`。
6. **验证与知识库**：运行车型 focused、Stage G/K 兼容、八车 isolation、Track-P guard、冻结 SHA、包重开验证；将真实仓库 tip、包、测试和未完成门同步到 Obsidian，替换旧占位符，保留未批准/未产品化边界。

## 完成判据

- LFA actual ASG event count 与 trace shift count 一致，wrong-condition 为 0；afterfire 资格不退化。
- Ferrari、RX-7、Supra、Aventador 都具备 actual arrays、trace event windows、pressure accounting、final PCM 和可信包收据。
- 八车未出现跨车型 stem/参数泄漏；七车/公共层/Track-P 冻结门按变更意图保持。
- 新包全部 WAV 为 48 kHz/stereo/PCM24/finite/0 clipping/peak ≤ -1.5 dBFS，manifest/SHA/ZIP 全部可重算。
- Obsidian 明确记录当前已完成、仍失败/不可用的门，以及下一步只剩的人耳/真实参考/产品化工作。
