import ctypes,datetime,hashlib,json,os,pathlib,re,shutil,subprocess,sys,time
from ctypes import wintypes as w
ROOT=pathlib.Path(__file__).resolve().parent;case=ROOT/'07-gui-default-prefs';case.mkdir(exist_ok=False)
python=pathlib.Path(r'C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe')
src=pathlib.Path(os.environ['APPDATA'])/'MathWorks'/'MATLAB MCP Server'/'v1'/'sessionDetails.json';backup=case/'sessionDetails.original.private.json'
home=pathlib.Path(os.environ['APPDATA'])/'MathWorks'/'mwhome'/'mwhomeartifacts_1.db'
def sha(p):
 try:return hashlib.sha256(p.read_bytes()).hexdigest()
 except OSError:return None
def acl_copy(source,target):
 e=os.environ.copy();e.update(ACL_SOURCE=str(source),ACL_TARGET=str(target))
 c="if ((Get-Acl -LiteralPath $env:ACL_SOURCE).Sddl -ne (Get-Acl -LiteralPath $env:ACL_TARGET).Sddl) { Get-Acl -LiteralPath $env:ACL_SOURCE | Set-Acl -LiteralPath $env:ACL_TARGET }; if ((Get-Acl -LiteralPath $env:ACL_SOURCE).Sddl -ne (Get-Acl -LiteralPath $env:ACL_TARGET).Sddl) { exit 2 }"
 subprocess.run(['powershell','-NoProfile','-Command',c],env=e,check=True,capture_output=True,text=True)
shutil.copy2(src,backup);acl_copy(src,backup)
original=backup.read_bytes();original_sha=hashlib.sha256(original).hexdigest()
if original_sha!=sha(src):raise RuntimeError('backup hash differs before start')
q=subprocess.run(['powershell','-NoProfile','-Command',"Get-CimInstance Win32_Process -Filter \"name = 'MATLAB.exe' OR name = 'matlab.exe'\" | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress"],capture_output=True,text=True,check=True)
procs=json.loads(q.stdout.strip() or '[]');procs=procs if isinstance(procs,list) else [procs]
protected=','.join(str(x['ProcessId']) for x in procs);before_home=sha(home)
baseline={'time':datetime.datetime.now().astimezone().isoformat(),'processes':procs,'mcp_discovery_sha256':original_sha,'home_db_sha256':before_home,'backup_acl_matches_original':True,'matlab_prefdir_set':'MATLAB_PREFDIR' in os.environ}
(case/'baseline.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
class Basic(ctypes.Structure):
 _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class Io(ctypes.Structure):_fields_=[(x,ctypes.c_ulonglong) for x in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class Extended(ctypes.Structure):_fields_=[('BasicLimitInformation',Basic),('IoInfo',Io),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];k.CreateJobObjectW.restype=w.HANDLE;k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];k.SetInformationJobObject.restype=w.BOOL;k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];k.AssignProcessToJobObject.restype=w.BOOL;k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
job=None;worker=None;timedout=False;restore_error=None;start=time.monotonic();wall_start=time.time();code=None
try:
 job=k.CreateJobObjectW(None,None)
 if not job:raise ctypes.WinError(ctypes.get_last_error())
 settings=Extended();settings.BasicLimitInformation.LimitFlags=0x2000
 if not k.SetInformationJobObject(job,9,ctypes.byref(settings),ctypes.sizeof(settings)):raise ctypes.WinError(ctypes.get_last_error())
 env=os.environ.copy();env['RECOVERY_PROTECTED_PIDS']=protected
 with (case/'worker-stdout.jsonl').open('wb') as out,(case/'worker-stderr.log').open('wb') as err:
  worker=subprocess.Popen([str(python),'-u',str(ROOT/'matched_gui_worker.py')],stdin=subprocess.PIPE,stdout=out,stderr=err,cwd=case,env=env)
  if not k.AssignProcessToJobObject(job,w.HANDLE(int(worker._handle))):worker.terminate();worker.wait(timeout=10);raise ctypes.WinError(ctypes.get_last_error())
  print(json.dumps({'event':'worker_started','worker_pid':worker.pid,'backup_verified':True}),flush=True);worker.stdin.write(b'GO\n');worker.stdin.close()
  checkpoint=30
  while worker.poll() is None:
   elapsed=time.monotonic()-start
   if elapsed>=150:timedout=True;print(json.dumps({'event':'watchdog_timeout','seconds':round(elapsed,1)}),flush=True);break
   if elapsed>=checkpoint:print(json.dumps({'event':'working','seconds':round(elapsed,1)}),flush=True);checkpoint+=30
   time.sleep(.5)
  if timedout:k.CloseHandle(job);job=None
  try:worker.wait(timeout=10)
  except subprocess.TimeoutExpired:pass
  code=worker.poll()
finally:
 if job:k.CloseHandle(job)
 if worker and worker.poll() is None:
  try:worker.wait(timeout=10)
  except subprocess.TimeoutExpired:pass
 try:
  if sha(src)!=original_sha:
   with src.open('r+b') as f:f.seek(0);f.write(original);f.truncate();f.flush();os.fsync(f.fileno())
   shutil.copystat(backup,src)
  acl_copy(backup,src)
  if sha(src)!=original_sha:raise RuntimeError('restored discovery hash mismatch')
 except BaseException as e:restore_error=str(e)
 if restore_error:print(json.dumps({'event':'discovery_restore_failed','error':restore_error,'backup':str(backup)}),flush=True)
 else:print(json.dumps({'event':'discovery_restored','hash_matches':True}),flush=True)
 events=[]
 for logfile in ('gui-stdout.log','gui-stderr.log'):
  log=case/logfile
  if log.exists():
   for name in set(re.findall(r'matlab_crash_dump\.\d+(?:-\d+)?',log.read_text(encoding='utf-8',errors='replace'))):
    dump=pathlib.Path(os.environ['TEMP'])/name
    if dump.exists() and dump.stat().st_mtime>=wall_start-1:shutil.copy2(dump,case/name)
 if (case/'worker-stdout.jsonl').exists():
  for line in (case/'worker-stdout.jsonl').read_text(encoding='utf-8',errors='replace').splitlines():
   try:events.append(json.loads(line))
   except ValueError:events.append({'event':'unparsed'})
 result={'worker_exit_code':code,'timed_out':timedout,'duration_seconds':round(time.monotonic()-start,3),'events':events,'mcp_hash_before':original_sha,'mcp_hash_after':sha(src),'restore_error':restore_error,'home_db_hash_before':before_home,'home_db_hash_after':sha(home),'natural_exit_zero_all_markers':code==0 and not timedout and not restore_error and any(x.get('event')=='probe_pass' for x in events)}
 (case/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result),flush=True)
