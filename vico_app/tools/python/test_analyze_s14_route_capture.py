import pytest
from analyze_s14_route_capture import verify
import analyze_s14_route_capture as capture
import copy

def pair():
    conditions = dict(device_instance='test-device',model='GM1910',sdk=30,route_id=3,route_type=2,route_category='BUILTIN',route_name='speaker',media_volume=8,media_volume_max=15,media_muted=False,sample_rate_hz=48000,channels=1)
    rows=[]
    for i,label in enumerate(('R','M')):
        rows.append(dict(schema='vico.s14.trial.v2',pair_id='p1',session_id=str(i),reference_label=label,trial_number=i+1,vehicle_key='c63_w204_v6',source_pcm_sha256={'R':'2d66e9adcc763619c1152dc124ceb73b7c9f128a0693925e6ab4197f507cc7a2','M':'127f2c08a9977e43510633bbbad44ee989f7d112b79d5876bff99b99a7ef0b4f'}[label],presentation_gain=1.0,submitted_complete=True,digital_reference_match=True,playback_position_complete=True,controlled=True,session_error=None,start_conditions=copy.deepcopy(conditions),end_conditions=copy.deepcopy(conditions),started_at_ms=i*40000,ended_at_ms=i*40000+30000))
    return rows

def test_complete_pair_has_its_own_condition_gate():
    assert capture.verify_pair(*pair())['status']=='PAIR_CONDITIONS_MATCHED'

@pytest.mark.parametrize('fault',['route','volume','missing_type','duplicate_trial','wrong_material','cancelled','unknown_end','muted','missing_pair'])
def test_pair_faults_do_not_pass(fault):
    a,b=pair()
    if fault=='route': b['start_conditions']['route_id']=4
    if fault=='volume': b['start_conditions']['media_volume']=9
    if fault=='missing_type': del b['start_conditions']['route_type']
    if fault=='duplicate_trial': b['session_id']=a['session_id']
    if fault=='wrong_material': b['reference_label']='R'
    if fault=='cancelled': b['session_error']='USER_STOP'
    if fault=='unknown_end': b['playback_position_complete']=None
    if fault=='muted': b['start_conditions']['media_muted']=True
    if fault=='missing_pair': del b['pair_id']
    assert capture.verify_pair(a,b)['status']!='PAIR_CONDITIONS_MATCHED'

def test_incomplete_run_cannot_be_passed_as_listening_evidence(tmp_path):
    with pytest.raises(ValueError,match='Incomplete'):
        verify({'diagnostic_phase':'S14','reference_label':'R','session_complete':False},tmp_path/'missing','x','R')

def test_other_phase_receipt_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='identity'):
        verify({'diagnostic_phase':'S13','reference_label':'R'},tmp_path/'missing','x','R')

def test_mislabeled_material_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='identity'):
        verify({'diagnostic_phase':'S14','reference_label':'M'},tmp_path/'missing','x','R')
