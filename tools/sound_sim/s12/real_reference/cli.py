"""Command line entry point for the Stage Q reference audit."""
from __future__ import annotations

import argparse
from pathlib import Path

from .inventory import build_inventory, write_stage_q_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="建立不复制原始音频的 S12 Stage Q 真实参考证据库")
    parser.add_argument(
        "--media-root",
        type=Path,
        default=Path(r"E:\Claude_allow\Download\tesla-sound-research"),
        help="外部原始媒体目录（不会复制到 Git）",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("tasks/reports/runtime/s12-stage-q-real-reference"),
        help="Stage Q 报告输出目录",
    )
    args = parser.parse_args(argv)
    inventory = build_inventory(args.media_root)
    outputs = write_stage_q_outputs(inventory, args.out_dir)
    print(f"status={inventory['status']}")
    print(f"stop_state={inventory['stop_state']}")
    print(f"recordings={len(inventory['recordings'])}")
    print(f"r1_eligible={sum(1 for row in inventory['recordings'] if row['evidence']['r1_eligible'])}")
    print(f"report={outputs['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
