# S12 Stage I Hellcat Whine Voicing Report

## 1. 结论

Stage I 已完成 Hellcat 增压器音色的实现、参数活动验证、三种诊断取向渲染、最终 PCM 资格计算和未合格诊断包发布。独立审查后的当前状态严格只有：

```text
UNQUALIFIED_DIAGNOSTIC_ONLY
PARTIAL / AUTOMATED_GATE_FAIL
```

当前包可以供 Jovi 做具名诊断试听，但它没有进入正式人耳门。A/B/C 三个候选均未通过正式自动硬门，因此没有自动选中候选，也没有生成 Profile Freeze Candidate；Jovi 对该包的意见属于工程诊断反馈，不构成正式人耳门结果。

所有声音继续属于：

```text
synthetic
uncalibrated
Hellcat-inspired
not OEM reproduction
```

## 2. 执行边界

- Branch：`agent/s12-stage-i-hellcat-whine-voicing`
- Base commit：`6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2`
- 工作树：`E:\Tesla_speed\worktrees\s12-stage-i-hellcat-whine-voicing`
- Track-S 离线声学路径内实施；FVM、PTR core、Radiation、Runtime、Android、MATLAB、Simulink 均未进入本阶段。
- Stage G 匿名第 2/第 3 条反馈仍为 `UNBOUND_STAGE_G_PAIR_FEEDBACK`；sealed key 未读取。
- Ferrari 458 与 RX-7 FD 使用 Stage H 冻结 WAV 原字节，SHA 分别为 `7f50e75e...e11d80` 与 `0f4680c3...b0bce8`。

## 3. 已完成能力

Stage I 在 Stage H 基础上增加了可验证的 Hellcat 专属音色结构：

```text
2.36-order shaft family
→ 11.8 / 23.6-order cluster
→ deterministic phase ripple and sidebands
→ intake / casing voicing
→ RPM / load / boost envelope
→ boost-history bypass release
→ named Track-S stems
→ common Pre-PTR EQ
→ Frozen PTR
→ edge fade
→ one fixed whole-cycle gain
→ PCM24
```

关键工程闭环：

- 参数使用诊断从“读取过”升级为 `requested/read/configured/consumed/active/inactive/unused`；r6 生产证据中三个 Stage I 候选均为 19 requested/read/configured/consumed、18 active、1 inactive、0 unused。唯一 inactive 是 neutral `afterfire.gain_scale`，不得把 neutral 配置伪报成 active。
- Stage H legacy 基线保留 14/14 requested/read/configured/consumed，但明确标记 `NOT_AVAILABLE_LEGACY_STAGE_H`，不伪造 active 证据。
- boost 与 lift response probe 绑定 candidate/profile/trace/render/stem SHA。
- 60 秒全工况采用顺序渲染与释放，不要求 Stage H+A/B/C 全部 SourceRender 同时驻留。
- 四条 blower-only 工程 stem 使用共同 attenuation-only 响度目标，保留候选间真实存在感差异。
- 正式具名包内含四个 60 秒 Hellcat、7 个工程诊断 WAV、Ferrari/RX-7 冻结锚点、四张分析图、metrics JSON、反馈表、manifest 与 SHA。

## 4. 三种诊断取向

| 取向 | 目的 | Final PCM SHA-256 | 自动资格 | 参考距离平均改善 |
|---|---|---|---|---:|
| I6-A Balanced | 平衡 V8 重量与 whine | `f65a2209...02c49` | FAIL | -17.5046% |
| I6-B Whine Forward | 提高增压器存在感 | `baab435e...ee4f` | FAIL | -13.5205% |
| I6-C Softer Mechanical | 更柔和、机械化的上部音色 | `36fafbc4...7c953` | FAIL | -18.9879% |

三种取向只是用于 Jovi 具名比较的诊断候选，不是“三个合格候选”。正式 `all_pass` 对 A/B/C 均为 `false`，因此 `selected_candidate = null`、`profile_freeze_permitted = false`。

## 5. 自动指标

### 5.1 最终 PCM 参考距离

参考比较域为 final PCM，eligible states 为 idle、acceleration、afterfire。30% 改善门保持不变。

| 取向 | idle | acceleration | afterfire | 平均 |
|---|---:|---:|---:|---:|
| A | -34.8970% | -17.4766% | -0.1402% | -17.5046% |
| B | -34.8572% | -5.6112% | -0.0930% | -13.5205% |
| C | -34.8813% | -21.8844% | -0.1980% | -18.9879% |

所有 required states 均可用，但三种候选都没有达到平均改善 `>=30%`，并且均存在超过 10% 的单状态恶化。自动状态因此为 `PARTIAL / AUTOMATED_GATE_FAIL`。

### 5.2 Hellcat 专属指标摘要

- Blower/load correlation：A `0.9566`，B `0.9560`，C `0.9629`，均通过相关性门。
- Shaft/lobe order error 均在小误差范围内，阶次追踪健康。
- A/B/C 的 acceleration blower/exhaust 分别为 `-2.2366 / -0.7411 / -2.2780 dB`，未达到相对 Stage H 的正式增量门。
- Sideband/main 分别为 `0.2733 / 0.2504 / 0.4595`，均未通过正式范围门。
- Response probe 的 attack、release、bypass decay 均未同时通过硬门。
- 三个最终 PCM 均为 48 kHz、stereo、PCM24、finite、clipping=0、peak 不高于 -1.5 dBFS。

这些指标证明实现可运行、阶次随状态移动且候选彼此不同；它们不证明 Jovi 会将任一候选听成真实 Hellcat。

## 6. 最终 fresh 测试证据

- 当前树 Stage I focused：`108 passed`，耗时 `56.34 s`。
- 当前树 regression isolation：`3 passed`。
- 当前树完整 S12：`596 passed / 232 subtests`，耗时 `740.41 s`。
- 当前树 Track-P guard script：PASS，核对 `180 files / 2 symbols`。
- Track-P guard pytest：`21/21 passed`，耗时 `1.23 s`。
- P1 审查前的 `583 passed / 232 subtests` 只保留为审查过程历史，不代表最终当前树。
- sealed key：未读取
- Profile Freeze：未执行

## 7. 当前未合格诊断包

- 根目录：`E:\Tesla_speed\review_packages\s12-stage-i-hellcat-whine-voicing-v1-unqualified-diagnostic`
- Package ID：`S12_Stage_I_Unqualified_Diagnostic_v1`
- Status：`UNQUALIFIED_DIAGNOSTIC_ONLY / PARTIAL / AUTOMATED_GATE_FAIL`
- ZIP：`S12_Stage_I_Unqualified_Diagnostic.zip`
- ZIP SHA-256：`98fcdc21d5208b7a43c1522a08ba063ee855023c134203e1389587dc23e507bc`
- 文件：27 个，共 223.35 MiB；`SHA256SUMS.txt` 为 26/26 条目。
- Source evidence：r6；manifest SHA-256 `0fce37d83da5e750a6897941d87031ff1ad5b0c82bd5e72d7a01b6d43d6441ea`。
- Reference canonical SHA-256：`43f93d2ded66a6df06240266db9a59d18b6ff49c89173d4aecc852aff601b623`，与 qualification 内嵌 reference summary 一致。

旧 `f6997bab...45f5d7` 包已可恢复地移动到 `E:\Tesla_speed\review_packages\_invalid_s12-stage-i-hellcat-whine-voicing-v1_pre-p1-review`。它属于 `HISTORICAL / INVALID_PRE_P1_REVIEW`，缺少审查后要求的完整资格绑定，不能再作为当前交付物。

工程 stem 只用于定位 blower、exhaust、shift 与 lift 行为，不是产品音频。公开 builder 对最终试听 WAV 自身执行 PCM 和 peak 健康检查，不能把上游健康声明当成包级证据。

## 8. 人耳状态与下一步

当前没有 Stage I 正式人耳反馈，因此没有 Hellcat likeness、whine presence、naturalness、harshness 或 artifact freedom 的正式人耳评分。自动门未解锁，不能生成正式候选选择，更不能宣称 Human PASS。

Jovi 可以试听诊断包中的 Stage H、A、B、C 60 秒文件与 blower-only/shift/lift 片段并给出显式 `file_id` 反馈，用来定位下一轮工程修改；该反馈不是已解锁的人耳验收。必须先产生通过正式自动资格的候选，才允许重新发布 `WAITING_FOR_JOVI...` 的正式人耳包并进入人耳门。
