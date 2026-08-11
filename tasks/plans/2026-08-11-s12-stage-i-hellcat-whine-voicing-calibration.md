# Jovi — S12 Stage I Hellcat 增压器音色、遮蔽关系与具名人耳闭环执行计划

> 执行模型：Luna。实施时必须使用 `using-git-worktrees`、`test-driven-development`、`executing-plans`、`verification-before-completion`。
> 本文是执行授权前的详细计划；只有 Jovi 后续明确要求“执行此计划”后，Luna 才能修改声源代码。
> 所有输出继续标记：`synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction`。

## 1. 阶段结论、目标与证据边界

### 1.1 当前权威状态

- 工作树：`E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration`
- 分支：`agent/s12-stage-h-hellcat-perceptual-calibration`
- Stage H 当前本地 tip：`6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2`
- 相对 `origin/main`：`0 behind / 30 ahead`
- Stage H 状态：`WAITING_FOR_JOVI_NAMED_CALIBRATION`
- Stage H focused：`14 passed`
- 完整 S12：`488 passed / 232 subtests`
- Track-P guard：`21/21`
- Stage H Hellcat blower/load correlation：`0.9764`
- Stage H Hellcat final-PCM reference-distance 改善：`8.479%`
- 固定自动门槛：`>=30%`，当前仍为 `PARTIAL / AUTOMATED_GATE_FAIL`
- Stage G sealed key 未读取；没有正式 confusion matrix 或通用 Human PASS。

### 1.2 Jovi 本轮人耳反馈

本轮反馈必须拆成两个证据层，不能混写：

1. 明确车型目标：Hellcat 当前“不像 Hellcat”，需要更容易识别的、随 RPM/load/boost 变化的“滋滋哟”增压器啸叫。
2. 编号反馈：
   - 第 1 个声音：不像 Hellcat；
   - 第 2 个声音：高频刺耳，低频轰鸣很好；
   - 第 3 个声音：整体很好，但仍有优化空间。

编号反馈在进入代码修改前必须绑定到具名 `file_id`。在绑定完成前：

- Hellcat 可依据 Jovi 明确提出的车型目标继续定向建模；
- 第 2、第 3 个声音记录为 `UNBOUND_NUMBERED_FEEDBACK`；
- 不得擅自把第 2 个绑定 Ferrari、把第 3 个绑定 RX-7；
- Ferrari 和 RX-7 的 Stage H/Stage G PCM SHA 全部冻结，不进行顺手调音。

### 1.3 Stage I 最终目标

Stage I 不再证明“参数能动”或“阶次存在”，而是要证明：

```text
Jovi 具名试听时：

Hellcat 的低频 cross-plane HEMI 仍然是主体
+
加速/高负载时出现可辨识但不刺耳的增压器“滋滋哟”啸叫
+
换挡时啸叫短暂下陷并重新建立
+
收油时出现受 boost 历史约束的短暂旁通释放
```

首次执行完成后必须停止在：

```text
WAITING_FOR_JOVI_STAGE_I_NAMED_REVIEW
```

不得自动进入 Profile Freeze、Simulink、Runtime、Android 或 ESP32。

## 2. 在线研究结论与可使用的推论

### 2.1 官方公开事实

Stellantis 公开资料说明：

- Hellcat 使用双螺杆机械增压器；
- 传动比为 `2.36:1`；
- 最大增压器转速约 `14,600 rpm`；
- 电子旁通阀用于调节增压压力；
- 排气系统本身被调校为浑厚的 Dodge 风格声浪。

资料：

- <https://blog.stellantisnorthamerica.com/2015/11/10/can-you-name-that-engine-day-ii/>
- <https://blog.stellantisnorthamerica.com/2022/08/15/the-cat-is-back-2023-dodge-durango-srt-hellcat-most-powerful-suv-ever-returns-to-dodge-lineup/>

Dodge 的公开驾驶描述反复把 Hellcat 的身份写成“排气轰鸣 + 增压器啸叫”的组合；油门打开后啸叫迅速成为可识别线索，收油后进入滑行：

- <https://www.dodge.com/news/2023-challenger-black-ghost-drive.html>
- <https://www.dodgegarage.com/news/article/reviews/2020/07/highway-to-hell-cat>

### 2.2 NVH 建模依据

SAE 研究指出：机械增压器是显著的高频阶次声源，声能经进气管路、airbox、intercooler 和壳体传播；窄带阶次在背景遮蔽不足时会非常突出甚至令人烦躁。因此“固定纯音 + 提高增益”不是可信路线，必须同时建模：

- 移动阶次；
- 确定性侧带；
- 进气/壳体传播塑形；
- 与燃烧/排气背景的遮蔽关系；
- boost 建立、换挡中断和旁通释放的时间结构。

资料：

- <https://saemobilus.sae.org/articles/nvh-integration-twin-charger-direct-injected-gasoline-engine-2014-01-2087>
- <https://saemobilus.sae.org/papers/improved-techniques-intake-acoustic-system-modeling-a-supercharged-engine-2017-01-1790>

### 2.3 禁止推论

- 官方没有给出本项目可直接采用的转子齿数、精确声压、麦克风位置或整车传递函数；不得伪造。
- Stage H 使用的 `11.8 / 23.6` order family 继续只标记为 C 级合成架构假设，不得写成 OEM 测量值。
- 在线视频和现有 B/R2 录音只能提供相对音色和状态变化方向，不用于绝对 LUFS/RMS 校准。
- 本阶段不下载新音频。若未来确需获取新参考 PCM，必须另获 Jovi 授权并记录许可、来源、SHA 和录音条件。

## 3. 根因假设与验证顺序

Luna 必须先验证假设，不能直接批量扫参数。

### H-I-1：Stage H 的阶次过于相干，听感仍接近合成正弦

当前 `blower_shaft / lobe / upper` 主体仍由少量纯正弦组成。即使 order error 很小、sideband ratio 合格，也可能听起来像电子 tone。

验证：

- 计算 400–3200 Hz 的单 ridge 能量集中度；
- 计算 spectral crest、order-cluster width 和 20–200 Hz 幅度调制能量；
- 与 Stage H v5 比较，而不是仅看总 blower energy。

预期修复：加入确定性的转速微扰 FM 和窄幅 order cluster；禁止白噪声、随机抖动和固定频率 tone。

### H-I-2：缺少进气/壳体传播音色，导致“有啸叫但不像 Hellcat”

Stage H 已经生成 moving orders，但没有足够的 intake/casing transfer voicing。移动阶次没有经过可听的共振/反共振塑形，会显得干、薄或刺耳。

验证：

- 用相同 blower excitation 分别渲染 transfer off/on；
- 比较 400–1000、1–2 kHz、2–4 kHz、4–12 kHz 的短时包络；
- 确认 transfer 只改变音色，不改变 order sweep 的物理跟随关系。

### H-I-3：Stage H 的时间指标不能准确反映候选参数

当前报告中 seed attack 为 `0.075 s`，但整段工况指标输出 `4.1 s`；bypass decay 输出 `0.0 s`。这些值不足以验证参数是否真的改变 boost step response。

验证和修复必须先于调音：

- 新建标准化 boost step、shift dip、lift release probe；
- 在 source-domain 直接测量 10–90% attack、90–10% release 和 bypass 90–10% decay；
- 测量值必须随对应参数单调变化，并在声明参数附近保持可解释关系。

### H-I-4：整段平均 blower/exhaust 比不能代表“啸叫何时出现”

Stage H 整段 blower/exhaust ratio 为 `-8.385 dB`，但 idle、acceleration、full pull、shift、lift 的听感职责不同。

验证：建立逐状态 ratio 和 masking 指标。idle 必须被 V8 遮蔽；acceleration/full pull 必须能穿透；shift 必须下陷后恢复；lift 只允许历史 boost 驱动的短暂释放。

## 4. Phase I0：独立工作树、反馈固化和证据冻结

### I0.1 Fail-closed 起点

执行前检查：

```powershell
git -C E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration rev-parse HEAD
git -C E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration branch --show-current
git -C E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration status --porcelain
git -C E:\Tesla_speed\worktrees\s12-stage-h-hellcat-perceptual-calibration rev-list --left-right --count origin/main...HEAD
```

预期：

```text
HEAD = 6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2
branch = agent/s12-stage-h-hellcat-perceptual-calibration
origin/main...HEAD = 0 30
```

由于本轮计划编写会留下计划/账本文件，允许的唯一 planning diff 是：

```text
tasks/plans/2026-08-11-s12-stage-i-hellcat-whine-voicing-calibration.md
tasks/todo.md
tasks/lessons.md
```

出现其他修改时停止：

```text
BLOCKED / BASELINE_DRIFT
```

不得 reset、stash、clean、pull、rebase 或覆盖用户文件。

### I0.2 建立新工作树

```powershell
git -C E:\Tesla_speed\prj worktree add `
  -b agent/s12-stage-i-hellcat-whine-voicing `
  E:\Tesla_speed\worktrees\s12-stage-i-hellcat-whine-voicing `
  6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2
```

所有实现只在新工作树进行。把本计划以 `apply_patch` 写入新工作树同路径，并在 `tasks/todo.md` 建立 I0–I8 清单。

### I0.3 冻结证据

记录 SHA-256：

- Stage H Candidate v5；
- Stage H 60 秒 Hellcat baseline/candidate；
- Ferrari/RX-7 unchanged WAV；
- Stage H named ZIP；
- Stage H metrics、reference-distance、test evidence；
- Stage H 报告；
- 相关 Obsidian 页面。

Stage H v5、Stage G v4、历史试听包和 sealed 文件必须保持原字节。

### I0.4 反馈落盘

新增：

```text
tasks/reports/runtime/s12-stage-i-hellcat-whine-voicing-v1/stage_i_feedback_intake.json
```

必须包含：

- Jovi 原始中文反馈；
- `hellcat_target_explicit=true`；
- 第 2、第 3 个声音的 `file_id=null` 和 `binding_status=UNBOUND`；
- 反馈来源为当前 Codex 会话，而不是虚构 CSV；
- 未绑定条目不得触发 Ferrari/RX-7 修改。

## 5. Phase I1：先用 TDD 修正可观测性

### 5.1 新增文件

```text
tools/sound_sim/s12/acoustic_identity_v015/stage_i/
├── __init__.py
├── candidate_profiles.py
├── render_candidate.py
├── whine_voicing.py
├── perceptual_metrics.py
├── candidate_search.py
├── named_review.py
└── feedback_contract.py

tools/sound_sim/s12/acoustic_identity_v015/tests/
├── test_s12_stage_i_feedback_binding.py
├── test_s12_stage_i_candidate_contract.py
├── test_s12_stage_i_whine_voicing.py
├── test_s12_stage_i_step_response_metrics.py
├── test_s12_stage_i_perceptual_metrics.py
├── test_s12_stage_i_pipeline_order.py
├── test_s12_stage_i_candidate_search.py
├── test_s12_stage_i_named_package.py
└── test_s12_stage_i_regression_isolation.py
```

### 5.2 RED 测试必须先证明以下缺口

- Stage H attack 的整段 `4.1 s` 指标不能代表 `0.075 s` source attack；
- Stage H bypass decay `0.0 s` 不能用于调参；
- 纯 order-family 单 ridge concentration 过高；
- 反馈没有 file ID 时，Ferrari/RX-7 调音请求必须 fail closed；
- 未实现 Stage I source/schema 时 collection 或行为测试应为 RED。

保存 RED 命令、失败摘要和时间，不得跳过。

### 5.3 标准 probe

新增固定、确定性的 probe：

```text
idle_probe        900 rpm / low load / low throttle
boost_step_probe  1800→4200 rpm / load 0.25→0.90 / throttle 0.25→0.95
shift_probe       high load + one RPM drop + throttle maintained
lift_probe        4200 rpm hot/high boost 3 s → throttle close 4 s
zero_probe        zero load + zero throttle + no boost history
```

所有 probe 使用 48 kHz，固定时长和固定 trace SHA。

验收：

- attack/release/decay 测量与参数单调对应；
- zero probe 的 blower 和 bypass 必须逐样本为零；
- 不同 `PYTHONHASHSEED` 输出 SHA 一致。

## 6. Phase I2：Supercharger Whine v3 音色重建

### 6.1 最小新增入口

新增：

```text
sources/supercharger_whine_v3.py
targets/stage_i_hellcat_candidate.schema.json
targets/stage_i_candidates/Hellcat_candidate_v6.json
```

公开：

```python
def render_supercharger_whine_v3(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    engine_phase: np.ndarray,
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    ...
```

```python
def load_stage_i_candidate(path: str | Path) -> StageICandidateProfile:
    ...
```

```python
def render_stage_i_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: StageICandidateProfile | None = None,
) -> SourceRender:
    ...
```

### 6.2 固定架构

```text
engine RPM
→ 2.36:1 shaft phase
→ deterministic four-event-per-rev torsional phase ripple
→ shaft / lobe / upper moving order clusters
→ V8-synchronous symmetric sidebands
→ boost/load/throttle envelope
→ synthetic intake/casing transfer voicing
→ shift dip and rebuild
→ boost-history bypass pitch fall / decay
→ Hellcat blower aggregate
```

实现约束：

- 频率必须随 RPM 连续移动；
- phase ripple 只允许确定性 FM，不得使用随机 jitter；
- order cluster 是窄带移动簇，不是静态 chorus 或白噪声；
- intake/casing transfer 只塑形 400–4000 Hz，不能用公共 EQ；
- 4–12 kHz 只能衰减或保持，不得以高频增益制造“滋滋哟”；
- bypass 必须同时满足历史 boost 和 throttle close；
- pressure 只通过 stem 差值回写一次；
- 新增能量全部在 Common Pre-PTR EQ 和 Frozen PTR 之前。

### 6.3 Stems

保留 Stage H 兼容 stem 名：

```text
blower_shaft
blower_lobe_family
blower_upper_family
blower_sidebands
blower_bypass_release
blower
```

允许新增诊断 stem：

```text
blower_intake_voicing
```

若新增该 stem，则所有 audible stems 之和必须逐样本等于 `blower`。不得把 pre-transfer 中间信号同时计入 aggregate。

### 6.4 Candidate v6 初始参数

以下全部是 C/synthetic 听感种子，不是 Hellcat OEM 数据：

| 参数 | v6 初值 | 允许范围 | 作用 |
|---|---:|---:|---|
| `blower_gain_scale` | 1.18 | 1.00–1.35 | 加速时 whine 存在感 |
| `blower_boost_mix` | 1.18 | 0.95–1.35 | boost 对 whine 包络的权重 |
| `lobe_family_mix` | 1.12 | 0.90–1.35 | 中部 order family 主体 |
| `upper_family_tilt_db` | -5.0 dB | -8.0–-2.0 dB | 抑制刺耳上部 family |
| `sideband_depth` | 0.14 | 0.08–0.22 | 增加机械粗糙感而非宽带噪声 |
| `phase_ripple_depth` | 0.004 | 0.001–0.010 | V8 同步微 FM |
| `order_cluster_spread_ratio` | 0.012 | 0.004–0.025 | 降低单纯正弦感 |
| `intake_voicing_mix` | 0.18 | 0.05–0.30 | 合成进气/壳体传播音色 |
| `boost_attack_s` | 0.075 s | 0.060–0.120 s | whine 建立 |
| `boost_release_s` | 0.24 s | 0.18–0.35 s | whine 消退 |
| `bypass_release_gain` | 0.12 | 0.06–0.20 | 收油旁通存在感 |
| `bypass_pitch_fall_ratio` | 0.80 | 0.65–0.95 | 收油时短促音高下滑 |
| `bypass_decay_s` | 0.16 s | 0.08–0.30 s | 旁通释放尾部 |

固定、不可调的 synthetic transfer modes 需要在代码和 diagnostics 中记录数值、单位与 C 级来源；不能藏在魔法常数中。

### 6.5 Candidate contract

每个公开参数必须使用统一 provenance 记录：

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

要求 exact-key、finite、严格升序二元 range、value 位于 range 内、unknown field fail closed。每个公开字段必须有单参数扰动测试；无法证明作用的字段从 schema 删除。

## 7. Phase I3：状态专属指标与候选搜索

### 7.1 新指标

新增：

```text
shaft_order_error
lobe_order_error
blower_load_correlation
blower_to_exhaust_ratio_idle_db
blower_to_exhaust_ratio_acceleration_db
blower_to_exhaust_ratio_full_pull_db
shift_whine_dip_db
shift_whine_rebuild_time_s
single_ridge_concentration
order_cluster_width_ratio
sideband_to_main_ratio
am_modulation_ratio_20_200hz
boost_attack_10_90_s
boost_release_90_10_s
bypass_decay_90_10_s
spectral_crest_400_3200hz
upper_band_share_4_12khz
upper_band_short_time_peak
```

### 7.2 硬门禁

- shaft/lobe ridge 相对误差 `<=1%`；
- blower/load correlation `>=0.82`；
- acceleration blower/exhaust ratio 相对 Stage H 提高 `2–4 dB`；
- idle blower/exhaust ratio相对 Stage H 增加不超过 `0.5 dB`；
- full-pull blower/exhaust ratio相对 Stage H 提高 `1.5–3.5 dB`；
- sideband/main ratio `0.08–0.18`；
- order-cluster width ratio `0.006–0.030`；
- 400–3200 Hz 的最大单 ridge concentration 相对 Stage H 下降 `15–40%`；
- acceleration 4–12 kHz share `<=0.010`，且相对 Stage H 增量 `<=0.003`；
- Stage I upper-band short-time peak不得高于 Stage H；
- standard probe attack `0.060–0.120 s`；
- standard probe release `0.18–0.35 s`；
- bypass decay `0.08–0.30 s` 且 event count `>=1`；
- Hellcat 40–200 Hz share 相对 Stage H 变化不超过 `5%`；
- rumble energy 相对 Stage H 下降不超过 `5%`；
- whole-cycle LUFS 相对 Stage H 差 `<=0.5 LU`；
- peak `<=-1.5 dBFS`、clipping `=0`、48 kHz/stereo/PCM24/finite；
- Ferrari、RX-7 和另外五车最终 PCM SHA 不变；
- Track-P guard `21/21`。

### 7.3 固定 reference-distance 不变

继续使用：

```text
D = sqrt(0.25 × Σ(actual_band_share - target_band_share)^2)
```

门槛仍为 eligible states 平均改善 `>=30%`、任一状态不得恶化超过 `10%`。不得修改公式、reference target 或阈值。

本阶段主要改善 whine 音色，可能不足以解决 afterfire 状态距离；因此：

- 可以生成具名诊断包；
- 若平均仍低于 30%，自动状态必须继续写 `PARTIAL / AUTOMATED_GATE_FAIL`；
- 即使 Jovi 认为 Hellcat 更像，也不得因此进入 Profile Freeze。

### 7.4 有界搜索

禁止沿用 broad-band coordinate descent 自动决定“更像 Hellcat”。使用确定性两阶段搜索：

1. 最多 36 个候选：presence、timbre、transient 三组参数做低维组合；
2. 先淘汰所有硬门禁失败项；
3. 从剩余候选中选择三种不同取向：
   - `I6-A Balanced`：排气和 whine 平衡；
   - `I6-B Whine Forward`：更明显“滋滋哟”，但通过 harshness gate；
   - `I6-C Softer Mechanical`：机械粗糙感更强、上部更柔和；
4. 自动系统只负责产生三种合格候选，不自行宣布哪一个更像 Hellcat；
5. 参数字典序作为确定性 tie-break；不同进程输出相同 SHA。

## 8. Phase I4：具名对比包

输出：

```text
E:\Tesla_speed\review_packages\s12-stage-i-hellcat-whine-voicing-v1\
├── 00_OPEN_ME_FIRST.md
├── 01_Hellcat_60s\
│   ├── 01_StageH_v5_Baseline_60s.wav
│   ├── 02_StageI_v6_A_Balanced_60s.wav
│   ├── 03_StageI_v6_B_WhineForward_60s.wav
│   └── 04_StageI_v6_C_SofterMechanical_60s.wav
├── 02_Hellcat_Diagnostics\
│   ├── StageH_BlowerOnly_Acceleration.wav
│   ├── StageI_A_BlowerOnly_Acceleration.wav
│   ├── StageI_B_BlowerOnly_Acceleration.wav
│   ├── StageI_C_BlowerOnly_Acceleration.wav
│   ├── StageI_Shift_Dip_Rebuild_12s.wav
│   ├── StageI_Lift_Bypass_12s.wav
│   └── StageI_ExhaustOnly_Acceleration.wav
├── 03_Anchor_Mapping\
│   ├── Ferrari_458_StageH_Unchanged_60s.wav
│   └── RX7_FD_StageH_Unchanged_60s.wav
├── 04_Metrics\
│   ├── candidate_comparison.json
│   ├── order_map.png
│   ├── spectrogram.png
│   ├── state_ratio_map.png
│   └── transient_response.png
├── 05_Feedback\
│   └── Jovi_Stage_I_Named_Feedback.csv
├── artifact_manifest.json
├── SHA256SUMS.txt
└── S12_Stage_I_Named_Review.zip
```

60 秒时间线继续固定：

```text
0–8 s idle
8–26 s acceleration + 3 shifts
26–36 s full pull
36–46 s lift / afterfire / bypass
46–52 s coast
52–60 s idle return
```

响度公平：

- 四个 Hellcat 60 秒文件使用共同 attenuation-only 目标；
- blower-only 诊断组使用另一个共同 attenuation-only 目标；
- 只能衰减，禁止 compressor、limiter、EQ、per-section AGC；
- 不把诊断副本的 gain 回写候选 profile。

反馈表字段：

```text
file_id
vehicle_id
candidate_id
hellcat_likeness_1_5
whine_presence_1_5
whine_naturalness_1_5
low_frequency_weight_1_5
high_frequency_harshness_1_5
shift_rebuild_naturalness_1_5
bypass_release_naturalness_1_5
artifact_freedom_1_5
preference_rank
keep_or_change
notes
```

具名人耳门禁：

- Hellcat likeness `>=4/5`；
- whine presence `>=4/5`；
- whine naturalness `>=4/5`；
- low-frequency weight `>=4/5`；
- high-frequency harshness `<=2/5`；
- shift rebuild naturalness `>=4/5`；
- bypass release naturalness `>=3/5`；
- artifact freedom `>=4/5`；
- Jovi 必须明确选择一个 candidate 或标记全部失败。

完成包、报告和 Obsidian 后必须硬停止：

```text
WAITING_FOR_JOVI_STAGE_I_NAMED_REVIEW
```

## 9. Phase I5：Jovi 反馈驱动的最多三轮迭代

版本只能新增，不能覆盖：

```text
Hellcat_candidate_v6 → v7 → v8
```

每轮：

1. 固化反馈 CSV SHA；
2. 校验 file_id、评分范围、rank 和 notes；
3. 一次只改变一个失败维度；
4. Ferrari/RX-7 和另外五车 PCM SHA 保持不变；
5. 重跑 Stage I focused、Stage H、identity、reference、Track-P；
6. 重新生成新版本具名包，不覆盖上一轮；
7. 保存参数、自动指标和 Jovi 原始文字。

失败映射：

- whine 不明显：只调 acceleration/full-pull presence envelope，不动全局 gain；
- whine 像电子 tone：增加 phase ripple/order cluster/intake voicing，保持 order ridge；
- 高频刺耳：降低 upper family 和 transfer high mode，禁止公共 EQ；
- 低频被盖住：降低 whine mix，LF body/rumble 不动；
- 换挡不自然：只调 whine dip/rebuild envelope；
- lift 不自然：只调 boost-history bypass pitch fall/decay；
- 出现随机噪声感：减少 cluster spread/sideband，不加入滤波白噪声。

三轮仍未达到人耳门禁：

```text
PARTIAL / HUMAN_AUDITION_FAIL
```

不得降低门槛。

## 10. 编号第 2、第 3 个声音的条件分支

首次 Stage I 包必须把 Ferrari、RX-7 具名文件放入 `03_Anchor_Mapping`。只有 Jovi 在反馈表中填写实际 `file_id` 后才能进入以下分支：

### 如果第 2 个确认为 Ferrari

- 只降低 event-driven metallic upper mode 的 Q、decay 或短时峰值；
- 4–12 kHz short-time peak 下降 `1.5–3 dB`；
- 1–4 kHz scream energy 下降不得超过 `5%`；
- 低频和 flat-plane event timing 保持不变；
- 使用独立 Candidate 和独立提交，不能混进 Hellcat v6。

### 如果第 2 个确认为 RX-7

- 只调整 turbine/BOV 上部能量和 release；
- rotary event timing、integer-order concentration 不得改变；
- half-order leakage 不得上升。

### 第 3 个“很好”

- 在 Jovi 给出具体改进项前，冻结该车型 PCM SHA；
- “还有优化空间”不能被 Luna自行解释为授权修改。

## 11. Phase I6：正式匿名包与 Profile Freeze 边界

只有具名 Hellcat 门禁通过后，才允许生成正式匿名包：

```text
E:\Tesla_speed\review_packages\s12-stage-i-blind-audition-v6\
```

匿名包复用 Stage G role-aware scorer：两轮各 15 题、三组真实 60 秒 A/B、sealed key、防泄漏和共同 attenuation-only。不得复制第二套评分逻辑。

三份正式答卷未返回前：

- 不读取 sealed key；
- 不生成 confusion matrix；
- 不写 Human PASS；
- 不进入 Profile Freeze。

即使匿名人耳通过，只要 30% 自动 reference gate 失败，仍不得进入 Profile Freeze Review。

## 12. 验证命令

### 12.1 Stage I focused

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_feedback_binding.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_candidate_contract.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_whine_voicing.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_step_response_metrics.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_perceptual_metrics.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_pipeline_order.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_candidate_search.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_named_package.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_i_regression_isolation.py -q
```

### 12.2 回归

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_h_candidate_contract.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_h_hellcat_whine_model.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_h_perceptual_metrics.py -q
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_g_reference_evidence.py -q
python -m pytest tools/sound_sim/s12/tests/test_s12_engine_acoustic_realism_v10.py -q
python -m pytest tools/sound_sim/s12/tests/test_s12_engine_acoustic_identity_v015.py -q
python -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q
python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py
git diff --check
git status --short
```

不得复用历史测试数量。报告实际 pass/subtest 数量、耗时和失败项。Track-P 失败立即停止，不 rebaseline、不改 allowlist。

## 13. 报告与知识库

仓库报告：

```text
tasks/reports/runtime/s12-stage-i-hellcat-whine-voicing-v1/
├── S12_Stage_I_Hellcat_Whine_Voicing_Report.md
├── stage_i_feedback_intake.json
├── stage_i_parameter_reachability.json
├── stage_i_step_response_metrics.json
├── stage_i_candidate_search.json
├── stage_i_hellcat_metrics.json
├── stage_i_reference_distance.json
├── stage_i_named_feedback_summary.json
├── stage_i_test_evidence.json
└── stage_i_artifact_manifest.json
```

Obsidian 新增：

```text
tesla\S12-Engine-Sound-v11\19-S12-Stage-I-Hellcat啸叫音色与遮蔽校准.md
```

更新：

- 项目概览；
- 总体计划；
- 当前进度；
- 工作流与知识；
- 12 号技术事实；
- 18 号 Stage H 历史页；
- Hellcat 车型卡；
- Ferrari/RX-7 卡片仅在 file_id 绑定并实际修改后更新；
- `tesla/index.md`。

状态必须区分：

```text
代码/指标健康
自动 reference qualification
Jovi 具名校准
正式匿名盲听
Profile Freeze Review
Jovi Explicit Approval
```

首次生成 Stage I 包后只能写 `WAITING_FOR_JOVI_STAGE_I_NAMED_REVIEW`。记录更新前后 SHA、YAML 检查和内部链接检查。

## 14. Git 提交建议

全部仅本地：

1. `test(s12): define Stage I Hellcat voicing contracts`
2. `fix(s12): make Hellcat whine timing metrics physically observable`
3. `feat(s12): add intake-voiced Hellcat supercharger clusters`
4. `feat(s12): publish Stage I named Hellcat candidate review`
5. `docs(s12): record Stage I evidence and knowledge handoff`

每次提交前只暂存明确文件，检查 staged diff，运行对应 focused tests，确认 Stage H v5 和所有冻结路径无变化。

禁止：

```text
push
merge
rebase
修改 main
删除历史包
修改 FVM/PTR/Radiation/Runtime/Android/MATLAB/Simulink
```

## 15. 失败行为、回滚和停止状态

回滚基线始终是：

```text
Stage H tip 6ee4b1a4a7e3925dd4ca2baf206c98ea76e697d2
Hellcat Stage H v5 WAV SHA 6eacaad7ff2e0fb52734d130d597d43efb6573a5491d93b0f4a70e505232c486
```

禁止覆盖 v5；Stage I 只新增 v6/v7/v8。任何失败候选保留 manifest 和失败原因，不作为 current candidate。

允许状态：

```text
BLOCKED / BASELINE_DRIFT
PARTIAL / AUTOMATED_GATE_FAIL
WAITING_FOR_JOVI_STAGE_I_NAMED_REVIEW
ITERATION_REQUIRED
WAITING_FOR_JOVI_STAGE_I_BLIND_AUDITION
PARTIAL / HUMAN_AUDITION_FAIL
JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS
PROFILE_FREEZE_REVIEW_PENDING
```

禁止状态：

```text
APPROVED PROFILE
OEM REPRODUCTION
CALIBRATED
UNIVERSAL HUMAN PASS
SIMULINK INTEGRATION
RUNTIME INTEGRATION
ANDROID / ESP32 INTEGRATION
```

## 16. Luna 首次执行交付与晨间审核清单

Luna 首次执行必须交付：

- Stage I v6 A/B/C 三种 Hellcat 具名候选；
- 标准 step/shift/lift probe 证据；
- 60 秒具名试听和独立 blower/exhaust 诊断 stem；
- Ferrari/RX-7 unchanged 具名映射文件；
- 指标、图、SHA、报告、Obsidian 更新；
- 本地提交和干净工作树；
- `PARTIAL / AUTOMATED_GATE_FAIL` 或实际自动门禁结果；
- `WAITING_FOR_JOVI_STAGE_I_NAMED_REVIEW`。

Jovi 晨间只需依次检查：

1. Stage H baseline；
2. Stage I A/B/C 三个 60 秒 Hellcat；
3. blower-only A/B/C；
4. shift rebuild 和 lift bypass；
5. 在反馈 CSV 中选择最接近 Hellcat 的 candidate；
6. 用具名 Ferrari/RX-7 文件绑定此前第 2、第 3 个声音。

在 Jovi 返回具名反馈前，Luna 不得继续第二轮调音、匿名评分或 Profile Freeze。
