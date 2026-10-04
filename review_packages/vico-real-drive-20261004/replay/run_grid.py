#!/usr/bin/env python3
"""Demand/ratio sensitivity only: exact GPS samples, acceleration noise, six frozen bank specs.
This is NOT evidence about arbitrary GPS errors; separate reported-u regressions are required.
"""
from pathlib import Path
import argparse,json,hashlib,os,subprocess

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--deps',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();repo=a.repo.resolve();out=a.output_dir.resolve();here=Path(__file__).resolve().parent
 if out.exists():raise ValueError('New output directory required')
 out.mkdir(parents=True);src=out/'source';src.mkdir();sources=[]
 root=repo/'vico_app/Project/android/app/src/main/java/com/vico/simulator/sound'
 for n in ['SoundModel.kt','SoundProfile.kt','MatlabPowertrainController.kt','QualifiedAfterfirePolicy.kt','VirtualDriveDemand.kt','VirtualCruiseGear.kt']:
  f=src/n;f.write_bytes((root/n).read_bytes());sources.append(f)
 fixtures=[]
 fields=['idle_rpm','redline_rpm','gear_ratios','final_drive','wheel_radius_m','launch_rpm','shift_rpm','shift_attack_s','shift_hold_s','shift_recovery_s','shift_settle_s','shift_min_torque','shift_reengage_gain','minimum_shift_interval_s','downshift_ratio','speed_ceiling_kmh','afterfire_minimum_rpm']
 for profile,h in sorted(json.load(open(here/'bank-manifest-sha256.json')).items()):
  b=(repo/'vico_app/Project/android/app/src/main/assets/s12_v10'/profile/'manifest.json').read_bytes()
  if hashlib.sha256(b).hexdigest()!=h:raise ValueError('Bank spec identity changed')
  m=json.loads(b);vals=['doubleArrayOf('+','.join(map(str,m[f]))+')' if isinstance(m[f],list) else str(float(m[f])) for f in fields]
  fixtures.append('"'+profile+'" to MatlabPowertrainSpec('+','.join(vals)+')')
 f=src/'BankSpecs.kt';f.write_text('package com.vico.simulator.sound\nfun bankSpecs()=listOf('+','.join(fixtures)+')\n');sources.append(f)
 f=src/'GridMain.kt';f.write_bytes((here/f.name).read_bytes());sources.append(f)
 jars=[]
 for x in json.load(open(repo/'vico_app/tools/jvm/dependencies.json')):
  f=a.deps.resolve()/x['file']
  if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=x['sha256']:raise ValueError('Pinned dependency missing')
  jars.append(str(f))
 cp=os.pathsep.join(jars);jar=out/'grid.jar';subprocess.run(['java','-cp',cp,'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-jvm-target','1.8','-classpath',cp,'-d',str(jar),*map(str,sources)],check=True)
 (out/'source-sha256.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},indent=2)+'\n')
 with (out/'grid.csv').open('w') as stdout,(out/'result.log').open('w') as stderr:
  subprocess.run(['java','-Xmx1g','-cp',str(jar)+os.pathsep+cp,'com.vico.simulator.sound.GridMainKt'],stdout=stdout,stderr=stderr,check=True)
 print((out/'result.log').read_text())
if __name__=='__main__':main()
