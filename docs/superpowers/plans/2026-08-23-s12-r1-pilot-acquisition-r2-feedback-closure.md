# S12 Stage Q-R1 Pilot Acquisition and R2 Human Feedback Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 完成现有中文 R2/R3 A/B 反馈入口校验与导入准备，并建立 Hellcat 默认 R1 单车试点的授权、采集、同步和 fail-closed 预检链；没有真实文件时明确停在 `WAITING_FOR_R1_PILOT_DELIVERY`。

**Architecture:** A 线新增独立的 anchor A/B 包校验器和反馈适配器，读取外部包、只写 SHA/评分/备注/问题分类和有限诊断建议，不触碰声源。B 线新增 R1 试点预检模块，分离 rights scope、SHA、状态时间同步和既有 `raw_audio_intake` R1 合同；预检只产生仓库元数据，不复制原始媒体。两条线都通过 CLI 生成中文报告和 JSON 收据，所有不完整输入均 fail-closed。

**Tech Stack:** Python 3、标准库 `json/csv/wave/hashlib/pathlib`、现有 `tools.sound_sim.s12.real_reference` 合同、pytest；外部原始媒体只允许 `E:\Claude_allow\Download`，不使用 Docker/YouTube 下载器，不把原始音频写入 Git。

## Global Constraints

- 停止继续优化 YouTube 下载器；24/24 可解码仍保持 R3。
- R1 必须有合法原始 WAV/FLAC、精确车型/原厂状态、工况、同步 RPM、Load/Throttle、Gear/shift、麦位、采样率、录音设备/AGC、来源和授权。
- 商业 SFX 普通许可不得自动当作算法开发许可；steady-RPM 文件名不得当时间 trace；不得猜测状态；不得将版权原始音频复制进 Git。
- R2/R3 结果只允许有限频谱/响度/心理声学/主观诊断和有界参数建议；不得进入 Order hard gate、自动阶次调参或 Profile Freeze。
- 没有 Jovi 真实反馈不得修改声源；Stage S 每次只允许一车、一场景问题、一个参数组，最多三轮。
- 默认 R1 试点为 Hellcat，可由 Jovi 指定更易获得且精确原厂的车型替换。

---

### Task 1: A 线 anchor_ab_zh_v1 完整性校验器

**Files:**
- Create: `tools/sound_sim/s12/real_reference/anchor_ab_validate.py`
- Create: `tools/sound_sim/s12/tests/test_s12_anchor_ab_validate.py`
- Create: `tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1/anchor_ab_validation.json`

**Interfaces:**
- `validate_anchor_ab_package(package_root: Path) -> dict[str, Any]`
- CLI: `python -m tools.sound_sim.s12.real_reference.anchor_ab_validate --package-root <external-package> --output <repo-json>`
- 返回 `status`, `manifest_sha256`, `receipt_sha256`, `trial_count`, `clip_count`, `vehicle_counts`, `page_checks`, `sha_checks`, `errors`。

- [ ] **Step 1: Write failing tests**

测试必须覆盖：真实 v1 包通过；manifest SHA、receipt SHA、页面缺失、重复 trial、18 个试听片段任一 SHA 错误均拒绝；不允许把外部原始 WAV 路径当成包内试听片段。

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_anchor_ab_validate.py -q`

Expected: FAIL because `anchor_ab_validate` does not yet exist。

- [ ] **Step 3: Implement minimal validator**

读取 `anchor_ab_zh_manifest.json`、`anchor_ab_zh_receipt.json`、`index.html`、`README_中文.md`；校验 `schema_version`、9 个 trial、Ferrari/Hellcat/RX-7 各 3 条、18 个 WAV 存在且 SHA 匹配、receipt 中 manifest/readme/trial SHA 匹配、页面包含包 SHA、9 个 trial ID、中文导出字段和 `automatic_tuning_eligible=false/profile_update=FORBIDDEN`。所有路径必须解析到 `package_root` 内的试听副本。

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_anchor_ab_validate.py -q`

Expected: all validator tests pass；随后运行 CLI 对 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1` 生成仓库外部媒体不复制的校验 JSON。

- [ ] **Step 5: Commit**

`git add tools/sound_sim/s12/real_reference/anchor_ab_validate.py tools/sound_sim/s12/tests/test_s12_anchor_ab_validate.py tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1/anchor_ab_validation.json && git commit -m "feat(s12): validate anchor chinese ab package"`

### Task 2: A 线真实反馈导入、问题分类和有限建议

**Files:**
- Create: `tools/sound_sim/s12/real_reference/r2_human_feedback.py`
- Create: `tools/sound_sim/s12/tests/test_s12_r2_human_feedback.py`
- Create: `tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1/S12_R2_Human_Feedback_Report.md`
- Create: `tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1/parameter_recommendations.json`
- Create: `tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1/feedback_gate.json`

**Interfaces:**
- `validate_anchor_feedback(feedback_path: Path, package_root: Path) -> dict[str, Any]`
- `classify_feedback_problems(trials: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]`
- `build_limited_parameter_recommendations(receipt: Mapping[str, Any]) -> dict[str, Any]`
- `write_feedback_outputs(package_root, output_dir, feedback_path=None) -> dict[str, Path]`

- [ ] **Step 1: Write failing tests**

测试覆盖：当前没有反馈时输出等待态且 `recommendations=[]`；完整导出 JSON 必须匹配 package SHA、9 个 trial、18 个 SHA、评分 1–5/不确定、偏好和 listener；草稿、漏 trial、SHA 错、`automatic_tuning_eligible=true`、`profile_update` 非 FORBIDDEN、恶意参数值均拒绝。问题分类至少覆盖车型身份、低频、机械/怠速、加速、换挡、回火、合成器伪影和整体偏好。

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_r2_human_feedback.py -q`

Expected: FAIL because the adapter and report functions do not yet exist。

- [ ] **Step 3: Implement minimal fail-closed adapter**

适配 anchor 页面导出的 `trials` 格式，不修改旧 `feedback_import.py`。完整反馈才生成 `VALIDATED_R2_HUMAN_FEEDBACK` 或 `VALIDATED_R3_HUMAN_FEEDBACK` 收据；R3 页面包只能生成诊断分类和有限建议，禁止任何声源写入。建议只输出参数组/方向待确认/不确定性和 `parameter_changes=0`，不输出数值调音或 Profile 状态。

- [ ] **Step 4: Run tests and generate waiting artifacts**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_anchor_ab_validate.py tools/sound_sim/s12/tests/test_s12_r2_human_feedback.py -q`

Then run the CLI without `--feedback` against v1. Expected: package validation PASS; `S12_R2_Human_Feedback_Report.md` status `WAITING_FOR_JOVI_HUMAN_FEEDBACK`; empty `parameter_recommendations.json`; no source/profile modifications。

- [ ] **Step 5: Commit**

`git add tools/sound_sim/s12/real_reference/r2_human_feedback.py tools/sound_sim/s12/tests/test_s12_r2_human_feedback.py tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1 && git commit -m "feat(s12): add bounded chinese feedback import"`

### Task 3: B 线供应方/车主交付、授权和采集模板

**Files:**
- Create: `tools/sound_sim/s12/real_reference/R1_VENDOR_OWNER_CONTACT_REQUEST_ZH.md`
- Create: `tools/sound_sim/s12/real_reference/R1_AUDIO_OBD_CAN_CAPTURE_GUIDE_ZH.md`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/spec.template.json`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/rights.template.json`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/rpm.csv`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/load_throttle.csv`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/gear_shift.csv`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/sha256.txt`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/README_中文.md`

**Interfaces:**
- Templates use `recording_id`, `vehicle_id`, `scenario`, external relative paths, explicit units and rights scope keys consumed by Task 4.

- [ ] **Step 1: Write failing template contract tests**

测试要求模板包含 Hellcat 默认值、三状态文件字段和单位、授权用途清单、`raw_media_stored_outside_git=true`，且不包含任何真实音频或猜测数值。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_r1_pilot_templates.py -q`

Expected: FAIL because templates/guides do not yet exist。

- [ ] **Step 3: Add Chinese templates and acquisition guides**

联系模板必须逐项询问精确原厂 trim、录音所有权、允许本地分析/派生特征/Comparator/A-B/有界调音的授权；采集说明规定共同时间基准、硬件/软件触发或可审计 clap/marker、OBD/CAN 时间戳、禁止人工猜测和静默外推。

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_r1_pilot_templates.py -q`

- [ ] **Step 5: Commit**

`git add tools/sound_sim/s12/real_reference/R1_VENDOR_OWNER_CONTACT_REQUEST_ZH.md tools/sound_sim/s12/real_reference/R1_AUDIO_OBD_CAN_CAPTURE_GUIDE_ZH.md tools/sound_sim/s12/real_reference/templates && git commit -m "docs(s12): add r1 pilot acquisition templates"`

### Task 4: B 线 rights scope、SHA 和状态同步验证器

**Files:**
- Create: `tools/sound_sim/s12/real_reference/r1_pilot.py`
- Create: `tools/sound_sim/s12/tests/test_s12_r1_pilot_preflight.py`

**Interfaces:**
- `validate_rights_scope(recording_root: Path, spec: Mapping[str, Any]) -> dict[str, Any]`
- `validate_sha256_manifest(recording_root: Path, required_files: Sequence[str]) -> dict[str, Any]`
- `validate_state_sync(recording_root: Path, spec: Mapping[str, Any]) -> dict[str, Any]`
- `run_r1_pilot_preflight(pilot_root: Path, recording_id: str, output_dir: Path) -> dict[str, Any]`
- CLI: `python -m tools.sound_sim.s12.real_reference.r1_pilot --pilot-root E:\Claude_allow\Download\s12-r1-pilot --recording-id hellcat_full_pull_01 --output-dir <repo-report-dir>`

- [ ] **Step 1: Write failing tests**

测试覆盖 rights.json 缺用途/普通 SFX 许可/PDF 需人工审查；sha256.txt 缺文件或 SHA 错；状态列缺失、单位不符、时间不递增、窗口外、长度不一致、CSV 猜测字段；完整空 fixture 必须返回 `WAITING_FOR_R1_PILOT_DELIVERY`，不能返回 ready。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_r1_pilot_preflight.py -q`

Expected: FAIL because the preflight module does not exist。

- [ ] **Step 3: Implement validators**

rights validator 只接受明确的 `local_analysis`, `derived_features`, `comparison`, `human_audition`, `bounded_tuning` 授权；PDF 没有机器可审计 scope 时返回 `MANUAL_REVIEW_REQUIRED`。state validator 复用现有 raw-audio metadata/state 合同，严格递增时间、单位、窗口覆盖、连续量/离散事件边界和 SHA；preflight 汇总 rights/SHA/state/raw-intake 四个 gate，所有 gate PASS 才是 `R1_PILOT_READY`。

- [ ] **Step 4: Run GREEN and verify real empty fixture**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_r1_pilot_preflight.py -q`

Then run the CLI against `E:\Claude_allow\Download\s12-r1-pilot\hellcat_full_pull_01` when absent. Expected: all requested JSON/report files are created as waiting/blocked, no raw file is copied, exit code nonzero for not-ready。

- [ ] **Step 5: Commit**

`git add tools/sound_sim/s12/real_reference/r1_pilot.py tools/sound_sim/s12/tests/test_s12_r1_pilot_preflight.py && git commit -m "feat(s12): add r1 pilot preflight gates"`

### Task 5: B 线报告、空 fixture 和端到端等待收据

**Files:**
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/rights_scope_validation.json`
- Create: `tools/sound_sim/s12/real_reference/templates/s12_r1_pilot_hellcat/state_sync_validation.json`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/S12_R1_Pilot_Acquisition_Report.md`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/r1_pilot_preflight.json`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/rights_scope_validation.json`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/state_sync_validation.json`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/comparison_results.json`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/parameter_recommendations.json`
- Create: `tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat/feedback_gate.json`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Write failing integration assertions**

断言空试点输出所有最终文件、报告中文、状态是 `WAITING_FOR_R1_PILOT_DELIVERY`、comparison cases/parameter recommendations 为空、`automatic_tuning_eligible=false`、`profile_candidate_ready=false`，并且 Git 跟踪列表没有 raw audio/state fixture。

- [ ] **Step 2: Run RED**

Run: `python -m pytest tools/sound_sim/s12/tests/test_s12_r1_pilot_end_to_end.py -q`

Expected: FAIL until Task 4 CLI/report writer exists。

- [ ] **Step 3: Implement report writer and waiting artifacts**

生成用户指定的 `S12_R1_Pilot_Acquisition_Report.md`、`r1_pilot_preflight.json`、`rights_scope_validation.json`、`state_sync_validation.json`、`comparison_results.json`、`parameter_recommendations.json`；comparison 明确写 `NOT_RUN_WAITING_FOR_R1`，建议明确 `WITHHELD_MISSING_R1_PILOT`，不调用 MATLAB、不改声源。

- [ ] **Step 4: Run full focused verification**

Run:
```powershell
python -m pytest tools/sound_sim/s12/tests/test_s12_anchor_ab_validate.py tools/sound_sim/s12/tests/test_s12_r2_human_feedback.py tools/sound_sim/s12/tests/test_s12_r1_pilot_templates.py tools/sound_sim/s12/tests/test_s12_r1_pilot_preflight.py tools/sound_sim/s12/tests/test_s12_r1_pilot_end_to_end.py -q
python -m compileall -q tools/sound_sim/s12/real_reference
git diff --check
```

Expected: all focused tests pass; no raw media enters Git; empty pilot remains waiting。

- [ ] **Step 5: Commit and push**

`git add docs/superpowers/plans/2026-08-23-s12-r1-pilot-acquisition-r2-feedback-closure.md tools/sound_sim/s12/real_reference tools/sound_sim/s12/tests tasks/reports/runtime/s12-stage-q-real-reference/r1-pilot-hellcat tasks/reports/runtime/s12-stage-s-human-calibration/anchor_ab_zh_v1 tasks/todo.md && git commit -m "feat(s12): prepare r1 pilot and r2 feedback closure" && git push origin agent/s12-stage-q-real-reference-calibration`

## Self-review against the request

- A1 manifest/page/18 SHA：Task 1。
- A2 等待/导入真实 JSON：Task 2；没有反馈时不会读取或修改声源。
- A3 评分、偏好、备注、问题分类：Task 2 canonical receipt/report。
- A4 仅 R2/R3 有限建议：Task 2 固定 `parameter_changes=0`、无 Order/Profile 权限。
- B1 contact request、B2 rights checker、B3 audio/OBD/CAN、B4 time-sync、B5 preflight、B6 scenario template、B7 empty fixture/fail-closed：Tasks 3–5。
- 收到真实文件后的 MATLAB/Comparator/A-B/调音流程：由 preflight 的 `R1_PILOT_READY` 门禁解锁；本轮没有真实文件，不伪造后续收据。
