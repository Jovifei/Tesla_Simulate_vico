from pathlib import Path
import sys,json,math,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/vico_app/tools/python'))
from generate_c63_live_loop_variant import decode,encode

def phase_offset(rpm):
 if not math.isfinite(rpm) or rpm not in (6800,7200):raise ValueError('Only reviewed high-RPM anchors')
 return round(math.ceil((7682+384)*rpm/(120*48000))*120*48000/rpm-7682)

def main():
 base=ROOT.parent/'vico-drive-demand/work/vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6'
 out=ROOT/'candidate-high-phase';out.mkdir(exist_ok=False)
 m=json.loads((base/'manifest.json').read_text());rows=[]
 for e in m['loops']:
  if e['rpm'] not in (6800,7200):continue
  raw=(base/e['file']).read_bytes();x=decode(raw);off=phase_offset(e['rpm']);y=np.roll(x,-off)
  assert len(x)==17280 and off>=384 and np.isfinite(y).all()
  assert np.array_equal(np.sort(x),np.sort(y))
  assert np.max(np.abs(y))<=10**(-1.5/20)+1e-7
  spectrum_error=float(np.max(np.abs(np.abs(np.fft.rfft(x.astype(float)))-np.abs(np.fft.rfft(y.astype(float))))))
  assert spectrum_error<1e-10
  b=encode(y);assert np.array_equal(decode(b),y);(out/e['file']).write_bytes(b)
  rows.append({'file':e['file'],'rpm':e['rpm'],'load':e['load'],'offset':off,'baseline_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(b).hexdigest(),'max_fft_magnitude_error':spectrum_error,'samples':len(y),'rms':float(np.sqrt(np.mean(y.astype(float)**2))),'peak':float(np.max(np.abs(y)))})
 manifest={'schema':'vico.offline.high_phase_candidate.v1','baseline_commit':'955b1355839f4b233e56c9ec9213fb86ae1927a6','scope':'offline only; source drop and original seam remain; no runtime route','fixed_gain':m['fixed_vehicle_gain'],'source_origin_contract':'first whole four-stroke cycle after original384-sample crossfade','rows':rows}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
