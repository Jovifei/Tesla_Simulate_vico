from pathlib import Path
import datetime, hashlib, json, subprocess, time, argparse
import psutil
from verify_capture import verify

base=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
out=parser.parse_args().out.resolve()
out.mkdir(exist_ok=False)
rows=[]
for scene,seconds in [('main',60),('low',30),('high',30),('holdout',60)]:
    cmd=[str(base/'build/Release/engine_offline.exe'),str(out/scene),scene,str(seconds)]
    t=time.time();peak=0
    with (out/(scene+'.log')).open('w',encoding='utf8') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        proc=psutil.Process(child.pid)
        while child.poll() is None:
            try:peak=max(peak,proc.memory_info().rss)
            except psutil.NoSuchProcess:pass
            if time.time()-t>180:
                child.terminate();child.wait();raise TimeoutError(scene)
            time.sleep(.2)
    row={'scene':scene,'seconds':seconds,'command':cmd,'exit':child.returncode,
         'wall_s':time.time()-t,'peak_rss_bytes':peak,
         'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    row['files']={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in (out/scene).glob('*') if p.is_file()}
    rows.append(row)
    if child.returncode==0:row['data_verification']=verify(out/scene)
    (out/'run-receipt.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(row|{'files':list(row['files'])}),flush=True)
    if child.returncode:raise SystemExit(child.returncode)
print('ALL_180_SECONDS_CAPTURED',flush=True)
