import ctypes, datetime, io, json, os, pathlib, subprocess, sys, time, traceback
from ctypes import wintypes as w

def event(name, **fields):
 print(json.dumps({'event':name,'local_time':datetime.datetime.now().astimezone().isoformat(),**fields}),flush=True)
if sys.stdin.readline().strip()!='GO':sys.exit(2)
sys.path.insert(0,r'D:\Program Files\MATLAB\R2026a\extern\engines\python\dist')
import matlab.engine
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
k.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];k.GetExitCodeProcess.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
name=os.environ['RECOVERY_ENGINE_NAME'];case=pathlib.Path.cwd().parent
protected={int(x) for x in os.environ['RECOVERY_PROTECTED_PIDS'].split(',') if x}
old_names=list(matlab.engine.find_matlab())
if name in old_names:raise RuntimeError('shared name not unique')
exe=r'D:\Program Files\MATLAB\R2026a\bin\win64\MATLAB.exe'
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=subprocess.SW_HIDE
with (case/'gui-stdout.log').open('wb') as out,(case/'gui-stderr.log').open('wb') as err:
 proc=subprocess.Popen([exe,'-desktop','-sd',str(pathlib.Path.cwd())],cwd=pathlib.Path.cwd(),stdin=subprocess.DEVNULL,stdout=out,stderr=err,startupinfo=startup)
 event('gui_started',pid=proc.pid,session_name=name,initial_shared_names_count=len(old_names))
 try:
  deadline=time.monotonic()+90
  while time.monotonic()<deadline:
   names=list(matlab.engine.find_matlab())
   if name in names:break
   code=proc.poll()
   if code is not None:raise RuntimeError(f'GUI process exited before shared engine: {code}')
   time.sleep(1)
  else:raise TimeoutError('shared session not found within 90 seconds')
  event('unique_share_found',session_name=name)
  eng=matlab.engine.connect_matlab(name)
  pid=int(eng.feature('getpid'))
  if pid in protected:raise RuntimeError('connected to a protected process')
  ancestors=[];node=pid
  for unused in range(12):
   if node in ancestors:break
   ancestors.append(node)
   if node==proc.pid:break
   query=subprocess.run(['powershell','-NoProfile','-Command',f'(Get-CimInstance Win32_Process -Filter "ProcessId={node}").ParentProcessId'],text=True,capture_output=True,check=True)
   s=query.stdout.strip()
   if not s:break
   node=int(s)
  if proc.pid not in ancestors:raise RuntimeError('new MATLAB PID not descended from GUI process')
  h=k.OpenProcess(0x1000|0x100000,False,pid)
  if not h:raise ctypes.WinError(ctypes.get_last_error())
  try:
   prefdir=eng.prefdir();startup_path=eng.which('startup');desktop=bool(eng.desktop('-inuse'))
   event('gui_connected',matlab_pid=pid,gui_pid=proc.pid,ancestors=ancestors,desktop=desktop,prefdir=prefdir,startup=startup_path,version=eng.version())
   if pathlib.Path(prefdir).resolve()!=pathlib.Path(os.environ['MATLAB_PREFDIR']).resolve():raise RuntimeError('prefdir not isolated')
   if pathlib.Path(startup_path).resolve()!=pathlib.Path.cwd().joinpath('startup.m').resolve():raise RuntimeError('startup not isolated')
   if not desktop:raise RuntimeError('desktop is not active')
   event('pause30_begin');t=time.monotonic();eng.pause(30.,nargout=0);elapsed=time.monotonic()-t
   if elapsed<29.5:raise RuntimeError('pause returned too early')
   event('pause30_done',seconds=round(elapsed,3))
   statement=("m='gui_recovery_probe'; new_system(m); add_block('simulink/Sources/Constant',[m '/Constant']); "
    "add_block('simulink/Sinks/Terminator',[m '/Terminator']); add_line(m,'Constant/1','Terminator/1'); "
    "out=sim(m,'StopTime','0.02','ReturnWorkspaceOutputs','on'); "
    "assert(numel(out.tout)>1 && abs(out.tout(end)-0.02)<1e-10); "
    "fprintf('GUI_SIM_DONE samples=%d end=%.6f\\n',numel(out.tout),out.tout(end)); "
    "close_system(m,0); disp('GUI_MODEL_CLOSED');")
   capture=io.StringIO();event('sim_begin');eng.eval(statement,nargout=0,stdout=capture,stderr=capture)
   simout=capture.getvalue()
   if 'GUI_SIM_DONE' not in simout or 'GUI_MODEL_CLOSED' not in simout:raise RuntimeError('simulation markers missing')
   event('sim_done',output=simout.strip())
   event('matlab_quit_begin');eng.eval('quit',nargout=0,background=True)
   waited=k.WaitForSingleObject(h,20000);code=w.DWORD()
   if not k.GetExitCodeProcess(h,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
   try:gui_code=proc.wait(timeout=5)
   except subprocess.TimeoutExpired:gui_code=None
   event('matlab_process_exit',wait_result=int(waited),backend_exit_code=int(code.value),gui_exit_code=gui_code)
   if waited!=0 or code.value!=0 or gui_code!=0:raise RuntimeError('MATLAB failed natural zero exit')
   event('probe_pass')
  finally:k.CloseHandle(h)
 except BaseException as exc:
  event('probe_fail',error_type=type(exc).__name__,message=str(exc),gui_exit_code=proc.poll(),traceback=traceback.format_exc())
  sys.exit(1)
