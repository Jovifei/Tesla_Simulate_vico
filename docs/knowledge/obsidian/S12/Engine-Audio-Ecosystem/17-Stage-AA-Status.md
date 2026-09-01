---
title: Stage AA Hellcat Acoustic Quality Closure
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-AA
document_type: engineering_status
status: waiting_for_jovi_audition
updated: 2026-09-01
---

# Stage AA 当前状态

Stage-Z PR #3 已合并到 main `209378bcb9a0c1a352ffd56ca1c765ecce01f81d`。AA1 layer ledger 确认主要能量损失在压力绝对基线被 dP/DC 去除，随后 frozen PTR 继续固定衰减；没有使用 master gain 修复。

AA0 将 Stage-Z 的旧 `PROVEN_CONTRIBUTION` 拆为 causal effect、engineering significance 和 quality direction。12 个可执行方法全部有 causal PCM effect，9 个达到工程显著性，collector/persistent/DasEtwas 三项低于阈值；ENSIM4 仍是 teacher-only。

AA4 只建立 AA-C0…AA-C3，均通过 11 场景 hard gates；AA-C3 是诊断偏好。AA5 使用 Python finalist 代理指标，MATLAB 未启动且保持 pending。

`raw_dynamic_contract.json` 明确 raw 的 idle→WOT、tip-in、shift、lift、afterfire、idle-return 口径；Dynamic Review 不做逐段响度匹配，Timbre Review 才允许共享 RMS 派生比较。

## v3 试听包

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3` 已生成并通过 validator：11 场景、110 个 PCM24 stereo WAV、Timbre Review、盲化 Dynamic B/C、答案页和 objective receipt。manifest SHA：`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`。v1/v2 保持原样。

AA-C3 平均 RMS=`-47.801 dBFS`、dynamic range=`5.747 dB`、centroid=`1830.4 Hz`，比 Stage-Z 的 `-62.039 dBFS / 3.582 dB / 4247.3 Hz` 更接近 Parent；这仍是诊断性数字证据，不是人耳验收。

当前唯一暂停点是 `WAITING_FOR_JOVI_AUDITION`。反馈前不合并候选音频/profile tuning，不扩散 Ferrari/RX-7；R1、OEM calibration、Profile Freeze、Android Runtime 与硬件验收仍关闭。
