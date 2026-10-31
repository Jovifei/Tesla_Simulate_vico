import argparse, datetime, hashlib, json, os, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent
MATLAB = pathlib.Path(r'D:\Program Files\MATLAB\R2026a\bin\matlab.exe')
KEY = 'MW_ARTIFACTS_WS_ENABLED'
parser = argparse.ArgumentParser()
parser.add_argument('--case', choices=['01-artifacts-off', '02-artifacts-off-repeat'], required=True)
args = parser.parse_args()
case = ROOT / args.case
case.mkdir(exist_ok=False)
for subdir in ('prefdir', 'temp', 'working'):
    (case / subdir).mkdir()
(case / 'working' / 'startup.m').write_text("disp('RECOVERY_STARTUP_OVERRIDE');\n", encoding='utf-8')

def db_stat():
    path = pathlib.Path(os.environ['APPDATA']) / 'MathWorks' / 'mwhome' / 'mwhomeartifacts_1.db'
    try:
        st = path.stat()
        return {'exists': True, 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    except OSError as exc:
        return {'exists': False, 'error_class': type(exc).__name__}

old = os.environ.get(KEY)
baseline = {'timestamp_local': datetime.datetime.now().astimezone().isoformat(),
            'artifact_env_present': KEY in os.environ,
            'artifact_env_value_if_known': old if old in ('0','1') else ('<other>' if old is not None else None),
            'home_db': db_stat(),
            'existing_preference_or_home_db_copied_or_edited_by_harness': False}
(case / 'baseline.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
env = os.environ.copy()
env.update({KEY:'0', 'MATLAB_PREFDIR':str(case / 'prefdir'), 'TEMP':str(case / 'temp'), 'TMP':str(case / 'temp')})
statement = ("disp('RECOVERY_BEGIN'); pause(30); disp('RECOVERY_PAUSE30_DONE'); "
 "m='recovery_probe'; new_system(m); "
 "add_block('simulink/Sources/Constant',[m '/Constant']); "
 "add_block('simulink/Sinks/Terminator',[m '/Terminator']); "
 "add_line(m,'Constant/1','Terminator/1'); "
 "out=sim(m,'StopTime','0.02','ReturnWorkspaceOutputs','on'); "
 "assert(numel(out.tout)>1 && abs(out.tout(end)-0.02)<1e-10); "
 "fprintf('RECOVERY_SIM_DONE samples=%d end=%.6f\\n',numel(out.tout),out.tout(end)); "
 "close_system(m,0); disp('RECOVERY_MODEL_CLOSED');")
cmd = [str(MATLAB), '-wait', '-batch', statement]
start=time.monotonic()
with (case/'stdout.log').open('wb') as stdout, (case/'stderr.log').open('wb') as stderr:
    proc=subprocess.Popen(cmd, cwd=case/'working', env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
    print(json.dumps({'event':'started','case':args.case,'launcher_pid':proc.pid,'baseline_artifact_env_present':baseline['artifact_env_present']}), flush=True)
    timed_out=False
    while proc.poll() is None:
        elapsed=time.monotonic()-start
        if elapsed >= 120:
            timed_out=True
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: print(json.dumps({'event':'termination_unconfirmed','pid':proc.pid}), flush=True)
            break
        if int(elapsed//30)>int(max(0,elapsed-0.5)//30):
            print(json.dumps({'event':'working','elapsed_seconds':round(elapsed,1),'launcher_pid':proc.pid}),flush=True)
        time.sleep(0.5)
    code=proc.poll()
log=(case/'stdout.log').read_text(encoding='utf-8',errors='replace')
markers={key:key in log for key in ('RECOVERY_STARTUP_OVERRIDE','RECOVERY_BEGIN','RECOVERY_PAUSE30_DONE','RECOVERY_SIM_DONE','RECOVERY_MODEL_CLOSED')}
result={'case':args.case,'command':cmd,'cwd':str(case/'working'),'launcher_pid':proc.pid,'exit_code':code,
        'exit_hex':f'0x{code % 4294967296:08X}' if code is not None else None,'timed_out':timed_out,
        'duration_seconds':round(time.monotonic()-start,3),'environment_overrides':{k:env[k] for k in (KEY,'MATLAB_PREFDIR','TEMP','TMP')},
        'markers':markers,'natural_exit_zero_all_markers':code == 0 and not timed_out and all(markers.values()),
        'home_db_after':db_stat(),'crash_dumps':[str(x) for x in (case/'temp').glob('matlab_crash_dump*')],
        'stdout':str(case/'stdout.log'),'stderr':str(case/'stderr.log')}
(case/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
