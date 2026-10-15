from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/vico_app/tools/python'))
import generate_c63_live_loop_variant as api
Trace,render,h,ptr=api.source_api(ROOT/'source')
base=ROOT.parent/'vico-drive-demand/work/vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6'
m=json.loads((base/'manifest.json').read_text());gain=m['fixed_vehicle_gain']
def metrics(x):
 x=np.asarray(x,dtype=np.float64)
 if x.ndim==2:x=x.mean(axis=1)
 x=x[-17280:];power=np.abs(np.fft.rfft(x*np.hanning(len(x))))**2;freq=np.fft.rfftfreq(len(x),1/48000)
 return {'rms':float(np.sqrt(np.mean(x*x))),'peak':float(np.max(np.abs(x))),'bands':{f'{a}-{b}':float(power[(freq>=a)&(freq<b)].sum()/max(power.sum(),1e-30)) for a,b in [(20,250),(250,1000),(1000,4000),(4000,10000)]}}
rows=[]
for e in m['loops']:
 trace=h['_constant_trace'](Trace,e['rpm'],e['load'],.52)
 source=render(trace);full=h['_render_stateful'](render,'c63_w204',trace);pre=h['_mono_48k'](ptr(full.pressure));old=(h['_loop'](pre)*gain).astype(np.float32);wav=(base/e['file']).read_bytes();expected=api.decode(wav)
 assert np.array_equal(old,expected),e['file']
 row={'rpm':e['rpm'],'load':e['load'],'wav_sha256':hashlib.sha256(wav).hexdigest(),'source':metrics(source.pressure),'realism':metrics(full.pressure),'post_ptr':metrics(pre),'bank':metrics(old),'stems':{k:metrics(v) for k,v in source.stems.items()},'exact_recipe_match':True};rows.append(row);print(e['file'],row['bank']['rms'],row['source']['rms'],flush=True)
out={'commit':'955b1355839f4b233e56c9ec9213fb86ae1927a6','gain':gain,'loop_samples':17280,'rows':rows,'source_sha256':{str(p.relative_to(ROOT/'source')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'source').rglob('*') if p.is_file() and '__pycache__' not in p.parts}}
(ROOT/'evidence/recipe-baseline.json').write_text(json.dumps(out,indent=2)+'\n')
