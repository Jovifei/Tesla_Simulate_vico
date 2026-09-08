# Stage AG-R1 Reference Remediation（2026-09-08）

状态：`IMPLEMENTED / REMOTE_FOCUSED_GREEN / WAITING_FOR_LOCAL_REFERENCE_RECHECK`

## 1. 为什么需要 R1

Stage AG v1 首次使用 Jovi 本机已有 24/24 Reference 进行真实门禁时，正确地停止在 3 个 >3% 回退场景：

| Vehicle / scene | Legacy | identity_v1 | relative change |
| --- | ---: | ---: | ---: |
| Ferrari 458 / hot_idle | 3.1459652061 | 3.2756765802 | +4.1231% |
| Lexus LFA / hot_idle | 2.4876268301 | 2.5627502190 | +3.0199% |
| Nissan GT-R R35 / full_pull | 0.5184745602 | 0.5365567371 | +3.4876% |

v1 的 mean matched-state pairwise separation 从 `0.6494165905` 增至 `0.6593646857`（delta `+0.0099480951`）。因此 v1 的方向并非完全无效：它确实让车型更分离；问题是部分真实 Reference 场景变差，不能推广。

## 2. 代码根因

v1 先通过 throttle/RPM envelope 衰减 identity source，但之后又把每条 identity layer 单独归一化到 `0.94` peak。该 per-track peak recovery 会重新抬高怠速/低负荷 identity source。

同时 v1 的 RPM state 使用 `rpm / max(rpm_of_current_track)`。恒定怠速轨迹的 `rpm_norm` 因而等于 1，而不是相对于车型 redline 的低 RPM 状态。

这两个行为一起解释了 Ferrari/LFA `hot_idle` 回退，也违反了“车型身份强度应随实际状态变化”的设计意图。

GT-R 的问题不同：full-pull 时 base renderer 已经包含 turbo/BOV identity，额外的 E3/E6/E9 + broadband source 在满负荷下仍以完整 v1 mix 叠加，导致 Reference 距离回退。

## 3. R1 修正策略

v1 保留不改，作为负证据。新增：

```text
vehicle_identity_v1r1
```

R1 不放宽 3% Reference guard，不做自动 fit。

### 3.1 绝对状态幅度

- RPM 使用 `rpm / vehicle_redline`；
- throttle/RPM envelope 保留；
- **取消 identity layer 的 per-track peak normalization**；
- 仅保留 `[-0.94, +0.94]` 的硬数值安全 clip，clip 不会主动放大低能量 scene。

### 3.2 GT-R 满负荷 selective attenuation

GT-R 从 throttle=0.75 开始平滑降低“新增 R1 identity source”的 sample-wise blend，在 WOT 时 blend scale=`0.68`。

原 identity mix=`0.16`，所以满负荷有效上限约：

```text
0.16 * 0.68 = 0.1088
```

中负荷不衰减，保留车型分离能力；已有 base turbo/BOV 路径不修改。

### 3.3 Hellcat anchor

Hellcat `identity_mix=0`，R1 仍必须 legacy/R1 逐 PCM byte-identical。

## 4. 新增实现

- `stage_ag/vehicle_identity_r1.py`
- `stage_ag/render_identity_probe_r1.py`
- `stage_ag/analyze_vehicle_identity_r1.py`
- `stage_ag/build_identity_dashboards_r1.py`
- `stage_ag/run_local_identity_validation_r1.py`
- `tests/test_s12_stage_ag_r1_reference_remediation.py`
- `.github/workflows/s12-stage-ag-r1-reference-remediation.yml`

R1 runner 增加两个不可绕过的前置 gate：

1. governed Reference >3% regression count 必须为 0；
2. mean matched-state cross-vehicle separation 不得低于 legacy。

两个条件同时通过，才生成 immutable legacy/R1 package 和 sealed blind package。

## 5. Exact-head focused CI

在提交 `332dc96ca747bf001e2df14c23e08a5227cf8b1c` 上：

- Stage AG-R1 focused：`8 passed`
- preserve Stage AG v1 + AF-R focused：`37 passed`
- `compileall`：PASS
- `git diff --check`：PASS
- workflow run：`34188298846`，`success`

完整 Stage AF / Stage Y exact-head 工作流仍以 GitHub 现场状态为准，不允许用旧 SHA 的 green run 冒充。

## 6. 下一步

本地只需要复用**同一批** IR / Reference 和旧 v1 scorecard，运行：

```text
stage_ag.run_local_identity_validation_r1
```

如果 R1 仍有 >3% Reference 回退：停止并把 R1 scorecard 返回，不放宽阈值。

如果 Reference 全绿但 separation 低于 legacy：同样停止，说明修得过保守。

只有两个 gate 都通过，才生成 R1 immutable package 和盲听包，随后等待 Jovi。
