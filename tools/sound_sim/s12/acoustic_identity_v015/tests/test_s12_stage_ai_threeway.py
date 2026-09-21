"""Original rich A/B/C rendering, eight-car navigation and no fixed-recipe B."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import shutil

import numpy as np
import pytest
from scipy.io import wavfile
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import three_way_audition as ui
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import qualified_three_way as qualified
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import SCENES, sha_file
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.qualification import (
    build_qualification_receipt,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reconstruction_peak import (
    reconstructed_peak_receipt,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.continuous_drive import (
    CONTINUOUS_SCHEMA,
    CONTINUOUS_SCENE_ID,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import continuous_drive as cycle
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.package_integrity import seal_payload


@pytest.fixture
def old_package(tmp_path,monkeypatch):
    specs=[]
    for vi,v in enumerate(qualified.VEHICLES):
        root=tmp_path/'sources'/v;web=root/'web_audio';web.mkdir(parents=True)
        scenes=[]
        for i,s in enumerate(SCENES):
            t=np.arange(4800)/48000.
            mono=(7000*np.sin(2*np.pi*(200+vi*40+i)*t)).astype(np.int16)
            wave=np.column_stack((mono,mono))
            ref_mono=(8000*np.sin(2*np.pi*(350+vi*40+i)*t)).astype(np.int16)
            ref=np.column_stack((ref_mono,ref_mono))
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


def _overwrite_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")


def _sync_vehicle_evidence(root, vehicle, info):
    folder=root/vehicle
    contract=json.loads((folder/"dashboard_contract.json").read_text(encoding="utf-8"))
    contract=seal_payload({**contract,"feedback_evidence":info},qualified.SCHEMA)
    _overwrite_json(folder/"dashboard_contract.json",contract)
    for name in ("index.html","index_standalone.html"):
        page=folder/name
        _replace_embedded(page,"DASHBOARD_CONTRACT",contract)
    summary=json.loads((root/"summary.json").read_text(encoding="utf-8"))
    summary["vehicles"][vehicle]["feedback_evidence"]=info
    summary=seal_payload(summary,qualified.SCHEMA)
    _overwrite_json(root/"summary.json",summary)
    _reseal_inventory(root)


def _reseal_vehicle_receipt(root,vehicle,mutate):
    path=root/"evidence"/(vehicle+"-qualification.json")
    receipt=json.loads(path.read_text(encoding="utf-8"));mutate(receipt)
    receipt=seal_payload(receipt,qualified.VEHICLE_QUALIFICATION_SCHEMA)
    _overwrite_json(path,receipt)
    contract=json.loads((root/vehicle/"dashboard_contract.json").read_text(encoding="utf-8"))
    info=copy.deepcopy(contract["feedback_evidence"])
    info["vehicle_qualification_receipt_sha256"]=sha_file(path)
    _sync_vehicle_evidence(root,vehicle,info)


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


def _record(vehicle, scene, pcm):
    audio=pcm.astype(np.float64)/32767.0
    peak=float(np.max(np.abs(audio)))
    return {
        "vehicle":vehicle,"scene_id":scene,
        "trace_sha256":hashlib.sha256(scene.encode()).hexdigest(),
        "sample_rate_hz":48000,"sample_count":len(pcm),"seed":20260908,
        "flags":[],"parent_peak_key":"parent/"+scene,"parent_peak":0.8,
        "candidate_raw_peak":0.7,"normalization_denominator":0.8,
        "output_policy":"linked_soft_ceiling_v1",
        "normalization":{"output_policy":"linked_soft_ceiling_v1",
            "normalization_denominator":0.8,"legacy_ceiling_input_exceedance_samples":0,
            "legacy_transfer_pre_guard_peak":0.7,"pre_guard_exceedance_longest_run":0,
            "pre_guard_peak":0.7,"frame_count":len(pcm),"soft_guard_active_frames":0,
            "soft_guard_delta_peak":0.0,"soft_guard_delta_rms":0.0,
            "post_guard_peak":peak,"post_guard_ceiling_exceedance_samples":0,
            "emergency_clip_count":0,"emergency_clip_error":0.0,
            "emergency_clip_error_rms":0.0},
        "identity_layer_clip_count":0,"identity_layer_clip_error":0.0,
        "post_identity_clip_count":0,"post_identity_clip_error":0.0,
        "final_peak":peak,"final_rms":float(np.sqrt(np.mean(audio*audio))),
        "final_pcm_sha256":hashlib.sha256(np.ascontiguousarray(pcm,dtype="<i2").tobytes()).hexdigest(),
        "peak_estimate_4x":{"peak":peak},"reconstruction_peak":reconstructed_peak_receipt(audio),
    }


def _continuous_event_report(*, source_onset=18.043, observed_onset=18.043,
                             observed_frame=866064, count=1, energy=1.0):
    return {
        "sample_count": 1_440_000,
        "candidate_source_diagnostics": {
            "shift_event_count": 3,
            "afterfire_event_count": count,
            "afterfire_stem_energy_after_lift": energy,
            "afterfire_requested_event_times_s": [18.0],
            "afterfire_onset_s": source_onset,
            "afterfire_observed_onset_s": observed_onset,
            "afterfire_observed_onset_frame": observed_frame,
            "afterfire_observation_domain": "SOURCE_STEM_PRE_IR",
        },
    }


def _continuous_event_receipt(reports):
    events = cycle.continuous_events()
    events.update({
        "shift_count": 3,
        "afterfire_event_count": 1,
        "afterfire_stem_energy_after_lift": 1.0,
        "afterfire_requested_event_times_s": [18.0],
        "afterfire_source_onset_s": 18.043,
        "afterfire_observed_onset_s": 18.043,
        "afterfire_observed_onset_frame": 866064,
        "afterfire_observation_domain": "SOURCE_STEM_PRE_IR",
        "stateful_single_render_per_role": True,
    })
    return {
        "schema": CONTINUOUS_SCHEMA,
        "vehicle": "rx7_fd",
        "duration_s": 30.0,
        "sample_rate_hz": 48_000,
        "events": events,
        "reports": reports,
    }


@pytest.fixture
def enabled_b_package(old_package,tmp_path,monkeypatch):
    vehicle="rx7_fd";source=tmp_path/"ai5-source"
    fit=_valid_fit();fit["baseline_records"]={};fit["selected_records"]={}
    for scene in SCENES:
        _,old_pcm=wavfile.read(old_package/vehicle/"web_audio"/("A_"+scene+".wav"))
        baseline=old_pcm.copy();baseline[20:23]+=1
        tuned=baseline.copy();tuned[100:103]+=1
        for role,pcm,field in (("baseline",baseline,"baseline_records"),("tuned",tuned,"selected_records")):
            web=source/role/vehicle/"web_audio";web.mkdir(parents=True,exist_ok=True)
            wavfile.write(web/(scene+".wav"),48000,pcm)
            fit[field][scene]=_record(vehicle,scene,pcm)
    fit["baseline_records"]["09_steady_mid"]["boundary_repair"]={
        "policy_id":"rx7_start_boundary_fade_v1","fade_frames":24,
        "modified_frames":24,"scope":"rx7_start_boundary_only","stereo_link":"common_frame_ramp"}
    other="aventador_lp700";no_improvement=_valid_fit()
    no_improvement.update(status="NO_IMPROVEMENT",baseline_records={},selected_records={},
                          selected_parameters={"gain":1.0},parameter_delta={"gain":0.0})
    for scene in SCENES:
        _,pcm=wavfile.read(old_package/other/"web_audio"/("A_"+scene+".wav"))
        for role,field in (("baseline","baseline_records"),("tuned","selected_records")):
            web=source/role/other/"web_audio";web.mkdir(parents=True,exist_ok=True)
            wavfile.write(web/(scene+".wav"),48000,pcm)
            no_improvement[field][scene]=_record(other,scene,pcm)
    summary={"schema":"s12.stage_ah.reference_feedback_run.v1",
             "output_policy":"linked_soft_ceiling_v1","vehicles":{vehicle:fit,other:no_improvement}}
    (source/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    source_files={path.relative_to(source).as_posix():sha_file(path) for path in source.rglob("*") if path.is_file()}
    _overwrite_json(source/"ARTIFACTS.json",seal_payload({"files":source_files},"s12.test.source.manifest.v1"))
    task1=build_qualification_receipt(source,summary)
    assert task1["status"]=="PASS" and task1["qualified_vehicle_count"]==2
    source_sha=sha_file(source/"ARTIFACTS.json")
    monkeypatch.setattr(qualified,"_feedback_source",lambda *args:(source,summary,task1,source_sha))
    monkeypatch.setattr(qualified,"_runtime_identity",lambda:{"fixture":"clean"})
    out=tmp_path/"enabled-b"
    qualified.build(old_package,sha_file(old_package/"ARTIFACTS.json"),out,
                    two_run=source,two_sha=source_sha)
    return out


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
    with pytest.raises(ValueError, match="source role coverage"):
        qualified.verify(out)


def test_fabricated_fit_pass_is_rejected():
    fit = _valid_fit()
    qualified._validate_fit_evidence(fit)
    fit["status"] = "FABRICATED_PASS"
    with pytest.raises(ValueError, match="measured/validated fit"):
        qualified._validate_fit_evidence(fit)


def test_historical_vehicle_row_without_display_name_uses_canonical_key():
    assert qualified._vehicle_name({}, "rx7_fd") == "rx7_fd"


def test_resealed_task1_summary_binding_drift_is_rejected(enabled_b_package):
    root=enabled_b_package;vehicle="rx7_fd"
    task1=root/"evidence"/(vehicle+"-task1-qualification.json")
    value=json.loads(task1.read_text(encoding="utf-8"))
    value["summary_sha256"]="0"*64
    _overwrite_json(task1,value)
    receipt_path=root/"evidence"/(vehicle+"-qualification.json")
    receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["fit_evidence"]["task1_qualification_receipt_sha256"]=sha_file(task1)
    receipt=seal_payload(receipt,qualified.VEHICLE_QUALIFICATION_SCHEMA)
    _overwrite_json(receipt_path,receipt)
    contract=json.loads((root/vehicle/"dashboard_contract.json").read_text(encoding="utf-8"))
    info=copy.deepcopy(contract["feedback_evidence"])
    info["task1_qualification_receipt_sha256"]=sha_file(task1)
    info["vehicle_qualification_receipt_sha256"]=sha_file(receipt_path)
    _sync_vehicle_evidence(root,vehicle,info)
    with pytest.raises(ValueError,match="Task-1"):
        qualified.verify(root)


def test_mixed_source_no_improvement_vehicle_stays_unavailable(enabled_b_package):
    summary=qualified.verify(enabled_b_package)
    assert summary["vehicles"]["rx7_fd"]["source_roles"]["feedback"]["available"] is True
    assert summary["vehicles"]["aventador_lp700"]["source_roles"]["feedback"]["available"] is False


def test_resealed_fit_measurement_drift_is_rejected(enabled_b_package):
    root = enabled_b_package
    vehicle = "rx7_fd"
    contract = json.loads((root / vehicle / "dashboard_contract.json").read_text(encoding="utf-8"))
    contract["fit_baseline_distance"] = 99.0
    contract = seal_payload(contract, qualified.SCHEMA)
    for page_name in ("index.html", "index_standalone.html"):
        page = root / vehicle / page_name
        _replace_embedded(page, "DASHBOARD_CONTRACT", contract)
    _overwrite_json(root / vehicle / "dashboard_contract.json", contract)
    _reseal_inventory(root)
    with pytest.raises(ValueError, match="fit|contract|evidence"):
        qualified.verify(root)


def test_resealed_visible_fit_evidence_drift_is_rejected(enabled_b_package):
    root = enabled_b_package
    vehicle = "rx7_fd"
    for page_name in ("index.html", "index_standalone.html"):
        page = root / vehicle / page_name
        text = page.read_text(encoding="utf-8")
        assert '&quot;baseline_train_loss&quot;: 2.0' in text
        page.write_text(text.replace('&quot;baseline_train_loss&quot;: 2.0',
                                     '&quot;baseline_train_loss&quot;: 99.0', 1),
                        encoding="utf-8")
    _reseal_inventory(root)
    with pytest.raises(ValueError, match="visible|fit UI|evidence"):
        qualified.verify(root)


def test_continuous_scene_requires_accepted_feedback_source(old_package, tmp_path, monkeypatch):
    monkeypatch.setattr(qualified, "_runtime_identity", lambda: {"fixture": "clean"})
    pcm = np.full((1_440_000, 2), 100, dtype=np.int16)
    pair = {
        "pcm_a": pcm,
        "pcm_b": pcm.copy(),
        "receipt": {
            "schema": CONTINUOUS_SCHEMA, "vehicle": "rx7_fd",
            "scene_id": CONTINUOUS_SCENE_ID, "duration_s": 30.0,
            "sample_rate_hz": 48_000,
            "shared": {"seed": 20260908, "trace_sha256": "a" * 64,
                       "parent_peak_key": "continuous_drive|" + "a" * 64,
                       "normalization_denominator": 0.4,
                       "output_policy": "linked_soft_ceiling_v1"},
            "events": {
                "shift_count": 3,
                "shift_events": cycle.continuous_events()["shift_events"],
                "afterfire_event_count": 1,
                "afterfire_events": cycle.continuous_events()["afterfire_events"],
                "afterfire_requested_event_times_s": [18.0],
                "afterfire_stem_energy_after_lift": 1.0,
                "afterfire_source_onset_s": 18.0,
                "afterfire_observed_onset_s": 18.0,
                "afterfire_observed_onset_frame": 864000,
                "afterfire_observation_domain": "SOURCE_STEM_PRE_IR",
                "stateful_single_render_per_role": True,
            },
            "boundary": {"policy_id": "rx7_start_boundary_fade_v1", "fade_frames": 24},
        },
    }
    out = tmp_path / "continuous-ui"
    with pytest.raises(ValueError, match="accepted feedback"):
        qualified.build(old_package, sha_file(old_package / "ARTIFACTS.json"), out,
                        continuous_pairs={"rx7_fd": pair})


def test_resealed_continuous_event_drift_is_rejected_semantically():
    reports = {role: _continuous_event_report() for role in ("A", "B", "off_switch")}
    receipt = _continuous_event_receipt(reports)
    cycle.validate_event_contract(receipt)

    receipt["events"]["afterfire_source_onset_s"] = 19.0
    receipt["events"]["afterfire_observed_onset_s"] = 19.0
    receipt["events"]["afterfire_observed_onset_frame"] = 912000
    with pytest.raises(ValueError, match="event"):
        cycle.validate_event_contract(receipt)


def test_resealed_vehicle_receipt_outcome_drift_is_rejected(enabled_b_package):
    _reseal_vehicle_receipt(enabled_b_package,"rx7_fd",
                            lambda value:value.__setitem__("outcome","B_UNAVAILABLE"))
    with pytest.raises(ValueError,match="outcome"):
        qualified.verify(enabled_b_package)


def test_resealed_vehicle_receipt_fit_binding_drift_is_rejected(enabled_b_package):
    def mutate(value):
        value["fit_evidence"]["source_manifest_sha256"]="0"*64
    _reseal_vehicle_receipt(enabled_b_package,"rx7_fd",mutate)
    with pytest.raises(ValueError,match="fit evidence"):
        qualified.verify(enabled_b_package)


def test_resealed_source_path_rebinding_is_rejected(enabled_b_package):
    root=enabled_b_package
    def mutate(value):
        value["scenes"][SCENES[0]]["original"]["source_path"]=str(
            (root/"rx7_fd"/"web_audio"/("A_"+SCENES[0]+".wav")).resolve())
    _reseal_vehicle_receipt(root,"rx7_fd",mutate)
    with pytest.raises(ValueError,match="source path"):
        qualified.verify(root)


def test_resealed_c_role_deletion_cannot_erase_build_time_availability(old_package,tmp_path):
    out=tmp_path/"deleted-c";qualified.build(old_package,sha_file(old_package/"ARTIFACTS.json"),out)
    vehicle="hellcat";scene=SCENES[0];folder=out/vehicle
    c_name="C_"+scene+".wav";(folder/"web_audio"/c_name).unlink()
    contract=json.loads((folder/"dashboard_contract.json").read_text(encoding="utf-8"))
    contract["source_sha256"]["reference"].pop(c_name)
    receipt_path=out/"evidence"/(vehicle+"-qualification.json")
    receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["scenes"][scene].pop("reference")
    receipt=seal_payload(receipt,qualified.VEHICLE_QUALIFICATION_SCHEMA)
    _overwrite_json(receipt_path,receipt)
    info=copy.deepcopy(contract["feedback_evidence"])
    info["vehicle_qualification_receipt_sha256"]=sha_file(receipt_path)
    contract["feedback_evidence"]=info
    contract=seal_payload(contract,qualified.SCHEMA);_overwrite_json(folder/"dashboard_contract.json",contract)
    for page_name in ("index.html","index_standalone.html"):
        page=folder/page_name;text=page.read_text(encoding="utf-8")
        scenes=ui._embedded(text,"SCENES");store=ui._embedded(text,"AUDIO_STORE")
        scenes[0]["reference_file"]="";store.pop(scene+"_reference")
        _replace_embedded(page,"SCENES",scenes);_replace_embedded(page,"AUDIO_STORE",store)
        _replace_embedded(page,"DASHBOARD_CONTRACT",contract)
    summary=json.loads((out/"summary.json").read_text(encoding="utf-8"))
    summary["vehicles"][vehicle]["source_sha256"]["reference"].pop(c_name)
    summary["vehicles"][vehicle]["feedback_evidence"]=info
    summary=seal_payload(summary,qualified.SCHEMA);_overwrite_json(out/"summary.json",summary)
    _reseal_inventory(out)
    with pytest.raises(ValueError,match="build-time|source role coverage"):
        qualified.verify(out)


def test_rx7_boundary_diff_receipt_rejects_change_after_window(tmp_path):
    old=tmp_path/"old.wav";new=tmp_path/"new.wav"
    pcm=np.zeros((64,2),dtype=np.int16);changed=pcm.copy();changed[23]=1
    wavfile.write(old,48000,pcm);wavfile.write(new,48000,changed)
    receipt=qualified._rx7_boundary_diff_receipt(old,new)
    assert receipt["changed_frame_indices"]==[23]
    changed[24]=1;wavfile.write(new,48000,changed)
    with pytest.raises(ValueError,match="24-frame"):
        qualified._rx7_boundary_diff_receipt(old,new)


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
