"""Command line entry point for the Stage Q reference audit."""
from __future__ import annotations

import argparse
from pathlib import Path

from .inventory import DEFAULT_ADDITIONAL_MEDIA_ROOTS, build_inventory, write_stage_q_outputs


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
    parser.add_argument(
        "--additional-media-root",
        type=Path,
        action="append",
        default=None,
        help="额外审计目录；只记录外部音频指针，不复制或分析原始文件（可重复指定）",
    )
    parser.add_argument(
        "--raw-reference-manifest",
        type=Path,
        action="append",
        default=None,
        help="raw_audio_intake.py 生成的外部 R1 manifest；合并到 canonical reference_database_v2（可重复指定）",
    )
    parser.add_argument(
        "--authorized-reference-manifest",
        type=Path,
        action="append",
        default=None,
        help="已审计授权 R2 manifest（只合并元数据指针，不复制音频；可重复指定）",
    )
    args = parser.parse_args(argv)
    additional_roots = DEFAULT_ADDITIONAL_MEDIA_ROOTS if args.additional_media_root is None else tuple(args.additional_media_root)
    inventory = build_inventory(
        args.media_root,
        additional_media_roots=additional_roots,
        raw_reference_manifests=tuple(args.raw_reference_manifest or ()),
        authorized_reference_manifests=tuple(args.authorized_reference_manifest or ()),
    )
    outputs = write_stage_q_outputs(inventory, args.out_dir)
    print(f"status={inventory['status']}")
    print(f"stop_state={inventory['stop_state']}")
    print(f"recordings={len(inventory['recordings'])}")
    print(f"r1_eligible={sum(1 for row in inventory['recordings'] if row['evidence']['r1_eligible'])}")
    print(f"report={outputs['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
