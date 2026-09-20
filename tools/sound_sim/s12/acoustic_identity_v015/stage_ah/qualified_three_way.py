"""AI-3: attach ONLY measured/validated fits to B of the existing eight-car UI.

Old fixed recipes stay in their old immutable packages, not relabelled as
automatic fitting. A/C are byte copies; B requires a verified fit and ten-scene
trace/numeric/PCM bindings. No renderer is invoked by this module.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
from scipy.io import wavfile

from . import three_way_audition as ui
from .feedback_evidence import AUTO, SCENES, Journal, fit_eligibility, sha_file, write_json
from .fourcar_reference_loop import verify_run as verify_fourcar
from . import reference_feedback_cli as feedback_cli
from .qualification import (
    QUALIFICATION_FILENAME,
    build_qualification_receipt,
)
from .reference_feedback_cli import verify_run as verify_two, numeric_ok, _runtime_identity
from ..stage_af.package_integrity import seal_payload

VEHICLES = ('hellcat','ferrari_458','lfa','gtr_r35','c63_w204','supra_jza80','rx7_fd','aventador_lp700')
SCHEMA = 's12.stage_ai6.qualified_three_way.v1'
VEHICLE_QUALIFICATION_SCHEMA = 's12.stage_ai6.vehicle_qualification.v1'


def _sealed(path):
    return ui._sealed(path)


def verify_legacy(root: Path, expected_sha: str):
    if sha_file(root/'ARTIFACTS.json') != expected_sha:
        raise ValueError('old three-way manifest digest mismatch')
    summary = ui.verify_package(root)
    if set(summary['vehicles']) != set(VEHICLES):
        raise ValueError('old three-way package must cover exactly eight vehicles')
    # Supplement the old verifier: compare identity fields, not merely schemas.
    for v in VEHICLES:
        folder=root/v
        contract=_sealed(folder/'dashboard_contract.json')
        for page in ('index.html','index_standalone.html'):
            text=(folder/page).read_text(encoding='utf-8')
            embedded=ui._embedded(text,'DASHBOARD_CONTRACT')
            if any(embedded.get(k)!=value for k,value in contract.items()):
                raise ValueError('old embedded contract does not match sidecar')
            for scene in ui._embedded(text,'SCENES'):
                for role,key in (('original','candidate_file'),('feedback','feedback_file'),('reference','reference_file')):
                    name=scene.get(key)
                    if name and sha_file(folder/'web_audio'/name)!=contract['source_sha256'][role].get(name):
                        raise ValueError('old A/B/C WAV differs from role contract')
    return summary


def _decoded_pcm_sha(path: Path) -> tuple[int, str]:
    sample_rate, pcm = wavfile.read(path)
    if sample_rate != 48_000 or pcm.dtype != np.int16 or pcm.ndim not in (1, 2):
        raise ValueError(f'role WAV must be 48 kHz int16 PCM: {path}')
    return int(sample_rate), hashlib.sha256(np.ascontiguousarray(pcm, dtype='<i2')).hexdigest()


def _validate_fit_evidence(result):
    if not fit_eligibility(result)['available']:
        raise ValueError('B lacks measured/validated fit')
    return result


def _legacy_feedback_run(root: Path, expected_sha: str):
    """Verify a pre-Task-1 sealed run without mutating it, then qualify it fresh."""
    if sha_file(root / 'ARTIFACTS.json') != expected_sha:
        raise ValueError('feedback source manifest digest mismatch')
    manifest = feedback_cli._sealed(root / 'ARTIFACTS.json')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('feedback source inventory is empty')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and p != root / 'ARTIFACTS.json'}
    if set(files) != actual:
        raise ValueError('feedback source inventory mismatch')
    for relative, digest in files.items():
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or sha_file(path) != digest:
            raise ValueError('feedback source artifact drift')
    summary = feedback_cli._read(root / 'summary.json')
    if summary.get('schema') != feedback_cli.RUN_SCHEMA or summary.get('promotable') is not False:
        raise ValueError('wrong feedback source contract')
    for vehicle, result in summary.get('vehicles', {}).items():
        if result.get('status') == 'ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK':
            raise ValueError(f'feedback source vehicle is blocked: {vehicle}')
        for group in ('baseline', 'tuned'):
            folder = root / group / vehicle
            contract = feedback_cli._sealed(folder / 'dashboard_contract.json')
            for filename in ('index.html', 'index_standalone.html'):
                page = folder / filename
                feedback_cli._verify_html(
                    page, contract,
                    feedback_cli._embedded(page.read_text(encoding='utf-8'), 'SCENES'),
                )
    qualification = build_qualification_receipt(root, summary)
    if qualification.get('status') != 'PASS':
        raise ValueError('feedback source independent qualification is BLOCKED')
    return summary, qualification


def _feedback_source(root: Path, expected_sha: str):
    root = root.resolve()
    if (root / QUALIFICATION_FILENAME).is_file():
        summary = verify_two(root, expected_sha)
        qualification = feedback_cli._read(root / QUALIFICATION_FILENAME)
    else:
        summary, qualification = _legacy_feedback_run(root, expected_sha)
    return root, summary, qualification, expected_sha


def _role_identity(source: Path, packaged: Path) -> dict:
    sample_rate, pcm_sha = _decoded_pcm_sha(packaged)
    source_sha = sha_file(source)
    if source_sha != sha_file(packaged):
        raise ValueError('copied role WAV differs from source')
    return {
        'source_path': str(source.resolve()),
        'source_sha256': source_sha,
        'wav_file_sha256': source_sha,
        'decoded_pcm_sha256': pcm_sha,
        'sample_rate_hz': sample_rate,
    }


def _vehicle_receipt(vehicle: str, roles: dict, scene_roles: dict, *, outcome: str,
                     fit_info: dict | None = None) -> dict:
    payload = {
        'schema': VEHICLE_QUALIFICATION_SCHEMA,
        'vehicle': vehicle,
        'roles': roles,
        'scenes': scene_roles,
        'outcome': outcome,
        'human_status': 'NOT_EVALUATED',
        'promotable': False,
    }
    if fit_info:
        payload['fit_evidence'] = fit_info
    return seal_payload(payload, VEHICLE_QUALIFICATION_SCHEMA)


def _qualified(run: Path, summary, qualification, vehicle: str, old_root: Path,
               *, require_old_a: bool = True):
    result=summary.get('vehicles',{}).get(vehicle)
    if not result:
        return None, '无已验证的自动反馈结果'
    eligibility=fit_eligibility(result)
    if not eligibility['available']:
        return None, ' / '.join(eligibility['reasons'])
    qualified_vehicle=qualification.get('vehicles',{}).get(vehicle)
    if not qualified_vehicle or qualified_vehicle.get('status') != 'PASS':
        raise ValueError('B lacks independent Task-1 qualification')
    for field in ('baseline_records','selected_records'):
        if set(result.get(field,{}))!=set(SCENES) or not all(numeric_ok(r) for r in result[field].values()):
            raise ValueError('fit lacks full numerical qualification')
    changed=0
    for scene in SCENES:
        a,b=result['baseline_records'][scene],result['selected_records'][scene]
        for key in ('trace_sha256','seed','flags','normalization_denominator'):
            if a[key]!=b[key]:
                raise ValueError('A/B context changed: '+key)
        original=old_root/vehicle/'web_audio'/('A_'+scene+'.wav')
        base=run/'baseline'/vehicle/'web_audio'/(scene+'.wav')
        tuned=run/'tuned'/vehicle/'web_audio'/(scene+'.wav')
        if require_old_a and sha_file(original)!=sha_file(base):
            raise ValueError('new-fit baseline differs from audition A; never attach incompatible B')
        for path,record in ((base,a),(tuned,b)):
            sr,pcm=wavfile.read(path)
            if sr!=48000 or pcm.dtype!=np.int16:
                raise ValueError('fit candidates must be 48 kHz int16 PCM')
            digest=hashlib.sha256(np.ascontiguousarray(pcm,dtype='<i2')).hexdigest()
            if digest!=record['final_pcm_sha256']:
                raise ValueError('fit PCM digest mismatch')
        changed+=sha_file(base)!=sha_file(tuned)
    if not changed:
        raise ValueError('accepted fit changed no scene')
    return result, ''


def rich_page(template, vehicle, title, scenes, contract, store, nav, report_link,
              fit_result=None):
    parameters = []
    if fit_result:
        parameters = [
            {'name': name, 'value': value,
             'baseline': fit_result.get('baseline_parameters', {}).get(name)}
            for name, value in fit_result.get('selected_parameters', {}).items()
        ]
    page=ui.build_page_html(template,vehicle,title,
        'A 原算法基线 / B 自动负反馈算法 / C 真车原声 · 有测量和验证才启用B',
        scenes,contract,store,nav,parameters)
    # Fail-safe switching: missing B/C must not keep playing the previous scene
    # while the title/index says another scene. Preserve the original rich UI.
    old="if (!triAvailable(role, scene)) return;"
    new="""if (!triAvailable(role, scene)) {
    audioEl.pause(); audioEl.removeAttribute('src'); audioEl.load();
    isPlaying = false; triSource = role; triSetHeader(scene); renderSceneCards(); return;
  }"""
    if old not in page:
        raise ValueError('triway source-switch contract changed')
    page=page.replace(old,new,1)
    page=page.replace("currentSceneIndex = index;\n  triSetAudio(role, true);",
                      "loadSceneTri(index, role, true);")
    # A/B equality is valid in insensitive states (e.g. Ferrari hot idle); show it.
    panel='<section id="feedbackProof" class="px-6 py-3"><b>闭环证据：</b> '
    panel+=html.escape(contract['feedback_evidence']['kind'])
    if report_link:
        panel+=' · <a href="'+report_link+'">逐次试探、参数差异与独立验证日志</a>'
    else:
        panel+=' · B未启用：'+html.escape(contract['source_roles']['feedback']['reason'])
    same=[s['id'] for s in scenes if s.get('ab_pcm_identical')]
    if same:
        panel+='<p>A/B相同场景（参数在该状态无可见作用，不冒充改善）：'+', '.join(same)+'</p>'
    provenance=contract.get('a_provenance')
    if provenance:
        panel+='<p>RX-7 A 来源：AI-5 feedback-off baseline after '+html.escape(
            str(provenance['boundary_policy']))+'；与 pre-AI4B A 不宣称字节一致。'
        panel+=' 边界差异仅限 '+str(provenance['boundary_difference_frames'])+' 帧。</p>'
    if fit_result:
        visible={key:fit_result[key] for key in (
            'baseline_parameters','selected_parameters','baseline_train_loss',
            'selected_train_loss','validation_baseline','validation_proposed','history'
        )}
        panel+='<details open><summary>完整参数、训练/验证损失与逐次试验</summary><pre>'+html.escape(
            json.dumps(visible,ensure_ascii=False,indent=2,allow_nan=False))+'</pre></details>'
        page=page.replace('NOT_MEASURED','MEASURED_FROM_SEALED_EVIDENCE')
        page=page.replace('0 parameters','MEASURED_PARAMETERS')
    panel+='<p>C 是保留的真车试听对照；训练与验证源、窗口见日志。误差不是机器相似度百分比。</p></section>'
    return page.replace('</header>','</header>'+panel,1)


def build(old_root: Path, old_sha: str, output: Path, *, fourcar_run: Path | None = None,
          fourcar_sha: str | None = None, two_run: Path | None = None, two_sha: str | None = None):
    old_root=old_root.resolve()
    old=verify_legacy(old_root,old_sha)
    runtime=_runtime_identity()
    inputs={}
    if fourcar_run:
        if not fourcar_sha: raise ValueError('fourcar manifest SHA required')
        fourcar_root=fourcar_run.resolve();fourcar_summary=verify_fourcar(fourcar_root,fourcar_sha)
        fourcar_qualification=build_qualification_receipt(fourcar_root,fourcar_summary)
        if fourcar_qualification.get('status')!='PASS':
            raise ValueError('four-car source independent qualification is BLOCKED')
        inputs['fourcar']=(fourcar_root,fourcar_summary,fourcar_qualification,fourcar_sha)
    if two_run:
        if not two_sha: raise ValueError('two-car manifest SHA required')
        inputs['two']=_feedback_source(two_run,two_sha)
    choices={}
    for v in VEHICLES:
        key='fourcar' if v in VEHICLES[:4] else 'two'
        if v=='c63_w204':
            choices[v]=(None,None,None,None,'C63 本阶段没有独立合格的 sealed B 证据')
        elif v=='supra_jza80':
            choices[v]=(None,None,None,None,'Supra 本阶段没有独立合格的 sealed B 证据')
        elif key not in inputs:
            choices[v]=(None,None,None,None,'尚未完成独立自动闭环；固定recipe/overlay不算自动反馈')
        else:
            root,summary,qualification,manifest_sha=inputs[key]
            result,reason=_qualified(root,summary,qualification,v,old_root,
                require_old_a=v not in ('rx7_fd','aventador_lp700'))
            choices[v]=(root,result,qualification,manifest_sha,reason)
    output=output.resolve()
    if not output.name.replace('-','').replace('_','').isalnum():
        raise ValueError('safe output identifier required')
    output.parent.mkdir(parents=True,exist_ok=True)
    lock=output.parent/('.'+output.name+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    staging=None
    try:
        if output.exists():raise FileExistsError(output)
        staging=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
        evidence=staging/'evidence';evidence.mkdir()
        nav=[{'key':v,'name':old['vehicles'][v]['vehicle'],
              'status':'AUTO_B_READY' if choices[v][1] else 'B_UNAVAILABLE'} for v in VEHICLES]
        vehicles={}
        template=ui.TEMPLATE_PATH.read_text(encoding='utf-8')
        for v in VEHICLES:
            folder=staging/v; web=folder/'web_audio';web.mkdir(parents=True)
            scenes=ui._load_scenes(old_root/v/'index.html')
            root,result,source_qualification,source_manifest_sha,reason=choices[v]
            roles={
                'original':{'label':'A: 原算法（本轮基线）','available':True,'status':'BASELINE'},
                'feedback':{'label':'B: 自动负反馈算法','available':bool(result),
                    'status':AUTO if result else 'NO_QUALIFIED_AUTOMATIC_B','reason':reason},
                'reference':{'label':'C: 真车原声','available':False,'status':'R3/R2_UNSYNCHRONIZED'}}
            if v=='rx7_fd' and result:
                roles['original']['label']='A: AI-5 feedback-off baseline after rx7_start_boundary_fade_v1'
            elif v=='aventador_lp700' and result:
                roles['original']['label']='A: AI-5 feedback-off baseline'
            hashes={k:{} for k in roles};store={};scene_roles={}
            for s in scenes:
                scene=s['id']
                a='A_'+scene+'.wav'
                old_a=old_root/v/'web_audio'/a
                a_source=(root/'baseline'/v/'web_audio'/(scene+'.wav')
                          if result and v in ('rx7_fd','aventador_lp700') else old_a)
                shutil.copy2(a_source,web/a)
                s['candidate_file']=a;hashes['original'][a]=sha_file(web/a)
                store[scene+'_original']=store[scene+'_candidate']='web_audio/'+a
                scene_roles[scene]={'original':_role_identity(a_source,web/a)}
                s['feedback_file']=s['ref_file']=''
                s['ab_pcm_identical']=False
                if result:
                    b='B_'+scene+'.wav';b_source=root/'tuned'/v/'web_audio'/(scene+'.wav')
                    shutil.copy2(b_source,web/b)
                    s['feedback_file']=s['ref_file']=b;hashes['feedback'][b]=sha_file(web/b)
                    store[scene+'_feedback']=store[scene+'_ref']='web_audio/'+b
                    s['ab_pcm_identical']=hashes['original'][a]==hashes['feedback'][b]
                    scene_roles[scene]['feedback']=_role_identity(b_source,web/b)
                c=s.get('reference_file','')
                if c:
                    c_source=old_root/v/'web_audio'/c;shutil.copy2(c_source,web/c)
                    hashes['reference'][c]=sha_file(web/c);store[scene+'_reference']='web_audio/'+c
                    scene_roles[scene]['reference']=_role_identity(c_source,web/c)
            roles['reference']['available']=bool(hashes['reference'])
            info={'kind':AUTO if result else 'NO_QUALIFIED_AUTOMATIC_B','available':bool(result)}
            link=None;fit_info=None
            if result:
                _validate_fit_evidence(result)
                log_path=evidence/(v+'-fit.json');write_json(log_path,result)
                task1_path=evidence/(v+'-task1-qualification.json')
                write_json(task1_path,source_qualification)
                trials_path=evidence/(v+'-trials.jsonl')
                with Journal(trials_path) as journal:
                    for row in result['history']:journal.append('MEASURED_TRIAL',row)
                    journal.append('SELECTION',{'status':result['status'],'selected_parameters':result['selected_parameters']})
                info.update(fit_report='evidence/'+log_path.name,fit_report_sha256=sha_file(log_path),
                    trial_log='evidence/'+trials_path.name,trial_log_sha256=sha_file(trials_path),
                    task1_qualification_receipt='evidence/'+task1_path.name,
                    task1_qualification_receipt_sha256=sha_file(task1_path),
                    source_manifest_sha256=source_manifest_sha,
                    trial_count=result['trial_count'],parameter_delta=result['parameter_delta'])
                fit_info=dict(info)
                log_html=evidence/(v+'-log.html')
                text='<html lang="zh-CN"><meta charset="utf-8"><title>负反馈试验日志</title><h1>'+v+'</h1>'
                text+='<p>训练误差不是相似度；验证源不用于搜参；没有Human PASS。</p><pre>'+html.escape(json.dumps(
                    {k:result[k] for k in ('status','baseline_train_loss','selected_train_loss','parameter_delta',
                        'validation_baseline','validation_proposed','history','reference_cases')},ensure_ascii=False,indent=2))+'</pre></html>'
                log_html.write_text(text,encoding='utf-8');link='../evidence/'+log_html.name
            a_provenance=None
            if v=='rx7_fd' and result:
                boundary=result['baseline_records']['09_steady_mid'].get('boundary_repair',{})
                if (boundary.get('policy_id')!='rx7_start_boundary_fade_v1'
                        or boundary.get('fade_frames')!=24 or boundary.get('modified_frames')!=24):
                    raise ValueError('RX-7 AI-5 A lacks 24-frame boundary-difference evidence')
                a_provenance={
                    'source':'AI-5 feedback-off baseline',
                    'boundary_policy':'rx7_start_boundary_fade_v1',
                    'boundary_difference_frames':24,
                    'byte_identity_to_pre_ai4b_a':False,
                    'old_a_source_root':str((old_root/v/'web_audio').resolve()),
                    'old_a_sha256':{scene:sha_file(old_root/v/'web_audio'/('A_'+scene+'.wav')) for scene in SCENES},
                }
            role_receipt={role:{'available':bool(data['available']),
                               'status':data.get('status'),
                               'reason':data.get('reason','')}
                          for role,data in roles.items()}
            qualification_receipt=_vehicle_receipt(
                v,role_receipt,scene_roles,
                outcome='B_READY' if result else 'B_UNAVAILABLE',fit_info=fit_info)
            receipt_path=evidence/(v+'-qualification.json');write_json(receipt_path,qualification_receipt)
            info['vehicle_qualification_receipt']='evidence/'+receipt_path.name
            info['vehicle_qualification_receipt_sha256']=sha_file(receipt_path)
            contract=seal_payload({'schema':SCHEMA,'package_id':output.name+'-'+v,'vehicle':v,
                'source_roles':roles,'source_sha256':hashes,'feedback_evidence':info,
                'references':{k:{'available':True,'sha256':h} for k,h in hashes['reference'].items()},
                'candidate_pcm_sha256':hashes['original'],'reference_sha256':hashes['reference'],
                'a_provenance':a_provenance,
                'fit_baseline_distance':result['baseline_train_loss'] if result else None,
                'fit_final_distance':result['selected_train_loss'] if result else None,
                'fit_metric_status':'MEASURED_FROM_SEALED_EVIDENCE' if result else 'B_UNAVAILABLE',
                'fit_status':result['status'] if result else 'B_UNAVAILABLE',
                'human_status':'NOT_EVALUATED','promotable':False,'source_status':'SOURCE_CLEAN',
                'scene_count':10,'sample_rate_hz':48000,'comparison':'A_BASELINE_B_VALIDATED_AUTO_C_REAL'},SCHEMA)
            write_json(folder/'dashboard_contract.json',contract)
            page=rich_page(template,v,old['vehicles'][v]['vehicle'],scenes,contract,store,nav,link,result)
            for name in ('index.html','index_standalone.html'):(folder/name).write_text(page,encoding='utf-8')
            vehicles[v]={'source_roles':roles,'source_sha256':hashes,'feedback_evidence':info,
                         'a_provenance':a_provenance,'scene_count':10}
        ready_count=sum(row['source_roles']['feedback']['available'] for row in vehicles.values())
        summary=seal_payload({'schema':SCHEMA,'run_id':output.name,'runtime':runtime,'vehicles':vehicles,
            'old_threeway_manifest_sha256':old_sha,'fourcar_manifest_sha256':fourcar_sha,'two_car_manifest_sha256':two_sha,
            'feedback_ready_vehicle_count':ready_count,'package_status':'PARTIAL_B_AVAILABILITY',
            'promotable':False,'human_status':'NOT_EVALUATED'},SCHEMA)
        write_json(staging/'summary.json',summary)
        (staging/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>三路声浪对照</h1>'+
            ''.join('<p><a href="'+v+'/index.html">'+v+'</a></p>' for v in VEHICLES),encoding='utf-8')
        verify_legacy(old_root,old_sha)
        if fourcar_run:verify_fourcar(fourcar_run,fourcar_sha)
        if two_run:_feedback_source(two_run,two_sha)
        if _runtime_identity()!=runtime:raise ValueError('source changed while packaging')
        files={p.relative_to(staging).as_posix():sha_file(p) for p in staging.rglob('*') if p.is_file()}
        write_json(staging/'ARTIFACTS.json',seal_payload({'schema':SCHEMA,'files':files},SCHEMA))
        verify(staging)
        staging.rename(output);staging=None
        return summary
    finally:
        if staging is not None:shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def verify(root:Path, expected_sha:str|None=None):
    root=root.resolve()
    if expected_sha and sha_file(root/'ARTIFACTS.json')!=expected_sha:raise ValueError('manifest SHA mismatch')
    m=_sealed(root/'ARTIFACTS.json');files=m['files']
    if m['schema']!=SCHEMA:raise ValueError('wrong ABC schema')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'ARTIFACTS.json'}
    if set(files)!=actual:raise ValueError('ABC inventory mismatch')
    for rel,digest in files.items():
        p=root/rel
        if p.is_symlink() or not p.resolve().is_relative_to(root) or sha_file(p)!=digest:raise ValueError('ABC artifact drift')
    summary=_sealed(root/'summary.json')
    if summary.get('schema')!=SCHEMA or summary.get('package_status')!='PARTIAL_B_AVAILABILITY':
        raise ValueError('wrong AI-6 summary contract')
    if set(summary['vehicles'])!=set(VEHICLES):raise ValueError('eight vehicles required')
    ready_count=sum(row['source_roles']['feedback']['available'] for row in summary['vehicles'].values())
    if summary.get('feedback_ready_vehicle_count')!=ready_count or ready_count==len(VEHICLES):
        raise ValueError('package-wide B availability is misleading')
    for v in VEHICLES:
        folder=root/v;contract=_sealed(folder/'dashboard_contract.json')
        stored=json.loads((folder/'dashboard_contract.json').read_text(encoding='utf-8'))
        if contract['source_roles']!=summary['vehicles'][v]['source_roles']:raise ValueError('ABC role identity mismatch')
        if contract.get('a_provenance')!=summary['vehicles'][v].get('a_provenance'):
            raise ValueError('A provenance mismatch')
        info=contract['feedback_evidence']
        receipt_path=root/info.get('vehicle_qualification_receipt','')
        if (not receipt_path.is_file()
                or sha_file(receipt_path)!=info.get('vehicle_qualification_receipt_sha256')):
            raise ValueError('vehicle qualification receipt missing or changed')
        receipt=_sealed(receipt_path)
        if receipt.get('schema')!=VEHICLE_QUALIFICATION_SCHEMA or receipt.get('vehicle')!=v:
            raise ValueError('vehicle qualification receipt mismatch')
        for role in ('original','feedback','reference'):
            if receipt['roles'][role]['available']!=contract['source_roles'][role]['available']:
                raise ValueError('vehicle qualification role mismatch')
        if contract['source_roles']['feedback']['available']:
            fit=root/info['fit_report']
            if sha_file(fit)!=info['fit_report_sha256']:
                raise ValueError('B fit evidence hash mismatch')
            result=json.loads(fit.read_text(encoding='utf-8'));_validate_fit_evidence(result)
            task1=root/info.get('task1_qualification_receipt','')
            if (not task1.is_file()
                    or sha_file(task1)!=info.get('task1_qualification_receipt_sha256')):
                raise ValueError('Task-1 qualification receipt missing or changed')
            source_qualification=json.loads(task1.read_text(encoding='utf-8'))
            source_vehicle=source_qualification.get('vehicles',{}).get(v)
            if not source_vehicle or source_vehicle.get('status')!='PASS':
                raise ValueError('Task-1 qualification did not enable B')
        else:
            result=None;source_vehicle=None
        for page in ('index.html','index_standalone.html'):
            text=(folder/page).read_text(encoding='utf-8')
            if ui._embedded(text,'DASHBOARD_CONTRACT')!=stored:raise ValueError('embedded contract differs')
            scenes=ui._embedded(text,'SCENES');store=ui._embedded(text,'AUDIO_STORE')
            if [s['id'] for s in scenes]!=list(SCENES):raise ValueError('ten scenes required')
            for s in scenes:
                for role,field in (('original','candidate_file'),('feedback','feedback_file'),('reference','reference_file')):
                    name=s.get(field,'');key=s['id']+'_'+role
                    if not name:
                        if key in store:raise ValueError('disabled role retains audio')
                        continue
                    if (key not in store or store[key]!='web_audio/'+name
                            or sha_file(folder/'web_audio'/name)!=contract['source_sha256'][role].get(name)):
                        raise ValueError('A/B/C source mapping mismatch')
                    identity=receipt['scenes'].get(s['id'],{}).get(role)
                    sample_rate,pcm_sha=_decoded_pcm_sha(folder/'web_audio'/name)
                    if (not identity or identity.get('source_sha256')!=sha_file(folder/'web_audio'/name)
                            or identity.get('wav_file_sha256')!=sha_file(folder/'web_audio'/name)
                            or identity.get('decoded_pcm_sha256')!=pcm_sha
                            or identity.get('sample_rate_hz')!=sample_rate):
                        raise ValueError('role WAV/PCM/source identity mismatch')
                if s.get('feedback_file'):
                    identical=(sha_file(folder/'web_audio'/s['candidate_file'])
                               ==sha_file(folder/'web_audio'/s['feedback_file']))
                    if s.get('ab_pcm_identical') is not identical:
                        raise ValueError('A/B identical-scene label mismatch')
            if result:
                for marker in ('baseline_parameters','selected_parameters','baseline_train_loss',
                               'selected_train_loss','validation_baseline','validation_proposed','history'):
                    if marker not in text:raise ValueError('fit/trial evidence missing from UI')
                if '0 parameters' in text or 'NOT_MEASURED' in text:
                    raise ValueError('measured fit rendered as unavailable')
        if result:
            with tempfile.TemporaryDirectory(prefix='ai6-requalify-') as temp:
                view=Path(temp)
                for role,prefix in (('baseline','A_'),('tuned','B_')):
                    destination=view/role/v/'web_audio';destination.mkdir(parents=True)
                    for scene in SCENES:
                        shutil.copy2(folder/'web_audio'/(prefix+scene+'.wav'),destination/(scene+'.wav'))
                policy=result['baseline_records'][SCENES[0]]['output_policy']
                fresh=build_qualification_receipt(
                    view,{'vehicles':{v:result},'output_policy':policy})['vehicles'][v]
            if fresh!=source_vehicle:
                raise ValueError('requalified B media differs from Task-1 receipt')
        if v=='rx7_fd' and result:
            provenance=contract.get('a_provenance') or {}
            if (provenance.get('boundary_policy')!='rx7_start_boundary_fade_v1'
                    or provenance.get('boundary_difference_frames')!=24
                    or provenance.get('byte_identity_to_pre_ai4b_a') is not False):
                raise ValueError('RX-7 A provenance is incomplete')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build')
    for arg in ('old-run','fourcar-run','two-run','out'):b.add_argument('--'+arg,type=Path,required=arg in ('old-run','out'))
    for arg in ('old-sha','fourcar-sha','two-sha'):b.add_argument('--'+arg,required=arg=='old-sha')
    s=sub.add_parser('serve');s.add_argument('--run',type=Path,required=True);s.add_argument('--sha',required=True)
    s.add_argument('--port',type=int,default=29580);s.add_argument('--preflight-only',action='store_true')
    args=p.parse_args()
    if args.command=='build':
        build(args.old_run,args.old_sha,args.out,fourcar_run=args.fourcar_run,fourcar_sha=args.fourcar_sha,
              two_run=args.two_run,two_sha=args.two_sha)
    else:
        if not 1024<=args.port<=65535:p.error('invalid port')
        verify(args.run,args.sha)
        if args.preflight_only:print('qualified ABC preflight PASS');return
        from ..stage_ag.serve_r1_review_strict import _make_server
        server=_make_server(args.run.resolve(),args.port)
        try:
            print(f'http://localhost:{args.port}/aventador_lp700/index.html')
            server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()


if __name__=='__main__':main()
