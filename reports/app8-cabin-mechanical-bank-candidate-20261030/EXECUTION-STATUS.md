# 隔离车内声浪实验：中止状态

2026-10-30；工作树 `E:\Tesla_speed\worktrees\hellcat-state-contract-20261027`，HEAD `7acf3b564ff3d03ffd4be6d9f93a118cd3166d3f`。状态：**部分私有函数与单元测试已编写；MATLAB 批处理启动崩溃，停止模型和仿真**。这不是试听包或产品交付。

## 已执行

- 初始和最终分别对隔离目录外的 7,942 个常规文件、9,129,302,830 字节计算 SHA-256：0 读取错误，文件无增加、删除或内容变化。详见 `protected-integrity.json` 和两份哈希清单；Git diff 两次 SHA-256 均为 `8fce57e220c986a6bd3b3faff1c7233d7e45498054a537e51b3a11d1fbcfcf98`。
- 仅在本目录创建唯一命名的私有源/identity 副本、事件/模态和双 bank 网络函数以及对应的 MATLAB 单元测试。完整路径和 SHA-256 见 `LAB-MANIFEST.json`。代码未完成总体合同，不可用于交付。
- 连接原有 MATLAB MCP 会话，`version` 返回 R2026a `26.1.0.3203278`，`license('test','Simulink')` 返回 1。此结果只说明原有会话可响应，不证明新进程或模型可用。
- 先后通过 MCP `run_matlab_test_file` 运行 `test_cabin_paths.m` 和 `test_cabin_source.m`：初次分别为 0/5、0/4，失败断言为私有实现文件尚不存在；实现后分别为 **5/5、4/4**。覆盖的有限范围为单事件面积及 ZOH 参考、分数时刻和分帧、720°回绕/停转、散射能量及首次到达/反射、对称分帧，以及一帧中性源回归、归一化前移除、分量重构和换挡切扭、原机械 tap。测试详细输出保留在调用会话中，不是 Simulink 运行证据；尚未完成多帧源回归、全部状态和端到端测试。

## 崩溃与隔离复试

父任务告知其另一 MATLAB `-batch` 单元测试于 `2026-10-30 23:38:52 +0800` 发生 `0xc0000005`，源转储原路径 `C:\Users\Admin\AppData\Local\Temp\matlab_crash_dump.347200-1`；原文件 SHA-256 `c41b9f573979b8b174940812655112e5d41eb25e7bd05b43f90f77518dac1a83`，字节一致副本为 `startup-diagnostic/original-crash-dump.347200-1`。父任务的精确原始命令和完整标准输出由父任务记录，本文不猜测。

按父任务要求，只执行一次最小隔离启动复试；可复现入口 `diagnose_matlab_startup.ps1` 将 `MATLAB_PREFDIR`、`TEMP`、`TMP` 限定到本目录 `startup-diagnostic`，命令为：

```powershell
& 'D:\Program Files\MATLAB\R2026a\bin\matlab.exe' -nojvm -batch "fprintf('MINIMAL_START\n'); assert(2+2==4); fprintf('VERSION=%s\n',version); fprintf('SIMULINK_LICENSE=%d\n',license('test','Simulink')); disp('MINIMAL_DONE');"
```

结果：退出码 `-1073741819`，即 `0xc0000005` 访问冲突；`MINIMAL_START` 和 `MINIMAL_DONE` 均未出现。调用栈在 `mwhomesessionmanager_impl.dll`、`mwrecent_artifacts_service_impl.dll` 和 `libmwfoundation_threadpool.dll`；隔离偏好和 `-nojvm` 没有使此启动成功。精确实参、环境和退出码见 `startup-diagnostic/nojvm-minimal-receipt.json`，标准输出/错误见 `startup-diagnostic/nojvm-minimal.log`，新转储见 `startup-diagnostic/temp/matlab_crash_dump.337416-1`，SHA-256 `8a99e1d20aadc460a6ede71f21e44cf6a0d6a1938e921ab3f05698fd66cda07e`。

两次故障都在未见目标测试/最小语句输出前进入 MATLAB 自带服务栈，支持启动/运行环境问题的判断；无法单凭调用栈确定更深层根因或排除所有环境交互。原有 MCP 会话能运行前述函数级测试，与独立 `-batch` 崩溃是不同证据。原始转储和 MATLAB 自动生成的隔离 prefs 仅作本地诊断，可能含会话数据，不应上传至项目 hub。

## 未执行和下一步

- 未创建或编辑新 SLX；未运行 Cold Reload、Update Diagram、Active Compile、model_check 或任何新 Simulink 短仿真。
- 未进行一次数字电平标定、7 条 90 秒仿真或 35 条 6 秒锚点仿真；未生成 PCM、WAV、试听副本、模型截图或任何数字/声学/设备/人耳通过结论。
- 不要把私有函数的 9 项测试结果当作系统集成、模型、声学或人耳验收。待 MATLAB 批处理启动环境经诊断恢复，并在隔离路径完成最小启动和真实 Simulink 短验证后，才能按冻结计划继续；保留上述两次失败作为证据。是否恢复实验由父任务协调。
- 项目 hub、账本及公共文档在本子任务限定写入目录之外，由父任务按项目要求处理。
