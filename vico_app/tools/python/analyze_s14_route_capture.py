"""Verify S14 digital receipts against original materials; physical sound is separate."""
import argparse
from pathlib import Path
import json
from build_s14_reference_bundle import sha

EXPECTED = {'R':'2d66e9adcc763619c1152dc124ceb73b7c9f128a0693925e6ab4197f507cc7a2','M':'127f2c08a9977e43510633bbbad44ee989f7d112b79d5876bff99b99a7ef0b4f'}
CONDITION_KEYS = ('device_instance','model','sdk','route_id','route_type','route_category','route_name','media_volume','media_volume_max','media_muted','sample_rate_hz','channels')

def verify_pair(a,b):
    reasons=[]
    if {a.get('reference_label'),b.get('reference_label')} != {'R','M'}:
        reasons.append('MATERIAL_SET_MISMATCH')
    if not a.get('pair_id') or a.get('pair_id')!=b.get('pair_id'):
        reasons.append('PAIR_ID_MISMATCH')
    if not a.get('session_id') or not b.get('session_id') or a.get('session_id')==b.get('session_id'):
        reasons.append('TRIAL_ID_MISSING_OR_DUPLICATED')
    if {a.get('trial_number'),b.get('trial_number')} != {1,2}:
        reasons.append('TRIAL_ORDER_MISMATCH')
    conditions=[]
    for trial in (a,b):
        if (trial.get('schema')!='vico.s14.trial.v2' or trial.get('vehicle_key')!='c63_w204_v6' or
            trial.get('source_pcm_sha256')!=EXPECTED.get(trial.get('reference_label')) or
            trial.get('presentation_gain')!=1.0 or trial.get('session_error') is not None or
            any(trial.get(key) is not True for key in ('digital_reference_match','submitted_complete','playback_position_complete'))):
            reasons.append('TRIAL_IDENTITY_OR_COMPLETION_FAILED')
        start=trial.get('start_conditions'); end=trial.get('end_conditions')
        if (not isinstance(start,dict) or not isinstance(end,dict) or
            any(key not in start or key not in end for key in CONDITION_KEYS)):
            reasons.append('OUTPUT_CONDITIONS_MISSING'); continue
        if start!=end:
            reasons.append('OUTPUT_CONDITIONS_CHANGED')
        numeric=('sdk','route_type','route_id','media_volume','media_volume_max','sample_rate_hz','channels')
        if any(type(start[k]) is not int for k in numeric):
            reasons.append('OUTPUT_CONDITIONS_INVALID'); continue
        if (not start['device_instance'] or not start['model'] or start['route_type']<=0 or start['route_id']<=0 or
            start['route_category'] not in ('BUILTIN','WIRED','BLUETOOTH') or not start['route_name'] or
            start['media_volume']<=0 or start['media_muted'] is not False or
            start['sample_rate_hz']!=48000 or start['channels']!=1):
            reasons.append('OUTPUT_CONDITIONS_INVALID')
        conditions.append(start)
    if len(conditions)!=2 or conditions[0]!=conditions[1]:
        reasons.append('PAIR_OUTPUT_MISMATCH')
    if a.get('controlled') is not b.get('controlled') or not isinstance(a.get('controlled'),bool):
        reasons.append('PRESENTATION_MODE_MISMATCH')
    return {'status':'PAIR_CONDITIONS_MATCHED' if not reasons else 'PAIR_CONDITIONS_NOT_MATCHED',
            'reasons':sorted(set(reasons)),'listening':'PENDING','physical_capture':'NOT_RUN'}

def verify(receipt, pcm, expected_sha, label):
    if receipt.get('diagnostic_phase')!='S14' or receipt.get('reference_label')!=label:
        raise ValueError('Wrong diagnostic identity')
    if receipt.get('session_complete') is not True or receipt.get('session_error') is not None:
        raise ValueError('Incomplete session')
    if expected_sha != EXPECTED.get(label):
        raise ValueError('Unrecognized original material SHA')
    for name in ('review_core','track_accepted'):
        report=receipt[name]
        if (report['sample_rate_hz']!=48000 or report['channels']!=1 or
            report['format']!='f32le' or report['full_window'] is not True or
            report['overflow'] or report['failed'] or report['sha256']!=expected_sha or
            any(report[k]!=1440000 for k in ('requested_frames','accepted_frames','captured_frames'))):
            raise ValueError('Digital capture contract failed')
    if Path(pcm).stat().st_size!=5760000 or sha(pcm)!=expected_sha:
        raise ValueError('Accepted PCM bytes differ')
    if (receipt.get('reference_route_device_id') is None or
        receipt['reference_route_device_id']!=receipt.get('audio_route_device_id')):
        raise ValueError('Route changed or unavailable')
    return {'label':label,'status':'DIGITAL_REFERENCE_MATCH','route_id':receipt['reference_route_device_id'],
            'pcm_sha256':expected_sha,'physical_capture':'NOT_RUN','listening':'PENDING'}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--bundle',type=Path,required=True); args=p.parse_args()
    root=args.bundle; manifest=json.loads((root/'manifest.json').read_text())
    results=[]; receipts=[]
    for label in ('R','M'):
        filename='R-full-receipt.json' if label=='R' else 'M-receipt.json'
        receipt=json.loads((root/filename).read_text()); receipts.append(receipt)
        results.append(verify(receipt,root/(label+'-accepted.f32le'),manifest['materials'][label]['pcm_sha256'],label))
    result={'status':'DIGITAL_REFERENCES_MATCH','results':results,'pair_conditions':verify_pair(*receipts),'same_route':results[0]['route_id']==results[1]['route_id'],
            'route_type':'NOT_BOUND','sound_quality':'PENDING_NAMED_LISTENING','historical_80_40_binding':'UNBOUND'}
    target=root/'digital-comparison.json'
    if target.exists(): raise FileExistsError(target)
    target.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2))
