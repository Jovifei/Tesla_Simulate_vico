#!/usr/bin/env python3
"""Reproduce the four pinned C63 low-RPM loops in a NEW output directory.

Uses the repository's existing synthetic recipe/PTR and original fixed gain.
Requires the repository's authoring dependencies; installs nothing. Never loads
private recordings, replaces original assets, changes gain, or clips a failure.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib,json,struct,sys,types
import numpy as np
from loop_preroll import make_period_preserving_loop

EXPECTED_MANIFEST_SHA256='f26d7ae6736af106e6cbb38c2ce6fdb097ae86d39f23c3f5f70a46af6a72de91'
def sha(b):return hashlib.sha256(b).hexdigest()
def decode(b):
    if b[:4]!=b'RIFF' or b[8:12]!=b'WAVE':raise ValueError('Expected RIFF')
    p=12;fmt=None
    while p+8<=len(b):
        key=b[p:p+4];n=struct.unpack_from('<I',b,p+4)[0];data=b[p+8:p+8+n]
        if len(data)!=n:raise ValueError('Truncated WAV')
        if key==b'fmt ':fmt=struct.unpack_from('<HHIIHH',data)
        elif key==b'data':
            if fmt is None or fmt[0]!=3 or fmt[1]!=1 or fmt[2]!=48000 or fmt[5]!=32:raise ValueError('Expected float32 mono 48k')
            x=np.frombuffer(data,dtype='<f4').copy()
            if not np.isfinite(x).all():raise ValueError('Nonfinite reference')
            return x
        p+=8+n+n%2
    raise ValueError('No data chunk')
def encode(x):
    b=np.asarray(x,dtype='<f4').tobytes()
    return b'RIFF'+struct.pack('<I',36+len(b))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,3,1,48000,192000,4,32)+b'data'+struct.pack('<I',len(b))+b

def source_api(repo):
    # Namespace containers bypass unrelated package exporters; every DSP function is original source.
    core=repo/'tools/sound_sim/s12/acoustic_identity_v015'
    package='_vico_live_loop_repro'
    for name,path in [(package,core),(package+'.sources',core/'sources'),(package+'.acoustic_layers',core/'acoustic_layers')]:
        module=types.ModuleType(name);module.__path__=[str(path)];sys.modules[name]=module
    contracts=importlib.import_module(package+'.contracts')
    renderer=importlib.import_module(package+'.sources.mercedes_v8_source').render_c63_w204
    layer_names=['idle_dynamics','afterfire_model','low_frequency_body','exhaust_rumble','shift_dynamics','pre_equalization']
    function_names=['apply_idle_dynamics','apply_afterfire','apply_low_frequency_body','apply_exhaust_rumble','apply_shift_dynamics','apply_pre_ptr_equalization']
    env={'np':np,'SRC_RATE':48000,'APP_RATE':48000,'LOOP_SECONDS':.36,'_SAMPLE_RATE_HZ':48000,'SourceRender':contracts.SourceRender,'VehicleStateTrace':contracts.VehicleStateTrace}
    for module_name,function_name in zip(layer_names,function_names):env[function_name]=getattr(importlib.import_module(package+'.acoustic_layers.'+module_name),function_name)
    exporter=repo/'vico_app/tools/python/export_s12_android_sound_banks.py'
    for path,names in [(exporter,{'_constant_trace','_mono_48k','_loop'}),(core/'render_realism_v10.py',{'_render_stateful'})]:
        nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
        if {n.name for n in nodes}!=names:raise ValueError('Original source helper missing')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
    demo=repo/'tools/sound_sim/s12/acoustic_demo';sys.path.insert(0,str(demo))
    config=importlib.import_module('s12_ptr_network').PtrNetworkConfig(package_path=repo/'tools/sound_sim/s12/benchmark/baselines/sprint-4d-b/radiation-boundary-package.json')
    adapter=importlib.import_module('runtime_ptr_adapter').RuntimePtrAdapter
    def ptr(stereo):return np.column_stack([adapter(config=config).process(stereo[:,i]) for i in range(2)])
    return contracts.VehicleStateTrace,renderer,env,ptr

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--repo',type=Path,required=True);a.add_argument('--output-dir',type=Path,required=True);args=a.parse_args()
    repo=args.repo.resolve();out=args.output_dir.resolve();reference=repo/'vico_app/Project/android/app/src/main/assets/s12_v10/c63_w204_v6'
    if out.exists() or out.is_relative_to(reference):raise SystemExit('Use a new directory outside the original bank')
    manifest_bytes=(reference/'manifest.json').read_bytes();manifest=json.loads(manifest_bytes);gain=manifest['fixed_vehicle_gain'];limit=10**(manifest['peak_limit_dbfs']/20)
    Trace,renderer,helpers,ptr=source_api(repo)
    lines=['schema=vico.live_loop_variant.v1','variant_id=c63_low_rpm_preroll_v1','vehicle_key=c63_w204_v6','sample_rate_hz=48000','baseline_manifest_sha256='+sha(manifest_bytes),'fixed_vehicle_gain='+str(gain),'peak_limit_dbfs=-1.5','loop_count=4'];files={}
    entries=[e for e in manifest['loops'] if e['rpm'] in (700,1400)]
    if len(entries)!=4:raise ValueError('Unexpected original low-RPM grid')
    for i,e in enumerate(entries):
        raw=(reference/e['file']).read_bytes();expected=decode(raw)
        trace=helpers['_constant_trace'](Trace,e['rpm'],e['load'],.52)
        rendered=helpers['_render_stateful'](renderer,'c63_w204',trace)
        pre=helpers['_mono_48k'](ptr(rendered.pressure))
        baseline=(helpers['_loop'](pre)*gain).astype(np.float32)
        if not np.array_equal(baseline,expected):raise ValueError('Original recipe no longer reproduces pinned C63 loop exactly')
        repaired,metadata=make_period_preserving_loop(pre,48000);pcm=(repaired*gain).astype(np.float32)
        if len(pcm)!=17280 or not np.isfinite(pcm).all() or float(max(abs(pcm)))>limit+1e-7:raise ValueError('Fixed period/finite/peak guard failed')
        wav=encode(pcm);files[e['file']]=wav
        row={'rpm':e['rpm'],'load':e['load'],'file':e['file'],'samples':len(pcm),'baseline_wav_sha256':sha(raw),'candidate_wav_sha256':sha(wav)}
        lines += [f'loop.{i}.{key}={row[key]}' for key in ('rpm','load','file','samples','baseline_wav_sha256','candidate_wav_sha256')]
    props=('\n'.join(lines)+'\n').encode('ascii')
    if sha(props)!=EXPECTED_MANIFEST_SHA256:raise ValueError('Generated variant differs from reviewed identity; do not publish')
    out.mkdir(parents=True,exist_ok=False)
    for name,b in files.items():(out/name).write_bytes(b)
    (out/'manifest.properties').write_bytes(props)
    print(json.dumps({'variant':'c63_low_rpm_preroll_v1','files':{name:sha(b) for name,b in files.items()},'manifest_sha256':sha(props),'reference_unchanged':True,'gain_unchanged':gain},indent=2))
if __name__=='__main__':main()
