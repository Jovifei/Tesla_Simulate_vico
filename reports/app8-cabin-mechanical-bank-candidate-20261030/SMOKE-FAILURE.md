# 最小 Simulink 烟测：失败并停止

2026-10-31；实际工作树 `E:\Tesla_speed\worktrees\hellcat-state-contract-20261027`。状态：**STOPPED_ON_UNEXPECTED_TEST_FAILURE**。

为最小模型新增 `test_smoke_wrapper.m` 与唯一命名的 `mb_smoke_step.m`，其目标是通过源/identity、机械事件模态、双 bank 运行一个仅用于环境检测的诊断帧。初次运行 4 个测试均按预期因包装器不存在而失败；首次实现后 4 个测试均因 `MATLAB:nonExistentField` 而失败，错误点 `mb_smoke_step.m:38`，提示无法识别 `firing_phases_deg`。

只读定位显示：原始 profile 的字段位于 `source.firing_phases_deg.value`；`s12_v12_validate_source_profile` 输出已展开的 `firing_phases_deg`。包装器将原始 JSON 当作展开后的结构读取。当前代码仍有该错误，未修复、未重跑，遵循遇到问题就停止的指令。

证据限制：MATLAB MCP 工具直接返回了两次测试的完整结果，但在本会话中 `diary` 生成的 `smoke-wrapper-red.log` 与 `smoke-wrapper-green.log` 都是 **0 字节**；不得把这两个空文件当作原始日志。`smoke-test-transcription.json` 是根据该工具返回人工转录的测试名称、计数与错误，明确标注了来源。

截至停止时：**未创建或编辑 SLX，未做 Cold Reload、Update Diagram、Active Compile、model_check 或任何 Simulink 仿真，未生成 PCM/WAV。** 当前 MCP 会话能执行测试，但本次没有使用或验证父任务提及的 isolated startup shadow。

初末各对隔离目录以外 7,942 个工作树常规文件、9,129,302,830 字节做 SHA-256 检查，无读取错误、无新增/删除/修改；见 `smoke-protected-integrity.json` 及 `resume-initial-protected-sha256.json`、`resume-final-protected-sha256.json`。未修改用户 startup、原模型、声库、Android 或公共源代码。

下一步：等待父任务决定是否允许修复包装器字段绑定，并在保持既有失败证据的前提下重跑单测；单测成功后才开始最小模型的全部门禁。诊断模型和它的合成帧不会证明正式信号路径、数字安全、设备或人耳资格。
