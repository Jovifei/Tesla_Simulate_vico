# Dimension failure diagnosis and isolated repair contract

Date: 2026-10-31

## Confirmed failure chain

The reported models are different saved artifacts and must not share one receipt:

- `...104325_161`: `Hellcat Synthetic Source` emits `[960x9]`. `Combustion_Selector` was configured with two-dimensional selector options although the incoming signal was treated by Simulink as one-dimensional. R2026a rejects `IndexOptions` before the model can compile.
- `...112408_106`: `Mechanical_Receiver` is reported as `[960x3]`. `Post_Frozen_Mechanical_Sum` cannot add that to the Frozen branch, which must be one `[960x1]` signal.
- `...112747_734`: later artifact. Its receipt records some explicit output dimensions, but its compiled Sum input still shows the Frozen branch as `[960x2]` and the receiver as `[960x1]`; this is a remaining hidden mismatch, not a clean proof.

## Required isolated contract

```text
source              [960x9]
combustion split    [960x2]
other split         [960x2]
control split       [960x5]
path bus            [960x2]  (pre_frozen, mechanical_input)
pre_frozen          [960x1]
mechanical receiver [960x1]
Frozen output       [960x1]
post-Frozen Sum     [960x1]
renderer Mux        [960x2]
```

The repair removes the ambiguous Selector configuration and uses explicitly dimensioned MATLAB Function blocks. Every multidimensional MATLAB Function block must have `Output1D='off'` and an explicit `OutputDimensions`; the Frozen output must be normalized at the isolated boundary to one column before the Sum. No change is made to the Frozen implementation.

## Verification gates

1. Static contract checks reject Selector index configuration and any `[960x3]` mechanical output.
2. Saved isolated model is reopened and audited for expressions, connections, and compiled dimensions.
3. Update, active compile, `model_check`, and one short native-input simulation pass.
4. Only after these gates may the approved preflight resume. No 90-second run or `MD-cold` claim is allowed from this repair alone.

MATLAB independent startup remains a separate unresolved native crash in `mwhomesessionmanager_impl.dll` / `mwrecent_artifacts_service_impl.dll`; the current Desktop/MCP session is not cold-start evidence.

## 2026-10-31 维度合同修复与 R2026a 启动审计

### 维度问题

- S12_hellcat_cabin_event_bank_20261031_104325_161 的 Combustion_Selector 把 [960x9] 源包按二维 Selector 参数配置，但 R2026a 将输入解释为一维，真实失败日志为 IndexOptions/IndexParamArray 维度不匹配。
- S12_hellcat_cabin_event_bank_20261031_112408_106 的 Mechanical_Receiver 输出 [960x3]，与 Post_Frozen_Mechanical_Sum 的 Frozen 输入不兼容。较晚的 112747_734 receipt 不能覆盖这两个旧模型的失败。
- 后续核对又发现 112747_734 的保存模型仍存在 runner 临时覆盖问题：默认 receiver 表达式与真实输入合同不一致，且 Frozen 输出是 960 元素一维向量，不能直接当作 [960x1] 与机械支路求和。

### 隔离修复

在授权隔离目录新增 mb_column_frame.m 和 epair_cabin_dimension_candidate.m，不改原模型、Frozen、公共 common、声库或 Android。新候选 isolated/S12_hellcat_cabin_event_bank_dimfix_20261031_154809_713.slx 使用显式 MATLAB Function 分流并在 Frozen 边界归一化为单列。

实际 R2026a Desktop/MCP 证据：

- Source [960x9]
- Combustion/Other/Control [960x2] / [960x2] / [960x5]
- Path bus [960x2]
- Pre-Frozen [960x1]
- Mechanical Receiver [960x1]
- Frozen boundary normalizer [960x1]
- Post-Frozen Sum inputs [960x1] + [960x1], output [960x1]
- model_check: healthy
- 5 帧 native B 短仿真：PASS
- Receipt: esearch-iteration3/dimension-fix-receipt-20261031_154809_713.json

本次一次路径字符串接线失败也保留为失败证据；改用端口句柄后重新生成唯一候选并通过验证。未运行 90 秒长轨、35 锚点或 MD-cold。

### MATLAB 独立启动

只读审计仍将故障定位在 mwhomesessionmanager_impl.dll / mwrecent_artifacts_service_impl.dll / threadpool 访问冲突；独立 pref/TEMP、-nojvm、空 startup、MW_ARTIFACTS_WS_ENABLED=0、Python Engine Desktop 均未证明修复。Home 数据库完整性检查为 ok，但不等于运行时访问安全。当前 Desktop/MCP 会话可用于同会话短探针，不替代新 PID、30 秒存活、短 Simulink、自然退出的冷启动证据。MD-cold 继续 BLOCKED_STARTUP。
