"""One bounded HY1 fit. No replayed fit, live normalization, or safety-set feedback."""
from pathlib import Path
import argparse,csv,hashlib,json,math,struct
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import fftconvolve,welch,lfilter
from scipy.stats import wasserstein_distance
from build_c63_hybrid_targets import minimum_phase_kernel,features,FEATURE_KEYS,CONTROL_HZ,SPECTRAL_EDGES_HZ
from build_c63_audible_targets import read_clip
from fit_c63_bark_modes import original_output
from c63_hybrid_event_kernel import event_bases
from extract_c63_ar2_events import envelope,summarize

RATE=48000
SEEDS=(5900067,5900017,5900023)

class FitBudget:
    def __init__(self,maximum,journal=None):
        if not isinstance(maximum,int) or not 1<=maximum<=64:raise ValueError('Invalid fit budget')
        self.maximum=maximum;self.count=0;self.history=[];self.journal=journal
        if journal is not None:Path(journal).open('x').close()
    def _write(self,row):
        if self.journal is not None:
            with Path(self.journal).open('a',encoding='utf-8') as out:out.write(json.dumps(row,allow_nan=False)+'\n')
    def evaluate(self,parameters,objective):
        p=np.asarray(parameters,dtype=float)
        if p.ndim!=1 or not p.size or not np.isfinite(p).all():raise ValueError('Invalid fit parameters')
        if self.count>=self.maximum:raise RuntimeError('Fit budget exhausted; no restart')
        self.count+=1;self._write({'attempt':self.count,'parameters':p.tolist(),'status':'STARTED'})
        result=objective(p)
        if not math.isfinite(result['score']):raise ValueError('Nonfinite objective')
        row={'evaluation':self.count,'parameters':p.tolist(),**result};self.history.append(row);self._write(row)
        if self.journal is not None and (self.count==1 or self.count%5==0):print(f'[{self.count}/{self.maximum}] objective={result["score"]:.6f}',flush=True)
        return result

def improves(before,after):return math.isfinite(before) and math.isfinite(after) and before>1e-12 and 0<=after<=.8*before

def distribution_distance(reference,candidate,scales,weights,candidate_weights=None):
    if not reference or not candidate:raise ValueError('Empty feature distribution')
    total=0.0
    for key,weight in weights.items():
        if key not in scales or not math.isfinite(scales[key]) or scales[key]<=0:raise ValueError('Missing frozen scale')
        x=np.asarray([r[key] for r in reference],float);y=np.asarray([r[key] for r in candidate],float)
        if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Nonfinite features')
        total+=weight*(wasserstein_distance(x,y,v_weights=candidate_weights)/scales[key])**2
    return float(math.sqrt(total))

def pack_profile(periodic,bases,source_scale,event_scale,fraction,event_fraction,weights,reference_hash,seeds=SEEDS):
    arrays=[np.asarray(periodic,dtype='<f8'),*[np.asarray(x,dtype='<f8') for x in bases]]
    if [len(x) for x in arrays]!=[2048,12288,12288,12288] or not all(np.isfinite(x).all() for x in arrays):raise ValueError('Invalid HY1 kernels')
    header=b'C63HY1V1'+struct.pack('<2i8d3q',2048,12288,source_scale,event_scale,fraction,event_fraction,*weights,*seeds)+bytes.fromhex(reference_hash)
    result=header+b''.join(x.tobytes() for x in arrays)
    if len(result)!=311432:raise ValueError('HY1 binary contract changed')
    return result

def coordinate_fit(initial,bounds,steps,budget,objective):
    best=np.asarray(initial,float).copy();result=budget.evaluate(best,objective)
    for step in steps:
        for index in range(len(best)):
            for sign in (-1,1):
                if budget.count>=budget.maximum:return best,result
                proposed=best.copy();proposed[index]=np.clip(proposed[index]+sign*step[index],*bounds[index])
                if np.array_equal(proposed,best):continue
                trial=budget.evaluate(proposed,objective)
                if trial['score']<result['score']:best=proposed;result=trial
    return best,result

def compose(data,bark,event=None):
    x=data[:,0]+bark;x=x+data[:,2];x=x+data[:,3];x=x+(data[:,4] if event is None else event)
    return x+data[:,5]+data[:,6]

def noise_weights(levels):
    smooth=gaussian_filter1d(levels,.9,mode='nearest');hz=np.array([315.,800.,2000.,5000.])
    gains=10**(np.interp(np.log(hz),np.log(CONTROL_HZ),smooth)/20)*np.sqrt(hz/315)
    return gains/np.linalg.norm(gains)

def held_amplitude(impulses):
    indexes=np.maximum.accumulate(np.where(impulses>0,np.arange(len(impulses)),0))
    return impulses[indexes]

def layer(data,kernel,weights,fraction,scale):
    impulse=data[:,7]*data[:,12]
    periodic=fftconvolve(impulse,kernel,mode='full')[:len(data)]*math.sqrt(1-fraction)
    colored=data[:,13:17]@weights
    random=np.sqrt(fraction*data[:,9]*4/(60*RATE))*held_amplitude(data[:,7])*data[:,12]*colored
    return scale*(periodic+random)*.125*(.60+.40*data[:,11])*.70

def load_fixtures(root):
    rows=list(csv.DictReader((root/'fixture.tsv').open(),delimiter='\t'));result=[]
    expected=[f'steady_{float(r)}_{l}' for r in (700,1400,2200,3200,4300,5500,6800,7200) for l in (.32,.92)]+['driven_ramp','event_background']
    if [row['id'] for row in rows]!=expected:raise ValueError('Missing/duplicate/reordered preregistered fixture')
    for row in rows:
        path=root/(row['id']+'.f64le');data=np.fromfile(path,dtype='<f8').reshape(-1,20)
        pcm=np.fromfile(root/(row['id']+'.f32le'),dtype='<f4').astype(float)
        if len(data)!=int(row['frames']) or len(pcm)!=len(data) or not np.isfinite(data).all() or not np.isfinite(pcm).all():raise ValueError('Fixture contract mismatch')
        if row['id']=='event_background' and np.any(data[:,4]!=0):raise ValueError('Event-off background contains event signal')
        result.append({'id':row['id'],'data':data,'pcm':pcm,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if len(result)!=18:raise ValueError('Missing fixed fixture')
    return result

def transfer_db(hz):
    impulse=np.zeros(65536);impulse[0]=1
    spectrum=np.abs(np.fft.rfft(original_output(impulse,np.zeros_like(impulse))))
    f=np.fft.rfftfreq(len(impulse),1/RATE)
    return 20*np.log10(np.maximum(np.interp(hz,f,spectrum),1e-12))

def groups_distance(rows,candidate,scales,weights,sample_weights):
    groups={}
    for name in sorted({r['filename'] for r in rows}):
        groups[name]=distribution_distance([r['features'] for r in rows if r['filename']==name],candidate,scales,weights,sample_weights)
    return groups

def event_descriptors(pcm,known_frames=None,episode_labels=None):
    env=envelope(pcm,RATE);report=summarize(env,RATE);events=report['events'];kept=[];false=0
    frames=np.asarray(known_frames if known_frames is not None else [],dtype=np.int64);used=set()
    for event in events:
        frame=event['frame_5ms']*240
        if known_frames is not None:
            prior=[int(v) for v in frames[(frames+212<=frame)&(frame<=frames+212+12288)] if int(v) not in used]
            if not len(prior):false+=1;continue
            used.add(prior[-1])
            event={**event,'episode':int(episode_labels[prior[-1]]) if episode_labels is not None else 1}
        else:event={**event,'episode':1}
        kept.append(event)
    attacks=[e['attack_ms'] for e in kept if e['attack_ms'] is not None]
    tails=[e['tail_10pct_ms'] for e in kept if e['tail_10pct_ms'] is not None]
    energies=[]
    for e in kept:
        if e['tail_10pct_ms'] is None:continue
        i=e['frame_5ms'];tail=env[i+1:min(i+26,len(env))]
        energies.append(float(np.sum(tail*tail)/max(env[i]**2,1e-30)*5))
    intervals=[]
    for a,b in zip(kept,kept[1:]):
        delta=(b['frame_5ms']-a['frame_5ms'])*5
        if a['episode']==b['episode'] and delta<=1000:intervals.append(delta)
    amp=[e['prominence'] for e in kept]
    def normalized(x):return (np.asarray(x,float)/max(float(np.median(x)),1e-12)).tolist() if x else []
    return {'attack':attacks,'tail':tails,'tail_energy':energies,'interval':normalized(intervals),'amplitude':normalized(amp),
            'matched':len(kept),'false_peaks':false,'censored':report['censored']}

def event_distance(reference,candidate,scales):
    distances={}
    for name in ('attack','tail','interval','amplitude'):
        if not reference[name] or not candidate[name]:return 1e6,{k:1e6 for k in ('attack','tail','interval','amplitude')}
        value=(wasserstein_distance(reference[name],candidate[name])/scales[name])**2
        if name=='tail':
            if not reference['tail_energy'] or not candidate['tail_energy']:return 1e6,{k:1e6 for k in ('attack','tail','interval','amplitude')}
            value=.5*(value+(wasserstein_distance(reference['tail_energy'],candidate['tail_energy'])/scales['tail_energy'])**2)
        distances[name]=float(math.sqrt(value))
    return float(math.sqrt(np.mean(np.square(list(distances.values()))))),distances

def old_event_energy():
    x=np.zeros(12288);x[0]=1;result=np.zeros_like(x)
    for hz,tau,weight in ((90,.040,1),(850,.012,.42)):
        radius=math.exp(-1/(tau*RATE));result+=weight*lfilter([math.sin(2*math.pi*hz/RATE)],[1,-2*radius*math.cos(2*math.pi*hz/RATE),radius*radius],x)
    return float(np.sum((result*.81)**2))

def run(args):
    targets=json.loads(args.targets.read_text());reference_hash=hashlib.sha256(args.targets.read_bytes()).hexdigest()
    args.out.mkdir(parents=True,exist_ok=True)
    if (args.out/'continuous-history.jsonl').exists() or (args.out/'frozen-profile.json').exists():raise FileExistsError('Existing fit; no restart')
    all_cases=load_fixtures(args.fixtures);cases=[c for c in all_cases if c['id']!='event_background']
    weights=targets['weights'];scales=targets['calibration_scales']
    cal=[r for r in targets['windows'] if r['id'] in targets['sustained_window_ids'] and r['split']=='calibration']
    reference=[r['features'] for r in cal];sample_weights=np.array([.75/16]*16+[.25])
    baseline=[features(c['pcm'][48000:] if c['id'].startswith('steady') else c['pcm'][24000:]) for c in cases]
    before=distribution_distance(reference,baseline,scales,weights,sample_weights);before_groups=groups_distance(cal,baseline,scales,weights,sample_weights)
    centers=np.sqrt(SPECTRAL_EDGES_HZ[:-1]*SPECTRAL_EDGES_HZ[1:])
    density=np.mean([[r['features'][f'spec{i}'] for i in range(8)] for r in cal],axis=0)-10*np.log10(np.diff(SPECTRAL_EDGES_HZ))
    initial_levels=np.interp(np.log(CONTROL_HZ),np.log(centers),density)-transfer_db(CONTROL_HZ);initial_levels-=initial_levels.mean()
    cv=float(np.median([r['features']['env_cv'] for r in cal]));initial=np.r_[initial_levels,np.clip(cv*cv/(1+cv*cv),0,.25)]
    initial_kernel=minimum_phase_kernel(initial[:8]);initial_weights=noise_weights(initial[:8])
    old_rms=[float(np.sqrt(np.mean(c['data'][48000:,1]**2))) for c in cases[:16]]
    new_rms=[float(np.sqrt(np.mean(layer(c['data'],initial_kernel,initial_weights,initial[8],1)[48000:]**2))) for c in cases[:16]]
    source_scale=float(np.median(old_rms)/np.median(new_rms))
    def persistent_objective(p):
        kernel=minimum_phase_kernel(p[:8]);nw=noise_weights(p[:8]);values=[];low=[];mid=[];source_rms=[]
        for c,base in zip(cases,baseline):
            bark=layer(c['data'],kernel,nw,p[8],source_scale);pcm=original_output(compose(c['data'],bark),c['data'][:,8])
            lo=48000 if c['id'].startswith('steady') else 24000;f=features(pcm[lo:]);values.append(f)
            delta=10*np.log10(np.maximum(f['absolute_band_power'],1e-30)/np.maximum(base['absolute_band_power'],1e-30))
            low.append(abs(delta[0]));mid.append(delta[1])
            if c['id'].startswith('steady'):source_rms.append(float(np.sqrt(np.mean(bark[48000:]**2))))
        distance=distribution_distance(reference,values,scales,weights,sample_weights);groups=groups_distance(cal,values,scales,weights,sample_weights)
        source_change=20*math.log10(np.median(source_rms)/np.median(old_rms))
        penalty=max(0,np.median(low)-1)**2+max(0,np.quantile(low,.9)-1.5)**2+max(0,max(mid)-1)**2+max(0,abs(source_change)-1)**2
        penalty+=sum(max(0,groups[k]/max(before_groups[k],1e-12)-1.1)**2 for k in groups)
        return {'score':float(distance*distance+4*penalty),'distance':distance,'groups':groups,'low_median_db':float(np.median(low)),
                'low_p90_db':float(np.quantile(low,.9)),'mid_max_rise_db':float(max(mid)),'source_representative_change_db':source_change}
    continuous=FitBudget(64,args.out/'continuous-history.jsonl')
    bounds=[(x-12,x+12) for x in initial_levels]+[(0,.25)]
    p,presult=coordinate_fit(initial,bounds,[np.r_[np.ones(8)*s,f] for s,f in ((6,.08),(3,.04),(1.5,.02))],continuous,persistent_objective)
    periodic=minimum_phase_kernel(p[:8]);nw=noise_weights(p[:8])
    event_case=next(c for c in all_cases if c['id']=='event_background');data=event_case['data'];imp=data[:,17];angle=data[:,18]
    known=np.flatnonzero(imp>0);active=data[:,11]<.15;episodes=np.cumsum(active & ~np.r_[False,active[:-1]])
    background=original_output(compose(data,data[:,1],np.zeros(len(data))),data[:,8])
    old_on=original_output(compose(data,data[:,1],data[:,19]),data[:,8]);old_effect=old_on-background
    meta=json.loads((args.bundle/'reference_clip_receipt.json').read_text())['clips']['ref_afterfire.wav']
    ref_pcm=read_clip(args.bundle/'ref_afterfire.wav',meta['sha256'])[:144000];ref_desc=event_descriptors(ref_pcm)
    floors={'attack':5.,'tail':5.,'tail_energy':5.,'interval':.1,'amplitude':.1}
    event_scales={k:max(float(np.std(ref_desc[k])) if ref_desc[k] else 0,v) for k,v in floors.items()}
    old_desc=event_descriptors(old_effect,known,episodes);old_distance,old_categories=event_distance(ref_desc,old_desc,event_scales)
    ref_summary=summarize(envelope(ref_pcm,RATE),RATE);spectra=[]
    for event in ref_summary['events']:
        peak=event['frame_5ms']*240;lo=peak-2880;hi=peak+12288
        if lo<0 or hi>len(ref_pcm) or event['tail_10pct_ms'] is None:continue
        f,psd=welch(ref_pcm[lo:hi],fs=RATE,nperseg=8192,noverlap=6144);spectra.append(psd)
    if not spectra:raise ValueError('No complete calibration transient window; event fit not supported')
    psd=np.median(spectra,axis=0);ehz=np.geomspace(40,4000,8)
    event_levels=10*np.log10(np.maximum(np.interp(ehz,f,psd),1e-30))-transfer_db(ehz);event_levels-=event_levels.mean()
    attack=float(np.clip(np.median(ref_desc['attack']) if ref_desc['attack'] else 30,1,100));tail=float(np.clip(np.median(ref_desc['tail']) if ref_desc['tail'] else 40,5,120))
    event_initial=np.r_[event_levels,attack,tail,.2];event_scale=math.sqrt(old_event_energy())
    def event_objective(q):
        basis=event_bases(q[8],q[9],q[:8],SEEDS[2]);r=q[10]
        signal=event_scale*(math.sqrt(1-r)*fftconvolve(imp,basis[0])[:len(data)]+math.sqrt(r)*(
            fftconvolve(imp*np.cos(angle),basis[1])[:len(data)]+fftconvolve(imp*np.sin(angle),basis[2])[:len(data)]))
        on=original_output(compose(data,data[:,1],signal),data[:,8]);effect=on-background
        desc=event_descriptors(effect,known,episodes);distance,categories=event_distance(ref_desc,desc,event_scales)
        energy_change=10*math.log10(max(float(np.sum(effect*effect)),1e-30)/max(float(np.sum(old_effect*old_effect)),1e-30))
        penalty=max(0,energy_change-1)**2+sum(max(0,categories[k]/max(old_categories[k],1e-12)-1.1)**2 for k in categories)
        penalty+=(desc['false_peaks']/max(desc['matched']+desc['false_peaks'],1))**2
        return {'score':float(distance*distance+4*penalty),'distance':distance,'categories':categories,'energy_change_db':energy_change,
                'matched':desc['matched'],'false_peaks':desc['false_peaks'],'censored':desc['censored']}
    event_budget=FitBudget(32,args.out/'event-history.jsonl')
    ebounds=[(x-12,x+12) for x in event_levels]+[(1,100),(5,120),(0,.5)]
    q,qresult=coordinate_fit(event_initial,ebounds,[np.r_[np.ones(8)*s,a,t,r] for s,a,t,r in ((6,15,15,.15),(3,7.5,7.5,.075))],event_budget,event_objective)
    basis=event_bases(q[8],q[9],q[:8],SEEDS[2]);payload=pack_profile(periodic,basis,source_scale,event_scale,p[8],q[10],nw,reference_hash)
    (args.out/'profile.bin').write_bytes(payload)
    result={'schema':'c63.hy1.frozen_fit.v1','candidate':'C63_HY1','profile_sha256':hashlib.sha256(payload).hexdigest(),'reference_constraints_sha256':reference_hash,
        'continuous_evaluations':continuous.count,'event_evaluations':event_budget.count,'persistent_parameters':p.tolist(),'event_parameters':q.tolist(),
        'source_scale_calibrated_once':source_scale,'event_scale_calibrated_once':event_scale,'noise_weights':nw.tolist(),
        'baseline_distance':before,'calibration_result':presult,'baseline_event_distance':old_distance,'calibration_event_result':qresult,
        'gain':3.7075542301539652,'headroom':.40803954754257843,'fixture_identities':{c['id']:c['sha256'] for c in all_cases},
        'status':'FROZEN_PENDING_ACTUAL_KOTLIN_QUALIFICATION','reference_scope':'Unverified local unsynchronized transient/statistical constraints; not OEM',
        'phase_contract':'Minimum-phase spectral design then causal finite zeroDC projection; not stable inversion',
        'reference_event_spectral_windows':len(spectra),
        'event_interval_scope':'Within known synthetic closure episodes;reference adjacent intervals<=1s;not measured RPM rate',
        'tool_identities':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in
            ('fit_c63_hybrid.py','build_c63_hybrid_targets.py','c63_hybrid_event_kernel.py','fit_c63_bark_modes.py','extract_c63_ar2_events.py')}}
    with (args.out/'frozen-profile.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2,allow_nan=False)
    print(json.dumps({k:result[k] for k in ('profile_sha256','continuous_evaluations','event_evaluations','calibration_result','calibration_event_result')},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fixtures',type=Path,required=True);parser.add_argument('--targets',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);run(parser.parse_args())
