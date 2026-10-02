import numpy as np

def raw_impulses(arrival_frames):
    values=np.asarray(arrival_frames)
    if values.ndim!=1 or not np.isfinite(values).all() or np.any(values<0) or np.any(values[1:]<values[:-1]):raise ValueError('Invalid raw arrival frame trace')
    return int(values.size)

def distinct_frame_impulses(arrival_frames):
    values=np.asarray(arrival_frames)
    raw_impulses(values)
    return int(np.unique(values).size)

def isolated_candidate(envelope,peak,lo,hi):
    env=np.asarray(envelope,dtype=np.float64)
    if env.ndim!=1 or not np.isfinite(env).all() or lo<0 or hi>len(env) or lo>peak or peak>=hi:raise ValueError('Invalid event observation')
    if peak-lo<12 or hi-peak<=25:return False
    value=env[peak]
    return value>0 and env[lo:peak].min()<=value*.5 and env[peak+1:hi].min()<=value*.5
