## Why

S12 声浪模拟器的 8 车粗调（Stage A）已完成：§4.2 粗调门禁 8/8 车 PASS，3 锚点（Ferrari 458 / Hellcat / RX-7）生产发布器 `publish_identity_v02` 全部 PUBLISH OK（health/loudness/one-gain/comparison 均通过）。但粗调仅覆盖「逐频带能量占比」与「idle centroid」两类粗粒度指标。

进入 Stage C–E 的核心动机：
- 逐状态（idle / steady / accel / full pull / lift-afterfire / idle return）频谱真实感、引擎身份分离（identity separation）、afterfire/lift 瞬态真实感尚未达标，无法支撑产品级体验。
- 12 个预存在 pytest 回归（ferrari / hellcat / rx7 的细粒度物理与 stem-balance 断言）仍 FAIL，属于 Stage B/C 收尾必须修复项。
- 缺少人耳盲听一致性门禁（human audition），产品收敛缺乏客观前置条件。

本 change 对三锚点做 Deep Realism、建立盲听门禁，并在三锚点全部通过后收敛出产品级 AudioParameterPackage。

## What Changes

- 对 Ferrari 458 / Hellcat / RX-7 三锚点做逐状态 deep realism 调音（仅 Track S 范围：sources / idle_dynamics / loudness / afterfire）。
- 修复 12 个预存在 pytest 回归（ferrari rms_bounded + high_freq_grows；hellcat blower shaft lobe；rx7 housing + turbo-lift + acceleration-stem-balance + constant_state；+5 个 LUFS-RMS 集成子测试），均在 Track S 内完成，不触及冻结物理边界。
- 新增人耳盲听混淆矩阵门禁（human audition gate），作为产品收敛的前置条件。
- 仅在三锚点 deep realism + 盲听门禁全部通过后，输出产品 AudioParameterPackage。
- **不修改** Track P（radiation / PTR core / FVM / runtime / MATLAB）或 `render_identity_v02._health` / `manage_bundle_loudness` 签名。

## Capabilities

### New Capabilities
- `anchor-deep-realism`：三锚点逐状态（idle/steady/accel/full pull/lift-afterfire/idle return）频谱目标、引擎身份分离目标，以及既有 12 个 pytest 回归修复。
- `human-audition-gate`：盲听混淆矩阵门禁——以参考/竞品为混淆项，三锚点盲听辨识率需达阈值方可进入产品收敛。
- `audio-parameter-package`：产品级 AudioParameterPackage 收敛输出（仅在三锚点 deep realism 与盲听门禁全部通过后生成）。

### Modified Capabilities
（无既有 spec 行为变更；本 change 新增上述三个能力。）

## Impact

- **代码**：`tools/sound_sim/s12/acoustic_identity_v015/sources/{flat_plane_v8_source.py, supercharged_hemi_source.py, rotary_turbo_source.py}` 及 idle_dynamics / afterfire / loudness 相关 Track S 模块；`tests/test_s12_engine_acoustic_identity_v015.py` 中 12 个回归修复。
- **保持**：§4.2 粗调门禁持续 PASS；Track P 冻结边界零改动；`git diff --check` 保持干净。
- **依赖**：`publish_identity_v02` 生产发布器、`reference_database/realism_reference_manifest.json` 参考库、Stage B 统一验收报告（`tasks/reports/runtime/s12-remaining-vehicles-v1/stage_b_acceptance_report.md`）。
- **产出**：人耳盲听样本集（ab.wav / 盲听表单）、AudioParameterPackage（JSON）、更新后的 verify JSON 与验收报告。
