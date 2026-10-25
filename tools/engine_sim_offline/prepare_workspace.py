"""Create a NEW reproducible experiment from exact local Git objects. No fetch/install."""
import argparse, io, json, shutil, subprocess, sys, tarfile
from pathlib import Path

ENGINE='85f7c3b959a908ed5232ede4f1a4ac7eafe6b630'
SOLVER='e009f4ff1c9c4c5874e865e893cdb62e208fb2b3'

def export(repo,sha,dest):
    subprocess.run(['git','-C',str(repo),'cat-file','-e',sha+'^{commit}'],check=True)
    raw=subprocess.check_output(['git','-C',str(repo),'archive',sha,'src','include','LICENSE'])
    dest.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
        for member in archive:
            target=(dest/member.name).resolve()
            if not target.is_relative_to(dest.resolve()) or not (member.isdir() or member.isfile()):
                raise ValueError('Unexpected archive member: '+member.name)
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine-repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();source=Path(__file__).resolve().parent;out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    export(a.engine_repo,ENGINE,out/'upstream')
    export(a.engine_repo/'dependencies/submodules/simple-2d-constraint-solver',SOLVER,out/'solver')
    # Only platform/dependency adaptation before the separately logged read-only taps.
    f=out/'upstream/src/synthesizer.cpp';s=f.read_text();assert '#include "../include/delta.h"' in s
    f.write_text(s.replace('#include "../include/delta.h"',''),newline='\n')
    f=out/'upstream/include/scs.h';s=f.read_text();s=s.replace('../dependencies/submodules/simple-2d-constraint-solver/include/scs.h','../../solver/include/scs.h');f.write_text(s,newline='\n')
    for name in ['CMakeLists.txt','model_builder.cpp','model_builder.h','offline_main.cpp','offline_taps.h','prepare_capture.py','verify_capture.py','run_captures.py','analyze_captures.py','test_analysis.py','render_vico_trace.mjs']:
        shutil.copyfile(source/name,out/name)
    subprocess.run([sys.executable,str(out/'prepare_capture.py')],check=True)
    (out/'source-identity.json').write_text(json.dumps({'engine':ENGINE,'solver':SOLVER,'no_fetch_or_install':True},indent=2)+'\n')
    print(out)

if __name__=='__main__':main()
