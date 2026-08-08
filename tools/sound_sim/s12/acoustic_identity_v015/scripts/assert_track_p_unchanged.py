# 断言本 change 相对 base 301fed4 仅改动 Track S；git diff --check 必须干净。
#
# 这是 S12 "deep realism" 变更中 Group 2 的收尾 guardrail：确保整次变更
# 严格遵守 "Track P 冻结" 硬约束。任何冻结路径出现在相对 base 的已提交
# diff 中，脚本即以退出码 1 失败。
#
# Track P 冻结边界（任意匹配的改动路径 → FAIL）：
#   - acoustic_demo/                 (runtime_ptr_adapter / runtime server /
#                                      sound_renderer adapters —— Track P)
#   - 路径包含 radiation / fvm / ptr  (PTR core)
#   - 路径包含 matlab                (MATLAB 工具链)
#   - 路径包含 manage_bundle_loudness (签名/API —— Track P)
#
# 已知限制：render_identity_v02._health 函数体亦属 Track P，但 diff 名级别
# 无法精确校验函数体；其完整性由人工 / review 检查（见任务 2.5 报告）。
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 本 change 的 base 提交
BASE = "301fed4c279f0c132ac5e0f858827ab81be31414"

# Track P 冻结路径模式（子串匹配，任意命中即 FAIL）
FROZEN_SUBSTRINGS = (
    "acoustic_demo/",        # Track P runtime 适配器
    "radiation",             # 辐射场核心
    "fvm",                   # FVM 求解器
    "ptr",                   # PTR core
    "matlab",                # MATLAB 工具链
    "manage_bundle_loudness",  # 签名/API
)


def _repo_root() -> Path:
    """稳健地解析仓库根目录。

    parents[4] 依赖脚本实际深度的假设并不可靠（本脚本位于 scripts/ 下，
    parents[4] 实际等于 tools），故优先使用 git rev-parse --show-toplevel。
    """
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
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
    return any(tok in path for tok in FROZEN_SUBSTRINGS)


def main() -> int:
    # 1) 仅已提交改动（git diff --name-only BASE 忽略未跟踪/未暂存文件）
    diff = _git(["diff", "--name-only", BASE])
    if diff.returncode != 0:
        print("FAIL: git diff --name-only 执行失败")
        print(diff.stderr)
        return 1
    changed = [p.strip() for p in diff.stdout.splitlines() if p.strip()]

    # 2) git diff --check 必须干净（无空白错误）
    check = _git(["diff", "--check", BASE])
    if check.returncode != 0:
        print("FAIL: git diff --check 发现空白错误：")
        print(check.stdout or check.stderr)
        return 1

    # 3) 检查是否存在 Track P 冻结路径
    frozen_hits = [p for p in changed if _is_frozen(p)]
    if frozen_hits:
        print("FAIL: 检测到 Track P 冻结路径被改动：")
        for p in frozen_hits:
            print(f"  - {p}")
        return 1

    print(f"OK: 已提交改动 {len(changed)} 个文件，均属 Track S；"
          f"Track P 未改动；git diff --check 干净")
    print(f"  repo root: {REPO}")
    for p in changed:
        print(f"  ~ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
