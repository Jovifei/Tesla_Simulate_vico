# APP8 低频轰鸣与机械声研究：实际交付

更新：2026-10-29（Asia/Shanghai）。Jovi已明确授权，执行子代理均为GPT-6.1 sol high。状态：实际模型运行、独立数值筛选和响度匹配验证全部通过；Codex with ChatGPT最终DONE、无阻断返修；本候选人耳尚未评价。

## 先试听

各整段与各短片段组分别从原始输出一次乘固定标量匹配−23.0LUFS；组内实际响度误差0.0LU，没有逐帧AGC或削波。短片段独立匹配，不能与另一片段按绝对音量直接比较。

|版本|含义|完整90秒|同工况高负载片段|
|---|---|---|---|
|B0|原声层比例、保留3升1降的基线|[B0](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/whole_tracks/B0.wav)|[B0](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/high_load_3/B0.wav)|
|R|只增加低频路径|[R](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/whole_tracks/R.wav)|[R](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/high_load_3/R.wav)|
|SR|较轻机械调制+低频|[SR](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/whole_tracks/SR.wav)|[SR](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/high_load_3/SR.wav)|
|SR2|较强机械调制+低频|[SR2](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/whole_tracks/SR2.wav)|[SR2](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/high_load_3/SR2.wav)|
|C_rejected|上轮Jovi否定的参考，已从原件重新匹配响度|[C](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/whole_tracks/C_rejected.wav)|[C](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/high_load_3/C_rejected.wav)|

[较强版第一次升挡](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/upshift_1/SR2.wav) / [较轻版第一次升挡](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/named/upshift_1/SR.wav) / [盲听说明](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/LISTENING.md)。

具名69个、盲听89个WAV，10组对照。原始固定gain音频另存；[SR2原始PCM24 WAV](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/runs/full-20261029-092429-542/SR2/candidate.wav)。此前B/C的原生4500×9double控制已由父任务MATLAB精确核对，参考C只有匹配工况的全长/驾驶片段，没有虚构对应新怠速锚点。

## 实际改动

唯一现有源码修改：s12_v12_render_source_frame.m，在Hellcat研究模式给现有source mechanical及归一化后identity mechanical增加固定机械增益/720°周期包络。两档S/S2为g=1.25,d=0.15和g=1.5,d=0.45，40曲轴度升余弦；缺省中性路径直接旁路，原默认/B/C的波形、状态与诊断精确保持。原归一化公式保持。

在新隔离候选中，bank平均之后、原Frozen之前加入HP20/LP220有状态支路，y=x+BP(x)。全信号仍经过原Frozen。参数是预先固定的研究刺激，不是实车机械/气门/活塞时序或辐射标定，没有新的自由振荡器。保留原增压/进气声作为B0对照，未继续仅压高频。

[新隔离SLX](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/isolated/S12_hellcat_2022_stock_v12_rumble_mechanics.slx) SHA eeb3cc8b89d55a7b184cfe44e76b306111b0d6b96feab6d8a1ed4684996b0002。

## 数值筛选：原始固定gain、相同工况

|条件|20–250Hz功率变化，全部7锚点+3窗口|250–1000Hz功率变化|结果|
|---|---|---|---|
|R相对B0|+4.372至+5.511dB|+1.205至+3.011dB|低频≥+3dB门通过|
|SR相对B0|+4.374至+6.577dB|+1.446至+3.025dB|低频≤+8dB、中频≥−1dB门通过|
|SR2相对B0|+4.383至+7.652dB|+1.725至+3.480dB|同门通过|

三个固定驾驶窗口为15.08–17.94、23.66–28.42、68.12–72.36秒。两声道分别验证后再按功率平均（输出仍为mono复制，非独立空间声道）。高转速四阶可超过250Hz，另测0.5/1/1.5/2/4/5/7/8/11/22/44阶。

实际机械包络相对于source双bank合并信号的4阶调幅：S **3.2969%**，S2 **9.8909%**。短工况实际waveform满足before×multiplier=after，独立逆DC的模型源压力差分残差最高约1.44e−14，证明这项调制实际进入输出。这是调制/声层因果证明，不能推出机械感更真实或Jovi偏好；原少数阶次机械源与共同RMS归一化的限制仍存在。

![实际同工况频谱](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/actual-frequency-comparison.png)

## 实际仿真与数据验证

完成B0、S、R、SR、SR-repeat、S2、SR2、SR2-repeat共8次90秒；另有7个机械分项短轨、7锚点×6版本共42个6秒稳态，57份唯一运行回执。每份长轨4,500帧、最后起点89.98秒、4,320,000×2样本、48kHz。状态直接读取旧B原生MATdouble，实际输入与独立模型时钟一致。

B0原始PCM SHA与旧B完全相等：1a56b2f54ce3149a15d184c80257f1a838ddee83fd0ff193318d791b4dc396ef。SR和SR2各自同MATLAB会话两次PCM/WAV哈希完全相同。SR2 PCM SHA 0e6fe3065b5e855f6d9dba7ff6507bc49a541d1937f4be4f5784812e5fbacbcb；WAV SHA b5df011381373205fe0c949212af5462f278566dbca9b78cc8882a2b0c3c0f94。

- 父任务MATLAB27/27，Python24/24；数字与研究筛选无失败；失败尝试原样保留，没有调参或改门。
- 冷重载、更新图、活动编译、model_check通过；运行表达式、38个依赖及模型/合同SHA绑定实际回执。
- Frozen存在初始化额外一次t0调用；短轨记录全部真实时刻为[0;实际时钟]。父任务额外读取全部8×4500原生PCM帧和二进制导出，所有辐射帧与顺序Frozen计算精确相同，最大误差0。此结论不只依赖调用次数。
- 8份原始输出最大samplepeak0.0547836121，最高真峰值−25.2dBTP；现有连续性门和PCM24独立读回通过。原始pre-Frozen压力允许超过1，不错套最终PCM±1门。
- 69个试听原件均实际测得−23.0LUFS；最高真峰值−4.6dBTP，低于预定−1.5；独立从RAW×固定标量复算，PCM24最大误差5.96e−8。
- 604个原模型/声库/profile/Android/Frozen保护SHA全部不变，7份旧listening文件不变；唯一已有common源码变化为本次获批source helper。原0.1 renderer gain保持。

完整证据：[analysis.json](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/runs/full-20261029-092429-542/analysis.json) / [分析摘要](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/runs/full-20261029-092429-542/analysis-summary.json) / [实际运行汇总](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/runs/full-20261029-092429-542/run-summary.json) / [原生帧与Frozen独立复核](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/native-frame-frozen-verification.json) / [试听独立验证](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/audition-full-20261029-092429-542/audition-verification.json) / [保护项验证](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/final-integrity.json)。

此次完成授权范围内的声源/传播试验、实际仿真和匹配试听交付。Jovi对新候选尚未评价；旧C拒绝保留。完整FVM/PTR物理网络、同步实车标定、OEM/设备/道路资格未通过。改动留在隔离工作树，未提交/合并/发布。Hub被工作树身份校验拒绝，未发送、无自动重试，记录见hub-NOT-SENDABLE.json。

最终审核：[Codex with ChatGPT](E:/Tesla_speed/worktrees/hellcat-state-contract-20261027/reports/app8-rumble-mechanics-candidate-20261029/C2C-REVIEW.md)返回DONE；GPT-6.1 sol high独立工程/实际数据复核通过。
