# Stage AF 开源方法吸收记录

## 1. AngeTheGreat Engine-Sim — 当前最重要的声学基线

本项目 main=f81d3a3 的成功听感来自 Engine-Sim 架构思想的 Python 物理/物理启发重做：cylinder event、firing geometry、exhaust propagation、IR/path、induction。继续以此为声音生成主线。

原则：借鉴 architecture/method，不把“root MIT”自动扩展解释为所有 WAV/IR 资产都已具备产品权利。

## 2. SSSSM-DDSP

Repo：`hyakuchiki/SSSSM-DDSP`

Pin：`9068d9489808300d2b06bad3f1ab47c1aa40aee3`

License：MIT。

值得吸收：真实声音与合成声音有 domain gap 时，sound matching 应优化音频/频谱域目标，而不是只追参数标签或 sample alignment。

Stage AF clean-room 吸收：

- scale-invariant frequency-band representation；
- spectral centroid；
- envelope/positive-flux transient features；
- real-vs-synthetic reference distance 只作 parameter proposal/ranking。

没有复制其 neural model、训练代码或权重。

## 3. DDSP / differentiable sound matching family

借鉴其 `target audio -> differentiable/parameterized synth -> spectral loss -> parameter proposal -> re-synthesis` 思维。Stage AF 当前仍采用 Sobol bounded search，因为 EngineAcoustics 不是 differentiable；以后可加 DDSP surrogate 作为 warm-start，但真实 renderer 永远复验最终候选。

## 4. CMA-ES / evolutionary synthesizer sound matching

社区中已有用 CMA-ES/evolutionary search 让 synth 参数逼近目标频谱的工程。Stage AF 当前采用 SciPy Sobol + shrinking local domain，原因是参数数量少、范围小、需要 deterministic receipt。未来如果存在强参数耦合，可比较 CMA-ES，但不得扩大为不可解释的几十维黑盒搜索。

## 5. 旧项目继续复用

- VehicleNoiseSynthesizer：state hysteresis/crossfade/lifecycle；
- FFTConvolver：未来 Android/C++ partitioned IR；
- Oboe：未来 Android low-latency output；
- EV-engine-sound-sonification：telemetry-rate vs audio-rate interpolation，method-only；
- DiffMoog：未来 analysis-by-synthesis warm-start。

## 当前结论

现阶段不需要再找更多“能发出发动机声音”的仓库。真正缺的是把当前已经好听的 physical renderer 做**可控、可拟合、可回归、可移植**。
