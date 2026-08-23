# S12 Professional Comparison Dashboard v1 + R2 Diagnostic Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 对 `anchor_ab_zh_v1` 页面实际使用的 9 对 5 秒参考/候选片段重新生成 MATLAB Audio Toolbox、MoSQITo 和 Legacy Proxy 分列的专业指标，建立中文专业 Dashboard、简化 Jovi 反馈和不修改声源的 R2 有界诊断候选。

**Architecture:** 先用 Python 校验并标准化页面 manifest 的 18 个外部试听片段，调用 MATLAB R2026a Audio Toolbox 对每个 reference/candidate 分别测量，再用隔离 MoSQITo 1.2.1 解释器对同一对信号测量；Python 只负责频带、频谱残差、spectrogram、瞬态和汇总，不冒充专业工具。Dashboard 是独立静态中文 HTML，读取仓库 JSON 与外部绝对音频路径，不复制旧 A/B 包或原始媒体；Jovi 反馈只导出绑定 JSON，不能触发源文件写入。

**Tech Stack:** Python 3 + NumPy/SciPy/SoundFile、MATLAB R2026a Audio Toolbox、隔离 MoSQITo 1.2.1、静态 HTML/CSS/JavaScript；外部收据写入 `E:\Claude_allow\Download\s12-professional-comparison-dashboard-v1`，仓库只保存摘要、SHA、图表数据、报告和 Dashboard。

## Global Constraints

- 冻结 FVM、PTR core、Radiation、Runtime、Android、Simulink Track‑P、Stage N 专业工具收据、R1 资格门、SHA/file-ID 反馈安全合同。
- 不再优化 YouTube 下载器；公开视频派生音频保持 R3。
- 不把 Python proxy 写成 MATLAB/MoSQITo 正式指标；每个指标必须注明 `MATLAB Audio Toolbox`、`MoSQITo`、`Legacy Proxy` 或 `Not Qualified`。
- 必须同时分析 reference 与 candidate；输出 reference、candidate、delta、单位和不确定性。
- 没有可信 RPM trace 时 Order 状态固定为 `ORDER_COMPARISON_NOT_QUALIFIED`；不得猜测 RPM、自动阶次调参或 Profile Freeze。
- 不修改 reference、整体 AGC、全局 EQ、错误 event timing、frozen PTR/Radiation 或任何 Track‑P 文件。
- R2 诊断候选只生成有界规格，不写入车型声源；三个锚点各一个参数组、每组最多 64 个候选。
- 不输出总相似度百分比；Jovi 只确认软件诊断是否符合听感。

---

### Task 1: Exact A/B evidence normalization and integrity audit

**Files:**
- Create: `tools/sound_sim/s12/real_reference/professional_clip_analysis.py`
- Create: `tools/sound_sim/s12/tests/test_s12_professional_clip_analysis.py`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/clip_integrity.json`

**Interfaces:**
- `load_exact_anchor_pairs(manifest_path: Path) -> list[dict[str, Any]]`
- `validate_exact_clip_pair(pair: Mapping[str, Any]) -> dict[str, Any]`
- `analyze_proxy_pair(pair: Mapping[str, Any]) -> dict[str, Any]`
- CLI: `python -m tools.sound_sim.s12.real_reference.professional_clip_analysis --manifest <external-manifest> --output-dir <repo-dashboard-dir> --proxy-only`

- [ ] **Step 1: Write failing tests**

测试覆盖：manifest 必须有 9 个 trial/3 个锚点各 3 个；reference/candidate 文件存在、时长大于 0、WAV 可读取、声明 SHA 匹配；缺失文件、0 秒 WAV、SHA 错、重复 file_id、外部 reference 路径进入 Git 均拒绝；输出包含 sample rate、duration、channel、window、reference class、microphone uncertainty、order status。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_clip_analysis.py -q`

Expected: FAIL because the exact professional analysis module does not yet exist。

- [ ] **Step 3: Implement integrity and Legacy Proxy path**

读取当前 `anchor_ab_zh_manifest.json`，只接受 `reference_audition_path`/`candidate_audition_path` 包内试听副本；对两个 WAV 分别计算 SHA/时长/采样率/通道，记录 reference `R3`、`ORDER_COMPARISON_NOT_QUALIFIED` 和 `microphone_agc_uncertainty`。复用现有 `spectrum_features`/`transient_shape` 只写到 `legacy_proxy` 字段；不把这些字段命名为 MATLAB 或 MoSQITo。

- [ ] **Step 4: Run GREEN and audit current v1**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_clip_analysis.py -q`；随后对 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1\anchor_ab_zh_manifest.json` 生成 `clip_integrity.json`。Expected: 9 对、18 个 WAV、全部 SHA/时长通过。

- [ ] **Step 5: Commit**

`git add tools/sound_sim/s12/real_reference/professional_clip_analysis.py tools/sound_sim/s12/tests/test_s12_professional_clip_analysis.py tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/clip_integrity.json && git commit -m "feat(s12): normalize exact professional comparison clips"`

### Task 2: Exact MATLAB and MoSQITo professional receipts

**Files:**
- Create: `tools/sound_sim/s12/real_reference/run_exact_anchor_professional_metrics.m`
- Create: `tools/sound_sim/s12/real_reference/run_exact_mosqito_metrics.py`
- Create: `tools/sound_sim/s12/tests/test_s12_professional_receipts.py`
- Create external-only: `E:\Claude_allow\Download\s12-professional-comparison-dashboard-v1\tool_receipts\matlab_exact_clip_metrics.json`
- Create external-only: `E:\Claude_allow\Download\s12-professional-comparison-dashboard-v1\tool_receipts\mosqito_exact_clip_metrics.json`

**Interfaces:**
- MATLAB: `receipt = run_exact_anchor_professional_metrics(manifestPath, outputRoot)`; 18 independent signals, exact 5 s clips, six Audio Toolbox functions, no order call.
- Python: `python run_exact_mosqito_metrics.py --manifest <manifest> --output <external-json> --python E:\AI_Tools\Other\S12StageN\mosqito-venv\Scripts\python.exe`.

- [ ] **Step 1: Write failing receipt tests**

测试必须拒绝 candidate-only receipts、missing reference metrics、wrong clip SHA、missing tool provenance、proxy labels under professional fields、absolute SPL claims；必须接受 explicit `ORDER_COMPARISON_NOT_QUALIFIED`。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_receipts.py -q`

Expected: FAIL because exact receipt validator/runner does not yet exist。

- [ ] **Step 3: Implement MATLAB runner and isolated MoSQITo runner**

MATLAB runner复用 `s12_psychoacoustic_analysis.m` 的真实 Audio Toolbox 调用，对每个 reference/candidate 分别输出 loudness、sharpness、roughness、fluctuation、TNR 和 prominence；记录 MATLAB release/function availability、input SHA、window、resampling and digital-domain calibration。MoSQITo runner 复用 `mosqito_adapter.compute_mosqito_metrics`，对同一 18 个 signal 输出版本、函数、结果和 digital-domain limitation；不可导入时明确 `MOSQITO_UNAVAILABLE`，不回退 proxy。

- [ ] **Step 4: Execute both real toolchains**

Run MATLAB through the existing MATLAB Desktop MCP session, writing only external receipts under `E:\Claude_allow\Download\s12-professional-comparison-dashboard-v1\tool_receipts`; run isolated MoSQITo venv for the same 18 WAVs. Expected: 9 pairs with reference/candidate/delta for each professional metric；Order remains not qualified。

- [ ] **Step 5: Validate receipts and commit code**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_receipts.py -q`; commit only scripts/tests, not external audio or external raw receipt files。

### Task 3: Unified pair metrics, plain-language diagnosis and R2 candidate plan

**Files:**
- Modify: `tools/sound_sim/s12/real_reference/professional_clip_analysis.py`
- Create: `tools/sound_sim/s12/tests/test_s12_professional_diagnosis.py`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/professional_pair_metrics.json`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/professional_plain_language_diagnosis.json`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/r2_diagnostic_parameter_plan.json`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/r2_diagnostic_candidate_results.json`

**Interfaces:**
- `build_professional_pair_metrics(clip_integrity, matlab_receipt, mosqito_receipt, proxy_results) -> dict[str, Any]`
- `build_plain_language_diagnosis(pair_metrics) -> dict[str, Any]`
- `build_r2_diagnostic_plan(pair_metrics) -> dict[str, Any]`
- `build_bounded_candidate_results(plan) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests**

测试要求三类来源分列；每对都有 ref/candidate/delta/unit/uncertainty；不生成相似度百分比；诊断必须包含 Hellcat/RX-7/Ferrari 的中文方向；每锚点只有一个参数组和不超过 64 个 candidate specs；candidate before/after 未实际渲染时必须是 null，不能冒充改善。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_diagnosis.py -q`

- [ ] **Step 3: Implement frequency/transient/diagnosis aggregation**

用 8 个指定频带生成 reference/candidate power 和 delta；用 Welch/STFT 生成可下采样的 spectrum/spectrogram residual；输出 attack/decay/crest/spectral flux/event count；诊断文字使用普通中文，且把 source class/microphone/order uncertainty 放在每条建议旁。

- [ ] **Step 4: Implement bounded R2 candidate plan**

Ferrari 仅 `metallic_high_order_envelope_mid_band`；Hellcat 仅 `pressure_attack_blower_intake_balance`；RX-7 仅 `rotary_housing_turbo_distribution`。每组生成最多 64 个确定性规格，状态 `WAITING_FOR_JOVI_GUIDED_REVIEW`，不渲染、不写声源、不修改 Order/event timing、不降低门限。

- [ ] **Step 5: Run GREEN and write JSON artifacts**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_diagnosis.py -q`; write the four JSON artifacts with statuses `R2_DIAGNOSTIC_CANDIDATE_READY`, `WAITING_FOR_JOVI_GUIDED_REVIEW`, `NOT_R1_QUALIFIED`, `NOT_PROFILE_FREEZE_READY`。

### Task 4: Chinese Professional Comparison Dashboard v1

**Files:**
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/index.html`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/dashboard.js`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/dashboard.css`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/Jovi_Guided_Feedback.json`
- Create: `tools/sound_sim/s12/tests/test_s12_professional_dashboard.py`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/S12_Professional_Comparison_Report.md`

**Design direction:** dark industrial acoustic observatory: graphite canvas, amber reference traces, cyan candidate traces, red gate warnings, compact data cards, no generic questionnaire layout. All copy is Chinese; no external font/CDN dependency.

**Interfaces:**
- Dashboard loads `professional_pair_metrics.json`, `professional_plain_language_diagnosis.json`, `r2_diagnostic_parameter_plan.json`, `r2_diagnostic_candidate_results.json` from the same directory and uses absolute `file:///E:/Claude_allow/...` audio URLs from the metadata.
- `window.S12Dashboard.exportFeedback()` returns `Jovi_Guided_Feedback.json` with package SHA, trial/file IDs, software agreement, identity 0–100, realism 0–100, scenario-filtered problem list, preference and notes.

- [ ] **Step 1: Write failing static/UI tests**

测试检查：页面存在每个 reference/candidate player、duration/SHA/status、R1/R2/R3、mic uncertainty、MATLAB/MoSQITo/Proxy 分栏、8 频带图、spectrum/spectrogram panels、diagnosis/candidate cards、简化反馈字段；`canplaythrough`/`duration>0`/`sha_status`/required files gate 缺一不可提交；0:00 音频拒绝；不显示总相似度百分比。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_dashboard.py -q`

- [ ] **Step 3: Implement dashboard**

用原生 HTML/CSS/JS 生成可双击打开的中文页面；顶部显示证据门和工具来源，左侧车型/试次导航，中部播放器与频谱/spectrogram，右侧诊断/参数组，底部反馈表。场景不含怠速/换挡/回火时隐藏对应问题或显示“当前片段不包含”。导出只生成绑定反馈 JSON，不调用 Python/MATLAB、不修改 source。

- [ ] **Step 4: Run static/dashboard tests and local smoke**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_professional_dashboard.py -q`; run Node syntax check `node --check dashboard.js`; verify `index.html` can be opened from the dashboard directory without Docker/server。

### Task 5: Report, package validation, R2 candidate gate and final verification

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/reports/runtime/S12_Real_Sound_Closed_Loop_Final_Report.md`
- Create: `docs/superpowers/plans/2026-08-23-s12-professional-comparison-dashboard-r2-diagnostic-tuning.md`

- [ ] **Step 1: Write integration assertions**

断言新 dashboard 不覆盖旧 `anchor_ab_zh_v1`；9 对 reference/candidate 都有指标或明确工具阻塞；R2 candidate plan 不超过 64/anchor；Jovi feedback 初始为空且 file-ID/SHA 绑定；Track‑P 和 R1 门未放宽。

- [ ] **Step 2: Run focused validation**

Run:
```powershell
python -m pytest tools/sound_sim/s12/tests/test_s12_professional_clip_analysis.py tools/sound_sim/s12/tests/test_s12_professional_receipts.py tools/sound_sim/s12/tests/test_s12_professional_diagnosis.py tools/sound_sim/s12/tests/test_s12_professional_dashboard.py -q
python -m compileall -q tools/sound_sim/s12/real_reference
node --check tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/dashboard.js
git diff --check
```

- [ ] **Step 3: Run Stage N/Q/R/S and full S12 verification**

Run Stage N focused, Stage Q/R/S focused, full `tools/sound_sim/s12/tests`, Track‑P pytest/independent guard, JSON/package validation. Expected: no frozen Track‑P paths changed, no raw media tracked, Order status remains not qualified。

- [ ] **Step 4: Commit and push when network permits**

`git add tools/sound_sim/s12/real_reference tools/sound_sim/s12/tests tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1 tasks/reports/runtime/S12_Real_Sound_Closed_Loop_Final_Report.md tasks/todo.md docs/superpowers/plans/2026-08-23-s12-professional-comparison-dashboard-r2-diagnostic-tuning.md && git commit -m "feat(s12): add professional comparison dashboard" && git push origin agent/s12-stage-q-real-reference-calibration`

## Self-review against the objective

- Phase 1 evidence table: Tasks 1–3 with explicit MATLAB/MoSQITo/Legacy Proxy/Not Qualified columns.
- Phase 2 exact clips: Task 2 invokes both signals of all 9 pairs; no candidate-only shortcut.
- Phase 3 Dashboard: Task 4 displays audio, SHA, evidence, uncertainty, metrics, charts, diagnosis, parameters and feedback.
- Phase 4 simplified Jovi feedback: Task 4 implements only software agreement, identity, realism, problem, preference and notes, with hard playback gates.
- Phase 5 R2 candidate plan: Task 3 limits one parameter group/anchor and 64 specs, with no source changes or Profile Freeze.
- Frozen boundaries and no total similarity percentage: Global Constraints and Task 5 integration assertions.

## Execution receipt

- [x] Exact clip integrity and Legacy Proxy: 9 pairs / 18 clips, SHA/duration/file-ID checks passed.
- [x] MATLAB R2026a Audio Toolbox: 18 exact clips executed and validated.
- [x] MoSQITo 1.2.1 isolated run: 18 exact clips executed and validated; fluctuation unsupported is explicit null.
- [x] Professional metrics/diagnosis/candidate plan: three domains separated; 64 specs per anchor; no source writes.
- [x] Chinese Dashboard, simplified Jovi feedback template, static contract, Node syntax and Chromium audio smoke passed.
- [x] Simplified `Jovi_Guided_Feedback.json` importer added with audio gate, SHA/file-ID, score-range and vehicle/problem summary validation; no automatic tuning authority.
- [ ] Jovi guided review and any later manual R2 candidate render remain external next steps; R1/Order/Profile Freeze remain closed.

## Long-window extension receipt

- [x] Existing 5s candidates were measured at 6.25s; no artificial looping was used.
- [x] External 60s synthetic complete-cycle candidate package built; 15/30s windows sliced from real long references and the complete cycle.
- [x] 18 long pairs (9×15s + 9×30s) received Legacy Proxy, MATLAB and MoSQITo metrics; long Dashboard added without replacing 5s baseline.
- [ ] Jovi long-window guided review remains pending.
