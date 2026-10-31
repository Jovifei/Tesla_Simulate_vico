from pathlib import Path
import json, datetime, hashlib

root = Path(r'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\reports\app8-cabin-mechanical-bank-candidate-20261030\startup-diagnostic')
invocations = [
('01-nojvm-batch','--nojvm'),
('02-jvm-batch',''),
('03-jvm-batch-nofigures','--no-figures'),
('04-desktop-r','--mode desktop'),
('05-batch-isolated-appdata','--isolate-appdata'),
('06-batch-isolated-localappdata','--isolate-localappdata'),
('07-batch-shadow-startup','--shadow-startup'),
('08-batch-empty-workdir','--case-workdir'),
('09-batch-startup-addpath','--startup-addpath'),
('10-batch-startup-init','--startup-init'),
('11-batch-addpath-repeat','--startup-addpath'),
('12-batch-simulink-smoke','--startup-addpath --simulink-smoke --timeout 60'),
('13-desktop-simulink-smoke','--mode desktop --startup-addpath --simulink-smoke --timeout 60'),
('14-batch-smoke-isolated-userprofile','--shadow-startup --isolate-userprofile --simulink-smoke --timeout 45'),
('15-batch-smoke-isolated-userprofile','--shadow-startup --isolate-userprofile --simulink-smoke --timeout 45'),
('16-desktop-smoke-close','--mode desktop --startup-addpath --simulink-smoke --timeout 90'),
('17-batch-addpath-delay','--startup-addpath --delay 15 --timeout 35'),
('18-batch-shadow-delay','--shadow-startup --delay 15 --timeout 35'),
('19-nojvm-shadow-delay','--nojvm --shadow-startup --delay 15 --timeout 35'),
]
markers=['DIAGNOSTIC_STARTUP_OVERRIDE','DIAGNOSTIC_STARTUP_ENTER','DIAGNOSTIC_ADDPATH_DONE','DIAGNOSTIC_INIT_ENTER','DIAGNOSTIC_INIT_DONE','MINIMAL_START','MINIMAL_DONE','SIMULINK_SMOKE_DONE','SIMULINK_CLOSE_BEGIN','SIMULINK_CLOSE_DONE','DIAGNOSTIC_DELAY_DONE']
entries=[]
for name, opts in invocations:
 p=root/name
 result=json.loads((p/'receipt.json').read_text(encoding='utf-8-sig'))
 result['wrapper_invocation']='python .\\run_case.py --case '+name+(' '+opts if opts else '')
 result['receipt_path']=str(p/'receipt.json')
 result['process_exit_interpretation']='forced termination after timeout; not a natural MATLAB exit' if result['timed_out'] else ('MATLAB launcher/process exit; inspect crash dump for underlying fault' if name=='16-desktop-smoke-close' else 'MATLAB process/launcher exit')
 result['log_markers']={}
 for log in ['stdout.log','stderr.log','matlab.log']:
  path=p/log
  if path.exists():
   data=path.read_text(encoding='utf-8',errors='replace')
   result['log_markers'][log]=[s for s in markers if s in data]
 if name.startswith('14-'):
  result['limitation']='Harness defect: --isolate-userprofile was accepted but no override was applied; USERPROFILE was original. This is not a user-profile isolation test.'
 if name.startswith('15-'):
  result['limitation']='USERPROFILE override was applied; MATLAB exited 1 with File system inconsistency before the expression, so this does not test the Home-service fault.'
 entries.append(result)
prior=json.loads((root/'nojvm-minimal-receipt.json').read_text(encoding='utf-8-sig'))
receipt={
 'schema':'matlab-startup-diagnostic-receipt-v1',
 'generated_local':datetime.datetime.now().astimezone().isoformat(),
 'agent':'matlab_startup_diagnosis',
 'working_directory':str(root),
 'scope':'Startup diagnosis; only diagnostic files were intentionally written inside this directory; no source/model/Android or original preferences were deliberately edited.',
 'status':'BLOCKED_NO_VERIFIED_STANDALONE_SIMULINK_FIX',
 'fault_observation':'R2026a native access violation; representative complete stacks identify homesessionmanager_impl.dll+00268967 with recent_artifacts_service_impl in the caller chain. Truncated dumps with same RIP do not independently establish the complete stack.',
 'root_cause_limit':'Deeper internal trigger and responsibility are unknown. The satk_initialize call can expose the timing-sensitive failure but is not established as the root cause: an empty startup and 15-second pause also crash.',
 'recommendation':'Preserve existing session and evidence; request MathWorks analysis. Do not treat quick batch success or the single desktop simulation marker as a verified standalone repair. Existing-session work is a separate, non-standalone evidence level.',
 'mcp_existing_session':{
  'tool':'mcp__matlab__evaluate_matlab_code',
  'command':"fprintf('PID=%d\\nROOT=%s\\nVERSION=%s\\nDESKTOP=%d\\nPREFDIR=%s\\nTEMPDIR=%s\\nJVM=%d\\nCWD=%s\\n',feature('getpid'),matlabroot,version,desktop('-inuse'),prefdir,tempdir,usejava('jvm'),pwd); fprintf('ENV_MATLAB_PREFDIR=%s\\nENV_TEMP=%s\\nENV_TMP=%s\\nENV_HOME=%s\\nENV_APPDATA=%s\\nENV_LOCALAPPDATA=%s\\n',getenv('MATLAB_PREFDIR'),getenv('TEMP'),getenv('TMP'),getenv('USERPROFILE'),getenv('APPDATA'),getenv('LOCALAPPDATA'));",
  'tool_result':'success; no process exit code because the existing session remained running',
  'observed':{'pid':218096,'version':'26.1.0.3203278 (R2026a)','desktop':True,'jvm':True,'matlabroot':r'D:\Program Files\MATLAB\R2026a','prefdir':r'C:\Users\Admin\AppData\Roaming\MathWorks\MATLAB\R2026a','tempdir':r'C:\Users\Admin\AppData\Local\Temp','cwd':r'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027'}
 },
 'inherited_evidence':{'description':'Previous agent independent -nojvm -batch check; not executed by this agent', 'receipt':str(root/'nojvm-minimal-receipt.json'),'matlab_exit_code':prior['exit_code'],'log':prior['log'],'crash_copy':str(root/'original-crash-dump.347200-1')},
 'cases':entries,
 'sources':['https://www.mathworks.com/help/matlab/ref/matlabwindows.html','https://www.mathworks.com/matlabcentral/answers/97167-why-will-matlab-not-start-up-properly-on-my-windows-based-system'],
 'notes':['Existing process working is not evidence standalone startup is fixed.','The 13 desktop timeout exit reflects the watchdog termination, not a natural exit.','The 14 isolation test had a harness defect; see per-case limitation.','SQLite PRAGMA integrity_check on the existing mwhome database returned ok; this alone cannot prove its contents or interaction are healthy.','MATLAB -batch disables setting changes; APPDATA and LOCALAPPDATA environment overrides alone may not redirect Windows known-folder resolution.']
}
(root/'diagnosis-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=[
'# MATLAB R2026a 独立启动诊断',
'',
'时间：2026-10-31（Asia/Shanghai）。范围：仅限此隔离诊断目录；不运行长仿真。',
'',
'**结论：尚无经过验证的独立 MATLAB/Simulink 修复。** 反复出现原生访问冲突，代表性完整栈位于 `mwhomesessionmanager_impl.dll+00268967`，调用链含 `mwrecent_artifacts_service_impl.dll`。这确定了故障位置，但不能确定二进制内部缺陷、数据或竞态的具体原因。',
'',
'现有 MCP 桌面会话 PID 218096 同版本可响应，使用正常系统偏好和 TEMP；其可用性不能证明新独立进程正常。原始 `startup.m` 调用 `satk_initialize` 时可在进入初始化后崩溃，但它**不是已证明的根因**：隔离 `startup.m` 只打印标记、不加工具路径，随后 `pause(15)` 仍崩溃（18、19）。此前短检查通过仅证明短程序能执行并退出，不证明更长工作负载安全。',
'',
'隔离短仿真：12 在 `MINIMAL_DONE` 后崩溃；13 的桌面进程打印 `SIMULINK_SMOKE_DONE samples=51`，但 60 秒内未自然退出，最终由 watchdog 终止；16 再次使用桌面模式在表达式前发生同 RIP 原生崩溃。不要把 13 标记为完整通过。测试 14 因测试脚本缺陷没有实际改变 USERPROFILE；15 修正后把 USERPROFILE 指向空目录，MATLAB 报 `File system inconsistency`、退出 1，未验证原故障。',
'',
'## 执行记录',
'',
'所有下列命令均在本目录运行。Python 启动器本身写回执后返回 0，表中的值是它捕获的 **MATLAB 启动器/进程** 退出码；所有运行均创建独立 `MATLAB_PREFDIR`、`TEMP`、`TMP`。每个目录的 `receipt.json` 和汇总 `diagnosis-receipt.json` 保存了实际 MATLAB 可执行文件、完整参数、表达式、工作目录、环境和绝对日志路径。`stdout.log` / `stderr.log` 均在该行目录下；桌面模式额外使用 `matlab.log`；崩溃转储在各自 `temp/`。',
'',
'| 实际启动器命令 | MATLAB 退出码 | 结果与证据 |',
'|---|---:|---|'
]
notes={
 '01':'空 pref/temp，-nojvm，表达式前崩溃', '02':'空 pref/temp，JVM，表达式前崩溃',
 '03':'禁用图窗仍崩溃，stderr 含完整 Home/最近文件服务栈',
 '04':'桌面模式最小表达式通过，正常退出；见 matlab.log',
 '05':'仅改 APPDATA，仍崩溃', '06':'仅改 LOCALAPPDATA，仍崩溃',
 '07':'隔离空 startup，快速最小表达式通过；不代表持久稳定',
 '08':'空工作目录，无覆盖 startup，崩溃',
 '09':'隔离 startup 仅 addpath，快速最小表达式通过',
 '10':'同 09 增加 satk_initialize，进入初始化后崩溃；不证明根因',
 '11':'09 快速检查复测通过',
 '12':'合成 0.01 秒模型：MINIMAL_DONE 后崩溃；未完成仿真',
 '13':'合成 0.01 秒模型有 51 个样本；超时后被终止，非自然退出，见 matlab.log',
 '14':'USERPROFILE 覆盖未实际生效（脚本缺陷）；崩溃，不能用于评估该变量',
 '15':'USERPROFILE 确实隔离；启动器报 File system inconsistency，非原故障复现',
 '16':'桌面模式再次运行，表达式前 native dump，退出 1',
 '17':'startup 仅 addpath + pause(15)：最小表达式后崩溃',
 '18':'startup 仅打印 + pause(15)：最小表达式后崩溃',
 '19':'18 关闭 JVM 后仍崩溃'
}
for item in entries:
 prefix=item['case'][:2]
 code=item['exit_hex']
 if item['timed_out']: code+='（超时强制终止）'
 lines.append('| `'+item['wrapper_invocation']+'` | `'+code+'` | '+notes[prefix]+'；日志：`'+item['case']+'/stdout.log`、`'+item['case']+'/stderr.log`'+('、`'+item['case']+'/matlab.log`' if (root/item['case']/'matlab.log').exists() else '')+' |')
lines += [
'',
'另有前一代理的 `-nojvm -batch` 隔离最小检查，MATLAB 有符号退出码 `-1073741819`（`0xC0000005`）；[原回执](nojvm-minimal-receipt.json)和[原日志](nojvm-minimal.log)为继承证据，未冒称由本代理执行。',
'',
'## 最小可回退建议与限制',
'',
'1. 不修改、删除或重命名原始偏好/历史文件；保留独立的失败日志、转储与回执。仅依靠独立 prefdir、TEMP、关闭 JVM/图窗、跳过初始化或桌面模式都没有证明可稳定执行独立仿真。',
'2. 对允许的短探索，可由主任务使用已有 MCP 会话，逐项记录实际成功或失败；它属于现有会话证据，不能替代独立进程证据。要执行任何完整仿真仍需针对其实际模型和运行条件验证。',
'3. 向 MathWorks 支持提供版本、案例 03/18/19 的最小复现、完整调用栈与回执，询问 Home session/recent artifacts 服务故障以及受支持的修复。转储可能含会话标识和本机路径，分享前由所有者审阅。数据库 `mwhomeartifacts_1.db` 的只读 `PRAGMA integrity_check` 为 `ok`，不代表数据或该服务一定无问题。',
'4. 如 MathWorks 给出受支持的补丁或配置，应先在独立、可回退环境复测 `pause(15)` 和合成短 Simulink，再验证目标隔离仿真，分别保留退出码；不能以快速启动或许可证检查代替。',
'',
'官方参考：[Windows 启动选项与 -wait](https://www.mathworks.com/help/matlab/ref/matlabwindows.html)、[MathWorks 启动问题排查](https://www.mathworks.com/matlabcentral/answers/97167-why-will-matlab-not-start-up-properly-on-my-windows-based-system)。',
'',
'完整机器回执：[diagnosis-receipt.json](diagnosis-receipt.json)。',
]
(root/'DIAGNOSIS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('WROTE',root/'DIAGNOSIS.md')
print('WROTE',root/'diagnosis-receipt.json')
print('CASES',len(entries))
for p in [root/'DIAGNOSIS.md',root/'diagnosis-receipt.json']:
 print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest(),p.name)

