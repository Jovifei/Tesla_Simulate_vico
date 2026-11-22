# APP8 v1.4 C2C 冻结实例与合成诊断

工作树 `E:/Tesla_speed/worktrees/v14-c2c-hellcat-20261122`，分支 `codex/v14-c2c-hellcat-20261122`，基础提交 `faac65cf240988b657990cb6436b1271e7bebe30`。实验文件位于 `E:/Tesla_speed/experiments/v14-local-handoff-20261122/hellcat`。

## M1 实例隔离

用真实 Simulink ModelReference 加载原 Frozen SLX 和新名称的 Frozen 派生副本。副本仅改用候选私有持久上下文包装，原数值核与边界包保持只读。纯合成的两个 960 采样帧序列以 20 ms 步长输入，单实例输出与各自独立数值核逐位一致。双实例同时运行、交换两个输入、重置后重复均与单实例逐位一致，顶层实测输入和输出时间也逐位或逐时间核对。

负控将两个不同 ModelReference 指向同一个原始持久包装。首帧末尾脉冲的跨帧尾音在负控中产生 0.6556874763178249 的无量纲偏差，证明本夹具能检出共享状态串扰。两个独立 MATLAB R2026a 进程的输入、正负控输出、包装代码与模型 SHA-256 一致，均正常退出。完整保护文件和模型哈希、PID、时间戳与误差见 `m1-cross-process-receipt.json`、`run_c/receipt.json` 与 `run_d/receipt.json`。

该夹具覆盖了固定离散步长、这组脉冲与交换输入。它没有证明任意求解器、任意输入、单帧重复求值或完整车辆工况下的行为。原 Frozen 是 radiation audio adapter，不是完整 FVM/PTR 网络。

## 预声明合成工程诊断

`SYNTHETIC-DIAGNOSTIC.json` 在仿真前固定两组 750/1200 RPM、load 0.16、48 kHz、150 帧和 1–3 秒测量窗。独立 source 使用项目配置中明确标记为合成假设的八缸点火相位和 bank map，生成确定性的周期脉冲，未使用外部音频素材。新 Simulink 模型把相同 source 分送到直达支路和 M1 独立 Frozen 派生实例，固定输出 `0.1 * 0.5 * (source + frozen)`。实际输入、source、Frozen、混合路由和原始 PCM 均已校验。无量纲声压及直达/路径的固定混合尚无实车标定依据。

| 条件 | 1–3 秒混合 RMS | 20–80 Hz | 80–250 Hz | 4 阶 | 全轨 true peak | 削波样本 |
|---|---:|---:|---:|---:|---:|---:|
| 750 RPM | −55.85 dBFS | −56.58 dBFS | −115.42 dBFS | −56.73 dBFS | −45.2 dBTP | 0 |
| 1200 RPM | −55.81 dBFS | −61.70 dBFS | −57.48 dBFS | −56.69 dBFS | −45.2 dBTP | 0 |

2/8 阶、阶次与剩余频率能量比、source/Frozen 分支、完整波形 SHA-256 和方法见 `synthetic_diagnostic/analysis.json` 与 `synthetic_diagnostic/receipt.json`。Welch 使用 1 秒 Hann 窗，阶次剩余量包含窗口泄漏。数值接近机器精度时不可解释为实车噪声比。当前信号几乎由 4 阶主导，尚不能证明期望的机械颗粒感或 Hellcat 音色。

## V2 固定因果脉冲结构试验

V2 在独立文件中预声明每次点火的上升和衰减分别占 90 曲轴度点火间隔的 1/8、3/8，采用半余弦窗；每 bank 四个气缸各占 0.25。沿用 v1 的 synthetic 点火相位、负载、时钟、0.5 混合和 0.1 renderer。该常数是事先固定的合成信号定义，没有拟合、EQ、AGC 或事后增益。v2 两组输入的 SHA-256 与 v1 各自一致，实际 Simulink 输入、source、Frozen 和混合路由均通过核对。

| 条件 | V2 混合 RMS 相对 V1 | V2 混合 20–80 Hz 相对 V1 | V1 的 8 阶/4 阶 | V2 的 8 阶/4 阶 | V2 true peak | V2 削波 |
|---|---:|---:|---:|---:|---:|---:|
| 750 RPM | −5.78 dB | −6.63 dB | −65.13 dB | −4.77 dB | −53.9 dBTP | 0 |
| 1200 RPM | −5.72 dB | −9.03 dB | −65.02 dB | −4.67 dB | −53.6 dBTP | 0 |

两个条件的 source、Frozen 和 combined 支路均通过事前声明的 RMS 与 20–80 Hz 不增加检查。V2 最大帧边界跳变分别为 0 和 1.10e−5。该固定结构提高了 8 阶相对 4 阶的比例，同时整体音量降低。2 阶仍接近数值底，不能据此声明机械感改善或车型保真。高阶次/剩余比在 1200 RPM 接近数值残差，不是实车噪声测量。

第二次 v2 在 `v2-relocation-repro/synthetic_diagnostic_v2/` 下执行。每个转速目录包含 `source.wav`、`frozen-cabin.wav`、`combined.wav`，以及三条对应的 `*-rendered.f32le`。两条单独支路各使用固定 0.1 renderer，混合轨保留 0.5/0.5 后的 0.1 renderer，均为单声道、48 kHz、24-bit PCM WAV。独立脚本逐样本验证 f32 和 WAV 对应关系，确认原始 source/Frozen/combined 与第一次 v2 哈希一致。此次迁移只复制了已验证的 v1 元数据和模型，未重新生成 v1；完整干净工作树复跑由集成方执行。

## 执行与范围

- `run_m1_isolation(artifactRoot,'run_c',false)` 与 `run_m1_isolation(artifactRoot,'run_d',false)` 分别由独立 MATLAB `-batch` 进程执行，退出码均为 0。模型由同脚本的首次 `buildModels=true` 阶段创建并保存。
- `run_synthetic_diagnostic(artifactRoot)` 由独立 MATLAB `-batch` 进程执行，退出码 0。其后 `python analyze_synthetic_diagnostic.py <artifactRoot>/synthetic_diagnostic` 退出码 0。
- `run_synthetic_diagnostic_v2(artifactRoot)` 由另一个 MATLAB `-batch` 进程执行，退出码 0。复用同一分析脚本及 `compare_synthetic_v1_v2.py`，两个进程退出码均为 0。
- 原 Frozen 模型与数值核、边界包、车型源配置等受保护依赖的运行前后哈希相同。实验结束后参与测试的 MATLAB 进程已退出。
- 文件 `m1-cross-process-receipt.json` SHA-256 `0156b2e163ebc71ca9932dbf9b096d75f32894687974e017ab680a5c08164a77`。
- 文件 `synthetic_diagnostic/receipt.json` SHA-256 `51fa544f0837ae0a878029ea67a50b0e4fc85a737d1c956fe67ededa956359f2`。
- 文件 `synthetic_diagnostic/analysis.json` SHA-256 `14d28d2f348a9983b8d5748372caa81962eeedf6480790550f32cf21d222e5b3`。
- 文件 `synthetic_diagnostic_v2/receipt.json` SHA-256 `71b45e74838aa32a04a454c38cde4b4b512b708cbec6595ed8edfb035bed2692`。
- 文件 `synthetic_diagnostic_v2/analysis.json` SHA-256 `cd2bdaac761ccb9f40c2c7b42ffc219b192fe5cbbde0ade22604ef864be3d6aa`。
- 文件 `synthetic_diagnostic_v2/v1_v2_comparison.json` SHA-256 `4aba5b8eff5964b277e014421947f40d721eef643c4c8f1bc2d51af1c5a5bad6`。
- 文件 `v2-relocation-repro/synthetic_diagnostic_v2/receipt.json` SHA-256 `cf63baa4697264f6b733eefa0296155948cceefc8ecf88e912f8b373ba7cca4e`。
- 文件 `v2-relocation-repro/synthetic_diagnostic_v2/analysis.json` SHA-256 `38ba70d1abce532c6db0dc9336a83349d4b829e9642ef6171e200d3fb6d8e907`。
- 文件 `v2-relocation-repro/synthetic_diagnostic_v2/v1_v2_comparison.json` SHA-256 `eb0193bf15adeb758b3eaf579c6969f85bf5a69dd986bcc13ff8ec19311e88b9`。
- 文件 `v2-relocation-repro/synthetic_diagnostic_v2/rendered-stems-verification.json` SHA-256 `9699fbb659279f76babd27cad6068b39e6a1f404d33a41e5a301196625d04b1`。
- 正式 M2 仍为 BLOCKED，缺少 T1–T4 冻结轨迹及哈希绑定与可用于拟合/留出的同车合格参考。本轮未运行正式 T1–T4/C0，未声明 −16 LUFS 正式结果，Jovi 听感、设备及车辆验收均未运行。
