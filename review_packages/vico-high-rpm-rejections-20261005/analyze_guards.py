from pathlib import Path
import json,csv,argparse
import numpy as np
R=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--render-output',type=Path,required=True);out=parser.parse_args().render_output
manifest=json.loads((R/'guard-source-holdouts/manifest.json').read_text())
def bands(x):
 x=x.astype(float).reshape(-1,4800);f=np.fft.rfftfreq(4800,1/48000);p=np.abs(np.fft.rfft(x*np.hanning(4800),axis=1))**2
 return {'rms':10*np.log10(np.mean(x*x,axis=1)+1e-30),**{f'{a}-{b}':10*np.log10(np.mean(p[:,(f>=a)&(f<b)],axis=1)+1e-30) for a,b in [(20,250),(250,1000),(1000,4000),(4000,10000)]}}
rows=[];anchors=[]
for q in manifest['rows']:
 suffix=f"{q['rpm']}_{round(q['load']*100)}.f32le";ref=bands(np.fromfile(R/'guard-source-holdouts'/q['file'],dtype='<f4'));araw=np.fromfile(out/('original_'+suffix),dtype='<f4');braw=np.fromfile(out/('rpm_guards_v1_'+suffix),dtype='<f4');a=bands(araw);b=bands(braw)
 if q['rpm']==5500:anchors.append(bool(np.array_equal(araw,braw)))
 for band in ref:
  ae=np.abs(a[band]-ref[band]);be=np.abs(b[band]-ref[band]);rows.append({'rpm':q['rpm'],'load':q['load'],'band':band,'median_improvement':float(np.median(ae)-np.median(be)),'p90_regression':float(np.percentile(be,90)-np.percentile(ae,90)),'strict_improved_fraction':float(np.mean(be<ae)),'baseline_median_error':float(np.median(ae)),'candidate_median_error':float(np.median(be)),'phase_blind_median_error_improvement':float(abs(np.median(a[band])-np.median(ref[band]))-abs(np.median(b[band])-np.median(ref[band]))),'phase_blind_p90_error_regression':float(abs(np.percentile(b[band],90)-np.percentile(ref[band],90))-abs(np.percentile(a[band],90)-np.percentile(ref[band],90)))})
primary=[x for x in rows if x['rpm'] in (5200,6100) and x['load'] in (.32,.92) and x['band']=='1000-4000'];protect=[x for x in rows if x not in primary]
scan=list(csv.DictReader((out/'blend.csv').open()));result={'primary':primary,'primary_pass':all(x['median_improvement']>=6 and x['p90_regression']<=0 and x['strict_improved_fraction']>=.6 for x in primary),'protection_pass':all(x['median_improvement']>=-.5 and x['p90_regression']<=.5 for x in protect),'anchor_bit_exact':all(anchors),'worst_protection':max(protect,key=lambda x:x['p90_regression']),'raw_peak':max(float(x['peak']) for x in scan),'bad_counts':sum(int(x['above'])+int(x['clip'])+int(x['nonfinite']) for x in scan),'rows':rows}
(R/'evidence/rpm-guards-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
