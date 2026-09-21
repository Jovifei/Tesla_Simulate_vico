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

连续收据升级为 `s12.stage_ai6.continuous_drive_pair.v2`，每个连续角色报告都必须通过以下绑定：

| 字段 | 约束 |
| --- | --- |
| `afterfire_requested_event_times_s` | 来自固定调度，当前为 `[18.0]` |
| `afterfire_observed_onset_s` | 源 stem 第一个非零观测 onset，不早于 lift，且在 30 秒窗口内 |
| `afterfire_observed_onset_frame` | 由观测秒数映射的 48 kHz 帧，误差不超过 1 帧 |
| `afterfire_observation_domain` | 固定为 `SOURCE_STEM_PRE_IR` |
| energy/count/role identity | 能量为正、事件计数有效、A/B/off-switch 共享 trace/seed/分母/输出策略并逐角色校验 |

`qualified_three_way` 同时校验新 v2 连续收据、旧 AI-6 连续文件的历史 role hash、十个 canonical 场景以及 RX-7 的历史 A 来源路径，避免包滚动时错误地把 AI-6 A 当成 pre-AI4B 来源。

## 验证结果

- focused AI-7/AI-6/three-way/remaining-vehicle/feedback-package/AI-5 回归：`88 passed`，退出码 `0`。
- 严格 Python 编译：`python -W error -m compileall -q tools/sound_sim/s12/acoustic_identity_v015`，退出码 `0`。
- Track-P：`180` 个冻结文件、`2` 个冻结符号，冻结路径改动 `0`，退出码 `0`。
- `git diff --check`：退出码 `0`。
- 新包通过 `qualified_three_way.verify` 和 manifest 自校验；旧 AI-6 v2 包未覆盖。

新包：`E:\Tesla_speed\review_packages\s12-stage-ai7-continuous-event-evidence-20260921-v2`

- `ARTIFACTS.json` SHA-256：`a4d487722d4abdca42eeb8b6ef65407a241f9c40873f1014a8904fff8a93af0e`
- `summary.json` SHA-256：`f0b119856aeb073d614ed89733864d7de4a2f1adf35671077c70815e91b20285`
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

1. 远端 ChatGPT 需要独立读取当前分支、diff、测试记录和 v2 包后给出 `DONE`、下一轮 `PLAN` 或 `BLOCKED`。
2. 需要把分支正常 push，并在 GitHub 认证可用时创建 Draft PR；不得合并 main 或 force-push。
3. Jovi 仍需对 RX-7/Aventador 的 A/B 连续驾驶包进行命名人耳试听；在明确反馈前不得把自动证据升级为 Human PASS。
