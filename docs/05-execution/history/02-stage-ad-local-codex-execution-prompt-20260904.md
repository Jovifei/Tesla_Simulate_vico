# Stage AD 本地 Codex 执行 Prompt — 只生成声音供 Jovi 试听

> 把本文件整体交给本地 Codex。目标不是继续写远端架构，也不是自动 Profile Freeze；目标是拉取 Stage AD 远端实现，在 Jovi 本地合法/已有参考音频上跑闭环，修复可修的 Simulink diagnostic mirror，并最终只产出一个可试听 WAV 目录给 Jovi。

---

你现在接手 `Jovifei/Tesla_Simulate_vico` 的 S12 Stage AD。

## 0. 任务目标

当前产品主线是 Android App-first，但你这一轮**不做 App**。这一轮只完成声音闭环验证：

```text
已有真实参考声音
→ AA-C3 当前候选链
→ Reference Comparator
→ source-causal 参数调整
→ 再渲染
→ 固定尺度 reference distance
→ 参数域 recenter + shrink
→ 再渲染
→ 最终 monitor WAV
→ Jovi 试听
```

最终只需要向 Jovi 提供：

1. 一个 `s12-stage-ad-hellcat-closed-loop-v1` 试听目录；
2. 每个场景一个清楚编号的 monitor WAV；
3. `audition_manifest.json`；
4. 一段极简说明：目录在哪里、跑了几轮、reference level 是 R1/R2/R3、是否有 hard gate failure。

**不要自动宣布 winner、HUMAN_PASS、OEM_MATCH 或 Profile Freeze。**

---

# 1. Git 安全接手

本地主要仓库预计在：

```text
E:\Tesla_speed\prj
```

先：

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git status --short
git ls-remote origin refs/heads/s12-stage-ad-closed-loop-calibration
```

不要覆盖用户当前工作树。如果当前工作树非空，使用独立 worktree：

```powershell
$WT = "E:\Tesla_speed\worktrees\s12-stage-ad-closed-loop-calibration"
if (!(Test-Path $WT)) {
    git worktree add $WT origin/s12-stage-ad-closed-loop-calibration
}
cd $WT
git status --short
git rev-parse HEAD
```

如果 worktree 已存在且干净：

```powershell
git fetch origin
git merge --ff-only origin/s12-stage-ad-closed-loop-calibration
```

禁止 force reset 用户有未提交改动的工作树。

---

# 2. 必读

先读：

```text
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Decision-History-And-Negative-Knowledge.md
docs/research/engine-audio-ecosystem/stage_ad_closed_loop_sources.md
docs/04-planning/05-s12-reference-closed-loop-optimization.md
S12_Simulink_Playground_v09_Offline_Audit.md
tools/sound_sim/s12/acoustic_identity_v015/stage_ad/
```

关键边界：

```text
AA-C3 official V3 package = IMMUTABLE
Track-P/PTR/Radiation = FROZEN
Stage AD output = DIAGNOSTIC AUDITION ONLY
ESP32 = OUT OF SCOPE
Android App = OUT OF THIS LOCAL ROUND
```

---

# 3. 先验证新代码

执行：

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ad_closed_loop.py -q
```

然后运行与你修改相关的 Stage AA/X/Y focused tests。使用 `rg` 找现有测试，不要猜名字：

```powershell
rg -n "candidate_search|render_candidate|parameter_reachability|multi_reference|reference_caseset" tools/sound_sim/s12/acoustic_identity_v015/tests
```

至少保证：

- Stage AD tests PASS；
- AA-C3 default render 与 `config_override=_fitted_config()` parity PASS；
- comparator/reference tests PASS；
- candidate search / parameter-domain tests PASS；
- git diff --check PASS。

如果新代码有 bug，直接在**本地 Stage AD 分支**修复并记录，不要修改官方 V3 PCM 文件。

---

# 4. 找本地已有合法参考声音

禁止为了完成任务临时从 YouTube/公网下载版权不明音频。

优先寻找项目已经使用过的 canonical reference registry / caseset / local WAV：

```powershell
rg -n "reference_registry|reference_caseset|audio_path|recording_session_id|hellcat" tasks docs tools E:\Tesla_speed -g "*.json" -g "*.md"
```

如果存在 canonical registry，检查：

- `vehicle_id = hellcat_v1`；
- 本地 WAV 文件存在；
- SHA 与 registry 一致；
- rights/evidence level 明确；
- speech/music contaminated case 不进入闭环。

R2/R3 可以用于这次 diagnostic closed loop，但必须保持原等级，绝不能升级为 R1。

如果找到多个独立 recording session，保留 independent reference count；不要把同一 recording 的多个窗口当多个独立 Reference。

如果本地确实没有可用 Reference：

1. 不下载新素材；
2. 生成 AA-C3 baseline audition 作为 smoke；
3. 向 Jovi 明确报告 `REFERENCE_LOCAL_FILE_MISSING`；
4. 停止 reference optimization。

---

# 5. 建议的负反馈执行顺序

不要一次搜索全部 22 个参数。采用可解释的 coordinate/family closed loop：

```text
BODY / IDLE
→ BLOWER
→ AFTERFIRE
```

每个 family：

- 先在固定 reference-distance 上优化；
- 得到 `final_config.json`；
- 下一 family 以它为 `--base-config-json`；
- 每 family 默认 2 个 outer iterations；
- 每轮 `coarse-count=24`, `refine-count=12`；
- 如果 reference distance 明显仍下降，可增加第 3 iteration；
- 如果 plateau，停止该 family。

假设 canonical registry 路径记为 `$REF`：

```powershell
$REF = "<FOUND_CANONICAL_REFERENCE_REGISTRY.json>"
$ROOT = "E:\Tesla_speed\stage_ad_runs\hellcat_closed_loop_v1"
```

## 5.1 Body / Idle

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli `
  --reference-registry $REF `
  --vehicle-id hellcat_v1 `
  --baseline aa-c3 `
  --family body `
  --iterations 2 `
  --coarse-count 24 `
  --refine-count 12 `
  --output-root "$ROOT\01_body"
```

检查：

- `closed_loop_summary.json`；
- `final_absolute_reference_distance`；
- hard gates；
- best overrides；
- hot_idle/full_pull 不出现 clipping/click；
- LF 改善不是 global/master gain。

## 5.2 Blower

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli `
  --reference-registry $REF `
  --vehicle-id hellcat_v1 `
  --baseline aa-c3 `
  --family blower `
  --base-config-json "$ROOT\01_body\final_config.json" `
  --iterations 2 `
  --coarse-count 24 `
  --refine-count 12 `
  --output-root "$ROOT\02_blower"
```

重点：不要简单 notch 741 Hz；观察 carrier/sideband/broadband/casing/intake/boost envelope 是否更接近 Reference。

## 5.3 Afterfire

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.cli `
  --reference-registry $REF `
  --vehicle-id hellcat_v1 `
  --baseline aa-c3 `
  --family afterfire `
  --base-config-json "$ROOT\02_blower\final_config.json" `
  --iterations 2 `
  --coarse-count 24 `
  --refine-count 12 `
  --output-root "$ROOT\03_afterfire"
```

必须检查 `afterfire_ineligible` event count = 0。

如果 afterfire reference 不存在，**不要因为缺参考而任意调 afterfire**。此时直接保留 `$ROOT\02_blower\final_config.json` 作为最终 config，并用最后一个有 Reference 的 loop 打包试听。

---

# 6. Human feedback 的使用

当前如果还没有 Jovi 新一轮 feedback，不要伪造 `human-feedback-json`。

如果 Jovi 后续提供 feedback：

```text
先保存 verbatim
→ SHA256
→ 再进入 Stage AD --human-feedback-json
```

feedback adjustment 只能是 bounded guidance；fixed-scale real-reference distance 仍单独保存。

---

# 7. Simulink：能修就修，但 Python 仍是权威

先找本地 `.slx`：

```powershell
Get-ChildItem E:\Tesla_speed -Recurse -Filter "*.slx" | Select-Object FullName
```

根据旧 audit，v0.9 主要错误是：

- subsystem 内还有默认 `In1→Out1` bypass；
- packed config 被推断成 scalar，不是固定 19x1；
- excitation/pressure/PCM dimensions 未固定；
- Audio Device Writer/To Workspace 接在 bypass；
- compile/update fail。

**不要覆盖原始 SLX。** 创建候选副本，例如：

```text
S12_Simulink_Sound_Playground_stage_ad_candidate.slx
```

在用户已有 MATLAB session 中执行（不要自动启动新的 MATLAB）：

```matlab
addpath(fullfile(pwd, 'tools', 'sound_sim', 's12', 'acoustic_identity_v015', 'stage_ad', 'simulink'));
s12_stage_ad_validate_model("<candidate_model_name>", "E:/Tesla_speed/stage_ad_runs/simulink_validation.json");
```

如果 validation PASS，再用 Python 生成一个 request JSON（或手工由 Stage AD receipt 生成），然后：

```matlab
s12_stage_ad_closed_loop_bridge( ...
    "<candidate_model_name>", ...
    "E:/Tesla_speed/stage_ad_runs/simulink_request.json", ...
    "E:/Tesla_speed/stage_ad_runs/simulink_bridge_receipt.json");
```

只有：

```text
Update Diagram PASS
+ simulation PASS
+ finite Nx2 PCM
+ frame multiple of 960
```

才保留候选 model。

然后再做 Python vs Simulink PCM/equivalence diagnostic。

如果不能在合理修改内通过，记录具体 compile error，保留 Python authoritative loop，不要卡住试听声音生成。

---

# 8. 打包最终试听声音

如果 `03_afterfire` 成功，使用它；否则使用最后一个成功 loop，例如 `02_blower`。

```powershell
$FINAL_LOOP = "$ROOT\03_afterfire"
$AUDITION = "E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1"

python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ad.package_audition `
  --loop-root $FINAL_LOOP `
  --output-root $AUDITION
```

最终目录应类似：

```text
s12-stage-ad-hellcat-closed-loop-v1/
  01_hot_idle.wav
  02_steady_low.wav
  03_steady_mid.wav
  04_steady_high.wav
  05_tip_in.wav
  06_full_pull.wav
  07_shift.wav
  08_lift.wav
  09_afterfire.wav
  10_idle_return.wav
  audition_manifest.json
```

这是 Stage AD **非盲 diagnostic audition package**，和官方 V3 分开。

---

# 9. 你最终回复 Jovi 的格式

不要给大段技术报告，只给：

```text
Stage AD 本地闭环已执行。

试听目录：<absolute path>
Reference evidence：R2/R3/R1（按实际）
Closed-loop：body X rounds → blower X rounds → afterfire X rounds
Final reference distance：<value>
Hard gates：PASS/FAIL
Simulink mirror：PASS / NOT_READY（如果未通过写一句原因）

请先听试听目录里的 01–10 WAV，我等你的听感反馈后再继续。
```

然后停止。不要自动继续调下一轮。

---

# 10. 禁止事项

- 不覆盖 `s12-stage-aa-hellcat-quality-v3`；
- 不打开/改变旧 blind answer mapping；
- 不改 Track-P/PTR/Radiation 数学；
- 不用 master/global/broad pre-PTR gain；
- 不把 R2/R3 写成 R1；
- 不从公网新下载未授权音频；
- 不做 ESP32；
- 不做 Android App；
- 不自动 push/merge 新本地调音结果；
- 不在 Jovi 听之前继续无限迭代。
