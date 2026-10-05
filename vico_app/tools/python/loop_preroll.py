"""Versioned offline loop authoring only; reference assets are never overwritten."""
import math
import numpy as np

def make_period_preserving_loop(signal,sample_rate,*,target_seconds=.36,overlap_seconds=.008):
    """Keep N and body phase. Extra pre-roll supplies the tail-to-start overlap."""
    x=np.asarray(signal,dtype=np.float32)
    if x.ndim!=1 or not np.isfinite(x).all() or sample_rate not in (48000,96000):
        raise ValueError('invalid finite mono source')
    if not math.isfinite(target_seconds) or not math.isfinite(overlap_seconds) or not 0<overlap_seconds<target_seconds/4:
        raise ValueError('invalid loop/overlap duration')
    count=int(round(target_seconds*sample_rate));overlap=int(round(overlap_seconds*sample_rate))
    if overlap<2 or count<=overlap or count+overlap>x.size:raise ValueError('missing source pre-roll')
    source=x[-(count+overlap):].copy()
    w=(.5-.5*np.cos(np.linspace(0,np.pi,overlap))).astype(np.float32)
    cross=(np.float32(1)-w)*source[-overlap:]+w*source[:overlap]
    loop=np.concatenate([source[overlap:-overlap],cross]).astype(np.float32)
    dc=np.mean(loop,dtype=np.float32)
    if not np.isfinite(dc):raise ValueError('nonfinite DC accumulator')
    loop-=dc
    if not np.isfinite(loop).all():raise ValueError('nonfinite loop after DC removal')
    return loop,{'schema':'vico.loop-preroll.candidate.v1','sample_count':count,'overlap_samples':overlap,
                 'period_seconds':count/sample_rate,'sample_rate_hz':sample_rate,'dc_removed':float(dc),
                 'window':'cosine exact endpoints','body_samples_preserved_before_dc':count-overlap,
                 'gain':'unchanged; full-bank peak gate still required'}
