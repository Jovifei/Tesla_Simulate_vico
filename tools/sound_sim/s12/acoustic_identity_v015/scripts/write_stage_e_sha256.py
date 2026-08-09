from __future__ import annotations
import hashlib
from pathlib import Path
import sys

def main():
    root = Path(sys.argv[1]).resolve()
    lines=[]
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
if __name__ == "__main__": main()
