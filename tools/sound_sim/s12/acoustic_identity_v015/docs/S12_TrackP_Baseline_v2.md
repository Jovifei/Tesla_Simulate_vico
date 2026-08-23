# S12 Track-P Baseline v2

> 状态：**生效中**（取代 Baseline v1）
> 建立日期：2026-08-08
> 适用变更：S12 Stage B 收口 + Stage C Deep Realism
> 声明：本项目全部音频产物为 `synthetic; uncalibrated; not OEM reproduction`

---

## 1. 为什么需要 v2

Baseline v1 以 `301fed4c279f0c132ac5e0f858827ab81be31414` 为 BASE。2026-08-08 发生
仓库对象库损坏（`prj/.git/objects/` 125 个前缀目录仅剩 18 个有效对象、无 pack 文件，
`refs/heads` 与 `refs/remotes` 结构丢失）。恢复过程中确认：

- `301fed4`（Track-P BASE）与 `5b54582`（Task 3.0 checkoff）**从未 push 到远端**，
  对象不可恢复，**永久丢失**；
- 本地 `feature/*` 分支一并 drop；
- `main` 与 `agent/s12-acoustic-realism-review-optimization` 通过 GitHub
  (`Jovifei/Tesla_Simulate_vico.git`) 的 `2d8c58a` / `2921dd91` 重建成功。

后果：`assert_track_p_unchanged.py` 的 `git diff --name-only 301fed4` 直接报
`bad object`，Track-P 治理断言**完全失效**。因此必须以恢复后的提交重新固化基线。

---

## 2. 基线标识

| 项 | 值 |
|---|---|
| 基线名称 | `S12 Track-P Baseline v2` |
| **Commit SHA** | `41d819ad0b99bb24b10d46e235b8b85f9e46359e`（短 SHA `41d819a`） |
| **Assertion baseline SHA** | `41d819ad0b99bb24b10d46e235b8b85f9e46359e`（脚本内 `BASE` 常量） |
| 父提交 | `2921dd9`（GitHub 上 agent 分支的最后一个已 push 提交） |
| 分支 | `agent/s12-acoustic-realism-review-optimization` |
| worktree | `E:/Tesla_speed/worktrees/s12-v12` |
| 推送状态 | **未 push**（遵循 no-push 默认策略，需 Jovi 显式授权） |
| 冻结文件清单摘要 | `9fa925f9cbf180d9929209a8ef806a33f588072fcb397d55cb77d2cc638f44cb` |
| 冻结文件数 | **177** |
| 冻结符号摘要 | `e1fbda0a64d7232a8c17712a0c63d9ae3e0f95ae9bf9236c55d049b9b5bd9f7d` |
| 冻结符号数 | 2 |

`41d819a` 的内容 = `2921dd9` + Task 3.1（Post-PTR Loudness Compensation）+
行尾归一化修复 + 临时脚本清理，共 91 个文件。

---

## 3. 冻结清单（Track-P，177 个文件 + 2 个符号）

### 3.1 路径级冻结

| 分组 | 文件数 | 说明 |
|---|---:|---|
| `tools/sound_sim/s12/acoustic_demo/` | 58 | runtime_ptr_adapter / runtime server / sound_renderer adapters |
| `tools/sound_sim/matlab/` | 39 | MATLAB 工具链 |
| `tools/sound_sim/s12/benchmark/` | 31 | radiation / fvm 基准 |
| `tools/sound_sim/s12/validation/` | 18 | fanno-fvm、radiation_impedance、transient_wave 参考实现 |
| `tools/sound_sim/s12/tests/` | 14 | radiation / fvm MATLAB 契约测试（`*.m`） |
| `tools/sound_sim/s12/models/` | 12 | PTR / 辐射模型 |
| `tools/sound_sim/s12/playground_v11/` | 4 | — |
| `tools/sound_sim/s12/playground_v12/` | 3 | — |
| **合计** | **177** | |

匹配规则（子串命中即冻结）：
`acoustic_demo/`、`radiation`、`fvm`、`ptr`、`matlab`、`manage_bundle_loudness`。

### 3.2 符号级冻结

路径子串匹配抓不到「函数级冻结项」——两者的宿主文件路径均不含冻结词。
v1 把这一点记为「已知限制，交人工 review」；v2 用 AST 规范化摘要闭合：

| 宿主文件 | 符号 | 冻结范围 |
|---|---|---|
| `tools/.../acoustic_identity_v015/loudness_manager.py` | `manage_bundle_loudness` | **仅签名/API**（参数 + 返回标注）；函数体可重构 |
| `tools/.../acoustic_identity_v015/render_identity_v02.py` | `_health` | **整个函数体** |

摘要基于 `ast.unparse`，对注释、空白、行尾、引号风格不敏感，只对语义敏感。

### 3.3 Track-S 豁免（allowlist）

| 路径 | 豁免理由 |
|---|---|
| `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_post_ptr_loudness_compensation.py` | Task 3.1 新建的 **Track-S 单测**，仅因文件名含 `ptr` 被子串规则误扫进冻结集。若不豁免，后续任何一次修改都会产生假 FAIL。 |
| `tools/sound_sim/s12/playground_v12/common/s12_v12_apply_frozen_radiation_frame.m` | v1.2 Track-S 音频适配器；文件名含 `radiation`，但只消费冻结 package，不修改其数学或内容。 |
| `tools/sound_sim/s12/tests/test_s12_v12_source_core_matlab.m` | v1.2 Track-S MATLAB regression；文件名含 `matlab`，不属于冻结 MATLAB 数值核心。 |

> 新增豁免条目必须同步登记在本表，并说明理由。

---

## 4. 允许编辑面（Track-S）

以下是本变更**唯一允许修改**的范围。

### 4.1 `tools/sound_sim/s12/acoustic_identity_v015/`（除 3.2 的两个冻结符号外）

- `acoustic_analysis/` — `engine_identity_metrics.py`、`realism_metrics.py`、
  `reference_feature_extractor.py`、`reference_features.py`、`spectral_targets.py`、`plotting.py`
- `acoustic_layers/` — `afterfire_model.py`、`idle_dynamics.py`、`low_frequency_body.py`
- `sources/` — 8 个车型声源：`flat_plane_v8`（Ferrari 458）、`supercharged_hemi`（Hellcat）、
  `rotary_turbo`（RX-7 FD）、`toyota_i6_turbo`（Supra JZA80）、`nissan_v6_turbo`（GT-R R35）、
  `lamborghini_v12`（Aventador）、`lexus_v10`（LFA）、`mercedes_v8`（C63 W204）
- `tuning/` — `deep_realism.py`、`loudness_compensation.py`、`reference_reconstruction.py`
- `targets/`、`reference_database/` — 目标与参考数据
- `render_identity_v02.py`（`_health` 除外）、`render_realism_v10.py`、
  `render_drive_cycle_v10.py`、`synth_primitives.py`、`contracts.py`
- `loudness_manager.py`（`manage_bundle_loudness` **签名**除外）
- `scripts/`、`tests/`、`docs/`（产物目录）

### 4.2 外挂载点

- `tools/sound_sim/s12/tests/test_s12_engine_acoustic_identity_v015.py`
- `docs/superpowers/**`（计划 / 设计 / 报告）

---

## 5. 断言脚本

`tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`

```bash
python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py
# 退出码 0 = Track-P 未改动；1 = 越界
```

### 5.1 五道检查

| # | 检查 | v1 是否覆盖 | 说明 |
|---|---|---|---|
| 0 | BASE commit 可解析性 | ❌ | 不可解析时降级为摘要校验并打印修复指引，而不是无声失效 |
| 1 | `git diff --name-only BASE` 无冻结路径 | ✅ | 已提交改动 |
| 2 | `git diff --check BASE` 干净 | ✅ | 空白/行尾错误 |
| 3 | 工作树 / 索引无冻结路径改动 | ❌ | 拦截**未提交**的 Track-P 编辑 |
| 4 | 冻结文件清单摘要匹配（177 个） | ❌ | 内容寻址，BASE 丢失仍有效；增删冻结文件同样拦截 |
| 5 | 冻结符号摘要匹配（2 个） | ❌ | 闭合 v1 的「已知限制」 |

检查 4/5 是**内容寻址**的：即使 BASE commit 对象再次丢失，冻结边界依然可验证。
这是针对本次事故的根因加固。

### 5.2 已跟踪 vs 未跟踪的不同判定

- **已跟踪**路径：整路径子串匹配（保守）。
- **未跟踪**路径：只看**目录段**。否则 Track-S 的临时分析脚本
  （如 `scripts/_analyze_radiation_fidelity.py`）会仅因文件名含 `radiation` 被误判越界。
  未跟踪文件不可能修改既有冻结内容，唯一风险是「往冻结目录塞新文件」——该场景仍被拦截。

### 5.3 rebaseline 流程

```bash
python .../assert_track_p_unchanged.py --print-baseline
# 输出 BASE / FROZEN_MANIFEST_SHA256 / FROZEN_MANIFEST_COUNT / FROZEN_SYMBOL_SHA256
# 将四个常量回填脚本，并更新本文档第 2 节表格
```

**前置条件**：rebaseline 只能在确认「当前 Track-P 内容可信」时执行；
本次的可信来源是 GitHub 上的 `2921dd9`（Track-P 部分与之逐文件一致）。

---

## 6. 回归测试

`tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_track_p_guard.py` — 21 项，
把建立 v2 时的三个手工负向验证固化为自动化用例：

1. 篡改冻结文件（`s12_radiation_case_definition.m`）→ 检查 1 + 3 命中；
2. 篡改 `_health` 函数体 → 检查 5 命中（v1 抓不到）；
3. 篡改 `manage_bundle_loudness` 签名默认值 → 检查 5 命中（v1 抓不到）；
   同时验证签名模式**不**因函数体重构误报。

```bash
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_track_p_guard.py -q
# 21 passed
```

---

## 7. 已知陷阱

- **行尾（CRLF/LF）**：本仓库混用行尾。用 Python 文本模式
  (`Path.read_text` / `write_text`) 回写 LF 文件会在 Windows 上整体转成 CRLF，
  导致 `git diff --check` 报出整文件的 trailing whitespace。修改文件时须显式
  `newline=""` 或对齐原文件行尾。（建立 v2 时的负向测试就踩过这一脚。）
- **`ptr` 是一个极短的子串**：任何含 `ptr` 的新文件名都会被判为冻结。
  Track-S 新文件命名请避开，否则需要进 allowlist。
- **`manage_bundle_loudness` 的路径子串规则永远不会命中任何文件**
  （宿主文件名是 `loudness_manager.py`），保留它只是历史兼容；实际防护来自符号级守卫。

---

## 8. 验证记录

```
OK: Track P 未改动（基线 S12 Track-P Baseline v2 / BASE 41d819a）
  repo root         : E:\Tesla_speed\worktrees\s12-v12
  冻结文件          : 177 个，清单摘要匹配
  冻结符号          : 2 个，摘要匹配
  工作树/索引       : 无冻结路径改动
  相对 BASE 已提交改动: 均属 Track S；git diff --check 干净
EXIT=0
```

守卫回归：`21 passed`。
