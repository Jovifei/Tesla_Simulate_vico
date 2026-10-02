"""Windows adapter contracts run with a fake CRT; real process tests run on the host OS.

Passing these mocks is not a claim that Windows locking or Windows crash durability was tested.
"""
import errno
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import n2_artifact_gate as gate


class WindowsLockContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.crt = SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=Mock())
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {"msvcrt": self.crt}).start()

    def test_byte_zero_locked_and_unlocked_even_for_empty_sidecar(self):
        positions = []
        self.crt.locking.side_effect = lambda fd, mode, size: positions.append((os.lseek(fd, 0, os.SEEK_CUR), mode, size))
        path = self.root / "budget.json"
        with patch.object(gate.sys, "platform", "win32"):
            with gate._ledger_lock(path) as locked:
                self.assertEqual(path.resolve(), locked)
                self.assertEqual([(0, self.crt.LK_NBLCK, 1)], positions)
        self.assertEqual([(0, 2, 1), (0, 0, 1)], positions)
        self.assertEqual(b"", path.with_name("budget.json.lock").read_bytes())

    def test_contention_retries_beyond_builtin_ten_attempts(self):
        self.crt.locking.side_effect = [OSError(errno.EACCES, "locked")] * 12 + [None, None]
        with (self.root / "lock").open("a+b", buffering=0) as lock:
            with patch.object(gate.time, "sleep") as sleep:
                with gate._windows_process_lock(lock):
                    self.assertEqual(13, self.crt.locking.call_count)
                self.assertEqual(12, sleep.call_count)
                sleep.assert_called_with(.05)
        self.assertEqual(14, self.crt.locking.call_count)
        self.assertEqual(self.crt.LK_UNLCK, self.crt.locking.call_args.args[1])

    def test_noncontention_error_does_not_enter_or_unlock(self):
        for code in (errno.EBADF, errno.EINVAL, errno.EIO):
            with self.subTest(code=code):
                self.crt.locking.reset_mock(side_effect=True)
                self.crt.locking.side_effect = OSError(code, "failure")
                with (self.root / "lock").open("a+b", buffering=0) as lock:
                    with patch.object(gate.time, "sleep") as sleep:
                        with self.assertRaises(OSError) as caught:
                            with gate._windows_process_lock(lock):
                                self.fail("critical section entered without lock")
                        self.assertEqual(code, caught.exception.errno)
                        self.crt.locking.assert_called_once_with(lock.fileno(), self.crt.LK_NBLCK, 1)
                        sleep.assert_not_called()

    def test_interrupted_wait_does_not_unlock_unacquired_range(self):
        self.crt.locking.side_effect = OSError(errno.EACCES, "locked")
        with (self.root / "lock").open("a+b", buffering=0) as lock:
            with patch.object(gate.time, "sleep", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    with gate._windows_process_lock(lock):
                        self.fail("entered")
        self.assertEqual(1, self.crt.locking.call_count)

    def test_body_exception_releases_original_range(self):
        positions = []
        self.crt.locking.side_effect = lambda fd, mode, size: positions.append((os.lseek(fd, 0, os.SEEK_CUR), mode, size))
        with (self.root / "lock").open("a+b", buffering=0) as lock:
            with self.assertRaisesRegex(RuntimeError, "body"):
                with gate._windows_process_lock(lock):
                    lock.seek(42)
                    raise RuntimeError("body")
        self.assertEqual([(0, 2, 1), (0, 0, 1)], positions)

    def test_unlock_error_is_not_reported_as_success(self):
        self.crt.locking.side_effect = [None, OSError(errno.EIO, "unlock failure")]
        with (self.root / "lock").open("a+b", buffering=0) as lock:
            with self.assertRaises(OSError):
                with gate._windows_process_lock(lock):
                    pass

    def test_missing_windows_lock_backend_fails_closed(self):
        with patch.dict(sys.modules, {"msvcrt": None}):
            with (self.root / "lock").open("a+b", buffering=0) as lock:
                with self.assertRaisesRegex(ValueError, "windows_process_lock_unavailable"):
                    with gate._windows_process_lock(lock):
                        self.fail("entered")

    def test_windows_atomic_replace_flushes_file_but_not_directory(self):
        path = self.root / "budget.json"
        real_open = gate.os.open
        calls = []
        def record_open(target, *args, **kwargs):
            calls.append(Path(target))
            return real_open(target, *args, **kwargs)
        with (patch.object(gate.sys, "platform", "win32"),
              patch.object(gate.os, "open", side_effect=record_open),
              patch.object(gate.os, "fsync", wraps=gate.os.fsync) as fsync):
            gate.atomic_json(path, {"first": True})
            gate.atomic_json(path, {"second": True})
            self.assertEqual(2, fsync.call_count)
        self.assertEqual({"second": True}, gate.load(path))
        self.assertNotIn(self.root, calls)
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_failed_replace_preserves_previous_file_and_cleans_temp(self):
        path = self.root / "budget.json"
        path.write_bytes(b'{"original":true}')
        with (patch.object(gate.sys, "platform", "win32"),
              patch.object(gate.os, "replace", side_effect=PermissionError("sharing violation"))):
            with self.assertRaises(PermissionError):
                gate.atomic_json(path, {"uncommitted": True})
        self.assertEqual(b'{"original":true}', path.read_bytes())
        self.assertFalse(list(self.root.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
