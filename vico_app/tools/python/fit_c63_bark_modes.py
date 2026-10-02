"""One32-evaluation fit using calibration references only; fixed output math."""
from pathlib import Path
import argparse,csv,hashlib,json,math
import numpy as np
from scipy.signal import lfilter,butter,sosfilt,ss2tf
from scipy.optimize import minimize
from build_c63_audible_targets import features,feature_distance

H=.40803954754257843
TAU=np.array([.045,.038,.034,.030]);HZ=np.array([540.,820.,1100.,1500.]);WEIGHTS=np.array([.50,.40,.42,.10])
class FitBudget:
    def __init__(self,maximum):
        if not 1<=maximum<=32:raise ValueError('Maximum fit budget is32')
        self.maximum=maximum;self.count=0
    def evaluate(self,parameters,objective):
        p=np.asarray(parameters,dtype=float)
        if p.shape!=(4,) or not np.isfinite(p).all() or np.any(p<.25) or np.any(p>1):raise ValueError('Invalid decay domain')
        if self.count>=self.maximum:raise RuntimeError('Fit budget exhausted; no restart')
        self.count+=1
        return objective(p)

def original_output(source,idle):
    source=source.astype('<f4').astype(float)
    x=np.concatenate((np.zeros(192),source[:-192]))+idle
    x=x+(10**(.9)-1)*sosfilt(butter(1,220,fs=48000,output='sos'),x)
    x=x+(10**(-.85)-1)*sosfilt(butter(1,3200,fs=48000,btype='high',output='sos'),x)
    x=sosfilt(butter(1,20,fs=48000,btype='high',output='sos'),x)
    x=np.concatenate((np.zeros(20),x[:-20]))*.98*.97
    a=np.array([[0.,1.],[-6.4359409190371978e8,-52275.601750547037]]);b=np.array([[0.],[1.]])
    c=np.array([[-6.4359409190371978e8,-6267.06783369803]]);dt=1/48000
    inv=np.linalg.inv(np.eye(2)-dt*a/2);ad=inv@(np.eye(2)+dt*a/2);bd=inv@(dt*b)
    numerator,denominator=ss2tf(ad,bd,c@ad,np.array([[1.]])+c@bd)
    return lfilter(numerator[0],denominator,x)*3.7075542301539652*H

def render(data,throttle,scale,texture_scale,sustained=True):
    parts=[data[:,i].copy() for i in range(7)]
    if sustained:
        bark=np.zeros(len(data))
        for hz,tau,weight in zip(HZ,TAU*scale,WEIGHTS):
            radius=np.exp(-1/(tau*48000));bark+=weight*lfilter([np.sin(2*np.pi*hz/48000)],[1,-2*radius*np.cos(2*np.pi*hz/48000),radius*radius],data[:,7])
        parts[1]=bark*.125*(.60+.40*throttle)*.70
        parts[3]=data[:,10]+.004*texture_scale*data[:,8]*.75
    source=parts[0]
    for part in parts[1:]:source=source+part
    return original_output(source,data[:,9])

def band_power(x):
    spectrum=np.abs(np.fft.rfft(x*np.hanning(len(x))))**2;f=np.fft.rfftfreq(len(x),1/48000)
    return [float(spectrum[(f>=lo)&(f<hi)].sum()) for lo,hi in ((20,200),(200,1000))]

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--targets',type=Path,required=True);parser.add_argument('--texture',type=Path,required=True);parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    targets=json.loads(args.targets.read_text());texture=json.loads(args.texture.read_text())
    with (args.fixture/'fixture.tsv').open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
    mapping={'low':'ref_steady_low.wav','mid':'ref_steady_mid.wav','pull':'ref_full_pull.wav','high':'ref_steady_high.wav'}
    fixture={};baseline={};reference={};powers={};hashes={};equivalence={}
    for row in rows:
        name=row['group'];file=args.fixture/f'{name}.f64le';data=np.fromfile(file,dtype='<f8').reshape(-1,11)
        if len(data)!=240000 or not np.isfinite(data).all():raise ValueError('Fixture changed')
        fixture[name]=(data,float(row['throttle']));hashes[name]=hashlib.sha256(file.read_bytes()).hexdigest()
        audio=render(data,float(row['throttle']),np.ones(4),texture['scale'],False)
        native=np.fromfile(args.fixture/f'{name}-AH.f32le',dtype='<f4');error=float(np.max(np.abs(audio-native)))
        if error>1e-6:raise ValueError(f'Original output mismatch:{name}:{error}')
        equivalence[name]=error;study=audio[96000:];baseline[name]=features(study);powers[name]=band_power(study)
        reference[name]=next(w['features'] for w in targets['windows'] if w['split']=='calibration' and w['filename']==mapping[name])
    budget=FitBudget(32);history=[]
    def objective(parameters):
        distances=[];penalties=[]
        for name,(data,throttle) in fixture.items():
            audio=render(data,throttle,parameters,texture['scale'])[96000:]
            distances.append(feature_distance(reference[name],features(audio),targets['calibration_scales']))
            changes=10*np.log10(np.array(band_power(audio))/np.array(powers[name]))
            penalties.append(float(np.sum(np.maximum(np.abs(changes)-1,0)**2)))
        value=float(np.mean(distances)+8*np.mean(penalties));history.append({'evaluation':budget.count,'scales':parameters.tolist(),'objective':value})
        return value
    result=minimize(lambda p:budget.evaluate(p,objective),np.ones(4)*.625,method='Nelder-Mead',bounds=[(.25,1)]*4,options={'maxfev':32,'maxiter':32,'xatol':1e-5,'fatol':1e-5})
    profile={'schema':'c63.ar1.frozen_source_profile.v1','candidate_id':'C63_AR1','decay_scales':result.x.tolist(),'decays_s':(TAU*result.x).tolist(),
             'texture_scale':texture['scale'],'event_seed':5900017,'event_amplitude_spread':0.,'event_response':'ORIGINAL90_850_REFERENCE_SUPPORT_PENDING',
             'headroom_scalar':H,'original_gain':3.7075542301539652,'fit_evaluations':budget.count,'initialization':[.625]*4,'objective':'calibration standardized feature distance +8*nonresonance low/mid loss penalty beyond1dB',
             'reference_targets_sha256':hashlib.sha256(args.targets.read_bytes()).hexdigest(),'texture_transfer_sha256':hashlib.sha256(args.texture.read_bytes()).hexdigest(),
             'fixture_sha256':hashes,'output_equivalence_max_errors':equivalence,'history':history,'status':'FROZEN_UNQUALIFIED_NO_REFIT'}
    with args.out.open('x') as stream:json.dump(profile,stream,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in profile.items() if k not in ('history','fixture_sha256')},indent=2))
