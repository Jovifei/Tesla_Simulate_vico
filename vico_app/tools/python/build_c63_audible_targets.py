"""Frozen relative targets from verified R2 clips, never OEM/RPM calibration."""
from pathlib import Path
import hashlib,json,math,argparse
import numpy as np
from scipy.signal import welch,hilbert,butter,sosfiltfilt
from scipy.io import wavfile

RATE=48000
BANDS={'low':(20,200),'mid':(200,1000),'high':(1000,4000),'ultrahigh':(4000,12000)}
KEYS=list(BANDS)+[f'prom{hz}' for hz in (540,820,1100,1500)]+['mod1_10','mod10_60','mod60_200','env_cv']
WEIGHTS=np.array([.25/4]*4+[.35/4]*4+[.25/3]*3+[.15])

def validate_windows(rows):
    ids=[r['id'] for r in rows]
    if not rows or len(ids)!=len(set(ids)):raise ValueError('Missing/duplicate window identity')
    for r in rows:
        if r['split'] not in ('calibration','holdout','context') or not isinstance(r['start_sample'],int) or not isinstance(r['end_sample'],int) or r['start_sample']<0 or r['start_sample']>=r['end_sample']:raise ValueError('Invalid frozen range')
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if a['source_sha256']==b['source_sha256'] and max(a['start_sample'],b['start_sample'])<min(a['end_sample'],b['end_sample']):raise ValueError('Overlapping source samples cannot be independent windows')

def features(pcm):
    x=np.asarray(pcm,dtype=np.float64)
    if x.ndim!=1 or len(x)<24000 or not np.isfinite(x).all():raise ValueError('Invalid feature PCM')
    rms=float(np.sqrt(np.mean(x*x)))
    if rms<=1e-10:raise ValueError('Silent input is not an improvement')
    # Gain invariance is for analysis only; never change a production waveform.
    x=x/rms
    f,p=welch(x,fs=RATE,nperseg=8192,noverlap=6144,detrend=False)
    total=float(p[(f>=20)&(f<12000)].sum())
    if total<=1e-14:raise ValueError('No usable acoustic-band content')
    result={'rms':rms}
    for name,(lo,hi) in BANDS.items():result[name]=float(10*np.log10(max(float(p[(f>=lo)&(f<hi)].sum())/total,1e-16)))
    for hz in (540,820,1100,1500):
        center=p[(f>=hz-15)&(f<=hz+15)]
        neighbors=p[((f>=hz-80)&(f<hz-30))|((f>hz+30)&(f<=hz+80))]
        result[f'prom{hz}']=float(10*np.log10(max(float(center.mean()),1e-16)/max(float(neighbors.mean()),1e-16)))
    env=sosfiltfilt(butter(6,800,fs=RATE,output='sos'),np.abs(hilbert(x)))[2400:-2400]
    env=env[:len(env)//24*24].reshape(-1,24).mean(axis=1)
    normalized=env/max(float(env.mean()),1e-12)
    result['env_cv']=float(normalized.std())
    mf,mp=welch(normalized-1,fs=2000,nperseg=min(4096,len(env)),detrend=False)
    mod_total=float(mp[(mf>=1)&(mf<200)].sum())
    for key,(lo,hi) in zip(KEYS[8:11],((1,10),(10,60),(60,200))):
        result[key]=-160.0 if mod_total<1e-14 else float(10*np.log10(max(float(mp[(mf>=lo)&(mf<hi)].sum())/mod_total,1e-16)))
    return result

def feature_distance(a,b,scales):
    if not all(k in a and k in b and k in scales for k in KEYS):raise ValueError('Missing feature/protection band')
    if any(not math.isfinite(scales[k]) or scales[k]<=0 for k in KEYS):raise ValueError('Invalid frozen feature scale')
    values=np.array([(a[k]-b[k])/scales[k] for k in KEYS],dtype=np.float64)
    if not np.isfinite(values).all():raise ValueError('Invalid feature value')
    return float(np.sqrt(np.sum(WEIGHTS*values*values)))

def improved(before,after):
    return math.isfinite(before) and math.isfinite(after) and before>1e-12 and 0<=after<=before*.8

def read_clip(path,expected):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Reference clip identity changed')
    sr,pcm=wavfile.read(path)
    if sr!=RATE or len(pcm)!=288000:raise ValueError('Reference clip contract changed')
    if np.issubdtype(pcm.dtype,np.integer):pcm=pcm.astype(np.float64)/max(abs(np.iinfo(pcm.dtype).min),np.iinfo(pcm.dtype).max)
    else:pcm=pcm.astype(np.float64)
    return pcm.mean(axis=1) if pcm.ndim==2 else pcm

def build(bundle):
    receipt=json.loads((bundle/'reference_clip_receipt.json').read_text())
    # Absolute source ranges are deduplicated, including the full/high overlap.
    specs={'ref_steady_low.wav':[(0,3,'calibration'),(3,6,'holdout')],
           'ref_steady_mid.wav':[(0,3,'calibration'),(3,6,'holdout')],
           'ref_full_pull.wav':[(0,3,'calibration'),(3,5,'holdout')],
           'ref_steady_high.wav':[(1,3.5,'calibration'),(3.5,6,'holdout')],
           # Verified clip contains a fading first~1.2s then exact silence, not a usable hot-idle holdout.
           'ref_hot_idle.wav':[(0,6,'context')],
           'ref_afterfire.wav':[(0,3,'calibration'),(3,6,'holdout')],
           'ref_shift.wav':[(0,6,'context')]}
    rows=[]
    for filename,ranges in specs.items():
        meta=receipt['clips'][filename];pcm=read_clip(bundle/filename,meta['sha256'])
        for lo,hi,split in ranges:
            start,end=round(lo*RATE),round(hi*RATE)
            rows.append({'id':f'{filename}:{lo}-{hi}','filename':filename,'clip_sha256':meta['sha256'],
                         'source_sha256':meta['source_sha256'],'source_id':meta['source_id'],'split':split,
                         'start_sample':meta['start_sample']+start,'end_sample':meta['start_sample']+end,
                         'clip_offset_start':start,'clip_offset_end':end,'features':features(pcm[start:end]),
                         'quality_note':'EXCLUDED_IDLE_LABEL_SILENT_TAIL' if filename=='ref_hot_idle.wav' else 'RELATIVE_UNSYNCHRONIZED_REFERENCE'})
    validate_windows(rows)
    # Afterfire and shift never enter the sustained-sound fitting objective.
    sustained=[r for r in rows if r['split']=='calibration' and r['filename'] not in ('ref_afterfire.wav','ref_shift.wav')]
    scales={k:max(float(np.std([r['features'][k] for r in sustained])),.05 if k=='env_cv' else 1.0) for k in KEYS}
    return {'schema':'c63.ar1.relative_targets.v1','scope':'R2_UNVERIFIED_LOCAL_UNSYNCHRONIZED_DIAGNOSTIC_ONLY',
            'raw_source_paths_currently_available':False,'windows':rows,'feature_keys':KEYS,'weights':WEIGHTS.tolist(),'calibration_scales':scales,
            'criterion':'heldout feature distance improves >=20%; pure gain/silence is not improvement',
            'fit_budget':32,'decay_scale_domain':[.25,1],'mode_centers_hz':[540,820,1100,1500],
            'event_response_support':'NOT_EVALUATED','idle_reference_support':'INSUFFICIENT_SILENT_TAIL',
            'source_split_boundary':'same-source time holdouts, not cross-vehicle validation'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    result=build(args.bundle)
    with args.out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print('Frozen',len(result['windows']),'non-overlapping windows; outputSHA',hashlib.sha256(args.out.read_bytes()).hexdigest())
