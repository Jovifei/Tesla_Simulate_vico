# Stage AF 当前接管真值（2026-09-06；Stage AG-R1 路由更新 2026-09-09）

> **2026-09-09 当前试听入口优先级：** 对已生成的四车型 Stage AG-R1 package，当前 source authority 是 `origin/local/stage-ag-vehicle-identity-20260908@717a5226eef39491938f7e796cb87de521c2c477`。不要用本文件历史的 `serve_dashboards.py` / 8080 / 8088–8091 指引打开 R1 页面。只能使用 `stage_ag.serve_r1_review_strict` 对固定 legacy/R1 manifest 做 SHA、contract、rich HTML 与端口预检后，访问 23380–23383（legacy）或 23480–23483（R1）。R1 mode=`vehicle_identity_v1r1`，status=`WAITING_FOR_JOVI_ACOUSTIC_REVIEW`；不是 Human PASS、OEM/R1 calibration 或 Profile Freeze。

## 先读结论

后续 AI 不得再把 Stage AE 当声音基线。

### 当前声音 authority

```text
main f81d3a3
→ stage_ad/engine_sim_acoustics.py
→ EngineAcoustics.render_track()
```

这是 Jovi 已实际试听并判断约 70–80% 相像的版本。

### Stage AE

状态：`HUMAN_FAIL`。

失败原因不是 pytest，而是最终声音实际听感显著退化。长期教训：**测试通过和架构统一不能替代声音 Human Gate。**

### Stage AF

分支：`s12-stage-af-physical-closed-loop`

目标：不替换好声音 renderer，仅增加：

1. deterministic wrapper；
2. bounded physical parameter families；
3. real-reference spectral/envelope fixed-distance；
4. iterative negative feedback；
5. 原 A/B 工作台绑定；
6. repo generated-artifact cleanup。

## 当前优化链

```text
R2/R3 Reference WAV
→ main 的 EngineAcoustics
→ 频带/centroid/envelope/flux 特征
→ fixed reference distance
→ Sobol bounded physical search
→ shrink/recenter
→ final_r3_diagnostic_fit.json
→ 同一个 EngineAcoustics 再生成
→ 原 build_unified_dashboards
→ 原 serve_dashboards.py
→ Jovi A/B
```

数值只负责找候选；Jovi 人耳负责决定是否真的更像。

## 物理参数族

- body：exhaust body / mechanical resonance / dF-F；
- path：runner length / exhaust length / IR contribution；
- induction：air/turbulence contribution；
- afterfire：existing event energy scale。

范围均围绕 f81d3a3 手工调好的 baseline，禁止大范围黑盒重搜。

## 工作台（Stage AF 历史路径）

以下是 Stage AF/H0-H2 的历史端口，不能用于 Stage AG-R1：

- 8080 portal
- 8088 Hellcat
- 8089 Ferrari 458
- 8090 LFA
- 8091 GT-R R35

不要开发新的 UI/backend。

## Git 清理规则

四套 WAV/Base64 dashboard 是可再生成产物，已经从 Stage AF Git 树移除。以后生成到 `E:/Tesla_speed/review_packages`。

Git 只保留：source、generator、server、fit JSON/receipt、关键 evidence、文档。

## Reference 边界

公开视频仍是 `R3_PRIVATE_DIAGNOSTIC_ONLY`。它可以：

- A/B 人耳对比；
- diagnostic negative-feedback ranking。

它不可以自动变成：

- R1/R2；
- OEM calibration；
- Profile Freeze；
- product redistributable audio asset。

## 开源吸收

Engine-Sim 继续是 physical architecture 最重要来源；SSSSM-DDSP / DDSP / CMA-ES sound matching 只吸收“audio-domain inverse parameter search”的方法。Stage AF 不复制神经网络，也不让黑盒 ML 替代 physical renderer。

## 下一位 AI 的历史执行入口

`docs/05-execution/04-stage-af-local-ai-handoff.md`

先 pull Stage AF，跑 focused test；再在本地 reference/IR 环境跑 fit；最后用原工作台试听，完成后停止等待 Jovi。

Stage AG-R1 当前固定入口见 `docs/08-reports/19-stage-ag-r1-strict-rich-review-routing-20260909.md`；它是“现有 immutable package 的严格试听路由”，不是新算法、fit 或重渲染任务。

## 2026-09-06 数值修正与页面服务接力真值

接力分支 `local/main-audio-review-20260906` 已在 `origin/main=28ee2bd73298959dc4831320e8b080b833c8c3d8` 之上完成 Stage AF 数值修正审查，并在 `df2fb6a3e2b490eb62fc78183a1b7a7bafbc5093` 合并点 fast-forward 进入 main；其后的文档状态提交继续位于 main，动态 SHA 必须现场读取。实现保留 `stage_ad/engine_sim_acoustics.py::EngineAcoustics` 以及原 `build_unified_dashboards.py`、HTML 模板和 `review_packages/serve_dashboards.py`；Stage AE 被否决的默认 renderer、另一个后台和 Track-P/FVM/PTR/Radiation 改动均未恢复。

新增的数值旗标是显式 opt-in，不改变 H0 默认输出：

- `cycle_phase`：把 720° crank radians 转换为 360° cycle radians 时只乘一次 0.5；
- `causal_delays`：以零状态分数延迟替代会回卷的 `np.roll`；
- `causal_convolution`：以已有 `UniformPartitionedConvolver` 替代可能提前响应的 centered `same` convolution；
- `causal_derivative`：以零状态后向差分替代 look-ahead gradient；
- `shift_cut`：使用 unity→cut→unity 的换挡切断包络。

Stage AF v4 fit/receipt 现在绑定车型、seed、数值模式、renderer source SHA、IR 原始/有效 SHA 和 Reference source SHA；缺失或旧 fit、缺失 IR、IR/模式漂移都必须 fail-closed。`multires_spectral_distance` 用多分辨率谱检查同一宽频带内的八度错误；`per_scene_guard` 对每个参考场景分别检查退化。参数调节仍只能按 `body → path → induction（NA 跳过）→ afterfire` 的 source-causal family 进行，不得使用 master/global/broad-pre-PTR gain。

Hellcat 已形成三套可听对照：

```text
H0  numerical_fixes=[]                         → localhost:8188
H1  [cycle_phase]                               → localhost:8488
H2  [causal_convolution, causal_delays,
     causal_derivative, shift_cut]              → localhost:8388
```

三套都使用同一已有 IR `test_engine_16_eq_adjusted_16.wav`，原始 SHA 为 `44ce5af25a55efdf996c7e5026271f80949625b95fbdc1c4b83863b6e991b152`，rights 仍是 `UNVERIFIED_LOCAL_ASSET`；每套 10 个 candidate WAV 和原真车 Reference 副本都写入 `stage_af_binding.json`。它们只是 diagnostic/Human audition 输入，不是 Human PASS、OEM_MATCH、CALIBRATED 或 Profile Freeze。

页面刷新故障的根因是自包含 HTML 约 34.5 MB，单线程 `TCPServer` 在慢客户端写响应时阻塞后续刷新。服务已改为 `ThreadingMixIn + TCPServer`，并设置 `daemon_threads=True`、`block_on_close=False`；“慢 socket 不读取 + 第二 HTTP 请求”实测返回 200。未来车型复用原服务时，必须保留该并发模型并只停止已确认属于本轮的 `serve_dashboards.py` PID。

最新工程证据：focused AF/AD/numerical `29 passed`；full S12 `1459 passed, 2 skipped, 1 warning, 232 subtests passed`；Track-P 冻结路径改动 0；Stage-Z/AA 真实 rows 各 `12/12 executable`。所有 automated evidence 仍不能替代 Jovi 的具名试听反馈。
