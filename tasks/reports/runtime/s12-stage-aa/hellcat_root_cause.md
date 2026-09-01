# S12 Stage AA Hellcat 根因报告

- main head: `209378bcb9a0c1a352ffd56ca1c765ecce01f81d`
- status: `DIAGNOSTIC_ONLY`
- parameter changes applied: `false`

| Finding | Severity | Hypothesis | Next bounded test |
| --- | --- | --- | --- |
| `low_frequency_body` | HIGH | absolute event pressure baseline dominates the source; DC/dP removes most of the body before PTR | event-derived AC pressure/body repair; do not add a master gain |
| `pressure_120_400` | HIGH | the desired pressure attack exists in the source but is attenuated by the pressure chain rather than created by post-EQ | bounded source/event pressure propagation with 120–400 Hz and click guards |
| `blower_tonal_artifact` | MEDIUM | forced-induction/high-band content becomes disproportionately dominant after the pressure/PTR stages | reduce carrier dominance only through load-linked sideband/broadband hypotheses; no fixed-tone filler |
| `dynamic_range` | HIGH | raw dynamic contrast is lost by pressure/PTR attenuation and is not a monitor-only issue | compare idle-to-WOT raw contract before/after every candidate |
| `afterfire_naturalness` | MEDIUM | afterfire scheduling is present, but its audible naturalness cannot be inferred from event count alone | preserve eligibility/latch and assess afterfire tail in the dynamic candidate package |

## 结论

Energy ledger 将问题定位为压力绝对基线主导：dP/DC 去掉大部分 body，随后 frozen PTR 继续施加固定衰减。候选只能在 event/pressure propagation、局部 source-layer balance、transient 或明确 monitor contract 内验证；不得用 master gain 恢复数字 RMS。

Reference 仍为 R2/R3 diagnostic，未提供同步 RPM/state 的 R1；因此任何方向判断都保持诊断性，不能生成 OEM、Profile Freeze 或 Human PASS。
