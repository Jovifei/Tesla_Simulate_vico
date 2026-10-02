from pathlib import Path
import csv,json,math,hashlib,argparse,collections
from qualify_c63_finite_pressure import expected_cases,LIMIT

def calibrate(rows,expected,input_hashes):
    ids=[r['id'] for r in rows]
    if not rows or not expected or len(ids)!=len(set(ids)) or set(ids)!=set(expected) or set(input_hashes)!=set(expected):raise ValueError('Calibration set identity invalid')
    for r in rows:
        if int(r['frames'])!=expected[r['id']] or r['input_sha256']!=input_hashes[r['id']]:raise ValueError('Calibration input changed')
        peak=float(r['A_peak'])
        if not math.isfinite(peak) or peak<0:raise ValueError('Nonfinite/negative calibration peak')
    worst=max(rows,key=lambda r:float(r['A_peak']));pcal=float(worst['A_peak'])
    h=min(1.,LIMIT*10**(-1/20)/pcal) if pcal else 1.
    duplicate=collections.defaultdict(list)
    for r in rows:duplicate[r['input_sha256']].append(r['id'])
    return {'Pcal':pcal,'worst_case':worst['id'],'headroom_scalar':h,'reserve_db':1,'level_cost_db':20*math.log10(h),
            'effective_total_gain':3.7075542301539652*h,'case_count':len(rows),'unique_input_count':len(duplicate),
            'duplicate_inputs':{k:v for k,v in duplicate.items() if len(v)>1},'input_manifest':input_hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--calibration',type=Path,required=True);p.add_argument('--phone',type=Path,required=True);p.add_argument('--holdout',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise FileExistsError(a.out)
    if hashlib.sha256(a.calibration.read_bytes()).hexdigest()!='0a92406a21d7a34947c5434363c4415a2304b1b9b83a241cb682af36874e712b':raise ValueError('Frozen calibration file changed')
    if hashlib.sha256(a.holdout.read_bytes()).hexdigest()!='757d9405b5e9b69a3247a671e27079081d373dfc012b77c3d525b871cd2954b1':raise ValueError('Frozen holdout manifest changed')
    with a.calibration.open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
    expected=expected_cases(len(json.loads(a.phone.read_text())['input_trace']['points']))
    result=calibrate(rows,expected,{r['id']:r['input_sha256'] for r in rows})
    result.update({'candidate_id':'C63_AH_V1','finite_excitation':False,'calibration_file_sha256':hashlib.sha256(a.calibration.read_bytes()).hexdigest(),
                   'holdout_manifest_sha256':hashlib.sha256(a.holdout.read_bytes()).hexdigest(),'original_gain':3.7075542301539652,'status':'CALIBRATED_HOLDOUT_PENDING'})
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(result,indent=2))
