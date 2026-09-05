# S12 真实车辆声音采集、切分与标定方法论 (Audio Collection & Calibration Guide)

> **版本**：v2.0  
> **更新时间**：2026-09-05  

---

## 1. 声音素材收集规范

### 1.1 推荐渠道与素材选择
1. **马力机全负荷拉转（Dyno Pull）**：转速从低至高均匀受控攀升，适合提取纯净全油门（WOT）阶次声。
2. **高速公路 / 赛道第一视角（Onboard POV 4K）**：真实座舱与排气负载，包含完整的加减速、升降挡与回火过程。
3. **外部定点静态轰油（Stationary Revs & Idle）**：适合提取热态纯净怠速与轰油自由回落工况。

### 1.2 音频切分与标准化处理
使用 Python 脚本将长视频音频提取为 48000 Hz 16-bit PCM 立体声 WAV，切分为 10 个标准工况：
- 采样率恒定：`48000 Hz`
- 位深：`16-bit Signed Integer (PCM)`
- 声道：`Stereo (双声道)`
- 头尾平滑：施加 5ms 线性淡入淡出（Fade-in / Fade-out），防止切片处出现直流跳变爆音（Click/Pop）。

---

## 2. 评审看板部署与统一架构

所有车辆评审看板均采用 Base64 全量内嵌独立架构（Single-File Standalone HTML）：
- **零网络依赖**：脱离公网环境依然可以离线试听；
- **零跨域阻碍**：在任何现代浏览器中直接以 `file://` 或本地 HTTP 访问均可无缝播放；
- **同屏双轨对比**：每个卡片同时放置仿真输出与真车原声，实现无缝瞬时 A/B 盲测对比；
- **全车互联导航**：顶部导航栏支持在全部已标定车型之间一键切换。

| 车型名称 | 端口 | 本地访问链接 | 核心验证点 |
| :--- | :--- | :--- | :--- |
| **Dodge Challenger SRT Hellcat** | 8088 | [http://localhost:8088](http://localhost:8088) | 24/48 Hz 美式煮水声、机增啸叫平衡 |
| **Ferrari 458 Italia** | 8089 | [http://localhost:8089](http://localhost:8089) | 139 Hz 排气管驻波、9000转自吸尖啸 |
| **Lexus LFA** | 8090 | [http://localhost:8090](http://localhost:8090) | 5/10 阶次天籁之吼、雅马哈声学腔体共振 |
| **Nissan GT-R R35** | 8091 | [http://localhost:8091](http://localhost:8091) | V6 浑厚喉音、双涡轮起压与 BOV 泄压 |
