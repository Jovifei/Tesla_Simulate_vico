"""Dependency-light acoustic comparator core; optional adapters live outside this module."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Sequence
import numpy as np

BANDS = ((20.,60.),(60.,120.),(120.,250.),(250.,400.),(400.,1000.),(1000.,4000.),(4000.,5500.),(5500.,12000.))
BAND_NAMES = ("20_60","60_120","120_250","250_400","400_1000","1000_4000","4000_5500","5500_12000")

@dataclass(frozen=True)
class ComparisonCase:
    vehicle_id: str
    scenario: str
    reference_id: str | None
    candidate_id: str
    sample_rate_hz: int
    reference_rpm: tuple[float,float]
    candidate_rpm: tuple[float,float]
    reference_load: tuple[float,float]
    candidate_load: tuple[float,float]
    analysis_domain: str

def _mono(x: np.ndarray) -> np.ndarray:
    value=np.asarray(x,dtype=np.float64)
    if value.ndim==2: value=value.mean(axis=1)
    if value.ndim!=1 or value.size<8 or not np.isfinite(value).all(): raise ValueError("signal must be finite mono/stereo audio")
    return value - value.mean()

def _features(x: np.ndarray, sr: int) -> tuple[dict[str,float], np.ndarray, np.ndarray]:
    n=x.size; spec=np.abs(np.fft.rfft(x))**2; freq=np.fft.rfftfreq(n,1/sr); total=max(float(spec.sum()),1e-18)
    bands={name:float(spec[(freq>=lo)&(freq<hi)].sum()/total) for name,(lo,hi) in zip(BAND_NAMES,BANDS)}
    centroid=float((freq*spec).sum()/total)
    rolloff=float(freq[min(len(freq)-1,int(np.searchsorted(np.cumsum(spec),.85*total)))])
    return {"rms_db":20*math.log10(max(float(np.sqrt(np.mean(x*x))),1e-12)),"centroid_hz":centroid,"rolloff_hz":rolloff,**bands},spec,freq

def _events(x: np.ndarray, eligible: np.ndarray | None) -> dict[str,int]:
    env=np.abs(x); threshold=max(float(np.quantile(env,.995)),float(env.mean()+4*env.std()))
    starts=np.flatnonzero((env>=threshold)&np.r_[True,env[:-1]<threshold]); kept=[]; gap=max(1,x.size//100)
    for i in starts:
        if not kept or int(i)-kept[-1]>=gap: kept.append(int(i))
    wrong=0 if eligible is None else sum(not bool(eligible[min(i,eligible.size-1)]) for i in kept)
    return {"event_count":len(kept),"wrong_condition_event_count":int(wrong)}

def compare_signals(reference: np.ndarray | None, candidate: np.ndarray, case: ComparisonCase, *, candidate_scenario: str | None=None, candidate_domain: str="unaltered_analysis_signal", eligible_event_mask: np.ndarray | None=None) -> dict[str,object]:
    if case.analysis_domain!="unaltered_analysis_signal" or candidate_domain!="unaltered_analysis_signal": raise ValueError("review-gain copy is forbidden for raw analysis")
    if candidate_scenario is not None and candidate_scenario!=case.scenario: raise ValueError("scenario mismatch")
    c=_mono(candidate); rpm_ok=abs(case.reference_rpm[0]-case.candidate_rpm[0])<=max(100.,.1*case.reference_rpm[0]) and abs(case.reference_rpm[1]-case.candidate_rpm[1])<=max(100.,.1*case.reference_rpm[1])
    cf,cs,fr=_features(c,case.sample_rate_hz)
    if reference is None or case.reference_id is None:
        return {"case":case.__dict__,"uncertainty":{"reference_missing":True,"digital_domain_relative_only":True},"spectral":{"log_distance":None},"bands":{},"order":{"rpm_compatible":rpm_ok},"events":{"candidate_event_count":_events(c,eligible_event_mask)["event_count"],"wrong_condition_event_count":_events(c,eligible_event_mask)["wrong_condition_event_count"]}}
    r=_mono(reference); n=min(r.size,c.size); r,c=r[:n],c[:n]
    shift=int(np.argmax(np.correlate(r[:min(n,8192)],c[:min(n,8192)],"full"))-(min(n,8192)-1)); c=np.roll(c,shift)
    rf,rs,fr=_features(r,case.sample_rate_hz); cf,cs,fr=_features(c,case.sample_rate_hz)
    norm=lambda z:z/max(float(np.linalg.norm(z)),1e-18)
    distance=float(np.linalg.norm(norm(np.log1p(rs))-norm(np.log1p(cs))))
    ev=_events(c,eligible_event_mask)
    bands={name:{"reference_share":rf[name],"candidate_share":cf[name],"delta":cf[name]-rf[name],"warning":"upstream perceptual compensation; outside validated radiation band; not physical radiation validation" if name=="5500_12000" else None} for name in BAND_NAMES}
    return {"case":case.__dict__,"uncertainty":{"reference_missing":False,"digital_domain_relative_only":True},"alignment":{"applied_shift_samples":shift},"spectral":{"log_distance":distance,"centroid_delta_hz":cf["centroid_hz"]-rf["centroid_hz"],"rolloff_delta_hz":cf["rolloff_hz"]-rf["rolloff_hz"]},"bands":bands,"loudness":{"delta_db":cf["rms_db"]-rf["rms_db"]},"order":{"rpm_compatible":rpm_ok},"psychoacoustics":{"sharpness_proxy_delta":cf["centroid_hz"]-rf["centroid_hz"]},"events":{"candidate_event_count":ev["event_count"],"wrong_condition_event_count":ev["wrong_condition_event_count"]}}
