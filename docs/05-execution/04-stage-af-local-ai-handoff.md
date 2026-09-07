# Stage AF 本地 AI 接手：在“好声音 main”上做负反馈并继续用原工作台

## 0. 唯一目标

从最新 `origin/main` 建立独立 worktree，在本地 Engine-Sim IR/真实 reference 环境中运行 Stage AF，**只围绕已试听过的 EngineAcoustics authority 做有界修正**，然后使用原有四车型 A/B 工作台生成声音给 Jovi 听。`f81d3a3` 仅是已试听 baseline 的 lineage，不是当前动态 HEAD。

不要切换到 Stage AE renderer，不要开发新的 dashboard/backend，不做 Android，不做 ESP32。

## 1. 安全拉取

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git worktree add -b local/<task-name> E:\Tesla_speed\worktrees\<task-name> origin/main
cd E:\Tesla_speed\worktrees\<task-name>
```

确认 HEAD 与远端一致。

## 2. 先测试

```powershell
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_physical_closed_loop.py
```

## 3. Reference 来源

优先直接复用当前已经能在旧工作台听到的 `ref_*.wav`。不要重新下载一套“更好听”的参考造成标尺变化。

建议把参考音频单独保存在：

```text
E:\Tesla_speed\stage_af_references\hellcat\ref_hot_idle.wav
E:\Tesla_speed\stage_af_references\hellcat\ref_steady_mid.wav
E:\Tesla_speed\stage_af_references\hellcat\ref_full_pull.wav
E:\Tesla_speed\stage_af_references\hellcat\ref_afterfire.wav
... ferrari_458 / lfa / gtr_r35 同结构
```

如果当前 reference 仍只在旧本地 review 包里，也可以直接把旧包根目录作为 reference source；Stage AF 不联网、不重新抓取素材。

公开视频保持 `R3_PRIVATE_DIAGNOSTIC_ONLY`。

## 4. 逐车运行负反馈

第一轮保持小范围、小搜索量。当前 baseline 已经是 Human 判断方向正确的声音，不允许用大搜索把它搜坏。

建议先 Hellcat 和 Ferrari，确认方向以后再 LFA/GT-R。

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_af.fit_cli `
  --vehicle hellcat `
  --reference-dir E:\Tesla_speed\stage_af_references\hellcat `
  --output-dir E:\Tesla_speed\stage_af_runs\hellcat `
  --numerical-fixes `
  --candidates 8 `
  --rounds 2 `
  --seed 20260906
```

Ferrari/LFA/GT-R 只替换 vehicle/reference/output。

默认 family：body → path → induction（仅增压车）→ afterfire。

Stage AF v2 不是让所有 family 共用一把模糊总分：

- body：hot_idle + steady_mid + full_pull；
- path：steady_mid + full_pull；
- induction：steady_mid + full_pull；
- afterfire：afterfire；
- 每个 family 还必须满足全 reference set 不明显退化的 guard。

如果某一 family 人耳明显变差，即使 metric 变好也回退它。

## 5. 生成原来的四车型工作台

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_af.build_existing_dashboards `
  --fit-root E:\Tesla_speed\stage_af_runs `
  --reference-root E:\Tesla_speed\stage_af_references `
  --output-root E:\Tesla_speed\review_packages `
  --seed 20260906
```

这里没有新 UI。Stage AF 只做两件事：

1. 把 tuned `EngineAcoustics` 注入原 `build_unified_dashboards.py`；
2. 把 `--reference-root` 里**已经存在、受治理的** `ref_*.wav` 复制到原 dashboard 所要求的 `web_audio` 位置，并把 SHA 写进 `stage_af_binding.json`。

它不会下载 reference，也不会替换真车字节。

然后**仍然运行原服务台**：

```powershell
python review_packages\serve_dashboards.py
```

访问：8080 门户；8088 Hellcat；8089 Ferrari；8090 LFA；8091 GT-R。

## 6. 试听方法

每辆车对同一 scene 做 A/B 热切换：

1. hot idle；
2. full pull；
3. steady low/mid/high；
4. lift；
5. afterfire；
6. shift/tip-in。

优先评价 vehicle identity / body / induction / dynamics / artificial artifact，不要只评价音量。

## 7. 停止条件

完成本轮声音后停止，不自动再跑第二轮。

向 Jovi 汇报：

- HEAD；
- 每车 baseline_distance → final_distance；
- final fit 路径 + SHA；
- 哪些 family 改了哪些参数；
- `stage_af_binding.json` 中 reference SHA；
- focused/full tests；
- 8088–8091 是否正常；
- 然后等待实际听感。

## 8. 永久禁止

- 不把 Stage AE 失败声音重新拿来；
- 不改/新写评审 UI；
- 不用 master/global gain 当优化参数；
- 不把 R3 写成 calibrated/OEM；
- 不因为 numerical distance 下降就宣告 Human PASS。

## 9. 2026-09-06 数值修正与刷新故障接力经验

本节追加当前验证过的复用规则，不替代前面的原始接管步骤。

### 9.1 H0/H1/H2 数值顺序

先固定车型、采样率、RPM/throttle 轨迹、seed、已有 IR 路径/SHA 和 Reference 路径/SHA。H0 使用空 `numerical_fixes`，在相同输入/seed/IR 下必须与旧 `EngineAcoustics` 逐 PCM 相等；H1 只打开 `cycle_phase`，修复 720° 曲轴角到 360° 四冲程循环相位的一次换算；H2 再打开 `causal_delays`、`causal_convolution`、`causal_derivative`、`shift_cut`，分别验证不回卷、不提前响应、无 look-ahead 和 unity→cut→unity 包络。所有旗标都必须是显式 opt-in，不能成为默认 renderer 或 master/global gain。

### 9.2 Fit/Reference/IR provenance

Stage AF v4 fit receipt 必须绑定 vehicle、seed、numerical fixes、renderer source SHA、IR 原始/有效 SHA、Reference source SHA 和自哈希。缺 fit、旧 schema、IR 漂移、模式不一致时 fail-closed；只有显式 `--baseline` 才允许生成 H0。真实 IR 找不到时停止，不能用单位脉冲替代。公开视频/未核实 rights 仍是 R3/private diagnostic，不能升级 R1/R2 或产品素材。参数阶段遵循 body → path → induction（NA 跳过）→ afterfire，每个 scene 单独 guard，不能用总体均值掩盖退化。

### 9.3 大体积 HTML 刷新

原工作台的自包含 HTML 可能约 34.5 MB。若 `ReusableTCPServer` 只是单线程 `TCPServer`，一个慢客户端会卡住整个 accept 循环；端口显示 Listen 不代表刷新可用。先查看 `Get-NetTCPConnection` 的 `ESTABLISHED` 连接、真实 `serve_dashboards.py` PID，再用 `127.0.0.1` curl 复现。修复只将 server 改为 `ThreadingMixIn + TCPServer`，设置 `daemon_threads=True`、`block_on_close=False`，不改页面/声音。用一个不读取的慢 socket 加第二 HTTP 请求验证并发；只停止已确认属于当前候选的 PID，不终止无关服务。

### 9.4 当前接力状态

代码验证提交：`b1b5b4109f9daff698f69057ae04218606e420f9`、`6feb0eca475d021e3e8facfe204691abb0dce80d`、`3c22a6327819995e15c7073e47eb9970c422a96f`。focused AF/AD/numerical 为 `29 passed`，full S12 为 `1459 passed, 2 skipped, 1 warning, 232 subtests passed`，Track-P 冻结路径改动 0；自动证据不能替代 Jovi 人耳试听。后续 Agent 读完本节后，生成明确编号候选即停止等待 Jovi，不自动扩车型或无限调参。

## 10. 2026-09-07 Stage AF-R 证据完整性接力

Stage AF-R 是对现有 Stage AF/AD 链的证据治理修正，不是第三套 renderer 或新试听服务。唯一允许的声音链仍是：

```text
VehicleState / existing scene trace
→ stage_ad.EngineAcoustics
→ original build_unified_dashboards.py
→ original HTML A/B workbench
→ existing serve_dashboards.py
```

接手时从现场 `origin/main` 建立新 worktree；不要引用旧 HEAD、不要覆盖已发布 package。每个新包必须使用新的安全 `package_id`，先写 `output_root/.stage_af_r_staging/<package_id>`，校验 manifest/binding/contract 和所有候选、Reference、HTML artifact 的 SHA，再原子发布到不存在的目标目录。目标已存在或 staging 失败必须停止/清理，不能覆盖旧包。

fit v4 的 `reference_sources` 是 fit 的硬输入：四个 `hot_idle / steady_mid / full_pull / afterfire` 场景都必须有 filename/SHA；build 必须从调用者显式传入的 `--reference-root` 找到相同 source bytes，并拒绝 SHA 漂移、缺失和 stale destination。省略 `--reference-root` 只允许生成没有 Reference 绑定的 audition-only candidate，绝不从 output root 或旧 package 猜测来源。参考素材仍按 rights/evidence 边界记录，`UNVERIFIED_LOCAL_ASSET`/R3 不能升级为 R1/R2。

页面只显示 `dashboard_contract.json` 的真实数据：没有 fit 或测量就显示 `NOT_FITTED` / `NOT_MEASURED`；参数数、fit distance、Reference source label、scene category/count、B 轨可用性和 FFT 轴都从当前 package 读取。反馈导出必须带 package/candidate/vehicle/contract SHA，状态保持 `WAITING_FOR_JOVI_FEEDBACK`。不要保留旧页面的固定分数、固定车型、PASS 文案或 `cruising` 假类别。

H0 必须用固定的 pre-fix Git commit 作为 oracle，在同一输入、seed 和 IR 下与当前空 flags 输出逐 PCM 比较；不能拿当前代码与当前代码比较。IR 搜索顺序保持 `new → archive → smooth → root`。H1/H2 描述要以实际 flags 为准：当前 H1 是 `cycle_phase`，H2 是四项时间处理修正，不能写成“只增加了时间修正”而忽略相位差异。

完成后至少运行 AF-R focused、受影响 AF/AD、完整 S12、compileall、Track-P 和 `git diff --check`；服务回归必须是真实慢连接加第二请求，并保留 single-thread negative control。软件/指标通过仍不等于 Human PASS、OEM_MATCH、CALIBRATED 或 Profile Freeze；生成编号试听包后停止，等待 Jovi 实际 A/B 反馈。
