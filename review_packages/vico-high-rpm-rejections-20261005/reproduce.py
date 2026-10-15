#!/usr/bin/env python3
"""Reproduce rejected offline bank experiments in a NEW isolated directory. No app changes."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--deps',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--stage',choices=['phase','guards','all'],default='all');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
 repo=a.repo.resolve();out=a.output_dir.resolve()
 if out.exists() or out.is_relative_to(repo):raise ValueError('Use a NEW output directory outside source checkout')
 pins=json.loads((HERE/'input-pins.json').read_text())
 for rel,digest in pins['all_required'].items():
  if hashlib.sha256((repo/rel).read_bytes()).hexdigest()!=digest:raise ValueError('Input identity differs: '+rel)
 out.mkdir(parents=True);lab=out/'vico-bank-refinement';lab.mkdir();(lab/'evidence').mkdir();mirror=out/'vico-drive-demand/work'
 for rel in pins['python_recipe']:
  dst=lab/'source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/rel,dst)
 for rel in pins['kotlin_and_bank']:
  dst=mirror/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/rel,dst)
 for n in ['probe_recipe.py','generate_high_phase.py','probe_holdout_source.py','probe_anchor_coverage.py','probe_guard_source.py','analyze_holdouts.py','analyze_guards.py']:shutil.copy2(HERE/n,lab/n)
 for n in ['phase-replay-frozen','guards-replay-frozen']:shutil.copytree(HERE/n,lab/n,ignore=shutil.ignore_patterns('__pycache__'))
 (out/'input-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
 if a.prepare_only:print('PREPARED_EXACT_INPUTS; no DSP replay executed');return
 env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
 def run(script,*args):subprocess.run([sys.executable,str(lab/script),*map(str,args)],check=True,env=env)
 run('probe_recipe.py')
 results={}
 if a.stage in ('phase','all'):
  run('generate_high_phase.py');run('probe_holdout_source.py')
  render=out/'phase-render';run('phase-replay-frozen/run_replay.py','--repo',mirror,'--deps',a.deps.resolve(),'--output-dir',render,'--variant','candidate','--candidate-bank',lab/'candidate-high-phase')
  run('analyze_holdouts.py','--render-output',render/'output');results['phase']=json.loads((lab/'evidence/heldout-result.json').read_text())
 if a.stage in ('guards','all'):
  run('probe_anchor_coverage.py');run('probe_guard_source.py');probe=json.loads((lab/'anchor-probe/manifest.json').read_text());candidate=lab/'candidate-rpm-guards';candidate.mkdir();rows=[r for r in probe['rows'] if r['rpm'] in (5400,5600)]
  for row in rows:shutil.copy2(lab/'anchor-probe'/row['file'],candidate/row['file'])
  (candidate/'manifest.json').write_text(json.dumps({'rows':[{**r,'candidate_sha256':r['sha256']} for r in rows]},indent=2)+'\n')
  render=out/'guards-render';run('guards-replay-frozen/run_replay.py','--repo',mirror,'--deps',a.deps.resolve(),'--output-dir',render,'--variant','candidate','--candidate-bank',candidate)
  run('analyze_guards.py','--render-output',render/'output');results['guards']=json.loads((lab/'evidence/rpm-guards-result.json').read_text())
 (out/'reproduced-results.json').write_text(json.dumps(results,indent=2)+'\n');print('RESEARCH_REPLAY_COMPLETE; read failed admission gates; no product promotion')
if __name__=='__main__':main()
