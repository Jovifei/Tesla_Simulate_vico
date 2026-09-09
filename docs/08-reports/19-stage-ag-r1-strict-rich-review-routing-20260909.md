# Stage AG-R1 严格富交互试听路由（2026-09-09）

状态：`STAGE_AG_R1_STRICT_RICH_REVIEW_READY / WAITING_FOR_JOVI_ACOUSTIC_REVIEW`

## 1. 结论与范围

本次不是新的声音算法、自动 fit、package 重渲染或 Stage AE 接手。目标是让 Jovi 打开经过 byte/contract/HTML 约束的 Stage AG-R1 四车型富交互 A/B 页面，而不是电脑上残留的历史 portal 或 Stage-AE simple page。已生成的 probe、R1 scorecard、legacy package、R1 package、blind package 与 private mapping 均不改写。

当前 source authority：

```text
repo   = Jovifei/Tesla_Simulate_vico
branch = local/stage-ag-vehicle-identity-20260908
head   = 717a5226eef39491938f7e796cb87de521c2c477
base   = 4ee1f83369681d2789ef8e6e547398d233f6521d (AF-R2)
main   = 374c7b50db51fee935601954c9ee28de5ad15797 (source + strict-route docs merged)
PR #16 = closed after main integration; source branch remains the AG code authority

Frozen authority map:

```text
CODE AUTHORITY  = local/stage-ag-vehicle-identity-20260908@717a5226...
REVIEW RECORD   = local/stage-ag-r1-strict-review-20260909@71bb9180...
AUDIO PACKAGE   = s12-stage-ag-r1-identity-20260908-v1
DO NOT USE      = Stage AE; local/stage-ag-r1-rich-audition-workbench-20260909;
                 local/stage-ag-r1-rich-audition-workbench-r2-20260909;
                 8080 / 8088–8091
```

The two `rich-audition-workbench*` branches are experimental alternatives, not source or review authority; their presence must not cause a second renderer/server route to be adopted.
```

R1 package 的 source receipt `git_head=0e9207a...` 是 package 构建时的事实；当前 717a source 新增的是严格 review serving，不重新 render candidate PCM。二者不能混为“源码落后”或“重新调音”。

## 2. 固定 package 与状态

| 角色 | 路径 | manifest SHA-256 | mode |
| --- | --- | --- | --- |
| Legacy | `E:\Tesla_speed\review_packages\s12-stage-ag-r1-identity-20260908-v1\packages\s12-stage-ag-r1-identity-20260908-v1-legacy` | `0f9338bfd97911f2ac78143b6e92586cd19926df9ef2f19f0d7c10ca30d7a541` | `legacy` |
| R1 | `E:\Tesla_speed\review_packages\s12-stage-ag-r1-identity-20260908-v1\packages\s12-stage-ag-r1-identity-20260908-v1-identity-v1r1` | `3fecb566416d498bcedcb6c1a5267f6c7b36e82e9e9a87af7c2740705f599519` | `vehicle_identity_v1r1` |

R1 已通过 16 个既有 Reference row 的 `>3%` 回退门禁（0 回退），且 `separation_nonnegative=true`；Hellcat legacy/R1 candidate 保持逐 PCM byte-identical。该自动/字节证据只说明 package 可以被准确归因，不构成 Jovi 人耳通过、OEM、正式 R1 calibration 或 Profile Freeze。

## 3. 为什么历史服务会把试听导向错误页面

历史 `review_packages/serve_dashboards.py` 同时开 portal `8080` 和固定车型端口。端口冲突时它只报告该端口不可用并继续启动其余线程，因此浏览器可能继续连到旧进程、旧 package 或 Stage-AE 页面，造成“服务已启动但声音/页面没变”的假象。

所以 Stage AG-R1 禁止以下入口：

```text
http://localhost:8080/
http://localhost:8088/
http://localhost:8089/
http://localhost:8090/
http://localhost:8091/
review_packages/serve_dashboards.py
```

## 4. 唯一允许的 strict server

入口：`tools/sound_sim/s12/acoustic_identity_v015/stage_ag/serve_r1_review_strict.py`。

它在任意端口 bind 前依次验证：

1. Stage AG manifest schema、自哈希和指定 manifest SHA；
2. legacy/R1 mode 与恰好四个车辆目录；
3. 每车 dashboard contract 的 mode 与 `WAITING_FOR_JOVI_FEEDBACK`；
4. manifest ↔ contract ↔ 真实 candidate WAV 的 SHA；
5. manifest ↔ contract ↔ 真实 Reference WAV 的 SHA；
6. rich HTML marker：`声源 A/B 瞬时无缝比对`、`实时动态声学分析仪`、`visualizerCanvas`、`categoryAllLabel`；
7. 禁止 marker：`package-wide gain`、`canonical S12 renderer`；
8. 全部 8 个 loopback 端口可同时预绑定。任一失败会关闭已占用 socket 并停止，不 fallback 到历史服务。

端口固定：

| 车型 | Legacy | R1 |
| --- | ---:| ---:|
| Hellcat | 23380 | 23480 |
| Ferrari 458 | 23381 | 23481 |
| LFA | 23382 | 23482 |
| GT-R R35 | 23383 | 23483 |

## 5. 2026-09-09 本机验证

- `serve_r1_review_strict --preflight-only`：PASS；两个 package 的 manifest、contract、candidate/Reference SHA 与 rich HTML marker 全部通过。
- 发现旧 `serve_dashboards.py` 占用 23380–23483；先核对 PID/command 确认其来自历史 `stage-ag-r1-blind-resume-20260908-r2` worktree 后停止，只停止这些已确认的旧服务。
- strict server 在 `127.0.0.1` 以单一 PID 绑定 23380–23383、23480–23483；八个 URL 均 HTTP 200。
- 浏览器打开 `http://localhost:23481/`：截图显示 Ferrari R1 当前车型、四车型导航、A/B 瞬时切换、FFT/Waveform、分类、10 场景卡、评分与意见输入。HTTP HTML 同时含 rich analyzer marker，且无 stale Stage-AE marker。
- 未检测到 8080 或 8088–8091 的监听服务。

## 6. Jovi 试听边界

Jovi 当前主要试听 R1：23480–23483。只有在上述 route、manifest 和 WAV byte 验证成立后，听感才可归因给 current R1 package；若仍然“不像”，记录为 `HUMAN_ACOUSTIC_FAIL`，再由后续授权任务处理声音本身。当前不自动调参、重新渲染、fit、R2、profile freeze、Android、ESP32 或 merge main。
