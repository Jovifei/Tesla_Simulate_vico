"""Preserve CRLF contracts and stored patch context without hiding source whitespace."""
import hashlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PATCH = "tools/patches/vico-p3-audio-engine-hook.patch"


def test_archived_patch_bytes_are_unchanged():
    assert hashlib.sha256((ROOT / PATCH).read_bytes()).hexdigest() == (
        "bbdb52d8361c17d45ebf692c0d4f68728a556a2cb80d66402e55c14bda2ed017"
    )


@pytest.mark.parametrize("path,content,clean", [
    ("source.py", b"line\r\n", True),
    ("source.py", b"line \r\n", False),
    ("source.py", b"line\r\n\r\n", False),
    ("source.py", b" \tline\r\n", False),
    (PATCH, b"@@ context @@\n \n+line\n", True),
    ("other.patch", b"@@ context @@\n \n+line\n", False),
    (PATCH, b"@@ context @@\n+line\n\n", False),
])
def test_whitespace_policy_in_real_git_history(tmp_path, path, content, clean):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True)

    assert git("init", "-q").returncode == 0
    assert git("config", "core.autocrlf", "false").returncode == 0
    (tmp_path / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    assert git("add", ".").returncode == 0
    assert git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
               "commit", "-qm", "baseline").returncode == 0
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    assert git("add", ".").returncode == 0
    staged = git("diff", "--cached", "--check")
    assert (staged.returncode == 0) == clean, staged.stdout
    assert git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
               "commit", "-qm", "candidate").returncode == 0
    committed = git("diff", "--check", "HEAD~..HEAD")
    assert (committed.returncode == 0) == clean, committed.stdout
