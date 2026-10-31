import argparse, ctypes, datetime, json, os, pathlib, subprocess, sys, time
from ctypes import wintypes
ROOT=pathlib.Path(__file__).resolve().parent
PYTHON=pathlib.Path(r'C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe')
PARSER=argparse.ArgumentParser()
PARSER.add_argument('--case',choices=['03-engine-desktop','04-engine-desktop-repeat'],required=True)
args=PARSER.parse_args()
case=ROOT/args.case
case.mkdir(exist_ok=False)
for d in ('working','prefdir','temp'): (case/d).mkdir()
(case/'working'/'startup.m').write_text("disp('RECOVERY_STARTUP_OVERRIDE');\n",encoding='utf-8')
base=subprocess.run(['powershell','-NoProfile','-Command',"Get-CimInstance Win32_Process -Filter \"name = 'MATLAB.exe' OR name = 'matlab.exe'\" | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress"],capture_output=True,text=True,check=True)
baseline=json.loads(base.stdout.strip() or '[]')
if isinstance(baseline,dict): baseline=[baseline]
protected=','.join(str(x['ProcessId']) for x in baseline)
(case/'baseline.json').write_text(json.dumps({'timestamp_local':datetime.datetime.now().astimezone().isoformat(),'existing_matlab_processes':baseline,'original_artifacts_var_present':'MW_ARTIFACTS_WS_ENABLED' in os.environ},indent=2),encoding='utf-8')
env=os.environ.copy()
env.pop('MW_ARTIFACTS_WS_ENABLED',None)
env.update({'MATLAB_PREFDIR':str(case/'prefdir'),'TEMP':str(case/'temp'),'TMP':str(case/'temp'),'RECOVERY_PROTECTED_PIDS':protected,'PYTHONDONTWRITEBYTECODE':'1'})
class Basic(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
class Io(ctypes.Structure):
    _fields_=[(x,ctypes.c_ulonglong) for x in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class Extended(ctypes.Structure):
    _fields_=[('BasicLimitInformation',Basic),('IoInfo',Io),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];k.SetInformationJobObject.restype=wintypes.BOOL
k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];k.AssignProcessToJobObject.restype=wintypes.BOOL
k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
job=k.CreateJobObjectW(None,None)
if not job: raise ctypes.WinError(ctypes.get_last_error())
settings=Extended();settings.BasicLimitInformation.LimitFlags=0x2000
if not k.SetInformationJobObject(job,9,ctypes.byref(settings),ctypes.sizeof(settings)): raise ctypes.WinError(ctypes.get_last_error())
start=time.monotonic()
timedout=False
with (case/'worker-stdout.jsonl').open('wb') as out,(case/'worker-stderr.log').open('wb') as err:
    worker=subprocess.Popen([str(PYTHON),'-u',str(ROOT/'engine_worker.py')],stdin=subprocess.PIPE,stdout=out,stderr=err,cwd=case/'working',env=env)
    if not k.AssignProcessToJobObject(job,wintypes.HANDLE(int(worker._handle))):
        worker.terminate(); worker.wait(timeout=10); raise ctypes.WinError(ctypes.get_last_error())
    print(json.dumps({'event':'worker_started','worker_pid':worker.pid,'case':args.case,'job_control':True}),flush=True)
    worker.stdin.write(b'GO\n'); worker.stdin.close()
    checkpoint=30
    while worker.poll() is None:
        elapsed=time.monotonic()-start
        if elapsed>=120:
            timedout=True
            print(json.dumps({'event':'watchdog_timeout','seconds':round(elapsed,1)}),flush=True)
            break
        if elapsed>=checkpoint:
            print(json.dumps({'event':'working','seconds':round(elapsed,1),'worker_pid':worker.pid}),flush=True)
            checkpoint+=30
        time.sleep(0.5)
    if timedout:
        k.CloseHandle(job);job=None
        try: worker.wait(timeout=10)
        except subprocess.TimeoutExpired: print(json.dumps({'event':'worker_still_running_after_job_close'}),flush=True)
    else:
        worker.wait()
    code=worker.poll()
if job: k.CloseHandle(job)
lines=(case/'worker-stdout.jsonl').read_text(encoding='utf-8',errors='replace').splitlines()
events=[]
for line in lines:
    try: events.append(json.loads(line))
    except ValueError: events.append({'event':'unparsed','content':line[:300]})
result={'case':args.case,'worker_pid':worker.pid,'worker_exit_code':code,'timed_out':timedout,'duration_seconds':round(time.monotonic()-start,3),'baseline_existing_pids':[x['ProcessId'] for x in baseline],'events':events,'natural_exit_zero_all_markers':code==0 and not timedout and any(x.get('event')=='probe_pass' for x in events),'crash_dumps':[str(x) for x in (case/'temp').glob('matlab_crash_dump*')]}
(case/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
