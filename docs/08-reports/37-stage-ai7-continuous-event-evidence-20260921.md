# S12 Stage AI-7：连续驾驶事件观测证据闭合

更新时间：2026-09-22

状态：`ENGINEERING_EVIDENCE_VERIFIED`；`HUMAN_STATUS=NOT_EVALUATED`；`PROMOTABLE=false`

## 结论

AI-7 已完成连续驾驶 afterfire 事件的“请求时间”和“源 stem 实际观测 onset”分离，并把观测帧、观测域、能量和角色/轨迹身份绑定进 A/B/off-switch 收据。此次修复没有改变声学源算法、参数、IR、seed、track、父级归一化分母、输出保护或 RX-7 24 帧边界策略。

自动化证据已通过，新的不可覆盖 v2 包已生成并验证；RX-7 和 Aventador 的 A/B 解码 PCM 均与固定的 AI-6 v2 包字节一致。六个没有合格 B 源的车型仍保持不可用。该结果不是 Human PASS、OEM 校准、Profile Freeze 或 Android 产品化许可。

## 根因与范围

旧连续收据把调度事件时间 `18.0s` 当成了源事件发生时间。实际 `afterfire_model.py` 已提供源侧 `afterfire_onset_s`，但连续流水线没有把它暴露为独立观测证据；旧测试中的伪造报告也只写入 `[18.0]`，因此没有证明源 stem 的实际 onset。

本阶段只改动以下范围：

- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/remaining_vehicle_pipeline.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/continuous_drive.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_ah/qualified_three_way.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai7_event_evidence.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai6_continuous_drive.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ai_threeway.py`
- `.github/workflows/s12-stage-ai-measured-feedback.yml`

明确未修改 `afterfire_model.py` 及源算法、搜参范围、IR、Reference、随机种子、连续轨迹、父级分母、输出保护和边界修复逻辑。

## 新证据合同

连续收据使用 `s12.stage_ai6.continuous_drive_pair.v2`，每个连续角色报告都必须通过以下绑定：

| 字段 | 约束 |
| --- | --- |
| `afterfire_requested_event_times_s` | 来自固定调度，当前为 `[18.0]` |
| `afterfire_source_onset_s` | 源层诊断给出的 onset，必须与观测 onset 相同 |
| `afterfire_observed_onset_s` | 源 stem 第一个非零观测 onset，不早于 lift，且在 30 秒窗口内 |
| `afterfire_observed_onset_frame` | 由观测秒数映射的 48 kHz 帧，误差不超过 1 帧 |
| `afterfire_observation_domain` | 固定为 `SOURCE_STEM_PRE_IR` |
| energy/count/role identity | 能量为正、事件计数有效、A/B/off-switch 共享 trace/seed/分母/输出策略并逐角色校验 |

`render_continuous_pair`、`write_continuous_pair` 和 `qualified_three_way` 现在复用同一事件合同：生成、写包和验包都校验 A/B/off-switch、源层 onset、观测 onset/frame、count、energy、角色上下文以及 contract/summary 副本。写包失败时不会创建 WAV 或 receipt。`qualified_three_way` 同时校验新 v2 连续收据、旧 AI-6 连续文件的历史 role hash、十个 canonical 场景以及 RX-7 的历史 A 来源路径，避免包滚动时错误地把 AI-6 A 当成 pre-AI4B 来源。

### 固定 AI-6 输入身份核验

AI-6 v2 目录的 215 个 manifest 文件均存在且无漂移，实际 `ARTIFACTS.json` SHA 为 `28ef0738097f7e28bb4d49136a47a17dac5b3f80bff229dfbbe2161f1bb8cb13`，summary SHA 为 `226fb189df31ad6ffaaee0220ac0730331e5172826ce911b84dbeb753a16fe61`。旧 AI-6 报告/交接文档中的 manifest SHA `28ef0738097e7e28...` 是历史记录笔误；没有修改旧包，也没有把错误值当作 expected 通过门禁。AI-7 v3 绑定的是现场实测的实际 SHA。

## 验证结果

- AI-7 contract RED/GREEN：`19 passed`；iteration 1 的 focused 回归：`88 passed`。
- iteration 2 当前 focused AI-7/AI-6/three-way/remaining-vehicle/feedback-package/AI-5 回归：`92 passed`，退出码 `0`。
- 最终 exact HEAD `3dd9f77` 的完整 S12：`1332 passed, 3 skipped, 118 subtests passed`，耗时 `2487.96s`，退出码 `0`。
- skip 原因：1 项需要显式配置 `S12_LOCAL_ASSET_ROOT` 的本地真实素材；2 项 3000-block acceptance 需要 `S12_RUN_SLOW=1`。这些不是通过证据。
- 严格 Python 编译：`python -W error -m compileall -q tools/sound_sim/s12/acoustic_identity_v015`，退出码 `0`。
- Track-P：`180` 个冻结文件、`2` 个冻结符号，冻结路径改动 `0`，退出码 `0`。
- `git diff --check`：退出码 `0`。
- 新包通过 `qualified_three_way.verify` 和 manifest 自校验；旧 AI-6 v2 包未覆盖。

新包：`E:\Tesla_speed\review_packages\s12-stage-ai7-continuous-event-evidence-20260921-v3`

- `ARTIFACTS.json` SHA-256：`44d9449c056768f454533041fd27a880b01a6f83df16057fe40f0526fab53833`
- `summary.json` SHA-256：`ecb8154c84c3a63cb81c71914fdc39afc23e2b026d9d64cc4b1f7623dd963740`
- 包源提交：`adaf72db254f28cc64616452d629c9a750db6616`
- 包状态：`PARTIAL_B_AVAILABILITY`；B-ready：`2`

连续观测摘要：

| 车型 | requested | observed | frame | domain | A/B PCM 基线一致 |
| --- | ---: | ---: | ---: | --- | --- |
| RX-7 FD | 18.0 s | 18.043 s | 866064 | `SOURCE_STEM_PRE_IR` | 是 |
| Aventador LP700 | 18.0 s | 18.010 s | 864480 | `SOURCE_STEM_PRE_IR` | 是 |

与固定 AI-6 v2 的解码 PCM SHA：

- RX-7 A：`decea5f9d9b775aba4568a20331f7466ec3efcc7b93bf72244c24270ddd24ac2`
- RX-7 B：`d6efea70a7433cceb5d4856e18467c350fab0852ebce30d95eafb68662c9071f`
- Aventador A：`8a7f52152bf63993602a1491e713638fa6819f9b2d3f8ddcfc609b574bcfcacd`
- Aventador B：`e9adb09e3c2c8337595630dc3b39e5e15cbf2901edce5515138b8efd84ff58e5`

## 当前门禁与下一步

当前没有已知的 AI-7 实现阻塞。仍然保持以下边界：

1. 需要在最终 v3 上完成 serve preflight/真实浏览器抽查，并通过同一 C2C 记录交给远端复核。
2. 远端 ChatGPT 需要复核本轮完整 diff、实际 AI-6 baseline SHA、v3 包和最终执行输出后给出 `DONE`、下一轮 `PLAN` 或 `BLOCKED`。
3. 需要把分支正常 push，并在 GitHub 认证可用时创建 Draft PR；不得合并 main 或 force-push。
4. Jovi 仍需对 RX-7/Aventador 的 A/B 连续驾驶包进行命名人耳试听；在明确反馈前不得把自动证据升级为 Human PASS。
