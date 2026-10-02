"""One standalone-stem conversion, never output RMS/peak normalization."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
from scipy.signal import lfilter,welch

def fixed_scale(reference,raw,start,end):
    reference=np.asarray(reference,dtype=float);raw=np.asarray(raw,dtype=float)
    if reference.ndim!=1 or raw.shape!=reference.shape or not np.isfinite(reference).all() or not np.isfinite(raw).all() or not 0<=start<end<=len(raw):raise ValueError('Texture identity/range mismatch')
    target=float(np.sqrt(np.mean(reference[start:end]**2)));original=float(np.sqrt(np.mean(raw[start:end]**2)))
    if min(target,original)<=1e-12:raise ValueError('Silent texture cannot calibrate')
    return target/original

def modulation(pcm):
    f,p=welch(pcm,fs=48000,nperseg=24000,noverlap=12000,detrend=False)
    # Texture itself is the temporal friction fluctuation, not a mixed-audio envelope.
    bands=[float(p[(f>=lo)&(f<hi)].sum()) for lo,hi in ((0,10),(10,30),(30,60),(60,200))]
    return np.asarray(bands)/sum(bands)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(args.source.parent))
    from acoustic_identity_v015.synth_primitives import mechanical_texture
    reference=mechanical_texture(1440000,48000,.08,5.9)
    mask=(1<<64)-1;state=5900000;random=np.empty(len(reference))
    for n in range(len(random)):
        state^=(state<<13)&mask;state^=state>>7;state^=(state<<17)&mask
        random[n]=(state>>11)/9007199254740992*2-1
    raw=lfilter(np.ones(800)/800,[1],random)
    old=lfilter([1/800],[1,-799/800],random)
    start,end=48000,1392000
    scale=fixed_scale(reference,raw,start,end);scaled=raw*scale
    target=modulation(reference[start:end]);before=float(np.linalg.norm(modulation(old[start:end])-target));after=float(np.linalg.norm(modulation(scaled[start:end])-target))
    result={'schema':'c63.ar1.texture_transfer.v1','scope':'STANDALONE_SOURCE_TEXTURE_NOT_MIXED_AUDIO','seed':5900000,'frames':1440000,
            'steady_range':[start,end],'window':800,'source_sha256':hashlib.sha256((args.source/'synth_primitives.py').read_bytes()).hexdigest(),
            'scale':scale,'unscaled_rms':float(np.sqrt(np.mean(raw[start:end]**2))),'target_rms':float(np.sqrt(np.mean(reference[start:end]**2))),
            'scaled_rms':float(np.sqrt(np.mean(scaled[start:end]**2))),'modulation_bands_hz':[[0,10],[10,30],[30,60],[60,200]],
            'reference_modulation':target.tolist(),'old_distance':before,'new_distance':after,'modulation_improvement':1-after/before,
            'coefficient_basis':'Fixed standalone steady RMS only; no whole-mix RMS, safety peak or device gain used',
            'source_policy':'Causal rectangle replaces centered convolution; no runtime peak normalization'}
    with args.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2))
