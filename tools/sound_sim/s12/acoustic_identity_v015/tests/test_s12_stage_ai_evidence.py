"""Synthetic evidence regressions; not real-vehicle similarity measurements."""
from copy import deepcopy
import json
import numpy as np
import pytest
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import (
    AUTO, Journal, fit_eligibility, read_journal, sha_file)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback import (
    ReferenceCase, Rendered, SearchConfig, optimize_reference_feedback)


def signal(mix, phase=0.):
    t=np.arange(12000)/48000.
    return .15*np.sin(2*np.pi*170*t+phase)+mix*.12*np.sin(2*np.pi*2400*t+phase)


@pytest.fixture
def fit():
    refs=[ReferenceCase('train','steady','source-a','a'*64,'train',signal(1.7),(0.,.25),True,'synthetic same operating state'),
          ReferenceCase('val','steady','source-b','b'*64,'validation',signal(1.7,.2),(0.,.25),True,'synthetic held-out phase')]
    return optimize_reference_feedback({'mix':1.},{'mix':(.5,2.)},refs,
        lambda p,s:Rendered(signal(p['mix']),True,{}),config=SearchConfig(max_trials=13))


def test_real_measured_history_qualifies_b(fit):
    result=fit_eligibility(fit)
    assert result['kind']==AUTO and result['available']
    assert result['promotable'] is False


@pytest.mark.parametrize('change', [
    {'schema':'fixed.recipe'}, {'history':[]}, {'trial_count':10000},
    {'selected_parameters':{'mix':1.}}, {'status':'NO_IMPROVEMENT'},
    {'validation_used_for_search':True}, {'validation_baseline':{}},
    {'validation_proposed':{'val':float('nan')}}, {'selected_train_loss':2.},
    {'selected_train_loss':float('nan')}, {'selected_parameters':{'mix':1.799999}},
])
def test_no_automatic_label_without_complete_proof(fit,change):
    result=deepcopy(fit);result.update(change)
    assert not fit_eligibility(result)['available']


def test_source_leakage_rejected_even_when_status_claims_success(fit):
    fit['reference_cases'][1]['source_sha256']=fit['reference_cases'][0]['source_sha256']
    assert not fit_eligibility(fit)['available']


def test_journal_persists_and_detects_reorder_or_drift(tmp_path):
    path=tmp_path/'trial.jsonl';obj={'parameters':{'mix':1.}}
    with Journal(path) as log:
        log.append('BASELINE',obj);obj['parameters']['mix']=9.
        assert read_journal(path)[0]['payload']['parameters']['mix']==1.
        log.append('TRIAL',{'decision':'REJECTED','error':.8})
    digest=sha_file(path)
    assert len(read_journal(path,expected_sha256=digest))==2
    lines=path.read_text().splitlines();path.write_text('\n'.join(lines[::-1])+'\n')
    with pytest.raises(ValueError):read_journal(path)
    with pytest.raises(FileExistsError):Journal(path)


def test_event_nan_does_not_write_partial_record(tmp_path):
    path=tmp_path/'log'
    with Journal(path) as log:
        log.append('START',{})
        with pytest.raises(ValueError):log.append('BAD',{'loss':float('nan')})
        log.append('FINISH',{})
    assert len(read_journal(path))==2
