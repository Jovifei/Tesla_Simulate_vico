# S12 真实声浪闭环总报告

状态：`R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED / WAITING_FOR_JOVI_HUMAN_FEEDBACK`

> 本报告是当前 HEAD 的等待态审计，不是“本地声浪与真实声浪比较、反馈和调优闭环已完成”的声明。

下载恢复补充：在仓库外独立目录 `retry_tools_20260822_v2` 关闭本机代理并启用 Node.js EJS 后，24 条最终视频均通过严格全流解码；两条短头部文件使用 `134 + 140-9/140-8` 分流回退。严格清单 SHA-256 为 `E029D78938C6B21DB7FD612E8693362A25BED122A0DF73602F0E87CB92F7208E`，恢复收据 SHA-256 为 `A5D49E871505A7FAEF6EBEF316191356F06976AB18E8A2830B4BE82355914DF4`。这只把外部媒体完整性从初始 `1/24` 恢复为 `24/24 COMPLETE_DECODABLE`，不改变其 YouTube 派生、未授权/未同步的 `R3` 资格。

当前环境对照探针：使用不读取账号 Cookie 的 Node.js EJS，对 `cKx-cb0fzeo` 分别走默认代理和 `--proxy ""` 的 `bestaudio/best` 请求，挑战解析成功但签名媒体请求两次均为 `HTTP 403`，没有生成新的完整媒体。探针收据已写入 Stage Q，旧的 24/24 外部解码收据保持不变。

本轮针对用户反馈再次做了独立 `yt-dlp` 验证：默认 `android_vr` 对 `XWEjZHFQ5lc` 复现 `HTTP 403`；切到 `web_embedded + Node.js EJS` 后，渐进式 `format 18` 虽显示下载完成，但严格 `ffmpeg -xerror` 判定为 `partial file`，未被采纳。改用 `134 + 140-9/140-8` 分流后，`XWEjZHFQ5lc` 与 `GQ0972wohFs` 均通过完整流解码。外部收据 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_yt_dlp_current_20260822\yt_dlp_node_web_embedded_retry_receipt_v2.json`，SHA-256 `52996AB90C3145B292E0E2964560B70A2A2F46443283C0C79ED90458A94E5BF8`。这只验证下载/解码回退，不提升 YouTube 素材的 R1/R2 资格。

2026-08-23 批量独立复试：在 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1` 中，默认客户端对 24 条原始 URL 有 `22/24 HTTP 403`；使用 `Node.js + EJS + android` 回退后，最终 `24/24` 媒体和音频均通过 `ffprobe`、`ffmpeg -xerror` 全流/音频解码，并生成 `24/24` 外部 WAV。合并回执 SHA-256 为 `0DAB94BFB99A4AEDC4855929A39EA211D958A4EAA6C3B9F3ADCE98F065363EEE`，严格解码回执 SHA-256 为 `C120BFE16B0CEF5B80C68FC47E4FB2BB6198CE94BAE8EE1BF9243B04A965C782`。这只说明下载工具链已能恢复完整可解码媒体；YouTube 派生音频仍保持 `R3`，不进入 R1/R2、MATLAB 阶次或自动调参。

2026-08-23 独立单条复测：对原先默认链路 403 的 `hellcat_01 / cKx-cb0fzeo`，直接调用 `yt-dlp + Node.js EJS + android` 成功取得 3,749,435 字节 MP4；`ffprobe` 识别 H.264/AAC、105.813 s，`ffmpeg -xerror` 全流解码通过，并无增益提取 48 kHz 双声道 PCM WAV（20,316,238 字节），WAV 再次完整解码通过。外部探针收据 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v2_probe\download_receipt_hellcat_01.json` SHA-256 `7BF6CC011DBDCE68FA26A8F68F2EF10B4513AC7535269FFA42ED9802603317DE`；该复测只证明 Android 客户端回退可用，仍是 YouTube 派生 `R3`，不提升为 R1/R2。

2026-08-23 403 重试补充：对 `ferrari_01 / pN3uGrx0sS4`，`web_safari + bestaudio` 仅返回图片格式，`android + bestaudio` 在 SABR 下无可用音频格式；改用 `android + best` 成功取得 12,177,206 字节 H.264/AAC、143.058 s 文件，`ffmpeg -xerror` 全流解码通过，媒体 SHA-256 为 `6576BFCEC095E4FD27DD437FA5D32D05319995599F6319A9695545AF62040B40`。外部收据 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v2\download_retry_receipt_ferrari_01_v1.json`；这验证了可用回退工具链，但不改变 YouTube 派生 `R3` 资格。

2026-08-23 独立单条复测补充：对 `c63_03 / vIbiUABVZO4`，默认 `yt-dlp` 客户端复现 `HTTP 403`；切换 `youtube:player_client=android`、`format=best` 后取得 10,340,349 字节 H.264/AAC MP4，`ffprobe`、`ffmpeg -xerror` 全流解码和无增益 PCM WAV（21,422,158 字节）再次完整通过。外部回执 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v4_probe\probe_receipt_c63_03_v2.json`，SHA-256 `C1E39775BB97B2A833DA915B67F0481CA3702F85B6F476750CACF887EF748DE5`；这只确认 Android 回退链路，仍为 YouTube 派生 `R3_DIAGNOSTIC_ONLY`，不进入 R1/R2。

2026-08-23 导入探针去重审计：外部目录 `E:\Claude_allow\Download\s12-rx7sim-q-import-probe-20260823-v2` 不含原始音频；其 `reference_database_v2\reference_manifest.json` SHA-256 `D317D2E10193D12B6607B59A714ABF4A55DCEE78A94C30ED96070F6D2DBC3E46` 与 canonical 完全相同，探针内 50/50 个元数据/派生文件与 canonical 逐文件 SHA 相同，23 条外部路径均指向既有文件。没有新增 R1、同步状态或人耳反馈，因此未合并、未升级门禁。

2026-08-23 采购候选复核：重新核对 Ferrari 458、Hellcat、RX-7 的商业录音库页面/曲目单。三者都声称有 steady-RPM、ramps、gearshift 或多麦位同步 take，但没有提供可验收的数值 RPM/Load/Throttle/Gear 文件；尚未购买或取得书面许可，因此仍是 `PROCUREMENT_CANDIDATE_NOT_R1`。机器可读清单为 `tasks/reports/runtime/s12-stage-q-real-reference/procurement_candidate_revalidation_20260823.json`；不下载版权原始音频，不改变 `R1=0`。

2026-08-23 R1 合同修正：资格门此前把麦位硬编码为 `EXTERIOR_REAR`、把 AGC 硬编码为 `DOCUMENTED_NO_AGC`，与规范“已记录即可”的要求不一致。现改为接受任意明确可审计的麦位和 AGC/后处理说明，同时继续拒绝 `UNKNOWN`/空值；新增车内麦位、AGC 开启但有电平记录和未知值拒绝测试。该修正没有制造任何 R1 记录，当前仍为 `R1=0`。

2026-08-23 合法 R2 参考复核：重新从 Wikimedia Commons 保存 Ferrari 458 Italia 与 Dodge Challenger SRT Hellcat 两条明确许可音频到 `E:\Claude_allow\Download\s12-commons-r2-audit-20260823`，原始 OGG 与无增益 PCM WAV 的 SHA、来源和许可已写入外部 `revalidation_manifest_20260823.json`（SHA-256 `16BB249DEDF7760AB02BB995B9F46953BCCDC4F62340B576AF7D177DC233340F`）。现有 Stage R R2 Comparator 复跑成功：Ferrari 频谱对数残差 `0.574775`、响度差 `+2.7001 dB`；Hellcat `0.503287`、`+0.4530 dB`。两案阶次均为 `not_evaluated_without_rpm_trace`，人耳反馈为空，自动调参仍关闭；R1 仍为 `0`。

同一批最新 WAV 随后重新进入现有 R3 诊断链，生成 `24` 条特征、`72` 个低置信场景切片、`24` 条 Comparator 诊断、`24` 条中文 A/B 试次和参数诊断；外部分析收据 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\r3_analysis_receipt_20260823.json` SHA-256 为 `18bea83f660d773b81b138a6982f01012a64cac9fcef8605c0d660dab3bdefc0`。该包仍是 `COMPLETE_DIAGNOSTIC_ONLY_R3 / R1=0 / R2=0 / R3=24`，A/B 反馈为空，未启动 MATLAB 阶次、自动调参或 Profile Candidate。

为便于 Jovi 进行中文试听，另生成三锚点 A/B 外部包 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1\README_中文.md`：Ferrari 458、Hellcat、RX-7 FD 各 3 个公开来源对本地 synthetic 候选的 5 秒片段，共 9 个试次/18 个文件。manifest SHA-256 为 `dc5bb05c24b338485f567b4e4107620aff76f8d210204b6cccae61eb4c4f6052`，receipt SHA-256 为 `fbcb0ccc701b4edfb20b371a13478ad8e2ac2172e3203bffb78e6ec15ff6ba6e`；状态为 `WAITING_FOR_JOVI_HUMAN_FEEDBACK`，反馈为空，不能推动 Stage S 调音。

为避免再次出现英文或难以理解的试听界面，已在同一外部包增加可直接双击的中文离线页面 `E:\Claude_allow\Download\s12-ytdlp-retry-20260823-v1\anchor_ab_zh_v1\index.html`。页面固定绑定 9 个试次、18 个片段 SHA-256，提供中文评分、备注、进度、草稿/完整状态和 JSON 下载；页面 SHA-256 为 `5C495F4FA900F99A1B90C613E818C61249B58A2D239C60F1A2C09BFD956A869F`。页面仅导出反馈，不自动调参、不更新 Profile，仍保持 `R3` 诊断边界。

本轮随后用仓库 URL 入口本身复现同一故障：`XWEjZHFQ5lc` 第 1 次默认客户端为 403、第 2 次 Android 残片被严格解码门拒绝，第 3 次 `Node.js + web_embedded` 自动选中完整 MKV（344.441 s，SHA-256 `A2D0C7AB0A048A302E468B72668D0E492F606FB57F2257F62AA9FFBC92AFCD06`）；`GQ0972wohFs` 同样在第 3 次选中完整 WebM（336.321 s，SHA-256 `3475C4E7CB139E31D84F12C8C7A26329E0994299EC1A2821207E1406C4716C0A`）。外部复试收据 `E:\Claude_allow\Download\s12-url-intake-repro-20260822\url_intake_repro_receipt_v2.json`，SHA-256 `4F6CF1E7D81ECDB5CF47C9E363D40B6D0FF35D8ECC783AC93F00FF64C58E19B6`；原始媒体、残片和日志均留在仓库外。这证明入口能识别并拒绝“有时长但不完整”的短头部文件，但不改变 YouTube 派生 R3、未授权/未同步边界。

最终视频绑定的 R3 重算也已完成：从上述 24 条最终视频重新抽取无增益 PCM WAV，并用 intake manifest SHA `2432218DFEF56CAE8A4FA4B475A1A7AEBB43BAB4BA9EBEC7459A4346611881CF` 绑定到分析收据 `final_video_analysis_receipt_v1.json`（SHA-256 `62492F2CABE3BBDF6606E7E1C16CAC4FE1703F784E4185D25D8C5D28841C1175`）。中文差异报告位于仓库外 `analysis_final_video_r3_v1/S12_Stage_R_Final_Video_R3_Difference_Report_20260822.md`，SHA-256 `60EAC35526ECF922EC50605EDF320F2A2BFCCD2CD06DA6BC38BF41054FD8F71D`。该结果是 24/24、8 车各 3 条的最新 R3 数字域诊断，不是 R1/R2 资格，也没有启动 MATLAB 阶次、自动调参或 Profile Candidate。

R1 门禁加固（2026-08-22）：资格函数现在额外要求非视频派生的原始 PCM/FLAC 收据、来源指针与授权证据、车型/工况、采样率和明确的原厂排气确认；即使视频容器声明 PCM 或手工传入 raw receipt，YouTube/视频抽取来源仍保持 R2/R3。针对性 URL/Stage-Q/Stage-R 测试覆盖该拒绝路径，当前真实资料重新审计仍为锚点 `R1=0`。

原始录音入口补充（2026-08-23）：新增 `raw_audio_intake.py`，将合法原始 WAV/FLAC、外部路径别名、音频/状态 SHA-256、provenance、精确车型/原厂排气、麦位/AGC 和同步状态合同 fail-closed 登记；原始版权媒体仍只在 `E:\Claude_allow\Download` 等批准外部目录，manifest/report 才可进入仓库。Stage R 支持带时间戳的低速率 RPM/Load/Throttle/Gear/shift 遥测，在窗口覆盖后插值/离散映射到音频采样网格，拒绝无时间戳低速率数据和外推。该实现验证了 R1 输入准备路径，但没有制造真实 R1 记录：当前 `R1=0`、MATLAB/MoSQITo 收据 `0`、Jovi 人耳反馈 `0`、调音轮次 `0`。

Stage Q 合并补充（2026-08-23）：`real_reference.cli --raw-reference-manifest` 可把外部入库记录接入 canonical `reference_database_v2`，生成 evidence matrix、场景窗口、RPM/state bindings、provenance 和派生特征指针，并执行 JSON Schema 校验；该合并只写元数据，不复制原始版权音频。

Stage Q 授权 R2 合并补充：`--authorized-reference-manifest` 已把 Ferrari 458、Hellcat、Supra 各一条，以及 RX-7sim 同一作者的五条已审计授权记录接入 canonical Q；入口重新核对外部文件 SHA-256，当前 canonical 为 23 条记录（R1=0、R2=8、R3=15）。R2 仍只允许频谱/响度/心理声学/瞬态主观相对比较，不开放阶次硬门或自动调参。

2026-08-23 MATLAB R2 专业指标复核：用仓库现有 `s12_psychoacoustic_analysis` 和 MATLAB R2026a Audio Toolbox 对 Ferrari 458、Hellcat、RX-7 FD 各一组 R2 参考/本地 synthetic 代理完成 5 秒共同窗口的响度、尖锐度、粗糙度、波动度、音调/突出度相对测量。外部收据 `E:\Claude_allow\Download\s12-r2-matlab-psychoacoustic-audit-20260823-v3\matlab_r2_psychoacoustic_audit.json`，SHA-256 `523C8264F6A83EE23640A166FDFA15E76771880EFBFE914A4FA79C161AABB70A`；状态 `R2_LIMITED_COMPARISON_COMPLETE`。该证据仍明确 `R1=0`、阶次未评估、自动调参关闭、Jovi 反馈为 0。

公开来源补充审计：新增一条 Freesound CC0 Ferrari 458 Italia GT3 页面/预览并完成 SHA 与容器核验；由于文件混合 17 辆 GT 赛车且没有 Ferrari 段落时间绑定或同步状态，登记为 `R2_CANDIDATE_NOT_COMPARISON_READY`，没有进入 R2 指标或调音，R1 仍为 0。

公开同步数据复核：F1Audio 有同步 RPM/挡位/油门但文件受限且车辆不是锚点；Visual-Acoustic 数据集有同步状态但车辆是 Lincoln MKS；HL-CEAD 有固定 RPM 录音但车型和负载/换挡证据不匹配。Ferrari 458、Hellcat、RX-7 的专业库仍需购买/书面许可与数值状态验收。筛选记录位于 `tasks/reports/runtime/s12-stage-q-real-reference/public_sync_reference_search_audit_20260822.json`，SHA-256 `FB0660B24699791BB4613A4E45C5A492471C1DDF515638AA5BDBB1ADEB796B43`；当前 `R1=0`，没有启动 MATLAB 阶次或自动调参。

中文听审入口实测：官方 webMUSHRA 外部 checkout 已应用中文 NLS 覆盖，并以 `language: zh` 的最小配置通过本地浏览器快照验证中文按钮和音频加载；截图与补丁均留在 `E:\Claude_allow\Download`，不进入 Git。该验证不产生 Jovi 听审行，真实反馈仍为 0。

2026-08-23 中文 R2 A/B 交接补充：针对唯一有语义匹配本地候选的 RX-7sim `exhaust/revLong01` `full_pull`，新增仓库外中文离线页面 `E:\Claude_allow\Download\s12-rx7sim-human-ab-zh-20260823\package\index.html`。研究清单 SHA-256 为 `68D525669E7789AF2A3570BE90E01FCD6AB571DEA0EA4866ACB2AE7DDB2FC428`，页面 SHA-256 为 `586322EE697AACDD0ED429A36DCB4531A1BDA01E4D9598C84A6AC590A25EF6BB`，中文说明 SHA-256 为 `AF2C91F1B3E5ED1B02A02F8FF9B44E8AB149C24C93ECB3178365E65B284C1EBA`；仅 1 个 R2 案例，绑定 `test_id`、参考/候选源与试听副本 SHA，状态仍为 `WAITING_FOR_JOVI_HUMAN_FEEDBACK`。其它 4 条 RX-7sim 录音因无语义匹配候选未进入 A/B；不自动调音、不升级 R1。

2026-08-23 中文 R2 A/B 可重建包修订：修复页面脚本转义并以全新外部目录 `E:\Claude_allow\Download\s12-rx7sim-human-ab-zh-20260823-v3\package` 重建。研究清单 SHA-256 为 `2BF26029B68DCAC80C7A9896DC570C18BC3D9F52B5F07C500F38C9A865CE501C`，页面 SHA-256 为 `65B43B200E4C4A2771CFF8E35A375A3DC62EFFC9B49029CA043F3A004D192A7D`；页面通过 Node 语法检查，且新增播放设备、系统音量、输出端点、系统音效字段。仓库内收据见 `tasks/reports/runtime/s12-stage-s-human-calibration/rx7sim-20260823-v3/`，状态仍为 `WAITING_FOR_JOVI_HUMAN_FEEDBACK`，反馈行数为 `0`。

## 阶段状态

| 阶段 | 当前状态 | 已完成内容 | 未完成内容 |
| --- | --- | --- | --- |
| Q 真实参考 | `REAL_REFERENCE_DATASET_LIMITED` | 原有目录审计加 3 条明确 CC/CC0 许可的 R2 参考，以及 RX-7sim 同一作者的 5 条 R2 资产；另审计 1 条 CC0 非目标 Pontiac G8 测功机视频作为 R3 流程样本；记录 3 条商业 R1 采购候选 | R1 元数据和同步 RPM/state；商业候选尚未购买/授权和验收 |
| R 差异基线 | `R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED` | Ferrari 458、Hellcat、Supra 已完成 R2 相对比较；RX-7 FD 的 `full_pull` 也完成一条语义匹配的 R2 诊断比较；R1 SHA-bound MATLAB/MoSQITo 输入准备仍在 | R1 阶次资格、自动调参、真实人耳反馈 |
| S 反馈调音 | `R2_R3_AB_PACKAGE_READY / WAITING_FOR_JOVI_HUMAN_FEEDBACK` | 已生成仓库外中文离线 A/B 包和双击页面，3 个锚点各 3 个试次，另有 RX-7sim R2 单案；v3 页面绑定播放环境字段和全部片段 SHA | 没有真实 Jovi 听审和调音轮次 |
| T Profile Candidate | `BLOCKED_PROFILE_CANDIDATE_NOT_READY` | Profile Candidate 阻断门和交接模板 | 没有候选参数包或产品交接 |

补充证据：原始 24 条 YouTube URL 已重新完成直接无代理音频下载与现有 Comparator 的 R3 诊断（8 车各 3 条）。该补充不改变 R2/R1 门禁；机器收据位于外部 `E:\Claude_allow\Download\s12-real-vehicle-source-library-v1-20260822\retry_direct_20260822_v1\analysis_r3_direct_v1\direct_analysis_receipt_v1.json`，SHA-256 为 `A007C99EAC91D3A875EF3EDEF4E2A6433EBF6AC18BF1F724D9DD89D46F778876`。

同步录音采购线索也已完成只读页面/曲目单核验：Ferrari 458、Hellcat、RX-7 1990 三项均为 `PROCUREMENT_CANDIDATE_NOT_R1`，没有购买、版权原始音频或数值 RPM/state 收据。外部候选审计 JSON 为 `E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\candidate_source_audit_v1.json`，SHA-256 为 `082bc43c24ba1aa84f9450fe826244376925bb58c040999ea032396077f8c636`；许可页还要求购买后许可，并限制未同步素材复制和 AI 训练/开发，使用前需完成范围确认。

## 八车型与工况

当前八车型全部没有 R1 资格；已有文件只能作为未授权/未对齐候选，不能进入自动调参。

| 车型 | 已登记候选 | R1 | 可资格指标 |
| --- | ---: | ---: | --- |
| 法拉利 458 | 2 | 0 | R2 频谱/响度/心理声学；无阶次 |
| 道奇 Hellcat | 5 | 0 | R2 频谱/响度/心理声学；无阶次 |
| 马自达 RX-7 FD | 6 | 0 | R2 频谱/响度/心理声学；仍无阶次/R1 |
| 兰博基尼 Aventador LP700 | 1 | 0 | 无；待授权和状态绑定 |
| 奔驰 C63 W204 | 3 | 0 | 无；待授权和状态绑定 |
| 日产 GT-R R35 | 3 | 0 | 无；待授权和状态绑定 |
| 雷克萨斯 LFA | 1 | 0 | 无；待授权和状态绑定 |
| 丰田 Supra JZA80 | 2 | 0 | R2 频谱/响度/心理声学；无阶次，代际未核实 |

已识别的工况提示包括 idle、steady/acceleration、full_pull、shift、lift/afterfire 等；当前窗口均为文件名或旧注释推断，未达到场景资格。

## 指标与人耳边界

- 阶次 / Order-RPM：`NOT_QUALIFIED`，所有新增公开素材都没有同步 RPM。
- 频谱、响度、心理声学：Ferrari 458、Hellcat、Supra 和 RX-7 FD `full_pull` 均只有 R2 相对数字域结果；不输出真实性百分比，不复用旧报告数字。RX-7sim 其余 4 条没有语义匹配候选，未比较。
- 瞬态：没有同步 Gear/shift/state；不进入自动门。
- 人耳：真实 Jovi 反馈行数为 0；Stage P fixture 不算人耳反馈。R2 A/B 包路径为 `E:\Claude_allow\Download\s12-stage-s-human-ab-r2-20260822`，study manifest SHA 为 `9471784e875c98beb2e2ea91081f1ffa87f851ff461bd8e405d414d3447411e6`。
- 追加 R2 A/B 包：RX-7sim `full_pull` 单案的中文包路径为 `E:\Claude_allow\Download\s12-rx7sim-human-ab-zh-20260823\package`，study manifest SHA 为 `68D525669E7789AF2A3570BE90E01FCD6AB571DEA0EA4866ACB2AE7DDB2FC428`，反馈行数仍为 `0`。
- 当前可重建中文包：RX-7sim `full_pull` 单案的中文包路径为 `E:\Claude_allow\Download\s12-rx7sim-human-ab-zh-20260823-v3\package`，study manifest SHA 为 `2BF26029B68DCAC80C7A9896DC570C18BC3D9F52B5F07C500F38C9A865CE501C`，反馈导入器会校验播放设备/音量/端点/系统音效与案例集合，反馈行数仍为 `0`。
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
- 历史提交链已推送到 `agent/s12-stage-q-real-reference-calibration`；本次交接以 `git rev-parse HEAD` 与 `git ls-remote` 的最终复核值为准，远端 SHA 必须与本地一致。
- working tree：提交后干净；本轮提交包含 R2 A/B SHA 大小写兼容、回归测试和中文交接收据，没有把外部试听/版权媒体写入 Git。
- push：是
- merge：否
- PR：否

## 本轮验证

- 最新完整 S12 Python 回归（当前 worktree）：`877 passed, 232 subtests passed in 1605.13s`；运行范围为 `tools/sound_sim/s12/tests` 与 `tools/sound_sim/s12/acoustic_identity_v015/tests`。
- 本轮 Stage Q/R/S 聚焦测试：`31 passed`；MATLAB R2 收据边界校验通过；Track-P pytest：`32 passed`；冻结守卫：`180 files / 2 symbols`。
- 本轮采购候选/guard 修订后聚焦回归：S12 Q/R/S/URL + Track-P guard 共 `69 passed`；独立 Track-P guard 重新通过 `180 files / 2 symbols`。新增 R2 MATLAB 审计入口已作为分析证据路径加入 Track-S allowlist，未触及 Track-P 物理模型。
- 当前 HEAD `10a78bc2` 的 S12 测试全集（`tools/sound_sim/s12/tests`：`394 passed, 114 subtests`；Track-P pytest：`32 passed`）重新执行：合计 `426 passed, 114 subtests`；核心回归用时 `147.48s`，Track-P 用时 `1.21s`。
- 本轮 Stage S/R 聚焦测试：`16 passed`；Track-P pytest：`32 passed`；冻结守卫：`180 files / 2 symbols`。
- 独立 Track-P 冻结守卫：`180` 个冻结文件、`2` 个冻结符号、工作树/索引均匹配；`git diff --check` 通过。
- R1 筛选 JSON、外部 YouTube 收据和当前 Git 远端 SHA 均已重新核验；由于锚点 `R1=0`，MATLAB 阶次执行、自动调参和 Profile Candidate 仍未启动。
- 2026-08-23 公开同步数据检索已固化到 `public_synchronized_source_screening_20260823.json`：Lincoln MKS 数据集虽有 RPM/油门/挡位时间戳但不是目标车型；HL-CEAD 仅有名义 RPM 文件夹且仓库页未声明许可证；Dodge 页面只是同步记录功能说明。三者均未下载或升级为 R1。

## 必须补齐的输入

1. 三个锚点的 R1 真实车辆原始录音及同步 RPM、Load/Throttle、Gear/shift；
2. 精确车型/配置/原厂状态、场景、麦克风位置和 AGC/后处理合同；
3. 真实 Jovi 中文听审结果及播放元数据；R2 结果不能替代 R1 或人耳反馈。

本轮 R2 结果：`tasks/reports/runtime/s12-stage-r-real-sound-difference/web-authorized-20260822/`；中文 A/B 包：`E:\Claude_allow\Download\s12-stage-s-human-ab-r2-20260822`；原始媒体和试听副本均存于仓库外，Git 只保存许可、路径、SHA-256 和派生合同。

所有产物继续声明：`synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。
