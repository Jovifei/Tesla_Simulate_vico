# 六车型真实声浪对齐：阶段性执行计划

日期：2026-10-27（Asia/Shanghai）
状态：`AUTHORIZED_RESEARCH_STAGE`；当前只执行真实录音分析与文档/账本同步，不改默认声库。

## 总目标

让 Hellcat、Ferrari 458、LFA、GT-R R35、C63 W204、Supra JZA80 的声音在启动、怠速、加速、收油、换挡和持续运行中尽可能接近对应真实车辆。工程测试通过、数字安全、设备、道路和人耳验收分开；没有证据就保持 `UNKNOWN` 或 `INSUFFICIENT_EVIDENCE`。

## 阶段 0：公开真实录音研究池（当前完成）

- 来源：Wikimedia Commons 原始 OGG。
- 文件：Honda F20C、BMW M57、Ferrari 250 GTO、Volvo 850 T5、Triumph I6。
- 证据：`E:\Claude_allow\Download\vico-real-engine-source-pool-20261027\manifest.json`、`RESEARCH_SCOPE.md`。
- 目的：验证连续性、重采样、声道、粒化、读头、谱/包络/调制分析。
- 结果：真实录音已取得；RPM/load/gear/phase/mic 全部 `UNKNOWN`；不得进入产品声库。

## 阶段 1：真实素材只读分析

输入每个源文件和固定 SHA。输出：格式、RMS/peak、1 s/100 ms 能量包络、谱质心/带宽、0.5–10 Hz 调制、自相关候选周期、静音/削波/多通道一致性。输出绑定源 SHA，禁止归一化和“听起来更好”的后处理。

门槛：分析可复现、源 SHA 一致；周期候选不能解释为 RPM 或 720° phase。

## 阶段 2：六车型来源收敛

每车型建立独立 source registry：精确年款/发动机/排气改装、来源 URL、作者、许可证、原始文件 SHA、采样格式、麦位/AGC/距离、工况标签。候选来源分为：

- `R1`：可进入状态对齐实验；有原始媒体、同步 RPM/load/gear、共同时间轴和独立 holdout。
- `R2`：许可清楚、车型身份和工况可听，但同步状态不完整；仅作有限听感/特征研究。
- `R3`：身份、许可、状态或配置不完整；只作参考，不进入产品训练/标定。

当前公开池全部是 `R2/R3`，不是六车型合格声图。

## 阶段 3：状态对齐数据合同

每个合格 take 必须同时保存 PCM 与状态 CSV：`rpm`、`throttle`、`load`（MAP/扭矩/估算来源分开）、`gear`、`clutch`、`coolant/oil temperature`、`boost/bypass`、`mic position`、`720-degree phase`、时间戳和校准/同步方法。缺字段不得用 GPS 加速度或素材坐标补写。

必须保留 train/validation/holdout 三个来源分组，不能把同一 take 切片后随机分组冒充独立验证。

## 阶段 4：三路离线对照

固定 60 秒不中途 reset：`15 s idle → 15 s acceleration → 15 s high-rpm → 10 s coast → 5 s idle`。比较：

1. `RECORDED_PRIMARY`：真实多区域读头，状态驱动；
2. `LEGACY_BANK`：现有 RPM×load bank；
3. `GENERIC_PHYSICS`：engine-sim 或其他明确 generic 的连续物理输出。

保留源 PCM、控制轨迹、pre-DSP/final PCM、SHA、CPU/内存、峰值/削波、10/20 ms 能量、调制谱、阶次图和过渡跳变。没有合格合同就只写 `INSUFFICIENT_EVIDENCE` 收据。

## 阶段 5：车型专项声音建模

- Hellcat：cross-plane V8、低频压力、机械增压器/旁通、排气与机械层；不得把普通 V8 改名。
- Ferrari 458：flat-plane V8、高转阶次、金属感和排气开阀状态；不能用 Ferrari 250 GTO 代替。
- LFA：V10 高转和进排气共鸣；需要独立 LFA 来源。
- GT-R R35：VR38 双涡轮、BOV/排气/负载；区分 Nismo、Tomei 和原厂配置。
- C63 W204：M156 自然吸气 V8、排气和收油事件；已有素材仍需重新核对来源和状态。
- Supra JZA80：2JZ-GTE 涡轮、压气机/泄压阀和排气；区分原厂与改装。

## 阶段 6：软件、设备、人耳分层验收

- 软件：合同、渲染确定性、生命周期、跨块连续性和安全范围。
- 声学：holdout 上的频谱/阶次/包络/调制/事件指标。
- 设备：Android AudioTrack/网页实际输出回录，记录设备、音量和路由。
- 人耳：Jovi 盲听 A/B/X，分别评分车型身份、怠速、加速、收油、低频、机械/增压器、周期感和疲劳感。

任何一层失败都不能由其他层“洗过”；产品接入必须在软件、声学、设备和人耳门分别有证据。

## 当前下一步

1. 完成公开池的只读特征分析并生成 JSON/Markdown 报告；
2. 为六车型建立 source registry 和缺口表；
3. 选择一个有 R1 状态数据的车型先闭环，优先 Hellcat；若没有 R1，则先用公开池验证算法，不宣称车型对齐；
4. 只有阶段 1–4 通过后，才讨论任何产品源码接入或默认声库替换。

## 明确停止条件

- 许可或原始文件身份不清；
- RPM/load/gear/phase/holdout 缺失；
- 候选只改善数字周期指标但人耳不接受；
- 新算法只能靠增益、随机种子或强行 EQ 才通过；
- 真实录音与合成模型来源混淆。

这些情况都保留失败证据并回退，不升级为“已对齐”。
