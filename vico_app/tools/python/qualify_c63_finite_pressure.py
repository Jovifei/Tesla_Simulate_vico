"""Independent fail-closed TRI14 numerical qualification; no normalization."""
from pathlib import Path
import csv,json,math,argparse

LIMIT=0.8413951416451951
def evaluate(rows,expected):
    if not expected or not rows:raise ValueError('Empty qualification set')
    ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected):raise ValueError('Missing, duplicate or unexpected case')
    failures=[]
    for row in rows:
        frames=int(row['frames']);a=float(row['A_peak']);b=float(row['B_peak'])
        if frames!=expected[row['id']] or not math.isfinite(a) or not math.isfinite(b) or min(a,b)<0:
            raise ValueError('Invalid frame count or peak')
        if b>LIMIT:failures.append({'id':row['id'],'A_peak':a,'B_peak':b,'first_exceed_frame':int(row['B_first_exceed']),'worst_frame':int(row['B_worst_frame'])})
    failures.sort(key=lambda r:r['B_peak'],reverse=True)
    return {'status':'CANDIDATE_REJECTED_NUMERICAL' if failures else 'NUMERICAL_PASS_ONLY',
            'case_count':len(rows),'limit_fs':LIMIT,'failed_case_count':len(failures),'failures':failures,
            'body_protection':'REQUIRES_SEPARATE_ANALYSIS','phone_install':'BLOCKED' if failures else 'PENDING_PROTECTION_AND_DEVICE',
            'human_acceptance':'NOT_RUN','physical_capture':'NOT_RUN','candidate_parameters':'TRI14_CAP1P2MS_AREA_NORMALIZED'}

def expected_cases(phone_blocks):
    cases={}
    for r in (700.,1400.,2200.,3200.,4300.,5500.,6800.,7200.):
        for l in (0.,.32,.92,1.):cases[f'Q0_steady_{r}_{l}']=144000
    for a in (700.,1800.,5500.,7200.):
        for b in (700.,1800.,5500.,7200.):cases[f'Q0_transition_{a}_{b}']=192000
    cases['Q0_phone']=phone_blocks*960;cases['Q1_original']=1440000;cases['Q1_phone_plus_hold']=(phone_blocks+100)*960
    for f in (540.,820.,1100.,1500.):
        for k in range(1,33):
            if 700<=15*f/k<=7200:cases[f'Q2_{f}_{k}']=144000
    for up in ('true','false'):cases['Q3_sweep_'+up]=3120000
    cases['Q3_hot_events']=576000
    for i in range(3):cases[f'Q3_restart_{i}']=240000
    for r in (700.,1400.,1849.,1850.,1851.):
        for l in (0.,.2,.32,.5,1.):
            for t in (0.,.2,.35,1.):
                for hot in ('false','true'):cases[f'Q4_{r}_{l}_{t}_{hot}']=240000 if hot=='true' else 144000
    return cases

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--phone',type=Path,required=True);a=p.parse_args()
    expected=expected_cases(len(json.loads(a.phone.read_text())['input_trace']['points']))
    with (a.root/'qualification.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
    result=evaluate(rows,expected);target=a.root/'numerical-verdict.json'
    if target.exists():raise FileExistsError(target)
    target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(result,indent=2))
