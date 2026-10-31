import ctypes,datetime,hashlib,json,os,pathlib,queue,re,subprocess,sys,threading,time,traceback
from ctypes import wintypes as w

def event(name,**kw):print(json.dumps({'event':name,'local_time':datetime.datetime.now().astimezone().isoformat(),**kw}),flush=True)
if sys.stdin.readline().strip()!='GO':sys.exit(2)
case=pathlib.Path.cwd(); discovery=pathlib.Path(os.environ['APPDATA'])/'MathWorks'/'MATLAB MCP Server'/'v1'/'sessionDetails.json'
protected={int(x) for x in os.environ['RECOVERY_PROTECTED_PIDS'].split(',') if x};gui=None;server=None;h=None
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
k.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];k.GetExitCodeProcess.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL

def disc_pid():
 try:return int(json.loads(discovery.read_text(encoding='utf-8-sig'))['pid'])
 except (OSError,ValueError,KeyError,TypeError):return None

def ancestry(pid):
 out=[];current=pid
 for _ in range(15):
  if current in out:break
  out.append(current)
  if gui and current==gui.pid:break
  ps=subprocess.run(['powershell','-NoProfile','-Command',f'(Get-CimInstance Win32_Process -Filter "ProcessId={current}").ParentProcessId'],capture_output=True,text=True,check=True)
  if not ps.stdout.strip():break
  current=int(ps.stdout.strip())
 return out

def rpc_send(message):
 server.stdin.write(json.dumps(message)+'\n');server.stdin.flush()
def rpc_recv(expected,timeout):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if server.poll() is not None:raise RuntimeError('MCP server exited '+str(server.returncode))
  try:line=messages.get(timeout=.25)
  except queue.Empty:continue
  try:r=json.loads(line)
  except ValueError:continue
  if r.get('id')==expected:
   if 'error' in r:raise RuntimeError('MCP error '+json.dumps(r['error']))
   return r.get('result',{})
 raise TimeoutError('MCP response timeout')
def call_tool(request_id,code,timeout):
 rpc_send({'jsonrpc':'2.0','id':request_id,'method':'tools/call','params':{'name':'evaluate_matlab_code','arguments':{'code':code}}})
 r=rpc_recv(request_id,timeout)
 if r.get('isError'):raise RuntimeError('MATLAB tool error '+json.dumps(r.get('content',[]))[:1200])
 return '\n'.join(str(c.get('text','')) for c in r.get('content',[]) if c.get('type')=='text')

try:
 if 'MATLAB_PREFDIR' in os.environ:raise RuntimeError('MATLAB_PREFDIR unexpectedly set')
 before=disc_pid()
 if before not in protected:raise RuntimeError('baseline discovery PID not among existing MATLAB processes')
 gui_env=os.environ.copy();gui_env.pop('RECOVERY_PROTECTED_PIDS',None)
 si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=subprocess.SW_HIDE
 with (case/'gui-stdout.log').open('wb') as out,(case/'gui-stderr.log').open('wb') as err:
  gui=subprocess.Popen([r'D:\Program Files\MATLAB\R2026a\bin\win64\MATLAB.exe','-useStartupFolderPref'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=gui_env,startupinfo=si)
 event('gui_started',gui_pid=gui.pid,baseline_discovery_pid=before)
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  pid=disc_pid()
  if pid is not None and pid!=before:
   if pid in protected:raise RuntimeError('new discovery points to protected process')
   chain=ancestry(pid)
   if gui.pid not in chain:raise RuntimeError('discovery PID is not descendant of new GUI')
   break
  code=gui.poll()
  if code is not None:raise RuntimeError('GUI exited before new session published: '+str(code))
  time.sleep(.25)
 else:raise TimeoutError('new discovery PID not published within 90 seconds')
 event('new_discovery_verified',pid=pid,ancestry=chain)
 h=k.OpenProcess(0x1000|0x100000,False,pid)
 if not h:raise ctypes.WinError(ctypes.get_last_error())
 if disc_pid()!=pid:raise RuntimeError('discovery PID changed before MCP attach')
 exe=pathlib.Path.home()/'.matlab/agentic-toolkits/bin/matlab-mcp-server.exe'
 server=subprocess.Popen([str(exe),'--matlab-session-mode=existing','--disable-telemetry','--log-folder',os.environ['TEMP']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,startupinfo=si)
 messages=queue.Queue()
 def read_messages():
  for line in server.stdout:messages.put(line)
 threading.Thread(target=read_messages,daemon=True).start()
 rpc_send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'cold-gui-diagnostic','version':'1.0'}}});rpc_recv(1,10)
 rpc_send({'jsonrpc':'2.0','method':'notifications/initialized'})
 ident=call_tool(2,"fprintf('RECOVERY_PID=%d\\n',feature('getpid'));",25)
 match=re.search(r'RECOVERY_PID=(\d+)',ident)
 if not match or int(match.group(1))!=pid:raise RuntimeError('MCP PID verification failed')
 event('mcp_attached_new_pid',pid=pid)
 start=time.monotonic();call_tool(3,"pause(30); disp('RECOVERY_PAUSE30_DONE');",45);elapsed=time.monotonic()-start
 if elapsed<29.5:raise RuntimeError('pause returned too early')
 event('pause30_done',seconds=round(elapsed,3))
 folder=str(case).replace("'","''").replace('\\','/')
 code=("original_folder=pwd; cleanup_folder=onCleanup(@()cd(original_folder)); cd('"+folder+"'); "
       "m='cold_gui_probe'; new_system(m); add_block('simulink/Sources/Constant',[m '/Constant']); "
       "add_block('simulink/Sinks/Terminator',[m '/Terminator']); add_line(m,'Constant/1','Terminator/1'); "
       "out=sim(m,'StopTime','0.02','ReturnWorkspaceOutputs','on'); assert(numel(out.tout)>1 && abs(out.tout(end)-0.02)<1e-10); "
       "fprintf('RECOVERY_SIM_DONE samples=%d end=%.6f\\n',numel(out.tout),out.tout(end)); close_system(m,0); cd(original_folder); clear cleanup_folder original_folder; disp('RECOVERY_MODEL_CLOSED');")
 simout=call_tool(4,code,35)
 if 'RECOVERY_SIM_DONE' not in simout or 'RECOVERY_MODEL_CLOSED' not in simout:raise RuntimeError('simulation completion markers absent')
 event('sim_done',output=simout[:500])
 event('normal_quit_sent')
 rpc_send({'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'evaluate_matlab_code','arguments':{'code':'quit'}}})
 wait=k.WaitForSingleObject(h,20000);exitcode=w.DWORD()
 if not k.GetExitCodeProcess(h,ctypes.byref(exitcode)):raise ctypes.WinError(ctypes.get_last_error())
 try:gui_code=gui.wait(timeout=10)
 except subprocess.TimeoutExpired:gui_code=None
 event('matlab_process_exit',wait_result=int(wait),backend_exit_code=int(exitcode.value),gui_exit_code=gui_code)
 if wait!=0 or exitcode.value!=0 or gui_code!=0:raise RuntimeError('MATLAB did not naturally exit zero')
 event('probe_pass')
except BaseException as exc:
 event('probe_fail',error_type=type(exc).__name__,message=str(exc),gui_exit_code=gui.poll() if gui else None,traceback=traceback.format_exc())
 sys.exit(1)
finally:
 if h:k.CloseHandle(h)
 if server:
  try:server.stdin.close()
  except Exception:pass
  try:server.wait(timeout=3)
  except subprocess.TimeoutExpired:server.terminate();server.wait(timeout=3)
