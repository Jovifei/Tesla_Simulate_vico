from pathlib import Path
import argparse,csv,json,math
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter,find_peaks,sosfilt
from measure_c63_ar2_event_morphology import isolated_candidate

def envelope(pcm,sample_rate_hz):
    x=np.asarray(pcm,dtype=np.float64)
    if x.ndim!=1 or sample_rate_hz!=48000 or not np.isfinite(x).all():raise ValueError('Invalid mono event PCM')
    filtered=sosfilt(butter(4,[40,4000],fs=sample_rate_hz,btype='bandpass',output='sos'),x)
    count=len(filtered)//240
    return np.sqrt(np.mean(filtered[:count*240].reshape(-1,240)**2,axis=1))

def summarize(env,sample_rate_hz):
    env=np.asarray(env,dtype=float)
    if env.ndim!=1 or not np.isfinite(env).all() or len(env)<52 or env.max()<=1e-10:raise ValueError('Silent or undersized acoustic reference')
    peaks,_=find_peaks(env,distance=4,prominence=max(float(np.median(env))*.75,1e-8))
    detected=[];censored=0
    for peak in peaks:
        lo=max(0,int(peak)-12);hi=min(len(env),int(peak)+26)
        if not isolated_candidate(env,int(peak),lo,hi):
            if peak-lo<12 or hi-peak<=25:censored+=1
            continue
        value=env[peak];base=min(float(env[lo:peak].min()),float(env[peak+1:hi].min()))
        signal=max(value-base,1e-12)
        attack=np.nan;tail=np.nan
        before=np.flatnonzero(env[lo:peak+1] >= base+signal*.10)
        up=np.flatnonzero(env[lo:peak+1] >= base+signal*.90)
        if before.size and up.size:attack=(int(up[0])-int(before[0]))*240/sample_rate_hz*1000
        after=env[peak+1:hi]
        tail_indices=np.flatnonzero(after <= base+signal*.10)
        if tail_indices.size:tail=(int(tail_indices[0])+1)*240/sample_rate_hz*1000
        else:censored+=1
        detected.append({'frame_5ms':int(peak),'peak':float(value),'prominence':float(value-base),
                         'attack_ms':attack if math.isfinite(attack) else None,'tail_10pct_ms':tail if math.isfinite(tail) else None})
    intervals=np.diff([event['frame_5ms'] for event in detected])*240/sample_rate_hz*1000
    valid_attack=[e['attack_ms'] for e in detected if e['attack_ms'] is not None]
    valid_tail=[e['tail_10pct_ms'] for e in detected if e['tail_10pct_ms'] is not None]
    amps=np.asarray([e['prominence'] for e in detected])
    median=float(np.median(amps)) if amps.size else None
    return {'detected_peaks':int(len(peaks)),'distinct_peaks':len(detected),'censored':censored,
            'events':detected,'attack_ms_median':float(np.median(valid_attack)) if valid_attack else None,
            'tail_10pct_ms_median':float(np.median(valid_tail)) if valid_tail else None,
            'interval_ms_median':float(np.median(intervals)) if intervals.size else None,
            'interval_cv':float(intervals.std()/intervals.mean()) if intervals.size and intervals.mean()>0 else None,
            'relative_amplitude_cv':float(amps.std()/median) if median and median>0 else None,
            'scope':'Unlabelled local transient candidates; not confirmed vehicle combustion/backfire events'}

def extract(bundle):
    receipt=json.loads((bundle/'reference_clip_receipt.json').read_text());clip=receipt['clips']['ref_afterfire.wav']
    path=bundle/clip['filename']
    import hashlib
    if hashlib.sha256(path.read_bytes()).hexdigest()!=clip['sha256']:raise ValueError('Reference hash mismatch')
    sr,pcm=wavfile.read(path)
    if sr!=48000 or len(pcm)!=288000:raise ValueError('Reference window contract changed')
    x=pcm.astype(np.float64)/(max(abs(np.iinfo(pcm.dtype).min),np.iinfo(pcm.dtype).max) if np.issubdtype(pcm.dtype,np.integer) else 1.0)
    mono=x.mean(axis=1) if x.ndim==2 else x
    return {'schema':'c63.ar2.event_reference.v1','clip_sha256':clip['sha256'],'evidence':clip['evidence_level'],'rights':clip['rights_status'],
            'synchronization':'UNSYNCHRONIZED_R2','calibration':summarize(envelope(mono[:144000],sr),sr),
            'same_source_time_holdout':summarize(envelope(mono[144000:],sr),sr),'cross_vehicle_generalization':'NOT_EVIDENCED',
            'labels':'UNVERIFIED_TRANSIENTS_NOT_CONFIRMED_COMBUSTION'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise FileExistsError(a.out)
    result=extract(a.bundle)
    with a.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps({k:(v if k not in ('calibration','same_source_time_holdout') else {j:u for j,u in v.items() if j!='events'}) for k,v in result.items()},indent=2))
