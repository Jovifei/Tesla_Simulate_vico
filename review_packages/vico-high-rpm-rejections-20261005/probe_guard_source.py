from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/vico_app/tools/python'))
import generate_c63_live_loop_variant as api
Trace,render,h,ptr=api.source_api(ROOT/'source')
base=ROOT.parent/'vico-drive-demand/work/vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6';m=json.loads((base/'manifest.json').read_text());gain=m['fixed_vehicle_gain'];out=ROOT/'guard-source-holdouts';out.mkdir(exist_ok=True);rows=[]
for rpm,load in [(r,l) for r in (5200,5500,6100,5450,5550,5250,5750,6050,6250) for l in (.32,.47,.77,.92)]:
 trace=h['_constant_trace'](Trace,rpm,load,4.0);rendered=h['_render_stateful'](render,'c63_w204',trace);pcm=(h['_mono_48k'](ptr(rendered.pressure))*gain).astype('<f4')[-144000:];name=f'{rpm}_{round(load*100)}.f32le';b=pcm.tobytes();(out/name).write_bytes(b);rows.append({'rpm':rpm,'load':load,'file':name,'sha256':hashlib.sha256(b).hexdigest(),'rms':float(np.sqrt(np.mean(pcm.astype(float)**2))),'peak':float(np.max(abs(pcm)))});print(rpm,load,rows[-1]['rms'],flush=True)
(out/'manifest.json').write_text(json.dumps({'commit':'955b1355839f4b233e56c9ec9213fb86ae1927a6','duration_generated_s':4,'warmup_discard_s':1,'gain':gain,'rows':rows},indent=2)+'\n')
