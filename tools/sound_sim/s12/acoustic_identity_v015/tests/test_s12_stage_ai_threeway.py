"""Original rich A/B/C rendering, eight-car navigation and no fixed-recipe B."""
from pathlib import Path
import json
import subprocess
import shutil

import numpy as np
import pytest
from scipy.io import wavfile
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import three_way_audition as ui
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import qualified_three_way as qualified
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import SCENES, sha_file
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import seal_payload


@pytest.fixture
def old_package(tmp_path,monkeypatch):
    specs=[]
    for vi,v in enumerate(qualified.VEHICLES):
        root=tmp_path/'sources'/v;web=root/'web_audio';web.mkdir(parents=True)
        scenes=[]
        for i,s in enumerate(SCENES):
            t=np.arange(4800)/48000.
            wave=(7000*np.sin(2*np.pi*(200+vi*40+i)*t)).astype(np.int16)
            ref=(8000*np.sin(2*np.pi*(350+vi*40+i)*t)).astype(np.int16)
            wavfile.write(web/(s+'.wav'),48000,wave);wavfile.write(web/('ref_'+s+'.wav'),48000,ref)
            scenes.append({'id':s,'index':i+1,'title':s,'desc':'controlled fixture','focus':'test',
                           'category':'cruise','candidate_file':s+'.wav','ref_file':'ref_'+s+'.wav'})
        page=root/'input.html';page.write_text('const SCENES='+json.dumps(scenes)+';',encoding='utf-8')
        # Intentional old fixed recipe with B == A: new UI must not call it auto.
        specs.append({'key':v,'name':v,'icon':'','title':v,'subtitle':'legacy fixture',
            'original':root,'feedback':root,'reference':root,'page':page,'status':'READY'})
    monkeypatch.setattr(ui,'_specs',lambda:specs)
    out=tmp_path/'old';ui.build_package(out)
    return out


def _reseal_inventory(root):
    files = {
        path.relative_to(root).as_posix(): sha_file(path)
        for path in root.rglob("*")
        if path.is_file() and path != root / "ARTIFACTS.json"
    }
    manifest = root / "ARTIFACTS.json"
    manifest.unlink()
    qualified.write_json(
        manifest,
        seal_payload({"schema": qualified.SCHEMA, "files": files}, qualified.SCHEMA),
    )


def _replace_embedded(page, name, value):
    text = page.read_text(encoding="utf-8")
    current = ui._embedded(text, name)
    old = "const " + name + " = " + json.dumps(current, ensure_ascii=False)
    new = "const " + name + " = " + json.dumps(value, ensure_ascii=False)
    assert old in text
    page.write_text(text.replace(old, new, 1), encoding="utf-8")


def _valid_fit():
    return {
        "schema": "s12.stage_ah.reference_feedback.v1",
        "status": "RELATIVE_IMPROVEMENT_VALIDATED",
        "baseline_train_loss": 2.0,
        "selected_train_loss": 1.0,
        "baseline_parameters": {"gain": 1.0},
        "selected_parameters": {"gain": 1.1},
        "parameter_delta": {"gain": 0.1},
        "trial_count": 2,
        "history": [
            {"trial": 0, "parameters": {"gain": 1.0}, "loss": 2.0,
             "decision": "TRAIN_REJECTED", "reason": "BASELINE"},
            {"trial": 1, "parameters": {"gain": 1.1}, "loss": 1.0,
             "decision": "TRAIN_ACCEPTED", "reason": "LOWER_TRAIN_LOSS"},
        ],
        "validation_used_for_search": False,
        "validation_baseline": {"validation-case": 1.0},
        "validation_proposed": {"validation-case": 0.9},
        "reference_cases": [
            {"case_id": "train-case", "split": "train", "source_sha256": "a" * 64},
            {"case_id": "validation-case", "split": "validation", "source_sha256": "b" * 64},
        ],
    }


def test_all_eight_preserve_ac_but_fixed_recipes_cannot_be_b(old_package,tmp_path):
    old_manifest_before = sha_file(old_package / "ARTIFACTS.json")
    out=tmp_path/'qualified-abc'
    result=qualified.build(old_package,sha_file(old_package/'ARTIFACTS.json'),out)
    qualified.verify(out,sha_file(out/'ARTIFACTS.json'))
    for v,row in result['vehicles'].items():
        assert not row['source_roles']['feedback']['available']
        assert row['source_roles']['original']['available']
        assert row['source_roles']['reference']['available']
        for s in SCENES:
            for role in ('A','C'):
                name=role+'_'+s+'.wav'
                assert (old_package/v/'web_audio'/name).read_bytes()==(out/v/'web_audio'/name).read_bytes()
            assert not (out/v/'web_audio'/('B_'+s+'.wav')).exists()
        text=(out/v/'index.html').read_text(encoding='utf-8')
        assert '实时动态声学分析仪' in text and 'vehicleSwitcher' in text
        assert all('../'+car+'/index.html' in text for car in qualified.VEHICLES)
        assert 'audioEl.removeAttribute' in text
        receipt = json.loads((out / "evidence" / (v + "-qualification.json")).read_text(encoding="utf-8"))
        assert receipt["schema"] == qualified.VEHICLE_QUALIFICATION_SCHEMA
        assert set(receipt["roles"]) == {"original", "feedback", "reference"}
    assert result["schema"] == qualified.SCHEMA
    assert result["feedback_ready_vehicle_count"] == 0
    assert result["package_status"] == "PARTIAL_B_AVAILABILITY"
    assert sha_file(old_package / "ARTIFACTS.json") == old_manifest_before
    # Same-schema metadata corruption can no longer pass verification.
    path=out/'hellcat'/'index.html';path.write_text(path.read_text(encoding='utf-8')+'tampered',encoding='utf-8')
    with pytest.raises(ValueError):qualified.verify(out)


def test_resealed_same_schema_embedded_contract_drift_is_rejected(old_package, tmp_path):
    out = tmp_path / "same-schema-drift"
    qualified.build(old_package, sha_file(old_package / "ARTIFACTS.json"), out)
    page = out / "rx7_fd" / "index.html"
    contract = ui._embedded(page.read_text(encoding="utf-8"), "DASHBOARD_CONTRACT")
    contract["source_roles"]["original"]["label"] = "fabricated same-schema label"
    _replace_embedded(page, "DASHBOARD_CONTRACT", contract)
    _reseal_inventory(out)
    with pytest.raises(ValueError, match="embedded contract"):
        qualified.verify(out)


def test_resealed_missing_c_audio_store_entry_is_rejected(old_package, tmp_path):
    out = tmp_path / "missing-c-store"
    qualified.build(old_package, sha_file(old_package / "ARTIFACTS.json"), out)
    page = out / "hellcat" / "index.html"
    store = ui._embedded(page.read_text(encoding="utf-8"), "AUDIO_STORE")
    store.pop(SCENES[0] + "_reference")
    _replace_embedded(page, "AUDIO_STORE", store)
    _reseal_inventory(out)
    with pytest.raises(ValueError, match="source mapping"):
        qualified.verify(out)


def test_fabricated_fit_pass_is_rejected():
    fit = _valid_fit()
    qualified._validate_fit_evidence(fit)
    fit["status"] = "FABRICATED_PASS"
    with pytest.raises(ValueError, match="measured/validated fit"):
        qualified._validate_fit_evidence(fit)


def test_missing_enabled_b_qualification_receipt_is_rejected(old_package, tmp_path):
    out = tmp_path / "missing-b-receipt"
    qualified.build(old_package, sha_file(old_package / "ARTIFACTS.json"), out)
    receipt = out / "evidence" / "rx7_fd-qualification.json"
    assert receipt.is_file()
    receipt.unlink()
    _reseal_inventory(out)
    with pytest.raises(ValueError, match="qualification receipt"):
        qualified.verify(out)


def test_rx7_provenance_and_complete_fit_evidence_are_visible():
    template = ui.TEMPLATE_PATH.read_text(encoding="utf-8")
    fit = _valid_fit()
    scenes = [{"id": SCENES[0], "title": "x", "desc": "x", "category": "idle",
               "candidate_file": "A.wav", "feedback_file": "B.wav",
               "reference_file": "", "ab_pcm_identical": True}]
    contract = {
        "source_roles": {
            "original": {"available": True, "label": "A: AI-5 feedback-off baseline after rx7_start_boundary_fade_v1"},
            "feedback": {"available": True, "label": "B: AI-5 tuned"},
            "reference": {"available": False, "label": "C: governed reference"},
        },
        "feedback_evidence": {"kind": "AUTOMATIC_REFERENCE_CLOSED_LOOP"},
        "a_provenance": {
            "byte_identity_to_pre_ai4b_a": False,
            "boundary_policy": "rx7_start_boundary_fade_v1",
            "boundary_difference_frames": 24,
            "old_a_sha256": "a" * 64,
        },
    }
    page = qualified.rich_page(template, "rx7_fd", "RX-7", scenes, contract, {}, [],
                               "../evidence/rx7-log.html", fit)
    assert "rx7_start_boundary_fade_v1" in page
    assert "24" in page and "pre-AI4B" in page
    assert "gain" in page and "1.1" in page
    assert "baseline_train_loss" in page and "validation_proposed" in page
    assert "LOWER_TRAIN_LOSS" in page
    assert "A/B相同场景" in page
    assert "0 parameters" not in page and "NOT_MEASURED" not in page


def test_unavailable_source_switch_stops_stale_audio(old_package,tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node required for actual JavaScript state transition check')
    template=ui.TEMPLATE_PATH.read_text(encoding='utf-8')
    scenes=[{'id':'scene','title':'x','desc':'x','category':'idle','candidate_file':'A.wav','ref_file':''}]
    contract={'source_roles':{'original':{'available':True},'feedback':{'available':False},'reference':{'available':False}},
              'feedback_evidence':{'kind':'NO_QUALIFIED_AUTOMATIC_B'}}
    contract['source_roles']['feedback']['reason']='blocked'
    page=qualified.rich_page(template,'hellcat','test',scenes,contract,{},[],None)
    script=page.split('<script>\nconst TRIWAY_ROLES',1)[1].split('</script>',1)[0]
    script='const TRIWAY_ROLES'+script
    harness="""
let paused=false, removed=false, loaded=false;
let isPlaying=true,currentSceneIndex=0,currentSource='candidate',playbackSpeed=1,isLooping=false;
const SCENES=[{id:'scene'}],AUDIO_STORE={},DASHBOARD_CONTRACT={source_roles:{feedback:{available:false}}};
const audioEl={currentTime:2,pause(){paused=true},removeAttribute(){removed=true},load(){loaded=true}};
let renderSceneCards=()=>{},loadScene,changeScene,selectAndPlayScene;
const document={querySelectorAll(){return []},getElementById(){return null}};
const window={addEventListener(){}};
"""+script+"""
triSetAudio('feedback',false);
if(!paused||!removed||!loaded||isPlaying)throw new Error('stale audio remained active');
"""
    run=subprocess.run([node,'-e',harness],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
