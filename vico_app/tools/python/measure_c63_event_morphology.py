import math
from collections import Counter
def isolated_peak(env,peak,lo,hi):
    if not all(math.isfinite(float(x)) for x in env):raise ValueError('Nonfinite envelope')
    if lo<0 or hi>len(env) or not lo<=peak<hi:raise ValueError('Malformed event window')
    if peak-lo<12 or hi-peak<=25:return False
    value=env[peak]
    return value>0 and min(env[lo:peak])<=value*.5 and min(env[peak+1:hi])<=value*.5
def impulse_counts(frames):
    if any(frame<0 for frame in frames) or any(b<a for a,b in zip(frames,frames[1:])):raise ValueError('Event frames must be monotonic')
    return {'raw_arrivals':len(frames),'distinct_impulses':len(set(frames))}
