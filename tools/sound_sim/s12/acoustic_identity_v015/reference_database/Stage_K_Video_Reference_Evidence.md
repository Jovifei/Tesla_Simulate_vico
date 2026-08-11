# Stage K 视频参考证据

## 证据边界

本文件记录 Stage K 执行前可访问的页面信息和研究用途，不把社交媒体页面当作 OEM 测量数据。页面可能受地区、登录、浏览器静音、压缩和自动增益影响；如果没有可审计的原始音轨，音频结论必须写 `NOT_AVAILABLE`。不得使用这些页面拟合绝对 LUFS、RMS、声压级或速度-响度曲线。

所有由页面得到的相对观察只能标记：

```text
R2/social-media-compressed
microphone/AGC dependent
not absolute loudness evidence
synthetic / uncalibrated / not OEM reproduction
```

## 页面记录

| 主题 | 页面 | 页面可访问性 | 可审计音轨 | 用途 |
|---|---|---|---|---|
| Hellcat SRT / 双螺杆听感 | [Douyin video 7442878447719943460](https://www.douyin.com/video/7442878447719943460) | 页面/标题可访问；播放受浏览器静音或平台限制时需以 `NOT_AVAILABLE` 记录 | `NOT_AVAILABLE`，除非执行阶段取得合法、可复核的音频文件 | 只用于“排气低频主体 + 随状态出现的增压器啸叫”定性方向 |
| RX-7 / GT-R 声浪原理讨论 | [Douyin video 7512312931426585890](https://www.douyin.com/video/7512312931426585890) | 页面/标题可访问；音轨不应假定可测 | `NOT_AVAILABLE` | 只用于转子/涡轮时间结构的定性研究，不用于数值拟合 |

## Hellcat 建模边界

官方资料支持把 Hellcat 作为双螺杆增压器、电子旁通和 HEMI 排气主体的组合来建模；Stage K 可将 2.36:1 驱动比和约 14,600 rpm 作为公开结构事实。转子齿数、精确啮合/BPF、壳体模态和麦克风传递仍未知，必须标记 `C/synthetic`，不能写成 OEM measured。

Stage K 的可听目标是：怠速以低频排气和机械底噪为主体；巡航保留轻微连续 whine；加速时 whine 随负荷/增压和转速连续建立；换挡短时下陷后恢复；收油时仅在存在 boost 历史且节气门关闭时产生旁通释放。不得用固定正弦、白噪声或全局 gain 伪造“滋滋哟”。

## RX-7 / GT-R 研究边界

第二个页面仅能支持“不同发动机的身份来自事件拓扑、阶次占用和时间结构，而不只是 EQ”这一工程假设。Stage K 不把其标题、评论或压缩音频当作转子阶次、涡轮齿数、BOV 时间或绝对频谱的测量证据。GT-R 继续使用并行双涡轮状态假设；任何转子/涡轮参数仍为 `C/synthetic/candidate_assumption`。

## 执行时的复核要求

1. 不下载新参考媒体；若合法获得临时音频，只放在 `E:\Claude_allow\Download\s12-stage-k-reference\`。
2. 记录文件 SHA、采样率、来源、压缩/AGC 风险和可用场景；原始媒体不得进入 Git、Obsidian 或 review ZIP。
3. 只提取相对频带、谱峰轨迹、调制和瞬态摘要，并在报告中单独列出 `NOT_AVAILABLE` 项。
4. Jovi 的具名反馈优先用于听感目标；在线资料只约束物理方向和证据等级。
