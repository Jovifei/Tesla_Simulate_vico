# 隔离烟测阶段回执

时间：2026-10-31（Asia/Shanghai）

## 已完成

- 修复隔离包装器 `mb_smoke_step.m` 的 profile 边界：原始 JSON 先保留给 `mb_source_frame`，只从 `s12_v12_validate_source_profile` 读取 `firing_phases_deg`。
- 处理 Simulink 根 MATLAB Function 的初始化时序：R2026a 在首个外部输入样本前会以全零 packet 探测一次；该单次全零探测旁路，真实重复时间且内容变化仍 fail-closed。
- `test_smoke_wrapper.m`：4/4 passed，0 failed，0 incomplete。
- 创建新隔离模型：`isolated-model/cabin_smoke_candidate.slx`。原模型、声库、Android 和公共源码未修改。
- 新模型冷重载、Update Diagram、Active Compile、`model_check(["all"])` 通过；根输入为 `[9x1] double`。
- 使用 `timeseries` 外部输入实际运行 3 帧：`t=[0,0.02,0.04]`；输出 Dataset 元素数据尺寸 `[3,960]`，wrapper 评估次数 3，重复 0，时间序列一致，finite=1，峰值 `0.18898513524785776`。

## 失败和修正证据

1. `[time,9列]` 矩阵输入被 R2026a 拒绝，因为 `[9x1]` 根 Inport 要求标量列维度；未进入仿真。
2. 改成 `timeseries` 后暴露初始化全零 packet 与真实 t=0 packet 的重复时刻差异；wrapper 先增加诊断信息，再只放行全零初始化探针。
3. 首次成功运行后的回执读取把 `Dataset` 误当 double；改为读取 `getElement(1).Values.Data` 后，短仿真回执完整生成。

## 当前边界

这只是隔离函数 + 最小 Simulink 烟测，不是正式 source→Frozen Radiation→PCM 信号路径；尚未完成新正式 SLX、90 秒仿真、PCM/WAV、响度匹配或车内试听。独立 MATLAB `-batch` 仍受 R2026a 原生启动崩溃阻塞，现有 MCP/Desktop 会话证据与独立进程证据分开记录。
