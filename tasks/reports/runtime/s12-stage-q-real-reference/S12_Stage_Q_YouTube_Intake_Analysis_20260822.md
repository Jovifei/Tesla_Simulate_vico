# S12 Stage Q：真实车辆声源下载、切片与比较诊断报告（2026-08-22）

状态：`COMPLETE_DIAGNOSTIC_ONLY_R3` / `R1=0` / `R2=0` / `等待 Jovi 人耳 A/B`

## 结论先行

本轮已经把压缩包中的八车型目录按“每车 3 条”落成 24 条外部来源，并完成了视频→无增益 PCM WAV→SHA-256→抽帧→派生特征→Comparator 诊断链。第一次批量下载受到 YouTube 403/SABR 影响，仅 1/24 条视频完整；Android 客户端回退得到 21 条可用记录，另外 3 条保留为不完整容器并用替代 URL 补齐组合库。针对原始 3 条又用 `yt-dlp + Node.js EJS + web_embedded` 重试：`yXw_35i3RMM` 通过完整视频/音频解码；`XWEjZHFQ5lc` 和 `GQ0972wohFs` 的视频仍是“可探测头部、媒体体不完整”，但新增的 `web_embedded` 音频格式 `140-9`/`140-8` 已分别完整下载并通过解码校验。随后发现系统代理 `127.0.0.1:7890` 是批量媒体直链 403 的主要触发条件之一；在全新目录关闭代理并按客户端回退后，原始 24 条 URL 的音频流全部取得并通过解码验证（`24/24`）。这不等于原始视频 `24/24` 恢复，也不等于真实原厂声浪闭环完成。

这不等于“真实原厂声浪闭环完成”。严格门禁下 24 条全部是 `R3`：公开 YouTube 视频的授权收据、精确原厂排气确认、同步 RPM/负载/挡位、麦克风与 AGC 采集合同均未提供。Comparator 结果只能作为数字域相对诊断；阶次、身份分数、自动调参和 Profile 更新均明确关闭。

## 按用户指定顺序的执行核对

| 顺序 | 本轮结果 | 是否可进入调音 |
| --- | --- | --- |
| 人工确认原厂状态 | 已检查 8 张车型接触表、24 条来源；车型/家族画面可见，但所有“原厂排气”保持 `NOT_CONFIRMED`。LFA Nürburgring、GT-R NISMO、C63 Black Series、Hellcat Stock/Muffler Delete 等变体风险已标出。 | 否 |
| 合法保存到仓库外 | 已保存至 `E:\\Claude_allow\\Download\\s12-real-vehicle-source-library-v1-20260822`；首轮 403 目录和重试日志保留为诊断证据，原始版权媒体未进入 Git。 | 仅作外部审计输入 |
| URL + SHA + provenance | 24/24 条有最终 URL、视频 SHA、WAV SHA、外部路径别名、标题、工况、来源页和替换说明。规范入口为外部 `intake_manifest_combined_v1.json`。 | 否，授权仍未核验 |
| 工况切片 | 每条生成 `context_head`、`scenario_candidate_peak`、`context_tail`，共 72 个窗口。切片依据为能量峰启发式+目录工况标签，状态标记 `PROVISIONAL_NO_SYNC_STATE`、置信度 `LOW`。 | 否 |
| R1/R2/R3 分类 | 24 条全部 `R3`；没有任何 R1/R2。公开视频有损派生音频和未核验授权不能升级。 | 否 |
| Comparator | 24 条与仓库内对应车型的本地合成 A/B WAV 做了重采样后数字域相对比较；输出频谱、响度、频段和心理声学差异。结果标记 `DIAGNOSTIC_ONLY_R3`，不产生身份结论。 | 否 |
| 人耳 A/B | 已生成中文 A/B 任务清单，引用外部 WAV 路径和仓库内合成候选；尚未收到 Jovi 的逐条听感记录。 | 等待 Jovi |
| 带不确定性的参数建议 | 已按每车 3 条来源汇总中位数、四分位数和范围，输出低置信诊断方向；`WITHHELD_NO_AUTO_TUNING`，不写入声浪调节系统。 | 否 |

## 归档与下载证据

- 输入压缩包 SHA-256：`139A7EC28DE65CF446096A230C6ACBE95D0BD9F902F00A913A57D993305CD375`（已匹配）。
- 压缩包安全解压：3 个文档文件，无路径穿越；解压目录位于仓库外。
- 最终来源数：`8 × 3 = 24`，每车型 3 条，URL 唯一。
- 视频/WAV：组合库 `24/24` 可探测、可读取；原始 3 条专门复核的完整视频仍为 `1/3`，但直接无代理音频重试已使原始 24 条 URL 的完整可解码音频达到 `24/24`。对应外部清单为 `retry_direct_20260822_v1/youtube_retry_direct_audio_manifest_v1.json`（SHA-256 `45DDB25441D3F09A35D6875011A8CBF2726DD03D921069F013B1E94385F4FD3F`），`decode_validation_v1.json`（SHA-256 `C881F8790B52426F5C9F6FF5CF8A57EF76670C5A651FCE32AAB0DEF3AECA7CE4`）。这只代表音频流完整，不把视频完整率改写为 `24/24`；WAV 为无增益 PCM 解码产物，未做 EQ/AGC/响度匹配。
- 抽帧：每条最多 12 帧；当前环境没有 Tesseract，OCR 状态为 `NOT_AVAILABLE_TESSERACT_MISSING`，没有把仪表读数当作 RPM 证据。
- 首轮失败物：`intake_20260822_v1` 保留 403/不完整下载日志；`intake_20260822_v2` 保留 21 条可用记录和 3 个损坏容器，`intake_replacements_20260822_v1` 提供 3 条替代 URL。Node.js/Web 客户端重试证据在外部 `retry_js_20260822/youtube_retry_js_manifest_v1.json`，其中两条视频仍标为 `INCOMPLETE_MEDIA_BODY`；仅音频成功回退及 WAV SHA 在 `audio_format_retry_20260822/youtube_retry_audio_manifest_v2.json`。没有删除或覆盖首轮证据。

## 派生结果（全部在仓库外）

外部分析根目录：
`E:\\Claude_allow\\Download\\s12-real-vehicle-source-library-v1-20260822\\analysis_20260822_v1`

- `source_analysis_manifest_v1.json`：24 条外部路径别名、URL、SHA、来源和门禁状态。
- `derived_features_v1\\<selection_id>.json`：每条的 WAV 头、三段切片、频谱、响度代理、心理声学代理和瞬态代理。
- `scenario_segments_v1.json`：72 个低置信工况候选窗口；不得用于阶次或调参。
- `comparator_diagnostics_v1.json`：24 条“真实公开视频派生音频 vs 本地 synthetic 候选”的相对差异。
- `human_ab_package_v1.json`：中文 A/B 任务清单，状态 `WAITING_FOR_JOVI_LISTENING`。
- `parameter_diagnostics_v1.json`：每车 3 条来源的带不确定性诊断方向，状态 `WITHHELD_NO_AUTO_TUNING`。
- `retry_js_20260822/youtube_retry_js_manifest_v1.json`：Node.js/Web 客户端回退、文件 SHA、ffprobe/ffmpeg 完整性校验和 403/截断结论；原始媒体仍只在仓库外。
- `audio_format_retry_20260822/youtube_retry_audio_manifest_v2.json`：两条截断视频的 `web_embedded` 仅音频成功回退、压缩音频/WAV SHA、44.1 kHz/2 ch 解码校验；仍标为 R3，未进入 R2 或调参。
- `retry_direct_20260822_v1/youtube_retry_direct_audio_manifest_v1.json`：关闭系统代理后的原始 24 条 URL 音频重试清单，记录客户端、外部路径、容器、编码、时长、SHA-256 和 R3 门禁；`decode_validation_v1.json` 记录 24/24 的 `ffmpeg` 解码验证。

Git 只保留本报告、入口代码和这些外部产物的路径/SHA/派生特征引用；没有复制任何原始视频或版权音频。

## Comparator 诊断摘要（不是合格度或相似度百分比）

以下是 3 条来源的中位数，仅用于定位“应该先听哪里”，不代表 OEM 差异：

| 车型 | 频谱对数距离 | 响度差（本地−参考） | 频谱重心差 Hz | 最大频段差 | 诊断方向（需人耳确认） |
| --- | ---: | ---: | ---: | --- | --- |
| Aventador LP700 | 0.7224 | -8.114 dB | -153.3 | 250–400 Hz: +0.0897 | 本地中低频相对偏高，先听主体厚度 |
| C63 W204 | 0.7872 | -0.419 dB | +121.5 | 400–1000 Hz: +0.2736 | 本地中频相对偏高，先听机械主体 |
| Ferrari 458 | 0.6578 | -6.999 dB | +317.1 | 1000–4000 Hz: +0.4826 | 本地中高频相对偏高，先听明亮/刺耳感 |
| GT-R R35 | 0.7808 | +3.536 dB | -99.0 | 400–1000 Hz: +0.2678 | 本地中频相对偏高，先听厚度与压迫感 |
| Hellcat | 0.6734 | -3.840 dB | +89.4 | 120–250 Hz: -0.3340 | 本地低中频相对偏低，先听 V8 主体是否不足 |
| LFA | 0.7093 | -5.254 dB | +859.6 | 250–400 Hz: -0.5760 | 本地低中频相对偏低、高频重心偏上，先听 V10 金属感 |
| RX-7 FD | 0.8352 | +3.389 dB | -502.1 | 120–250 Hz: +0.8324 | 本地低中频相对偏高，先听转子主体/轰鸣 |
| Supra JZA80 | 0.8149 | -9.304 dB | -82.4 | 60–120 Hz: +0.3341 | 本地低频相对偏高，先听涡轮/低频轰鸣 |

这些数值受公开视频编码、麦克风位置、车速/转速、环境和切片启发式影响很大；不能直接转成增益、滤波器或 Profile 参数。

## 仍未闭环的真实阻塞

1. 来源授权或 Jovi 可审计的使用许可收据。
2. 精确年份/Trim/市场配置和原厂排气确认；画面只能支持车型身份，不能证明“原厂”。
3. 与音频同步的 RPM、Load/Throttle、Gear/shift 和可复核事件时间轴。
4. 固定麦克风位置、录音设备、采样链和 AGC/后处理合同。
5. Jovi 对每车/每工况的中文 A/B 听感记录，并以 `selection_id + WAV SHA-256` 绑定。

补齐这些输入后，才可以把合格记录提升到 R2/R1，运行阶次/状态门禁，并把经过人耳确认的差异反馈给声浪调节系统。当前不会启动 MATLAB 调参，也不会修改任何车型 Profile。
