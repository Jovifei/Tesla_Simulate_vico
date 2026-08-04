# S12 Engine Acoustic Realism — 阶段审核与反思报告

> 日期：2026-08-04  
> 审核对象：Ferrari 458 / Hellcat / RX-7 FD 的离线 Python 声学身份与真实感候选  
> 当前状态：`AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`  
> 强制边界：`synthetic / uncalibrated / not OEM reproduction`

## 1. 给 Jovi 的执行摘要

这一阶段已经不再是“三个名字、一个模板、几个 EQ/增益参数”的做法。三个车型在 PTR 前使用独立事件拓扑：Ferrari 是 flat-plane V8 交替 bank 与金属瞬态；Hellcat 是不规则 cross-plane V8 排气、机械层和带惯性的增压器；RX-7 是双转子相位事件与双阶段涡轮状态。三者共享的只是低频压力传播、冻结 audition adapter、PCM24 写入、响度测量和绘图基础设施。

Jovi 最新试听反馈应被精确理解为：**Hellcat 的低频轰鸣已经提供了部分可辨识的“大排量/机械重量”线索，但在实际播放链中整体响度仍偏小。** 这不是“已通过真实感”的结论。它同时说明低频身份层方向有效，也暴露出数字文件响度与实际设备听感之间还没有被校准。

当前正式 Hellcat 文件的数字证据是：`-16.00 LUFS`、`-20.77 dBFS RMS`、`-3.12 dBFS peak`、零削波；整段使用固定 `+18.569 dB` 增益。这证明文件没有静音、未削波、没有按 RPM 自动增益，也没有在不同片段之间做 AGC。**它不能证明 Windows 音量 30–50%、当前扬声器/耳机、或人耳对低频的主观响度足够。** 该缺口是当前最具体的审核与下一轮优化入口。

本压缩包只包含已完整生成并验证的正式 30 秒连续驾驶循环。它明确排除了先前因工具时限中断、只有 Ferrari/Hellcat 中间文件而缺少 RX-7/报告/manifest 的目录。

## 2. 最终目标、当前阶段和不变边界

### 最终目标

闭眼试听时，用户首先能分辨：

- Ferrari 458：轻而高转、金属、自然吸气 V8 的连续 scream；
- Hellcat：大排量 V8 的低频压力、机械侵略性和随负载变化的 blower；
- RX-7 FD：非活塞转子时间结构、涡轮起压与收油释放。

同时，它们的怠速、加速、全负载、收油减速和回怠速必须是同一条连续车辆状态链，而不是把独立 WAV 拼接在一起。

### 本阶段范围

`Vehicle State → 独立 Source → Idle dynamics → Afterfire → Pressure/Exhaust/Body/Radiation layer → frozen audition adapter → fixed whole-cycle loudness → PCM24`。

没有修改下列内容：FVM、PTR core、Radiation Boundary、Runtime latency、Android protocol、MATLAB、Simulink。当前 Python adapter 是受冻结包约束的轻量试听适配器，**不是**完整 FVM/PTR 管网仿真。

## 3. 已完成工作

| 子系统 | 已完成内容 | 已有证据 | 真实感含义 |
| --- | --- | --- | --- |
| 车型身份 | 三套独立 renderer：`flat_plane_v8_source.py`、`supercharged_hemi_source.py`、`rotary_turbo_source.py` | v0.15 58/58 回归 | 不再用同一 excitation generator 加不同 gain |
| Ferrari | 90° 全机事件间隔、交替 bank、2350/3820 Hz impulse-driven metallic resonator、高转能量重分配 | 高频比例与金属 stem | 高转仍是音色/事件密度变化，不把 RPM 直接当音量 |
| Hellcat | 不规则 cross-plane bank、左右不同包络、blower shaft families、belt/compressor/valvetrain/casing/intake | blower/boost/bypass diagnostics、40–200 Hz 指标 | 深 V8 与机械增压器为两路独立声源 |
| RX-7 | 两条相位差 0.5 cycle 的 rotor event train、housing、primary/secondary spool、boost、BOV | rotary/turbo/blow-off stems | 不使用活塞 firing order，也不是只改 EQ |
| 怠速 | deterministic cycle amplitude/phase variation、accessory、valvetrain、crank stems | 每车 variation/jitter 指标 | 解决纯振荡器怠速过于死板 |
| 低频 | `pressure_pulse → exhaust_coupling → body_resonance → radiation` 因果链 | Hellcat 40–200 Hz fraction `0.6912` | 低频来自状态相关压力与共振，不是 `audio *= 5` |
| 收油 | thermal + high RPM + closed throttle + event cluster 的 afterfire | 连续循环中 43 / 38 / 30 个事件 | 回火需要高转、热态和收油；不是随机白噪声 |
| 响度 | K-weighted LUFS、RMS、peak、crest、single fixed gain/headroom | 全部正式 WAV 读回 | 不做逐段 AGC、不过度削波 |
| 连续试听 | 每车一条完整 30 s WAV，18 s 高转收油 | 新增 RED→GREEN 回归 | 听到的回火与之前加速/热态直接连续 |
| 可审计发布 | WAV、spectrogram、order map、JSON、报告与 SHA manifest | formal manifest 13 项逐项复算一致 | 复查时可定位任一音频及参数 |

## 4. 正式试听工况与交付物

### 连续状态时间线（所有车辆）

| 时间 | 状态 | 目的 |
| --- | --- | --- |
| 0–4 s | idle | 检查机械怠速、循环波动和基础低频 |
| 4–13 s | acceleration | 检查转速/负载导致的阶次、压力和增压状态增长 |
| 13–18 s | full pull | 建立高负载热态与最高转速 |
| 18–23 s | closed-throttle lift / afterfire | 节气门由约 `0.98` 直接闭至 `0.03`，检查回火/减速 |
| 23–26 s | coast | 检查压力衰减、blower/turbo 余量与机械尾音 |
| 26–30 s | idle return | 回到车型怠速，而不是突然截断 |

默认工况参数：48 kHz、双声道、PCM24、每车 `1,440,001` 帧、精确时长 `30.000020833 s`。多出的 `1/48000 s` 是端点采样，不是时间拉伸或循环。

### 每车轨迹参数（全部为 C/synthetic）

| 车型 | RPM 节点：0 / 4 / 13 / 18 / 23 / 26 / 30 s | Load 节点 | 目标 |
| --- | --- | --- | --- |
| Ferrari 458 | 1050 / 1050 / 7800 / 9000 / 5500 / 1800 / 1050 | .14 / .14 / .35 / .98 / .12 / .08 / .14 | 高转 NA scream，低频克制 |
| Hellcat | 820 / 820 / 5200 / 6200 / 3600 / 1300 / 820 | .16 / .16 / .35 / 1.00 / .12 / .08 / .16 | 低频排气压力与 blower 负载感 |
| RX-7 FD | 920 / 920 / 6500 / 7800 / 4800 / 1700 / 920 | .15 / .15 / .35 / .98 / .12 / .08 / .15 | 转子/涡轮状态，不套活塞节奏 |

收油前的 throttle 节点是 `.14 / .14 / .92 / .98`；18 s 起为 `.03 / .03 / .03`，到结尾回到各车 idle load。该突变是刻意的 engine-state input，用于触发收油逻辑；**并不是把已生成的音频剪接到一起。**

## 5. 当前正式音频与指标

| 车型 | 正式 WAV | LUFS | RMS / peak dBFS | 固定整段 gain | 40–200 Hz energy fraction | afterfire events / energy | 削波 |
| --- | --- | ---: | --- | ---: | ---: | --- | ---: |
| Ferrari 458 | `formal_artifacts/ferrari_458/drive_cycle.wav` | -16.00 | -25.28 / -4.57 | -1.829 dB | 0.0446 | 43 / 121.925709 | 0 |
| Hellcat | `formal_artifacts/hellcat/drive_cycle.wav` | -16.00 | -20.77 / -3.12 | +18.569 dB | **0.6912** | 38 / 93.795542 | 0 |
| RX-7 FD | `formal_artifacts/rx7_fd/drive_cycle.wav` | -16.00 | -21.58 / -3.00 | +1.317 dB | 0.0429 | 30 / 44.788674 | 0 |

Hellcat 的 `0.6912` 是整个连续 source 的 40–200 Hz 能量占比，而不是“真实车辆已测得 69.12%”。它只证明本 synthetic source 的低频压力层明显重于 Ferrari/RX-7，和 Jovi 听到“低频轰鸣有点像”是一致的方向性证据。

Ferrari 的 spectral centroid 是 `1424.45 Hz`，Hellcat 是 `267.38 Hz`，RX-7 是 `776.00 Hz`。这是自动化结构分离的辅助指标，不是车型真实性分数。

## 6. 关键参数审计

所有数值是 `C/synthetic` 工程参数；R2 公开视频只给相对听感/频带提示，不能升格为 OEM measured 或绝对 SPL 标定。

### 6.1 Hellcat：当前最应审核的低频与增压参数

| 部件 | 当前参数 | 作用与风险 |
| --- | --- | --- |
| LF body resonators | engine body `50 Hz, Q=2.2, gain=.55`; exhaust `73 Hz, Q=2.5, gain=.45`; mechanical `105 Hz, Q=3.0, gain=.18` | 低频重量的来源；盲目加 gain 会加重 masking，未必提高可听“力量” |
| pressure chain | pulse `1.12`; exhaust `74 Hz ×1.05`; body `51 Hz ×.92`; radiation `×1.08` | 当前 40–200 Hz 的主要原因；必须和 attack/中低频共同审，不应只放大 50 Hz |
| exhaust | 4 events/rev，不规则 bank pattern `(0,1,0,1,1,0,1,0)`；左右包络 time constant `40/28 ms` | 提供 cross-plane 非均匀时间结构 |
| blower inertia | boost rise/fall `75/220 ms`; load rise/fall `70/200 ms`; bypass `50 ms` | 使 whine 随 rpm/load/boost 变化，非固定正弦 |
| blower family | shaft ratio `2.36 × (.93 + .16×boost)`；基频、5×、10×，权重 `.34/.94/.38` | 当前主要机械增压听感；应由高负载片段而非怠速决定 |
| blower envelope | baseline `.086 × pressure compensation × load² × throttle`; bypass attenuates up to 30% | 解释“负载增加 whine 增强” |
| mechanical/intake | casing `.030`、belt `.010`、valvetrain `.008`、compressor `.012`、intake `.026` | 提供皮带/压缩机/进气存在感，不是录音采样 |
| digital master | integrated target `-16 LUFS`; result `-3.12 dBFS` peak; fixed gain `+18.569 dB` | 数字层尚有 `2.12 dB` 峰值空间到 -1 dBFS；不能据此直接宣称设备会更响 |

### 6.2 Ferrari 与 RX-7 的关键差异参数

| 车型 | 关键 source | LF pressure profile | 重要限制 |
| --- | --- | --- | --- |
| Ferrari 458 | 4 events/rev、90° 间隔、交替 bank；metallic impulse resonators `2350/3820 Hz` | pulse `.26`; exhaust `132 Hz ×.68`; body `96 Hz ×.34`; radiation `.58` | 禁止为了听感把 Ferrari 的低频推到 Hellcat 水平 |
| RX-7 FD | two-phase rotor train，offset `.5 cycle`; primary spool `160 ms`、secondary spool `310 ms`; boost rise/fall `100/220 ms`; BOV decay `280 ms` | pulse `.31`; exhaust `128 Hz ×.48`; body `86 Hz ×.28`; radiation `.48` | 禁止换成 piston firing order 或以 EQ 替代 rotor time structure |

### 6.3 Idle 与 afterfire 参数

| 车型 | Idle variation / jitter | Idle valve | Afterfire min RPM / gain / ringing |
| --- | --- | --- | --- |
| Ferrari | `.12` / `.30 ms` | `1850 Hz` | `4200 RPM`, `.060`, `115/1550 Hz` |
| Hellcat | `.18` / `.55 ms` | `930 Hz` | `3300 RPM`, `.095`, `78/920 Hz` |
| RX-7 | `.10` / `.42 ms` | `1320 Hz` | `4300 RPM`, `.045`, `135/2050 Hz` |

Afterfire 共用资格条件是 `throttle < .12`、一次由开到关的 transition、最近 `0.52 s` 内有 close-memory、温度 proxy `>= .16`、超过车型最低 RPM、并落在确定性 event cluster。温度 proxy 的时间常数 `220 ms`。所以它不是任何时刻随机叠加的爆音。

## 7. 已验证与未验证的边界

### 已验证（自动化/文件层）

- focused realism suite：`9/9 PASS`，包括连续 drive-cycle 在三车收油后都有非零 event/energy 的新回归；
- v0.15 regression：`58/58 PASS`；
- `compileall` 与 `git diff --check`：PASS；
- 三个最终 WAV 都重新读回为 48 kHz / stereo / PCM24、finite、zero clipping；
- formal output 13 个非 manifest 项的 SHA-256 与 `manifest.json` 精确一致；
- frozen `runtime_ptr_adapter.py` SHA-256：`fdb594838ada4e2867f0ee1d2ea64a53788c1feb6593f7f37c5caf7bae494cb5`；
- FVM/PTR core/Radiation/Runtime/Android/MATLAB/Simulink 受保护路径 diff：`NONE`。

### 尚未验证，不能写 PASS

- Jovi 是否闭眼即能稳定识别三车；
- Hellcat 在 Jovi 的 Windows 音量、声卡、耳机/扬声器上的实际 dB SPL 与主观响度；
- 三车是否接近真实 stock vehicle，而不是“有身份差异的 synthetic candidate”；
- R1 录音、RPM trace、麦克风位置、负载、档位、排气状态、绝对 SPL 与 reference-distance 标定；
- 完整物理 FVM/PTR 网络对本试听音频的实际输出；
- Android/实时硬件/车载部署。

## 8. 当前 Git、交付与清理状态

代码工作树：`E:\Tesla_speed\worktrees\s12-v12`，branch `feature/s12-v12-reference-calibration`，HEAD `561b8fc77b32cb105b22bd5d498833f163d7f9e2`（v0.15 identity commit）。

当前 v1.0 realism/drive-cycle 工作**未提交**：7 个 tracked 修改路径与 9 个未跟踪 source/data/test 路径。这样能保证 Jovi 审核当前成果前没有把“自动化候选”混同为正式 release。是否 commit/push 应在听感与优化决定后另行授权。

先前超时产物目录仍在磁盘上，但它只含两车中间文件；环境策略拒绝删除命令，因此它被明确排除在本审计包与正式清单之外。正式审核只认下列目录：

`E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10-complete-drive-cycle-30s`

## 9. 对本轮问题的反思

### 已纠正的错误

第一次把 `full_pull.wav` 当成试听入口是错误的产品交付选择：它定义上保持开节气门，因此不会触发 afterfire。虽然独立 `deceleration.wav` 已包含回火，用户听到的却不是一个完整驾驶过程。此后已新增回归：默认试听必须是单一连续 trace；18 s 由高负载直接收油；每车必须有 `afterfire_event_count > 0` 与 nonzero afterfire energy。

### 当前不能再次犯的错误

1. 不能把 Jovi 的“音量小”直接解释成 `audio *= N`。那会掩盖固定 gain、headroom、Windows 播放链、频带掩蔽和车型身份之间的差异。
2. 不能因为 Hellcat 的 40–200 Hz 指标很高就继续盲目加强 50–74 Hz。当前它已经占 `0.6912`，更深不一定更有压迫感；可能损失 100–400 Hz attack 或在播放设备上被低频滚降。
3. 不能把 -16 LUFS 视为“人耳音量已经合格”。这是完整数字文件的 K-weighted integrated 值，并非设备/房间/耳机听感认证。
4. 不能以自动 A/B 与零削波替代真实参考标定和盲听。

## 10. 待完成项、真正卡点与下一轮可选优化

### 待完成项

| 优先级 | 工作 | 需要的输入/授权 | 成功标准 |
| --- | --- | --- | --- |
| P0 | Jovi 对三条完整 WAV 的人工审核 | 请记录播放设备、Windows 音量、耳机/扬声器、最明显时刻 | 逐车给出“像/不像”、音量、低频、机械/增压/转子三项评价 |
| P0 | Hellcat audition-master 对比 | Jovi 授权只改离线 master，不改 source topology | 保持单一整段 gain、peak ≤ -1 dBFS、无 clipping；A/B 比较 -16 与候选 -14 LUFS |
| P1 | Hellcat 低频存在感优化 | Jovi 授权 source-level 参数修改 | 先比较 50–100、100–200、200–400 Hz 与 attack；禁止仅增加总体 gain |
| P1 | 真实参考标定准备 | 可审计 R1 音频、RPM/工况、视角、stock、录音位置权利 | 建立 reference-vs-synthetic order/spectrum/transient distance，而非依赖公开视频印象 |
| P2 | 人耳盲听试验 | 车型名隐藏、音量匹配、至少数轮 | 身份识别率和混淆矩阵；结论才可从 candidate 提升或否决 |
| P2 | Git 收口 | Jovi 审核并明确提交范围 | 仅 stage source/test/docs；不提交 WAV/PNG/raw media/缓存 |

### 当前卡点

没有代码崩溃、PCM 格式错误、回火 gate 失败或冻结边界冲突。真正的卡点是**校准和感知证据**：

1. 没有可用于数值拟合的 R1 参考；当前三车均是 R2 third-party listening context，含未验证 trim、麦克风 AGC、距离、环境、RPM/load 风险。
2. 没有 Jovi 当前设备的主观响度/频带反馈记录；所以不能判断音量小来自 -16 LUFS 目标、Windows、扬声器/耳机低频响应，还是 Hellcat 的频带平衡。
3. 没有盲听结果，不能说“身份已经成功”或“真实感已 PASS”。

### 建议 Jovi 审核后的最小下一步

优先建议选择 **P0：只做 Hellcat 固定整段 audition-master A/B**。理由是当前 Hellcat peak 为 `-3.12 dBFS`，若从 `-16` 提升到 `-14 LUFS`，理论上增加约 `+2 dB` 后 peak 约为 `-1.12 dBFS`，仍在 -1 dBFS headroom 约束内。该实验不改 RPM→音量关系、不改 afterfire、不改低频共振，也不做 per-clip AGC。它可以最干净地回答“只是数字播放级别偏小吗”。

如果 -14 LUFS 仍觉得 Hellcat 缺力量，再进入 P1：将 Hellcat 的低频优化从“更多 50 Hz”改为“压力 attack、73/105 Hz articulation、100–400 Hz 可闻重量”的对比实验。该实验必须每次只变一组参数，并同时给出源级/最终 PCM 频带、peak、LUFS、afterfire 与人耳 A/B，不能以单一 RMS 为准。

## 11. 包内容索引

| 路径 | 内容 |
| --- | --- |
| `S12_Acoustic_Realism_Phase_Review_2026-08-04.md` | 本阶段报告 |
| `review_evidence.json` | 机器可读关键证据 |
| `formal_artifacts/` | 3 个正式 WAV、每车 metrics/频谱/order map、正式报告与原始 formal manifest |
| `code_snapshot/` | 当前 publisher、三套 source、idle/afterfire/LF/loudness/metrics、测试与 target/reference records |
| `package_manifest.json` | 包内每个文件的 SHA-256 |

## 12. 审核结论模板（请 Jovi 填写）

| 车型 | 音量（小/合适/大） | 怠速 | 加速 | 18 s 收油/回火 | 最像/最不像的点 | 下一步授权 |
| --- | --- | --- | --- | --- | --- | --- |
| Ferrari 458 |  |  |  |  |  |  |
| Hellcat | 当前反馈：低频轰鸣有点像；整体音量偏小 |  |  |  |  |  |
| RX-7 FD |  |  |  |  |  |  |

本报告不声明 OEM 复刻、校准完成、物理声压正确或人耳最终 PASS。它的作用是把当前候选、参数和未解决问题完整暴露给下一轮审核。
