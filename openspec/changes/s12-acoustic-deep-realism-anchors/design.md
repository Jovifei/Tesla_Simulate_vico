## Context

动机见 proposal.md（Why）。当前约束：渲染链为 `source → idle_dynamics → afterfire → low_frequency_body → 冻结 PTR 适配器 → PCM24`，纯 Python 实现，不依赖 Simulink 运行时。**Track P（radiation / PTR core / FVM / runtime / MATLAB、`render_identity_v02._health`、`manage_bundle_loudness` 签名）已冻结，零改动**；仅 **Track S（sources / idle_dynamics / afterfire / loudness 等 Python 模块）可编辑**。Stage A 八车粗调已完成，§4.2 门禁 idle/accel 8/8 PASS；三锚点（Ferrari 458 / Hellcat / RX-7）生产发布器 PUBLISH OK。仍存在 12 个预存在 pytest 回归与缺失的人耳盲听门禁。§4.3 约束：5.5–12 kHz 仅允许上游感知补偿。

## Goals / Non-Goals

**Goals:**
- 三锚点逐状态（idle / steady / accel / full pull / lift-afterfire / idle return）频谱真实感达标，且引擎身份分离满足参考库阈值。
- 在 Track S 内修复全部 12 个预存在 pytest 回归，且不触碰冻结边界。
- 建立人耳盲听混淆矩阵门禁，作为产品收敛的客观前置条件。
- 三锚点 deep realism + 盲听门禁全部通过后，确定性收敛输出 AudioParameterPackage。

**Non-Goals:**
- 不修改 Track P 任何模块、不改动 `_health` 或 `manage_bundle_loudness` 签名。
- 不重做 Stage A 八车粗调（仅确保粗调门禁在 deep realism 后保持 PASS）。
- 本 change 不扩展至八车全量 deep realism——仅三锚点；其余五车留给后续 change。
- 不引入新的外部运行时依赖（如 MATLAB/Simulink）。

## Decisions

**D1：逐状态频谱目标注入 Track S 源 manifest，而非冻结 PTR。**
每个锚点的 Track S 源模块（如 `flat_plane_v8_source.py` / `supercharged_hemi_source.py` / `rotary_turbo_source.py`）新增按状态键控的频谱目标块（per-band 能量占比 / 阶次耦合）。理由：只有 Track S 可编辑，目标注入必须落在源与 afterfire 层。替代方案（调冻结 PTR 适配器）被否决——违反冻结边界。

**D2：身份分离以 `realism_reference_manifest.json` 阈值强制。**
跨锚点 + 参考的逐状态 band-energy 向量计算 pairwise 谱距，最小分离阈值存于参考库 manifest。理由：复用既有参考库，避免引入新依赖；与 §4.2 粗调共用同一参考体系。

**D3：12 个回归全部以 Track S-only 编辑修复。**
ferrari（`rms_bounded` + `high_freq_grows`→高频内容门控）、hellcat（`blower shaft lobe`→机械增压 whine 建模）、rx7（`housing` / `turbo-lift` / `acceleration-stem-balance` / `constant_state`→转子机专属）及 5 个 LUFS-RMS 集成子测试，均在 Track S 的 source / idle / afterfire / loudness 行为层修正。理由：前期分类已确认这 12 项全部位于 Track S 范围。

**D4：盲听门禁为 Track S 脚本——生成密封的 opaque-coded wav 集 + 盲听表单 + 混淆矩阵聚合器。**
样本身份映射单独密封存储（不进入盲听表单）。门禁阈值与天花板以配置驱动。理由：提供可复现、客观的产品收敛前置条件。

**D5：AudioParameterPackage 为含可复现 manifest（source commit + 确定性 render seed）的 JSON。**
收敛严格受 `anchor-deep-realism` 与 `human-audition-gate` 两个 spec 要求门控，仅当两者 PASS 后产出。

## Risks / Trade-offs

- **[风险] 逐状态 deep realism 调音可能偏移 §4.2 粗调指标** → 缓解：每个锚点调音后即在 CI 跑 `publish_identity_v02`，粗调门禁作为回归护栏。
- **[风险] 盲听需要真实受试者，排期与一致性难控** → 缓解：门禁可失败重跑；若受试者不可得，可先以自动感知代理指标占位（见 Open Questions）。
- **[风险] 12 个回归间存在隐藏跨依赖** → 缓解：小批量修复，每批之间跑全量 pytest。
- **[权衡] 仅三锚点做 deep realism，五车留后续** → 接受：锚点先建立产品级范式，再横向铺开。

## Migration Plan

所有改动均为 Track S 增量编辑 + 新增 spec/package 产物，无 Track P 系统级变更。回滚 = 对该 change 分支 commit 做 `git revert`；冻结 Track P 不受影响，无需系统回滚。

## Open Questions

- 各状态 deep-realism 残差阈值的精确数值（在 build 阶段于 tuning manifest 中最终确定）。
- 盲听采用真实人类受试者，还是受试者不可得时以自动感知代理指标占位（门禁逻辑兼容两者）。
- 盲听门禁辨识率阈值与交叉混淆天花板的具体数值（配置驱动，build 阶段设定）。
