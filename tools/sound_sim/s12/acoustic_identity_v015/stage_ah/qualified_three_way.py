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
from .reference_feedback_cli import verify_run as verify_two, numeric_ok, _runtime_identity
from ..stage_af.package_integrity import seal_payload

VEHICLES = ('hellcat','ferrari_458','lfa','gtr_r35','c63_w204','supra_jza80','rx7_fd','aventador_lp700')
SCHEMA = 's12.stage_ai.qualified_three_way.v1'


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


def _qualified(run: Path, summary, vehicle: str, old_root: Path):
    result=summary.get('vehicles',{}).get(vehicle)
    if not result:
        return None, '无已验证的自动反馈结果'
    eligibility=fit_eligibility(result)
    if not eligibility['available']:
        return None, ' / '.join(eligibility['reasons'])
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
        if sha_file(original)!=sha_file(base):
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


def rich_page(template, vehicle, title, scenes, contract, store, nav, report_link):
    page=ui.build_page_html(template,vehicle,title,
        'A 原算法基线 / B 自动负反馈算法 / C 真车原声 · 有测量和验证才启用B',
        scenes,contract,store,nav)
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
        inputs['fourcar']=(fourcar_run.resolve(),verify_fourcar(fourcar_run,fourcar_sha))
    if two_run:
        if not two_sha: raise ValueError('two-car manifest SHA required')
        inputs['two']=(two_run.resolve(),verify_two(two_run,two_sha))
    choices={}
    for v in VEHICLES:
        key='fourcar' if v in VEHICLES[:4] else 'two'
        if v in ('c63_w204','supra_jza80') or key not in inputs:
            choices[v]=(None,None,'尚未完成独立自动闭环；固定recipe/overlay不算自动反馈')
        else:
            root,summary=inputs[key]
            result,reason=_qualified(root,summary,v,old_root)
            choices[v]=(root,result,reason)
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
            root,result,reason=choices[v]
            roles={
                'original':{'label':'A: 原算法（本轮基线）','available':True,'status':'BASELINE'},
                'feedback':{'label':'B: 自动负反馈算法','available':bool(result),
                    'status':AUTO if result else 'NO_QUALIFIED_AUTOMATIC_B','reason':reason},
                'reference':{'label':'C: 真车原声','available':False,'status':'R3/R2_UNSYNCHRONIZED'}}
            hashes={k:{} for k in roles};store={}
            for s in scenes:
                scene=s['id']
                a='A_'+scene+'.wav';shutil.copy2(old_root/v/'web_audio'/a,web/a)
                s['candidate_file']=a;hashes['original'][a]=sha_file(web/a)
                store[scene+'_original']=store[scene+'_candidate']='web_audio/'+a
                s['feedback_file']=s['ref_file']=''
                s['ab_pcm_identical']=False
                if result:
                    b='B_'+scene+'.wav';shutil.copy2(root/'tuned'/v/'web_audio'/(scene+'.wav'),web/b)
                    s['feedback_file']=s['ref_file']=b;hashes['feedback'][b]=sha_file(web/b)
                    store[scene+'_feedback']=store[scene+'_ref']='web_audio/'+b
                    s['ab_pcm_identical']=hashes['original'][a]==hashes['feedback'][b]
                c=s.get('reference_file','')
                if c:
                    shutil.copy2(old_root/v/'web_audio'/c,web/c)
                    hashes['reference'][c]=sha_file(web/c);store[scene+'_reference']='web_audio/'+c
            roles['reference']['available']=bool(hashes['reference'])
            info={'kind':AUTO if result else 'NO_QUALIFIED_AUTOMATIC_B','available':bool(result)}
            link=None
            if result:
                log_path=evidence/(v+'-fit.json');write_json(log_path,result)
                trials_path=evidence/(v+'-trials.jsonl')
                with Journal(trials_path) as journal:
                    for row in result['history']:journal.append('MEASURED_TRIAL',row)
                    journal.append('SELECTION',{'status':result['status'],'selected_parameters':result['selected_parameters']})
                info.update(fit_report='evidence/'+log_path.name,fit_report_sha256=sha_file(log_path),
                    trial_log='evidence/'+trials_path.name,trial_log_sha256=sha_file(trials_path),
                    trial_count=result['trial_count'],parameter_delta=result['parameter_delta'])
                log_html=evidence/(v+'-log.html')
                text='<html lang="zh-CN"><meta charset="utf-8"><title>负反馈试验日志</title><h1>'+v+'</h1>'
                text+='<p>训练误差不是相似度；验证源不用于搜参；没有Human PASS。</p><pre>'+html.escape(json.dumps(
                    {k:result[k] for k in ('status','baseline_train_loss','selected_train_loss','parameter_delta',
                        'validation_baseline','validation_proposed','history','reference_cases')},ensure_ascii=False,indent=2))+'</pre></html>'
                log_html.write_text(text,encoding='utf-8');link='../evidence/'+log_html.name
            contract=seal_payload({'schema':SCHEMA,'package_id':output.name+'-'+v,'vehicle':v,
                'source_roles':roles,'source_sha256':hashes,'feedback_evidence':info,
                'references':{k:{'available':True,'sha256':h} for k,h in hashes['reference'].items()},
                'candidate_pcm_sha256':hashes['original'],'reference_sha256':hashes['reference'],
                'human_status':'NOT_EVALUATED','promotable':False,'source_status':'SOURCE_CLEAN',
                'scene_count':10,'sample_rate_hz':48000,'comparison':'A_BASELINE_B_VALIDATED_AUTO_C_REAL'},SCHEMA)
            write_json(folder/'dashboard_contract.json',contract)
            page=rich_page(template,v,old['vehicles'][v]['vehicle'],scenes,contract,store,nav,link)
            for name in ('index.html','index_standalone.html'):(folder/name).write_text(page,encoding='utf-8')
            vehicles[v]={'source_roles':roles,'source_sha256':hashes,'feedback_evidence':info,'scene_count':10}
        summary=seal_payload({'schema':SCHEMA,'run_id':output.name,'runtime':runtime,'vehicles':vehicles,
            'old_threeway_manifest_sha256':old_sha,'fourcar_manifest_sha256':fourcar_sha,'two_car_manifest_sha256':two_sha,
            'promotable':False,'human_status':'NOT_EVALUATED'},SCHEMA)
        write_json(staging/'summary.json',summary)
        (staging/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>三路声浪对照</h1>'+
            ''.join('<p><a href="'+v+'/index.html">'+v+'</a></p>' for v in VEHICLES),encoding='utf-8')
        verify_legacy(old_root,old_sha)
        if fourcar_run:verify_fourcar(fourcar_run,fourcar_sha)
        if two_run:verify_two(two_run,two_sha)
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
    if set(summary['vehicles'])!=set(VEHICLES):raise ValueError('eight vehicles required')
    for v in VEHICLES:
        folder=root/v;contract=_sealed(folder/'dashboard_contract.json')
        stored=json.loads((folder/'dashboard_contract.json').read_text(encoding='utf-8'))
        if contract['source_roles']!=summary['vehicles'][v]['source_roles']:raise ValueError('ABC role identity mismatch')
        if contract['source_roles']['feedback']['available']:
            info=contract['feedback_evidence'];fit=root/info['fit_report']
            if sha_file(fit)!=info['fit_report_sha256'] or not fit_eligibility(json.loads(fit.read_text(encoding='utf-8')))['available']:
                raise ValueError('B lacks measured/validated fit')
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
                    if store[key]!='web_audio/'+name or sha_file(folder/'web_audio'/name)!=contract['source_sha256'][role].get(name):
                        raise ValueError('A/B/C source mapping mismatch')
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
