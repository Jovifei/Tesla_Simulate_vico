"""Read-only prefix probes for offline S12 dependencies identified by remote review."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import inspect
import numpy as np

def prefix_metrics(a,b,frames):
    delta=np.asarray(a[:frames],dtype=float)-np.asarray(b[:frames],dtype=float)
    divergent=np.flatnonzero(np.any(np.abs(delta)>1e-12,axis=1)) if delta.ndim==2 else np.flatnonzero(np.abs(delta)>1e-12)
    return {'prefix_frames':frames,'max_abs':float(np.max(np.abs(delta))),
            'rms':float(np.sqrt(np.mean(delta**2))),
            'first_divergence_frame':int(divergent[0]) if divergent.size else None}

def full_chain_probes():
    from sound_sim.s12.acoustic_identity_v015 import render_realism_v10 as runtime
    from sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
    from sound_sim.s12.acoustic_identity_v015.acoustic_layers.shift_dynamics import detect_shift_events
    rate=48000; split=24000
    def make(seconds=1.,changed=None):
        count=int(seconds*rate)+1; time=np.arange(count)/rate
        rpm=np.full(count,5500.); load=np.full(count,.5); throttle=np.full(count,.5)
        if changed=='rpm':rpm[split+1:]=3500.
        if changed=='load':load[split+1:]=.9
        if changed=='throttle':throttle[split+1:]=.1
        return VehicleStateTrace(time,rpm,load,throttle,np.zeros(count)).validate()
    stages=[('idle_dynamics',runtime.apply_idle_dynamics),('afterfire',runtime.apply_afterfire),
            ('low_frequency_body',runtime.apply_low_frequency_body),('exhaust_rumble',runtime.apply_exhaust_rumble),
            ('shift_dynamics',runtime.apply_shift_dynamics),('pre_ptr_equalization',runtime.apply_pre_ptr_equalization)]
    result=[]
    for changed in ('rpm','load','throttle','length'):
        ta=make(); tb=make(2.) if changed=='length' else make(changed=changed)
        a=runtime._RENDERERS['c63_w204'](ta); b=runtime._RENDERERS['c63_w204'](tb)
        rows=[{'stage':'independent_source',**prefix_metrics(a.pressure,b.pressure,split)}]
        for name,fn in stages:
            a=fn(a,'c63_w204',ta,rate);b=fn(b,'c63_w204',tb,rate)
            rows.append({'stage':name,**prefix_metrics(a.pressure,b.pressure,split)})
        x=runtime._apply_frozen_ptr(a.pressure);y=runtime._apply_frozen_ptr(b.pressure)
        rows.append({'stage':'frozen_ptr',**prefix_metrics(x,y,split)})
        mono_a=x.mean(axis=1);mono_b=y.mean(axis=1)
        rows.append({'stage':'arithmetic_mono',**prefix_metrics(mono_a,mono_b,split)})
        rows.append({'stage':'fixed_gain',**prefix_metrics(mono_a*3.7075542301539652,mono_b*3.7075542301539652,split)})
        def events(t):
            return [{'frame':int(e.sample_index),'time_s':float(e.time_s)} for e in detect_shift_events(t,rate)]
        result.append({'case':'future_'+changed,'domain':'OFFLINE_SYNTHETIC_PREFIX_DIAGNOSIS',
                       'stages':rows,'detected_events_a':events(ta),'detected_events_b':events(tb),
                       'event_audio_vs_detection':'Combined shift layer recorded; independent fixed-plan event-tail test remains NOT_RUN'})
    return result

def shift_detector_and_tail_probes():
    from sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace,SourceRender
    from sound_sim.s12.acoustic_identity_v015.acoustic_layers import shift_dynamics as shifts
    rate=48000
    def make(seconds,recovery):
        time=np.arange(int(seconds*rate)+1)/rate
        rpm=np.interp(time,[0,.48,.54,seconds],[5500,5500,3500,3500])
        if recovery:
            mask=time>.6
            rpm[mask]=np.interp(time[mask],[.6,.8,seconds],[3500,5000,5000])
        return VehicleStateTrace(time,rpm,np.full(time.size,.5),np.full(time.size,.5),np.zeros(time.size))
    a=make(1.,False); b=make(1.,True)
    events_a=shifts.detect_shift_events(a,rate); events_b=shifts.detect_shift_events(b,rate)
    short=make(1.,False);long=make(2.,False)
    def render(trace):
        signal=np.repeat(np.sin(2*np.pi*110*trace.time_s)[:,None],2,axis=1)
        return SourceRender(signal,{'probe':signal},{})
    original=shifts.detect_shift_events
    try:
        shifts.detect_shift_events=lambda _trace,_rate:events_b
        x=shifts.apply_shift_dynamics(render(short),'c63_w204',short,rate)
        y=shifts.apply_shift_dynamics(render(long),'c63_w204',long,rate)
    finally:
        shifts.detect_shift_events=original
    return {'domain':'SYNTHETIC_DEPENDENCY_DIAGNOSIS','same_prefix_frames':28800,
            'past_detected_events_a':[int(e.sample_index) for e in events_a if e.sample_index<28800],
            'past_detected_events_b':[int(e.sample_index) for e in events_b if e.sample_index<28800],
            'fixed_plan_method':'Actual shift layer; detector dependency replaced in memory with the same immutable event tuple; file unchanged',
            'fixed_plan_tail_prefix':prefix_metrics(x.pressure,y.pressure,48000)}

def ptr_partition_probe():
    from runtime_ptr_adapter import RuntimePtrAdapter
    from s12_ptr_network import PtrNetworkConfig
    signal=np.sin(2*np.pi*110*np.arange(5760)/48000)
    whole=np.asarray(RuntimePtrAdapter().process(signal))
    rows=[]
    for block in (96,192,240,256,480,960):
        adapter=RuntimePtrAdapter(); output=[]
        for start in range(0,signal.size,block):output.extend(adapter.process(signal[start:start+block]))
        delta=np.asarray(output)-whole
        rows.append({'block_frames':block,'frames':len(output),'max_abs':float(np.max(np.abs(delta))),
                     'identical':bool(np.array_equal(output,whole))})
    files=[Path(inspect.getfile(RuntimePtrAdapter)),Path(inspect.getfile(PtrNetworkConfig)),PtrNetworkConfig().package_path]
    return {'scope':'EXISTING_RUNTIME_PTR_ADAPTER_ONLY','lookahead_samples_in_this_adapter':0,
            'delay_frames':{'upstream':8,'downstream':12},'rows':rows,
            'inputs':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}

def probe(source_root):
    sys.path.insert(0,str(Path(source_root).resolve()))
    from sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace, SourceRender
    from sound_sim.s12.acoustic_identity_v015.acoustic_layers import low_frequency_body as body, idle_dynamics as idle
    rate=48000; count=48000; split=24000
    time=np.arange(count)/rate
    signal=np.repeat(np.sin(2*np.pi*110*time)[:,None],2,axis=1)
    stems={key:signal for key in body._COMPONENT_INPUTS['c63_w204']['exhaust_pressure']}
    render=SourceRender(signal,stems,{})
    rpm_a=np.full(count,3000.); rpm_b=rpm_a.copy(); rpm_b[split:]=6000.
    def trace(rpm):
        return VehicleStateTrace(time,rpm,np.full(count,.5),np.full(count,.5),np.zeros(count))
    a=body.apply_low_frequency_body(render,'c63_w204',trace(rpm_a),rate).pressure
    b=body.apply_low_frequency_body(render,'c63_w204',trace(rpm_b),rate).pressure
    difference=float(np.max(np.abs(a[:split]-b[:split])))
    x=idle._mechanical_texture(count,rate,1.,.123)
    y=idle._mechanical_texture(count*2,rate,1.,.123)
    texture=float(np.max(np.abs(x[:split]-y[:split])))
    package=Path(source_root)/'sound_sim/s12/acoustic_identity_v015'
    inventory={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(package.rglob('*.py'))}
    return {'schema':'vico.s14.causality_audit.v2','domain':'SYNTHETIC_PREFIX_PROBES',
        'source_inventory':inventory,'probe_frames':count,'prefix_frames':split,
        'low_frequency_future_rpm_prefix_max_abs':difference,
        'low_frequency_future_dependency_detected':difference>1e-10,
        'mechanical_texture_total_length_prefix_max_abs':texture,
        'mechanical_texture_total_length_dependency_detected':texture>1e-10,
        'shift_dependency':'SOURCE_INSPECTION: gradient plus future recovery maximum; runtime event contract required',
        'block_invariance':'PTR adapter tested; complete upstream array API has no persisted state interface and remains NOT_RUN',
        'whole_source_prefix':full_chain_probes(),
        'shift_detection_vs_fixed_plan_tail':shift_detector_and_tail_probes(),
        'ptr_partition_probe':ptr_partition_probe(),
        'T1':'NOT_IMPLEMENTED','source_changes':'NONE'}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.resolve().relative_to(Path(r'E:\Claude_allow\Download').resolve())
    if args.output.exists(): raise FileExistsError(args.output)
    result=probe(args.source_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_inventory'},indent=2))
