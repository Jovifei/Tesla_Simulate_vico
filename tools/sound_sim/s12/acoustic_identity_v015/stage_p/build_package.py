"""Build a new, non-overwriting Stage-P webMUSHRA review package."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..stage_n.run_stage_n import _study_trials
from ...acoustic_comparator.listening.webmushra_export import export_webmushra_study


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_sha256sums(destination: Path) -> Path:
    """Write a recursive, POSIX-relative checksum ledger without self-hashing."""
    lines = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(destination).as_posix()
        lines.append(f"{_sha256(path)}  {relative}")
    checksum_path = destination / "SHA256SUMS"
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return checksum_path


def build(destination: Path, stage_m_package: Path, *, study_id: str) -> dict[str, object]:
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite populated package: {destination}")
    upstream = {
        "tool": "webMUSHRA",
        "source": "https://github.com/AndreasRoses/webMUSHRA",
        "checkout_policy": "official upstream checkout outside repository",
        "upstream_receipt": "external checkout commit must be recorded by Stage-P evidence",
        "hidden_reference": "synthetic_parent_not_real_reference",
    }
    manifest = export_webmushra_study(
        destination,
        _study_trials(stage_m_package),
        upstream_receipt=upstream,
        study_id=study_id,
    )
    (destination / "STAGE_P_PACKAGE_POLICY.md").write_text(
        "# Stage-P review package policy\n\n"
        "This is a new, non-overwriting, fixture/UAT package. The hidden reference is a "
        "synthetic Stage-K parent, not a real external vehicle recording. Candidate files "
        "are Stage-M artifacts copied into loudness-matched audition files; no vehicle source "
        "or profile is changed by this package. Raw browser exports are not human feedback "
        "until a SHA-bound Jovi submission passes the Stage-O entry gate.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_sha256sums(destination)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--stage-m-package", type=Path, required=True)
    parser.add_argument("--study-id", default="s12-stage-p-system-acceptance-v1")
    args = parser.parse_args(argv)
    manifest = build(args.destination, args.stage_m_package, study_id=args.study_id)
    print(json.dumps({"destination": str(args.destination), "trial_count": len(manifest["trials"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
