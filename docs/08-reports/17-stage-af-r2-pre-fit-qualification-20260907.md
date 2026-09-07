# Stage AF-R2 预拟合资格与证据范围报告（2026-09-07）

状态：`LOCAL_VERIFIED / WAITING_FOR_EXACT_PUSHED_HEAD_CI`

## 1. 现场远端与执行边界

执行前已在 `E:\Tesla_speed\prj` 运行 `git fetch origin --prune`。现场远端当前为：

```text
origin/main = ba13ced7f9eafdf0e4e4287c9c23eefc838c53f8
PR #15      = open / Draft
PR head    = 49bb97756c1f78baa9a25ae1e78168ebb72d258d
PR base    = main@ba13ced7f9eafdf0e4e4287c9c23eefc838c53f8
```

R2 worktree：

```text
E:\Tesla_speed\worktrees\stage-af-r2-qualification-20260907
branch: local/stage-af-r2-qualification-20260907
```

在本轮实现前，匹配 PR head 的 Actions 为 `34110365821`（S12 Stage AF Physical Closed Loop）和 `34110365538`（S12 Stage Y Open-Source Integration Audit），两者现场状态均为 `in_progress`。R2 资格必须在最终推送 SHA 上重新读取，不能引用本机历史计数或旧 SHA 的 CI。

禁止范围保持不变：不启用 Stage AE、不创建新 renderer/backend、不改 Track-P/PTR/Radiation、不使用 global/master gain、不做四车型 fit、自动调参、Android/ESP32，也不宣称 Human PASS/OEM/R1。

## 2. AF-R2 实现内容

### 2.1 三段 dependency identity

`stage_af/package_integrity.py` 现在分别输出：

| scope | 内容 | fit 影响 |
| --- | --- | --- |
| `audio_runtime_fingerprint` | `stage_ad/engine_sim_acoustics.py`、`stage_af/partitioned_convolver.py` | 改变可能改变 PCM，fit 失效 |
| `fit_algorithm_fingerprint` | `physical_closed_loop.py`、`spectral_guard.py`、`fit_cli.py` | objective/search/guard 改变，fit 失效 |
| `package_ui_fingerprint` | AF builder、原 dashboard builder/template、原 `serve_dashboards.py` | 只改页面/服务不使 fit 失效 |

`fit_identity_projection()` 只比较 audio runtime、fit algorithm、renderer、IR、车型、采样率和 flags，不比较 package UI；因此页面修复不会无理由使相同声音的 fit 失效。由于 identity 合同发生实质变化，fit schema 升为 `s12.stage_af.physical_fit.v5`，旧 v4 直接拒绝。

### 2.2 fit snapshot 与 source receipt

fitted package 会把 source fit JSON 原始字节复制到：

```text
<vehicle>/evidence/fit/final_fit.json
```

snapshot 记录 source path/SHA、snapshot path/SHA、schema、fit self SHA，并作为 `fit:snapshot` artifact 进入 manifest；删除 source 后仍可只凭 snapshot bytes 通过自校验。

package/binding/contract/manifest 同时记录 Git source receipt：`repository`、`git_head`、`base_main`、`dependency_dirty`、`source_policy`、`source_status`、`promotable` 和 `promotion_status`。正式 build 默认要求 tracked source clean；只有显式 `--allow-dirty-dev` 才接受脏 tracked source，并写入 `DEV_DIRTY_SOURCE / NOT_PROMOTABLE`。

### 2.3 package/UI/status hardening

`--vehicle hellcat` 时，导航只枚举当前 package 实际选择的车型，不能链接到历史 8088–8091。现有 Tailwind 仍从外网加载，因此 HTML/contract/manifest 明确标记 `AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY`，没有伪称完全 self-contained。

页面和 contract 拆开 `fit_status`、`fit_metric_status`、`human_status`；fitted diagnostic 可写 `FITTED` + `FIT_DIAGNOSTIC_DISTANCE_AVAILABLE` + `WAITING_FOR_JOVI_FEEDBACK`，但永远不能生成 Human PASS/OEM/R1。

### 2.4 H0 fixed Git oracle

`h0_oracle_cases()` 与 `compare_h0_with_legacy()` 覆盖三种窗口：steady/body、shift、afterfire。shift/afterfire 事件时间被约束在实际输出 duration 内；每个窗口都用固定 pre-fix Git implementation、同一 IR bytes、同一 seed、同一 RPM/throttle input、`numerical_fixes=[]`，要求 PCM byte equality。oracle 只读取固定旧实现，不改生产声音。

## 3. 本地验证（R2 代码阶段）

最终本地代码验证已经完成：AF-R2/AF/AD 受影响测试 `55 passed, 2 warnings`；完整 S12 `1486 passed, 2 skipped, 3 warnings, 232 subtests passed`，退出码 0。开发 smoke 使用显式 `--allow-dirty-dev`，输出：

```text
E:\Tesla_speed\review_packages\stage-af-r2-qualification-smoke-20260907\hellcat-r2-dev-smoke
```

现场 smoke 检查确认：

- `source_status=DEV_DIRTY_SOURCE`、`promotion_status=NOT_PROMOTABLE`；
- `repository=Jovifei/Tesla_Simulate_vico`、`git_head=49bb977…`、`base_main=ba13ced…`；
- 单车型 contract 只含 `hellcat` 导航 `http://localhost:21088/`，无 `21089` 或历史 `8088`；
- `fit_status=NOT_FITTED`、`fit_metric_status=NOT_MEASURED`、`human_status=WAITING_FOR_JOVI_FEEDBACK`；
- 10 candidate WAV、8 个可用 Reference 绑定、2 个无 B 轨场景，原工作台页面正常生成；
- 该 smoke 是 `NOT_PROMOTABLE` 开发验证，不是正式试听包。

正式 clean package 必须在提交后的 clean tracked source 上重新生成；若 source receipt 报告 dirty，R2 仍不成立。

## 4. 验证与停止门

最终代码必须运行：

```powershell
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_r_integrity.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_physical_closed_loop.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_numerical_fixes.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_ad_closed_loop.py
python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015
python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py
git diff --check
python -m pytest -q tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests
```

随后从最终 clean（或显式 dev）提交 push 隔离分支，按 exact pushed SHA 读取 GitHub Actions。只有两类远端 CI 均为 `completed / success`，且 source receipt、fit snapshot、manifest、H0 oracle 与单车型页面证据闭合，才可标记：

```text
STAGE_AF_R2_REMOTE_QUALIFIED
```

否则保持 `WAITING_FOR_EXACT_HEAD_CI` 并停止，不进入 R3。

## 5. R3 预置但尚未执行

R2 绿色后才生成三个全新、不可覆盖的 Hellcat package：

```text
H0 = []
H1 = ["cycle_phase"]
H2 = ["causal_convolution", "causal_delays", "causal_derivative", "shift_cut"]
```

三包共用相同 vehicle/seed/IR/scene input/governed Reference。逐 WAV 只允许 `BYTE_IDENTICAL`、`EXPECTED_DIFFERENCE_WITH_EXPLAINED_CAUSE` 或 `UNEXPECTED_DRIFT`；后者立即停止。正确归因是 H0↔H1 的 cycle-phase effect 与 H0↔H2 的 time-processing-group effect，不能写成“H1→H2 只是增加时间修正”。R3 生成后立即停止并等待 Jovi 试听，不自动 fit、不扩车型、不进入 Android。
