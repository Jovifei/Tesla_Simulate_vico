# Stage AF 当前接管真值（2026-09-06）

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

## 工作台

继续使用原有端口：

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

## 下一位 AI 的唯一执行入口

`docs/05-execution/04-stage-af-local-ai-handoff.md`

先 pull Stage AF，跑 focused test；再在本地 reference/IR 环境跑 fit；最后用原工作台试听，完成后停止等待 Jovi。
