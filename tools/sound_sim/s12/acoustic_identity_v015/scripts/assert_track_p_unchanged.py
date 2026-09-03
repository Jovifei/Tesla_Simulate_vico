"""Track-P 冻结边界断言（S12 Track-P Baseline v3）。

基线：`S12 Track-P Baseline v3`，BASE = ea586bc。
（v3 固化 main 与声学分支的统一合并结果，并新增 HY3 恢复的 PTR 试听适配器；
  详见 tools/sound_sim/s12/acoustic_identity_v015/docs/S12_TrackP_Baseline_v3.md。）

设计目标（相对 v1 的改进）：
  v1 只做 `git diff --name-only BASE` 的路径子串匹配，有两个致命弱点：
    1. BASE commit 对象一旦丢失，整个断言失效且无法重建（已实际发生）。
    2. 函数级冻结项（manage_bundle_loudness 签名 / render_identity_v02._health
       函数体）所在文件的路径不含冻结子串，永远抓不到——v1 自己把这一点
       记为「已知限制」，交给人工 review。
  v2 改为 **内容寻址** 断言：把 180 个冻结文件的 (mode, blob-sha, path) 清单
  与 2 个冻结符号的 AST 规范化文本，分别摘要成常量内联在本文件里。
  即使 BASE commit 再次丢失，摘要校验仍然成立；符号级冻结也不再靠人肉。

Track-P 冻结边界：
  路径级（任意匹配的改动路径 → FAIL）：
    - acoustic_demo/                  runtime_ptr_adapter / runtime server /
                                      sound_renderer adapters
    - 路径包含 radiation / fvm / ptr   辐射场 + FVM 求解器 + PTR core
    - 路径包含 matlab                  MATLAB 工具链
    - 路径包含 manage_bundle_loudness  （历史保留；实际由符号级守卫覆盖）
  符号级（AST 规范化后比对摘要）：
    - loudness_manager.manage_bundle_loudness  —— 仅冻结签名/API
    - render_identity_v02._health              —— 冻结整个函数体

用法：
    python assert_track_p_unchanged.py                # 断言，退出码 0/1
    python assert_track_p_unchanged.py --print-baseline
        # 依据当前工作树重新计算并打印基线常量（rebaseline 时使用）
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 基线常量（S12 Track-P Baseline v3）
# --------------------------------------------------------------------------

BASELINE_NAME = "S12 Track-P Baseline v3"

# 本 change 的 base 提交（= assertion baseline SHA）
BASE = "ea586bc53d8e115324db586035823cbc4f605c8c"

# Track P 冻结路径模式（子串匹配，任意命中即 FAIL）
FROZEN_SUBSTRINGS = (
    "acoustic_demo/",          # Track P runtime 适配器
    "radiation",               # 辐射场核心
    "fvm",                     # FVM 求解器
    "ptr",                     # PTR core
    "matlab",                  # MATLAB 工具链
    "manage_bundle_loudness",  # 签名/API（另有符号级守卫）
)

# Track-S 显式豁免：路径**碰巧**命中冻结子串、但按治理归属 Track S 的文件。
# 若不豁免，改动这些文件会产生假 FAIL（v1 埋的地雷：下面这个测试文件是
# Task 3.1 新建的 Track-S 单测，仅因文件名含 "ptr" 就被划进冻结集）。
# 新增条目必须在基线文档 §3.3 里同步登记理由。
TRACK_S_ALLOWLIST = frozenset({
    "tools/sound_sim/s12/acoustic_identity_v015/tests/"
    "test_s12_post_ptr_loudness_compensation.py",
    # Stage-N comparator artifacts are Track-S analysis/evidence.  Their
    # MATLAB path token must not classify them as Track-P source/toolchain.
    "tasks/reports/runtime/s12-stage-n-professional-comparator/matlab_order_validation.json",
    "tasks/reports/runtime/s12-stage-n-professional-comparator/matlab_psychoacoustic_validation.json",
    "tasks/reports/runtime/s12-stage-n-professional-comparator/matlab_shared_psychoacoustic_validation.json",
    "tools/sound_sim/s12/acoustic_comparator/matlab/s12_export_matlab_comparator_result.m",
    "tools/sound_sim/s12/acoustic_comparator/matlab/s12_order_analysis.m",
    "tools/sound_sim/s12/acoustic_comparator/matlab/s12_psychoacoustic_analysis.m",
    "tools/sound_sim/s12/acoustic_comparator/matlab/s12_stage_n_run_order_analysis.m",
    "tools/sound_sim/s12/acoustic_comparator/matlab/s12_stage_n_run_psychoacoustic_analysis.m",
    "tools/sound_sim/s12/acoustic_comparator/matlab/s12_stage_n_run_shared_psychoacoustic_fixture.m",
    "tools/sound_sim/s12/acoustic_identity_v015/stage_n/matlab_inputs.py",
    "tools/sound_sim/s12/acoustic_identity_v015/stage_n/matlab_receipts.py",
    # Stage-Q/R MATLAB psychoacoustic audit is analysis/evidence only; it does
    # not edit or execute the frozen Track-P physical model/toolchain.
    "tools/sound_sim/s12/real_reference/run_r2_matlab_psychoacoustic_audit.m",
})

# 冻结文件清单摘要：sha256 over sorted "mode SP type SP blobsha TAB path" 行。
# 由 --print-baseline 生成；内容寻址，不依赖 BASE commit 对象存活。
FROZEN_MANIFEST_SHA256 = "94281467e14a66780232fb6ae04bd01917a58a3332721967a80c41f4d6217a8a"
FROZEN_MANIFEST_COUNT = 180

# 符号级冻结守卫：(相对仓库根的路径, 符号名, 模式)
#   模式 "signature" 仅冻结签名（参数 + 返回标注）；
#   模式 "body" 冻结整个函数（AST 规范化文本）。
FROZEN_SYMBOLS: tuple[tuple[str, str, str], ...] = (
    (
        "tools/sound_sim/s12/acoustic_identity_v015/loudness_manager.py",
        "manage_bundle_loudness",
        "signature",
    ),
    (
        "tools/sound_sim/s12/acoustic_identity_v015/render_identity_v02.py",
        "_health",
        "body",
    ),
)

FROZEN_SYMBOL_SHA256 = "e1fbda0a64d7232a8c17712a0c63d9ae3e0f95ae9bf9236c55d049b9b5bd9f7d"


# --------------------------------------------------------------------------
# 基础设施
# --------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent


def _repo_root() -> Path:
    """解析仓库根目录。

    以脚本自身所在目录为 cwd 调用 git（而非进程 cwd），否则从仓库外调用
    本脚本时会解析到错误的仓库。
    """
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(_SCRIPT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0 and res.stdout.strip():
        return Path(res.stdout.strip())
    # 回退：仅当 git 不可用时
    return Path(__file__).resolve().parents[4]


REPO = _repo_root()


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(REPO), capture_output=True, text=True,
    )


def _is_frozen(path: str) -> bool:
    """已跟踪路径的冻结判定：整路径子串匹配（保守），扣除 Track-S 豁免。"""
    if path in TRACK_S_ALLOWLIST:
        return False
    return any(tok in path for tok in FROZEN_SUBSTRINGS)


def _is_frozen_untracked(path: str) -> bool:
    """未跟踪路径的冻结判定：只看**目录段**是否命中。

    未跟踪文件不可能修改既有冻结内容，唯一的风险是「往冻结目录里塞新文件」。
    若沿用整路径子串匹配，Track-S 的临时分析脚本（如
    scripts/_analyze_radiation_fidelity.py）会仅因文件名含 "radiation" 被误判。
    """
    if path in TRACK_S_ALLOWLIST:
        return False
    segments = path.split("/")[:-1]  # 去掉文件名，只看目录段
    return any(tok.strip("/") in seg for seg in segments for tok in FROZEN_SUBSTRINGS)


def _sha256_lines(lines: list[str]) -> str:
    payload = "\n".join(lines) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# 摘要计算
# --------------------------------------------------------------------------

def _frozen_manifest(ref: str) -> tuple[list[str], str]:
    """返回 (冻结条目列表, sha256)。

    条目取自 `git ls-tree -r <ref>`，形如 "100644 blob <sha>\t<path>"。
    blob sha 是内容寻址的，且已按 index 归一化（不受工作树 CRLF/LF 影响）。
    """
    res = _git(["ls-tree", "-r", ref])
    if res.returncode != 0:
        raise RuntimeError(f"git ls-tree {ref} 失败: {res.stderr.strip()}")
    entries = []
    for line in res.stdout.splitlines():
        line = line.rstrip("\r")
        if not line:
            continue
        # path 在 TAB 之后
        path = line.split("\t", 1)[1] if "\t" in line else line
        if _is_frozen(path):
            entries.append(line)
    entries.sort()
    return entries, _sha256_lines(entries)


def _extract_symbol(source: str, symbol: str, mode: str, where: str) -> str:
    """从源码中抽取冻结符号的 AST 规范化文本。

    用 ast.unparse 做规范化：注释、空白、行尾、引号风格的差异被消除，
    只有真正的语义改动才会改变摘要——这正是「冻结 API/行为」的语义。
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            if mode == "signature":
                returns = ast.unparse(node.returns) if node.returns else ""
                return f"def {node.name}({ast.unparse(node.args)}) -> {returns}"
            return ast.unparse(node)
    raise RuntimeError(f"在 {where} 中找不到冻结符号 {symbol}")


def _symbol_digest_from_worktree() -> tuple[list[str], str]:
    canon: list[str] = []
    for rel, symbol, mode in FROZEN_SYMBOLS:
        path = REPO / rel
        if not path.is_file():
            raise RuntimeError(f"冻结符号宿主文件缺失: {rel}")
        source = path.read_text(encoding="utf-8")
        canon.append(f"{rel}::{symbol}::{mode}::{_extract_symbol(source, symbol, mode, rel)}")
    return canon, _sha256_lines(canon)


# --------------------------------------------------------------------------
# rebaseline 辅助
# --------------------------------------------------------------------------

def print_baseline() -> int:
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    entries, manifest_sha = _frozen_manifest("HEAD")
    canon, symbol_sha = _symbol_digest_from_worktree()
    print(f"{BASELINE_NAME} —— 依据 HEAD={head} 计算：")
    print(f"  BASE                   = \"{head}\"")
    print(f"  FROZEN_MANIFEST_SHA256 = \"{manifest_sha}\"")
    print(f"  FROZEN_MANIFEST_COUNT  = {len(entries)}")
    print(f"  FROZEN_SYMBOL_SHA256   = \"{symbol_sha}\"")
    print(f"  冻结符号 {len(canon)} 个：")
    for rel, symbol, mode in FROZEN_SYMBOLS:
        print(f"    - {rel}::{symbol} ({mode})")
    return 0


# --------------------------------------------------------------------------
# 断言主流程
# --------------------------------------------------------------------------

def main() -> int:
    failures: list[str] = []

    # 0) BASE commit 是否仍然可解析（v1 就是死在这一步却没有诊断信息）
    base_ok = _git(["cat-file", "-e", f"{BASE}^{{commit}}"]).returncode == 0
    if not base_ok:
        print(f"WARN: BASE {BASE[:7]} 的 git 对象不可解析——"
              f"跳过 diff 类检查，改由内容摘要兜底。")
        print("      若确认基线已失效，请执行 --print-baseline 重新固化常量。")

    changed: list[str] = []
    if base_ok:
        # 1) 仅已提交改动（忽略未跟踪/未暂存文件）
        diff = _git(["diff", "--name-only", BASE])
        if diff.returncode != 0:
            failures.append(f"git diff --name-only 执行失败: {diff.stderr.strip()}")
        else:
            changed = [p.strip() for p in diff.stdout.splitlines() if p.strip()]
            frozen_hits = [p for p in changed if _is_frozen(p)]
            if frozen_hits:
                failures.append(
                    "检测到 Track P 冻结路径被改动（已提交）：\n"
                    + "\n".join(f"    - {p}" for p in frozen_hits)
                )

        # 2) git diff --check 只作用于「自 BASE 以来确实变动的冻结文件」。
        #    绝不把空白检查扩散到整段历史（BASE 是一个很久以前的提交，它与
        #    HEAD 之间隔着上千个非冻结文件的合法改动；对它们跑 diff --check
        #    会把历史里早已存在的 CRLF 误报成当前越界）。
        #    冻结文件是否变化，本就由步骤 4 的内容寻址清单摘要严格覆盖；
        #    这里只做一次「若真动了冻结文件则其 diff 必须无空白错误」的兜底。
        if frozen_hits:
            check = _git(["diff", "--check", BASE, "--", *frozen_hits])
            if check.returncode != 0:
                failures.append("冻结文件 diff --check 发现空白错误：\n"
                                + (check.stdout or check.stderr))

    # 3) 工作树/索引侧的冻结守卫（v1 完全没覆盖：未提交的冻结改动会漏网）
    status = _git(["status", "--porcelain"])
    if status.returncode != 0:
        failures.append(f"git status 执行失败: {status.stderr.strip()}")
    else:
        dirty_frozen = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            code, path = line[:2], line[3:].strip().strip('"')
            predicate = _is_frozen_untracked if code == "??" else _is_frozen
            # 处理重命名 "old -> new"
            for part in path.split(" -> "):
                if predicate(part):
                    dirty_frozen.append(f"{code} {part}")
        if dirty_frozen:
            failures.append(
                "检测到 Track P 冻结路径在工作树/索引中被改动：\n"
                + "\n".join(f"    - {p}" for p in dirty_frozen)
            )

    # 4) 冻结文件清单摘要（内容寻址，BASE 丢失也能校验）
    try:
        entries, manifest_sha = _frozen_manifest("HEAD")
        if len(entries) != FROZEN_MANIFEST_COUNT:
            failures.append(
                f"冻结文件数量变化：期望 {FROZEN_MANIFEST_COUNT}，实际 {len(entries)}"
                "（新增/删除冻结文件同样属于越界）"
            )
        if manifest_sha != FROZEN_MANIFEST_SHA256:
            failures.append(
                "冻结文件清单摘要不匹配：\n"
                f"    期望 {FROZEN_MANIFEST_SHA256}\n"
                f"    实际 {manifest_sha}"
            )
    except RuntimeError as exc:
        failures.append(str(exc))
        entries = []

    # 5) 符号级冻结守卫
    try:
        _, symbol_sha = _symbol_digest_from_worktree()
        if symbol_sha != FROZEN_SYMBOL_SHA256:
            failures.append(
                "Track P 冻结符号摘要不匹配（manage_bundle_loudness 签名 / _health 函数体）：\n"
                f"    期望 {FROZEN_SYMBOL_SHA256}\n"
                f"    实际 {symbol_sha}"
            )
    except (RuntimeError, SyntaxError) as exc:
        failures.append(f"冻结符号校验失败: {exc}")

    if failures:
        print(f"FAIL: Track-P 冻结边界被破坏（基线 {BASELINE_NAME} / {BASE[:7]}）")
        for item in failures:
            print(f"  * {item}")
        return 1

    print(f"OK: Track P 未改动（基线 {BASELINE_NAME} / BASE {BASE[:7]}）")
    print(f"  repo root         : {REPO}")
    print(f"  冻结文件          : {len(entries)} 个，清单摘要匹配")
    print(f"  冻结符号          : {len(FROZEN_SYMBOLS)} 个，摘要匹配")
    print(f"  工作树/索引       : 无冻结路径改动")
    if base_ok:
        frozen_changed = [p for p in changed if _is_frozen(p)]
        if frozen_changed:
            print(f"  相对 BASE 冻结路径改动: {len(frozen_changed)} 个（diff --check 干净）")
            for p in frozen_changed:
                print(f"    ~ {p}")
        else:
            print(f"  相对 BASE 冻结路径改动: 0 个（冻结文件仅由内容寻址清单严格守护）")
        print(f"  相对 BASE 非冻结改动   : {len(changed)} 个文件（属 Track S / 各 stage；"
              f"空白卫生由 CI repository_checks 的 merge-base diff --check 负责）")
    return 0


if __name__ == "__main__":
    if "--print-baseline" in sys.argv:
        sys.exit(print_baseline())
    sys.exit(main())
