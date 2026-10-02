from pathlib import Path
import argparse,csv,hashlib,json,math
import numpy as np

LIMIT=.8413951416451951
def line_power(x,hz):
    samples=np.asarray(x,dtype=np.float64)
    if samples.ndim!=1 or len(samples)<1024 or not math.isfinite(hz) or not 0<hz<24000 or not np.isfinite(samples).all():raise ValueError('Invalid modal pressure PCM')
    n=np.arange(len(samples),dtype=np.float64)
    phasor=np.exp(-2j*np.pi*hz*n/48000.0)
    value=float(abs(np.dot(samples,phasor))**2/(float(len(samples))*len(samples)))
    if not math.isfinite(value) or value<0:raise ValueError('Modal power must be finite/nonnegative')
    return value

def band_prominence(x,hz):
    center=line_power(x,hz)
    neighbors=[line_power(x,hz+offset) for offset in (-80.,-60.,-40.,40.,60.,80.)]
    return 10*math.log10(max(center,1e-30)/max(float(np.mean(neighbors)),1e-30))

def band_power(x):
    power=np.abs(np.fft.rfft(np.asarray(x,dtype=np.float64)*np.hanning(len(x))))**2
    freq=np.fft.rfftfreq(len(x),1/48000)
    return [float(power[(freq>=a)&(freq<b)].sum()) for a,b in ((20,200),(200,1000),(1000,4000),(4000,12000))]

def expected_cases():
    return {f'Q2_{hz}_{k}':(hz,15*hz/k) for hz in (540.,820.,1100.,1500.) for k in range(1,33) if 700<=15*hz/k<=7200}

def analyze(root):
    with (root/'modal.tsv').open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
    expected=expected_cases();index={r['case']:r for r in rows}
    if len(index)!=len(rows) or set(index)!=set(expected):raise ValueError('Missing/duplicate frozen Q2 case')
    grouped={hz:[] for hz in (540.,820.,1100.,1500.)};failures=[];records=[]
    for case,(hz,rpm) in expected.items():
        row=index[case]
        if float(row['mode_hz'])!=hz or float(row['rpm'])!=rpm or not math.isfinite(float(row['T_center_line_power'])) or float(row['T_center_line_power'])<0:raise ValueError('Pressure input changed')
        series={}
        for branch in ('T','S2'):
            path=root/f'{case}-{branch}.f32le';raw=path.read_bytes()
            if len(raw)!=48000*4:raise ValueError('Recorded steady-window frame count changed')
            x=np.frombuffer(raw,dtype='<f4')
            if not np.isfinite(x).all():raise ValueError('Non-finite output')
            peak=float(np.max(np.abs(x)));series[branch]=x
            if peak>LIMIT:failures.append({'case':case,'branch':branch,'peak':peak})
        bp={branch:band_power(x) for branch,x in series.items()}
        before=band_prominence(series['T'],hz);after=band_prominence(series['S2'],hz)
        record={'case':case,'mode_hz':hz,'rpm':rpm,'T_peak':float(np.max(np.abs(series['T']))),
                'S2_peak':float(np.max(np.abs(series['S2']))),'T_prominence_db':before,'S2_prominence_db':after,
                'prominence_reduction_db':before-after,
                'center_line_energy_ratio':line_power(series['S2'],hz)/max(line_power(series['T'],hz),1e-30),
                'neighbor_mean_power_T':float(np.mean([line_power(series['T'],hz+d) for d in (-80.,-60.,-40.,40.,60.,80.)])),
                'neighbor_mean_power_S2':float(np.mean([line_power(series['S2'],hz+d) for d in (-80.,-60.,-40.,40.,60.,80.)])),
                'absolute_band_db_changes':[float(10*math.log10(max(b,1e-30)/max(a,1e-30))) for a,b in zip(bp['T'],bp['S2'])]}
        records.append(record);grouped[hz].append(record['prominence_reduction_db'])
    modes={str(hz):{'cases':len(values),'median_reduction_db':float(np.median(values)),'passes_3db':bool(np.median(values)>=3)} for hz,values in grouped.items()}
    return {'schema':'c63.ar2.modal_pressure.v1','domains':'48k mono post-fixed-output pre-app-envelope, same level/gain/h; known-Q2 regressions, not unseen truth',
            'candidate':'S2 pressure-arrival branch versus T texture control','case_count':len(records),'cases':records,'modes':modes,
            'numeric_out_of_contract':failures,'overall_pass':len(failures)==0 and all(v['passes_3db'] for v in modes.values()),
            'physical_acoustic_similarity':'NOT_MEASURED'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    result=analyze(args.root)
    with args.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps({'case_count':result['case_count'],'modes':result['modes'],'numeric_failures':len(result['numeric_out_of_contract']),'overall_pass':result['overall_pass']} ,indent=2))
