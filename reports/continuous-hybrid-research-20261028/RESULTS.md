# 连续混合渲染器：研究阶段结果

日期：2026-10-28（Asia/Shanghai）

## 实施范围

本阶段只在隔离工作树新增研究内核，不改变默认产品路径：

- `vico_web/src/continuous-hybrid.mjs`
- `vico_web/tools/continuous-hybrid-study.mjs`
- 对应连续性、事件、边界和研究收据测试

内核包含：

- 单一 PCM 相位时钟的纹理读头；
- RPM 变化时不重新 seek 的持相读取；
- 平滑动态包络；
- 有界 raised-cosine 事件攻击/释放；
- 非有限值、峰值和长缓冲安全检查。

## 验证

- RED：模块不存在时测试失败，记录于 `reports/continuous-hybrid-red.log`。
- 聚焦 GREEN：7/7，通过 `reports/continuous-hybrid-focused-final.log`。
- 完整 Web 回归：此前 177/177；长度门修复后需再次执行最终全量回归。
- 账本检查：PASS。
- `git diff --check`：PASS。

## 公开真实纹理研究 A/B

输入：公开 Wikimedia Honda F20C OGG，先用 ffmpeg 解码为 mono 48 kHz F32LE；原始来源 SHA 绑定在 `E:\Claude_allow\Download\vico-real-engine-source-pool-20261027\manifest.json`。

输出目录：本报告目录下的 `honda-f20c.f32le`、`continuous-hybrid-research.f32le` 和 `continuous-hybrid-research.json`。

结果：

- 研究输出 480000 帧（10 秒，48 kHz）；
- `preClipPeak=0.2837267518`；
- `maxSampleJump=0.0292004198`；
- 纹理源帧 `6579489`；
- `productCandidate=false`；
- `stateQualification=INSUFFICIENT_EVIDENCE`。

这证明研究内核可以连续处理长 PCM 并保留源身份，不证明 Honda 纹理像 Hellcat，也不证明任何 RPM/load/phase 对齐。

## 限制和下一步

- 该内核当前未接入 `core.mjs`、AudioWorklet、Android 或默认 bank；
- 公开录音仍没有同步 RPM/load/gear/720-degree phase；
- 下一步应在隔离 harness 中把 `RECORDED_PRIMARY`、`LEGACY_BANK` 和 `GENERIC_PHYSICS` 做同轨迹对照，再由 Jovi盲听；
- 不能因为连续性指标改善就宣称车型真实性完成。
