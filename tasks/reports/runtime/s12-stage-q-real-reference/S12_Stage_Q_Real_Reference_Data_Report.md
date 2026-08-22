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

本轮没有新增合法、车型明确且可绑定同步状态的三锚点原始包，Stage Q 仍保持 `REAL_REFERENCE_DATASET_LIMITED / WAITING_FOR_REAL_REFERENCE_DATA`。

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

边界：所有产物继续标记 `synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。
