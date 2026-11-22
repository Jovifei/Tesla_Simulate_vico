# PR #45 运行包装器失败即停修复

本地候选基于 `codex/v14-a-step1-win11-20261122`，起始 HEAD `840ef3123283af03e91934a2673394d73e11b2aa`。历史运行包装器位于 `E:\Tesla_speed\experiments\v14-local-handoff-20261122\step1-runbook-executed.ps1`，SHA-256 为 `da5c40a2e3619955bf3cc8c886ccb07eb9060f54666e82a6c3693347752c1459`，与现有 `host-receipt.json` 中的记录一致。`historical-step1-runbook.fixture.txt` 是同一字节的测试副本，使新检出环境可以核对来源并复跑模拟。历史文件第 52、55、59、62 行保存了 configure、build、smoke、verify 的原生退出码，但没有在非零时停止。冻结 `HOST-RUNBOOK.md` 的对应错误检查和错误文字是此修复的来源。

候选 `step1-runbook-guarded.ps1` 独立保存在本目录，SHA-256 为 `a71a852e53885a8af50cf53e8d5b9160a9744c488bcab5db5355f5478d976c62`。它沿用历史包装器的调用约定，在上述四处赋值后各增加一条非零即抛错的检查。`historical-to-candidate.diff` 只含四行新增。检查失败时会离开四阶段区段，外层失败处理不应记录成功。

本次触达范围为候选副本、历史测试副本、四行 diff、mock 脚本和新建 mock 证据。局部 `.gitattributes` 保护来源和测试文件的字节身份。已在候选报告目录与冻结包内搜索，未找到现成调用历史包装器的脚本。原冻结包、配置、导出接口及既有回执均未更改。候选副本依赖原包装环境提供的 `TaskFixed*` 路径和 `TaskStage`，尚未作为独立入口集成到实际主机流程。

## 对照结果

2026-11-23 最终复核命令 `python -B reports/v14-direction-a-win11-20261122/fail-fast-repair/test_fail_fast.py --run-id review-20261123-v3` 的进程退出码为 0。每一组均先生成完全相同的假旧 configure 文件、假可执行文件、假采集文件和假 PASS 文件，再分别运行一次旧、新包装器。四个调用点均被替换为独立 PowerShell mock 子进程，分别返回 31、32、33、34。真实 engine-sim、构建器、原生采集和原校验器均未运行。测试还包含一组所有 mock 阶段返回 0 的对照。

| 注入失败及真实 mock 退出码 | 旧包装器进程退出码 / 失败后的行为 | 候选包装器进程退出码 / 失败后的行为 |
| --- | --- | --- |
| configure 31 | 0；继续 build、smoke、verify。build 读取假旧 configure 文件，模拟外层记录成功。 | 1；立即停止，未读取假旧产物，未生成模拟成功回执。 |
| build 32 | 0；继续 smoke、verify。计算假旧可执行文件的哈希，并由 mock smoke 读取该假旧文件，模拟外层记录成功。 | 1；立即停止，未读取假旧产物，未生成模拟成功回执。 |
| smoke 33 | 0；继续 verify。mock verify 读取假旧采集文件，模拟外层记录成功。 | 1；立即停止，未读取假旧产物，未生成模拟成功回执。 |
| verify 34 | 0；没有后续阶段，但假旧 PASS 文件仍在，外层模拟逻辑仍记录成功。该案例**没有声称旧包装器读取了假 PASS 文件**。 | 1；立即停止。假旧 PASS 文件仍保留，但未生成模拟成功回执。 |
| 无失败 | 0；四个 mock 均返回 0，模拟成功。 | 0；四个 mock 均返回 0，模拟成功。 |

`mock-runs/review-20261123-v3/mock-result.json` 包含每个外层 PowerShell 进程的完整命令和实际进程退出码、每个已执行 mock 的退出码、后续阶段、假制品读取事件、初始假制品与日志哈希，以及本次执行的脚本哈希和各案例事件。Windows junction 负例分别对 mock 驱动和 mock 阶段返回非零，链接指向的测试目录中没有创建文件。之前的 `mock-runs/fixture-v1/mock-result.json` 保留第一次完整对照的记录，其逐案例原日志仅保留在本机。

测试首先以历史 fixture 的 SHA 和原主机回执复核来源，然后从旧版和候选版各提取同一段四阶段代码，并只替换四条外部命令。`Get-FileHash` 对假可执行文件的读取也记录到事件中。成功回执是 mock 外层专用文件，用来复现历史外层的成功判定，未触及历史回执。验证针对中段保护，原 HOST-RUNBOOK 整体要求输出目录在开始前不存在。

第一次启动测试脚本在任何 mock 案例运行前退出 1，原因是历史文件混用了 LF 和 CRLF。已修正为逐处保留原换行，详见 `preflight-01.txt`。复跑时可提供此前未使用的 `--run-id`，或省略该参数自动生成新编号。`duplicate-run-check-final3.json` 记录了重复编号被拒绝且原结果哈希不变。另将所需文件复制到本工作树的全新目录，十个 mock 对照和 junction 负例再次通过，见 `portable-reproduction-final3.json`。

实际 HOST-RUNBOOK 集成运行、真实 MSVC 构建、engine-sim smoke、声音渲染及试听在本次修复验证中均 `NOT_RUN`。
