import ctypes, json, os, pathlib, subprocess, sys
from ctypes import wintypes as w
k=ctypes.WinDLL('kernel32',use_last_error=True);n=ctypes.WinDLL('ntdll')
class FILEINFO(ctypes.Structure):
 _fields_=[('attrs',w.DWORD),('creation',w.FILETIME),('access',w.FILETIME),('write',w.FILETIME),('volume',w.DWORD),('sizehigh',w.DWORD),('sizelow',w.DWORD),('links',w.DWORD),('indexhigh',w.DWORD),('indexlow',w.DWORD)]
class HANDLEENTRY(ctypes.Structure):
 _fields_=[('object',ctypes.c_void_p),('pid',ctypes.c_size_t),('value',ctypes.c_size_t),('access',w.ULONG),('trace',w.USHORT),('type',w.USHORT),('attributes',w.ULONG),('reserved',w.ULONG)]
class HANDLEHEADER(ctypes.Structure):
 _fields_=[('count',ctypes.c_size_t),('reserved',ctypes.c_size_t)]
k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE];k.CreateFileW.restype=w.HANDLE
k.GetFileInformationByHandle.argtypes=[w.HANDLE,ctypes.POINTER(FILEINFO)];k.GetFileInformationByHandle.restype=w.BOOL
k.GetFileType.argtypes=[w.HANDLE];k.GetFileType.restype=w.DWORD
k.GetCurrentProcess.argtypes=[];k.GetCurrentProcess.restype=w.HANDLE
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.DuplicateHandle.argtypes=[w.HANDLE,w.HANDLE,w.HANDLE,ctypes.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD];k.DuplicateHandle.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
n.NtQuerySystemInformation.argtypes=[w.ULONG,ctypes.c_void_p,w.ULONG,ctypes.POINTER(w.ULONG)];n.NtQuerySystemInformation.restype=ctypes.c_long
INVALID=ctypes.c_void_p(-1).value
root=pathlib.Path(os.environ['APPDATA'])/'MathWorks'/'mwhome';db=root/'mwhomeartifacts_1.db'
def openhandle(path,access,flags=0x80):
 h=k.CreateFileW(str(path),access,7,None,3,flags,None)
 if h==INVALID:return None,ctypes.get_last_error()
 return h,0
def info(h):
 q=FILEINFO()
 if not k.GetFileInformationByHandle(h,ctypes.byref(q)):return None
 return (q.volume,q.indexhigh,q.indexlow)
result={'directory_entries':[{'name':f.name,'bytes':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns,'is_file':f.is_file()} for f in root.iterdir()],'open_delete_access_checks':{},'matching_db_file_handles':[]}
for label,path,flags in [('file',db,0x80),('directory',root,0x02000000)]:
 h,err=openhandle(path,0x10000|0x80,flags)
 result['open_delete_access_checks'][label]={'opened':h is not None,'win32_error':err}
 if h:k.CloseHandle(h)
myfile,err=openhandle(db,0x80)
if not myfile:raise OSError(err,'cannot open db metadata')
target=info(myfile)
ps=subprocess.run(['powershell','-NoProfile','-Command',"Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'MATLAB|MathWorks|ServiceHost|Connector' } | Select-Object ProcessId,Name | ConvertTo-Json -Compress"],text=True,capture_output=True,check=True)
procs=json.loads(ps.stdout);procs=procs if isinstance(procs,list) else [procs]
pids={int(x['ProcessId']):x['Name'] for x in procs};pids[os.getpid()]='self'
needed=w.ULONG();size=1024*1024
while size<=128*1024*1024:
 buf=ctypes.create_string_buffer(size)
 status=n.NtQuerySystemInformation(64,buf,size,ctypes.byref(needed))
 if status==0:break
 if ctypes.c_uint32(status).value != 3221225476:raise OSError(ctypes.c_uint32(status).value,'NtQuerySystemInformation failed')
 size=max(size*2,needed.value+65536)
else:raise RuntimeError('handle table exceeds bound')
header=HANDLEHEADER.from_buffer(buf)
entries=(HANDLEENTRY*header.count).from_buffer(buf,ctypes.sizeof(HANDLEHEADER))
types={e.type for e in entries if e.pid==os.getpid() and e.value==myfile}
if len(types)!=1:raise RuntimeError('could not identify DB file handle type')
typeid=types.pop();processes={};errors={}
for pid in pids:
 h=k.OpenProcess(0x40|0x1000,False,pid)
 if h:processes[pid]=h
 else:errors[str(pid)]=ctypes.get_last_error()
scanned=0
for e in entries:
 if e.type!=typeid or e.pid not in processes:continue
 dup=w.HANDLE()
 if not k.DuplicateHandle(processes[e.pid],w.HANDLE(e.value),k.GetCurrentProcess(),ctypes.byref(dup),0,False,2):continue
 try:
  if k.GetFileType(dup)==1:
   scanned+=1
   if info(dup)==target:result['matching_db_file_handles'].append({'pid':int(e.pid),'name':pids[e.pid]})
 finally:k.CloseHandle(dup)
for h in processes.values():k.CloseHandle(h)
k.CloseHandle(myfile)
result['scanned_processes']=pids;result['open_process_errors']=errors;result['disk_handles_scanned']=scanned
result['limitations']='Point-in-time best-effort scan of selected MathWorks/MATLAB process names; handles may change immediately; no claim about unselected or protected processes. Delete-access open is not a rename.'
print(json.dumps(result,ensure_ascii=False,indent=2))
