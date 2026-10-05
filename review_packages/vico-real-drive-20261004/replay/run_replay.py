#!/usr/bin/env python3
"""Actual REAL controller/renderer replay. Same c778 normal bank in both branches.
Only the unchanged bank data classes are extracted to avoid Android AssetManager.
No synthetic renderer or private audio. Output is ~46 MiB per drive variant.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,os,math
BASE='c7789afe8dd287980e7a8fba052b133ca3cc35ac'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--deps',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--variant',choices=['baseline','candidate'],required=True);p.add_argument('--profile',default='c63_w204_v6');p.add_argument('--reported-uncertainty',default='0',help='m/s, or unknown; source fixture metadata, not added measurement noise');p.add_argument('--scene',choices=['drive','lifecycle'],default='drive');a=p.parse_args()
 repo=a.repo.resolve();out=a.output_dir.resolve();here=Path(__file__).resolve().parent
 uncertainty=None if a.reported_uncertainty=='unknown' else float(a.reported_uncertainty)
 if uncertainty is not None and (not math.isfinite(uncertainty) or uncertainty<0):raise ValueError('Invalid reported uncertainty')
 if out.exists():raise ValueError('Use a new output directory')
 if out.is_relative_to(repo/'vico_app/Project/android/app/src'):raise ValueError('Output cannot overwrite app sources/assets')
 out.mkdir(parents=True);src=out/'source';src.mkdir();assets=out/'assets';assets.mkdir()
 root='vico_app/Project/android/app/src/main/java/com/vico/simulator/sound/'
 baseline=json.load(open(here/'baseline-source-sha256.json'));names=list(baseline)
 if a.variant=='candidate':names+=['VirtualDriveDemand.kt','VirtualCruiseGear.kt','MatlabSoundStateMapping.kt']
 sources=[];identities={}
 for n in names:
  b=(repo/root/n).read_bytes()
  if a.variant=='baseline' and sha(b)!=baseline[n]:b=subprocess.run(['git','-C',str(repo),'show',BASE+':'+root+n],stdout=subprocess.PIPE,check=True).stdout
  if a.variant=='baseline' and sha(b)!=baseline[n]:raise ValueError('Baseline identity mismatch '+n)
  identities[root+n]=sha(b)
  if n=='MatlabSoundBank.kt':
   t=b.decode();b=('package com.vico.simulator.sound\n'+t[t.index('data class MatlabLoop'):t.index('object MatlabSoundBankLoader')]).encode();n='OriginalBankData.kt'
  f=src/n;f.write_bytes(b);sources.append(f)
 expected_manifests=json.load(open(here/'bank-manifest-sha256.json'))
 if a.profile not in expected_manifests:raise ValueError('Unknown profile')
 mpath=repo/'vico_app/Project/android/app/src/main/assets/s12_v10'/a.profile/'manifest.json';mb=mpath.read_bytes()
 if sha(mb)!=expected_manifests[a.profile]:raise ValueError('Original bank manifest changed')
 m=json.loads(mb);overlay=(repo/'vico_app/Project/android/app/src/main/assets/live_loop_variants/c63_low_rpm_preroll_v1') if a.profile=='c63_w204_v6' else mpath.parent
 expected=json.load(open(here/'all-normal-bank-sha256.json'))[a.profile]
 for row in m['loops']+[m['afterfire']]+m['shift_events']:
  n=row['file'];f=overlay/n
  if not f.exists():f=mpath.parent/n
  b=f.read_bytes()
  if sha(b)!=expected[n]:raise ValueError('Normal bank identity mismatch '+n)
  (assets/n).write_bytes(b)
 fields=['idle_rpm','redline_rpm','gear_ratios','final_drive','wheel_radius_m','launch_rpm','shift_rpm','shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','shift_min_torque','shift_reengage_gain','minimum_shift_interval_s','downshift_ratio','speed_ceiling_kmh','afterfire_minimum_rpm']
 vals=['doubleArrayOf('+','.join(map(str,m[f]))+')' if isinstance(m[f],list) else str(float(m[f])) for f in fields]
 loader='package com.vico.simulator.sound\nimport java.io.File\nfun loadProbeBank(root:File):MatlabSoundBank {fun wav(f:String)=FloatWavDecoder.decode(File(root,f).readBytes()).samples\nreturn MatlabSoundBank("'+a.profile+'",48000,MatlabPowertrainSpec('+','.join(vals)+'),listOf('+','.join('MatlabLoop('+str(float(l['rpm']))+','+str(l['load'])+',wav("'+l['file']+'"))' for l in m['loops'])+'),wav("'+m['afterfire']['file']+'"),listOf('+','.join('MatlabTransient("'+l['file']+'",wav("'+l['file']+'"))' for l in m['shift_events'])+'))}\nfun probeDemand(s:MatlabPowertrainState,t:Double)='+('t' if a.variant=='baseline' else '(s.virtualDemand ?: t)')+'\n'
 loader+='fun probeControl(c:DriveInputControl):DriveInputControl='+('c' if a.variant=='baseline' else 'c.copy(reportedSpeedUncertaintyMps='+('null' if uncertainty is None else str(uncertainty))+')')+'\n'
 loader+='fun probeHasRevision()='+('false' if a.variant=='baseline' else 'true')+'\n'
 loader+='fun probeRevision(c:DriveInputControl?)='+('0L' if a.variant=='baseline' else '(c?.modelContinuityRevision ?: 0L)')+'\n'
 loader+='fun probeMap(s:MatlabPowertrainState,p:DrivePoint,c:DriveInputControl):SoundState='+('SoundState(p.timeS,s.rpm,s.rpm/60*4,kotlin.math.max(.08,s.load),s.load,floatArrayOf(),p.speedKmh>=148,p.throttle,s.load,p.brake,s.gear,s.torqueGain,s.afterfireTrigger,s.shiftTrigger,c,s.afterfireCauseCode,s.afterfireSourceId,p.speedKmh,p.accelMps2)' if a.variant=='baseline' else 's.toMappedSoundState(p,c)')+'\n'
 f=src/'LoadBank.kt';f.write_text(loader);sources.append(f)
 harness='RenderDemand.kt' if a.scene=='drive' else 'LifecycleDemand.kt';f=src/harness;f.write_bytes((here/harness).read_bytes());sources.append(f)
 jars=[]
 for d in json.load(open(repo/'vico_app/tools/jvm/dependencies.json')):
  f=a.deps.resolve()/d['file']
  if not f.is_file() or sha(f.read_bytes())!=d['sha256']:raise ValueError('SHA-pinned dependency missing '+d['file'])
  jars.append(str(f))
 cp=os.pathsep.join(jars);jar=out/'replay.jar'
 subprocess.run(['java','-cp',cp,'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-jvm-target','1.8','-classpath',cp,'-d',str(jar),*map(str,sources)],check=True)
 receipt={'baseline':BASE,'variant':a.variant,'scene':a.scene,'profile':a.profile,'reported_speed_uncertainty_mps':uncertainty,'scope':'actual Kotlin core; exact bank DTO extraction; Android adapters/device/human NOT_RUN','source_sha256':identities,'compiled_sha256':{f.name:sha(f.read_bytes()) for f in sources},'bank_sha256':expected}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 subprocess.run(['java','-Xmx1g','-cp',str(jar)+os.pathsep+cp,'com.vico.simulator.sound.'+harness[:-3]+'Kt',str(assets),str(out/'output')],check=True)
if __name__=='__main__':main()
