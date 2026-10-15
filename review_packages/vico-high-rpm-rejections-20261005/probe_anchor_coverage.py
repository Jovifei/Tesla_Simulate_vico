from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/vico_app/tools/python'))
import generate_c63_live_loop_variant as api
from loop_preroll import make_period_preserving_loop
Trace,render,h,ptr=api.source_api(ROOT/'source')
base=ROOT.parent/'vico-drive-demand/work/vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6';m=json.loads((base/'manifest.json').read_text());gain=m['fixed_vehicle_gain'];out=ROOT/'anchor-probe';out.mkdir(exist_ok=False);rows=[]
for rpm in (5400,5450,5500,5550,5600,6100,6150,6200):
 for load in (.32,.92):
  t=h['_constant_trace'](Trace,rpm,load,.52);full=h['_render_stateful'](render,'c63_w204',t);pre=h['_mono_48k'](ptr(full.pressure));old=(h['_loop'](pre)*gain).astype(np.float32);loop,_=make_period_preserving_loop(pre,48000);new=(loop*gain).astype(np.float32)
  name=f'rpm_{rpm:04d}_load_{round(load*100):02d}.wav';b=api.encode(new);(out/name).write_bytes(b);row={'rpm':rpm,'load':load,'file':name,'sha256':hashlib.sha256(b).hexdigest(),'baseline_loop_rms':float(np.sqrt(np.mean(old.astype(float)**2))),'preroll_loop_rms':float(np.sqrt(np.mean(new.astype(float)**2))),'preroll_peak':float(np.max(abs(new))),'finite':bool(np.isfinite(new).all()),'peak_budget_pass':bool(np.max(abs(new))<=10**(-1.5/20)+1e-7)};rows.append(row);print(row,flush=True)
(out/'manifest.json').write_text(json.dumps({'status':'probe only; candidate selection not made','commit':'955b1355839f4b233e56c9ec9213fb86ae1927a6','gain':gain,'rows':rows},indent=2)+'\n')
