# C63高转声库：两条离线候选均拒绝

门槛时序说明：执行者报告在本轮先约定门槛后运行持出；归档没有结果生成前的合同SHA/独立时间锚，独立审查无法由当前归档证明该时序。这里不能声称正式预注册。各失败门保持原数值，未因结果不利而放宽。

本轮基线为955b1355839f4b233e56c9ec9213fb86ae1927a6。没有修改已安装normal bank、Python S12权威source、reference emitter、事件素材或增益。两个候选都没有进入产品，也不具备安装资格。

## 已证实

1. 当前Python recipe逐float32重建原C63全部16个loop。load=.92时5500→6800RPM，source RMS下降13.4773dB，导出bank下降15.8605dB。端点没有RPM层混音，因此这部分下降不能归因于层间相消。固定共振器与事件压力RPM补偿都在原source中；当前数据支持source/传递链主导该端点差异。
2. 实际Kotlin renderer的6950RPM/.32、10秒测试中，lower/upper相关系数−.6457，相对同权重端点RMS上包络，混音下降7.5167dB，最差500ms下降8.8582dB。此上包络只是相消诊断基准，不是真实发动机目标响度。
3. 原source有两个不同的窄共振区域：5500RPM的第三点火谐波落1100Hz，6150RPM的第二谐波落820Hz。新增source探针保留固定gain，6150/.92的preroll loop RMS=.35737、峰=.60271，原粗grid没有该锚点。这个缺口可以解释为什么只修一处频带会遗漏另一处，但不是完整车型真实度结论。

## 候选A：高转相位登记，拒绝

只轮转6800/7200的四个现有loop，不改变样本集合、RMS、峰、离散傅里叶幅谱或loop长度。偏移由源裁剪时间计算，最终为789/1118样本，避开旧exporter前384样本crossfade。早期全域诊断在7200用318，落在旧crossfade中，不能作为严格源起相位；没有把那版诊断冒充最终候选。

全域轮转低转曾退化.639dB，所以被收窄；已审核低转四WAV保持。最终新持出10个RPM/load条件包含未用过的6830/6890/7020/7090/7170和.47/.77；完整160组实际renderer、每组30秒。严重相消组中位改善2.47374dB，未达约定的3dB门；worst500ms没有恶化，但这一项不能替代主门。与原S12的保护频带比较，6500/.32的250–1000Hz P90误差退化2.72215dB，超过.5门。峰=.661887，越界/硬削波/非有限均0，仍然拒绝。

相位候选30秒render尾部与4秒source的稳态窗口不是波形相位对齐，相关频带误差只作稳态幅度诊断；不得称sample级真值误差。相消主门独立失败，不依赖该配对窗口诊断。

## 候选B：5400/5600采样guard，拒绝

保护集新旧边界：5450/5550和5250/5750/6050/6250的.32/.92此前已出现于全域诊断，不能统称未见持出；.47/.77组合才是新组合。phase候选的十个RPM/load持出组合则未见于旧全域扫描。

借鉴仓库已有experiment_s13_c63_rpm_guard_bank.py的两个RPM及目标/保护门。原实验依赖的外部冻结包不可得，故没有声称重跑了原S13资格。这里是955现bank、原S12source、同gain的新隔离实验，并使用已审核的period-preserving preroll生成新增四loop；保留原16loop/低转overlay及全部事件。

5200/6100、两端load的1–4kHz目标误差改善10.7–12.6dB，严格改善窗口比例1.0；5500原anchor PCM逐bit相同。72组4秒实际renderer峰=.661887，坏计数0。但6100/.92整体RMS误差中位恶化7.8393dB，P90恶化8.2161dB；保护门失败。phase-blind中位误差同样恶化7.8507dB，说明不能靠重新对齐窗口解释掉。不能将“目标频段改善”包装成整声改善。

## 解释、假设和后续边界

“稀疏稳态整段压力loop的表示限制”是当前实验支持的根因解释：在测试条件下，单相位偏移和局部单峰采样均无法同时满足各频段保护。尚不能推广为所有bank方案必然失败，或断言真实用户听到的杂音唯一来自它。

后续两条路线保持研究比较：根据原模态的共振宽度设计局部采样/相位周期表示；复用既有S12连续激励/模态结构。必须首先评审新合同和源码范围，不能为过门调整gain/阈值、偷偷改权威reference或用更多已见数据当持出集。本轮不继续生成第三个产品候选。

人耳、道路、设备输出和实际车辆加速度没有由本轮离线测试证明。新REAL控制策略已装版本的验收属于另一份设备回执，不能合并为本轮声学完成。

## 复审入口

CONTRACT.md和GUARD_CONTRACT.md保存两个候选的合同与原阈值（时序证明限制见开头）；evidence/recipe-baseline.json绑定source与16loop；evidence/heldout-result.json、rpm-guards-result.json保留全部失败行；evidence/*-source-receipt.json绑定实际编译源；evidence/*-raw-files.json绑定全部输出。raw-evidence/保留原PCM，未从手机采音或读取私人轨迹。

脚本/执行harness目前按本任务隔离目录布局保存。重放依赖vico-drive-demand/work的精确955源及SHA固定JVM依赖；phase-replay-frozen和guards-replay-frozen分别保存实际执行版本，避免当前后续诊断harness覆盖历史。原始输出目录必须新建；不能覆盖已安装bank或旧证据。

工具标注更正：原始receipt继承baseline=c778字段和“REAL controller”旧说明；本轮实际执行harness直接构造恒定SoundState。源码hash/pins绑定955，旧字段不是本轮动态控制器验收。原始receipt保留不回写；r2复放工具明确source_commit=955与steady-renderer scope。

原始输出范围：raw-evidence中的每份PCM只保留该条件最后3秒；30秒整体与逐500ms相消值来自实际执行harness的统计及可复放代码，不能把尾部文件称为全部30秒录音。原始guard每条件4秒也只保留末3秒。

尚未执行：候选A合同中的动态ramp、REAL控制器带事件轨迹、全低转逐bit资格及设备/人耳门没有全部运行；因主门已失败而停止后续资格。160组恒速renderer测试不能替代这些动态验收。候选B也未进入后续事件/动态资格。

Archive packaging note: raw-evidence PCM and source-control PCM were retained for independent review but are not committed in this compact Git archive. Their hashes and recipes are included; run reproduce.py in a new directory to regenerate them. No failed WAV is added to app assets.
