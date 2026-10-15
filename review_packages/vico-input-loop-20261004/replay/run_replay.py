#!/usr/bin/env python3
"""Replay 55 synthetic C63 cases through pinned actual Kotlin core and original bank.

Output is ~230 MiB. No Android adapters/device/GPS or private recordings are used.
Current files must match pinned 7bf34080 core, or Git must provide that exact source.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,shutil,csv
HEAD='7bf34080c358cc8b2eb4407266f008773c3efb6a'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--repo',type=Path,required=True);a.add_argument('--deps',type=Path,required=True);a.add_argument('--output-dir',type=Path,required=True);a.add_argument('--variant',choices=['reference','c63_low_rpm_preroll_v1'],default='reference');v=a.parse_args();repo=v.repo.resolve();out=v.output_dir.resolve();here=Path(__file__).resolve().parent
 if out.exists():raise SystemExit('Output must be a new directory')
 if out.is_relative_to(repo/'vico_app/Project/android/app/src'):raise SystemExit('Never write replay into production sources/assets')
 out.mkdir(parents=True);src=out/'source';src.mkdir();assets=out/'assets';assets.mkdir();rendered=out/'rendered'
 pinned=json.load(open(here/'core-source-sha256.json'));sources=[]
 for relative,digest in pinned.items():
  local=repo/relative;b=local.read_bytes() if local.exists() else b''
  if sha(b)!=digest:b=subprocess.run(['git','-C',str(repo),'show',HEAD+':'+relative],stdout=subprocess.PIPE,check=True).stdout
  if sha(b)!=digest:raise ValueError('Pinned source identity unavailable: '+relative)
  p=src/Path(relative).name;p.write_bytes(b)
  if p.name=='MatlabSoundBank.kt':
   text=b.decode();dto='package com.vico.simulator.sound\n\n'+text[text.index('data class MatlabLoop'):text.index('object MatlabSoundBankLoader')];p=src/'OriginalBankData.kt';p.write_text(dto)
  sources.append(p)
 reference=repo/'vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6';manifest_bytes=(reference/'manifest.json').read_bytes()
 if sha(manifest_bytes)!='7a03686ce671562fabd6f5160ce6fe6d2e04887e84d89a0ae4f3594bfb7d8869':raise ValueError('Original bank manifest changed')
 bank=json.loads(manifest_bytes);files=bank['loops']+[bank['afterfire']]+bank['shift_events']
 reference_hashes=json.load(open(here/'reference-bank-sha256.json'))
 for row in files:
  data=(reference/row['file']).read_bytes()
  if sha(data)!=reference_hashes[row['file']]:raise ValueError('Original bank WAV changed: '+row['file'])
  (assets/row['file']).write_bytes(data)
 if v.variant!='reference':
  new=repo/'vico_app/Project/android/app/src/main/assets/live_loop_variants'/v.variant;props=(new/'manifest.properties').read_bytes()
  if sha(props)!='f26d7ae6736af106e6cbb38c2ce6fdb097ae86d39f23c3f5f70a46af6a72de91':raise ValueError('Variant manifest changed')
  entries=dict(line.split('=',1) for line in props.decode('ascii').splitlines() if line)
  for i in range(4):
   f=entries[f'loop.{i}.file'];b=(new/f).read_bytes()
   if sha((reference/f).read_bytes())!=entries[f'loop.{i}.baseline_wav_sha256'] or sha(b)!=entries[f'loop.{i}.candidate_wav_sha256']:raise ValueError('Bank asset identity mismatch')
   (assets/f).write_bytes(b)
 fields=['idle_rpm','redline_rpm','gear_ratios','final_drive','wheel_radius_m','launch_rpm','shift_rpm','shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','shift_min_torque','shift_reengage_gain','minimum_shift_interval_s','downshift_ratio','speed_ceiling_kmh','afterfire_minimum_rpm']
 values=['doubleArrayOf('+','.join(str(float(x)) for x in bank[f])+')' if isinstance(bank[f],list) else str(float(bank[f])) for f in fields]
 loader='package com.vico.simulator.sound\nimport java.io.File\nfun readBank(root:File):MatlabSoundBank {\n fun wav(n:String)=FloatWavDecoder.decode(File(root,n).readBytes()).also{require(it.sampleRateHz==48000)}.samples\n val spec=MatlabPowertrainSpec('+','.join(values)+')\n return MatlabSoundBank("c63_w204_v6",48000,spec,listOf('+','.join(f'MatlabLoop({float(e["rpm"])},{e["load"]},wav("{e["file"]}"))' for e in bank['loops'])+'),wav("'+bank['afterfire']['file']+'"),listOf('+','.join('MatlabTransient("'+e['file']+'",wav("'+e['file']+'"))' for e in bank['shift_events'])+'))\n}\n';p=src/'LoadPinnedBank.kt';p.write_text(loader);sources.append(p);sources.append(here/'OfflineAudit.kt')
 jars=[]
 for entry in json.load(open(repo/'vico_app/tools/jvm/dependencies.json')):
  p=v.deps.resolve()/entry['file']
  if not p.is_file() or sha(p.read_bytes())!=entry['sha256']:raise ValueError('Missing SHA-pinned JVM dependency '+str(p))
  jars.append(str(p))
 cp=os.pathsep.join(jars);jar=out/'harness.jar';subprocess.run(['java','-cp',cp,'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-jvm-target','1.8','-classpath',cp,'-d',str(jar),*map(str,sources)],check=True)
 subprocess.run(['java','-Xmx2g','-cp',str(jar)+os.pathsep+cp,'com.vico.simulator.sound.OfflineAuditKt',str(assets),str(rendered)],check=True)
 stats=[]
 for d in sorted(rendered.iterdir()):
  row=next(csv.DictReader(open(d/'stats.tsv'),delimiter='\t'));row={'case':d.name,**row};stats.append(row)
  if any(int(row[k]) for k in ['hardClipFrames','nonFiniteFrames','aboveContractFrames']):raise ValueError('Raw renderer guard failed '+d.name)
 receipt={'baseline_head':HEAD,'variant':v.variant,'scope':'synthetic trace; actual pinned core with exact bank DTO extraction; Android not run','cases':len(stats),'core_source_sha256':pinned,'asset_sha256':{p.name:sha(p.read_bytes()) for p in sorted(assets.glob('*.wav'))},'stats':stats}
 if len(stats)!=55:raise ValueError('Incomplete replay')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
