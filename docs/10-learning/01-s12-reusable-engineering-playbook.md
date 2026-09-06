# S12 可复用发动机声浪工程 Playbook

更新：2026-09-05

这套路线可复用于新的车型，而不是每辆车从“听起来不像”重新乱调。

## 1. Source governance first

先建立 source registry、license/rights、paper/project version。代码许可和录音权利分开。

## 2. Clean-room method adoption

```text
Source
→ Method
→ local equivalent implementation
→ runtime call path
→ OFF/ON / ablation
→ PCM SHA
→ metric/evidence
```

不要复制不必要的第三方代码/音频/权重。

## 3. Persistent event-domain model

优先建立 crank/event/state、combustion、cylinder/path/bank/collector、forced induction、mechanical、transients，而不是 fixed harmonics + EQ。

## 4. ReferenceCaseSet / hard gates

reference 治理与 renderer correctness 分开。先保证 finite/no-clipping/no-click/state continuity/afterfire condition/Track-P，再比较真实感。

## 5. Reachability before optimization

参数必须真的被 runtime 消费并改变目标 layer/PCM/metric，才进入 search。不可达参数不放进优化器。

## 6. Analysis-by-synthesis

Stage X/Y 一轮 search → Stage AD 多轮 negative feedback：

```text
render
→ compare with Reference
→ fixed reference distance
→ source-causal parameter proposal
→ recenter/shrink
→ repeat
```

跨轮必须固定 ruler；不拿 changing-parent improvement 假装收敛。

## 7. Tune by causal family

推荐：body/idle → blower/induction → afterfire/transients。每个 family 有明确 target/guard；后一级继承前一级 final config。

## 8. Human is a separate sensor

算法指标不能替代人耳。听感问题转换为 scene→source→metric→hypothesis，再决定是否做 bounded final round。

## 9. Profile freeze is not OEM freeze

Human accepted 可以形成 Engineering Profile；只有 R1 才能进入更正式 calibration/OEM-level claims。

## 10. Product bridge

```text
Engineering Profile
→ AudioParameterPackage
→ Golden state/PCM
→ portable C++
→ Python↔C++ equivalence
→ Android realtime
```

离线 optimizer/CFD/report 不进入 realtime callback。

## 11. 借鉴的主要项目/论文路线

### 发动机事件/物理启发
- Engine-Sim：event/cylinder/path/bank/collector/forced-induction/persistent thinking。
- ENSIM4：重物理/1D CFD teacher，明确 teacher≠mobile runtime。
- DasEtwas enginesound：stateful waveguide/continuity。
- VehicleNoiseSynthesizer：state scheduling/hysteresis/crossfade。
- Ignis/pressure-domain literature：pressure/dP/DC lifecycle。
- PSOLA/cylinder-pressure OLA：cycle alignment/continuity。
- EONE/parametric engine representation：heavy authoring→compact runtime parameters。

### 负反馈/参数反演
- DiffMoog：differentiable modular synth / sound matching。
- Magenta DDSP：differentiable DSP/audio-domain losses。
- SSSSM-DDSP：synthetic↔real domain gap。
- Modulation Discovery：可解释 time-varying modulation。
- InverSynth / synth-setter / TorchSynth：audio→parameter proposal + re-synthesis。

### 车辆状态与实时产品
- SenaTaka engine-simulator：GPS/accelerometer→vehicle/engine state。
- EV-engine-sound-sonification：低频 telemetry→高频 DSP 的 interpolation/state reconstruction。
- ddsp-realtime：authoring 与 realtime runtime 分离的工程参考。

具体版本/license/adoption boundary 以 `docs/research/engine-audio-ecosystem/` 为准。

## 12. 最重要的复用经验

**不要以“找一个更像的项目”为路线；以“可解释 source model + governed reference + causal reachability + negative feedback + Human gate + versioned product runtime”为路线。**

## 13. Stage AF 数值修正的可迁移做法（2026-09-06）

对另一车型做声音修正时，先把“原声音是否被改变”和“修正是否有因果依据”分开。`EngineAcoustics` 的空 `numerical_fixes` 是 H0 anchor；固定车型、采样率、RPM/throttle 轨迹、seed 和 IR 后，H0 必须与旧输出逐 PCM 相等。之后一次只打开一个旗标：`cycle_phase` 处理 720° 曲轴角到 360° 四冲程循环相位的一次性换算；`causal_delays` 禁止 `np.roll` 回卷未来样本；`causal_convolution` 用 `UniformPartitionedConvolver` 让 IR 的 `h[0]` 成为时间零点；`causal_derivative` 用后向差分消除 look-ahead；`shift_cut` 保证换挡切断包络是 unity→cut→unity。每个旗标都要有最小 fixture、OFF/ON PCM SHA 和首个改变层的记录，不能只凭“听起来更响”或总体距离下降保留。

fit 阶段必须把车型、seed、数值旗标、renderer source SHA、IR 原始/有效 SHA 和 Reference source SHA 写入同一个 v4 receipt。候选参数只能来自明确的 source-causal family 范围；`body → path → induction（NA 跳过）→ afterfire` 的阶段顺序要稳定，后一阶段读取前一阶段的 `final_r3_diagnostic_fit.json`。每个参考场景单独执行退化 guard，不能用总体均值掩盖一个坏场景。缺少 fit、IR、Reference 或 provenance 时宁可停止，也不要回退默认配置、单位脉冲或新造一个 renderer。自动 metric 只做 engineering/diagnostic ranking，不能升级 Human accepted、R1、OEM 或 Profile Freeze。

## 14. 大体积试听页面的服务可用性经验（2026-09-06）

原 A/B 工作台采用自包含 HTML，把 WAV/Base64 嵌入单页后，文件可能达到几十 MB。此时“端口在 Listen”并不等于“可以刷新”：如果 `SimpleHTTPRequestHandler` 由单线程 `TCPServer` 承载，一个客户端慢慢读取响应会占住 handler，后续浏览器刷新只能等待或被拒绝。正确诊断顺序是查看监听端口、该端口的 `ESTABLISHED` 连接、实际进程命令行和 `127.0.0.1` 的 curl 结果；不要先删除试听包、改页面或终止其他端口。

修复只改变服务并发模型，不改变声音链路或页面内容：`ThreadingMixIn + TCPServer`，配合 `daemon_threads=True` 与 `block_on_close=False`。回归测试要故意保留一个不读取的 socket，再发第二个 HTTP 请求，第二请求必须在固定超时内返回 200；同时检查 H0/H1/H2 或四车型端口。这个经验适用于所有自包含试听包，也适用于未来车型迁移；服务修复成功仍只证明页面可用，不证明声音真实或人耳通过。
