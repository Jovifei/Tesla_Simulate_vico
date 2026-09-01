# S12 Stage AA Hellcat 有界候选复核

- main head: `209378bcb9a0c1a352ffd56ca1c765ecce01f81d`
- status: `DIAGNOSTIC_ONLY`
- 候选数量：4（AA-C0…AA-C3）

| Candidate | Hard gates | Pareto | Diagnostic preference |
| --- | --- | --- | --- |
| `AA-C0` | `True` | `True` | `False` |
| `AA-C1` | `True` | `True` | `False` |
| `AA-C2` | `True` | `True` | `False` |
| `AA-C3` | `True` | `True` | `True` |

## 解释

AA-C1 只使用负载相关的 pressure-AC 局部缩放；AA-C2 在其上加入 event-derived 120–400 Hz body；AA-C3 仅抑制 forced-induction 的高频 carrier。三者都不修改 master gain、PTR、Radiation 或 Track-P。

`diagnostic_preference` 只是进入 v3 试听的工程候选，不是人耳验收或 Profile Freeze 决策；所有软指标仍受 R1 缺失限制。
