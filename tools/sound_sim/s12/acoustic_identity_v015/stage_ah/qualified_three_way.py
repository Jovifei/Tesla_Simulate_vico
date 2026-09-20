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
import re
from pathlib import Path
import shutil
import tempfile

import numpy as np
from scipy.io import wavfile

from . import three_way_audition as ui
from .feedback_evidence import AUTO, SCENES, Journal, canonical, fit_eligibility, read_journal, sha_file, write_json
from .fourcar_reference_loop import verify_run as verify_fourcar
from . import reference_feedback_cli as feedback_cli
from .qualification import (
    QUALIFICATION_FILENAME,
    QUALIFICATION_SCHEMA,
    build_qualification_receipt,
)
from .continuous_drive import CONTINUOUS_SCENE_ID, CONTINUOUS_SCHEMA, write_continuous_pair
from .reconstruction_peak import reconstructed_peak_receipt
from .reference_feedback_cli import verify_run as verify_two, numeric_ok, _runtime_identity
from ..stage_af.package_integrity import seal_payload

VEHICLES = ('hellcat','ferrari_458','lfa','gtr_r35','c63_w204','supra_jza80','rx7_fd','aventador_lp700')
SCHEMA = 's12.stage_ai6.qualified_three_way.v1'
VEHICLE_QUALIFICATION_SCHEMA = 's12.stage_ai6.vehicle_qualification.v1'


def _sealed(path):
    return ui._sealed(path)


def _vehicle_name(row, key):
    return str(row.get('vehicle') or row.get('vehicle_name') or key)


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


def _canonical_sha(value) -> str:
    encoded=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),
                       allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _rx7_boundary_diff_receipt(old_path: Path, ai5_path: Path) -> dict:
    old_rate,old_pcm=wavfile.read(old_path);new_rate,new_pcm=wavfile.read(ai5_path)
    if (old_rate!=48_000 or new_rate!=48_000 or old_pcm.dtype!=np.int16
            or new_pcm.dtype!=np.int16 or old_pcm.ndim!=2 or old_pcm.shape[1]!=2
            or new_pcm.shape!=old_pcm.shape):
        raise ValueError('RX-7 old A and AI-5 baseline require equal-shape 48 kHz stereo int16 PCM')
    changed=np.flatnonzero(np.any(old_pcm!=new_pcm,axis=1))
    if not len(changed) or np.any(changed>=24):
        raise ValueError('RX-7 difference is not confined to the 24-frame repair window')
    old_post=np.ascontiguousarray(old_pcm[24:],dtype='<i2').tobytes()
    new_post=np.ascontiguousarray(new_pcm[24:],dtype='<i2').tobytes()
    if old_post!=new_post:
        raise ValueError('RX-7 PCM differs after the 24-frame repair window')
    return {
        'schema':'s12.stage_ai6.rx7_boundary_diff.v1',
        'repair_window_frames':24,
        'sample_rate_hz':48_000,
        'pcm_shape':[int(value) for value in old_pcm.shape],
        'changed_frame_count':int(len(changed)),
        'changed_frame_indices':[int(value) for value in changed],
        'first_changed_frame':int(changed[0]),
        'last_changed_frame':int(changed[-1]),
        'post_window_byte_identical':True,
        'post_window_pcm_sha256':hashlib.sha256(old_post).hexdigest(),
        'old_a':{'path':str(old_path.resolve()),'wav_sha256':sha_file(old_path),
                 'decoded_pcm_sha256':_decoded_pcm_sha(old_path)[1]},
        'ai5_baseline':{'path':str(ai5_path.resolve()),'wav_sha256':sha_file(ai5_path),
                        'decoded_pcm_sha256':_decoded_pcm_sha(ai5_path)[1]},
    }


def _unavailable_reason(vehicle: str) -> str:
    if vehicle=='c63_w204':return 'C63 本阶段没有独立合格的 sealed B 证据'
    if vehicle=='supra_jza80':return 'Supra 本阶段没有独立合格的 sealed B 证据'
    return '尚未完成独立自动闭环；固定recipe/overlay不算自动反馈'


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
        'fit_evidence':copy.deepcopy(fit_info or {}),
        'human_status': 'NOT_EVALUATED',
        'promotable': False,
    }
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
        visible=_fit_visible_payload(fit_result)
        visible_json=json.dumps(visible,ensure_ascii=False,indent=2,allow_nan=False)
        panel+='<details open><summary>完整参数、训练/验证损失与逐次试验</summary><pre id="ai6-fit-visible">'+html.escape(
            visible_json)+'</pre></details>'
        page=page.replace('NOT_MEASURED','MEASURED_FROM_SEALED_EVIDENCE')
        page=page.replace('0 parameters','MEASURED_PARAMETERS')
        payload=json.dumps(_fit_evidence_payload(fit_result),ensure_ascii=False,
                           sort_keys=True,separators=(',',':'))
        page=page.replace('</body>', '<script>const AI6_FIT_EVIDENCE = '+payload+';</script></body>', 1)
    panel+='<p>C 是保留的真车试听对照；训练与验证源、窗口见日志。误差不是机器相似度百分比。</p></section>'
    return page.replace('</header>','</header>'+panel,1)


def build(old_root: Path, old_sha: str, output: Path, *, fourcar_run: Path | None = None,
          fourcar_sha: str | None = None, two_run: Path | None = None, two_sha: str | None = None,
          continuous_pairs: Mapping[str, Mapping[str, Any]] | None = None):
    old_root=old_root.resolve()
    old=verify_legacy(old_root,old_sha)
    continuous_pairs=dict(continuous_pairs or {})
    if any(vehicle not in ('rx7_fd', 'aventador_lp700') for vehicle in continuous_pairs):
        raise ValueError('continuous drive is currently qualified only for RX-7 and Aventador')
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
            choices[v]=(None,None,None,None,None,_unavailable_reason(v))
        elif v=='supra_jza80':
            choices[v]=(None,None,None,None,None,_unavailable_reason(v))
        elif key not in inputs:
            choices[v]=(None,None,None,None,None,_unavailable_reason(v))
        else:
            root,summary,qualification,manifest_sha=inputs[key]
            result,reason=_qualified(root,summary,qualification,v,old_root,
                require_old_a=v not in ('rx7_fd','aventador_lp700'))
            if not result:reason=_unavailable_reason(v)
            choices[v]=(root,result,summary,qualification,manifest_sha,reason)
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
        nav=[{'key':v,'name':_vehicle_name(old['vehicles'][v],v),
              'status':'AUTO_B_READY' if choices[v][1] else 'B_UNAVAILABLE'} for v in VEHICLES]
        vehicles={}
        template=ui.TEMPLATE_PATH.read_text(encoding='utf-8')
        for v in VEHICLES:
            folder=staging/v; web=folder/'web_audio';web.mkdir(parents=True)
            scenes=ui._load_scenes(old_root/v/'index.html')
            base_scenes=copy.deepcopy(scenes)
            root,result,source_summary,source_qualification,source_manifest_sha,reason=choices[v]
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
            for s in base_scenes:
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
            continuous_pair=continuous_pairs.get(v)
            continuous_info={
                'schema': CONTINUOUS_SCHEMA,
                'available': bool(continuous_pair),
                'scene_id': CONTINUOUS_SCENE_ID,
                'role_availability': {
                    'original': {'available': bool(continuous_pair),
                                 'reason': '' if continuous_pair else '连续驾驶未完成：该车型尚无完整30秒受控渲染'},
                    'feedback': {'available': bool(continuous_pair),
                                 'reason': '' if continuous_pair else '连续驾驶未完成：该车型尚无合格 A/B 对照'},
                    'reference': {'available': False,
                                  'reason': '没有可绑定的整段真实录音，C 保持不可用'},
                },
            }
            continuous_scene={
                'id': CONTINUOUS_SCENE_ID, 'index': len(base_scenes) + 1,
                'category': 'dynamics', 'title': '连续驾驶（30秒）',
                'desc': '完整怠速→加速→换挡→巡航→收油→回落状态渲染，不拼接分段 WAV',
                'focus': '连续驾驶 A/B 对照', 'candidate_file': '',
                'feedback_file': '', 'reference_file': '', 'ref_file': '',
                'role_availability': copy.deepcopy(continuous_info['role_availability']),
            }
            if continuous_pair:
                if not result:
                    raise ValueError(f'continuous B requires accepted feedback result: {v}')
                packaged_pair=copy.deepcopy(continuous_pair)
                packaged_receipt=packaged_pair.get('receipt', {})
                selected_receipt=packaged_receipt.get('parameters',{}).get('selected',{})
                if (packaged_receipt.get('vehicle')!=v
                        or any(selected_receipt.get(name)!=value
                               for name,value in result.get('selected_parameters',{}).items())):
                    raise ValueError(f'continuous parameters are not the accepted AI-5 selection: {v}')
                packaged_receipt['source_manifest_sha256']=source_manifest_sha
                packaged_pair['receipt']=packaged_receipt
                receipt=write_continuous_pair(folder, packaged_pair)
                continuous_scene.update(candidate_file='A_continuous_drive.wav',
                                        feedback_file='B_continuous_drive.wav',
                                        ref_file='B_continuous_drive.wav')
                store[CONTINUOUS_SCENE_ID+'_original']='web_audio/A_continuous_drive.wav'
                store[CONTINUOUS_SCENE_ID+'_candidate']='web_audio/A_continuous_drive.wav'
                store[CONTINUOUS_SCENE_ID+'_feedback']='web_audio/B_continuous_drive.wav'
                store[CONTINUOUS_SCENE_ID+'_ref']='web_audio/B_continuous_drive.wav'
                continuous_info.update({
                    'receipt_sha256': sha_file(folder/'continuous_drive_receipt.json'),
                    'wav_sha256': receipt['wav'],
                    'shared': receipt.get('shared', {}),
                    'events': receipt.get('events', {}),
                    'boundary': receipt.get('boundary', {}),
                    'selected_parameters': receipt.get('parameters', {}).get('selected'),
                    'source_manifest_sha256': source_manifest_sha,
                })
            scenes=base_scenes+[continuous_scene]
            roles['reference']['available']=bool(hashes['reference'])
            info={'kind':AUTO if result else 'NO_QUALIFIED_AUTOMATIC_B','available':bool(result)}
            link=None
            if result:
                _validate_fit_evidence(result)
                log_path=evidence/(v+'-fit.json');write_json(log_path,result)
                task1_path=evidence/(v+'-task1-qualification.json')
                write_json(task1_path,source_qualification)
                source_summary_path=evidence/(v+'-source-summary.json')
                write_json(source_summary_path,source_summary)
                trials_path=evidence/(v+'-trials.jsonl')
                with Journal(trials_path) as journal:
                    for row in result['history']:journal.append('MEASURED_TRIAL',row)
                    journal.append('SELECTION',{'status':result['status'],'selected_parameters':result['selected_parameters']})
                info.update(fit_report='evidence/'+log_path.name,fit_report_sha256=sha_file(log_path),
                    trial_log='evidence/'+trials_path.name,trial_log_sha256=sha_file(trials_path),
                    task1_qualification_receipt='evidence/'+task1_path.name,
                    task1_qualification_receipt_sha256=sha_file(task1_path),
                    source_summary='evidence/'+source_summary_path.name,
                    source_summary_sha256=sha_file(source_summary_path),
                    source_run_path=str(root.resolve()),
                    source_manifest_sha256=source_manifest_sha,
                    trial_count=result['trial_count'],parameter_delta=result['parameter_delta'])
                log_html=evidence/(v+'-log.html')
                text='<html lang="zh-CN"><meta charset="utf-8"><title>负反馈试验日志</title><h1>'+v+'</h1>'
                log_visible=json.dumps(_fit_visible_payload(result),ensure_ascii=False,indent=2,allow_nan=False)
                text+='<p>训练误差不是相似度；验证源不用于搜参；没有Human PASS。</p><pre id="ai6-fit-visible">'+html.escape(log_visible)+'</pre></html>'
                log_payload=json.dumps(_fit_evidence_payload(result),ensure_ascii=False,
                                       sort_keys=True,separators=(',',':'))
                text=text.replace('</html>', '<script>const AI6_FIT_EVIDENCE = '+log_payload+';</script></html>', 1)
                log_html.write_text(text,encoding='utf-8');link='../evidence/'+log_html.name
                info['fit_log']='evidence/'+log_html.name
                info['fit_log_sha256']=sha_file(log_html)
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
                    'scene_differences':{
                        scene:_rx7_boundary_diff_receipt(
                            old_root/v/'web_audio'/('A_'+scene+'.wav'),
                            root/'baseline'/v/'web_audio'/(scene+'.wav'))
                        for scene in SCENES
                    },
                }
            fit_info=copy.deepcopy(info)
            role_receipt=copy.deepcopy(roles)
            qualification_receipt=_vehicle_receipt(
                v,role_receipt,scene_roles,
                outcome='B_READY' if result else 'B_UNAVAILABLE',fit_info=fit_info)
            receipt_path=evidence/(v+'-qualification.json');write_json(receipt_path,qualification_receipt)
            info['vehicle_qualification_receipt']='evidence/'+receipt_path.name
            info['vehicle_qualification_receipt_sha256']=sha_file(receipt_path)
            contract=seal_payload({'schema':SCHEMA,'package_id':output.name+'-'+v,'vehicle':v,
                'source_roles':roles,'source_sha256':hashes,'feedback_evidence':info,
                'continuous_drive':continuous_info,
                'references':{k:{'available':True,'sha256':h} for k,h in hashes['reference'].items()},
                'candidate_pcm_sha256':hashes['original'],'reference_sha256':hashes['reference'],
                'a_provenance':a_provenance,
                'fit_baseline_distance':result['baseline_train_loss'] if result else None,
                'fit_final_distance':result['selected_train_loss'] if result else None,
                'fit_evidence_payload':_fit_evidence_payload(result) if result else None,
                'fit_metric_status':'MEASURED_FROM_SEALED_EVIDENCE' if result else 'B_UNAVAILABLE',
                'fit_status':result['status'] if result else 'B_UNAVAILABLE',
                'human_status':'NOT_EVALUATED','promotable':False,'source_status':'SOURCE_CLEAN',
                'scene_count':10,'sample_rate_hz':48000,'comparison':'A_BASELINE_B_VALIDATED_AUTO_C_REAL'},SCHEMA)
            write_json(folder/'dashboard_contract.json',contract)
            page=rich_page(template,v,_vehicle_name(old['vehicles'][v],v),scenes,contract,store,nav,link,result)
            for name in ('index.html','index_standalone.html'):(folder/name).write_text(page,encoding='utf-8')
            vehicles[v]={'source_roles':roles,'source_sha256':hashes,'feedback_evidence':info,
                         'a_provenance':a_provenance,'scene_count':10,
                         'continuous_drive':continuous_info}
        ready_count=sum(row['source_roles']['feedback']['available'] for row in vehicles.values())
        summary=seal_payload({'schema':SCHEMA,'run_id':output.name,'runtime':runtime,'vehicles':vehicles,
            'old_threeway_source_path':str(old_root),'old_threeway_manifest_sha256':old_sha,
            'fourcar_manifest_sha256':fourcar_sha,'two_car_manifest_sha256':two_sha,
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


def _fit_binding(info: dict) -> dict:
    return {key:copy.deepcopy(value) for key,value in info.items()
            if key not in ('vehicle_qualification_receipt','vehicle_qualification_receipt_sha256')}


def _fit_evidence_payload(result: dict) -> dict:
    fields = (
        'status', 'baseline_parameters', 'selected_parameters', 'parameter_delta',
        'baseline_train_loss', 'selected_train_loss', 'validation_baseline',
        'validation_proposed', 'validation_used_for_search', 'trial_count',
        'history', 'reference_cases',
    )
    return {field: copy.deepcopy(result[field]) for field in fields}


def _fit_visible_payload(result: dict) -> dict:
    fields = (
        'baseline_parameters', 'selected_parameters', 'baseline_train_loss',
        'selected_train_loss', 'parameter_delta', 'validation_baseline',
        'validation_proposed', 'history',
    )
    return {field: copy.deepcopy(result[field]) for field in fields}


def _verify_trial_evidence(root: Path, info: dict, result: dict) -> None:
    journal_path = root / info.get('trial_log', '')
    if (not journal_path.is_file()
            or sha_file(journal_path) != info.get('trial_log_sha256')):
        raise ValueError('fit trial journal missing or changed')
    rows = read_journal(journal_path, expected_sha256=info['trial_log_sha256'])
    expected = result['history']
    if len(rows) != len(expected) + 1:
        raise ValueError('fit trial journal count mismatch')
    for index, trial in enumerate(expected):
        row = rows[index]
        if row.get('event') != 'MEASURED_TRIAL' or row.get('payload') != trial:
            raise ValueError('fit trial journal evidence mismatch')
    selection = rows[-1]
    if (selection.get('event') != 'SELECTION'
            or selection.get('payload') != {
                'status': result['status'],
                'selected_parameters': result['selected_parameters'],
            }):
        raise ValueError('fit selection journal evidence mismatch')


def _verify_fit_evidence_payload(page: str, contract: dict, result: dict) -> None:
    expected = _fit_evidence_payload(result)
    if contract.get('fit_evidence_payload') != expected:
        raise ValueError('fit contract evidence mismatch')
    try:
        embedded = ui._embedded(page, 'AI6_FIT_EVIDENCE')
    except ValueError as error:
        raise ValueError('fit UI evidence missing') from error
    if embedded != expected:
        raise ValueError('fit UI evidence mismatch')


def _verify_visible_fit_evidence(document: str, result: dict, label: str) -> None:
    match=re.search(r'<pre id="ai6-fit-visible">(.*?)</pre>', document, re.DOTALL)
    if not match:
        raise ValueError(label+' visible evidence missing')
    try:
        visible=json.loads(html.unescape(match.group(1)))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(label+' visible evidence malformed') from error
    if visible != _fit_visible_payload(result):
        raise ValueError(label+' visible evidence mismatch')


def _verify_source_identity(identity: dict, expected: Path, packaged: Path) -> None:
    expected=expected.resolve()
    if identity.get('source_path')!=str(expected):
        raise ValueError('role source path binding mismatch')
    if not expected.is_file() or sha_file(expected)!=identity.get('source_sha256'):
        raise ValueError('role source path/hash binding mismatch')
    rate,pcm_sha=_decoded_pcm_sha(packaged)
    if (sha_file(packaged)!=identity.get('wav_file_sha256')
            or pcm_sha!=identity.get('decoded_pcm_sha256')
            or rate!=identity.get('sample_rate_hz')
            or sha_file(expected)!=sha_file(packaged)):
        raise ValueError('role WAV/PCM/source identity mismatch')


def _verify_bound_source_run(source_run: Path, expected_manifest_sha: str,
                             source_summary: dict, task1: dict) -> None:
    manifest_path=source_run/'ARTIFACTS.json'
    if not manifest_path.is_file() or sha_file(manifest_path)!=expected_manifest_sha:
        raise ValueError('Task-1 immutable source manifest identity mismatch')
    manifest=_sealed(manifest_path);files=manifest.get('files')
    actual={path.relative_to(source_run).as_posix() for path in source_run.rglob('*')
            if path.is_file() and path!=manifest_path}
    if not isinstance(files,dict) or set(files)!=actual:
        raise ValueError('Task-1 immutable source manifest inventory mismatch')
    for relative,digest in files.items():
        path=source_run/relative
        if path.is_symlink() or not path.resolve().is_relative_to(source_run) or sha_file(path)!=digest:
            raise ValueError('Task-1 immutable source artifact drift')
    external_summary=json.loads((source_run/'summary.json').read_text(encoding='utf-8'))
    if external_summary!=source_summary:
        raise ValueError('Task-1 persisted source summary differs from immutable source manifest')
    if build_qualification_receipt(source_run,external_summary)!=task1:
        raise ValueError('Task-1 persisted qualification differs from immutable source evidence')


def _verify_continuous_scene(folder: Path, contract: dict, scene: dict, store: dict,
                             vehicle: str) -> None:
    info=contract.get('continuous_drive')
    if not isinstance(info, dict) or info.get('schema')!=CONTINUOUS_SCHEMA:
        raise ValueError('continuous drive contract missing')
    available=bool(info.get('available'))
    role_availability=scene.get('role_availability')
    if role_availability != info.get('role_availability'):
        raise ValueError('continuous role availability mismatch')
    if not available:
        if any(scene.get(field) or key in store for field,key in (
                ('candidate_file', CONTINUOUS_SCENE_ID+'_original'),
                ('feedback_file', CONTINUOUS_SCENE_ID+'_feedback'),
                ('reference_file', CONTINUOUS_SCENE_ID+'_reference'))):
            raise ValueError('unavailable continuous scene retains audio')
        return
    receipt_path=folder/'continuous_drive_receipt.json'
    if (not receipt_path.is_file()
            or sha_file(receipt_path)!=info.get('receipt_sha256')):
        raise ValueError('continuous receipt missing or changed')
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if (receipt.get('schema')!=CONTINUOUS_SCHEMA or receipt.get('vehicle')!=vehicle
            or receipt.get('scene_id')!=CONTINUOUS_SCENE_ID
            or receipt.get('duration_s')!=30.0
            or receipt.get('sample_rate_hz')!=48_000):
        raise ValueError('continuous receipt identity mismatch')
    if (receipt.get('events',{}).get('shift_count')!=3
            or int(receipt.get('events',{}).get('afterfire_event_count',0))<=0
            or len(receipt.get('events',{}).get('afterfire_events',()))!=1
            or float(receipt.get('events',{}).get('afterfire_stem_energy',0.0))<=0.0):
        raise ValueError('continuous event evidence incomplete')
    if receipt.get('source_manifest_sha256')!=info.get('source_manifest_sha256'):
        raise ValueError('continuous source manifest binding mismatch')
    reports=receipt.get('reports')
    if not isinstance(reports,dict) or not all(role in reports for role in ('A','B','off_switch')):
        raise ValueError('continuous renderer reports missing')
    pcm_by_role={}
    for role,filename,store_key in (
            ('A','A_continuous_drive.wav',CONTINUOUS_SCENE_ID+'_original'),
            ('B','B_continuous_drive.wav',CONTINUOUS_SCENE_ID+'_feedback')):
        path=folder/'web_audio'/filename
        if not path.is_file() or store.get(store_key)!='web_audio/'+filename:
            raise ValueError('continuous audio binding missing')
        if sha_file(path)!=receipt.get('wav',{}).get(role,{}).get('wav_file_sha256'):
            raise ValueError('continuous WAV identity mismatch')
        rate,pcm=wavfile.read(path)
        if int(rate)!=48_000 or pcm.dtype!=np.int16 or pcm.ndim!=2 or pcm.shape[1]!=2:
            raise ValueError('continuous WAV format mismatch')
        decoded=hashlib.sha256(np.ascontiguousarray(pcm,dtype='<i2').tobytes()).hexdigest()
        if decoded!=receipt['wav'][role].get('decoded_pcm_sha256'):
            raise ValueError('continuous PCM identity mismatch')
        report=reports[role]
        if (report.get('vehicle')!=vehicle or report.get('scene_id')!=CONTINUOUS_SCENE_ID
                or int(report.get('sample_count',-1))!=1_440_000
                or report.get('final_pcm_sha256')!=decoded
                or not numeric_ok(report)):
            raise ValueError('continuous report numeric identity mismatch')
        recomputed=reconstructed_peak_receipt(pcm.astype(np.float64)/32767.0,
                                              sample_rate=48_000)
        if canonical(recomputed)!=canonical(report.get('reconstruction_peak')):
            raise ValueError('continuous report reconstructed-peak mismatch')
        pcm_by_role[role]=pcm
    report_a,reports_b=reports['A'],reports['B']
    for field in ('trace_sha256','seed','flags','parent_peak_key','normalization_denominator','output_policy','sample_rate_hz'):
        if report_a.get(field)!=reports_b.get(field):
            raise ValueError('continuous report shared context mismatch')
    if report_a.get('candidate_source_diagnostics',{}).get('shift_event_count')!=3:
        raise ValueError('continuous renderer did not report three shifts')
    for report in (report_a,reports_b):
        diag=report.get('candidate_source_diagnostics',{})
        if int(diag.get('afterfire_event_count',0))<=0 or float(diag.get('afterfire_stem_energy',diag.get('afterfire_thermal_peak',0.0)))<=0.0:
            raise ValueError('continuous renderer afterfire evidence missing')
    if receipt.get('parameters',{}).get('selected')!=contract.get('continuous_drive',{}).get('selected_parameters'):
        raise ValueError('continuous accepted parameter binding mismatch')
    if scene.get('candidate_file')!='A_continuous_drive.wav' or scene.get('feedback_file')!='B_continuous_drive.wav':
        raise ValueError('continuous scene filename mismatch')
    if scene.get('reference_file') or scene.get('ref_file')!='B_continuous_drive.wav':
        raise ValueError('continuous reference role must remain unavailable')


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
    old_root=Path(summary.get('old_threeway_source_path','')).resolve()
    verify_legacy(old_root,summary.get('old_threeway_manifest_sha256',''))
    ready_count=sum(row['source_roles']['feedback']['available'] for row in summary['vehicles'].values())
    if summary.get('feedback_ready_vehicle_count')!=ready_count or ready_count==len(VEHICLES):
        raise ValueError('package-wide B availability is misleading')
    task1_verified=set()
    for v in VEHICLES:
        folder=root/v;contract=_sealed(folder/'dashboard_contract.json')
        stored=json.loads((folder/'dashboard_contract.json').read_text(encoding='utf-8'))
        row=summary['vehicles'][v]
        if (contract['source_roles']!=row['source_roles']
                or contract['source_sha256']!=row['source_sha256']
                or contract['feedback_evidence']!=row['feedback_evidence']
                or contract.get('continuous_drive')!=row.get('continuous_drive')):
            raise ValueError('ABC role identity mismatch')
        if contract.get('a_provenance')!=row.get('a_provenance'):
            raise ValueError('A provenance mismatch')
        info=contract['feedback_evidence'];feedback=contract['source_roles']['feedback']['available']
        receipt_path=root/info.get('vehicle_qualification_receipt','')
        if (not receipt_path.is_file()
                or sha_file(receipt_path)!=info.get('vehicle_qualification_receipt_sha256')):
            raise ValueError('vehicle qualification receipt missing or changed')
        receipt=_sealed(receipt_path)
        if receipt.get('schema')!=VEHICLE_QUALIFICATION_SCHEMA or receipt.get('vehicle')!=v:
            raise ValueError('vehicle qualification receipt mismatch')
        if receipt.get('outcome')!=('B_READY' if feedback else 'B_UNAVAILABLE'):
            raise ValueError('vehicle qualification outcome mismatch')
        if receipt.get('roles')!=contract['source_roles']:
            raise ValueError('vehicle qualification full role status/reason mismatch')
        if receipt.get('fit_evidence')!=_fit_binding(info):
            raise ValueError('vehicle qualification fit evidence mismatch')
        if not feedback and (info.get('kind')!='NO_QUALIFIED_AUTOMATIC_B'
                             or info.get('available') is not False
                             or contract['source_roles']['feedback'].get('reason')!=_unavailable_reason(v)):
            raise ValueError('unavailable B reason/status mismatch')
        if feedback:
            if info.get('kind')!=AUTO or info.get('available') is not True:
                raise ValueError('enabled B fit status mismatch')
            fit=root/info['fit_report']
            if sha_file(fit)!=info['fit_report_sha256']:raise ValueError('B fit evidence hash mismatch')
            result=json.loads(fit.read_text(encoding='utf-8'));_validate_fit_evidence(result)
            if (contract.get('fit_baseline_distance') != result['baseline_train_loss']
                    or contract.get('fit_final_distance') != result['selected_train_loss']
                    or contract.get('fit_status') != result['status']
                    or contract.get('fit_evidence_payload') != _fit_evidence_payload(result)):
                raise ValueError('fit contract evidence mismatch')
            _verify_trial_evidence(root, info, result)
            fit_log=root/info.get('fit_log','')
            if (not fit_log.is_file() or sha_file(fit_log)!=info.get('fit_log_sha256')):
                raise ValueError('fit log missing or changed')
            try:
                fit_log_text=fit_log.read_text(encoding='utf-8')
                if ui._embedded(fit_log_text, 'AI6_FIT_EVIDENCE') != _fit_evidence_payload(result):
                    raise ValueError('fit log evidence mismatch')
                _verify_visible_fit_evidence(fit_log_text, result, 'fit log')
            except ValueError as error:
                if 'fit log evidence mismatch' in str(error) or 'fit log visible evidence' in str(error):
                    raise
                raise ValueError('fit log evidence missing') from error
            source_summary_path=root/info.get('source_summary','')
            task1_path=root/info.get('task1_qualification_receipt','')
            if (not source_summary_path.is_file() or sha_file(source_summary_path)!=info.get('source_summary_sha256')
                    or not task1_path.is_file() or sha_file(task1_path)!=info.get('task1_qualification_receipt_sha256')):
                raise ValueError('Task-1 source summary/qualification receipt missing or changed')
            source_summary=json.loads(source_summary_path.read_text(encoding='utf-8'))
            task1=json.loads(task1_path.read_text(encoding='utf-8'))
            if (task1.get('schema')!=QUALIFICATION_SCHEMA or task1.get('status')!='PASS'
                    or task1.get('summary_sha256')!=_canonical_sha(source_summary)
                    or source_summary.get('vehicles',{}).get(v)!=result):
                raise ValueError('Task-1 schema/status/summary binding mismatch')
            if info.get('source_manifest_sha256') not in (
                    summary.get('fourcar_manifest_sha256'),summary.get('two_car_manifest_sha256')):
                raise ValueError('vehicle qualification fit evidence source manifest mismatch')
            source_run=Path(info.get('source_run_path','')).resolve()
            _verify_bound_source_run(source_run,info['source_manifest_sha256'],source_summary,task1)
            task1_key=(info['task1_qualification_receipt_sha256'],info['source_summary_sha256'])
            if task1_key not in task1_verified:
                with tempfile.TemporaryDirectory(prefix='ai6-requalify-') as temp:
                    view=Path(temp)
                    for source_vehicle,source_result in source_summary.get('vehicles',{}).items():
                        if source_result.get('status')=='ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK':continue
                        if source_vehicle not in VEHICLES:raise ValueError('Task-1 source vehicle not in AI-6')
                        source_contract=_sealed(root/source_vehicle/'dashboard_contract.json')
                        source_enabled=source_contract['source_roles']['feedback']['available']
                        if source_enabled:
                            source_info=source_contract['feedback_evidence']
                            source_fit=json.loads((root/source_info['fit_report']).read_text(encoding='utf-8'))
                            if source_fit!=source_result:raise ValueError('Task-1 complete source summary fit mismatch')
                        for role,prefix in (('baseline','A_'),('tuned','B_')):
                            destination=view/role/source_vehicle/'web_audio';destination.mkdir(parents=True)
                            for scene in SCENES:
                                source_audio=(root/source_vehicle/'web_audio'/(prefix+scene+'.wav')
                                              if source_enabled else source_run/role/source_vehicle/'web_audio'/(scene+'.wav'))
                                shutil.copy2(source_audio,
                                             destination/(scene+'.wav'))
                    fresh=build_qualification_receipt(view,source_summary)
                if fresh!=task1:raise ValueError('Task-1 complete receipt recomputation mismatch')
                task1_verified.add(task1_key)
        else:
            result=None;source_run=None
        expected_hashes={role:{} for role in ('original','feedback','reference')}
        for page in ('index.html','index_standalone.html'):
            text=(folder/page).read_text(encoding='utf-8')
            if ui._embedded(text,'DASHBOARD_CONTRACT')!=stored:raise ValueError('embedded contract differs')
            if feedback:
                _verify_fit_evidence_payload(text, contract, result)
                _verify_visible_fit_evidence(text, result, 'fit UI')
            scenes=ui._embedded(text,'SCENES');store=ui._embedded(text,'AUDIO_STORE')
            scene_ids=[scene['id'] for scene in scenes]
            if scene_ids not in (list(SCENES), list(SCENES)+[CONTINUOUS_SCENE_ID]):
                raise ValueError('ten scenes plus optional continuous scene required')
            if set(receipt.get('scenes',{}))!=set(SCENES):raise ValueError('vehicle receipt scene coverage mismatch')
            base_scene_rows=[scene for scene in scenes if scene['id'] in SCENES]
            for scene_row in base_scene_rows:
                scene=scene_row['id'];a='A_'+scene+'.wav';b='B_'+scene+'.wav';c='C_'+scene+'.wav'
                c_available=(old_root/v/'web_audio'/c).is_file()
                expected_names={'original':a,'feedback':b if feedback else '',
                                'reference':c if c_available else ''}
                if (scene_row.get('candidate_file')!=a
                        or scene_row.get('feedback_file','')!=expected_names['feedback']
                        or scene_row.get('ref_file','')!=expected_names['feedback']
                        or scene_row.get('reference_file','')!=expected_names['reference']):
                    raise ValueError('source role coverage filename mismatch')
                expected_store={scene+'_original':'web_audio/'+a,scene+'_candidate':'web_audio/'+a}
                if feedback:expected_store.update({scene+'_feedback':'web_audio/'+b,scene+'_ref':'web_audio/'+b})
                if c_available:expected_store[scene+'_reference']='web_audio/'+c
                actual_store={key:value for key,value in store.items() if key.startswith(scene+'_')}
                if actual_store!=expected_store:raise ValueError('source role coverage store alias mismatch')
                expected_receipt_roles={'original'}|({'feedback'} if feedback else set())|({'reference'} if c_available else set())
                if set(receipt['scenes'][scene])!=expected_receipt_roles:
                    raise ValueError('source role coverage receipt mismatch')
                for role,name in expected_names.items():
                    if not name:continue
                    packaged=folder/'web_audio'/name;expected_hashes[role][name]=sha_file(packaged)
                    if role=='original':
                        source=(source_run/'baseline'/v/'web_audio'/(scene+'.wav')
                                if feedback and v in ('rx7_fd','aventador_lp700') else old_root/v/'web_audio'/a)
                    elif role=='feedback':source=source_run/'tuned'/v/'web_audio'/(scene+'.wav')
                    else:source=old_root/v/'web_audio'/c
                    _verify_source_identity(receipt['scenes'][scene][role],source,packaged)
                if feedback:
                    identical=sha_file(folder/'web_audio'/a)==sha_file(folder/'web_audio'/b)
                    if scene_row.get('ab_pcm_identical') is not identical:
                        raise ValueError('A/B identical-scene label mismatch')
            continuous_rows=[scene for scene in scenes if scene['id']==CONTINUOUS_SCENE_ID]
            if len(continuous_rows)>1:
                raise ValueError('duplicate continuous scene')
            if continuous_rows:
                _verify_continuous_scene(folder,contract,continuous_rows[0],store,v)
            elif contract.get('continuous_drive',{}).get('available'):
                raise ValueError('continuous contract has no scene')
            if result:
                for marker in ('baseline_parameters','selected_parameters','baseline_train_loss',
                               'selected_train_loss','validation_baseline','validation_proposed','history'):
                    if marker not in text:raise ValueError('fit/trial evidence missing from UI')
                if '0 parameters' in text or 'NOT_MEASURED' in text:raise ValueError('measured fit rendered as unavailable')
        if contract['source_sha256']!=expected_hashes:
            raise ValueError('source role coverage contract hashes mismatch')
        if (contract['source_roles']['original']['available'] is not True
                or contract['source_roles']['feedback']['available'] is not feedback
                or contract['source_roles']['reference']['available'] is not bool(expected_hashes['reference'])):
            raise ValueError('source role coverage availability mismatch')
        if v=='rx7_fd' and result:
            provenance=contract.get('a_provenance') or {}
            expected_differences={scene:_rx7_boundary_diff_receipt(
                old_root/v/'web_audio'/('A_'+scene+'.wav'),
                source_run/'baseline'/v/'web_audio'/(scene+'.wav')) for scene in SCENES}
            if (provenance.get('boundary_policy')!='rx7_start_boundary_fade_v1'
                    or provenance.get('boundary_difference_frames')!=24
                    or provenance.get('byte_identity_to_pre_ai4b_a') is not False
                    or provenance.get('scene_differences')!=expected_differences):
                raise ValueError('RX-7 A 24-frame provenance is incomplete')
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
