# Stage AF 状态：回到已通过人耳方向的 main，并清理生成物

日期：2026-09-06

## 决策

用户实际试听否决 Stage AE 输出，认为声音非常差；同时明确 `main=f81d3a3aa1b32fcd35aa8b66a253492c70ed47b4` 的 Engine-Sim-inspired 四车版本约 70–80% 相似。

因此：

- Stage AE = `HUMAN_FAIL / DO_NOT_USE_AS_SOUND_BASELINE`；
- Stage AF 基于 main f81d3a3；
- `EngineAcoustics.render_track()` 保持声音 authority；
- 自动负反馈直接围绕该 renderer；
- 原 review workbench 保留；
- generated WAV/Base64 HTML 移出 Git。

## Stage AF 已实现

1. `stage_af/physical_closed_loop.py`：bounded physical parameter fitting；
2. `stage_af/fit_cli.py`：本地执行入口；
3. `stage_af/build_existing_dashboards.py`：把 fit 注入原 Stage-AD dashboard generator；
4. 原服务端口保留；
5. deterministic render seed；
6. frequency-band + spectral centroid + envelope/flux fixed-distance；
7. R3 evidence boundary 不变。

## 负反馈现状

旧 closed loop 的控制器结构值得复用，但 renderer 对象错误。Stage AF 修成：

`Reference -> EngineAcoustics -> audio features -> bounded physical params -> EngineAcoustics -> A/B Human`。

## 仓库清理

删除可再生成的四套 review package 目录。Hellcat 单独：`index.html ≈ 34.5 MB`，另有约 10 个 1.1–1.3 MB candidate WAV、references/web_audio；四车重复提交严重拖累同步。

删除历史重复压缩包：

`tasks/reports/runtime/S12_Acoustic_Realism_Phase_Review_2026-08-04.zip`

历史 SHA256：`a42f880e416760793198d5a3673072ead03eda1d5a8a814754ed497def3cd7bb`。

解压后的历史报告/evidence 仍保留，因此没有丢掉工程结论。

## 当前仍保留

- `review_packages/index.html` 门户；
- `review_packages/serve_dashboards.py`；
- dashboard template/generator；
- source/tests/reference manifests/receipts；
- 历史报告文本与关键 JSON evidence。

## 下一步

本地 AI 拉 Stage AF：先跑 fit，再用原工作台试听。Jovi 明确听感通过后才决定参数是否升级为 Engineering Profile。Android 继续后置。
