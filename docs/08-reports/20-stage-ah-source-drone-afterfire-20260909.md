# Stage AH：固定频段轰鸣与回火的源层对照实验

## 基线与授权

起点是远端 main `078643e9e90cb5b05f82225cc8404bef25a3db84`，不是旧 AE、rich-workbench 实验分支或过期 worktree。PR #16 已合并。用户最新反馈为四车型约 80% 主观相似、仍有低频轰鸣和回火不真实；80% 不是计量指标或完美复刻证明。

本次新授权只改变可选源层。AG-R1 的 identity profile、IR 字节、事件时间表、现有 numerical_fixes、富交互模板、Track-P/PTR/Radiation 均保留。旧两包不重写。EngineAcoustics 无 `_source_policy` 时必须与固定 Git 078643 的旧实现逐 PCM 相等。

## 已确认的代码事实，不等同于已确认的耳边噪声根因

- `_synthesize_channel` 固定机械共振中心：Hellcat 95 Hz、Ferrari 135 Hz、LFA 380 Hz、GT-R 145 Hz。其额外 bandpass 支路增益恒为 0.35，可能把随机气流或燃烧成分变成固定频带的持续突出。
- `bass_body` 所有车型共用 0.50 主阶次 + 0.35 半阶次 + 0.15 二倍阶次；其油门为零时仍有 0.45 floor。它随 RPM 移动，不是固定频率振荡器。不要把合法低频发动机阶次都当成噪声。
- 气流调制使用 2200 Hz 低通噪声，仍可含低频；IR 和听音设备也可能导致突出频段。没有本机实际 IR/候选 WAV 的逐支路结果，不能认定唯一根因。
- 基础 renderer 仍有整轨 peak normalization+tanh。旧包 `package_gain_db=0` 只表示没有额外包增益，不表示算法内部无归一化。
- 原 afterfire 为 60 ms Gaussian noise × exp 衰减，左右声道同一激励。近片尾条件 `<N` 会丢掉整次事件，且 centered `same` IR 卷积会提前截取响应。这不等价于真实尾管压力瞬态。

## 四个候选（不是四种新车型）

| 编号 | variant | 改动 |
|---|---|---|
| AH-B0 | r1_baseline | AG-R1 原声 + 只读诊断，必须与既有 R1 包 40/40 WAV 字节相同 |
| AH-B1 | body_damping | 只降低额外固定共振支路的低负荷增益；不动主燃烧、低频阶次、IR、增压/BOV |
| AH-B2 | afterfire_pressure | 显式事件时间不变，改为压力前沿与短有色尾音，经同一 IR 的独立因果支路传播 |
| AH-B3 | combined | B1+B2，用于检验相互作用，不先行替代基线 |

B1 使用 15 ms 因果油门平滑，固定共振支路 scale 从 0.72 到 1.0。不是对最终输出做 notch/EQ。

B2 是工程假设，不是燃料/温度仿真：使用各车固定前沿/衰减参数、独立 RNG；固定事件能量预算为旧 60 ms 白噪声源期望能量的 4%，以适应更集中的压力前沿和独立路由。该数值没有经真车拟合，不能称最优。无整轨/逐事件 peak recovery，无额外事件、无自动改时序。基线随机数抽样仍消耗原数量，避免改回火顺便改了其它噪声源。新事件靠片尾时保留可输出的部分，不整次丢弃。因果支路不是整个旧 renderer 已实时化/全链因果化的声明。

所有干预候选用同一 parent trace 的旧 pre-saturation peak 作为固定分母，不重新按候选 peak 拉满，以免降低共振后其它声音被再次放大。不是可调 master gain。输出仍有数值上限保护；任何非零 ceiling count 必须显示为数值阻塞，不当作音质通过。

## 本轮真的借鉴了什么

均为重新编写的通用 DSP / 方法吸收，未复制下列项目代码、录音、preset、模型权重。

| Primary source | 本次采用 / 未采用 |
|---|---|
| https://github.com/DasEtwas/enginesound | 采用独立 engine-vibration / intake / exhaust 分层及 resonance dampening 的方法；本轮不是移植其 Rust 波导或整个引擎。MIT 项目。 |
| https://github.com/rdoerfler/ptr-model 与 https://arxiv.org/abs/2603.09391 | 采用“压力瞬态激励→声学传播”方向而非持续谐波/白噪声贴片；不移植神经网络、Karplus-Strong 网络或权重。仓库 CC BY-NC 4.0，商业代码/权重不能未经授权拿来直接嵌入。 |
| https://github.com/ATG-Simulator/VehicleNoiseSynthesizer | 分源和显式 tip-in/out/shift 事件边界作为工程参照；不接 Unity，不使用其录音颗粒库；本轮不声称移植它的 afterfire，它的文档不把 BOV 视作该素材库的一部分。 |
| https://arxiv.org/abs/2606.21521 | per-engine-order 与宽带残差分离、可解释参数表是下一步参考对齐方向；本轮未训练 EONE、未部署模型。 |
| https://github.com/ange-yaghi/engine-sim | 既有 EngineAcoustics 的主要启发来源继续保留；IR 是用户本地 UNVERIFIED_LOCAL_ASSET，不因源项目代码开源而升级资产权利。 |

检索日期 2026-09-09。不能把五个来源写成已完整集成五套引擎。ignis 仅作公开研究参照，本轮没有因 README 可见而假定其许可证或复制代码。

## 执行合同与交付

`stage_ah.run_experiment build` 强制传入既有 R1 package 和 manifest 文件 SHA。先验证源包、Base64 实际音频、IR 原始/有效 SHA，再渲染 B0。B0 40 WAV 任何一个与父包不同就终止；不拿“都是 R1”替代字节证据。

4 候选复用原 ten-scene generator / rich template / AF-R 不可覆盖发布器。identity_mode 仍表示 AG-R1 identity 层，另在 contract/signature 绑定独立 `source_remediation_variant`，不是改名冒充同一声音。

逐 variant 保存16条同名 Reference 对照、源支路 Welch谱（约2.93Hz频率bin，取决于样本长度）、pre-saturation/normalization数据、实际 decoded PCM SHA 与原 WAV-file SHA 的区别。相关支路能量不可以当作百分比直接相加。IR/Reference 原字节仅在用户本地流转，不推送Git。

某候选回退 >3% / 缺必需参考 / ceiling>0 时，保留有标记诊断产物，禁止自动服务/提升；其余候选仍完成诊断，不因一个失败让其它有用结果丢失。阈值不放宽、不自动调参。门禁通过也只是 READY_FOR_HUMAN_REVIEW。

serve 子命令复用已有 `StrictHTTPServer` / `_make_server`，没有新后台或新页面。默认 B0 23680–23683；B1 23780–23783；B2 23880–23883；B3 23980–23983。一次服务 B0 和一个候选，全部预绑定成功才启动。旧 23480–23483 和旧包不被替换。

## 不能承诺的内容

本次远端无法访问用户 E: 盘实际 IR/WAV，不声称已把剩余20%全部解决。固定频谱峰不自动等于错误；无同步 RPM/负载/麦克风条件的真实录音，与仿真逐样本波形不相同很正常。验收关注阶次轨迹、源能量/谐波比例、瞬态起落、回火尾音和人耳，不以截图曲线重合为目标。

远端工作流明确 checkout PR head SHA，而不是把 PR merge ref 叫作 exact-head。真实素材验证与合成 fixture 资格必须分开报告。
