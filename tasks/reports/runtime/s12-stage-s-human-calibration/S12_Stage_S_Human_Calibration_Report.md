# S12 Stage S 反馈驱动调音报告

状态：`R2_AB_PACKAGE_READY` / `WAITING_FOR_JOVI_HUMAN_FEEDBACK`

Stage Q 已有三条可审计 CC/CC0 R2 参考（Ferrari 458、Hellcat、Supra），并新增 RX-7sim 作者录音的五条 R2 指针；Stage R 已完成有限数字域比较。本轮已生成仓库外的中文 A/B 包：

`E:\\Claude_allow\\Download\\s12-stage-s-human-ab-r2-20260822`

其 `study_manifest.json` SHA-256 为 `9471784e875c98beb2e2ea91081f1ffa87f851ff461bd8e405d414d3447411e6`。包内只有响度匹配试听副本；原始分析 WAV 仍由 Stage Q 外部路径和 SHA 绑定，试听副本不能用于指标计算。另有一个单案 RX-7sim R2 中文包：`E:\\Claude_allow\\Download\\s12-rx7sim-human-ab-zh-20260823\\package`，`study_manifest.json` SHA-256 为 `68D525669E7789AF2A3570BE90E01FCD6AB571DEA0EA4866ACB2AE7DDB2FC428`；仅 `exhaust/revLong01` `full_pull` 有语义匹配候选，其余四条不进入 A/B。

Jovi 需要按 README_中文.md 播放 A/B，并在 `feedback_template.csv` 中绑定听者、设备、系统音量、输出端点、系统音效、case ID、参考 SHA、候选 SHA 和全部中文评分维度。空模板不是反馈，任何 fixture 结果也不算真实听审。

一次只允许修改一个车型、一个场景问题和一个参数组；自动指标改善且人耳不退步后，才能进入下一轮。所有调音都必须在独立 sound-fix 分支进行，当前分支不修改车型 source。

中文评分维度已写入 `stage_s_chinese_listening_contract.json`；本轮 A/B 包的可见文案为中文，不依赖英文浏览器页面。一次只允许修改一个车型、一个场景问题和一个参数组；自动指标改善且人耳不退步后，才能进入下一轮。所有调音都必须在独立 sound-fix 分支进行，当前分支不修改车型 source。

中文页面实测（2026-08-22）：在仓库外官方 webMUSHRA checkout 应用 `webmushra_zh_cn_nls.js`（SHA-256 `7E3B64C48A971E436BD1561234F17B2445D942F37A731FDA6B30AF6C04102021`），并使用 `s12-zh-probe.yaml`（SHA-256 `1E69987E46095106602387813A03B9DFA5936E8D2364C0CBE5F3D4B53DFFF9B1`）启动本地静态页面。浏览器快照显示“播放音量校准、播放、暂停、下一页”等中文控件，音频页成功加载；截图在外部 `E:\Claude_allow\Download\s12-stage-n-zh-probe-confirmed-20260822.png`（SHA-256 `338443A7F683CD9809D313F95405C480D9AC646B540AC8D446C25B9E7E9DC75B`）。这只是 UI/音频加载验证，不是 Jovi 听审结果，`feedback_rows` 仍为 0。
