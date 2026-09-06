# Stage AF 本地 AI 接手：在“好声音 main”上做负反馈并继续用原工作台

## 0. 唯一目标

从远端 `s12-stage-af-physical-closed-loop` 拉取代码，在本地 Engine-Sim IR/真实 reference 环境中运行 Stage AF，**只优化 main=f81d3a3 已经好听的 EngineAcoustics**，然后使用原有四车型 A/B 工作台生成声音给 Jovi 听。

不要切换到 Stage AE renderer，不要开发新的 dashboard/backend，不做 Android，不做 ESP32。

## 1. 安全拉取

```powershell
cd E:\Tesla_speed\prj
git fetch origin --prune
git worktree add E:\Tesla_speed\worktrees\s12-stage-af-physical-closed-loop origin/s12-stage-af-physical-closed-loop
cd E:\Tesla_speed\worktrees\s12-stage-af-physical-closed-loop
```

确认 HEAD 与远端一致。

## 2. 先测试

```powershell
python -m pytest -q tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_af_physical_closed_loop.py
```

## 3. Reference 来源

优先直接复用当前已经能在旧工作台听到的 `ref_*.wav`。如果 Git 清理后本地旧包仍存在，可以从：

`E:\Tesla_speed\review_packages\s12-stage-ad-<vehicle>-closed-loop-v1\`

读取；不要重新下载一套“更好听”的参考造成标尺变化。

公开视频保持 `R3_PRIVATE_DIAGNOSTIC_ONLY`。

## 4. 逐车运行负反馈

第一轮保持小范围、小搜索量。当前 baseline 已经是 Human 判断方向正确的声音，不允许用大搜索把它搜坏。

建议先 Hellcat 和 Ferrari，确认方向以后再 LFA/GT-R。

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_af.fit_cli `
  --vehicle hellcat `
  --reference-dir E:\Tesla_speed\review_packages\s12-stage-ad-hellcat-closed-loop-v1 `
  --output-dir E:\Tesla_speed\stage_af_runs\hellcat `
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
  --output-root E:\Tesla_speed\review_packages `
  --seed 20260906
```

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
- focused/full tests；
- 8088–8091 是否正常；
- 然后等待实际听感。

## 8. 永久禁止

- 不把 Stage AE 失败声音重新拿来；
- 不改/新写评审 UI；
- 不用 master/global gain 当优化参数；
- 不把 R3 写成 calibrated/OEM；
- 不因为 numerical distance 下降就宣告 Human PASS。
