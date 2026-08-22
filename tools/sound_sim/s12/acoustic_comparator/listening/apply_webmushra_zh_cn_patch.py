"""Apply the S12 Chinese UI overlay to one external webMUSHRA checkout."""
from __future__ import annotations

import argparse
from pathlib import Path

from .webmushra_export import apply_chinese_webmushra_patch


def main() -> int:
    parser = argparse.ArgumentParser(description="为外部 webMUSHRA checkout 应用 S12 中文界面覆盖")
    parser.add_argument("--checkout", type=Path, required=True, help="官方 webMUSHRA checkout 目录")
    parser.add_argument("--patch", type=Path, required=True, help="导出包中的 webmushra_zh_cn_nls.js")
    arguments = parser.parse_args()
    result = apply_chinese_webmushra_patch(arguments.checkout, arguments.patch)
    print(f"已写入中文 NLS：{result['nls_path']}")
    print("index.html 中文脚本标签：" + ("已插入" if result["index_updated"] else "已存在"))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
