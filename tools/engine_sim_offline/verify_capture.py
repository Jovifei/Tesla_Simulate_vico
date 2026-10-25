"""Validate actual data, not merely the simulator's process exit code."""
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np

def verify(root):
    root=Path(root)
    d=json.loads((root/'capture.json').read_text())
    ns=round(d['duration_s']*d['physics_fs']);na=round(d['duration_s']*d['audio_fs'])
    assert d['physics_frames']==ns and d['audio_frames']==na
    assert d['all_steps']==round((d['duration_s']+d['warmup_s'])*d['physics_fs'])
    assert (root/'pressure-input.f32le').stat().st_size==ns*18*4
    assert (root/'audio-taps.f32le').stat().st_size==na*6*4
    p=np.memmap(root/'pressure-input.f32le',dtype='<f4',mode='r',shape=(ns,18))
    a=np.memmap(root/'audio-taps.f32le',dtype='<f4',mode='r',shape=(na,6))
    assert np.isfinite(p).all() and np.isfinite(a).all()
    assert (p[:,:16]>0).all(), 'Absolute pressure must be positive Pa'
    assert np.isin(a[:,5],[0,1]).all()
    assert int(a[:,5].sum())==d['clip_count']
    assert float(abs(a[:,3]).max())==d['final_peak']
    assert (a[:,3]>=-1).all() and (a[:,3]<1).all()
    checks={};map_max=None
    for name in ['state.csv','dyno.csv']:
        with (root/name).open() as f:rows=list(csv.DictReader(f))
        x=np.array([[float(v) for v in row.values()] for row in rows])
        assert len(x)==round(d['duration_s']*100) and np.isfinite(x).all()
        assert np.allclose(np.diff(x[:,0]),.01,rtol=0,atol=1e-10)
        checks[name]={'rows':len(x),'first_t':x[0,0],'last_t':x[-1,0]}
        if name=='state.csv':map_max=max(float(row['map_pa']) for row in rows)
    physical={'status':'NOT_EVALUATED_NO_SIGNED_ROTATION_CAPTURE'}
    if (root/'physical-validity.json').exists():
        physical=json.loads((root/'physical-validity.json').read_text())
        assert physical['cw_all_capture'] and physical['max_omega_rad_s']<0
        assert physical['lit_cylinder_steps']>0,'No active combustion captured'
        assert map_max<2*101325,'Grossly impossible NA manifold pressure'
        physical['status']='BASIC_DIRECTION_COMBUSTION_NA_SANITY_ONLY_NOT_CALIBRATION'
    return {'scene':d['scene'],'physics_frames':ns,'audio_frames':na,'clip_count':d['clip_count'],
            'final_peak':d['final_peak'],'streams_finite':True,'tables':checks,
            'pressure_domain':'first16 absolutePa; last2 internal audio excitation',
            'audio_domain':'rawSum is resampled and1900Hz-prefiltered; not Pa',
            'state_time_note':'timestamp is 100us earlier than completed-step endpoint',
            'physical_sanity':physical,'map_max_pa':map_max,
            'files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.glob('*') if f.is_file()}}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('capture',nargs='+');parser.add_argument('--out',required=True)
    args=parser.parse_args();result=[verify(p) for p in args.capture]
    with open(args.out,'x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'validated':len(result),'total_seconds':sum(r['audio_frames']/44100 for r in result),
                      'clip_counts':[r['clip_count'] for r in result]}))
