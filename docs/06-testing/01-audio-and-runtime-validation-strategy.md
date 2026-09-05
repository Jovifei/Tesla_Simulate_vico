# 声音算法与产品 Runtime 验证策略

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

## L0 Static
compileall、JSON/schema、license/source registry、git diff check。

## L1 Software unit/regression
persistent state、event/source/path、snapshot/restore、parameter domain/reachability、ReferenceCaseSet、closed-loop controller、determinism。

## L2 PCM hard gates
finite、no clipping、block-boundary click/pop、wrong-condition afterfire=0、raw/monitor separation、Track-P frozen guard。

## L3 Reference engineering evidence
比较 raw dynamic、loudness-matched timbre、scene metrics、fixed absolute reference distance。跨轮收敛用 fixed ruler；changing-parent improvement 只作诊断。

R3 public extract 不得作为默认自动 optimizer target。

## L4 Human
Jovi 判断 vehicle identity、realism、idle life、LF pressure、mechanical texture、blower、acceleration、shift/lift、afterfire、synthetic artifact。Human result 独立记录。

## L5 Simulink mirror
结构/端口/尺寸 → Update Diagram → simulation → finite 960x2 PCM → Python equivalence。没全通过就 `NOT_READY`。

## L6 Portable C++
Golden state/PCM、block/stream/snapshot、event timing、bounded numeric diff、long-run continuity。

## L7 Android realtime
callback WCET/p95/p99、xrun、input→audio latency、CPU、heap、battery、thermal、pause/resume/audio focus、30/60/120min run、profile switch。

## L8 R1 formal calibration
只有 rights-cleared synchronized R1 才允许 Order-RPM/formal calibration/OEM-level claim。

## 核心原则

每个 report 必须写清楚“测试了哪一层”和“没有证明哪一层”。
