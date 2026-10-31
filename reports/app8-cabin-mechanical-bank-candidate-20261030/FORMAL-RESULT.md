# Formal isolated SLX execution result

时间：2026-10-31（Asia/Shanghai）

## 模型与接线

- 副本：`isolated-model/S12_hellcat_cabin_formal_candidate.slx`
- 原始副本初始 SHA-256：`71f8b9899688278e908e244649331352d43c46779e6fd93c0903f86785198a9c`；复制前后源模型字节一致。
- 仅修改隔离副本 `blk_11` 的 MATLAB Function 表达式为 `mb_formal_source_bank_modal_step(u, 'MD')`。
- 隔离 wrapper 调用 `mb_source_frame`、`mb_bank_network_frame`、`mb_event_modal_frame`；Frozen Radiation Adapter、Renderer Gain=0.1、Stereo Renderer 保留在副本原链路。
- 原模型、声库、Android、Frozen 文件和公共源码未修改。

## 门禁与实测

- `model_check(["all"])`：healthy。
- Cold Reload、Update Diagram、Active Compile：通过。
- 0.04 s 实际 Simulink 运行：3 个时间点 `[0, 0.02, 0.04]`。
- PCM Dataset：`[960, 2, 3]`，finite=1，峰值 `0.022595687370885784`。
- 新输入桥使用 9x1 native state packet；首个全零初始化探针只在隔离 wrapper 中旁路，真实重复时间改包仍 fail-closed。

## 失败与边界

- 独立 `-batch` 仍被 R2026a 原生 Home/recent-artifacts 服务崩溃阻塞；本结果来自现有 MCP/Desktop 会话。
- 短仿真证明 source→candidate wrapper→Frozen→stereo PCM 的结构和运行链路，不证明 90 秒、PCM24/WAV、响度、人耳、设备或 OEM 资格。
- B0 未在本次副本中重写，必须继续引用历史原模型结果；N/M/D/MD 仍需按相同原生控制生成长轨。
