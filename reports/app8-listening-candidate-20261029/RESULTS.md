# APP8 隔离听感优化实际结果

更新：2026-10-29（Asia/Shanghai）。状态：实际仿真、数字门与受控声学筛选通过；Terra max独立只读复核无阻断；C2C最终DONE、无阻断返修；Jovi试听尚未验收。基于明确授权的 C2C-OPTIMIZATION-PLAN.md 执行，固定参数首轮通过，没有搜索或救场调参。

## 直接试听与模型

下列试听副本均为每个完整版本一个固定标量，统一实测到−23.0 LUFS；片段沿用同一标量，仅首尾5ms淡入淡出，没有逐帧归一化或AGC。原始仿真gain仍为0.1，原件另存，未覆盖。

- [C完整90秒试听](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/C-full-level-matched.wav)
- [B相同换挡/原声层比例90秒对照](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/B-full-level-matched.wav)
- [A旧工况/原音色90秒基线](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/A-full-level-matched.wav)
- [C第一次升挡9.5–13秒](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/C-upshift_1-level-matched.wav)
- [C降挡56.5–60秒](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/C-downshift-level-matched.wav)
- [B高负载68–73秒](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/B-highload-level-matched.wav) / [C高负载68–73秒](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/C-highload-level-matched.wav)
- [实际隔离SLX](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/isolated/S12_hellcat_2022_stock_v12_listening_candidate.slx)
- [C固定gain原始PCM24 WAV](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/C/candidate.wav)

## 实际变更与结果

只改两份已授权声源helper：身份渲染器提供原归一化后的分层输出；源渲染器提供默认关闭的Hellcat研究选项。原默认/显式关闭路径三车型九帧golden精确一致。新增脚本、分析器、三份测试和模型均隔离，保留原bank mixer和Frozen处理。

|事件|时间|挡位|RPM变化|时长|
|---|---|---|---|---|
|升挡1|11.00s|1→2|4544→3019|0.24s|
|升挡2|20.00s|2→3|4963→3389|0.24s|
|升挡3|30.00s|3→4|4858→3295|0.24s|
|降挡|58.00s|4→3|2728→3985|0.30s|

RPM与声明的虚拟轮径/终传/挡速比、连续速度一致，换挡滑差单列。燃烧、燃烧阶次与identity exhaust采用平滑乘法包络，最小激励系数0.3500000144后恢复；机械与whine不被一并切断；最大相位对齐误差1.975×10^-7 rad，未在换挡重置源或Frozen状态。这里是燃烧声音激励减弱，不声称求解了真实轴端扭矩。

C相对相同控制的B，在原公共归一化之后将22/44阶identity whine最多降6dB，独立8阶induction最多降3dB，2000–3500RPM平滑启用。没有加新低频振荡器、输出低频EQ、辐射逆滤波或提高总gain。

|预登记筛选门|实测|结果|
|---|---|---|
|6个稳态锚点20–250Hz绝对功率变化≤1dB|最大0.000326dB|6/6通过|
|符合高RPM/load的稳态HF/LF降低≥3dB|降低5.918–5.999dB|4/4通过|
|驾驶轨迹所有合格窗口HF/LF降低≥3dB|降低5.999277–5.999923dB|3/3通过|

三个窗口为15.08–17.94、23.66–28.42、68.12–72.36秒；按窗口时长加权的高低频比变化−5.999658dB。HF为1–10kHz，LF为20–250Hz；均为相同控制、原始固定gain、分声道功率及功率均值比较。转速升高时阶次能量会离开固定低频带，另报0.5/1/1.5/2/4/8/22/44阶。结论是保留本底低频并减少高阶遮蔽，不能声称低频物理源幅度增加或人耳一定更好。

## 实际仿真与验证

A90秒+B90秒+C90秒+C_repeat90秒，以及6锚点B/C各6秒，均在实际Simulink中完成。C重复发生在同一MATLAB会话。每个90秒输出4500帧，最后起点89.98秒；4,320,000×2样本、48kHz、PCM24 WAV独立读回通过，实数/finite/非静音/最终PCM±1与既有连续性门保持。实际9维输入逐帧与声明工况精确相同，源与辐射压力均捕获；另对四份原生capture矩阵逐一读取全部4500帧，对照顺序PCM字节且无尾部剩余，全部通过（native-frame-verification.json）。

- MATLAB回归131/131，failed/incomplete均0：[日志](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/regression-bound.log)。
- 分析器Python59/59（analysis-tests.log）；源合同Python8/8：[源合同日志](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/source-interface-python-final.log)。
- A原始PCM与前一版默认90秒SHA精确相同：2e809bf2f17e1ea07f9a3e9c1b54027da12d9d09f8cd85f974ce39f66ce2f74d。
- C/C_repeat PCM SHA均为b77d372ddc23336e9d94437854f53548ae4b626a4ea553a5b47297072c4be610；WAV SHA均为f3d3ae39cf511b4413958ad70a4a6ae557ada80dfe7c1129219c87035cb5d279；峰值0.02959120394。
- 原SLX、声库、profile原件、Android、Frozen等604项保护SHA全部不变；运行前后34项依赖一致。[交付清单](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/delivery-manifest.json)。
- 原模型SHA 71f8b9899688278e908e244649331352d43c46779e6fd93c0903f86785198a9c；新隔离模型SHA 30d0c9b024dc9cd70d39f45544e1518c61fed511b6ba112c278562fac6891db3。

[原始运行回执](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/run-summary.json) / [频谱与阶次分析JSON](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/analysis.json) / [窗口CSV](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/comparable_windows.csv) / [响度匹配验证](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/audition/level-match-verification.json)。

![换挡包络](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/shift-envelope.png)

![曲轴阶次](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/order.png)

## 研究因素与边界

先前频率采样已经从实际源压力、传递响应和最终PCM定位到高阶声源与辐射后的频谱倾斜，详见[诊断与论文因素记录](E:/Tesla_speed/reports/app8-acoustic-review-20261028/FINDINGS.md)。研究覆盖RPM/load、燃烧脉冲与点火阶次、进气/机械增压、bank时序、排气传播与辐射、瞬态、观测条件；当前候选仅修本次授权的驾驶事件和选择性声层平衡。轮径、速比、切断时长与声层参数均为研究假设，未作为OEM实测标定。

完整FVM/PTR物理网络、工况同步实车录音声图、独立真实留出、设备道路及人耳接受仍未完成。此次完成的是受控听感候选仿真与自动筛选。车型资格不提升，原产品路线不变。

旧runs/full-20261029-011621保留INVALIDATED.json并排除；新run修复了脚本局部变量作用域导致的锚点目录复用，16目录唯一、12个锚点控制均核验。失败证据没有覆盖，合同和参数没有修改。最初回归路径缺失的失败日志保留，显式补全测试路径后131/131通过，未为此改源函数。

工程产物仍位于隔离工作树、未提交。Hub报告被既有仓库身份校验拒绝，本地NOT-SENDABLE保留，无发送成功、无自动重试或修改绑定。

实际最终PCM事件检查：对B/C原始双声道按20ms逐帧RMS计算，覆盖四次换挡前后，保留后级延迟与尾响；不把单次RMS最低值当作单独切断的因果贡献或人耳门。见 [最终PCM换挡包络](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/runs/full-20261029-013256/final-pcm-shift-envelopes.png)、同名CSV/JSON。

最终评审：[Codex with ChatGPT复核](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-listening-candidate-20261029/C2C-REVIEW.md)返回DONE；Terra max独立只读复审无阻断。Jovi对本候选的试听验收仍未发生。

归档：Obsidian受管progress/decisions经Fresh DryRun与原子写入返回MEMORY_UPDATED；根项目账本及两份生成视图同步，--check通过。Hub未发送状态仍保留。
