"""Real four-car engines with controlled fixtures; never real-recording claims."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import fourcar_reference_loop as loop
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import SCENES, read_journal
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback import ReferenceCase, SearchConfig, optimize_reference_feedback
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import artifact_record, seal_payload


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    ir=tmp_path/'ir';ir.mkdir()
    impulse=np.array([28000,1000,-500,200],dtype=np.int16)
    for name in set(loop.IR_NAMES.values()):wavfile.write(ir/(name+'.wav'),48000,impulse)
    monkeypatch.setenv('S12_ENGINE_SIM_IR_ROOT',str(ir))
    dash=loop._import_dashboards()
    def schedule(v,cfg):
        eng=dash.EngineAcoustics(vehicle_type=v,sr=48000)
        web=cfg['dir']/'web_audio';web.mkdir(parents=True,exist_ok=True)
        for i,row in enumerate(cfg['scenes']):
            context={'rpm':np.full(12000,6500.+i*9),'throttle':np.full(12000,.55),
                'duration':.25,'shift_events':None,'afterfire_events':None,'bov_events':None}
            audio=eng.render_track(context['rpm'],context['throttle'],context['duration'])
            for path in (web/row['candidate_file'],cfg['dir']/row['candidate_file']):wavfile.write(path,48000,audio)
            cfg['_render_observer'](scene_id=row['id'],audio=audio,**context)
    monkeypatch.setattr(dash,'render_vehicle_audio',schedule)
    parent=tmp_path/'parent';parent.mkdir()
    entries=[];expected={}
    for v in loop.FOURCAR_VEHICLES:
        folder=parent/loop._vehicle_directory(v);web=folder/'web_audio';web.mkdir(parents=True)
        eng=loop.RemediationEngine(v,seed=20260908,variant='r1_baseline',output_policy=loop.LINKED_SOFT_CEILING_V1)
        rows=[];hashes={}
        for i,s in enumerate(SCENES):
            rpm=np.full(12000,6500.+i*9);thr=np.full(12000,.55)
            audio=eng.render_track(rpm,thr,.25)
            wavfile.write(web/(s+'.wav'),48000,audio)
            rows.append(dict(copy.deepcopy(eng.last_report),scene_id=s))
            hashes[s+'.wav']=loop.sha_file(web/(s+'.wav'))
        refs={}
        for scene,name in loop.RELATIVE_SCENES.items():
            sr,a=wavfile.read(web/(scene+'.wav'));wavfile.write(web/name,sr,a)
            refs[name]=loop.sha_file(web/name)
        loop.write_json(folder/'stage_ah_fourcar_binding.json',seal_payload({'records':rows},'fixture.binding.v1'))
        entry={'vehicle':v,'directory':folder.name,'candidate_sha256':hashes,'reference_sha256':refs}
        entries.append(entry)
        expected[v]=hashes
    artifacts=[artifact_record(p,parent,'synthetic:'+p.name) for p in parent.rglob('*') if p.is_file()]
    loop.write_json(parent/'audition_manifest.json',seal_payload({'group':'C0','identity_mode':'vehicle_identity_v1r1',
        'output_policy':loop.LINKED_SOFT_CEILING_V1,'numeric_gate':{'status':'PASS'},'vehicles':entries,
        'artifacts':artifacts},'s12.stage_ah.fourcar.real_reference.package_manifest.v2'))
    return parent,entries,expected


@pytest.mark.parametrize('vehicle',loop.FOURCAR_VEHICLES)
def test_actual_fourcar_zero_delta_and_named_parameter(fixture,tmp_path,vehicle):
    parent,entries,_=fixture;entry=next(e for e in entries if e['vehicle']==vehicle)
    _,contexts,records,peaks=loop.capture_baseline(vehicle,tmp_path/'replay',entry,parent)
    adapter=loop.FourCarFeedbackRenderer(vehicle,contexts,peaks)
    scene='07_steady_high'
    a=adapter(adapter.baseline,scene)
    _,old=wavfile.read(parent/entry['directory']/'web_audio'/(scene+'.wav'))
    assert np.array_equal(a.audio,old)
    p=dict(adapter.baseline);p[adapter.name]*=1.02
    b=adapter(p,scene)
    assert not np.array_equal(a.audio,b.audio)
    assert a.diagnostics['normalization_denominator']==b.diagnostics['normalization_denominator']
    assert a.diagnostics['trace_sha256']==b.diagnostics['trace_sha256']
    assert b.diagnostics['source_parameter_change']['candidate_value']==p[adapter.name]
    assert set(records)==set(SCENES)
    with pytest.raises(ValueError):adapter(dict(p,master_gain=.8),scene)


def test_run_uses_real_engine_and_retains_all_scene_evidence(fixture,tmp_path):
    parent,entries,_=fixture
    catalog={'vehicles':{}}
    case_rows=[]
    # Keep E2E short: Hellcat demonstrates train/validation execution. Other
    # engines are exercised independently above, not falsely labelled fitted.
    v='hellcat';entry=next(e for e in entries if e['vehicle']==v)
    _,contexts,_,peaks=loop.capture_baseline(v,tmp_path/'target-replay',entry,parent)
    adapter=loop.FourCarFeedbackRenderer(v,contexts,peaks)
    params=dict(adapter.baseline);params[adapter.name]+=0.05
    target=adapter(params,'07_steady_high').audio
    sources=[]
    for i in range(3):
        path=tmp_path/f'ref-{i}.wav';wavfile.write(path,48000,np.roll(target,i*13,axis=0))
        source={'id':f'controlled{i}','source_url':f'https://example.invalid/synthetic/{i}',
            'wav_sha256':loop.sha_file(path),'rights_status':'SYNTHETIC_FIXTURE'}
        sources.append(source)
        case_rows.append({'vehicle':v,'case_id':str(i),'source_id':source['id'],'wav_path':str(path),
            'source_window_s':[0.,.25],'scene':'07_steady_high','candidate_window_s':[0.,.25],
            'split':'validation' if i==2 else 'train','comparable':True,
            'comparability_note':'synthetic known parameter target; not a real recording',
            'viewpoint':'synthetic','state_family':'steady'})
    catalog['vehicles'][v]={'sources':sources}
    catalog_path=tmp_path/'catalog.json';loop.write_json(catalog_path,catalog)
    plan=tmp_path/'plan.json';loop.write_json(plan,{'schema':loop.PLAN_SCHEMA,'evidence_level':'R3_UNSYNCHRONIZED',
        'catalog_path':str(catalog_path),'catalog_sha256':loop.sha_file(catalog_path),
        'parent_package':str(parent),'parent_manifest_sha256':loop.sha_file(parent/'audition_manifest.json'),
        'cases':case_rows})
    out=tmp_path/'ai-loop'
    result=loop.run(plan,out,config=SearchConfig(max_trials=5,rounds=2))
    assert v in result['vehicles'],result['blocked_vehicles']
    r=result['vehicles'][v]
    assert len(r['history'])>1
    assert r['off_switch_equal_count']==10
    assert len(r['baseline_records'])==10
    assert r['promotable'] is False
    # Baseline refs intentionally equal the baseline: any changed spectrum may
    # fail the separate relative guard. Rollback is a tested valid result.
    loop.verify_run(out,loop.sha_file(out/'ARTIFACTS.json'))
    assert read_journal(out/r['logs']['renders'])[-1]['event']=='VEHICLE_COMPLETE'
    assert len(read_journal(out/r['logs']['trials']))==len(r['history'])+1
    with pytest.raises(FileExistsError):loop.run(plan,out,config=SearchConfig(max_trials=1))
    p=out/'tuned'/v/'web_audio'/'07_steady_high.wav'
    p.write_bytes(p.read_bytes()+b'tamper')
    with pytest.raises(ValueError):loop.verify_run(out)
