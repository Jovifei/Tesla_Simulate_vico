# S12 真实声浪闭环总报告

状态：`R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED / WAITING_FOR_JOVI_HUMAN_FEEDBACK`

> 本报告是当前 HEAD 的等待态审计，不是“本地声浪与真实声浪比较、反馈和调优闭环已完成”的声明。

下载恢复补充：在仓库外独立目录 `retry_tools_20260822_v2` 关闭本机代理并启用 Node.js EJS 后，24 条最终视频均通过严格全流解码；两条短头部文件使用 `134 + 140-9/140-8` 分流回退。严格清单 SHA-256 为 `E029D78938C6B21DB7FD612E8693362A25BED122A0DF73602F0E87CB92F7208E`，恢复收据 SHA-256 为 `A5D49E871505A7FAEF6EBEF316191356F06976AB18E8A2830B4BE82355914DF4`。这只把外部媒体完整性从初始 `1/24` 恢复为 `24/24 COMPLETE_DECODABLE`，不改变其 YouTube 派生、未授权/未同步的 `R3` 资格。

当前环境对照探针：使用不读取账号 Cookie 的 Node.js EJS，对 `cKx-cb0fzeo` 分别走默认代理和 `--proxy ""` 的 `bestaudio/best` 请求，挑战解析成功但签名媒体请求两次均为 `HTTP 403`，没有生成新的完整媒体。探针收据已写入 Stage Q，旧的 24/24 外部解码收据保持不变。

最终视频绑定的 R3 重算也已完成：从上述 24 条最终视频重新抽取无增益 PCM WAV，并用 intake manifest SHA `2432218DFEF56CAE8A4FA4B475A1A7AEBB43BAB4BA9EBEC7459A4346611881CF` 绑定到分析收据 `final_video_analysis_receipt_v1.json`（SHA-256 `62492F2CABE3BBDF6606E7E1C16CAC4FE1703F784E4185D25D8C5D28841C1175`）。中文差异报告位于仓库外 `analysis_final_video_r3_v1/S12_Stage_R_Final_Video_R3_Difference_Report_20260822.md`，SHA-256 `60EAC35526ECF922EC50605EDF320F2A2BFCCD2CD06DA6BC38BF41054FD8F71D`。该结果是 24/24、8 车各 3 条的最新 R3 数字域诊断，不是 R1/R2 资格，也没有启动 MATLAB 阶次、自动调参或 Profile Candidate。

公开来源补充审计：新增一条 Freesound CC0 Ferrari 458 Italia GT3 页面/预览并完成 SHA 与容器核验；由于文件混合 17 辆 GT 赛车且没有 Ferrari 段落时间绑定或同步状态，登记为 `R2_CANDIDATE_NOT_COMPARISON_READY`，没有进入 R2 指标或调音，R1 仍为 0。

## 阶段状态

| 阶段 | 当前状态 | 已完成内容 | 未完成内容 |
| --- | --- | --- | --- |
| Q 真实参考 | `REAL_REFERENCE_DATASET_LIMITED` | 原有目录审计加 3 条明确 CC/CC0 许可的 R2 参考；RX-7 仅新增 1 条 R3 旋转机械演示；另审计 1 条 CC0 非目标 Pontiac G8 测功机视频作为 R3 流程样本；记录 3 条商业 R1 采购候选 | R1 元数据和同步 RPM/state；商业候选尚未购买/授权和验收 |
| R 差异基线 | `R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED` | Ferrari 458、Hellcat、Supra 已完成未增益分析信号的 R2 频谱/响度/心理声学相对比较；R1 SHA-bound MATLAB/MoSQITo 输入准备仍在 | R1 阶次资格、自动调参、真实人耳反馈 |
| S 反馈调音 | `R2_AB_PACKAGE_READY / WAITING_FOR_JOVI_HUMAN_FEEDBACK` | 已生成仓库外中文 R2 A/B 包，3 个案例绑定参考/候选 SHA；RX-7 FD 明确排除为 R3 | 没有真实 Jovi 听审和调音轮次 |
| T Profile Candidate | `BLOCKED_PROFILE_CANDIDATE_NOT_READY` | Profile Candidate 阻断门和交接模板 | 没有候选参数包或产品交接 |

补充证据：原始 24 条 YouTube URL 已重新完成直接无代理音频下载与现有 Comparator 的 R3 诊断（8 车各 3 条）。该补充不改变 R2/R1 门禁；机器收据位于外部 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_direct_20260822_v1\analysis_r3_direct_v1\direct_analysis_receipt_v1.json`，SHA-256 为 `A007C99EAC91D3A875EF3EDEF4E2A6433EBF6AC18BF1F724D9DD89D46F778876`。

同步录音采购线索也已完成只读页面/曲目单核验：Ferrari 458、Hellcat、RX-7 1990 三项均为 `PROCUREMENT_CANDIDATE_NOT_R1`，没有购买、版权原始音频或数值 RPM/state 收据。外部候选审计 JSON 为 `E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\candidate_source_audit_v1.json`，SHA-256 为 `082bc43c24ba1aa84f9450fe826244376925bb58c040999ea032396077f8c636`；许可页还要求购买后许可，并限制未同步素材复制和 AI 训练/开发，使用前需完成范围确认。

## 八车型与工况

当前八车型全部没有 R1 资格；已有文件只能作为未授权/未对齐候选，不能进入自动调参。

| 车型 | 已登记候选 | R1 | 可资格指标 |
| --- | ---: | ---: | --- |
| 法拉利 458 | 2 | 0 | R2 频谱/响度/心理声学；无阶次 |
| 道奇 Hellcat | 5 | 0 | R2 频谱/响度/心理声学；无阶次 |
| 马自达 RX-7 FD | 2 | 0 | R3 定性旋转纹理；无 R2/R1 |
| 兰博基尼 Aventador LP700 | 1 | 0 | 无；待授权和状态绑定 |
| 奔驰 C63 W204 | 3 | 0 | 无；待授权和状态绑定 |
| 日产 GT-R R35 | 3 | 0 | 无；待授权和状态绑定 |
| 雷克萨斯 LFA | 1 | 0 | 无；待授权和状态绑定 |
| 丰田 Supra JZA80 | 2 | 0 | R2 频谱/响度/心理声学；无阶次，代际未核实 |

已识别的工况提示包括 idle、steady/acceleration、full_pull、shift、lift/afterfire 等；当前窗口均为文件名或旧注释推断，未达到场景资格。

## 指标与人耳边界

- 阶次 / Order-RPM：`NOT_QUALIFIED`，所有新增公开素材都没有同步 RPM。
- 频谱、响度、心理声学：Ferrari 458、Hellcat、Supra 均只有 R2 相对数字域结果；不输出真实性百分比，不复用旧报告数字。
- 瞬态：没有同步 Gear/shift/state；不进入自动门。
- 人耳：真实 Jovi 反馈行数为 0；Stage P fixture 不算人耳反馈。R2 A/B 包路径为 `E:\Claude_allow\Download\s12-stage-s-human-ab-r2-20260822`，study manifest SHA 为 `9471784e875c98beb2e2ea91081f1ffa87f851ff461bd8e405d414d3447411e6`。
- 真实性百分比：禁止输出。

## 调音与交接

- 调音轮次：0。
- 车型 source/profile 参数修改：0。
- `approved_profile_candidate/`：未生成。
- Profile Freeze：未授权。
- Simulink、Runtime、Android、ESP32、CAN、实车部署：未进入。
- Track-P：按边界未修改。

## 当前提交与 Git 状态

- 分支：`agent/s12-stage-q-real-reference-calibration`
- 报告基线提交：`b915b99`（历史 YouTube 403 回退与外部 R3 诊断）；直接无代理音频 R3 补充提交为 `87c7bc8`；本轮商业同步候选审计提交为 `b0fbf5b`，最终 SHA 以 `git rev-parse HEAD` 和远端核验为准。
- working tree：提交前必须为干净；本报告不得把外部试听副本写入 Git。
- push：是
- merge：否
- PR：否

## 必须补齐的输入

1. 三个锚点的 R1 真实车辆原始录音及同步 RPM、Load/Throttle、Gear/shift；
2. 精确车型/配置/原厂状态、场景、麦克风位置和 AGC/后处理合同；
3. 真实 Jovi 中文听审结果及播放元数据；R2 结果不能替代 R1 或人耳反馈。

本轮 R2 结果：`tasks/reports/runtime/s12-stage-r-real-sound-difference/web-authorized-20260822/`；中文 A/B 包：`E:\Claude_allow\Download\s12-stage-s-human-ab-r2-20260822`；原始媒体和试听副本均存于仓库外，Git 只保存许可、路径、SHA-256 和派生合同。

所有产物继续声明：`synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。
