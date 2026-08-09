"""Track-P 冻结守卫的回归测试（守卫的守卫）。

背景：2026-08-08 的仓库损坏事件让旧基线 301fed4 的 git 对象永久丢失，
Track-P 断言随之失效且无诊断信息。重建为 Baseline v2 时，断言脚本从
「纯路径子串匹配 + 依赖 BASE commit 存活」升级为「内容寻址摘要 + 符号级
守卫」。本测试把当时手工做的三个负向验证固化下来，避免守卫在后续改动中
被悄悄削弱。Baseline v3 只重固化统一分支的冻结快照，不改变守卫算法。

覆盖：
  - 冻结路径分类（含 Track-S 豁免、未跟踪文件的目录段规则）
  - 冻结文件清单摘要与常量一致（等价于「Track-P 内容未被改动」）
  - 冻结符号摘要与常量一致，且任一符号被改就会变化
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "assert_track_p_unchanged.py"
)


def _load_guard():
    spec = importlib.util.spec_from_file_location("_s12_track_p_guard", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载守卫脚本: {_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


# --------------------------------------------------------------------------
# 冻结路径分类
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "tools/sound_sim/s12/acoustic_demo/runtime_ptr_adapter.py",
        "tools/sound_sim/s12/validation/radiation_impedance/s12_radiation_case_definition.m",
        "tools/sound_sim/s12/tests/test_s12_fanno_fvm_contract.m",
        "tools/sound_sim/matlab/anything.m",
    ],
)
def test_frozen_paths_are_classified_frozen(path: str) -> None:
    assert guard._is_frozen(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "tools/sound_sim/s12/acoustic_identity_v015/tuning/loudness_compensation.py",
        "tools/sound_sim/s12/acoustic_identity_v015/sources/flat_plane_v8_source.py",
        "tools/sound_sim/s12/acoustic_identity_v015/render_identity_v02.py",
    ],
)
def test_track_s_paths_are_not_frozen(path: str) -> None:
    assert guard._is_frozen(path) is False


def test_allowlisted_track_s_file_is_not_frozen() -> None:
    """文件名含 "ptr" 的 Track-S 单测必须被豁免，否则改它就假 FAIL。"""
    path = (
        "tools/sound_sim/s12/acoustic_identity_v015/tests/"
        "test_s12_post_ptr_loudness_compensation.py"
    )
    assert path in guard.TRACK_S_ALLOWLIST
    assert guard._is_frozen(path) is False
    assert guard._is_frozen_untracked(path) is False


def test_untracked_scratch_script_named_after_frozen_token_is_allowed() -> None:
    """未跟踪的分析脚本仅因文件名含 radiation 不应被判越界。"""
    path = (
        "tools/sound_sim/s12/acoustic_identity_v015/scripts/"
        "_analyze_radiation_fidelity.py"
    )
    assert guard._is_frozen_untracked(path) is False
    # 已跟踪判定仍保守命中——这正是需要区分两种规则的原因
    assert guard._is_frozen(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "tools/sound_sim/matlab/brand_new.m",
        "tools/sound_sim/s12/acoustic_demo/brand_new.py",
        "tools/sound_sim/s12/validation/radiation_impedance/brand_new.m",
    ],
)
def test_untracked_file_inside_frozen_directory_is_rejected(path: str) -> None:
    """往冻结目录塞新文件必须被拦截。"""
    assert guard._is_frozen_untracked(path) is True


# --------------------------------------------------------------------------
# 内容寻址摘要
# --------------------------------------------------------------------------

def test_frozen_manifest_matches_baseline_constant() -> None:
    entries, digest = guard._frozen_manifest("HEAD")
    assert len(entries) == guard.FROZEN_MANIFEST_COUNT
    assert digest == guard.FROZEN_MANIFEST_SHA256


def test_frozen_symbol_digest_matches_baseline_constant() -> None:
    _, digest = guard._symbol_digest_from_worktree()
    assert digest == guard.FROZEN_SYMBOL_SHA256


def test_symbol_extraction_is_line_ending_and_comment_invariant() -> None:
    """AST 规范化必须吃掉行尾/注释/空白差异，只对语义敏感。"""
    src_lf = "def f(a: int=1) -> int:\n    # comment\n    return a + 1\n"
    src_crlf = "def f(a: int = 1) -> int:\r\n\r\n    return a + 1\r\n"
    assert guard._extract_symbol(src_lf, "f", "body", "<lf>") == \
        guard._extract_symbol(src_crlf.replace("\r\n", "\n"), "f", "body", "<crlf>")


def test_symbol_digest_changes_when_health_body_is_tampered() -> None:
    """负向：_health 函数体被改 → 摘要必须变化（v1 完全抓不到这一类）。"""
    path = (
        Path(guard.REPO)
        / "tools/sound_sim/s12/acoustic_identity_v015/render_identity_v02.py"
    )
    source = path.read_text(encoding="utf-8")
    clean = guard._extract_symbol(source, "_health", "body", str(path))
    tampered_src = source.replace('"channels": 2', '"channels": 3', 1)
    assert tampered_src != source, "夹具失效：未找到可篡改的锚点"
    tampered = guard._extract_symbol(tampered_src, "_health", "body", str(path))
    assert tampered != clean


def test_symbol_digest_changes_when_loudness_signature_is_tampered() -> None:
    """负向：manage_bundle_loudness 签名被改 → 摘要必须变化。"""
    path = (
        Path(guard.REPO)
        / "tools/sound_sim/s12/acoustic_identity_v015/loudness_manager.py"
    )
    source = path.read_text(encoding="utf-8")
    clean = guard._extract_symbol(
        source, "manage_bundle_loudness", "signature", str(path)
    )
    tampered_src = source.replace(
        "target_lufs: float = -18.0", "target_lufs: float = -16.0", 1
    )
    assert tampered_src != source, "夹具失效：未找到可篡改的锚点"
    tampered = guard._extract_symbol(
        tampered_src, "manage_bundle_loudness", "signature", str(path)
    )
    assert tampered != clean


def test_signature_mode_ignores_body_changes() -> None:
    """签名模式只冻结 API：函数体重构不应触发 FAIL。"""
    base = "def f(a: int) -> int:\n    return a\n"
    rewritten = "def f(a: int) -> int:\n    b = a\n    return b\n"
    assert guard._extract_symbol(base, "f", "signature", "<a>") == \
        guard._extract_symbol(rewritten, "f", "signature", "<b>")
    assert guard._extract_symbol(base, "f", "body", "<a>") != \
        guard._extract_symbol(rewritten, "f", "body", "<b>")


def test_missing_symbol_raises() -> None:
    with pytest.raises(RuntimeError, match="找不到冻结符号"):
        guard._extract_symbol("x = 1\n", "nope", "body", "<mem>")


# --------------------------------------------------------------------------
# 基线自洽
# --------------------------------------------------------------------------

def test_baseline_constants_are_populated() -> None:
    assert guard.BASE == "ea586bc53d8e115324db586035823cbc4f605c8c"
    assert len(guard.FROZEN_MANIFEST_SHA256) == 64
    assert len(guard.FROZEN_SYMBOL_SHA256) == 64
    assert "PLACEHOLDER" not in guard.FROZEN_MANIFEST_SHA256
    assert "PLACEHOLDER" not in guard.FROZEN_SYMBOL_SHA256


def test_guard_reports_pass_on_clean_tree() -> None:
    assert guard.main() == 0
