# Jovi — S12 Stage L Hellcat 机械增压进气身份、Cross-Plane 顿挫轰鸣与低频体感校准执行计划

> **For Luna:** REQUIRED SUB-SKILL: use `using-git-worktrees`, `test-driven-development`, `subagent-driven-development`, `executing-plans`, `requesting-code-review`, `receiving-code-review`, and `verification-before-completion`.
>
> 每个实现任务严格执行：写 RED 测试 → 观察预期失败 → 最小实现 → GREEN → focused regression → staged diff review → 独立本地提交。首次具名包生成后硬停止，等待 Jovi 试听。

## 1. 目标、当前事实与阶段边界

### 1.1 Stage L 的唯一目标

本阶段只修 Hellcat，并把三个听感问题拆到正确的物理/声学源域：

```text
机械增压器/进气路径
→ 可辨识但不过度电子化的 twin-screw whine

Cross-plane HEMI 燃烧、blowdown、排气与结构路径
→ 更有重量的低频压力
→ 单侧 bank 不均匀节拍带来的“促—停—促”顿挫轰鸣

换挡/负载瞬态
→ torque cut、boost inertia、重新接合
→ 不再由整车混音统一下压和固定 70 Hz boom 冒充
```

首次执行结束时必须交付一套具名 Hellcat 工程试听包并停止。不得同时继续 C63、GT-R、LFA，不得进入 Profile Freeze、Simulink、Runtime 或 Android / ESP32。

### 1.2 权威起点

```text
Stage K 工作树：
E:\Tesla_speed\worktrees\s12-stage-k-four-vehicle-perceptual-repair

分支：
agent/s12-stage-k-four-vehicle-perceptual-repair

Stage K 当前 HEAD：
bf653c6f7a3779314d9891aaa801b29a4874db40

稳定实现提交：
4261bbfe34b11980fcb15a0a9b01bd6d5f75c9e6

相对 origin/main：
0 behind / 56 ahead

Stage K 当前状态：
PARTIAL / AUTOMATED_GATE_FAIL
WAITING_FOR_JOVI_STAGE_K_NAMED_REVIEW
```

本计划写入前工作树已核验 clean；本轮规划结束后允许唯一新增项为本计划文件本身。Luna 必须重新核验，不能复用本计划写作时的输出，也不能把该受控计划例外扩展到任何其它未跟踪或已修改文件。

### 1.3 已核验的声学事实

Python Track-S **已经包含机械增压器**，不是缺失该模块：

- `supercharger_whine_v4.py` 使用 `2.36:1` shaft phase；
- 存在 rotor/pressure family、gear/casing、sideband、intake transfer、boost attack/release 与 boost-history bypass；
- Stage K 用新 `blower` 替换旧 HEMI source 的 blower，并在公共 Pre-PTR EQ 与 Frozen PTR 前完成混合；
- Stage K Candidate v7 的 source 参数全部是 `C/synthetic/candidate_assumption`。

所以 Stage L 不应“再加一个更响的正弦增压器”。真正缺口是：

1. `blower` 虽存在，但 intake-radiated aero tone、gear/casing structure tone 与 HEMI 排气主体之间的职责仍不够清晰；
2. current blower-only acceleration 为约 `-16.425 LUFS`，exhaust-only 为约 `-21.337 LUFS`，blower 已高约 `4.91 dB`，证明“更响”没有自动产生 Hellcat 身份；
3. Stage K 继续使用通用 shift 层：整混音最低压到约 `0.22`，并加固定 recovery boom；
4. 正式 shift probe 在一次换挡中 throttle/load 仍约 `0.82/0.78`，没有 throttle `<0.25` 样本，因此 v4 的 throttle-close bypass 不会表达高负载换挡中的 boost/drive transient；
5. Stage K Hellcat `shift_or_transient` 为空，缺少车型专属的 torque-cut、boost inertia 和 re-engagement；
6. Stage K final-PCM reference-distance 平均改善只有 `4.2019%`，其中 idle `+19.20%`、acceleration `-6.20%`、afterfire `-0.40%`，未达到固定 `30%` 门禁。

### 1.4 Jovi 反馈的正式绑定方式

Jovi 本轮文字反馈为 Stage L 的权威具名输入：

```text
- Hellcat “猫叫”来自机械增压器和进气传播，不是排气；
- 当前 Hellcat 低频重量不足；
- 高频过于平滑，缺少顿挫轰鸣感；
- 希望结合发动机声浪机理重新判断是否需要 Simulink。
```

Stage K 包内存在两个同名 CSV，必须 fail closed 区分：

```text
顶层正式模板：
E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1\06_Feedback\Jovi_Stage_K_Named_Feedback.csv
SHA-256 = DE55EB154E05530F2905AA0CFC5C247EE7D6F81158119CB2A8FE2535E60F374E
24 rows / 0 filled rows

嵌套已填副本：
E:\Tesla_speed\review_packages\s12-stage-k-four-vehicle-perceptual-repair-v1\S12_Stage_K_Named_Review\06_Feedback\Jovi_Stage_K_Named_Feedback.csv
SHA-256 = 88F9636511233C04014B848BDC4A9C2CB49B188D23F964BBF3C337C1783FAF95
24 filled rows / 6 values equal 0
```

处理规则：

- 顶层空模板继续标记 `UNSUBMITTED_TEMPLATE`；
- 嵌套副本与 SHA256SUMS 所绑定模板不一致，并含合同外的 `0`，只能标记 `INVALID_UNBOUND_DIAGNOSTIC_COPY`；
- 不允许把嵌套副本直接喂给候选搜索、人耳评分、报告或 Profile Freeze；
- Luna 先把 Jovi 本轮文字反馈写入 hash-bound JSON；Stage L 新包再生成唯一的 1–5 合法 CSV；
- 不把这次文字反馈写成 Human PASS。

### 1.5 视频与在线证据边界

Jovi 提供的短链：

```text
https://v.douyin.com/GfkmfGAoqfs/
```

本计划阶段无法合法打开或定位该音轨，状态固定为：

```text
AUDIO_NOT_AVAILABLE
USER_TEXT_DESCRIPTION_AVAILABLE
```

Luna 执行时只允许再做一次非绕过式访问尝试。若仍不可用：记录 URL、时间、错误与 `NOT_AVAILABLE` 后继续；不得抓取私人 cookie、绕过登录、虚构字幕或声谱结论。若公开音轨可合法获得，只能写入：

```text
E:\Claude_allow\Download\s12-stage-l-reference\
```

仅可提取相对谱峰、order ridge、modulation 与瞬态摘要，并标记：

```text
R2/social-media-compressed
microphone/AGC dependent
not absolute loudness evidence
not OEM calibration
```

### 1.6 在线研究锚点

Stage L 可以使用的少数硬件/声学锚点：

- Hellcat 使用约 2.38 L twin-screw supercharger、`2.36:1` drive ratio、最高约 `14,600 rpm`、公开最大 boost 约 `11.6 psi / 80 kPa`；
- 高音调 whine 是 supercharger/intake-system source，与 exhaust roar 分属不同声源；
- supercharger noise 可由 aero pressure ripple 经 airbox/intake/plenum 路径传播，也可含 timing-gear/casing structure-borne tone；
- 四冲程 V8 合并后的主 firing component 是 4th engine order；
- 90° cross-plane V8 单侧 bank 的 blowdown 间隔为 `90° / 180° / 270° / 180°`；
- 这种不均匀 bank interval 与管路 junction/phase delay 会改变 blowdown interference 和尾管声质；
- roughness 应通过受控包络调制、shock-type combustion excitation 与结构/管路响应形成，不能通过白噪声或宽带高频增益伪造。

未知 rotor pocket 数、timing-gear 齿数、真实进气管传递函数、OEM SPL 不得猜成事实。相关参数只能是 `C/synthetic/candidate_assumption`。

研究来源矩阵：

| 主题 | 一手/权威来源 | Stage L 允许的用途 |
|---|---|---|
| Hellcat 2.38 L twin-screw、2.36:1、约 14,600 rpm、11.6 psi | [Stellantis Hellcat technical release](https://www.media.stellantis.com/me-en/dodge-archive/press/cat-out-of-hell-dodge-srt-introduces-the-most-powerful-suv-ever-2021-durango-srt-hellcat-in-the-u-s-market) | 锁定 architecture、ratio 与公开工作上限；不得把 boost 直接映射为绝对声压 |
| exhaust roar 与 supercharger whine 是不同声源 | [Dodge Black Ghost drive description](https://www.dodge.com/news/2023-challenger-black-ghost-drive.html) | 确立 intake/supercharger 与 exhaust 分层，不作绝对响度标定 |
| supercharger 是 intake acoustic source，声音经 airbox/duct/plenum 辐射 | [SAE 2017-01-1790](https://doi.org/10.4271/2017-01-1790) | 支持 `SC_AERO_PRESSURE_RIPPLE → intake transfer` 架构 |
| supercharger timing-gear whine 与 shaft modes/transmission error | [SAE 2007-01-2293](https://doi.org/10.4271/2007-01-2293) | 支持 gear/casing 独立 stem；未知齿数不得推断 |
| 90° V8 单 bank 的 90/180/270/180 blowdown interference | [SAE 2011-01-0337](https://doi.org/10.4271/2011-01-0337) | 锁定 bank event topology 与测试 |
| V8 junction phase delay 会改变 blowdown/exhaust sound | [SAE 1999-01-1651](https://doi.org/10.4271/1999-01-1651) | 支持有界 bank delay/cross-coupling，不声称真实排气几何 |
| engine roughness 与 shock-type crank/combustion excitation相关 | [SAE 440155](https://doi.org/10.4271/440155) | 支持 structure-shock 与 pressure-rise modulation，禁止白噪声替代 |
| roughness/tonality psychoacoustic 范围与计算边界 | [ECMA-418-2](https://www.ecma-international.org/wp-content/uploads/ECMA-418-2_2nd_edition_december_2022.pdf) | 辅助指标，不替代 Jovi 听感 |
| Simscape gas restriction/pipe 与 driveline backlash 能力边界 | [MathWorks Local Restriction (G)](https://www.mathworks.com/help/simscape/ref/localrestrictiong.html)、[Pipe (G)](https://www.mathworks.com/help/simscape/ref/pipeg.html)、[Gear with Backlash](https://www.mathworks.com/help/sdl/ug/gear-with-backlash.html) | 只用于未来 physical/productization 任务的范围判断 |

### 1.7 Stage L 的 Simulink 决策

**Stage L 不修改 MATLAB 或 Simulink。**

理由：

1. 反馈所指问题都可在 Python Track-S 的 source、transient 与 operating-state 层定位；
2. 当前自动参考门失败，正式有效反馈 CSV 未形成，Profile Freeze Candidate 与 Approved Profile 均不存在；
3. v6/v11/v12 模型没有引用 Stage K Candidate、Stage K stem schema/contract 或 Python `supercharger_whine_v4`；现在修改只会把未通过的人耳假设复制到另一套实现；
4. 现有 v6 虽已有 blowdown/combustion variation/exhaust network/induction 概念，但它与 Stage K final-PCM 管线不是等价实现；
5. Obsidian 当前权威顺序仍是：

```text
Python Realism
→ Automatic Qualification
→ Human Audition
→ Profile Freeze Review
→ Jovi Explicit Approval
→ Approved Profile
→ Simulink Productization
→ Runtime
→ Android / ESP32
```

现有模型能力必须按事实区分：

| 模型栈 | 已有能力 | Stage L 不能据此声称的内容 |
|---|---|---|
| v6 | 96 kHz MATLAB procedural layers、SLX harness、独立低频 Simscape 校准 plant | 不是完整 FVM/PTR，也不是 Stage K final-PCM 等价实现 |
| v11 | 8 模型 build/compile 和离线 90 秒音频证据 | 没有 90 秒 Simulink simulation 证据，也不是 Stage K 候选实现 |
| v12 | 三车型实际 Simulink runtime、90 秒重复性和 pre-PTR identity | `full_fvm_ptr_network=false`、R1=0、无 Stage K reference fit、人耳批准或 final-PCM 等价证据 |

未来产品化任务开始前必须先写 ADR：在 v6/v11/v12 中选择并 SHA-256 固定一个 canonical target。默认只允许评估 v12 作为候选骨架，v6/v11 仅作历史比较；ADR 未完成时状态为：

```text
BLOCKED / SIMULINK_CANONICAL_TARGET_UNSELECTED
```

本阶段最多生成一份 read-only `simulink_defer_decision.json`，不得写 `.m/.mlx/.slx/.sldd`，不得启动模型重建。

### 1.8 冻结边界

禁止修改：

- FVM、PTR core、Radiation Boundary；
- Runtime、Android、ESP32；
- MATLAB、Simulink、`.m/.mlx/.slx/.sldd`；
- Track-P guard、baseline、allowlist；
- `manage_bundle_loudness` 的接口、实现和正式 `-16 LUFS / -1.5 dBFS` 策略；
- 公共 LF Body、Exhaust Rumble、Pre-PTR EQ；
- Stage K Candidate v7、历史试听包及其字节；
- C63、GT-R、LFA 和另外四辆非目标车型；
- reference target 原始内容与固定 30% 公式。

禁止下载新参考音频、push、merge、rebase 或修改 main。

---

## Task 1 — Phase L0：独立工作树与证据冻结

### Task L0.1：Fail-closed 起点检查

执行：

```powershell
$stageK = 'E:\Tesla_speed\worktrees\s12-stage-k-four-vehicle-perceptual-repair'
git -C $stageK rev-parse HEAD
git -C $stageK branch --show-current
git -C $stageK status --porcelain=v1 --untracked-files=all
git -C $stageK rev-list --left-right --count origin/main...HEAD
git -C $stageK log -1 --format='%H %s'
```

预期：

```text
HEAD   = bf653c6f7a3779314d9891aaa801b29a4874db40
branch = agent/s12-stage-k-four-vehicle-perceptual-repair
status = 以下二者之一：
  A. empty
  B. 只有 `?? tasks/plans/2026-08-12-s12-stage-l-hellcat-intake-combustion-roughness-calibration.md`
ahead/behind = 0 56
```

如果状态为 B，Luna 只允许把本计划作为 docs-only bootstrap commit 提交，重新核验 clean 后再创建 Stage L worktree；该 commit 不得含任何其它文件。如果本计划已作为独立本地 docs commit 位于 `bf653c6...` 之后，只允许 `bf653c6...HEAD` 的 diff 恰好包含本计划文件，并以实际 docs commit 作为 Stage L worktree 起点。任何代码、模型或其它文档变化都视为：

```text
BLOCKED / BASELINE_DRIFT
```

不得 stash、reset、pull、clean 或覆盖。

### Task L0.2：建立独立 Stage L 工作树

从冻结的 Stage K code/evidence tip 建立：

```powershell
git -C E:\Tesla_speed\prj worktree add `
  -b agent/s12-stage-l-hellcat-intake-roughness-calibration `
  E:\Tesla_speed\worktrees\s12-stage-l-hellcat-intake-roughness-calibration `
  <actual-clean-tip-after-optional-plan-only-commit>
```

记录 `<actual-clean-tip-after-optional-plan-only-commit>` 的完整 SHA；禁止继续硬编码旧 tip。如果创建了 bootstrap commit，提交消息固定为：

```text
docs(s12): define Stage L Hellcat calibration plan
```

后续所有仓库修改只允许发生在新工作树。

### Task L0.3：冻结 Stage K 证据

至少记录以下现有 SHA-256：

```text
hellcat_candidate_v7.json
= B730090DAA6274C9E6501E9CDF6894EA00F8CCFFF535AF3F887EC00721D6D358

S12_Stage_K_Named_Review.zip
= D81BC9E77276BF6066C73BF3444239800067F1A1545F43460061C37BD88FDEEF

Stage K artifact_manifest.json
= 8A3831BC9FBD71C3A56D7FE85520683FBA9012C64EEF7B66C5D7789C7DAC1C79

stage_k_reference_distance.json
= 14D9E761C31F32FEA597C5F2049FAD3A59F7C4B6D79B81DC343A53DF133F72D4

supercharger_whine_v4.py
= F41CFBBC92CF54F59CEB0645A266FC6D9530233D236841490F9BA8890917F2A6

supercharged_hemi_source.py
= C0F8D8FD038BD8495B355BCD81A04E216F330E2F64A4415B4AD9090A2C3F5EDD
```

新增：

```text
tasks/plans/2026-08-12-s12-stage-l-hellcat-intake-combustion-roughness-calibration.md
tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_stage_k_evidence_receipt.json
tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_jovi_feedback_intake.json
tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_simulink_defer_decision.json
```

`stage_l_jovi_feedback_intake.json` 必须保存 Jovi 原始文字、消息时间、相关 Stage K package/candidate SHA、两个 CSV 的路径/SHA/合法性结论，并明确：

```text
human_pass = false
feedback_scope = named_engineering_direction
formal_stage_k_csv_status = UNSUBMITTED_TEMPLATE
nested_csv_status = INVALID_UNBOUND_DIAGNOSTIC_COPY
```

### Task L0.4：账本与计划提交

更新：

- `tasks/todo.md`：新增 L0–L9 清单；
- `tasks/lessons.md`：新增三条规则：
  - 增压器进气 whine 与排气低频 roar 必须分离建模和导出；
  - “更响”不能替代声学身份，stem LUFS 更高仍可能不像目标车型；
  - 同名反馈副本必须绑定 manifest/SHA 并通过范围校验，非法 `0` 不能解释为真实听感分数。

提交：

```powershell
git add tasks/plans/2026-08-12-s12-stage-l-hellcat-intake-combustion-roughness-calibration.md
git add tasks/todo.md tasks/lessons.md
git add tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_stage_k_evidence_receipt.json
git add tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_jovi_feedback_intake.json
git add tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/stage_l_simulink_defer_decision.json
git diff --cached --check
git commit -m "docs(s12): freeze Stage L Hellcat calibration inputs"
```

---

## Task 2 — Phase L1：Candidate 契约、共同曲轴时钟与 parent isolation

### 3.1 文件

新增：

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_l/__init__.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/candidate_profiles.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/crank_clock.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/feedback_intake.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/render_candidate.py
tools/sound_sim/s12/acoustic_identity_v015/targets/stage_l_hellcat_candidate.schema.json
tools/sound_sim/s12/acoustic_identity_v015/targets/stage_l_candidates/hellcat_candidate_v8.json
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_candidate_contract.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_crank_clock.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_feedback_intake.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_regression_isolation.py
```

### 3.2 公共接口

```python
def load_stage_l_candidate(
    path: str | Path,
) -> StageLCandidateProfile:
    ...
```

```python
@dataclass(frozen=True)
class HellcatCrankClock:
    engine_phase_cycles: np.ndarray
    cycle_phase_cycles: np.ndarray
    firing_event_gate: np.ndarray
    left_bank_event_gate: np.ndarray
    right_bank_event_gate: np.ndarray
    torque_ripple_envelope: np.ndarray
    event_sample_indices: tuple[int, ...]
    bank_labels: tuple[str, ...]
```

```python
def build_hellcat_crank_clock(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> HellcatCrankClock:
    ...
```

```python
@dataclass(frozen=True)
class StageLFeedbackReceipt:
    stage_k_package_sha256: str
    formal_template_sha256: str
    formal_template_status: str
    nested_copy_sha256: str
    nested_copy_status: str
    named_text_feedback_sha256: str
    feedback_scope: str
    human_pass: bool
```

```python
def inspect_stage_l_feedback_inputs(
    package_root: str | Path,
    named_text_feedback_path: str | Path,
) -> StageLFeedbackReceipt:
    ...
```

该接口必须允许“正式 CSV 尚未提交，但 hash-bound 文字反馈可作为工程方向”的状态；不得把文字反馈升级成人耳评分。若调用方试图把嵌套非法副本作为正式 CSV，必须失败。

```python
def render_stage_l_parent(
    trace: VehicleStateTrace,
) -> SourceRender:
    ...
```

```python
def render_stage_l_candidate(
    trace: VehicleStateTrace,
    candidate: StageLCandidateProfile,
) -> SourceRender:
    ...
```

不提供含糊的 `candidate=None` 多车型语义。`render_stage_l_parent` 必须显式渲染 hash-bound Stage K Hellcat v7；Stage L candidate 只支持 `hellcat`。其它七车不接入 Stage L 路由，以 SHA regression 证明未变。

### 3.3 Candidate v8 顶层契约

exact-key：

```text
schema_version = s12-stage-l-hellcat-candidate-profile-1
candidate_id
vehicle_id = hellcat
base_commit = bf653c6f7a3779314d9891aaa801b29a4874db40
parent_candidate_id = hellcat_stage_k_v7
parent_candidate_path
parent_candidate_sha256 = b730090d...
status = Candidate
hypothesis
reference_target
feedback_receipt
crank_clock
combustion_and_blowdown
supercharger_intake
shift_and_load_transient
operating_level
afterfire
loudness
locked_layers
provenance
```

每个可调参数继续使用：

```json
{
  "value": 0.0,
  "unit": "",
  "range": [0.0, 1.0],
  "source_level": "C",
  "source": "synthetic",
  "source_scope": "",
  "verification_state": "candidate_assumption"
}
```

硬件锚点可在 `provenance.official_facts` 记录，但不得把 B/R2 或官方硬件事实升级为合成音色参数的 provenance。

### 3.4 固定管线

```text
VehicleStateTrace
→ One Shared Hellcat Crank Clock
→ Cross-Plane Combustion/Blowdown Source
→ Twin-Screw Intake/Case Source
→ Existing State Spectral Targets Applied Once to the Combined Source
→ Source Operating Trim
→ Idle Dynamics
→ Deterministic Afterfire
→ Frozen Common LF Body
→ Frozen Exhaust Rumble
→ Hellcat Shift/Load Transient
→ Hellcat Named Peak Budget
→ Frozen Common Pre-PTR EQ
→ Frozen PTR
→ Edge Fade
→ One Whole-Cycle Gain
→ PCM24
```

新增能量不得位于 Frozen PTR 之后。

Stage L 必须调用 `render_hellcat(..., apply_state_shaping=False)` 或等价的 raw-source 路径，只取得未做 state-band shaping 的历史 HEMI 组件；将新 combustion/blowdown 与新 supercharger intake 组合后，才允许复用现有 `state_band_shaper` **一次**。禁止先塑形旧 HEMI、再替入未塑形 blower，也禁止修改 state-band target、公共 shaper 算法或 reference target。

在调用 shaper 前必须建立显式 contributor contract：

```python
diagnostics["pressure_stem_contract"] = {
    "contributors": [...],          # 只含逐样本参与 pressure 求和的 primitive stems
    "diagnostic_aggregates": [...], # blower/exhaust 等只读聚合，不参与 pressure 求和
}
```

执行顺序必须是：只把 `contributors` 交给一次 state shaping → 由塑形后的 primitive stems 重新求和得到 pressure → 从已塑形 primitives 重建 diagnostic aggregates。禁止将 aggregate 与其 children 一起塑形、一起 trim 或一起累加；必须测试 `pressure == sum(contributors)`、aggregate identity、无重复增益和无双重 state shaping。

### 3.5 RED 测试

- 未知字段、错误车型、错误 parent id/path/SHA、错误 base commit 失败；
- range 非严格升序、value 越界、NaN/Inf 失败；
- `status != Candidate` 失败；
- 未知 rotor pocket count/timing gear tooth count 若伪装成 official fact 失败；
- 顶层空模板返回 `UNSUBMITTED_TEMPLATE`，嵌套 `88f9...` 副本因 SHA 漂移与 `0` 分返回 `INVALID_UNBOUND_DIAGNOSTIC_COPY`；
- feedback receipt 必须绑定 Stage K package/template/nested copy/文字反馈 SHA，且 `human_pass=false`；
- Stage K v7 parent 对同一 trace 的 pressure/stems/diagnostics SHA 与冻结值一致；
- contributor contract exact-key 且覆盖每个 pressure primitive；aggregate 与 contributor 集合严格不相交；
- state shaper 每次渲染恰好调用一次，且只接收 contributors；塑形后重建 aggregate，pressure accounting 逐样本误差 `<=1e-12`；
- Ferrari、RX-7、Aventador、Supra、C63、GT-R、LFA 现有正式路径 PCM SHA 均不变；
- 相同 trace、profile、`PYTHONHASHSEED` 变化时 Stage L 输出一致；
- 每个公开参数必须分别证明 `read/configured/active|inactive/unused`，不得用 JSON 存在推断 active；
- 先运行并观察 Stage L 模块缺失造成 RED。

### 3.6 GREEN 与提交

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_candidate_contract.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_crank_clock.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_feedback_intake.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_regression_isolation.py -q
git diff --check
git add <本任务明确文件>
git commit -m "test(s12): define Stage L Hellcat source contracts"
```

---

## Task 3 — Phase L2：Cross-Plane HEMI 非正弦燃烧与低频压力源

### 4.1 文件与接口

新增：

```text
tools/sound_sim/s12/acoustic_identity_v015/sources/hellcat_crossplane_combustion_v2.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_crossplane_combustion.py
```

```python
def render_hellcat_crossplane_combustion_v2(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: HellcatCrankClock,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    ...
```

### 4.2 固定结构

```text
shared crank clock
→ firing order 1-8-4-3-6-5-7-2
→ bank-specific 90/180/270/180° event schedule
→ non-sinusoidal blowdown pulse kernel
→ deterministic cylinder-strength pattern
→ load-dependent combustion pressure-rise envelope
→ bank-specific delay/phase response
→ X-pipe-style coherent mixing
→ exhaust-source + structure-shock source
```

新 pressure-contributing stems：

```text
hemi_exhaust_left
hemi_exhaust_right
hemi_blowdown_body
hemi_structure_shock
hemi_mechanical_torque_ripple
```

诊断 aggregates 不得再次进入 pressure 求和。

### 4.3 Candidate v8 初始搜索边界

全部为 C 级合成范围，不是 OEM 实测：

```text
cylinder_strength_variation       0.06 … 0.20 ratio
bank_amplitude_asymmetry           0.00 … 0.12 ratio
blowdown_attack_ms                 0.20 … 0.80 ms
blowdown_fast_decay_ms             1.2 … 3.0 ms
blowdown_slow_decay_ms             4.0 … 10.0 ms
blowdown_slow_weight               0.15 … 0.45 ratio
low_frequency_blowdown_gain        0.95 … 1.35 ratio
structure_shock_mix                0.04 … 0.18 ratio
torque_ripple_modulation_depth     0.05 … 0.20 ratio
xpipe_cross_coupling               0.05 … 0.25 ratio
xpipe_delay_ms                     0.10 … 1.50 ms
```

禁止：

- 白噪声、随机 crackle、宽带高频 gain；
- 为了“顿挫”改变 RPM trace；
- 把整车速度作为 source gain；
- 修改公共 LF Body/Rumble；
- 将单侧 bank 不均匀间隔错误写成整机总体不均匀点火。

### 4.4 RED 测试

- firing event 相对理论曲轴角误差不超过 1 个音频采样；
- 合并整机主 firing ridge 跟随 4EO；
- 每一 bank 的 interval multiset 与 `90/180/270/180°` 等价，归一比为 `1:2:3:2`；
- 变 RPM 只连续移动事件频率，不丢失事件数或改变 firing order；
- `cylinder_strength_variation=0` 时周期内各缸幅度一致；非零时模式确定、bounded、跨进程一致；
- blowdown 参数分别只改变 attack、fast/slow decay 或能量权重；
- 低频增强来自 event-driven pressure pulse，不是静态 low shelf；
- high-load `80–250 Hz` pulse RMS/crest 相对 Stage K parent 增加，但 final-PCM 20–250 Hz reference abs-error 不得扩大；
- `250–1000 Hz` body share 朝现有 B/R2 target 移动，不允许通过高 Q 单频共振过门；
- 4–12 kHz share 不因低频修复增加超过 `0.005`；
- pressure 精确等于 pressure-contributing stems 的逐样本和；
- 每参数 perturbation 有目标输出差异，非目标 stems 不变。

### 4.5 GREEN 与提交

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_crossplane_combustion.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_k_hellcat_whine_v4.py -q
git diff --check
git add <本任务明确文件>
git commit -m "feat(s12): model Hellcat cross-plane blowdown and torque roughness"
```

---

## Task 4 — Phase L3：机械增压进气/壳体 v5 重建

### 5.1 文件与接口

新增：

```text
tools/sound_sim/s12/acoustic_identity_v015/sources/hellcat_supercharger_intake_v5.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_supercharger_intake.py
```

```python
def render_hellcat_supercharger_intake_v5(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: HellcatCrankClock,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    ...
```

### 5.2 职责分离

固定分为：

```text
SC_AERO_PRESSURE_RIPPLE
→ twin-screw pocket/pressure family
→ intake duct/plenum transfer
→ sc_intake_radiated

SC_TIMING_GEAR_CASE
→ shaft/gear transmission-error family
→ torque-ripple modulation
→ casing transfer
→ sc_casing_radiated

SC_BYPASS
→ boost history + throttle/load/shift state
→ bypass release
```

新 stems：

```text
sc_aero_raw                 # diagnostic only
sc_gear_raw                 # diagnostic only
sc_intake_radiated          # pressure contributor
sc_casing_radiated          # pressure contributor
sc_bypass_release           # pressure contributor
supercharger_intake         # diagnostic aggregate only
```

`supercharger_intake` 必须逐样本等于三个 pressure contributors 之和，但不得再被重复加到 pressure。

### 5.3 物理与合成参数

固定官方锚点：

```text
shaft speed ratio = 2.36
published maximum shaft rpm ≈ 14,600 (rounded public figure; informational tolerance only)
published maximum boost ≈ 11.6 psi / 80 kPa (hardware context only; not an SPL or amplitude calibration)
```

候选参数全部 C/synthetic：

```text
aero_family_order_ratio         4.0 … 7.0 per shaft revolution
aero_harmonic_mix               0.10 … 0.40
aero_cluster_spread_ratio       0.010 … 0.030
gear_family_order_ratio         6.0 … 18.0 per shaft revolution
gear_to_aero_ratio              0.04 … 0.20
torque_ripple_to_gear_depth     0.04 … 0.18
intake_transfer_mix             0.20 … 0.55
casing_transfer_mix             0.05 … 0.25
boost_attack_10_90_s            0.06 … 0.14 s
boost_release_90_10_s           0.18 … 0.40 s
bypass_release_gain             0.00 … 0.18
bypass_decay_90_10_s            0.08 … 0.30 s
```

`aero_family_order_ratio` 和 `gear_family_order_ratio` 只是 feature-count design variables；报告不得称其为 Hellcat rotor lobe count 或 gear tooth count。

### 5.4 RED 测试

- shaft phase/rpm 严格为 `2.36 × engine`，不得为了贴合公开约数而 clamp 或扭曲 canonical trace；
- 专用 `800–6100 rpm` hardware-anchor sweep 的 shaft speed 必须 `<=14,600 rpm`；现有 6200 rpm canonical trace 对应 `14,632 rpm`，只记录为相对公开约数约 `+0.22%` 的信息项，不作为失败门；
- aero/gear family 从 shaft phase 派生，不能由固定 Hz tone 产生；
- 同 load/boost 不同 RPM 时 ridge 连续移动；同 RPM 不同 load 时频率基本不变、幅度改变；
- `sc_intake_radiated` 是 cat-call 主路径，exhaust stems 不含 supercharger order；
- gear/casing 与 aero/intake 能分别静音并保持其它路径字节不变；
- torque ripple 只调制 gear/casing，不把 cross-plane roughness复制为宽带噪声；
- boost attack/release 参数改变实测 10–90/90–10 时间；
- bypass 必须依赖 boost history；无历史 boost 时严格为零；
- 高负载换挡即使 throttle 未低于 0.25，也可由显式 shift torque state 产生 drive/load transient，但不得伪装成 throttle-close bypass；
- `supercharger_intake == sc_intake_radiated + sc_casing_radiated + sc_bypass_release`；
- pressure 不得重复计算 aggregate；
- 不调用 `np.random`、white noise、随机 crackle；
- 每个公开参数逐项 perturbation 可达；
- 4–12 kHz final-PCM share `<=0.06`，不以宽带高频增益获得 whine。

### 5.5 GREEN 与提交

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_supercharger_intake.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_k_hellcat_whine_v4.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_hellcat_whine_model.py -q
git diff --check
git add <本任务明确文件>
git commit -m "feat(s12): separate Hellcat intake whine from exhaust roar"
```

---

## Task 5 — Phase L4：Hellcat 专属 shift/load transient 与峰值预算

### 6.1 文件与接口

新增：

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_l/hellcat_transient_dynamics.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/hellcat_peak_budget.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_transients.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_peak_budget.py
```

```python
def apply_hellcat_transient_dynamics(
    render: SourceRender,
    trace: VehicleStateTrace,
    candidate: StageLCandidateProfile,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    ...
```

```python
def apply_hellcat_named_peak_budget(
    render: SourceRender,
    trace: VehicleStateTrace,
    candidate: StageLCandidateProfile,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    ...
```

### 6.2 换挡结构

Stage L Hellcat 不调用通用 `apply_shift_dynamics`。继续复用 `detect_shift_events`，但独立处理：

```text
HEMI source
→ torque-cut envelope
→ exhaust pressure短时下陷
→ re-engagement combustion pulse

Supercharger source
→ shaft pitch仍跟随RPM
→ boost state按惯性保留
→ drive torque modulation / casing transient
→ 无条件禁止固定70Hz recovery sine
```

新 stems：

```text
hellcat_shift_torque_cut
hellcat_shift_reengagement
hellcat_sc_drive_transient
hellcat_tip_in_blowdown
```

初始 C 级范围：

```text
shift_interruption_s            0.08 … 0.20 s
shift_min_exhaust_gain          0.40 … 0.70
shift_min_sc_gain               0.70 … 0.95
reengagement_decay_s            0.06 … 0.20 s
sc_drive_modulation_depth       0.04 … 0.16
tip_in_blowdown_gain            0.04 … 0.18
```

### 6.3 Named peak budget

只允许处理短时具名 stems：

```text
afterfire
hellcat_shift_reengagement
hellcat_sc_drive_transient
hellcat_tip_in_blowdown
```

禁止压缩 steady exhaust、supercharger intake、LF body、rumble 或 whole pressure。处理后以 before/after stem 差值精确回写 pressure。

目的不是降低响度，而是削掉偶发孤立峰值，为 sustained HEMI body 和试听静态增益释放 headroom。`manage_bundle_loudness` 保持完全不变。

### 6.4 RED 测试

- canonical 60 秒 trace 的 3 次 shift 均被识别；
- monotonic lift 不误判 shift；
- exhaust dip、SC dip 和 boost inertia 分别可测，不再统一下压到 0.22；
- shift dip 目标 `2–5 dB`，settling `0.10–0.30 s`，overshoot `<=1.5 dB`；
- sustained throttle shift 不触发 throttle-close bypass，但可触发 `hellcat_sc_drive_transient`；
- 无 shift 时全部 shift stems 为零；
- 不生成固定 70 Hz recovery boom；
- 具名 peak budget 对 steady stems bit-identical；
- pressure 差值严格等于四个处理 stem 的差值和；
- final PCM peak `<=-1.5 dBFS`、clipping `=0`；
- whole-cycle candidate LUFS 相对 Stage K parent 不降低超过 `0.5 LU`；
- formal A/B 公平副本不得用 limiter/compressor；
- candidate-only comfort copy 若有足够 headroom，可静态增加最多 `+1.9382 dB`，不足时必须记录 actual gain 与 `headroom_limited=true`，不得削波硬加。

### 6.5 GREEN 与提交

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_transients.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_peak_budget.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_k_source_level.py -q
git diff --check
git add <本任务明确文件>
git commit -m "fix(s12): rebuild Hellcat load and shift acoustic transients"
```

---

## Task 6 — Phase L5：指标、最终 PCM 参考距离与有界搜索

### 7.1 文件

新增：

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_l/perceptual_metrics.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/reference_distance.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/candidate_search.py
tools/sound_sim/s12/acoustic_identity_v015/scripts/qualify_stage_l_hellcat.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_perceptual_metrics.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_reference_distance.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_candidate_search.py
```

### 7.2 严格区分三个测量域

```text
source-domain:
event timing、shaft phase、stem identity、pressure accounting

pre-PTR:
layer order、source mixing、named transient、parameter reachability

final PCM24:
band shares、reference-distance、LUFS、peak、clipping、试听 artifact
```

不得把 source-domain float pressure 标成 `final_pcm_health`。

### 7.3 Hellcat 专属指标

机械增压/进气：

```text
shaft_ratio_error
shaft_max_rpm
intake_whine_load_correlation
intake_to_exhaust_ratio_db
gear_to_aero_ratio
intake_transfer_energy_ratio
bypass_event_count
boost_attack_10_90_s
boost_release_90_10_s
bypass_decay_90_10_s
order_ridge_continuity
tone_prominence_ratio
```

HEMI/blowdown：

```text
firing_event_angle_error_samples
bank_interval_pattern_error
fourth_order_presence
20_80_hz_share
80_160_hz_share
160_250_hz_share
250_1000_hz_share
low_band_pulse_crest_db
low_band_envelope_cv
fluctuation_below_20_hz
roughness_20_300_hz
modulation_peak_hz
bank_to_bank_delay
```

瞬态与数字健康：

```text
shift_dip_db
shift_settling_s
shift_overshoot_db
review_requested_gain_db
review_actual_gain_db
headroom_limited
final_pcm_lufs
final_pcm_peak_dbfs
clipping_count
```

### 7.4 低频听感与 B/R2 reference 冲突的处理

现有 Hellcat acceleration target/Stage K 频带份额为：

```text
20–250 Hz target 0.4069 / Stage K 0.6023
250–1000 Hz target 0.5005 / Stage K 0.2263
1–4 kHz target 0.0611 / Stage K 0.1670
4–12 kHz target 0.0313 / Stage K 0.0044
```

Jovi 听到“低频不足”不能被简单翻译为再提高 20–250 Hz share。Stage L 应优先修：

- 80–250 Hz 非正弦 pulse crest 与时域密度；
- 250–1000 Hz exhaust/body 传播与 bank modulation；
- isolated peak 导致的 whole-cycle headroom；
- intake whine 与 exhaust body 的动态遮蔽。

自动门要求 20–250 Hz reference abs-error 不得扩大，250–1000 Hz error 必须缩小；不得用低架 EQ 投机。

### 7.5 固定 reference-distance

继续使用 final PCM、同一 trace、同一窗口、同一 extractor：

```text
idle          0–8 s
acceleration  8–26 s
afterfire     36–46 s
```

四频段：

```text
20–250 Hz
250–1000 Hz
1–4 kHz
4–12 kHz
```

公式禁止修改：

```text
D = sqrt(0.25 × Σ(actual_share - target_share)^2)
improvement = (D_stage_k - D_stage_l) / max(D_stage_k, 1e-12)
```

正式自动门：

- eligible states 平均改善 `>=30%`；
- 任一 state 不得比 Stage K 恶化超过 `10%`；
- 缺失状态输出 `N/A`；
- 不比较 reference LUFS/RMS；
- Stage C identity distance 不得退化超过 `10%`；
- 4–12 kHz final share `<=0.06`；
- Track-P 与七车 isolation 必须通过。

### 7.6 感知辅助门

以下是候选筛选辅助门，不替代 30% reference 门或人耳：

- per-bank interval pattern error `<=1 audio sample`；
- SC shaft ratio error `<=1%`；`800–6100 rpm` anchor sweep 的 max shaft rpm `<=14,600`，6200 rpm canonical trace 的 `14,632 rpm` 仅作 rounded-public-figure consistency 信息项，不得 clamp；
- whine/load correlation `>=0.82`；
- high-load intake/exhaust ratio相对 Stage K 在有界网格内可区分，但不固定成 OEM dB；
- high-load low-band pulse crest 相对 Stage K 提升 `1–3 dB`；
- 250–1000 Hz acceleration abs-error 缩小；
- 20–300 Hz roughness 相对 Stage K 增加 `10–35%`，但 4–12 kHz share 增量 `<=0.01`；
- steady high-load 不出现单样本 click；
- repeated SHA deterministic。

### 7.7 有界搜索

只使用 8–12 秒 probes；一次只保留一个完整 `SourceRender`：

```text
1. exact contract / parameter reachability
2. source-domain physics gates
3. final PCM health
4. no state regression >10%
5. 30% reference-distance
6. vehicle-specific perceptual error
7. minimum parent parameter delta
8. lexical tie-break
```

不得用高频 gain、全局 gain、公共 EQ、阈值降低或公式修改选择候选。

### 7.8 RED/GREEN 与提交

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_perceptual_metrics.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_reference_distance.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_candidate_search.py -q
python tools/sound_sim/s12/acoustic_identity_v015/scripts/qualify_stage_l_hellcat.py --help
git diff --check
git add <本任务明确文件>
git commit -m "feat(s12): qualify Hellcat intake and cross-plane roughness"
```

---

## Task 7 — Phase L6：具名 Hellcat 试听包与反馈合同

### 8.1 文件

新增：

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_l/named_review.py
tools/sound_sim/s12/acoustic_identity_v015/stage_l/feedback_contract.py
tools/sound_sim/s12/acoustic_identity_v015/scripts/build_stage_l_named_review.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_named_review.py
tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_feedback_contract.py
```

### 8.2 外部输出

```text
E:\Tesla_speed\review_packages\s12-stage-l-hellcat-intake-roughness-v1\
├── 00_OPEN_ME_FIRST.md
├── 01_Formal_Comparison\
│   ├── 01_StageK_Parent_60s.wav
│   ├── 02_StageL_Candidate_60s.wav
│   └── 03_StageL_Candidate_Comfort_60s.wav
├── 02_Source_Separation\
│   ├── 01_SC_Intake_Aero_Acceleration.wav
│   ├── 02_SC_Gear_Casing_Acceleration.wav
│   ├── 03_HEMI_Exhaust_Body_Acceleration.wav
│   ├── 04_HEMI_Structure_Shock_Acceleration.wav
│   └── 05_Full_Mix_Acceleration.wav
├── 03_State_Review\
│   ├── 01_Idle_12s.wav
│   ├── 02_Low_Load_12s.wav
│   ├── 03_High_Load_12s.wav
│   ├── 04_Shift_12s.wav
│   └── 05_Lift_Bypass_12s.wav
├── 04_Metrics\
│   ├── order_map.png
│   ├── intake_vs_exhaust_spectrogram.png
│   ├── bank_event_timeline.png
│   ├── modulation_spectrum.png
│   ├── shift_response.png
│   └── stage_l_hellcat_metrics.json
├── 05_Feedback\
│   └── Jovi_Stage_L_Hellcat_Feedback.csv
├── artifact_manifest.json
├── SHA256SUMS.txt
└── S12_Stage_L_Hellcat_Named_Review.zip
```

### 8.3 60 秒时间线

```text
0–8 s     idle
8–26 s    acceleration + 3 shifts
26–36 s   full pull
36–46 s   lift / afterfire / bypass
46–52 s   coast
52–60 s   idle return
```

Stage K parent 和 Stage L candidate 使用相同 trace。Parent WAV 冻结后续轮次复用字节。

### 8.4 响度与 1.25x 请求

正式 A/B：

- parent/candidate 使用同一静态公平 gain；
- 不用 compressor、limiter、EQ、per-section AGC；
- 由于 Stage K parent 已接近 `-1.5 dBFS`，共同 gain 很可能被限制为约 0 dB；必须如实记录，不能伪称已经 1.25x。

单独的 `Candidate_Comfort_60s.wav`：

- 不是 A/B 资格音频；
- 只在 Stage L candidate 自身具备 headroom 时静态增加最多 `+1.9382 dB`；
- peak `<=-1.5 dBFS`、clipping `=0`；
- 若不足，降低 actual gain 并写 `headroom_limited=true`；
- 不修改正式产品 PCM 或候选 profile。

manifest 对每个文件记录：

```text
requested_gain_db
actual_gain_db
headroom_limited
raw_lufs
final_lufs
raw_peak_dbfs
final_peak_dbfs
pcm_sha256
source/profile/trace binding
```

### 8.5 反馈 CSV

预填 exact rows/file IDs，评分必须 `1–5`：

```text
package_id
listener_id
file_id
vehicle_id
supercharger_intake_likeness_1_5
whine_presence_1_5
whine_naturalness_1_5
low_frequency_weight_1_5
crossplane_pulse_naturalness_1_5
roughness_naturalness_1_5
shift_naturalness_1_5
high_frequency_harshness_1_5
loudness_balance_1_5
artifact_freedom_1_5
keep_or_change
notes
```

规则：

- 所有数值必须为整数 `1–5`，`0` 立即失败；
- `keep_or_change` 只能 `keep/change`；
- file_id/vehicle_id/package_id 必须完整且唯一；
- feedback 文件 SHA 固化后才允许评分/迭代；
- 不接受包内嵌套或重名副本，必须显式指定 canonical path。

### 8.6 包状态

自动门全部通过：

```text
WAITING_FOR_JOVI_STAGE_L_NAMED_REVIEW
```

任一自动门失败：

```text
PARTIAL / AUTOMATED_GATE_FAIL
UNQUALIFIED_DIAGNOSTIC_ONLY
DIAGNOSTIC_FEEDBACK_ALLOWED
```

两种状态都不得写 Human PASS。若是诊断包，README、ZIP 名、manifest 和报告都必须明确 unqualified。

### 8.7 测试与提交

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_named_review.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_feedback_contract.py -q
python tools/sound_sim/s12/acoustic_identity_v015/scripts/build_stage_l_named_review.py --help
git diff --check
git add <本任务明确文件>
git commit -m "feat(s12): publish Stage L Hellcat named calibration package"
```

完成后第一次硬停止，不读取或推断未提交反馈。

---

## Task 8 — Phase L7：Jovi 反馈后的最多三轮闭环

候选版本：

```text
hellcat_candidate_v8
→ hellcat_candidate_v9
→ hellcat_candidate_v10
```

每轮：

1. 固化 canonical feedback CSV SHA；
2. 校验全部行、1–5 范围、keep/change 与 notes；
3. 一次只修改一个明确失败的 source/transient family；
4. Stage K parent WAV 字节不变；
5. 其它七车 PCM SHA 不变；
6. 新增 candidate 版本，不覆盖旧版；
7. 重跑 focused、reference-distance、完整 S12、Track-P；
8. 生成新包和新 SHA，不覆盖旧包；
9. 保存 Jovi 原始评价，不润色成 PASS。

反馈映射：

- “whine不像/不从进气出来”：只动 `SC_AERO_PRESSURE_RIPPLE` 与 intake transfer；
- “太电子/太尖”：降低 gear/aero ratio、ridge concentration 或 casing Q，不削弱 HEMI body；
- “低频仍不够”：只动 event-driven blowdown/structure pulse、250–1000 Hz body 与 isolated peak budget，不改公共 LF EQ；
- “高频仍太平滑”：增加 torque-ripple modulation 或 bank-event AM，禁止宽带高频 gain；
- “太抖/太假”：降低 cylinder strength CV、structure shock 或 gear torque modulation；
- “换挡不对”：只动 Hellcat transient，不能改 crank clock、PTR 或 whole gain；
- “声音仍小”：只优化具名 transient peak budget与 candidate comfort copy；不得修改 loudness manager 或削波硬增益。

三轮后仍未同时满足自动和具名听感目标：

```text
PARTIAL / HUMAN_AUDITION_FAIL
```

不得降低阈值或进入 Simulink。

具名工程目标：

```text
supercharger_intake_likeness >= 4
whine_presence >= 4
whine_naturalness >= 4
low_frequency_weight >= 4
crossplane_pulse_naturalness >= 4
roughness_naturalness >= 4
shift_naturalness >= 4
high_frequency_harshness <= 2
artifact_freedom >= 4
Candidate = keep 或明确优于 Stage K parent
```

即使上述通过，也只允许进入后续正式匿名人耳任务，不得直接 Approved。

---

## Task 9 — Phase L8：Simulink 延后门与未来产品化触发条件

Stage L 必须验证：

```powershell
$base = 'bf653c6f7a3779314d9891aaa801b29a4874db40'
$protectedRoots = @(
  'tools/sound_sim/matlab/',
  'simulink/',
  'tools/sound_sim/s12/acoustic_identity_v010/playground/',
  'tools/sound_sim/s12/acoustic_identity_v011/playground/',
  'tools/sound_sim/s12/acoustic_identity_v012/playground/'
)
$protectedExt = @('.m', '.mlx', '.slx', '.sldd', '.mdl')

$committed = git diff --name-only "$base..HEAD"
$working = git status --porcelain=v1 --untracked-files=all |
  ForEach-Object { $_.Substring(3) }
$changed = @($committed + $working | Sort-Object -Unique)
$violations = $changed | Where-Object {
  $path = ($_ -replace '\\', '/')
  ($protectedRoots | Where-Object { $path.StartsWith($_) }).Count -gt 0 -or
  $protectedExt -contains [IO.Path]::GetExtension($path).ToLowerInvariant()
}
if ($violations) {
  $violations
  throw 'BLOCKED / SIMULINK_BOUNDARY_VIOLATION'
}
```

该检查同时覆盖 committed、staged、unstaged 和 untracked；并保护 `.m/.mlx/.slx/.sldd/.mdl`、Simulink builder、profile JSON 和各版本 playground。预期无输出。任何命中：

```text
BLOCKED / SIMULINK_BOUNDARY_VIOLATION
```

未来另立 `Hellcat Approved Track-S → Simulink Productization` 任务，必须同时满足：

1. Stage L final-PCM 自动门 `>=30%` 且任一 state 不恶化 `>10%`；
2. Jovi 完整具名反馈及播放环境证据；
3. 正式匿名人耳门通过；
4. Profile Freeze Review 通过；
5. Jovi 对 exact candidate/profile SHA 明确批准；
6. 先完成 canonical-target ADR，记录选定 v6/v11/v12 模型栈、模型文件 SHA、builder SHA、模型消费 JSON SHA；未选择即 `BLOCKED / SIMULINK_CANONICAL_TARGET_UNSELECTED`；
7. 生成 `ApprovedProfile.sldd` 后不能只检查文件存在。批准回执必须同时绑定：SLDD SHA、Stage L candidate/profile SHA、映射 schema SHA、Jovi 批准记录 SHA、reference target/source SHA、冻结 Radiation SHA、选定 canonical model/builder/profile JSON SHA；任一缺失或漂移即 `BLOCKED / APPROVED_PROFILE_BINDING_INVALID`；
8. 新独立 worktree 中建立 Python→Simulink 参数/stem 映射；
9. 不修改 FVM/PTR/Radiation；
10. Track-P、candidate/parent/reference SHA、Radiation SHA 任一漂移立即停止；
11. 在实现前冻结 `Python_Simulink_Equivalence_Contract_v1`，至少包含：canonical trace 与状态窗口、48 kHz/通道/PCM 规格、输入采样和保持规则、初相位与 cold-load/reset 语义、事件对齐方式、允许的 sample latency、source/stem/pressure shape、幅度/相位/order/band-distance 数值容差、repeatability SHA/容差、final-PCM loudness/peak/clipping 门禁；缺失即 `BLOCKED / EQUIVALENCE_CONTRACT_MISSING`；
12. 完成 build/compile/simulation，并严格按该契约验证 Python↔Simulink source/stem/final-PCM 等价、cold-load/reset、repeatability 与 PCM health；v12 旧 runtime 证据只能复用基础设施，不能替代 Stage L 等价证明；
13. 只有产品化等价通过后才可另立 Runtime/Android / ESP32 任务。

现有 v6/v11/v12 可作为历史设计参考，不能作为 Stage L 已产品化证据。

---

## Task 10 — Phase L9：完整验证、报告、Obsidian 与本地提交

### 11.1 最终测试

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_candidate_contract.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_crank_clock.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_feedback_intake.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_crossplane_combustion.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_supercharger_intake.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_hellcat_transients.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_peak_budget.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_perceptual_metrics.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_reference_distance.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_candidate_search.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_named_review.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_feedback_contract.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_l_regression_isolation.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_k_hellcat_whine_v4.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_k_protected_boundaries.py -q
python -m pytest tools/sound_sim/s12/tests/test_s12_engine_acoustic_realism_v10.py -q
python -m pytest tools/sound_sim/s12/tests/test_s12_engine_acoustic_identity_v015.py -q
python -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q
python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py
git diff --check
git status --short
```

必须记录本轮实际数量与耗时，不复用 Stage K 历史数字。

### 11.2 冻结检查

```text
Track-P pytest = 21/21
Track-P guard = 180 frozen files / 2 symbols unchanged
loudness_manager.py SHA-256 = 26feb740842a1e4db93e0a83fd7924c17c1ee5cfb8d1737a304af83e3e163fd3
Stage K Candidate/package bytes unchanged
七辆非目标车型 PCM SHA unchanged
MATLAB/Simulink diff = empty
```

任一失败立即停止，不 rebaseline、不改 allowlist。

### 11.3 仓库报告

```text
tasks/reports/runtime/s12-stage-l-hellcat-calibration-v1/
├── S12_Stage_L_Hellcat_Intake_and_Roughness_Report.md
├── stage_l_stage_k_evidence_receipt.json
├── stage_l_jovi_feedback_intake.json
├── stage_l_online_reference_matrix.json
├── stage_l_simulink_defer_decision.json
├── stage_l_parameter_reachability.json
├── stage_l_source_domain_metrics.json
├── stage_l_final_pcm_metrics.json
├── stage_l_reference_distance.json
├── stage_l_loudness_and_headroom.json
├── stage_l_named_feedback_summary.json
├── stage_l_test_evidence.json
└── stage_l_artifact_manifest.json
```

首次生成包时 `stage_l_named_feedback_summary.json` 只能写：

```text
NOT_PERFORMED / WAITING_FOR_JOVI
```

### 11.4 Obsidian

新增：

```text
tesla\S12-Engine-Sound-v11\22-S12-Stage-L-Hellcat进气增压与Cross-Plane顿挫校准.md
```

更新：

- 项目概览；
- 总体计划；
- 当前进度；
- 工作流与知识；
- 12 号技术事实；
- 21 号 Stage K 历史页；
- Hellcat 车型卡；
- `tesla/index.md`。

必须记录：

- Stage K 已经有 mechanical supercharger，Stage L 修的是身份/传播/瞬态而不是“从零补模块”；
- cat-call 主路径是 supercharger/intake/casing，不是 exhaust；
- 低频 roar 与顿挫来自 HEMI combustion/blowdown/exhaust/structure；
- 抖音音轨是否实际可用；
- 顶层空 CSV 与非法嵌套副本的证据状态；
- Stage L 没有修改 MATLAB/Simulink；
- 当前 branch/HEAD、candidate/package SHA、测试与停止状态。

验证 YAML、内部链接、唯一 current status、更新前后 SHA。不得写 Human PASS、Approved、OEM reproduction 或 calibrated。

### 11.5 本地提交顺序

```text
1. docs(s12): freeze Stage L Hellcat calibration inputs
2. test(s12): define Stage L Hellcat source contracts
3. feat(s12): model Hellcat cross-plane blowdown and torque roughness
4. feat(s12): separate Hellcat intake whine from exhaust roar
5. fix(s12): rebuild Hellcat load and shift acoustic transients
6. feat(s12): qualify Hellcat intake and cross-plane roughness
7. feat(s12): publish Stage L Hellcat named calibration package
8. docs(s12): publish Stage L evidence and knowledge handoff
```

每次只暂存明确文件，检查 staged diff，运行对应 focused tests。全部只保留本地：

```text
禁止 push
禁止 merge
禁止 rebase
禁止修改 main
```

---

## 12. 首次执行交付与停止状态

Luna 首次执行必须交付：

- hash-bound Jovi 文字反馈与 CSV 冲突说明；
- Hellcat Candidate v8；
- cross-plane bank event / blowdown / structure source；
- 独立 SC aero/intake 与 gear/casing source；
- Hellcat 专属 shift/load transient；
- source-domain 与 final-PCM 指标；
- 30% reference-distance 结果；
- 60 秒具名 parent/candidate/comfort 文件；
- source-separated 与 state clips；
- 合法 1–5 反馈 CSV；
- 全部 SHA、测试、报告与 Obsidian 更新；
- 本地 commits；
- MATLAB/Simulink 零修改证据。

然后停止于以下之一：

```text
WAITING_FOR_JOVI_STAGE_L_NAMED_REVIEW

或

PARTIAL / AUTOMATED_GATE_FAIL
UNQUALIFIED_DIAGNOSTIC_ONLY
DIAGNOSTIC_FEEDBACK_ALLOWED
```

不得自行进入：

```text
HUMAN PASS
PROFILE FREEZE
APPROVED PROFILE
SIMULINK INTEGRATION
RUNTIME INTEGRATION
ANDROID / ESP32 INTEGRATION
OEM REPRODUCTION
CALIBRATED
```

全部输出继续标记：

```text
synthetic
uncalibrated
Hellcat-inspired
vehicle-inspired
not OEM reproduction
```
