# Stage J 三车型声学目标矩阵

状态：`C/synthetic` 建模目标；参考录音只提供 `B/R2 relative features`，受麦克风、AGC、录音位置和后处理影响。本文不提供 OEM measured 数值，也不是 OEM 复刻声明。

## 公开架构事实

| 车型 | 可用于建模的公开架构事实 | 本阶段声学方向 |
|---|---|---|
| Mercedes-AMG C63 W204 | M156 自然吸气 cross-plane V8，独立事件与排气脉冲为主要身份线索 | lumpy cross-plane cadence、barked mid-low exhaust、机械纹理；不加涡轮啸叫 |
| Nissan GT-R R35 | Nissan Heritage 资料将 VR38DETT 记为 3.8 L V6 twin-turbo，并记录后置双离合变速器 | even-fire V6 event train、双 turbo spool/whistle、boost onset、收油 wastegate/BOV |
| Lexus LFA | Lexus Media 资料记为高转 4.8 L naturally aspirated V10、后置六速 sequential automatic | 5/10/15 moving orders、高转进气、事件化 metallic texture；不使用固定中心 tone |

官方参考：

- Nissan GT-R Heritage：<https://www.nissan-global.com/EN/HERITAGE_COLLECTION/418_nissan_gt-r.html>
- Lexus LFA Media：<https://media.lexus.co.uk/lexus-lfa/>

## 现有 target JSON 数值真值

Stage J 使用 `reference_database/{vehicle}_reference_targets.json` 的 `stock_median`。四频段顺序固定为 `20–250 Hz / 250–1000 Hz / 1–4 kHz / 4–12 kHz`，比较域为最终 PCM；不比较参考录音的绝对 LUFS/RMS。

| 车型 | idle bands | acceleration bands | afterfire bands | 建模重点 |
|---|---|---|---|---|
| C63 W204 | `[0.8607, 0.1080, 0.0276, 0.0026]` | `[0.3137, 0.5416, 0.1275, 0.0165]` | `[0.2671, 0.5634, 0.1686, 0.0003]` | 中低排气与事件化 bark，不靠全局增益 |
| GT-R R35 | `[0.8690, 0.0934, 0.0352, 0.0021]` | `[0.1796, 0.6646, 0.1498, 0.0057]` | `[0.4089, 0.4586, 0.1140, 0.0060]` | turbo 动态与中频 racy texture，低频不过重 |
| LFA | `[0.7175, 0.2786, 0.0039, 0.00002]` | `[0.0011, 0.9745, 0.0235, 0.0010]` | `[0.0034, 0.8023, 0.1308, 0.0635]` | 低频克制、moving order 高转身份、收油尾部 |

## 已知冲突与处理

- 旧 LFA research brief 中的 idle centroid 描述与 target JSON 不一致；Stage J 以 target JSON 为数值真值，旧描述仅保留为历史研究线索，不作为调参依据。
- 旧 GT-R 资料中出现未经当前官方来源确认的 bank-angle 数字；Stage J 不编码该数字，仅使用官方确认的 V6/twin-turbo/DCT 架构和 C 级合成相位关系。

## 资格边界

参考距离达到 30% 仍是自动门禁；本轮即使生成可试听 WAV，也只能处于 `PARTIAL / AUTOMATED_GATE_FAIL` 或 `WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW`。输出继续标记：`synthetic / uncalibrated / not OEM reproduction`。
