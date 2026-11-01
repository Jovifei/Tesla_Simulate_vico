"""Run the cabin 'cold' stage in a brand-new MATLAB process.

Batch mode crashes in mwhomesessionmanager_impl.dll on this machine, but
desktop mode with -r starts and exits cleanly. This launcher uses that path
and records a receipt proving a different MATLAB PID ran the cold repeat.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(r'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\reports\app8-cabin-mechanical-bank-candidate-20261030')
EXE = Path(r'D:\Program Files\MATLAB\R2026a\bin\matlab.exe')

run_root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if run_root is None:
    raise SystemExit('usage: run_cold_in_new_process.py <preflight_run_root>')
run_root = run_root.resolve()
if not (run_root / 'full.json').is_file():
    raise SystemExit(f'full.json missing in {run_root}; run the full stage first')

stamp = time.strftime('%Y%m%d-%H%M%S')
case = LAB / 'cold-process' / stamp
case.mkdir(parents=True, exist_ok=False)
pref = case / 'prefdir'
tmp = case / 'temp'
pref.mkdir()
tmp.mkdir()

statement = (
    "disp('COLD_START'); "
    f"cd('{LAB}'); "
    f"try, s=run_cabin_candidate('cold','{run_root}'); "
    "fprintf('COLD_DONE status=%s\\n', string(s.status)); "
    "catch e, fprintf('COLD_FAIL %s: %s\\n', e.identifier, e.message); "
    "disp(getReport(e,'extended','hyperlinks','off')); end; "
    "disp('COLD_EXIT');"
)
args = [str(EXE), '-wait', '-desktop', '-logfile', str(case / 'matlab.log'),
        '-r', statement + " exit(0,'force');"]

env = os.environ.copy()
env.update(MATLAB_PREFDIR=str(pref), TEMP=str(tmp), TMP=str(tmp))

start = time.time()
with (case / 'stdout.log').open('wb') as out, (case / 'stderr.log').open('wb') as err:
    proc = subprocess.Popen(args, cwd=str(case), env=env, stdin=subprocess.DEVNULL,
                            stdout=out, stderr=err)
    try:
        code = proc.wait(timeout=900)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        code = proc.wait(timeout=30)

logs = {}
for name in ('stdout.log', 'stderr.log', 'matlab.log'):
    p = case / name
    logs[name] = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''

receipt = {
    'case': 'cold-new-process',
    'run_root': str(run_root),
    'command': args,
    'pid': proc.pid,
    'exit_code': code,
    'exit_hex': f'0x{code % 4294967296:08X}',
    'timed_out': timed_out,
    'duration_seconds': round(time.time() - start, 3),
    'environment_overrides': {k: env[k] for k in ('MATLAB_PREFDIR', 'TEMP', 'TMP')},
    'cold_json_exists': (run_root / 'cold.json').is_file(),
    'markers': {
        'COLD_START': 'COLD_START' in logs['stdout.log'] or 'COLD_START' in logs['matlab.log'],
        'COLD_DONE': 'COLD_DONE' in logs['stdout.log'] or 'COLD_DONE' in logs['matlab.log'],
        'COLD_FAIL': 'COLD_FAIL' in logs['stdout.log'] or 'COLD_FAIL' in logs['matlab.log'],
        'COLD_EXIT': 'COLD_EXIT' in logs['stdout.log'] or 'COLD_EXIT' in logs['matlab.log'],
    },
    'stdout': str(case / 'stdout.log'),
    'stderr': str(case / 'stderr.log'),
    'matlab_log': str(case / 'matlab.log'),
    'crash_dumps': [str(p) for p in tmp.glob('matlab_crash_dump*')],
}
(case / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))
