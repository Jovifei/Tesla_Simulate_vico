# 冻结HY1实际Kotlin后验验证 · 2026-10-02

仅验证既有冻结参数，不拟合、不改增益、不改seed。profile.bin SHA256=3891836e55069d64392d84bee268e8974ba89558fa31f9c23ec95c375c65f294。通过opt-in C63FrozenHybridValidationTest加载本地二进制。

## 实際输出

- 16个稳态RPM/load组合、1条driven ramp、1条四次收油事件轨迹；每项T/S/E/SE与SE-event-off，共90组真实Kotlin PCM输出。
- 单独E-event-off与T-event-off逐样本一致性通过，证明事件关闭保持基线主体；paired event对照使用同一输入。
- 现有数字峰值合同0.8413951416451951：90组均通过，最大0.6236417365。此结果不覆盖全部333+297、新seed/phase状态矩阵，不称完整数字资格。
- 持续声calibration：低频绝对变化median0.036340937dB、p90 0.871912428dB；中频最大+1.468181685dB，超过1dB，FAIL。
- 持续声分布距离T=3.689243619、S=1.972351110；aggregate improvement不能替代频带保护，仍FAIL。
- 事件：实际Kotlin E减同输入E-off；与同occurrence旧E2响应counterfactual比较。D_baseline=2.022749667，D_actual=1.858305439，改善8.129737%，低于20%，FAIL。
- 69个已知impulse frames，matched27，false peaks2，censored9。Reference为本地R2/unverified calibration窗口，未做held-out/OEM/人耳验收。

现有拟合代理的两项失败被实际Kotlin输出复现，未发生隐式profile重置。HY1不可启用/安装。当前手机基线诊断是AH，不是此失败候选。

## 可复验命令

在vico_app/Project/android设置VICO_C63_FROZEN_HY1_PROFILE为既有本地profile.bin，VICO_C63_FROZEN_HY1_VALIDATION为不存在的新输出目录，运行gradlew.bat :app:testDebugUnitTest --tests '*C63FrozenHybridValidationTest.exportActualFrozenFourBranchesAndEventOff' --offline --console=plain。

同一profile、VICO_C63_FROZEN_HY1_PAIR_OUTPUT指向不存在的新目录，运行--tests '*C63FrozenHybridValidationTest.exportFrozenEventOffControls'。两个focused执行都实际BUILD SUCCESSFUL；输出不得覆盖旧run。

测量使用既有build_c63_hybrid_targets.features与fit_c63_hybrid.event_descriptors/event_distance，不改目标/参考/门槛。记录本地E:/Claude_allow/Download/vico-frozen-hy1-kotlin-20261002-1819/actual-kotlin*.json和tsv；paired PCM在vico-frozen-hy1-event-pairs-20261002-1823。原始参考和PCM不上传GitHub。

下一步远端新N2必须解决hard feasibility与事件分布限制，再由本地跑实际参考计算。不能用这90组calibration数字检查替代held-out或生产资格。
