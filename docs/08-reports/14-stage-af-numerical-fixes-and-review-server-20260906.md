# Stage AF 数值修正与评审服务当前报告（2026-09-06）

状态：`CURRENT_STATUS / DIAGNOSTIC_ONLY / WAITING_FOR_JOVI_AUDITION`

## 1. 本报告结论

本轮在 `origin/main` 的 `28ee2bd73298959dc4831320e8b080b833c8c3d8` 之上，以独立分支 `local/main-audio-review-20260906` 审查并实现了 Stage AF 的五类数值修正、Stage-AF fit/receipt 治理、真实参考绑定、CI scorecard 行证据修复，以及原 A/B 工作台的大 HTML 并发服务修复。实现提交为：

- `b1b5b4109f9daff698f69057ae04218606e420f9`：Stage AF 数值修正、谱距离 guard、fit v4、原工作台绑定与测试；
- `6feb0eca475d021e3e8facfe204691abb0dce80d`：原 `serve_dashboards.py` 改为并发处理慢 HTML 客户端；
- `3c22a6327819995e15c7073e47eb9970c422a96f`：记录刷新阻塞的根因与防回归经验。

`EngineAcoustics` 仍是当前已被 Jovi 试听过的声音 authority；原 `build_unified_dashboards.py`、HTML 模板和 `serve_dashboards.py` 仍是试听工作台。没有启用被否决的 Stage AE 默认 renderer，没有新建试听后台，也没有修改 Track-P/FVM/PTR/Radiation。

本报告及实现已从隔离分支 fast-forward 合并并推送到 `origin/main`；当前 main tip 为 `df2fb6a3e2b490eb62fc78183a1b7a7bafbc5093`。后续 Agent 仍必须在新的独立 worktree 中从最新 `origin/main` 接手。

本轮只完成 Hellcat 的可编号对照试听：H0 原声音、H1 点火相位修正、H2 时间处理修正。它们是诊断候选，不是 Human PASS、OEM_MATCH、CALIBRATED 或 Profile Freeze。

## 2. 新增数值功能

所有修正都通过 `EngineAcoustics(..., numerical_fixes=...)` 显式开启；空集合必须保留旧输出。允许的旗标定义于 `tools/sound_sim/s12/acoustic_identity_v015/stage_ad/engine_sim_acoustics.py:67`：

| 旗标 | 旧问题 | 新行为 | 试听映射 |
| --- | --- | --- | --- |
| `cycle_phase` | 4 冲程循环相位是 0..2π，而 firing angle 是 720° 曲轴角，直接相减会把角度域混用 | 在进入 cycle-domain 前只做一次 `crank_radians * 0.5`，见 `firing_phase_for_cycle()` | H1 |
| `causal_delays` | `np.roll` 把尾部样本回卷到开头，产生未来响应 | `causal_fractional_delay()` 使用零状态、线性分数延迟，不读取未来样本；同时覆盖涡轮/低频声道的固定左右延迟 | H2 |
| `causal_convolution` | `fftconvolve(..., mode="same")` 的中心裁切会让 IR 在时间零点前响应 | 使用已有 `UniformPartitionedConvolver`，以 `h[0]` 为时间零点，输出只保留因果响应 | H2 |
| `causal_derivative` | `np.gradient` 使用前后样本，存在 look-ahead | `causal_backward_difference()` 使用零状态后向差分 | H2 |
| `shift_cut` | 旧换挡窗从低值单向爬升，包络不对称 | 改为 unity → cut → unity 的连续切断包络，见 `shift_cut_mask()` | H2 |

`numerical_fixes=()` 的回归测试以固定输入、seed 和恒等 IR 对比原始 `EngineAcoustics` 输出，要求 PCM 完全相等；数值修正不是新的默认 renderer，也不是自动选择的优化旋钮。

## 3. 评分与 fit 治理

`stage_af/physical_closed_loop.py` 增加：

1. `multires_spectral_distance()`：在 1024/4096/8192 多分辨率 STFT 上比较归一化谱，避免同一宽频带内相差一个八度却被粗频带统计判为零距离；
2. `renderer_identity()`：绑定车型、采样率、源文件 SHA、IR 原始路径/SHA、有效 IR SHA、数值旗标和 rights 状态；
3. fit schema `s12.stage_af.physical_fit.v4`：绑定 seed、车型、numerical fixes、自哈希和 renderer identity；旧/缺失/篡改 fit 直接拒绝；
4. `per_scene_guard()`：每个参考场景相对初始 anchor 单独检查，任何一个场景超过退化界限都不能被候选吞掉；
5. 真实 Reference/IR 在加载时记录 source path、SHA 和 evidence boundary。公开视频/未核实 rights 的素材仍只能是 `R3_PRIVATE_DIAGNOSTIC_ONLY` 或明确的本地诊断输入。

`stage_af/build_existing_dashboards.py` 现在要求 `--fit-root`，除非调用者显式指定 `--baseline`；缺失 fit 不会静默回退默认参数。试听时必须将同一车型、seed、numerical fixes 和 IR identity 传到 renderer，fit/render 不一致时直接失败。禁止 master/global/broad-pre-PTR gain；原 renderer 的历史增益路径保持不变并在 receipt 中标明。

## 4. Hellcat H0/H1/H2 实际试听包

输出根目录：`E:\Tesla_speed\review_packages\s12-stage-af-hellcat-numerical-review-20260906-v2\`

每个目录都包含原工作台生成的 10 个候选 WAV、`web_audio/ref_*.wav` 真车参考副本、`index.html`、`index_standalone.html` 和 `stage_af_binding.json`。旧的试听包没有被覆盖。

| 对照 | numerical fixes | 页面 | 说明 |
| --- | --- | --- | --- |
| H0 | `[]` | `http://localhost:8188/` | 原始声音模式，作为同一 IR/seed 的 anchor |
| H1 | `["cycle_phase"]` | `http://localhost:8488/` | 只观察点火相位修正 |
| H2 | `["causal_convolution", "causal_delays", "causal_derivative", "shift_cut"]` | `http://localhost:8388/` | 观察时间处理修正 |

三套收据共用 IR：`E:\project\engine-sim\runtime\v0.1.11a\engine-sim-build_0_1_11a\es\sound-library\archive\test_engine_16_eq_adjusted_16.wav`，SHA-256 为 `44ce5af25a55efdf996c7e5026271f80949625b95fbdc1c4b83863b6e991b152`，rights 状态为 `UNVERIFIED_LOCAL_ASSET`。该状态只允许受控本地诊断试听，不代表可分发产品素材。

## 5. 评审服务故障与修复

症状：浏览器刷新 `8188` 无响应，端口进程仍存在，`8488/8388` 正常。

根因链：

```text
34.5 MB self-contained HTML
→ 单线程 TCPServer 写一个慢客户端
→ serve_forever 无法及时 accept 新连接
→ 浏览器刷新被拒绝或超时
```

证据是 8188 进程存在多条 `ESTABLISHED` 连接；停止并确认仅为本轮 `serve_dashboards.py` 进程后，`ThreadingMixIn + TCPServer` 修复通过。回归测试还保留一个不读取的慢 socket，再发第二个请求，第二个请求仍返回 HTTP 200。服务仍使用 `S12_REVIEW_ROOT` 与可选 `S12_REVIEW_PORT_BASE`，没有改变原页面布局或默认端口。

## 6. 验证证据

- Focused AF/AD/numerical：`29 passed, 1 warning`；
- Full S12：`1459 passed, 2 skipped, 1 warning, 232 subtests passed`；
- Track-P：冻结 180 个文件、2 个符号，冻结路径改动 0；
- Stage-Z/Stage-AA：从真实 rows 的 OFF/ON SHA 与 runtime call path 计算，均为 `12/12 executable`；
- `compileall`、`git diff --check`：通过；
- H0/H1/H2 三个服务：HTTP 200；慢客户端并发刷新：HTTP 200。

warning 是原始 IR WAV 的非 data chunk 提示，不是测试失败。

## 7. 后续车型复用规则

1. 先在独立 worktree 从当前 remote HEAD 开始，读取本报告、Stage-AF handoff 和 `tasks/lessons.md`；
2. 对新车型先建立同一 `EngineAcoustics`/Stage-AF 输入合同，先输出 H0 原始模式，再一次只打开一个数值旗标，保留固定 seed、IR 和参考路径；
3. 任何数值修正都要有 OFF/ON、因果响应、场景级 guard 和 PCM/SHA 证据；测试通过不能替代人耳试听；
4. fit 使用 v4 receipt，fit/render 必须共享车型、seed、numerical fixes、renderer source SHA 和 IR SHA，缺失或漂移就停止；
5. 参考音频只复制已有字节并记录 source/destination/SHA/rights，不下载、不把 R3 升级为 R2/R1；
6. 原工作台可以复用，但大体积自包含页面必须由并发服务提供，并用慢连接 + 第二请求验证；
7. 生成明确编号的试听候选后停止，等待 Jovi 的实际反馈，不自动继续调参或扩车型。

## 8. 未完成边界

- 本报告不证明任何车型 Human PASS、OEM_MATCH、CALIBRATED 或 Profile Freeze；
- 本轮没有执行有限参数 fit，也没有生成四车型 final audition package；
- Hellcat IR rights 仍是 `UNVERIFIED_LOCAL_ASSET`；
- H0/H1/H2 仍等待 Jovi 实际试听意见；
- Android、ESP32、Simulink 产品化和 R1 正式标定不在本轮范围。
