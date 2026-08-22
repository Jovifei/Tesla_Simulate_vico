# S12 Stage Q 真实参考数据报告

状态：`REAL_REFERENCE_DATASET_LIMITED` / `R2_REFERENCES_AVAILABLE_R1_BLOCKED`

## 结论

本轮审计外部本地参考，并在 Jovi 明确授权后新增了三条带可审计 Creative Commons/CC0 许可的公开声浪参考。它们只进入 R2 有限比较；不会被伪装成 R1，也不会触发阶次硬门或自动调参。原始音频没有复制进 Git；仓库只保存路径指针、SHA-256、音频容器信息、许可证据和缺口。当前仍没有任何记录满足 R1，因此真实阶次基线、自动参数建议和调音闭环不能启动。

## 车型覆盖

| 车型 | 记录数 | 可读取 | R1 | R2 | R3 | 当前状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 法拉利 458 | 2 | 2 | 0 | 1 | 0 | `R2_AVAILABLE_R1_BLOCKED` |
| 道奇 Hellcat | 5 | 5 | 0 | 1 | 0 | `R2_AVAILABLE_R1_BLOCKED` |
| 马自达 RX-7 FD | 2 | 2 | 0 | 0 | 1 | `R3_ONLY_R1_BLOCKED` |
| 兰博基尼 Aventador LP700 | 1 | 1 | 0 | 0 | 1 | `R3_ONLY_R1_BLOCKED` |
| 奔驰 C63 W204 | 3 | 3 | 0 | 0 | 3 | `R3_ONLY_R1_BLOCKED` |
| 日产 GT-R R35 | 3 | 3 | 0 | 0 | 3 | `R3_ONLY_R1_BLOCKED` |
| 雷克萨斯 LFA | 1 | 1 | 0 | 0 | 1 | `R3_ONLY_R1_BLOCKED` |
| 丰田 Supra JZA80 | 2 | 2 | 0 | 1 | 1 | `R2_AVAILABLE_R1_BLOCKED` |

## 外部目录审计

本轮已审计以下外部媒体目录；未登记音频只保留路径和 SHA-256，不进入分析、听审包或调音：
- `E:\Claude_allow\Download\tesla-sound-research`
- `E:\Claude_allow\Download\tesla-sound-research-v12`
- `E:\Claude_allow\Download\s12-acoustic-realism-v10`

## 新增公开许可参考（2026-08-22）

| 记录 | 车型/场景 | 许可证据 | 解码文件 | 证据等级 | 可用范围 |
| --- | --- | --- | --- | --- | --- |
| `web_ferrari_458_goodwood_2010` | Ferrari 458 / 从起点驶出加速 | [Wikimedia Commons 页面](https://commons.wikimedia.org/wiki/File:Ferrari_458_Italia.ogg)，CC BY-SA 3.0，作者 Edvvc | 外部 WAV，44.1 kHz / 2 ch / 24 bit，11.638s，SHA-256 `44b236ac66d3` | `R2` | 频谱、响度、心理声学、主观瞬态 |
| `web_hellcat_launching_sound_2019` | Dodge Challenger Hellcat / 启动或起步声 | [Wikimedia Commons 页面](https://commons.wikimedia.org/wiki/File:Launching_sound_Challenger.ogg)，CC BY-SA 4.0，作者 Axepas12 | 外部 WAV，44.1 kHz / 1 ch / 24 bit，6.548s，SHA-256 `b5a23a855b80` | `R2` | 频谱、响度、心理声学、主观瞬态 |
| `web_supra_jza80_chassis_dyno_cc0_2019` | Toyota Supra / 底盘测功机全油门拉升 | [Freesound 页面](https://freesound.org/people/editboy23/sounds/496171/)，CC0 1.0，作者 editboy23 | 外部 HQ MP3 预览解码 WAV，48 kHz / 2 ch / 24 bit，35.469s，SHA-256 `029c95505a09` | `R2` | 频谱、响度、心理声学、主观瞬态；有损预览，车型代际未核实 |

三条 R2 记录都缺同步 RPM、Load/Throttle、Gear/shift、麦克风与 AGC 合同，故 `R1=0`、阶次硬门关闭、自动调参关闭。Supra 记录明确是测功机全油门，但页面未核实 JZA80 代际且下载的是公开 HQ MP3 有损预览。Wankel3.ogv（CC BY-SA 2.5）是 Mazda 13B 机械演示，不是 RX-7 FD 整车录音，已登记为 `R3 qualitative_only`，不进入 R2。

本轮另外下载并审计了 [Wikimedia Commons 的 Pontiac G8 测功机视频](https://commons.wikimedia.org/wiki/File:Metro_Cruise_2019_Dyno_test.webm)。该文件为 CC0、约 9 秒；抽取出的单声道 48 kHz WAV 峰值达到 `1.0`，抽帧未看到数值转速表或同步状态。它已登记为非目标车型 `R3` 测功机流程样本，只能验证“视频→音频→元数据审计”路径，不进入八车型 R2/R1、阶次比较、自动调参或 Profile Candidate。

## 公开同步数据检索结论（未纳入）

- [F1Audio](https://zenodo.org/records/21186137) 页面声称提供约 300 小时的 F1 车载声学特征与同步 RPM、挡位、油门，但 Zenodo 文件受限访问，且车辆不是本项目八个锚点，因此不能作为本项目 R1 输入。
- [Procedural Engine Sounds Dataset](https://huggingface.co/datasets/rdoerfler/procedural-engine-sounds) 把真实录音提取的结构用于程序化扩增；其公开说明明确是合成数据。即使通道嵌入 RPM/扭矩，也不能替代真实车辆原始录音。
- [Sounds of Vehicle Internal Combustion Engines](https://zenodo.org/records/18777405) 以 CC BY 4.0 发布真实车辆声样本，但页面只描述怠速和部分负载/加速片段，没有与本项目锚点绑定的同步 RPM、挡位、麦克风和 AGC 合同；因此不升级为 R1。本轮只下载并核验 51 MB 的 Petrol ZIP，未下载 Diesel ZIP。

### 公开发动机声数据集筛选结果

- 外部文件：`E:\Claude_allow\Download\s12-public-vehicle-engine-ccby4-20260822\Petrol Motor Sounds.zip`；官方 MD5 与本地实测均为 `896accd703c04b46af23485698ce6c45`，本地 SHA-256 为 `ee7faf50612dc7d5f001cd8b190eb3ea1d5846ae6ffc4adfe7b03a6b36f71a66`。
- ZIP 内有 137 个 `PetrolClean/REC*.wav`、0 个 CSV/JSON/README/metadata 条目；未发现 Ferrari 458、Dodge Challenger Hellcat 或 Mazda RX-7 FD 的可绑定车型/Trim，也没有 RPM、Load/Throttle、Gear/shift、麦位或 AGC 字段。
- 筛选清单：`E:\Claude_allow\Download\s12-public-vehicle-engine-ccby4-20260822\screening_manifest.json`，SHA-256 `a87f11b45b14cbd9ca4a48e6ea20c9ed1543570407bc45c606d58de314dba2cb`。结论为 `NOT_TARGET_BINDABLE_NO_MODEL_OR_STATE`，保留公开来源与校验记录，但不进入 R1/R2、Comparator 或调参。

## 本轮继续检索复核（2026-08-22）

- [Dodge Challenger Hellcat 2015 音效目录](https://www.asoundeffect.com/wp-content/uploads/2020/02/Dodge_Challenger_Hellcat_2015.pdf) 列出了 96 kHz/24 bit、steady RPM、车载/车外多麦位等商业录音条目；它只是目录/采购线索，当前没有取得原始文件、授权收据或同步状态文件，因此保持 `PROCUREMENT_CANDIDATE_NOT_R1`，不下载预览、不进入比较。
- [VS13 音视频车辆速度数据集](https://slobodan.ucg.ac.me/science/vs13/) 提供 13 种非本项目锚点车型的 400 段道路通过视频/音频，标注是恒定道路速度和通过时刻，不是 RPM、Load/Throttle 或 Gear/shift；不纳入八车型参考，只保留为方法学线索。
- [Procedural Engine Sounds Dataset](https://huggingface.co/datasets/rdoerfler/procedural-engine-sounds) 虽然提供时间对齐的 RPM/扭矩通道，但官方说明明确为程序化合成音频，并包含虚构发动机/排气配置；它不能替代真实车辆原始录音，继续排除在 Stage Q R1/R2 之外。
- [RX-7 免费音效页面](https://www.instantsoundfx.com/audio/mazda-rx-7-brap-brap-brap/) 声称可免费下载和免版税，但没有可核验的实车录音作者、车型配置、采集链或同步状态；最多只能作为 R3 定性线索，不下载、不升级为 RX-7 FD 实车证据。

## YouTube 403 重试复核（2026-08-22）

- 原始 3 条失败 URL 继续保留在外部 `retry_js_20260822`；`yXw_35i3RMM` 为完整可解码视频，`XWEjZHFQ5lc` 与 `GQ0972wohFs` 的视频容器仍为 `INCOMPLETE_MEDIA_BODY`。
- 对后两条新增 `web_embedded + Node.js EJS` 的仅音频格式回退：`XWEjZHFQ5lc` 的 `140-9` 与 `GQ0972wohFs` 的 `140-8` 均取得完整 44.1 kHz / 2 ch AAC，并通过 `ffprobe` + `ffmpeg` 解码；同时生成外部 PCM WAV。清单为 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\audio_format_retry_20260822\youtube_retry_audio_manifest_v2.json`，SHA-256 `09FEB0090619F55F281D540BA433059E131706079108C8C848619AFAB9E1F5B1`。
- 这把“可用音频流”从 `1/3` 提升为 `3/3`，但没有把“原始视频完整率”改写为 `3/3`；三条仍是未核验 YouTube 授权、原厂状态与同步状态的 `R3`，不进入 R2 基线、阶次门、Comparator 资格或自动调参。

### 直接无代理音频重试（2026-08-22）

- 复核发现系统代理 `127.0.0.1:7890` 会让 `googlevideo` 媒体直链返回 HTTP 403。保留所有首轮失败物后，在全新外部目录使用 `yt-dlp 2026.06.30.234726 + Node.js EJS`，关闭代理（`--proxy ""`），按 `web_embedded → android_vr → tv_embedded → mweb` 回退，仅请求音频格式。
- 原始 24 条 URL 的音频流均取得完整可探测文件（`24/24`），外部清单为 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_direct_20260822_v1\youtube_retry_direct_audio_manifest_v1.json`，SHA-256 `45DDB25441D3F09A35D6875011A8CBF2726DD03D921069F013B1E94385F4FD3F`。
- 对选定音频逐条运行 `ffmpeg -v error -map 0:a:0 -f null -`，解码验证 `24/24`；验证清单 `decode_validation_v1.json` SHA-256 `C881F8790B52426F5C9F6FF5CF8A57EF76670C5A651FCE32AAB0DEF3AECA7CE4`。
- 这只证明“可下载、可解码的 YouTube 有损派生音频”完整，不证明原始视频 `24/24`、授权、原厂状态、麦克风/AGC 或同步 RPM/负载/挡位。24 条继续保持 `R3`，不得进入 R2、阶次门、Comparator 合格输入或自动调参；原始文件仍只在仓库外。

### 视频体恢复重试（2026-08-22，后续收据）

- 在独立外部目录 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_tools_20260822_v2` 使用 `yt-dlp 2026.06.30.234726 + Node.js EJS`、`--proxy ""`、`web_embedded` 和渐进式 360p/≤480p 格式重试；首轮 403 产生的 `.part`/截断物全部保留。
- 对 `XWEjZHFQ5lc`、`GQ0972wohFs` 仍返回短头部的两条，改用 `134` 视频 + 英文原声 `140-9`/`140-8` 分流合并；随后对 24 个最终候选执行 `ffprobe`、`ffmpeg -xerror -err_detect explode` 全流解码和 info.json 时长对照，结果为 `24/24 COMPLETE_DECODABLE`。
- 最终严格收据：`strict_decode_manifest_v3.json`，SHA-256 `E029D78938C6B21DB7FD612E8693362A25BED122A0DF73602F0E87CB92F7208E`；恢复策略和旧失败物收据：`download_recovery_receipt_v2.json`，SHA-256 `A5D49E871505A7FAEF6EBEF316191356F06976AB18E8A2830B4BE82355914DF4`。
- `24/24` 只表示这些公开 YouTube 派生媒体在仓库外可完整解码；它们仍没有可审计授权、原厂状态或同步 RPM/Load/Throttle/Gear/shift，全部保持 `R3`，不得进入 R1/R2 阶次门或自动调参。

### 当前 yt-dlp 独立复试（2026-08-22）

- 默认 `android_vr` 客户端对 `XWEjZHFQ5lc` 复现 `HTTP 403`；`web_embedded + Node.js EJS` 的渐进式 `format 18` 生成的短头部通过 `yt-dlp` 表面成功，但被 `ffmpeg -xerror` 判定为 `partial file`，未计入完整率。
- 改用 `134 + 140-9`（XWE）和 `134 + 140-8`（GQ）分流后，两个视频均 `ffprobe=0` 且完整流 `ffmpeg -xerror=0`；残留 `.part`/短头部保留在外部目录，未覆盖旧证据。
- 外部收据：`E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_yt_dlp_current_20260822\yt_dlp_node_web_embedded_retry_receipt_v2.json`，SHA-256 `52996AB90C3145B292E0E2964560B70A2A2F46443283C0C79ED90458A94E5BF8`。本次只是下载完整性回退验证；两条仍是 YouTube 派生 `R3`，不进入 R1/R2、阶次门或调参。

### Node/EJS 当前环境对照探针（2026-08-22）

- 为区分客户端挑战解析与媒体出口拒绝，在不读取账号 Cookie 的前提下，对 `cKx-cb0fzeo` 以 `yt-dlp 2026.06.30.234726 + Node.js EJS`、`bestaudio/best` 分别使用默认代理和 `--proxy ""` 重试；两次都在签名 `googlevideo` 数据请求阶段返回 `HTTP 403`，没有产生新的完整媒体文件。
- 机器收据：`youtube_node_ejs_probe_20260822.json`；详细日志和元数据仍在外部 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_node_ejs_20260822`，不进入 Git。该对照结果不撤销上方已完成的 24/24 外部音频/视频收据，也不把任何截断物升级为可用录音。

### 当前批量独立重试（2026-08-23）

- 在全新外部目录 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1` 从 24 条原始 URL 重新开始，默认 `yt-dlp`（关闭代理）有 `22/24 HTTP 403`，仅 2 条直接取得媒体；每条默认日志和失败物均保留。
- 对失败项使用 `Node.js + EJS` 的 `android` client 回退，补齐 `22/22` 个媒体容器；再对最终 24 个候选逐条执行 `ffprobe`、`ffmpeg -xerror` 全流解码和无增益音频解码，结果为 `24/24 COMPLETE_MEDIA_AND_AUDIO`，并生成 `24/24` 外部 WAV。合并回执为 `youtube_retry_combined_receipt_20260823.json`（SHA-256 `0DAB94BFB99A4AEDC4855929A39EA211D958A4EAA6C3B9F3ADCE98F065363EEE`），严格解码回执为 `strict_decode_receipt_20260823.json`（SHA-256 `C120BFE16B0CEF5B80C68FC47E4FB2BB6198CE94BAE8EE1BF9243B04A965C782`）。
- 这次解决的是下载/解码完整性，不是来源资格：24 条仍是 YouTube 视频派生、授权/原厂排气/麦位与 AGC/同步 RPM-Load-Throttle-Gear 缺失的 `R3`；原始媒体与派生 WAV 只在仓库外，禁止进入 R1/R2 阶次门、自动调参或人耳资格门。
- 最新 24 条 WAV 已重新绑定到独立 R3 分析清单并运行现有 `analyze_downloaded_sources.py`：`24` 条特征、`72` 个低置信场景切片、`24` 条 Comparator 诊断、`24` 条中文 A/B 试次和参数诊断均生成；分析收据 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\r3_analysis_receipt_20260823.json` SHA-256 `18bea83f660d773b81b138a6982f01012a64cac9fcef8605c0d660dab3bdefc0`。状态仍为 `COMPLETE_DIAGNOSTIC_ONLY_R3`、`R1=0/R2=0/R3=24`、`WAITING_FOR_JOVI_LISTENING`，不得把低置信特征或人耳空白反馈写成调参结论。
- 为三锚点另行生成中文人耳 A/B 包：`E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1\README_中文.md`，Ferrari 458/Hellcat/RX-7 FD 各 3 个试次、18 个 5 秒试听片段；manifest SHA-256 `dc5bb05c24b338485f567b4e4107620aff76f8d210204b6cccae61eb4c4f6052`，receipt SHA-256 `fbcb0ccc701b4edfb20b371a13478ad8e2ac2172e3203bffb78e6ec15ff6ba6e`。包绑定 `test_id/file_id/reference SHA/candidate SHA`，反馈字段为空；它只支持 R3 定性试听，不是自动调参或资格门。

本轮没有新增合法、车型明确且可绑定同步状态的三锚点原始包，Stage Q 仍保持 `REAL_REFERENCE_DATASET_LIMITED / WAITING_FOR_REAL_REFERENCE_DATA`。

### 公开同步数据复核（2026-08-22）

- [F1Audio](https://zenodo.org/records/21186137) 明确包含同步 RPM、挡位和油门，但文件受限访问，且对象是 F1 赛车，不是 Ferrari 458、Hellcat 或 RX-7 FD；不下载、不升级为锚点 R1。
- [Visual-Acoustic Vehicle Dataset](https://vehical.org/ITSDataset/) 提供时间戳、发动机 RPM、油门、挡位和车内/车外麦克风，但车辆是 Lincoln MKS；只作为方法学参考，不进入锚点资格。
- [HL-CEAD](https://github.com/MachineLearningVisionRG/machine_biometrics) 说明了 1000/1500/2000 RPM 的 WAV 录音、麦克风和录音设备，但车型不包含三个锚点，且只记录空挡稳态、没有数值负载/换挡轨迹；不进入 R1。
- Ferrari 458、Hellcat、RX-7 的专业库仍需购买或书面许可；供应商页面的“同步 take/steady RPM/gearshift”不是数值状态文件，继续登记为 `PROCUREMENT_CANDIDATE_NOT_R1`。本次未下单、未下载版权原始音频。
- 筛选收据：`public_sync_reference_search_audit_20260822.json`，SHA-256 `FB0660B24699791BB4613A4E45C5A492471C1DDF515638AA5BDBB1ADEB796B43`。该审计只保存 URL、字段证据和分类，不包含原始音频；当前锚点 `R1=0`、可用 R2=2、RX-7 FD 开放 R1 未找到。

### 新增 CC0 Ferrari 458 GT3 候选（2026-08-22）

公开检索补到一条 Freesound CC0 录音：[Moscow Raceway GT Race sounds](https://freesound.org/people/Walking.With.Microphones/sounds/556039/)。页面明确列出 `FERRARI 458 ITALIA GT3`，并注明 Zoom H6 录制；但同一文件还列出其他 16 辆 GT 赛车，没有分段时间绑定，也没有 RPM/Load/Throttle/Gear 状态。因此它只能登记为 `R2_CANDIDATE_NOT_COMPARISON_READY`，不进入当前 R2 指标、A/B 或调参。

- 外部目录：`E:\Claude_allow\Download\s12-freesound-authorized-20260822\ferrari_458_gt3_cc0`；原始/派生媒体均未进入 Git。
- 审计指针：[freesound_ferrari_458_gt3_cc0_audit_20260822.json](freesound_ferrari_458_gt3_cc0_audit_20260822.json)，其中绑定页面 SHA、MP3 SHA `48e347d37de126be15fefc188c2e62a281d186cafce6a15858abc3c1aa4fa49b` 和 PCM SHA `b0cc9e3d7d7b315420242d71478eb83f08841d954cb4559495711bd73318ea79`。

## 可采购/授权的 R1 候选（尚未纳入）

公开检索没有找到可直接下载、同时满足本项目 R1 合同的三锚点原始包。以下商业库是下一步最短路径，但当前没有购买或 Jovi 的使用授权，且网页营销描述仍需在取得文件后逐条验收，不能先标成 R1：

| 候选 | 页面公开信息 | 取得后必须补验 | 当前结论 |
| --- | --- | --- | --- |
| [Ferrari 458 2013（Sonniss）](https://sonniss.com/sound-effects/ferrari-458-2013/) | 页面列出 197 个文件、96 kHz/24 bit、29 声道、10 个同步 take，并描述 steady RPM、ramp、gearshift、多机位和 BWAV/Soundminer 元数据 | 原始 WAV/BWAV、每段数值 RPM 或可复核的同步 trace、Load/Throttle、Gear/shift 时间点、麦位、AGC/后处理、授权条款 | `PROCUREMENT_CANDIDATE_NOT_R1` |
| [Dodge Challenger Hellcat 2015（Sonniss）](https://sonniss.com/sound-effects/dodge-challenger-hellcat-2015/) | 页面列出 196 个文件、96 kHz/24 bit、12 个同步 take，并描述 onboard/exterior、steady RPM、ramp、gearshift 和 BWAV 元数据 | 同上；特别核验 6.2 HEMI 配置、录音是否含原始同步状态而非仅文件命名 | `PROCUREMENT_CANDIDATE_NOT_R1` |
| [Mazda RX-7 1990（Sonniss）](https://sonniss.com/sound-effects/mazda-rx-7-1990/) | 页面列出 208 个文件、96 kHz/24 bit、12 个同步 take，并描述 13B twin-turbo、steady RPM、ramp、gearshift、麦位和元数据 | 核验是否确为目标 FD 配置或明确可接受的 1990 车型、双转子事件与同步 RPM/负载/挡位 trace | `PROCUREMENT_CANDIDATE_NOT_R1` |

这三项页面显示的价格均为商业购买入口；本轮没有代 Jovi 下单，也没有把预览流保存为 R1。即使购买，仍必须先生成 `reference_id`、原始文件 SHA-256、时间轴/单位审计、采集合同和授权收据；验收不通过则降为 R2 或 R3。只有验收通过，才允许执行 MATLAB 阶次基线和自动调参。

## 记录审计

| 记录 | 场景提示 | 格式 | 时长 | SHA-256 前 12 位 | 证据等级 | 可用于调音 |
| --- | --- | --- | ---: | --- | --- | --- |
| `aventador_lp700_accel` | acceleration | 48000 Hz / 2 ch / 16 bit | 177.365s | `7dccc0bd4a55` | `R3` | 否 |
| `c63_w204_close_downshift` | shift | 48000 Hz / 1 ch / 16 bit | 12.014s | `4e7600abe78d` | `R3` | 否 |
| `c63_w204_headers_backfire` | afterfire | 48000 Hz / 1 ch / 16 bit | 62.009s | `3261aa79236a` | `R3` | 否 |
| `c63_w204_performance_accel` | acceleration | 48000 Hz / 1 ch / 16 bit | 143.787s | `534605237d62` | `R3` | 否 |
| `ferrari_458_accel` | acceleration | 48000 Hz / 2 ch / 16 bit | 212.160s | `22b0d0e1da61` | `R3` | 否 |
| `gtr_r35_nismo_accel` | acceleration | 48000 Hz / 1 ch / 16 bit | 119.993s | `dd3bd936f5d5` | `R3` | 否 |
| `gtr_r35_tomei_close` | afterfire | 48000 Hz / 1 ch / 16 bit | 30.014s | `4aeed8ff74b8` | `R3` | 否 |
| `gtr_r35_tuned_backfire` | afterfire | 48000 Hz / 1 ch / 16 bit | 68.661s | `0058a67bda86` | `R3` | 否 |
| `hellcat_burble_tune` | afterfire | 48000 Hz / 1 ch / 16 bit | 11.014s | `c062f3b8fd31` | `R3` | 否 |
| `hellcat_redeye_downshift` | shift | 48000 Hz / 1 ch / 16 bit | 25.014s | `4090dd9fa0f7` | `R3` | 否 |
| `hellcat_redeye_leave` | full_pull | 48000 Hz / 1 ch / 16 bit | 39.014s | `e5c29a92428b` | `R3` | 否 |
| `hellcat_stock_accel` | acceleration | 48000 Hz / 1 ch / 16 bit | 142.803s | `cf2ecf83c894` | `R3` | 否 |
| `lfa_full_accel` | full_pull | 48000 Hz / 2 ch / 16 bit | 90.430s | `ec75623d44c7` | `R3` | 否 |
| `rx7_fd_13brew` | acceleration | 44100 Hz / 2 ch / 16 bit | 63.948s | `c3458bd392e8` | `R3` | 否 |
| `supra_jza80_stock` | acceleration | 48000 Hz / 2 ch / 16 bit | 16.695s | `ccde31e8ec6e` | `R3` | 否 |

## 不能进入 R1/R2 的原因

- 缺少 Jovi 明确授权或可审计的合法来源记录。
- 没有任何记录绑定同步 RPM trace；不能执行 R1 阶次资格或自动调参。
- 没有可靠的 Load/Throttle、Gear/shift、麦克风位置和 AGC 记录。
- 公开/改装候选不能被当作原厂 OEM 参考。

目录中另发现 `18` 个未登记音频文件；它们只记录在 manifest 的 `unmapped_external_media`，不进入分析或调音。

## 后续必须补齐的输入

1. 有权使用的真实原始录音；不得只提供公开视频链接或无法确认权限的下载文件。
2. 精确车型/年份/市场/配置、原厂或改装状态及麦克风位置。
3. 与音频同步的 RPM；同时提供 Load/Throttle、Gear/shift 和场景起止点。
4. 录音设备、采样率、通道及 AGC/后处理说明。
5. Jovi 确认允许用于本地分析、派生特征和听审的授权记录。

在这些资料到位之前，Stage Q 只能保持 `REAL_REFERENCE_DATASET_LIMITED / WAITING_FOR_REAL_REFERENCE_DATA`；不会生成真实差异合格报告，也不会修改车型参数。

## 商业同步录音候选页面核验（2026-08-22）

本轮只下载公开商品页、许可页和曲目单 PDF，没有代 Jovi 下单，也没有把版权原始音频或试听流保存到本地。三项候选均保持 `PROCUREMENT_CANDIDATE_NOT_R1`：供应商页面对“同步 take、steady RPM、ramp、gearshift”的描述不能替代数值 RPM、Load/Throttle、Gear/shift 时间轴、采集链和授权凭证。

- Ferrari 458： [Pole Position Ferrari 458 2013](https://pole.se/product/ferrari-458-2013-2/) 声称 2013 F136 F 4.5 L V8、straight pipes、228 文件、11 个同步 take；外部候选审计 JSON 记录商品页快照 SHA `5f649fb8740d...78824a`、曲目单 SHA `565232a65620...dbda45`。
- Dodge Hellcat： [Sonniss Hellcat 2015](https://sonniss.com/sound-effects/dodge-challenger-hellcat-2015/) 声称 6.2 L HEMI V8、196 文件、96 kHz/24 bit、12 个同步 take；商品页快照 SHA `82c292e954e4...367802`、曲目单 SHA `1d0c9444c255...e6f9d`。
- RX-7： [Sonniss Mazda RX-7 1990](https://sonniss.com/sound-effects/mazda-rx-7-1990/) 声称 1990 13B Bridgeport twin-turbo、208 文件、96 kHz/24 bit、12 个同步 take；商品页快照 SHA `78b6108e5bbc...54634c`、曲目单 SHA `75e60b119cb1...524bad`。该配置与目标 RX-7 FD/原厂状态尚未确认等价。

完整 URL、绝对路径、抓取方法、完整 SHA 和许可限制见外部收据 `E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\candidate_source_audit_v1.json`（SHA-256 `082bc43c24ba1aa84f9450fe826244376925bb58c040999ea032396077f8c636`）。Pole Position 与 Sonniss 许可文字均要求购买后许可，并限制未同步素材复制；同时明确禁止 AI 训练/开发。若 Comparator→反馈系统被许可方认定为 AI 用途，使用前必须取得书面范围确认。当前 R1 仍为 0，阶次与自动调参继续关闭。

## R1 门禁加固（2026-08-22）

资格函数现要求 `vehicle_and_scenario_identity`、`source_and_license`、`raw_audio_source`、`sample_rate` 和明确的 `stock_exhaust_confirmation`，并拒绝 `video_extracted`/YouTube 来源即使其容器声称 PCM 或手工附带 raw receipt。完整 S12 回归为 `377 passed, 114 subtests passed`；当前三锚点重新审计仍为 `R1=0`，没有启动 MATLAB 阶次或自动调参。

raw intake manifest 现在可通过 `real_reference.cli --raw-reference-manifest` 合并到 canonical `reference_database_v2`；已审计的授权 R2 清单也可通过 `--authorized-reference-manifest` 合并。两者都只写入外部路径、SHA、provenance、证据等级和派生指针，不复制原始媒体，并通过 Stage Q JSON Schema。当前 canonical Q 已登记 Ferrari/Hellcat/Supra 各一条 R2，三锚点和其余车辆仍没有 R1。

## 原始录音 R1 入库与低速率状态绑定（2026-08-23）

新增 `tools/sound_sim/s12/real_reference/raw_audio_intake.py` 和中文 `RAW_AUDIO_INTAKE_GUIDE.md`。入口只接受批准外部目录中的原始 PCM WAV/FLAC、来源/授权凭证、精确车型与原厂排气确认，以及带明确单位和时间窗口的 RPM、Load/Throttle、Gear/shift CSV/JSON；只把 manifest、外部路径、原始 SHA-256、状态文件 SHA-256 与 provenance 写入元数据，绝不复制原始版权音频到 Git。YouTube/视频抽音即使完整解码仍被 R1 门禁拒绝。

Stage R 现在允许低于音频采样率的、带严格递增时间戳且覆盖窗口的状态遥测：RPM/负载/油门采用线性插值，挡位/换挡事件采用离散最近点映射到音频采样网格；没有时间戳的低速率状态、窗口外推或长度/单位不一致继续 fail-closed。FLAC 仅在外部临时 MATLAB 输入准备阶段无重采样解码，原始 FLAC SHA 保持绑定。

raw intake manifest 现在可通过 `real_reference.cli --raw-reference-manifest` 合并到 canonical `reference_database_v2`，同步生成 evidence matrix、带状态窗口的 `scenario_segments.json`、R1 `rpm_state_bindings.json`、provenance 和派生特征指针；合并过程不复制原始媒体，并通过 Stage Q JSON Schema。

本轮验证：Stage Q/R/S/T 定向测试 `18 passed`；完整 S12 `384 passed, 114 subtests passed`；Track-P `32 passed`；独立冻结守卫 `180 files / 2 symbols`；`compileall` 与 `git diff --check` 通过。验证的是入口和合同，不代表已有外部资料已经出现 R1；当前真实数据仍为 `R1=0`，MATLAB 阶次、真人 A/B 和调参继续关闭。

边界：所有产物继续标记 `synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。

## 中文离线 A/B 试听页（2026-08-23）

为三锚点 R3 诊断包生成 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1\index.html`，可在 Windows 中直接双击打开，无需 Docker、网页服务器或英文界面。页面绑定 9 个试次/18 个 5 秒片段，导出 JSON 时携带包清单 SHA `dc5bb05c24b338485f567b4e4107620aff76f8d210204b6cccae61eb4c4f6052`、片段 SHA、监听人编号、评分和备注；页面 SHA-256 为 `5C495F4FA900F99A1B90C613E818C61249B58A2D239C60F1A2C09BFD956A869F`。页面仅服务 R3 人耳诊断，反馈为空前不得推动 Stage S 或自动调参。
