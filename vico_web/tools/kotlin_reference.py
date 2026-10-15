#!/usr/bin/env python3
"""Actual pinned Kotlin -> 48 constant-state references. Local/offline; never runs MATLAB.

Requires existing SHA-pinned JARs from vico_app/tools/jvm/dependencies.json.
The Android-only loader shell is replaced by an exact extracted bank DTO; actual
renderer, seam, envelope, control types and FloatWavDecoder compile unchanged.
"""
from pathlib import Path
import argparse, hashlib, json, math, os, subprocess

SOURCE = '477913e7500bb3ff13c3b72cf5b1a3cac1b28145'
SOUND = 'vico_app/Project/android/app/src/main/java/com/vico/simulator/sound/'
ASSETS = 'vico_app/Project/android/app/src/main/assets/'
VEHICLES = ['c63_w204_v6','hellcat_v6','ferrari_458','lfa','gtr_r35','supra_jza80']
HIGH = [6231.675097345275,6066.437170616317,7551.387581961789,7787.616449526502,5451.186664080444,6175.052996363627]
FIELDS = ['idle_rpm','redline_rpm','gear_ratios','final_drive','wheel_radius_m','launch_rpm','shift_rpm','shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','shift_min_torque','shift_reengage_gain','minimum_shift_interval_s','downshift_ratio','speed_ceiling_kmh','afterfire_minimum_rpm']

def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--deps',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--java',default='java');p.add_argument('--seconds',type=int,default=12);p.add_argument('--mode',choices=['LEGACY_LOCKED','NORMAL_CANONICAL_SEAM_V1','NORMAL_SEAM_ENVELOPE_V1'],default='NORMAL_SEAM_ENVELOPE_V1');a=p.parse_args()
 if not 1 <= a.seconds <= 30: p.error('seconds must be 1..30')
 repo=a.repo.resolve();out=a.out.resolve()
 if out==repo or out.is_relative_to(repo/'vico_app') or out.is_relative_to(repo/'.git'): p.error('protected output path')
 if out.exists():p.error('output directory must not exist')
 def gitfile(name):return subprocess.run(['git','--no-replace-objects','-C',str(repo),'show',SOURCE+':'+name],capture_output=True,check=True).stdout
 deps=json.loads(gitfile('vico_app/tools/jvm/dependencies.json'));jars=[]
 for row in deps:
  file=a.deps.resolve()/row['file']
  if not file.is_file() or sha(file.read_bytes())!=row['sha256']:raise RuntimeError('NOT_RUN: missing/mismatched pinned dependency '+row['file'])
  jars.append(str(file))
 out.mkdir(parents=True);src=out/'source';src.mkdir();assets=out/'assets';assets.mkdir();identities={};sources=[]
 for name in ['SoundModel.kt','SoundProfile.kt','MatlabPowertrainController.kt','QualifiedAfterfirePolicy.kt','VirtualDriveDemand.kt','VirtualCruiseGear.kt','MatlabStatefulBankRenderer.kt','NormalLoopTraversal.kt','NormalEnvelopeDamper.kt','FloatWavDecoder.kt','S13ReviewContract.kt']:
  b=gitfile(SOUND+name);(src/name).write_bytes(b);identities[SOUND+name]=sha(b);sources.append(src/name)
 raw=gitfile(SOUND+'MatlabSoundBank.kt');text=raw.decode();dto='package com.vico.simulator.sound\n\n'+text[text.index('data class MatlabLoop'):text.index('object MatlabSoundBankLoader')];(src/'BankData.kt').write_text(dto,encoding='utf8');sources.append(src/'BankData.kt');identities[SOUND+'MatlabSoundBank.kt']=sha(raw)
 loaders=[];cases=[];bank_ids={}
 for vi,id in enumerate(VEHICLES):
  root=ASSETS+'s12_v10/'+id;mb=gitfile(root+'/manifest.json');m=json.loads(mb);target=assets/id;target.mkdir();override={};vh=None
  if id=='c63_w204_v6':
   vr=ASSETS+'live_loop_variants/c63_low_rpm_preroll_v1';pb=gitfile(vr+'/manifest.properties');props=dict(line.split('=',1) for line in pb.decode().splitlines() if line);vh=sha(pb)
   if props['baseline_manifest_sha256']!=sha(mb):raise ValueError('C63 manifest mismatch')
   for i in range(4):
    file=props[f'loop.{i}.file'];b=gitfile(vr+'/'+file)
    if sha(b)!=props[f'loop.{i}.candidate_wav_sha256'] or sha(gitfile(root+'/'+file))!=props[f'loop.{i}.baseline_wav_sha256']:raise ValueError('C63 asset mismatch')
    override[file]=b
  bank_ids[id]={'referenceManifestSha256':sha(mb),'variantManifestSha256':vh}
  for row in m['loops']+[m['afterfire']]+m['shift_events']:
   file=row['file']
   if Path(file).name!=file or '/' in file or '\\' in file:raise ValueError('asset path')
   b=override.get(file) or gitfile(root+'/'+file);(target/file).write_bytes(b);identities[root+'/'+file]=sha(b)
  values=['doubleArrayOf('+','.join(str(float(v)) for v in m[k])+')' if k=='gear_ratios' else str(float(m[k])) for k in FIELDS]
  loops=','.join('MatlabLoop('+str(float(r['rpm']))+','+str(float(r['load']))+',wav('+json.dumps(r['file'])+'))' for r in m['loops'])
  shifts=','.join('MatlabTransient('+json.dumps(r['file'])+',wav('+json.dumps(r['file'])+'))' for r in m['shift_events'])
  loaders.append('fun bank'+str(vi)+'(root:File):MatlabSoundBank { val folder=File(root,"'+id+'"); fun wav(n:String)=FloatWavDecoder.decode(File(folder,n).readBytes()).also{require(it.sampleRateHz=='+str(m['sample_rate_hz'])+')}.samples; return MatlabSoundBank("'+id+'",'+str(m['sample_rate_hz'])+',MatlabPowertrainSpec('+','.join(values)+'),listOf('+loops+'),wav('+json.dumps(m['afterfire']['file'])+'),listOf('+shifts+')) }')
  for ri,rpm in enumerate([910.0 if id=='c63_w204_v6' else m['idle_rpm']*1.3,1400.0,3000.0,HIGH[vi]]):
   for load in [.32,.92]:cases.append({'id':f'{id}-{ri}-{int(load*100)}','vehicle':id,'bankIndex':vi,'rpm':rpm,'load':load,'sampleRate':m['sample_rate_hz'],'seconds':a.seconds})
 code='package com.vico.simulator.sound\nimport java.io.File\nimport java.nio.ByteBuffer\nimport java.nio.ByteOrder\n'+ '\n'.join(loaders)+'\nfun main(args:Array<String>){ val root=File(args[0]); val out=File(args[1]); val banks=listOf('+','.join('bank'+str(i)+'(root)' for i in range(6))+');\n'
 for c in cases:
  code+='run { val b=banks['+str(c['bankIndex'])+']; val r=MatlabStatefulBankRenderer(b,LoopTraversalMode.'+a.mode+'); val state=SoundState(0.0,'+str(c['rpm'])+',1.0,1.0,1.0,floatArrayOf(),false,load='+str(c['load'])+',shiftGain=1.0); val frames=b.sampleRateHz*'+str(a.seconds)+';val bytes=ByteBuffer.allocate(frames*4).order(ByteOrder.LITTLE_ENDIAN); var first=0;while(first<frames){val n=minOf(960,frames-first);for(v in r.render(state,n))bytes.putFloat(v);first+=n};File(out,"'+c['id']+'.f32le").writeBytes(bytes.array());println("'+c['id']+'|"+r.mixStats()) };\n'
 code+='}\n';h=src/'WebReference.kt';h.write_text(code,encoding='utf8');sources.append(h);cp=os.pathsep.join(jars)
 commands=[[a.java,'-cp',cp,'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-jvm-target','17','-classpath',cp,'-d',str(out/'reference.jar'),*map(str,sources)],[a.java,'-cp',str(out/'reference.jar')+os.pathsep+cp,'com.vico.simulator.sound.WebReferenceKt',str(assets),str(out)]]
 for i,cmd in enumerate(commands):
  r=subprocess.run(cmd,capture_output=True,text=True);(out/f'command-{i}.log').write_text(r.stdout+r.stderr,encoding='utf8')
  if r.returncode:raise RuntimeError('Kotlin command failed; see log '+str(i))
 for c in cases:
  b=(out/(c['id']+'.f32le')).read_bytes()
  if len(b)!=c['sampleRate']*a.seconds*4:raise ValueError('Incomplete capture')
  c['sha256']=sha(b);c['file']=c['id']+'.f32le'
 receipt={'schema':'vico.web.kotlin-reference.v1','sourceCommit':SOURCE,'mode':a.mode,'scope':'actual Kotlin static bank renderer; no Android device or human evidence','banks':bank_ids,'source_sha256':identities,'compiler_inputs':{q.name:sha(q.read_bytes()) for q in sources},'cases':cases,'commands':commands};(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('Kotlin reference complete: 48 cases; web equivalence not yet evaluated')
if __name__=='__main__':main()
