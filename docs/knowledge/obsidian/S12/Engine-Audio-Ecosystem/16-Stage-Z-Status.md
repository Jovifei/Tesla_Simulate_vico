---
title: Stage Z Open-Source Absorption Status
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-Z
document_type: engineering_status
status: traceability_pass_acoustic_gain_unproven
updated: 2026-09-01
---

# Stage Z 当前状态

Stage Z 原始输入 main 为 `62b3759c9e8026e62b4aa2cefeb0a3fbc73597aa`；PR #3 已普通 merge，当前 main 为 `209378bcb9a0c1a352ffd56ca1c765ecce01f81d`。Stage Z 在独立分支上建立 method-level traceability 与 OFF/ON PCM 证据，v2 包位于 `E:\Tesla_speed\review_packages\s12-stage-y-hellcat-layers-v2`，manifest SHA 为 `cf70e877b4018389df1fede3963d4cf685244860ae3efacf1476c31d0644a64c`。

矩阵覆盖 25 个 source、30 个 method rows；Engine-Sim 6 个 clean-room methods、VehicleNoiseSynthesizer/DasEtwas/Ignis/Markeasting 为等价实现，ENSIM4 保持 teacher-only。12 组 A/B 均有 SHA 差异、目标指标变化和 guard 通过。AA0 已新增 `method_adoption_matrix_v3.json` 与 `tasks/reports/runtime/s12-stage-aa/method_ablation_scorecard_v2.json`，将 causal effect、engineering significance 与 quality direction 分开。详细机器证据在 `tasks/reports/runtime/s12-stage-z/` 与 `tasks/reports/runtime/s12-stage-aa/`，整体报告在 `docs/08-reports/08-s12-stage-z-open-source-absorption.md`。

AA0 已将旧 `PROVEN_CONTRIBUTION` 降为兼容字段：12/12 方法有可检测 causal PCM effect，9/12 达到工程显著性，collector/persistent/DasEtwas 三项低于逐指标 significance contract；quality direction 因无同步 R1 全部为 `REFERENCE_UNAVAILABLE`。Parent→Final objective 只证明当前 main 的数字声学变化，不证明声音质量提升；Final raw 的 aggregate RMS/dynamic range 低于 Parent，故整体 acoustic contribution 保持 `PARTIAL / UNPROVEN`。试听页默认 A/B 盲化，答案页独立揭盲。

旧 v1 包保持原样。HUMAN_AUDITION、合法同步 R1、OEM/calibration、Profile Freeze、Android Runtime 和硬件验收仍为外部门禁。
