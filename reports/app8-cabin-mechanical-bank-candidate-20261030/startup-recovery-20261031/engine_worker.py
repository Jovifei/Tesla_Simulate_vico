import ctypes, datetime, io, json, os, pathlib, sys, time, traceback
from ctypes import wintypes

def event(name, **kwargs):
    print(json.dumps({'event':name, 'local_time':datetime.datetime.now().astimezone().isoformat(), **kwargs}),flush=True)

if sys.stdin.readline().strip() != 'GO':
    event('cancelled_before_matlab')
    sys.exit(2)

sys.path.insert(0, r'D:\Program Files\MATLAB\R2026a\extern\engines\python\dist')
import matlab.engine
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
kernel.OpenProcess.restype=wintypes.HANDLE
kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
kernel.WaitForSingleObject.restype=wintypes.DWORD
kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
kernel.GetExitCodeProcess.restype=wintypes.BOOL
kernel.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]
kernel.IsProcessInJob.restype=wintypes.BOOL
kernel.CloseHandle.argtypes=[wintypes.HANDLE]
kernel.CloseHandle.restype=wintypes.BOOL
h=None
eng=None
try:
    event('engine_launch',python=sys.version.split()[0],engine_module=matlab.engine.__file__,option='-desktop',artifact_env_present='MW_ARTIFACTS_WS_ENABLED' in os.environ)
    eng=matlab.engine.start_matlab('-desktop')
    pid=int(eng.feature('getpid'))
    protected={int(x) for x in os.environ['RECOVERY_PROTECTED_PIDS'].split(',') if x}
    if pid in protected:
        raise RuntimeError('Engine unexpectedly returned a protected existing process')
    h=kernel.OpenProcess(0x1000|0x100000,False,pid)
    if not h: raise ctypes.WinError(ctypes.get_last_error())
    in_job=wintypes.BOOL()
    if not kernel.IsProcessInJob(h,None,ctypes.byref(in_job)): raise ctypes.WinError(ctypes.get_last_error())
    version=eng.version()
    desktop=bool(eng.desktop('-inuse'))
    prefdir=eng.prefdir()
    startup=eng.which('startup')
    event('engine_connected',matlab_pid=pid,desktop=desktop,version=version,prefdir=prefdir,startup=startup,any_job=bool(in_job.value))
    expected=pathlib.Path(os.environ['MATLAB_PREFDIR']).resolve()
    if pathlib.Path(prefdir).resolve()!=expected: raise RuntimeError('Preference isolation not applied')
    if pathlib.Path(startup).resolve()!=pathlib.Path.cwd().joinpath('startup.m').resolve(): raise RuntimeError('Startup isolation not applied')
    if not desktop: raise RuntimeError('Desktop not active')
    event('pause30_begin')
    started=time.monotonic()
    eng.pause(30.0,nargout=0)
    elapsed=time.monotonic()-started
    if elapsed<29.5: raise RuntimeError('pause returned too early')
    event('pause30_done',seconds=round(elapsed,3))
    buf=io.StringIO()
    stmt=("m='engine_recovery_probe'; new_system(m); "
          "add_block('simulink/Sources/Constant',[m '/Constant']); "
          "add_block('simulink/Sinks/Terminator',[m '/Terminator']); "
          "add_line(m,'Constant/1','Terminator/1'); "
          "out=sim(m,'StopTime','0.02','ReturnWorkspaceOutputs','on'); "
          "assert(numel(out.tout)>1 && abs(out.tout(end)-0.02)<1e-10); "
          "fprintf('ENGINE_SIM_DONE samples=%d end=%.6f\\n',numel(out.tout),out.tout(end)); "
          "close_system(m,0); disp('ENGINE_MODEL_CLOSED');")
    event('sim_begin')
    eng.eval(stmt,nargout=0,stdout=buf,stderr=buf)
    simout=buf.getvalue()
    if 'ENGINE_SIM_DONE' not in simout or 'ENGINE_MODEL_CLOSED' not in simout:
        raise RuntimeError('Simulation completion markers missing')
    event('sim_done',output=simout.strip())
    event('engine_quit_begin')
    eng.quit()
    eng=None
    event('engine_quit_returned')
    result=kernel.WaitForSingleObject(h,20000)
    code=wintypes.DWORD()
    if not kernel.GetExitCodeProcess(h,ctypes.byref(code)): raise ctypes.WinError(ctypes.get_last_error())
    event('matlab_process_exit',wait_result=int(result),exit_code=int(code.value))
    if result!=0 or code.value!=0: raise RuntimeError('MATLAB did not exit normally with status zero')
    event('probe_pass')
except BaseException as exc:
    event('probe_fail',error_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    sys.exit(1)
finally:
    if h: kernel.CloseHandle(h)
