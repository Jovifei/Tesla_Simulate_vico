# Stage AF-R 证据完整性与原工作台修复报告（2026-09-07）

状态：`IMPLEMENTED / VERIFIED / DIAGNOSTIC_ONLY / WAITING_FOR_JOVI`

## 1. 范围与基线

本轮从 `origin/main=ba13ced7f9eafdf0e4e4287c9c23eefc838c53f8` 建立独立 worktree：

```text
E:\Tesla_speed\worktrees\stage-af-r-evidence-20260907
branch: local/stage-af-r-evidence-20260907
```

没有 reset、覆盖已有 review package 或合并到 `main`。`EngineAcoustics` 仍是已试听声音 authority；Stage AF-R 只在其周围增加证据、fit/reference 闭合和原工作台的 fail-closed 保护，没有启用 Stage AE 默认 renderer、没有新建试听后台、没有改 Track-P/FVM/PTR/Radiation、没有做 Android/ESP32。

## 2. 本轮修复的审计问题

| 风险 | Stage AF-R 行为 | 主要入口 |
| --- | --- | --- |
| 页面写死旧分数、车型和 PASS | 页面从 `dashboard_contract.json` 读取 fit/measurement/parameter 状态；缺失值显示 `NOT_MEASURED` / `NOT_FITTED`，不再写死 `0.880`、`0.64835` 或 PASS | `stage_ad/audition_dashboard_template.html`、`stage_ad/build_unified_dashboards.py` |
| fit/reference 漂移 | fit v4 必须包含四个 fit scene 的 `reference_sources`；build 按 source filename/SHA 校验，漂移或缺失立即停止；fit 与 audition-only Reference 用 `fit_required` 区分 | `stage_af/physical_closed_loop.py`、`stage_af/build_existing_dashboards.py` |
| 陈旧目标字节回退 | `--reference-root` 省略时不搜索 output root；source 缺失且目标已有旧字节时拒绝，不把 stale destination 当 Reference | `stage_af/build_existing_dashboards.py` |
| H0 只和当前代码比较 | `compare_h0_with_legacy()` 从固定 Git commit 加载旧 `EngineAcoustics`，注入相同 IR、输入、seed 后逐 PCM 比较；IR 搜索顺序固定为 `new → archive → smooth → root` | `stage_af/package_integrity.py`、`stage_ad/engine_sim_acoustics.py` |
| 页面类别/参考状态不实 | `cruise` 从实际 scenes 计数；`hasReference()` 只在实际嵌入/绑定字节存在时开放 B 轨；缺参考场景不会伪造 B 轨；FFT 轴依据 sample rate/Nyquist | `stage_ad/audition_dashboard_template.html` |
| 包发布半成品或覆盖旧包 | 每次要求安全 package id；先写 `.stage_af_r_staging/<id>`，校验所有 artifact SHA 后原子 rename；已存在 id 或失败残留均拒绝/清理 | `stage_af/package_integrity.py`、`stage_af/build_existing_dashboards.py` |
| 产物无法追溯 | v1 manifest、v5 binding 和 dashboard contract 包含 package/candidate/vehicle/flags/seed、renderer/IR identity、fit identity、Reference source/SHA/rights、逐场景输入/候选/参考/HTML 记录及 package gain policy | 同上 |

## 3. 原有试听链没有改变

```text
VehicleState / existing scene trace
→ stage_ad.EngineAcoustics
→ original build_unified_dashboards.py
→ original HTML A/B workbench
→ existing serve_dashboards.py
```

Stage AF-R 的 builder 只把 `TunableEngineAcoustics` 作为原 renderer 的显式 adapter 注入；它没有实现第三套声音 renderer 或新后台。包记录的 `package_gain_db=0.0`、`gain_policy=no_additional_package_gain`，不得用 master/global gain 掩盖差异。

## 4. 已验证的 smoke 产物

为验证发布/页面链路生成了新的、未覆盖旧包的 Hellcat baseline smoke package：

```text
E:\Tesla_speed\review_packages\stage-af-r-smoke-20260907\smoke-hellcat-r3
```

它使用已有 H0 Reference 字节作为显式 `--reference-root`，不是新下载素材，也不是四车型最终包。包内 10 个 candidate WAV、8 个可用 Reference 绑定、2 个没有 Reference 的自测场景、`index.html`、`index_standalone.html`、`dashboard_contract.json`、`stage_af_binding.json` 和 `audition_manifest.json` 均生成。

现场重算结果：manifest SHA=`8dec1792745703bf014867ba0f3ced2201897a4931072152ede480fcc46f48b4`，32 个列举 artifact 全部 SHA 匹配；contract=`NOT_FITTED / NOT_MEASURED`、Reference level=`AUDITION_ONLY`；IR rights=`UNVERIFIED_LOCAL_ASSET`。浏览器访问 `http://localhost:20088/` 时页面显示 `NOT_MEASURED`、动态场景计数 `10/2/1/1/3/3`、当前 package 导航端口 `20088–20091`，真实 source label 为本地已有字节；console error 为 0。该 smoke 仅证明链路和证据契约，不能升级为真实感、人耳或 OEM 结论。

## 5. 验证证据

- AF-R/AF/AD/Track-P 聚焦：`77 passed, 1 warning`；
- 当前完整 S12：`1476 passed, 2 skipped, 1 warning, 232 subtests passed`，退出码 0；
- `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015`：通过；仅有既有 Stage-K 测试字符串无效转义 warning；
- `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`：冻结 180 文件/2 符号，冻结路径改动 0；
- `git diff --check`：通过；
- 原 review server 的慢客户端并发回归：threaded server 第二请求 HTTP 200；single-thread negative control 按预期超时；
- 页面反馈导出 schema=`s12.stage_af.feedback.v1`，包含 package/candidate/vehicle/contract SHA 与 `WAITING_FOR_JOVI_FEEDBACK`。

## 6. 未完成边界与下一位 Agent 规则

本轮没有宣称任何车型 `Human PASS`、`OEM_MATCH`、`CALIBRATED`、`Profile Freeze` 或 R1。四车型真实 Reference fit 仍需调用者显式提供已经治理的 `--fit-root` 与 `--reference-root`；缺失任一 fit scene、Reference/IR 或 SHA 漂移必须停止，不能用单位脉冲、旧 output root 或默认参数替代。

生成正式新试听包时必须使用新的 `--package-id`、新的输出目录和同一 fit/render 的车型、seed、numerical fixes、IR 与 Reference identity；沿用原工作台与 `serve_dashboards.py`，生成后停止并等待 Jovi 的实际 A/B 听感反馈，不自动继续调参。

最终分支 commit SHA 以现场 `git rev-parse HEAD` 为准；本报告所在提交仅属于上述隔离分支，不能作为 main 已合并证明。
