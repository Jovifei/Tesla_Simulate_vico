from pathlib import Path
import json,csv,hashlib,argparse
import numpy as np
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--render-output',type=Path,required=True);out=parser.parse_args().render_output
rows=list(csv.DictReader((out/'blend.csv').open()));a={(x['rpm'],x['load']):x for x in rows if x['variant']=='original'};b={(x['rpm'],x['load']):x for x in rows if x['variant']=='high_phase_v1'}
if len(a)!=80 or len(b)!=80:raise SystemExit(f'Incomplete scan {len(a)} {len(b)}')
holdouts=[k for k in a if int(k[0]) in (6830,6890,7020,7090,7170) and float(k[1]) in (.47,.77)]
severe=[float(b[k]['cancellation_db'])-float(a[k]['cancellation_db']) for k in holdouts if float(a[k]['cancellation_db'])<=-4]
worst_window=min(float(b[k]['worst_500ms_db'])-float(a[k]['worst_500ms_db']) for k in holdouts)
print('severe improvement',severe,'median',np.median(severe),'worst window delta',worst_window)
def bands(x):
 x=np.asarray(x,dtype=float).reshape(-1,4800);win=np.hanning(4800);fft=np.fft.rfft(x*win,axis=1);f=np.fft.rfftfreq(4800,1/48000)
 return {'rms':10*np.log10(np.mean(x*x,axis=1)+1e-30),**{f'{lo}-{hi}':10*np.log10(np.mean(np.abs(fft[:,(f>=lo)&(f<hi)])**2,axis=1)+1e-30) for lo,hi in [(20,250),(250,1000),(1000,4000),(4000,10000)]}}
report=[]
for row in json.loads((ROOT/'source-holdouts/manifest.json').read_text())['rows']:
 suffix=f"{row['rpm']}_{round(row['load']*100)}.f32le";ref=bands(np.fromfile(ROOT/'source-holdouts'/row['file'],dtype='<f4'));v={variant:bands(np.fromfile(out/(variant+'_'+suffix),dtype='<f4')) for variant in ('original','high_phase_v1')}
 for band in ref:
  ae=np.abs(v['original'][band]-ref[band]);be=np.abs(v['high_phase_v1'][band]-ref[band]);report.append({'rpm':row['rpm'],'load':row['load'],'band':band,'baseline_median_error_db':float(np.median(ae)),'candidate_median_error_db':float(np.median(be)),'median_regression_db':float(np.median(be)-np.median(ae)),'p90_regression_db':float(np.percentile(be,90)-np.percentile(ae,90))})
result={'cases':len(rows),'severe_cancellation_median_improvement_db':float(np.median(severe)) if severe else None,'worst_heldout_window_delta_db':worst_window,'cancellation_gate':bool(severe and np.median(severe)>=3 and worst_window>=-.5),'source_band_gate':all(x['median_regression_db']<=.5 and x['p90_regression_db']<=.5 for x in report),'peak':max(float(x['peak']) for x in rows),'above_contract':sum(int(x['above']) for x in rows),'hard_clip':sum(int(x['clip']) for x in rows),'nonfinite':sum(int(x['nonfinite']) for x in rows),'source_band_rows':report}
(ROOT/'evidence/heldout-result.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='source_band_rows'});print('worst band',max(report,key=lambda x:x['p90_regression_db']))
