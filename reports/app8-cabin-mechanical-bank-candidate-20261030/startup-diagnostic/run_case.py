import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(r'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\reports\app8-cabin-mechanical-bank-candidate-20261030\startup-diagnostic')
EXE = Path(r'D:\Program Files\MATLAB\R2026a\bin\matlab.exe')
p = argparse.ArgumentParser()
p.add_argument('--case', required=True)
p.add_argument('--mode', choices=['batch', 'desktop'], default='batch')
p.add_argument('--nojvm', action='store_true')
p.add_argument('--no-figures', action='store_true')
p.add_argument('--isolate-appdata', action='store_true')
p.add_argument('--isolate-localappdata', action='store_true')
p.add_argument('--isolate-userprofile', action='store_true')
p.add_argument('--shadow-startup', action='store_true')
p.add_argument('--case-workdir', action='store_true')
p.add_argument('--startup-addpath', action='store_true')
p.add_argument('--startup-init', action='store_true')
p.add_argument('--simulink-smoke', action='store_true')
p.add_argument('--delay', type=int, default=0)
p.add_argument('--timeout', type=int, default=45)
a = p.parse_args()
if not a.case.replace('-', '').isalnum():
    raise ValueError('case must be alphanumeric or hyphen')
case = ROOT / a.case
case.mkdir(exist_ok=False)
pref = case / 'prefdir'
tmp = case / 'temp'
pref.mkdir()
tmp.mkdir()
cwd = ROOT
if a.shadow_startup or a.case_workdir or a.startup_addpath or a.startup_init:
    cwd = case / 'working'
    cwd.mkdir()
if a.shadow_startup:
    (cwd / 'startup.m').write_text("disp('DIAGNOSTIC_STARTUP_OVERRIDE');" + chr(10), encoding='utf-8')
if a.startup_addpath or a.startup_init:
    startup = "disp('DIAGNOSTIC_STARTUP_ENTER'); toolkitRoot = fullfile(getenv('USERPROFILE'), '.matlab', 'agentic-toolkits', 'simulink'); if isfolder(toolkitRoot), addpath(toolkitRoot); disp('DIAGNOSTIC_ADDPATH_DONE'); "
    if a.startup_init:
        startup += "disp('DIAGNOSTIC_INIT_ENTER'); satk_initialize; disp('DIAGNOSTIC_INIT_DONE'); "
    startup += 'end;'
    (cwd / 'startup.m').write_text(startup + chr(10), encoding='utf-8')
env = os.environ.copy()
env.update(MATLAB_PREFDIR=str(pref), TEMP=str(tmp), TMP=str(tmp))
if a.isolate_userprofile:
    target = case / 'userprofile'
    target.mkdir()
    env['USERPROFILE'] = str(target)
if a.isolate_appdata:
    target = case / 'appdata'
    target.mkdir()
    env['APPDATA'] = str(target)
if a.isolate_localappdata:
    target = case / 'localappdata'
    target.mkdir()
    env['LOCALAPPDATA'] = str(target)
statement = "disp('MINIMAL_START'); assert(2+2==4); fprintf('VERSION=%s\\n',version); fprintf('SIMULINK_LICENSE=%d\\n',license('test','Simulink')); disp('MINIMAL_DONE');"
if a.simulink_smoke:
    statement += " m='startup_probe'; new_system(m); add_block('simulink/Sources/Constant',[m '/Constant']); add_block('simulink/Sinks/Terminator',[m '/Terminator']); add_line(m,'Constant/1','Terminator/1'); out=sim(m,'StopTime','0.01','ReturnWorkspaceOutputs','on'); assert(~isempty(out.tout)); fprintf('SIMULINK_SMOKE_DONE samples=%d\\n',numel(out.tout)); disp('SIMULINK_CLOSE_BEGIN'); close_system(m,0); disp('SIMULINK_CLOSE_DONE');"
if a.delay:
    statement += f" pause({a.delay}); disp('DIAGNOSTIC_DELAY_DONE');"
args = [str(EXE), '-wait']
if a.nojvm:
    args.append('-nojvm')
if a.no_figures:
    args.append('-noFigureWindows')
if a.mode == 'desktop':
    args.extend(['-desktop', '-logfile', str(case / 'matlab.log'), '-r', statement + " exit(0,'force');"])
else:
    args.extend(['-batch', statement])
start = time.time()
with (case / 'stdout.log').open('wb') as stdout, (case / 'stderr.log').open('wb') as stderr:
    proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
    try:
        code = proc.wait(timeout=a.timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        code = proc.wait(timeout=10)
result = {
    'case': a.case, 'command': args, 'cwd': str(cwd), 'pid': proc.pid,
    'exit_code': code, 'exit_hex': f'0x{code % 4294967296:08X}', 'timed_out': timed_out,
    'duration_seconds': round(time.time()-start, 3),
    'environment_overrides': {k: env[k] for k in ('MATLAB_PREFDIR','TEMP','TMP','APPDATA','LOCALAPPDATA','USERPROFILE')},
    'stdout': str(case / 'stdout.log'), 'stderr': str(case / 'stderr.log'),
    'crash_dumps': [str(x) for x in tmp.glob('matlab_crash_dump*')],
}
(case / 'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
for path in (case / 'stdout.log', case / 'stderr.log', case / 'matlab.log'):
    text = path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''
    result[path.name + '_MINIMAL_START'] = 'MINIMAL_START' in text
    result[path.name + '_MINIMAL_DONE'] = 'MINIMAL_DONE' in text
print(json.dumps(result, ensure_ascii=False))







