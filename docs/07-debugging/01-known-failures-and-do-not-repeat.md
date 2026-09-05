# 已知失败与禁止重复踩坑

更新：2026-09-05

## 声音模型

- fixed harmonic/resonator/EQ 堆叠不能作为最终真实感路线。
- P6 counterfactual residual 不是独立 source stem，不能作为 source-causal gain。
- broad/master/pre-PTR gain 不能伪装 source repair。
- LF persistence v1 `mean(env>median)` 数学上失效；使用 v2 指标。
- blower v1 曾忽略 audible post-PTR；分析必须区分 source/audible/contribution。
- dynamic event 缺 pre/post window 时必须 `NOT_MEASURABLE`，不能假造 0 ms。
- Stage AD 跨轮不能比较 changing-parent improvement；必须 fixed absolute reference distance。

## Reference

- public availability != rights。
- `extract_reference_audio.py` 的公网片段是 R3 human-only，不能默认进 optimizer。
- speech/music contamination fail-closed。

## Simulink

历史 v0.9 已知：default In1→Out1 bypass、设计端口未正确连接、19x1 config 未锁、PCM dimensions inherited、Audio Writer/To Workspace 接错、compile fail。不要把 `.slx` 存在当成 model PASS；只在复制 candidate 后本地修复。

## CI / repository

已解决或已识别的历史坑包括 Windows review-package path、Track-P ancient-base whitespace false positive、generated CRLF、receipt base/merge-base 错误规则、旧 failure count 误读、workflow concurrency 跨 ref 互相 cancel。再次遇到时先核对当前 commit/CI，不从旧聊天重建根因。

## Product direction

- 不因仓库有 ESP32 代码就重新切回 ESP32。
- 不把 CAN/OBD 设成 App MVP 前置条件。
- 不把 Human PASS 当 R1/OEM calibrated。
