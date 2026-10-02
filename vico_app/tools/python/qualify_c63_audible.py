from pathlib import Path
import argparse,csv,hashlib,json,math
import numpy as np
from scipy.signal import butter,sosfilt,find_peaks
from fit_c63_bark_modes import render,band_power
from build_c63_audible_targets import features,feature_distance,read_clip,improved

PROFILE_SHA='0aee164277afc36691c468ef6778b12d637b4d16b5e7cde5118d7e33359babea'
def validate_profile(profile):
    if profile.get('candidate_id')!='C63_AR1' or profile.get('headroom_scalar')!=.40803954754257843 or profile.get('original_gain')!=3.7075542301539652:raise ValueError('Candidate identity/fixed gain changed')

def decide_acoustics(results):
    return results.get('event_support',False) and results.get('spectral_improvement',0)>=.2 and results.get('modal_reduction_db',0)>=3 and results.get('body_protection',False) and results.get('texture_pass',False) and results.get('event_pass',False)

def transient_candidates(pcm):
    filtered=sosfilt(butter(4,[40,4000],fs=48000,btype='bandpass',output='sos'),pcm)
    env=np.sqrt(np.mean(filtered[:len(filtered)//240*240].reshape(-1,240)**2,axis=1))
    baseline=float(np.median(env));peaks,props=find_peaks(env,prominence=max(baseline*.75,1e-8),distance=4)
    # A separable impulse must have both local valleys at least6dB below its peak.
    isolated=[]
    for peak in peaks:
        lo=max(0,peak-12);hi=min(len(env),peak+25)
        if lo>=peak or hi<=peak+1:continue
        if min(env[lo:peak].min(),env[peak+1:hi].min())<env[peak]*.5:
            isolated.append(int(peak))
    return {'detected_peaks':len(peaks),'separable_candidates':len(isolated),'frames_5ms':isolated,
            'scope':'Unlabelled transient candidates, not confirmed combustion/afterfire events'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    profile_path=args.root/'frozen-profile.json'
    if hashlib.sha256(profile_path.read_bytes()).hexdigest()!=PROFILE_SHA:raise ValueError('Frozen parameter profile changed')
    profile=json.loads(profile_path.read_text());validate_profile(profile);targets=json.loads((args.root/'reference-targets.json').read_text());texture=json.loads((args.root/'texture-transfer.json').read_text())
    fixture=args.root/'fit-fixture-v2'
    with (fixture/'fixture.tsv').open() as stream:controls=list(csv.DictReader(stream,delimiter='\t'))
    mapping={'low':'ref_steady_low.wav','mid':'ref_steady_mid.wav','pull':'ref_full_pull.wav','high':'ref_steady_high.wav'}
    details=[];changes=[]
    for control in controls:
        name=control['group'];data_path=fixture/f'{name}.f64le'
        if hashlib.sha256(data_path.read_bytes()).hexdigest()!=profile['fixture_sha256'][name]:raise ValueError('Frozen control changed')
        data=np.fromfile(data_path,dtype='<f8').reshape(-1,11);throttle=float(control['throttle'])
        ah=render(data,throttle,np.ones(4),profile['texture_scale'],False)[96000:]
        candidate=render(data,throttle,np.asarray(profile['decay_scales']),profile['texture_scale'])[96000:]
        reference=next(w for w in targets['windows'] if w['split']=='holdout' and w['filename']==mapping[name])
        af=features(ah);cf=features(candidate);scales=targets['calibration_scales']
        before=feature_distance(reference['features'],af,scales);after=feature_distance(reference['features'],cf,scales)
        delta=(10*np.log10(np.asarray(band_power(candidate))/np.asarray(band_power(ah)))).tolist();changes.append(delta)
        details.append({'group':name,'window_id':reference['id'],'AH_distance':before,'S_distance':after,'low_mid_db_changes':delta,
                        'high_relative_db_change':cf['high']-af['high'],'ultrahigh_relative_db_change':cf['ultrahigh']-af['ultrahigh']})
    before=float(np.mean([r['AH_distance'] for r in details]));after=float(np.mean([r['S_distance'] for r in details]));delta=np.abs(np.asarray(changes))
    median=np.median(delta,axis=0);p90=np.percentile(delta,90,axis=0)
    modal=[]
    with (args.root/'modal-pressure/cases.tsv').open() as stream:cases=list(csv.DictReader(stream,delimiter='\t'))
    for case in cases:
        name=case['id'];key='prom'+str(int(float(case['mode_hz'])))
        ah=np.fromfile(args.root/f'modal-pressure/{name}-AH.f32le',dtype='<f4');s=np.fromfile(args.root/f'modal-pressure/{name}-S.f32le',dtype='<f4')
        if len(ah)!=144000 or len(s)!=144000:raise ValueError('Modal frames changed')
        modal.append({'id':name,'reduction_db':features(ah)[key]-features(s)[key]})
    receipt=json.loads((args.bundle/'reference_clip_receipt.json').read_text());meta=receipt['clips']['ref_afterfire.wav']
    waveform=read_clip(args.bundle/'ref_afterfire.wav',meta['sha256'])
    event_cal=transient_candidates(waveform[:144000]);event_hold=transient_candidates(waveform[144000:])
    support=min(event_cal['separable_candidates'],event_hold['separable_candidates'])>=8
    result={'schema':'c63.ar1.acoustic_verdict.v1','candidate_id':'C63_AR1','profile_sha256':PROFILE_SHA,
            'spectral_improvement':1-after/before,'heldout_distances':details,'modal_reduction_db':float(np.median([r['reduction_db'] for r in modal])),
            'modal_cases':modal,'body_low_mid_absolute_change_median':median.tolist(),'body_low_mid_absolute_change_p90':p90.tolist(),
            'body_protection':bool(np.all(median<=1) and np.all(p90<=1.5)),
            'texture_pass':bool(texture['modulation_improvement']>=.2 and abs(20*np.log10(texture['scaled_rms']/texture['target_rms']))<=.5),
            'event_support':support,'event_reference_calibration':event_cal,'event_reference_holdout':event_hold,
            'event_pass':False,'event_status':'INSUFFICIENT_SEPARABLE_LABELLED_REFERENCE' if not support else 'TRANSIENT_CANDIDATES_REQUIRE_EVENT_QUALIFICATION',
            'human_acceptance':'PENDING','physical_speaker_oem':'NOT_PROVEN'}
    result['status']='ACOUSTIC_PASS_DEVICE_PENDING' if decide_acoustics(result) else 'ACOUSTIC_NOT_QUALIFIED_NO_INSTALL'
    with args.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('modal_cases','heldout_distances')},indent=2))
