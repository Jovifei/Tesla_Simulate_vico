"""Export committed sources and receipts into a NEW isolated directory. No network/install."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

# Importing the adapter must not create __pycache__ in an original source checkout.
sys.dont_write_bytecode = True
from prepare_capture import adapt

ENGINE_PIN = '85f7c3b959a908ed5232ede4f1a4ac7eafe6b630'
SOLVER_PATH = 'dependencies/submodules/simple-2d-constraint-solver'
PAYLOAD = ['CMakeLists.txt', 'model_builder.cpp', 'model_builder.h', 'offline_main.cpp',
           'offline_taps.h', 'verify_capture.py', 'prepare_capture.py', 'prepare_workspace.py',
           'LICENSE-engine-sim.txt', 'LICENSE-solver.txt', 'README.md', 'HOST-RUNBOOK.md']


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    return subprocess.check_output(['git', '-C', str(repo), *args], env=env)


def repo_root(path):
    path = Path(path).resolve(strict=True)
    top = Path(git(path, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if top != path:
        raise ValueError(f'Pass an exact Git checkout root, not a parent/subdirectory: {path}')
    return path


def status(repo):
    return git(repo, 'status', '--porcelain=v1', '--untracked-files=all').decode('utf-8')


def extract(raw, dest):
    """Extract only regular src/include files and LICENSE. Reject links and traversal."""
    dest.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or '\\' in member.name
                    or ':' in member.name or not name.parts
                    or name.parts[0] not in ('src', 'include', 'LICENSE')
                    or (name.parts[0] == 'LICENSE' and len(name.parts) != 1)
                    or not (member.isfile() or member.isdir())):
                raise ValueError(f'Unexpected archive member: {member.name}')
            target = dest.joinpath(*name.parts)
            if not target.resolve().is_relative_to(dest.resolve()):
                raise ValueError(f'Escaping archive member: {member.name}')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst)


def manifest(root):
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()}


def export(repo, commit, name, out):
    git(repo, 'cat-file', '-e', commit + '^{commit}')
    raw = git(repo, 'archive', '--format=tar', commit, 'src', 'include', 'LICENSE')
    archive_path = out / 'archives' / (name + '.tar')
    archive_path.write_bytes(raw)
    snapshot = out / 'snapshot' / name
    extract(raw, snapshot)
    for path in ('src', 'include', 'LICENSE'):
        if not (snapshot / path).exists():
            raise ValueError(f'Archive is missing {name}/{path}')
    return {'commit': commit, 'archive': archive_path.relative_to(out).as_posix(),
            'archive_sha256': sha256(raw), 'files_sha256': manifest(snapshot),
            'license_sha256': sha256((snapshot / 'LICENSE').read_bytes())}


def prepare(engine_repo, product_repo, out, solver_repo=None):
    source = Path(__file__).resolve().parent
    engine = repo_root(engine_repo)
    product = repo_root(product_repo)
    solver = repo_root(solver_repo or engine / SOLVER_PATH)
    out = Path(out).resolve()
    for original in (engine, product, solver, source):
        if out == original or out.is_relative_to(original) or original.is_relative_to(out):
            raise ValueError(f'Output must be disjoint from original/source directories: {original}')
    if out.exists():
        raise FileExistsError(f'Refusing an existing output directory: {out}')
    actual_solver = git(solver, 'rev-parse', 'HEAD^{commit}').decode().strip()
    tree = git(engine, 'ls-tree', ENGINE_PIN, '--', SOLVER_PATH).decode().strip().split()
    if len(tree) < 3 or tree[0:2] != ['160000', 'commit']:
        raise ValueError('Pinned engine does not contain the expected solver gitlink')
    gitlink = tree[2]
    originals = {'engine': engine, 'product': product, 'solver': solver}
    before = {name: {'head': git(repo, 'rev-parse', 'HEAD').decode().strip(),
                     'porcelain': status(repo)} for name, repo in originals.items()}
    out.mkdir(parents=True, exist_ok=False)
    (out / 'archives').mkdir()
    (out / 'snapshot').mkdir()
    receipt = {'schema_version': 1, 'status': 'EXPORT_IN_PROGRESS',
               'created_utc': datetime.now(timezone.utc).isoformat(),
               'engine_repository': 'https://github.com/ange-yaghi/engine-sim',
               'solver_repository': 'https://github.com/ange-yaghi/simple-2d-constraint-solver',
               'engine_pin': ENGINE_PIN, 'solver_actual_checkout_sha': actual_solver,
               'solver_engine_gitlink_sha': gitlink,
               'solver_matches_engine_gitlink': actual_solver == gitlink,
               'original_repositories_before': before,
               'no_fetch_install_checkout_clean': True,
               'DTV': False, 'DISCORD_ENABLED': False,
               'build_validation': 'NOT_RUN', 'smoke_validation': 'NOT_RUN',
               'model': 'generic_crossplane_v8_ls_example_NOT_HELLCAT_NO_OEM_CALIBRATION'}
    try:
        receipt['engine'] = export(engine, ENGINE_PIN, 'engine', out)
        receipt['solver'] = export(solver, actual_solver, 'solver', out)
        # Arbitrary solver HEADs cannot inherit a historical MIT assertion.
        for name, license_file in (('engine', 'LICENSE-engine-sim.txt'), ('solver', 'LICENSE-solver.txt')):
            expected = (source / license_file).read_bytes().replace(b'\r\n', b'\n')
            actual = (out / 'snapshot' / name / 'LICENSE').read_bytes().replace(b'\r\n', b'\n')
            if actual != expected:
                raise ValueError(f'{name} LICENSE differs from reviewed full MIT text; stop for review')
        shutil.copytree(out / 'snapshot' / 'engine', out / 'upstream')
        shutil.copytree(out / 'snapshot' / 'solver', out / 'solver')
        for name in PAYLOAD:
            shutil.copyfile(source / name, out / name)
        receipt['adapter_files_sha256'] = {name: sha256((source / name).read_bytes()) for name in PAYLOAD}
        receipt['adaptations'] = adapt(out)
        receipt['prepared_engine_files_sha256'] = manifest(out / 'upstream')
        receipt['prepared_solver_files_sha256'] = manifest(out / 'solver')
        receipt['status'] = ('EXPORTED_NOT_BUILT' if actual_solver == gitlink
                             else 'EXPORTED_STOP_SOLVER_COMPATIBILITY_REVIEW_REQUIRED')
    except Exception as error:
        receipt['status'] = 'EXPORT_FAILED_PRESERVE_FOR_DIAGNOSIS'
        receipt['error'] = str(error)
        raise
    finally:
        after = {name: {'head': git(repo, 'rev-parse', 'HEAD').decode().strip(),
                        'porcelain': status(repo)} for name, repo in originals.items()}
        receipt['original_repositories_after'] = after
        receipt['original_repositories_unchanged'] = before == after
        if before != after:
            receipt['status'] = 'STOP_ORIGINAL_REPOSITORY_CHANGED'
        (out / 'source-identity.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    if before != after:
        raise RuntimeError('Original Git status or HEAD changed; stop and investigate concurrent activity')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-repo', type=Path, required=True)
    parser.add_argument('--product-repo', type=Path, required=True)
    parser.add_argument('--solver-repo', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.engine_repo, args.product_repo, args.out, args.solver_repo)
    print(json.dumps({'out': str(args.out), 'status': result['status'],
                      'engine': result['engine_pin'], 'solver': result['solver_actual_checkout_sha']}))
