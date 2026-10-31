# 隔离车内候选复核纠正与续接

2026-10-31，Jovi 已授权按既定隔离方案继续修复，执行为 GPT-6.1 Terra max。此记录优先于此前 FORMAL-RESULT、run-summary 中的完成措辞；旧文件与音频保留。

## 当前判定

`formal-long-20261031-005916-982` 是真实产生了七条音频的探索运行，文件级 PCM/WAV 安全检查成立，但**不符合批准实验，不能标记方案完成或机械感改善**。原批准方案仍为 `E:/Tesla_speed/reports/app8-mechanical-bank-research-20261030/C2C-APPROVAL-PLAN.md`。

## 已核实的偏差与修复方向

1. `run_formal_long.m` 没有加载旧 B 的原生 `capture.mat/actualState`，而用了原模型内置 cycle；本次 B0 SHA 为 `2e809bf2…`，批准的旧 B 为 `1a56b2f5…`。两者工况和 source 选项不同。续接必须绑定原生 B double、实际输入与独立 Clock，并逐 PCM 核验 B0。
2. `mb_formal_source_bank_modal_step.m` 的 N/M 绕过网络；D/MD 把全部混合 banks 送入网络；模态加在 Frozen 前且未校准。续接只将切扭后的 combustion 两列送入相同网络，N/M 先平均复制、D/MD 保留差异；机械经一次预登记 RMS 校准后，通过新 SLX 可见支路在 Frozen 后、renderer 前 Sum。
3. 磁盘正式 SLX 与原模型的 ZIP 成员仅 windowsInfo 有差异，没有保存 Selector 或新 Sum。旧 formal-short-result 的三帧与该次 B0 前三帧完全相同，不能证明最终 MD 路径。续接先保存新模型，再冷重载并独立检查 ZIP/表达式/连接，然后以最终源码 SHA 做真实短仿真。
4. 日志配置名为 formal_logs，读取时却查 logsout 并容忍缺失，因此缺少控制、各路径和 Frozen 实际捕获。续接按 cabin_logs 显式读取，缺项即失败；顺序重算与运行计数不能用元数据替代。
5. 旧 MD-cold 仅关模型重载，仍为同一 MATLAB 进程。续接必须记录独立新 MATLAB PID；否则保持 NOT_RUN。35 条锚点和一次机械电平校准尚未完成。
6. M−N 与 MD−D 的原始输出差值 RMS 约 1.6314e−7（−135.75 dBFS），不足以支持已改善机械感的说法。已有音频可作诊断试听，不能宣传为修复后的批准候选。

## 可直接听到的现有文件

旧试听写在同级 20261031 目录，超出批准的唯一研究目录；现已将原音频字节一致复制到本目录 `audition-formal-20261031/named/whole_tracks/`，原件保留。已独立解码真实 PCM24 并与 RAW×固定标量对比，最大误差 5.96e−8；实测均为 −23 LUFS。B0/MD 的 12–24 秒片段在 `audition-formal-20261031/diagnostic-excerpts/`。这些文件明确标记 DIAGNOSTIC_ONLY_PLAN_DEVIATION，不代表新合格声路。

## 并行续接与边界

- 启动恢复代理独占独立启动探针；现有 MATLAB Desktop/MCP 不终止。原生崩溃位置仍为 Home/recent-artifacts 服务，内部根因尚未确定，不能认定 satk 是唯一根因。
- 实施代理只在本候选目录补齐已批准的合同、源码和模型；运行前等待启动调查释放 MATLAB 资源。普通集成错误在此范围内修复，冻结参数或数值安全失败不得调参掩盖。
- 父任务负责远端复核、文档/账本与 Obsidian；原 SLX、声库、Android、公共源码和 Frozen 不修改。车内设备试听与 Jovi 的人耳接受均待实际发生。
- C2C 应用已实际返回 Tesla_speed/645b71a7e91b；根工作区是非 Git 目录，审阅源码必须用 `worktrees/hellcat-state-contract-20261027/...` 精确路径，不能靠根 git_diff 空结果判断无变更。
