"""Synthetic contract tests only. These do NOT build or simulate engine-sim."""
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import prepare_capture
import prepare_workspace as workspace
import verify_capture


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def fixture_capture(root):
    root.mkdir()
    data = {'model': 'generic_crossplane_v8_ls_example_NOT_HELLCAT', 'scene': 'smoke',
            'qualification': 'OFFLINE_SYNTHETIC_MECHANISM_ONLY', 'duration_s': .01,
            'physics_fs': 10000, 'audio_fs': 44100, 'warmup_s': 5, 'seed': 24817,
            'physics_frames': 100, 'audio_frames': 441, 'all_steps': 50100,
            'clip_count': 0, 'final_peak': 0}
    write_json(root / 'capture.json', data)
    write_json(root / 'physical-validity.json', {
        'cw_all_capture': True, 'initialization': 'upstream_starter0.5s_then_hold_dyno',
        'min_omega_rad_s': -100, 'max_omega_rad_s': -100, 'lit_cylinder_steps': 1})
    (root / 'pressure-input.f32le').write_bytes(struct.pack('<18f', *([101325] * 16 + [0, 0])) * 100)
    (root / 'signed-omega.f32le').write_bytes(struct.pack('<f', -100) * 100)
    (root / 'audio-taps.f32le').write_bytes(struct.pack('<6f', 0, 0, 0, 0, 1, 0) * 441)
    (root / 'state.csv').write_text('t_s,rpm,target_rpm,speed_control,throttle_plate,map_pa,cycle_angle_rad,integrated_cycles\n.01,910,910,.08,.5,101325,1,.1\n')
    (root / 'dyno.csv').write_text('t_s,torque_nm\n.01,10\n')
    return data


def fixture_sources(root):
    """Tiny source-shaped fixtures: not upstream source and not compilable."""
    for name in ('src', 'include'):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / 'include' / 'scs.h').write_text('#include "../dependencies/submodules/simple-2d-constraint-solver/include/scs.h"\n')
    (root / 'src' / 'simulator.cpp').write_text('''    const double targetLatency = getSynthesizerInputLatencyTarget();
    if (m_synthesizer.getLatency() < targetLatency) {
        m_steps = static_cast<int>((m_steps + 1) * 1.1);
    }
    else if (m_synthesizer.getLatency() > targetLatency) {
        m_steps = static_cast<int>((m_steps - 1) * 0.9);
        if (m_steps < 0) {
            m_steps = 0;
        }
    }
    m_synthesizer.destroy();
''')
    (root / 'src' / 'piston_engine_simulator.cpp').write_text('    synthesizer().writeInput(m_exhaustFlowStagingBuffer);\n')
    (root / 'src' / 'synthesizer.cpp').write_text('''#include "../include/delta.h"
    float signal = 0;
        const float r_0 = 1;
    int r_int = std::lround(v_leveled);
    return static_cast<int16_t>(r_int);
''')


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()


def init_repo(path):
    path.mkdir()
    git(path, 'init', '-q')
    git(path, 'config', 'user.name', 'Synthetic fixture')
    git(path, 'config', 'user.email', 'fixture@example.invalid')
    return path


def commit(path):
    git(path, 'add', '.')
    git(path, 'commit', '-qm', 'Synthetic contract fixture, not upstream')
    return git(path, 'rev-parse', 'HEAD')


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'capture'
        self.meta = fixture_capture(self.root)

    def mutate_float(self, filename, index, value):
        path = self.root / filename
        data = bytearray(path.read_bytes())
        struct.pack_into('<f', data, index * 4, value)
        path.write_bytes(data)

    def test_valid_synthetic_fixture(self):
        self.assertTrue(verify_capture.verify(self.root)['signed_rotation_all_negative'])

    def test_missing_physical_evidence_fails(self):
        (self.root / 'physical-validity.json').unlink()
        with self.assertRaises(FileNotFoundError):
            verify_capture.verify(self.root)

    def test_missing_rotation_fails(self):
        (self.root / 'signed-omega.f32le').unlink()
        with self.assertRaises(FileNotFoundError):
            verify_capture.verify(self.root)

    def test_wrong_frames(self):
        self.meta['physics_frames'] = 99
        write_json(self.root / 'capture.json', self.meta)
        with self.assertRaises(ValueError):
            verify_capture.verify(self.root)

    def test_truncated_and_extra_bytes(self):
        path = self.root / 'audio-taps.f32le'
        raw = path.read_bytes()
        for data in (raw[:-1], raw + b'0'):
            with self.subTest(length=len(data)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    verify_capture.verify(self.root)

    def test_nonfinite_streams(self):
        for name in ('pressure-input.f32le', 'audio-taps.f32le', 'signed-omega.f32le'):
            original = (self.root / name).read_bytes()
            for value in (float('nan'), float('inf'), -float('inf')):
                with self.subTest(stream=name, value=value):
                    self.mutate_float(name, 0, value)
                    with self.assertRaises(ValueError):
                        verify_capture.verify(self.root)
            (self.root / name).write_bytes(original)

    def test_nonpositive_pressure(self):
        for value in (0, -1):
            self.mutate_float('pressure-input.f32le', 15, value)
            with self.assertRaises(ValueError):
                verify_capture.verify(self.root)

    def test_signed_reverse_or_stopped_rotation(self):
        for value in (0, 100):
            self.mutate_float('signed-omega.f32le', 50, value)
            with self.assertRaises(ValueError):
                verify_capture.verify(self.root)

    def test_physical_summary_cannot_override_stream(self):
        physical = json.loads((self.root / 'physical-validity.json').read_text())
        physical['max_omega_rad_s'] = -90
        write_json(self.root / 'physical-validity.json', physical)
        with self.assertRaises(ValueError):
            verify_capture.verify(self.root)

    def test_bad_csv_timing_and_nonfinite(self):
        path = self.root / 'dyno.csv'
        for row in ('0.0099,10', '.01,nan', '.01,10,extra'):
            path.write_text('t_s,torque_nm\n' + row + '\n')
            with self.assertRaises(ValueError):
                verify_capture.verify(self.root)

    def test_nonfinite_json(self):
        for value in (float('nan'), float('inf')):
            self.meta['unused_wall_s'] = value
            write_json(self.root / 'capture.json', self.meta)
            with self.assertRaises(ValueError):
                verify_capture.verify(self.root)

    def test_clamp_rounding_edges(self):
        for leveled, output, flag in ((32767.2, 32767 / 32768, 0),
                                      (32767.75, 32767 / 32768, 1),
                                      (-32768.25, -1, 0), (-32768.75, -1, 1)):
            with self.subTest(leveled=leveled):
                (self.root / 'audio-taps.f32le').write_bytes(struct.pack('<6f', 0, 0, leveled, output, 1, flag) * 441)
                self.meta['clip_count'], self.meta['final_peak'] = flag * 441, abs(output)
                write_json(self.root / 'capture.json', self.meta)
                verify_capture.verify(self.root)

    def test_wrong_pcm_and_clamp_flag(self):
        for column in (3, 5):
            original = (self.root / 'audio-taps.f32le').read_bytes()
            self.mutate_float('audio-taps.f32le', column, 1)
            with self.assertRaises(ValueError):
                verify_capture.verify(self.root)
            (self.root / 'audio-taps.f32le').write_bytes(original)

    def test_python_optimized_still_rejects(self):
        self.mutate_float('signed-omega.f32le', 0, 1)
        result = subprocess.run([sys.executable, '-O', str(Path(verify_capture.__file__)),
                                 str(self.root), '--out', str(self.root.parent / 'not-created.json')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root.parent / 'not-created.json').exists())


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.engine = init_repo(self.root / 'engine')
        self.solver = init_repo(self.root / 'solver')
        self.product = init_repo(self.root / 'product')
        source = Path(workspace.__file__).parent
        fixture_sources(self.engine)
        fixture_sources(self.solver)
        (self.engine / 'LICENSE').write_bytes((source / 'LICENSE-engine-sim.txt').read_bytes())
        (self.solver / 'LICENSE').write_bytes((source / 'LICENSE-solver.txt').read_bytes())
        solver_sha = commit(self.solver)
        git(self.engine, 'add', '.')
        git(self.engine, 'update-index', '--add', '--cacheinfo', f'160000,{solver_sha},{workspace.SOLVER_PATH}')
        git(self.engine, 'commit', '-qm', 'Synthetic engine fixture with solver gitlink')
        self.engine_sha = git(self.engine, 'rev-parse', 'HEAD')
        (self.product / 'keep.txt').write_text('original product unchanged')
        commit(self.product)
        # Fixture-only pin substitution. Production CLI has no pin override.
        self.mock = patch.object(workspace, 'ENGINE_PIN', self.engine_sha)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def prepare(self, name='out'):
        return workspace.prepare(self.engine, self.product, self.root / name, self.solver)

    def test_archive_receipts_dirty_files_ignored_and_sources_unchanged(self):
        (self.engine / 'src' / 'synthesizer.cpp').write_text('dirty source MUST NOT be exported')
        (self.solver / 'untracked.txt').write_text('untracked MUST NOT be exported')
        before = {p: workspace.status(p) for p in (self.engine, self.solver, self.product)}
        result = self.prepare()
        self.assertEqual(result['status'], 'EXPORTED_NOT_BUILT')
        self.assertTrue(result['original_repositories_unchanged'])
        self.assertEqual(len(result['adaptations']), 4)
        self.assertEqual(result['solver_actual_checkout_sha'], git(self.solver, 'rev-parse', 'HEAD'))
        self.assertEqual(before, {p: workspace.status(p) for p in before})
        self.assertNotIn('dirty source', (self.root / 'out/snapshot/engine/src/synthesizer.cpp').read_text())
        self.assertFalse((self.root / 'out/snapshot/solver/untracked.txt').exists())
        self.assertTrue((self.root / 'out/archives/engine.tar').is_file())
        self.assertTrue(result['prepared_engine_files_sha256'])

    def test_existing_output_rejected_without_writes(self):
        out = self.root / 'out'
        out.mkdir()
        (out / 'keep').write_text('keep')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((out / 'keep').read_text(), 'keep')

    def test_output_inside_each_original_rejected(self):
        for repo in (self.engine, self.solver, self.product):
            with self.subTest(repo=repo):
                with self.assertRaises(ValueError):
                    workspace.prepare(self.engine, self.product, repo / 'new', self.solver)
                self.assertFalse((repo / 'new').exists())

    def test_actual_solver_mismatch_recorded_without_substitution(self):
        (self.solver / 'src' / 'new.cpp').write_text('new committed solver fixture')
        actual = commit(self.solver)
        result = self.prepare()
        self.assertEqual(result['solver_actual_checkout_sha'], actual)
        self.assertFalse(result['solver_matches_engine_gitlink'])
        self.assertEqual(result['status'], 'EXPORTED_STOP_SOLVER_COMPATIBILITY_REVIEW_REQUIRED')

    def test_changed_license_stops_and_preserves_receipt(self):
        (self.solver / 'LICENSE').write_text('Not the reviewed MIT license')
        commit(self.solver)
        with self.assertRaises(ValueError):
            self.prepare()
        receipt = json.loads((self.root / 'out/source-identity.json').read_text())
        self.assertEqual(receipt['status'], 'EXPORT_FAILED_PRESERVE_FOR_DIAGNOSIS')
        self.assertTrue(receipt['original_repositories_unchanged'])

    def test_patch_cannot_apply_twice(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            prepare_capture.adapt(self.root / 'out')


class GuardTests(unittest.TestCase):
    def test_missing_or_duplicate_patch_anchor(self):
        for text in ('none', 'xx'):
            with self.assertRaises(ValueError):
                prepare_capture.replace_once(text, 'x', 'y')

    def test_export_cli_help_leaves_source_directory_unchanged(self):
        import shutil
        import os
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = Path(workspace.__file__).parent
            for name in ('prepare_workspace.py', 'prepare_capture.py'):
                shutil.copyfile(source / name, root / name)
            before = workspace.manifest(root)
            env = dict(os.environ)
            env.pop('PYTHONDONTWRITEBYTECODE', None)
            result = subprocess.run([sys.executable, str(root / 'prepare_workspace.py'), '--help'],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(workspace.manifest(root), before)
            self.assertFalse((root / '__pycache__').exists())

    def test_tar_traversal_links_and_unexpected_paths_rejected(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('src/../../escape', tarfile.REGTYPE),
                           ('src\\escape', tarfile.REGTYPE), ('/src/escape', tarfile.REGTYPE),
                           ('src/link', tarfile.SYMTYPE), ('bin/ce.exe', tarfile.REGTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode='w') as archive:
                    item = tarfile.TarInfo(name)
                    item.type = kind
                    item.linkname = '/outside'
                    archive.addfile(item, io.BytesIO())
                with self.assertRaises(ValueError):
                    workspace.extract(buffer.getvalue(), Path(temporary) / 'extract')


if __name__ == '__main__':
    unittest.main(verbosity=2)
