# Stage AI 本地真实参考闭环验收（2026-09-16）

## 结论边界

本记录对应本机真实素材执行，不把远端交接测试或试听页面当作声学 Human PASS。源码实现保持远端交接 HEAD 不变；本分支只提交本验收记录。最终状态为：

- `STAGE_AI_LOCAL_REFERENCE_EXECUTION_COMPLETE`
- `QUALIFIED_ABC_READY_FOR_JOVI`（Ferrari 458、Nissan GT-R R35、Aventador 的 B 可用；其余车型按证据禁用或保留既有阻塞）
- `WAITING_FOR_JOVI_ACOUSTIC_REVIEW`

当前不声明 OEM 同步、Profile Freeze 或“剩余 20% 已解决”。

## 版本、输入与不可变边界

- 源分支：`feature/stage-ai-measured-feedback-20260916`
- 源 HEAD：`52c2d5462993748942c00bf353ea4152bc0ac38e`
- 本验收分支：`local/stage-ai-validation-20260916`
- `origin/main`：`d98a6238c091187595e71c0c88e8fa0e718548c2`
- PR：[#27](https://github.com/Jovifei/Tesla_Simulate_vico/pull/27)，仍为 open Draft，head 为上述源 HEAD，base 为 `feature/stage-ah-three-way-audition-20260915`（`c52d5011c80528f564bba650b98efbd3c82f80f8`）。
- C0 父包：`E:\Tesla_speed\review_packages\s12-stage-ah-fourcar-audit-fix-20260913-v4\packages\ah-fourcar-realref-s12-stage-ah-fourcar-audit-fix-20260913-v4-c0`
- C0 `audition_manifest.json` SHA：`ab379153fdbf1606577b681ccd86e6790cbf39bb751687c9368256af3c5a7da3`
- 既有 A/C 三路包 ARTIFACTS SHA：`e6f697858100335244fbcc5ae75426c0bc5cb032146caaa1f801c784b0f53e1c`
- 既有 Aventador 闭环 ARTIFACTS SHA：`8266e91da02152a1c8909c9d1c008d158d0bf57ae11000ae6d3587834a538a8c`
- 真实 IR 根目录：`E:\project\engine-sim\runtime\v0.1.11a\engine-sim-build_0_1_11a\es\sound-library`
- 外部真实 WAV 仍只读、未加入 Git；未下载或替换新 Reference。

## 参考计划与 fail-closed 处理

初审计划 v1 SHA 为 `b64a302d2a558dea205e592b66d743d7976311c706b3904670fae8c155409042`。loader 对规定的 44.1k→48k polyphase 重采样出现有限但大于 1.0 的峰值后，失败证据单独保存在：

`E:\Tesla_speed\review_packages\s12-stage-ai-fourcar-plan-20260916-load-failure.json`（SHA `1b67d34b1233078971d14bd409f641145e7a06d91e921d0864be1635a4cea72f`）。

没有裁剪、归一化、make-up gain 或改阈值。修订计划 v3：

`E:\Tesla_speed\review_packages\plans\stage-ai-fourcar-plan-20260916-v3.json`（SHA `d032ffd682c5cf34ebd9cc5a66d4b419151d9f58a6fb3f1b257b73179eb34d90`）。

它在拟合前冻结 7 条可闭包记录：Ferrari 3 条、GT-R 4 条；每车至少 2 条独立 train，validation 视角/工况在 train 中出现。13 条排除逐条保留原 source SHA 与理由：8 条是重采样后超过 full scale，4 条虽安全但剩余不可形成匹配 validation 分层，1 条（LFA_04）原窗口本身超过 1% full-scale clipping。Hellcat 与 LFA 因此没有伪造 B，保持 BLOCKED。

## 实际真实闭环

执行环境：Python `3.14.2`、NumPy `2.4.6`、SciPy `1.17.1`、Windows 11；`PYTHONPATH` 指向本 worktree，`PYTHONUTF8=1`，`S12_ENGINE_SIM_IR_ROOT` 指向上述真实 IR 根目录。

命令：

```text
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_reference_loop run --plan E:\Tesla_speed\review_packages\plans\stage-ai-fourcar-plan-20260916-v3.json --out E:\Tesla_speed\review_packages\s12-stage-ai-fourcar-loop-20260916-v2 --max-trials 25 --allow-r3-unsynchronized
```

run 已通过 `verify_run`，目录：
`E:\Tesla_speed\review_packages\s12-stage-ai-fourcar-loop-20260916-v2`

- `summary.json` SHA：`5cabbbe41cd2ca20ef5299fcd99e98a907af02aae0f7d6923380fa6abf6cf2fa`
- `ARTIFACTS.json` SHA：`c8a156057edef5991b40e4996634e2eeb3bc719d106a4f162e7a421a0709c648`
- `off-switch`：Ferrari `10/10`、GT-R `10/10`；固定父分母、trace、seed、flags 均保持。

| 车型 | 参数 baseline → selected | 实际试探决定 | train 误差 | 独立 validation | 状态 |
|---|---|---|---:|---:|---|
| Ferrari 458 | `high_rpm_growth_scale 1.12 → 0.90` | 1 baseline / 3 accepted / 2 no-improvement | `0.6980336636 → 0.6965733564` | `0.7060151565 → 0.7030823273` | `RELATIVE_IMPROVEMENT_VALIDATED` |
| Nissan GT-R R35 | `turbo_whistle_mix 0.18 → 0.26` | 1 baseline / 4 accepted / 1 no-improvement | `0.5669764829 → 0.5657202275` | `0.5141973343 → 0.5086184482` | `RELATIVE_IMPROVEMENT_VALIDATED` |
| Hellcat | — | — | — | — | `BLOCKED`：安全剩余源无匹配 validation 分层 |
| Lexus LFA | — | — | — | — | `BLOCKED`：安全剩余源不足以形成独立 train/validation |

每车均为真实 renderer→callback→实际 optimizer trial→source-disjoint validation→旧 4 场景 Reference guard 链。日志（每次 render 前后 flush/fsync）：

- Ferrari `diagnostics/ferrari_458/render_journal.jsonl` SHA `3c73cc44e80e1ec4b2a748a8ce884b08b7095e87f9a4c1a7a60d757321746698`；`trials.jsonl` SHA `47d09fb3e9257b6781ec4243cf8bd6102541bb370369f06ecc11cbdcbd1e412e`；`result.json` SHA `1ea2ecbbac75f5a1a86d039c71e55ff63c2f6ec618a3329543f1587325b703be`
- GT-R `diagnostics/gtr_r35/render_journal.jsonl` SHA `8305b5f313fe0a4f21c46841b1d918af5ee978855f423086b1f4035735bb4254`；`trials.jsonl` SHA `7a001ff69677ea6bb5609df6e983f051ab51625c644bd7290afeb903a6273b2c`；`result.json` SHA `69d6335291f061e7e567ddb50f2a0de60fe5ba69cc2ef82a0d2772af6c581301`

旧 Reference 四场景 guard 均无 `>3%` regression：

- Ferrari：`01 0.7751606611→0.7756431303`、`02 1.0369238147→1.0387144917`、`03 3.1481887116→3.1481887116`、`09 2.2438394397→2.2438394397`。
- GT-R：`01 1.3823288876→1.3805996710`、`02 0.5341186629→0.5367183418`、`03 1.8363958943→1.8363958943`、`09 1.5733745232→1.5702004697`，全部 `regression_gt_3pct=false`。

输出保护摘要（10 场景汇总）：

| 车型 | legacy pre-guard count | soft guard frames | 最大 active ratio | 最小 gain | 最大衰减 dB | 最大 delta peak | 最大 delta RMS | 最大 post-guard peak | post/emergency/identity clip |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ferrari | 0 | 7682 | 0.00727431 | 0.98985507 | 0.08856776 | 0.00953623 | 0.00013441 | 0.93046377 | `0/0/0/0` |
| GT-R | 8 | 2911 | 0.00725347 | 0.98487458 | 0.13238142 | 0.01433186 | 0.00008403 | 0.93320289 | `0/0/0/0` |

4×峰值是固定的 `scipy.signal.resample_poly(up4/down1, Kaiser beta=5.0, boundary=line)` 诊断估计，明确 `DIAGNOSTIC_NOT_ITU_CERTIFIED`；Ferrari 最大 `0.86507866`，GT-R 最大 `0.90448870`。

## 新八车 A/B/C 包

目录：`E:\Tesla_speed\review_packages\s12-stage-ai-qualified-three-way-20260916-v2`

- `summary.json` SHA：`f9c92da7daa819ea02efd4bb4f2acf0631981f267baeb9a69972f33d3ed4112c`（包内 seal 已校验）
- `ARTIFACTS.json` SHA：`179f3ed31ebe93dab316ef9bef6bb238fda31931f29a51eb49009d04a1e6e3f5`
- A 原算法：旧包已有 `80/80` 个 A WAV 字节一致。
- C 真车对照：旧包实际存在的 `65/65` 个 C WAV 字节一致；缺受控音频的场景继续禁用 C。
- 新 B：Ferrari 与 GT-R 各 `10/10` 个 B WAV 与本次 fit `tuned` 字节一致；A/C 没有重新渲染或归一化。
- Aventador B 只导入既有已验证闭环，不在本轮重复 25 trial；C、RX7、C63、Supra 的既有证据边界保留。

八车型导航仍完整：Hellcat、Ferrari 458、LFA、GT-R R35、C63 W204、Supra JZA80、RX-7 FD、Aventador LP700-4。B 状态为：Ferrari、GT-R、Aventador `AUTO_B_READY`；Hellcat、LFA、C63、Supra、RX7 `B_UNAVAILABLE`，没有用固定 recipe 冒充自动 fit。

## 页面与浏览器验证

严格预检：`qualified ABC preflight PASS`，端口 `29581` 空闲后绑定；没有 fallback，也未触碰旧 29480/29380。页面：

- [Ferrari 458 三路试听](http://localhost:29581/ferrari_458/index.html)
- [Aventador 三路试听](http://localhost:29581/aventador_lp700/index.html)
- [GT-R 三路试听](http://localhost:29581/gtr_r35/index.html)
- Ferrari/GTR 日志：[Ferrari log](http://localhost:29581/evidence/ferrari_458-log.html)、[GT-R log](http://localhost:29581/evidence/gtr_r35-log.html)

浏览器现场验证：Ferrari A→B→C 三路切换成功，右上角 Ferrari→GT-R 切换成功；Aventador 页面显示三路按钮、八车型下拉、闭环证据日志入口。HTTP 200 已检查根页、三车型页、两份 log 与 Ferrari/GT-R B WAV；两个页面控制台 error/warn 均为空。Ferrari 与 Aventador 修正版页面截图已在 Codex 试听交付中截取。

## 测试与 CI

当前 HEAD 本机专项：`59 passed in 42.22s`；Track-P `exit 0`（冻结文件 180、冻结符号 2、0 frozen changes）；compileall `exit 0`；`git diff --check` `exit 0`。

当前 HEAD full S12 实际命令：

```text
python -m pytest -q tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests
```

结果：`1697 passed, 3 skipped, 1 warning, 232 subtests passed in 2636.03s (0:43:56)`，退出码 `0`。唯一 warning 是既有测试字符串中的 Python `SyntaxWarning`，不是本轮代码改动。完整本机测试收据：`E:\Tesla_speed\review_packages\s12-stage-ai-full-s12-receipt-20260916.json`（SHA `6423d945c95a4912e4be9e18da4b671d6d68be8c5cfe099ea280f4f0e7f2a6f1`）。

PR27 exact-head 远端收据（交接 HEAD，源码本轮未改）：run `34997464648`；Ubuntu job `104477207227` success；Windows job `104477207327` success；两 job 的 head 均为 `52c2d5462993748942c00bf353ea4152bc0ac38e`。

## 未完成与下一步

本轮没有为了让四车都通过而修改 loader、resampling、音色、K/C、阈值、父分母或 Reference。Hellcat/LFA 的真实 source 证据仍不足，故没有 B；这不是声学“无改善”结论。R3 录音未做 RPM/gear/mic/AGC 同步，页面中的误差是相对频谱诊断，不是机器相似度百分比。下一步是 Jovi 在 29581 试听并独立给出 Human acoustic review；未授权前不继续第二轮调参、不揭盲、不合并 main。



