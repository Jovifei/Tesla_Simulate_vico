"""Remove public-manifest leakage from an already generated Stage-G package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(output_root: str | Path) -> None:
    root = Path(output_root).resolve()
    listener = root / "listener"
    manifest_path = listener / "listener_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("vehicles", None)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (listener / "README.md").write_text(
        "Anonymous Stage-G v4 two-round listening package. Fill blind_responses.csv, "
        "ab_responses.csv, and playback_context.json after listening. Do not inspect the private answer files.\n",
        encoding="utf-8",
        newline="\n",
    )

    listener_zip = root / "S12_Stage_G_Listener_Package.zip"
    with zipfile.ZipFile(listener_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(listener.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"listener/{path.relative_to(listener).as_posix()}")
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())

    sums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            sums[path.relative_to(root).as_posix()] = _sha256(path)
    (root / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {path}\n" for path, digest in sorted(sums.items())),
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    sanitize(args.output_root)


if __name__ == "__main__":
    main()
