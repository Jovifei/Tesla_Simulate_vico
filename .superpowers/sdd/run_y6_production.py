"""One staged, logged Stage-Y production package run; no renderer changes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FINAL = Path('E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v1')

def now():
    return datetime.now(timezone.utc).isoformat()

if len(sys.argv) == 3 and sys.argv[1] == '--worker':
    sys.path.insert(0, str(ROOT))
    from tools.sound_sim.s12.acoustic_identity_v015.stage_y import package
    stage = Path(sys.argv[2])
    original = package.build_hellcat_bakeoff_trace
    scene_number = 0
    def observed_trace(scene, duration):
        global scene_number
        scene_number += 1
        print(f'[{scene_number}/{len(package.SCENES)}] render {scene} duration={duration}s', flush=True)
        return original(scene, duration)
    package.build_hellcat_bakeoff_trace = observed_trace
    manifest = package.build_hellcat_layer_package(stage, long_window=True, duration_s=8.0)
    errors = package.validate_layer_package(stage)
    if errors:
        raise RuntimeError(errors)
    if FINAL.exists():
        raise FileExistsError(FINAL)
    stage.rename(FINAL)
    errors = package.validate_layer_package(FINAL)
    if errors:
        raise RuntimeError(errors)
    print(json.dumps({'status': 'PACKAGE_VALIDATED', 'output': str(FINAL), 'scene_count': len(manifest['scenes'])}), flush=True)
else:
    if FINAL.exists():
        raise FileExistsError(FINAL)
    run_id = 'y6-production-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stage = FINAL.parent / ('.' + run_id)
    logs = ROOT / 'tasks/reports/runtime/s12-stage-y/y6_audition/logs'
    logs.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(stage)]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    stdout, stderr = logs / f'{run_id}.stdout.log', logs / f'{run_id}.stderr.log'
    started = now()
    print(f'RUN_ID={run_id}', flush=True)
    with stdout.open('wb') as out, stderr.open('wb') as err:
        result = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err)
    ended = now()
    record = {'run_id': run_id, 'command': command, 'source_head': head, 'started_at': started, 'ended_at': ended, 'exit_code': result.returncode, 'output': str(FINAL), 'stage': str(stage), 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'logs': {}}
    for name, path in [('stdout', stdout), ('stderr', stderr)]:
        record['logs'][name] = {'path': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if result.returncode == 0:
        manifest = FINAL / 'package_manifest.json'
        record['package_manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (logs / f'{run_id}.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record), flush=True)
    sys.exit(result.returncode)
