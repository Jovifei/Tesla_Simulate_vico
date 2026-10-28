# 三路研究对照结果（2026-10-28）

目的：在不依赖 R1 同步状态、不接入产品的情况下，比较连续混合纹理、legacy bank 和 generic physics 的同轨迹输出安全/连续性。

固定轨迹：60 秒，`15s idle → 15s acceleration → 15s high-rpm → 10s coast → 5s idle`，全程不 reset。

| 纹理 | 路由 | RMS | Peak | 最大样本跳变 | 状态 |
|---|---|---:|---:|---:|---|
| Honda F20C | RECORDED_PRIMARY | 0.131711 | 0.288303 | 0.000299 | RESEARCH_ONLY |
| Honda F20C | LEGACY_BANK | 0.224446 | 0.404000 | 0.002358 | RESEARCH_ONLY |
| Honda F20C | GENERIC_PHYSICS | 0.242364 | 0.448414 | 0.005320 | RESEARCH_ONLY |
| Ferrari 250 GTO | RECORDED_PRIMARY | 0.131785 | 0.348461 | 0.002313 | RESEARCH_ONLY |
| Ferrari 250 GTO | LEGACY_BANK | 0.224446 | 0.404000 | 0.002358 | RESEARCH_ONLY |
| Ferrari 250 GTO | GENERIC_PHYSICS | 0.242364 | 0.448414 | 0.005320 | RESEARCH_ONLY |

输入纹理 SHA 和三路输出 SHA 见各自目录的 `three-way-research.json`。临时 PCM 已删除，仓库不携带大音频。

## 结论

连续混合纹理路由在这两个公开输入上均保持有限值和峰值安全；Honda 输入的最大跳变明显低于 legacy/generic，Ferrari 输入与 legacy 接近。这个指标只证明渲染连续性，不能证明车型身份、RPM/load/gear/phase 对齐或人耳真实性。所有路线仍为 `INSUFFICIENT_EVIDENCE`、`productCandidate=false`。
