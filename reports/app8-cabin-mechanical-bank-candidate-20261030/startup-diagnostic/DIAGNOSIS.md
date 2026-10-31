# MATLAB R2026a 独立启动诊断

时间：2026-10-31（Asia/Shanghai）。范围：仅限此隔离诊断目录；不运行长仿真。

**结论：尚无经过验证的独立 MATLAB/Simulink 修复。** 反复出现原生访问冲突，代表性完整栈位于 `mwhomesessionmanager_impl.dll+00268967`，调用链含 `mwrecent_artifacts_service_impl.dll`。这确定了故障位置，但不能确定二进制内部缺陷、数据或竞态的具体原因。

现有 MCP 桌面会话 PID 218096 同版本可响应，使用正常系统偏好和 TEMP；其可用性不能证明新独立进程正常。原始 `startup.m` 调用 `satk_initialize` 时可在进入初始化后崩溃，但它**不是已证明的根因**：隔离 `startup.m` 只打印标记、不加工具路径，随后 `pause(15)` 仍崩溃（18、19）。此前短检查通过仅证明短程序能执行并退出，不证明更长工作负载安全。

隔离短仿真：12 在 `MINIMAL_DONE` 后崩溃；13 的桌面进程打印 `SIMULINK_SMOKE_DONE samples=51`，但 60 秒内未自然退出，最终由 watchdog 终止；16 再次使用桌面模式在表达式前发生同 RIP 原生崩溃。不要把 13 标记为完整通过。测试 14 因测试脚本缺陷没有实际改变 USERPROFILE；15 修正后把 USERPROFILE 指向空目录，MATLAB 报 `File system inconsistency`、退出 1，未验证原故障。

## 执行记录

所有下列命令均在本目录运行。Python 启动器本身写回执后返回 0，表中的值是它捕获的 **MATLAB 启动器/进程** 退出码；所有运行均创建独立 `MATLAB_PREFDIR`、`TEMP`、`TMP`。每个目录的 `receipt.json` 和汇总 `diagnosis-receipt.json` 保存了实际 MATLAB 可执行文件、完整参数、表达式、工作目录、环境和绝对日志路径。`stdout.log` / `stderr.log` 均在该行目录下；桌面模式额外使用 `matlab.log`；崩溃转储在各自 `temp/`。

| 实际启动器命令 | MATLAB 退出码 | 结果与证据 |
|---|---:|---|
| `python .\run_case.py --case 01-nojvm-batch --nojvm` | `0xC0000005` | 空 pref/temp，-nojvm，表达式前崩溃；日志：`01-nojvm-batch/stdout.log`、`01-nojvm-batch/stderr.log` |
| `python .\run_case.py --case 02-jvm-batch` | `0xC0000005` | 空 pref/temp，JVM，表达式前崩溃；日志：`02-jvm-batch/stdout.log`、`02-jvm-batch/stderr.log` |
| `python .\run_case.py --case 03-jvm-batch-nofigures --no-figures` | `0xC0000005` | 禁用图窗仍崩溃，stderr 含完整 Home/最近文件服务栈；日志：`03-jvm-batch-nofigures/stdout.log`、`03-jvm-batch-nofigures/stderr.log` |
| `python .\run_case.py --case 04-desktop-r --mode desktop` | `0x00000000` | 桌面模式最小表达式通过，正常退出；见 matlab.log；日志：`04-desktop-r/stdout.log`、`04-desktop-r/stderr.log`、`04-desktop-r/matlab.log` |
| `python .\run_case.py --case 05-batch-isolated-appdata --isolate-appdata` | `0xC0000005` | 仅改 APPDATA，仍崩溃；日志：`05-batch-isolated-appdata/stdout.log`、`05-batch-isolated-appdata/stderr.log` |
| `python .\run_case.py --case 06-batch-isolated-localappdata --isolate-localappdata` | `0xC0000005` | 仅改 LOCALAPPDATA，仍崩溃；日志：`06-batch-isolated-localappdata/stdout.log`、`06-batch-isolated-localappdata/stderr.log` |
| `python .\run_case.py --case 07-batch-shadow-startup --shadow-startup` | `0x00000000` | 隔离空 startup，快速最小表达式通过；不代表持久稳定；日志：`07-batch-shadow-startup/stdout.log`、`07-batch-shadow-startup/stderr.log` |
| `python .\run_case.py --case 08-batch-empty-workdir --case-workdir` | `0xC0000005` | 空工作目录，无覆盖 startup，崩溃；日志：`08-batch-empty-workdir/stdout.log`、`08-batch-empty-workdir/stderr.log` |
| `python .\run_case.py --case 09-batch-startup-addpath --startup-addpath` | `0x00000000` | 隔离 startup 仅 addpath，快速最小表达式通过；日志：`09-batch-startup-addpath/stdout.log`、`09-batch-startup-addpath/stderr.log` |
| `python .\run_case.py --case 10-batch-startup-init --startup-init` | `0xC0000005` | 同 09 增加 satk_initialize，进入初始化后崩溃；不证明根因；日志：`10-batch-startup-init/stdout.log`、`10-batch-startup-init/stderr.log` |
| `python .\run_case.py --case 11-batch-addpath-repeat --startup-addpath` | `0x00000000` | 09 快速检查复测通过；日志：`11-batch-addpath-repeat/stdout.log`、`11-batch-addpath-repeat/stderr.log` |
| `python .\run_case.py --case 12-batch-simulink-smoke --startup-addpath --simulink-smoke --timeout 60` | `0xC0000005` | 合成 0.01 秒模型：MINIMAL_DONE 后崩溃；未完成仿真；日志：`12-batch-simulink-smoke/stdout.log`、`12-batch-simulink-smoke/stderr.log` |
| `python .\run_case.py --case 13-desktop-simulink-smoke --mode desktop --startup-addpath --simulink-smoke --timeout 60` | `0x00000001（超时强制终止）` | 合成 0.01 秒模型有 51 个样本；超时后被终止，非自然退出，见 matlab.log；日志：`13-desktop-simulink-smoke/stdout.log`、`13-desktop-simulink-smoke/stderr.log`、`13-desktop-simulink-smoke/matlab.log` |
| `python .\run_case.py --case 14-batch-smoke-isolated-userprofile --shadow-startup --isolate-userprofile --simulink-smoke --timeout 45` | `0xC0000005` | USERPROFILE 覆盖未实际生效（脚本缺陷）；崩溃，不能用于评估该变量；日志：`14-batch-smoke-isolated-userprofile/stdout.log`、`14-batch-smoke-isolated-userprofile/stderr.log` |
| `python .\run_case.py --case 15-batch-smoke-isolated-userprofile --shadow-startup --isolate-userprofile --simulink-smoke --timeout 45` | `0x00000001` | USERPROFILE 确实隔离；启动器报 File system inconsistency，非原故障复现；日志：`15-batch-smoke-isolated-userprofile/stdout.log`、`15-batch-smoke-isolated-userprofile/stderr.log` |
| `python .\run_case.py --case 16-desktop-smoke-close --mode desktop --startup-addpath --simulink-smoke --timeout 90` | `0x00000001` | 桌面模式再次运行，表达式前 native dump，退出 1；日志：`16-desktop-smoke-close/stdout.log`、`16-desktop-smoke-close/stderr.log`、`16-desktop-smoke-close/matlab.log` |
| `python .\run_case.py --case 17-batch-addpath-delay --startup-addpath --delay 15 --timeout 35` | `0xC0000005` | startup 仅 addpath + pause(15)：最小表达式后崩溃；日志：`17-batch-addpath-delay/stdout.log`、`17-batch-addpath-delay/stderr.log` |
| `python .\run_case.py --case 18-batch-shadow-delay --shadow-startup --delay 15 --timeout 35` | `0xC0000005` | startup 仅打印 + pause(15)：最小表达式后崩溃；日志：`18-batch-shadow-delay/stdout.log`、`18-batch-shadow-delay/stderr.log` |
| `python .\run_case.py --case 19-nojvm-shadow-delay --nojvm --shadow-startup --delay 15 --timeout 35` | `0xC0000005` | 18 关闭 JVM 后仍崩溃；日志：`19-nojvm-shadow-delay/stdout.log`、`19-nojvm-shadow-delay/stderr.log` |

另有前一代理的 `-nojvm -batch` 隔离最小检查，MATLAB 有符号退出码 `-1073741819`（`0xC0000005`）；[原回执](nojvm-minimal-receipt.json)和[原日志](nojvm-minimal.log)为继承证据，未冒称由本代理执行。

## 最小可回退建议与限制

1. 不修改、删除或重命名原始偏好/历史文件；保留独立的失败日志、转储与回执。仅依靠独立 prefdir、TEMP、关闭 JVM/图窗、跳过初始化或桌面模式都没有证明可稳定执行独立仿真。
2. 对允许的短探索，可由主任务使用已有 MCP 会话，逐项记录实际成功或失败；它属于现有会话证据，不能替代独立进程证据。要执行任何完整仿真仍需针对其实际模型和运行条件验证。
3. 向 MathWorks 支持提供版本、案例 03/18/19 的最小复现、完整调用栈与回执，询问 Home session/recent artifacts 服务故障以及受支持的修复。转储可能含会话标识和本机路径，分享前由所有者审阅。数据库 `mwhomeartifacts_1.db` 的只读 `PRAGMA integrity_check` 为 `ok`，不代表数据或该服务一定无问题。
4. 如 MathWorks 给出受支持的补丁或配置，应先在独立、可回退环境复测 `pause(15)` 和合成短 Simulink，再验证目标隔离仿真，分别保留退出码；不能以快速启动或许可证检查代替。

官方参考：[Windows 启动选项与 -wait](https://www.mathworks.com/help/matlab/ref/matlabwindows.html)、[MathWorks 启动问题排查](https://www.mathworks.com/matlabcentral/answers/97167-why-will-matlab-not-start-up-properly-on-my-windows-based-system)。

完整机器回执：[diagnosis-receipt.json](diagnosis-receipt.json)。
