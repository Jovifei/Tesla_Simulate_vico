# Stage AG-R1 Reference Remediation（2026-09-08）

状态：`REFERENCE_GATES_GREEN / BLIND_ADAPTER_FIXED / WAITING_FOR_LOCAL_RESUME`

## 1. v1 Reference 门禁结果

Stage AG v1 使用 Jovi 本机已有 24/24 Reference 进行真实门禁时，正确地停止在 3 个 >3% 回退场景：

| Vehicle / scene | Legacy | identity_v1 | relative change |
| --- | ---: | ---: | ---: |
| Ferrari 458 / hot_idle | 3.1459652061 | 3.2756765802 | +4.1231% |
| Lexus LFA / hot_idle | 2.4876268301 | 2.5627502190 | +3.0199% |
| Nissan GT-R R35 / full_pull | 0.5184745602 | 0.5365567371 | +3.4876% |

v1 mean matched-state pairwise separation 从 `0.6494165905` 增至 `0.6593646857`（delta `+0.0099480951`）。所以 v1 确实增加车型分离，但部分真实 Reference 变差，不能推广。

## 2. v1 根因

v1 先通过 throttle/RPM envelope 衰减 identity source，但随后又把每条 identity layer 恢复到 `0.94` peak。该 per-track peak recovery 抵消了怠速/低负荷衰减。

同时 v1 使用 `rpm / max(rpm_of_current_track)`。恒定怠速轨迹因此得到 `rpm_norm=1`，而不是相对车型 redline 的低 RPM 状态。

GT-R 的 full-pull 问题来自另一侧：base renderer 已经包含 turbo/BOV identity，新加 E3/E6/E9 + broadband 在 WOT 仍以完整 v1 mix 叠加。

## 3. R1 修正

保留 `vehicle_identity_v1` 不改，作为负证据。新增：

```text
vehicle_identity_v1r1
```

R1 不放宽 3% Reference guard，不做自动 fit。

### 3.1 绝对状态幅度

- RPM 使用 `rpm / vehicle_redline`；
- throttle/RPM envelope 保留；
- 取消 identity layer 的 per-track peak normalization；
- 只保留 `[-0.94,+0.94]` 安全 clip；clip 不主动放大低能量 scene。

### 3.2 GT-R WOT selective attenuation

GT-R 从 throttle=0.75 开始降低新增 R1 identity blend，WOT scale=`0.68`。

原 identity mix=`0.16`，所以 WOT 有效上限约：

```text
0.16 * 0.68 = 0.1088
```

中负荷不衰减；已有 base turbo/BOV 不修改。

### 3.3 Hellcat anchor

Hellcat `identity_mix=0`，legacy/R1 必须逐 PCM byte-identical。

## 4. R1 真实本地复测结果

R1 使用与 v1 相同的 IR / 24 Reference 重新运行后：

```text
reference_regressions_gt_3pct = 0
separation_nonnegative = true
```

mean pairwise：

```text
legacy = 0.6494165905433259
R1     = 0.6541488359403442
delta  = +0.004732245397018331
```

三个原失败项：

```text
Ferrari hot_idle : +4.1231% -> +0.6631%
LFA hot_idle     : +3.0199% -> +0.4708%
GT-R full_pull   : +3.4876% -> +1.1753%
```

所以 R1 已同时通过：

1. 16 个 governed Reference row 的 3% guard；
2. matched-state separation 不低于 legacy。

已成功生成 immutable：

- legacy package；
- `vehicle_identity_v1r1` package。

## 5. blind adapter 阻塞与修复

首次 R1 本地运行在两个 immutable package 都已生成后，blind builder 抛出：

```text
ValueError: source package has unsupported identity mode
```

根因是旧 blind builder 只接受：

```text
legacy
vehicle_identity_v1
```

而 R1 package 合同正确使用：

```text
vehicle_identity_v1r1
```

该问题是 package adapter allow-list 漏项，不是声音算法或 Reference gate 失败。

远端修复：

1. blind builder 显式支持 `vehicle_identity_v1r1`；
2. private/public blind receipt 保留 `source_identity_mode`；
3. R1 runner 新增 `--resume-after-package`；
4. resume 不重新 probe、scorecard 或渲染 40 个 WAV；
5. resume 先重验 gate receipt、scorecard SHA、package manifest self-hash、Hellcat byte anchor、non-Hellcat change、Reference SHA equality；
6. 重验通过才创建 sealed blind package + final summary；
7. blind output、private mapping、final summary 均拒绝覆盖已存在目标。

## 6. Exact-head 自动验证

最终适配修复 HEAD：

```text
3b1546650d89a578b041e0f67007582c7d56f5b0
```

专用 workflow：

```text
S12 Stage AG-R1 Reference Remediation
run 34233498716
completed / success
```

实际结果：

```text
R1 focused                         11 passed
preserve Stage AG v1 + AF-R       37 passed
compileall                         PASS
git diff --check                   PASS
```

11 个 R1 测试已包括：

- blind builder 接受 R1 identity package；
- `resume-after-package` 从现有 gate-passed package pair 继续生成 blind + summary；
- R1 package adapter bind/restore；
- Hellcat byte-preserving；
- Ferrari/LFA idle amplitude 不再 peak-recover；
- GT-R WOT attenuation。

## 7. 当前本地恢复命令

不需要重跑 R1 probe/scorecard/package。

更新到最新远端 HEAD 后直接：

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ag.run_local_identity_validation_r1 `
  --output-root E:\Tesla_speed\review_packages `
  --mapping-root E:\Tesla_speed\review_packages_private `
  --run-id s12-stage-ag-r1-identity-20260908-v1 `
  --reference-root E:\Tesla_speed\review_packages `
  --resume-after-package
```

该命令只继续：

```text
validate existing gate/package pair
-> build sealed blind package
-> write stage_ag_r1_validation_summary.json
```

随后启动 23380–23383、23480–23483 与 23580 页面，等待 Jovi blind feedback。

仍禁止自动 fit、profile freeze、Android、ESP32、OEM/R1 claim、Human PASS 或 merge main。
