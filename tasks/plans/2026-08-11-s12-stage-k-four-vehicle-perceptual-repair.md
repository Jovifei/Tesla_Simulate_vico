# S12 Stage K 四车声学修复、瞬态重建与状态响度校准

## 目的与状态边界

本计划针对 Jovi 对具名试听的反馈，修复四个独立声学身份：Hellcat、C63 W204、GT-R R35 与 LFA。目标是让声源的时间结构、机械/增压特征、换挡与收油行为以及低负载到高负载的响度变化可解释、可回归、可供 Jovi 试听。所有产物继续标记为 `synthetic / uncalibrated / vehicle-inspired / not OEM reproduction`。

当前冻结起点：

- Stage J 基线提交：`b78b6c3031269eae1a0b917ce7bbaaed2af81c76`
- Stage J 分支：`agent/s12-stage-j-three-vehicle-identity`
- Stage J 工作树：`E:\Tesla_speed\worktrees\s12-stage-j-three-vehicle-identity`
- 新 Stage K 工作树：`E:\Tesla_speed\worktrees\s12-stage-k-four-vehicle-perceptual-repair`
- 新 Stage K 分支：`agent/s12-stage-k-four-vehicle-perceptual-repair`
- 基线相对 `origin/main`：`0 behind / 42 ahead`
- 基线工作树必须保持干净；任何漂移均为 `BLOCKED / BASELINE_DRIFT`。

禁止修改 FVM、PTR core、Radiation、Runtime、Android/ESP32、MATLAB、Simulink、Track-P guard/baseline/allowlist、公共 LF Body/Rumble/Pre-PTR EQ、`manage_bundle_loudness` 的签名/实现/正式 `-16 LUFS / -1.5 dBFS` 策略。不得覆盖 Stage I/Stage J 历史候选和试听包，不得 push、merge、rebase 或修改 `main`。

## 证据与反馈边界

Jovi 的反馈是具名目标输入，不等同于自动指标或正式 Human PASS：

- Hellcat：A/B/C 均不像地狱猫；保留 C 的较柔和机械方向，目标是可辨识的双螺杆啸叫与 HEMI 低频主体。
- C63 W204：加速低频轰鸣方向可保留；高频噪音过大且不正确，需要降低粗糙/刺耳感。
- GT-R R35：已有调性方向，但真实感仍有约 60% 缺口。
- LFA：总体身份较好；换挡顿挫、减速行为和加速段响度跨度需要修复。
- 全局响度：低负载/怠速略提高，高负载略降低；RPM 只改变阶次频率，不得直接驱动大幅全局增益。

两个社交媒体页面只作为 R2 定性研究入口：

- [Hellcat 视频](https://www.douyin.com/video/7442878447719943460)
- [RX-7 / GT-R 声浪原理视频](https://www.douyin.com/video/7512312931426585890)

执行时必须记录页面可访问性和音轨是否可用。若无法合法获得可审计音轨，写 `NOT_AVAILABLE`，不得声称已听到或测量视频音频，不下载新媒体，不将原始媒体放入仓库、Obsidian 或试听 ZIP。若未来获得临时音频，只能置于 `E:\Claude_allow\Download\s12-stage-k-reference\`，只保存相对频带/谱峰/瞬态摘要，并标记 `R2/social-media-compressed`, `microphone/AGC dependent`, `not absolute loudness evidence`。

## 固定管线

四车候选均保持独立源，不共享 excitation：

```text
Independent Source
→ Source Operating Trim（仅 load/throttle）
→ Idle
→ Deterministic Afterfire
→ LF Body
→ Exhaust Rumble
→ Vehicle Shift/Transient
→ Common Pre-PTR EQ
→ Frozen PTR
→ Edge Fade
→ One Whole-Cycle Gain
→ PCM24
```

所有新增能量必须在公共 Pre-PTR EQ 和 Frozen PTR 之前；正式响度只允许一次 whole-cycle gain。试听副本可请求 `1.25x = +1.9382 dB`，但只能采用同车共同的 peak-safe attenuation-only 处理并记录 requested/actual/headroom。

## 分阶段执行清单

### K0：冻结输入与账本

1. Fail-closed 检查 Stage J HEAD、分支、clean 状态和 `origin/main...HEAD = 0 42`。
2. 写入 `tasks/reports/runtime/s12-stage-k-four-vehicle-repair-v1/stage_k_jovi_input_feedback.json` 与视频证据文档。
3. 记录 Stage J 候选、试听包、报告及参考 evidence 的 SHA；旧字节保持不变。
4. 更新 `tasks/todo.md`、`tasks/lessons.md`，记录“RPM 决定阶次频率而非响度”和“通过主体只改瞬态层”两条规则。
5. 本阶段提交：`docs(s12): freeze Stage K perceptual repair inputs`。

### K1：Candidate 契约与父候选隔离

建立 `acoustic_identity_v015/stage_k/` 的 loader、renderer 和 schema。父候选固定为 Hellcat Stage I C（诊断父候选）、C63/GT-R/LFA Stage J v1；`candidate=None` 对八车保持 Stage C bit-identical。每个字段必须有 base commit、parent SHA、`C/synthetic/candidate_assumption` provenance；诊断必须区分 requested/read/configured/active/inactive/unused。先写 RED，观察 schema/模块缺失，再最小实现 GREEN。

### K2：状态响度平衡

新增 `source_level.py` 的 `OperatingLevelTrim`。初始边界为低负载 `+1.5 dB`、高负载 `-1.5 dB`、load blend `[0.25, 0.75]`、平滑 `0.15 s`。只读 load/throttle，同步作用于 pressure 和指定连续 stems；不读 RPM/speed/PCM/RMS/LUFS，不处理 shift/afterfire/BOV/bypass 事件，不做 AGC/compressor/limiter。对低/高负载、RPM 不变性、事件 stem 不变、pressure 差值和零输入写测试。

### K3：Hellcat 双螺杆身份重建

新增 `sources/supercharger_whine_v4.py`，用 2.36:1 shaft、rotor/lobe family、gear/casing、扭转调制、load/boost envelope、进气/壳体传递和 boost-history bypass 组成动态声源。官方事实只锁定 twin-screw、旁通、2.36:1 和约 14,600 rpm；11.8/23.6 等阶次继续标记 synthetic。删除 `sideband_depth × 5` 隐式倍率；attack/release 改为真实 10–90/90–10 时间并用 `tau = measured_time / ln(9)`。`blower` 必须等于所有子 stem 逐样本之和；无 boost history 的 bypass 严格为零；禁止固定 tone、白噪声和全局 gain。门禁包括 order ridge ≤1%、load correlation ≥0.82、sideband/main 0.08–0.18、4–12 kHz ≤0.06、40–200 Hz/rumble ≤5% 变化。

### K4：C63 高频粗糙度修复

用 `mercedes_na_v8_source_v3.py` 替换语义错误的 `bark_resonance_scale`，拆分 primary order、upper partial mix、decay、mechanical upper tilt、high-RPM compression。保留 cross-plane 时序、低频排气、LF Body、Rumble 和 closed-throttle tail。要求 4–12 kHz 短时峰下降 3–6 dB、低频变化 ≤5%、1–4 kHz bark 能量下降 ≤10%、roughness 降低 20–40%，不得添加随机宽带噪声。

### K5：GT-R 并行双涡轮时间结构

用 `nissan_parallel_twin_turbo_v6_source_v3.py` 建立两套并行 shaft state、轻微失谐、shaft/BPF、进气 duct、boost-history BOV。修正绝对 `turbo_whistle_mix` 误用（范围 0.12–0.24），恢复 bank phase 120°（108–132°），取消 3800 rpm secondary gate；BPF 必须由 shaft phase 产生，不能直接由 engine RPM。保持 V6 三事件/转结构、两轴同时建立、无 boost history 时 release 为零，并以 1–4 kHz、4–12 kHz 和 order concentration 门禁约束。

### K6：LFA 专属换挡/减速

继续使用 `lexus_high_rev_v10_source_v2.py`，新增 `lfa_transient_dynamics.py`，不调用通用 shift layer。用 ASG torque cut、exhaust re-engagement、intake reopen 替代通用深切和固定 70 Hz boom；收油使用连续的 intake/metallic decay 与 V10 overrun。门禁为 shift dip 2–4 dB、settling 0.12–0.25 s、overshoot ≤1 dB、无固定 70 Hz、5/10/15 阶变化 ≤5%、加速响度跨度 ≤4 LU。

### K7：指标、有界搜索与四车具名试听

建立车型专属指标和确定性有界候选搜索：先硬门禁，再检查状态无回退 >10%，再按车型误差、父候选改动量、字典序稳定选择。保留 final-PCM reference-distance 公式和 30% 门禁，不得降低阈值。生成 `E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1\`，每车提供 baseline/candidate 60 秒、低/高负载、shift、lift/deceleration 和诊断 stems，预填具名反馈 CSV。自动门全过才写 `WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW`；失败则写 `PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY / DIAGNOSTIC_FEEDBACK_ALLOWED`。

### K8：验证、报告、Obsidian 与反馈闭环

运行 Stage K focused、Stage I/J 回归、完整 S12 和 Track-P guard，记录实际数量和 SHA，不复用历史数字。生成 Stage K 报告、metrics、reference distance、loudness balance、test evidence 和 artifact manifest；同步 Obsidian 项目状态、车型卡和新 `21-S12-Stage-K-四车声学修复与状态响度校准.md`。收到具名反馈后最多 K v1→v2→v3：一次只改失败车型，另外三车 PCM SHA 不变；三轮仍失败则 `PARTIAL / HUMAN_AUDITION_FAIL`，不进入 Profile Freeze、Approved、Simulink、Runtime 或 Android。

## 验收与停止状态

每个任务执行顺序必须是：RED 测试 → 观察预期失败 → 最小实现 → GREEN → focused regression → staged diff review → 独立提交。任何 Track-P guard 失败立即停止，不 rebaseline、不改 allowlist。自动指标和具名反馈都不能自行生成 Human PASS 或 Approved Profile。

首次交付允许状态：

```text
WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW
PARTIAL / AUTOMATED_GATE_FAIL
UNQUALIFIED_DIAGNOSTIC_ONLY
DIAGNOSTIC_FEEDBACK_ALLOWED
```

最终禁止状态：

```text
PROFILE FREEZE
APPROVED PROFILE
SIMULINK INTEGRATION
RUNTIME INTEGRATION
ANDROID / ESP32 INTEGRATION
OEM REPRODUCTION
```
