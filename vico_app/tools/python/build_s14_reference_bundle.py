"""Prepare original C63 D0/D1 for same-route comparison; never retune audio."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import numpy as np
import soundfile as sf

FRAMES = 1440000
PINNED = {
    'D0': '2fc4ef96d5ed88657f50da05ca0128d1615c118938e716912a937d3063d92767',
    'D1': '127f2c08a9977e43510633bbbad44ee989f7d112b79d5876bff99b99a7ef0b4f',
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require_new_directory(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(path)
    path.mkdir(parents=True, exist_ok=True)
    return path

def canonical_pcm(samples, rate, frames, *, allow_endpoint):
    x = np.asarray(samples)
    if rate != 48000 or x.ndim != 1 or x.size not in ({frames, frames+1} if allow_endpoint else {frames}):
        raise ValueError('Expected 48 kHz mono with the declared frame count')
    if not np.isfinite(x).all():
        raise ValueError('Non-finite source PCM')
    return x[:frames].astype('<f4')

def validate_material_sources(manifest):
    identities=manifest.get('D0_D1_D2',{})
    if any(label not in identities for label in PINNED):
        raise ValueError('Incomplete R/M source set')
    for label,expected in PINNED.items():
        identity=identities[label]
        if identity.get('sha256')!=expected or identity.get('frames')!=(FRAMES+1 if label=='D0' else FRAMES):
            raise ValueError('Frozen source identity mismatch: '+label)
    return identities

def build(experiment_root, output_root):
    manifest_path = Path(experiment_root)/'experiment.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    signals = {}
    for label, identity in validate_material_sources(manifest).items():
        if label not in PINNED:
            continue
        p = Path(identity['path'])
        if identity['sha256'] != PINNED[label] or sha(p) != PINNED[label]:
            raise ValueError('Frozen '+label+' identity changed')
        if label == 'D0':
            samples, rate = sf.read(p,dtype='float32',always_2d=False)
            if len(samples) != identity['frames']:
                raise ValueError('D0 container frame count mismatch')
        else:
            samples = np.frombuffer(p.read_bytes(),dtype='<f4'); rate = 48000
        signals[label] = canonical_pcm(samples,rate,FRAMES,allow_endpoint=label=='D0')
    out = Path(output_root).resolve()
    out.relative_to(Path(r'E:\Claude_allow\Download').resolve())
    require_new_directory(out)
    materials = {}
    for label, x in signals.items():
        name = 'R' if label=='D0' else 'M'
        (out/(name+'.f32le')).write_bytes(x.tobytes())
        sf.write(out/(name+'.wav'),x,48000,subtype='FLOAT')
        materials[name] = {'source':label,'source_sha256':PINNED[label],
            'pcm_sha256':sha(out/(name+'.f32le')),'wav_sha256':sha(out/(name+'.wav')),
            'frames':FRAMES,'presentation_gain':1.0,'peak':float(np.max(np.abs(x))),
            'rms_dbfs':float(20*np.log10(max(float(np.sqrt(np.mean(x.astype(float)**2))),1e-12)))}
    result = {'schema':'vico.s14.reference_bundle.v1','status':'PREPARED_WAITING_FOR_LISTENING',
        'sample_rate_hz':48000,'channels':1,'comparison_range':'[0,1440000)',
        'experiment_sha256':sha(manifest_path),'historical_80_40_binding':'UNBOUND',
        'normalization':'NONE','extra_envelope':'NONE','materials':materials,
        'routes':{key:'NOT_RUN' for key in ['desktop','phone_speaker','common_wired','car_bluetooth']}}
    (out/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--experiment-root',type=Path,required=True); p.add_argument('--output-root',type=Path,required=True)
    args=p.parse_args(); print(json.dumps(build(args.experiment_root,args.output_root),indent=2))
