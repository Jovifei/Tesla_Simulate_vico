"""Package the last Stage-AD iteration into a simple monitor-WAV audition folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_audition_package(loop_root: str | Path, output_root: str | Path) -> dict[str, Any]:
    loop_root = Path(loop_root)
    output_root = Path(output_root)
    summary_path = loop_root / "closed_loop_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    iterations = list(summary.get("iterations") or [])
    if not iterations:
        raise ValueError("closed-loop summary contains no completed iterations")

    final_iteration = iterations[-1]
    iteration_manifest_path = loop_root / final_iteration["audition_manifest"]
    iteration_manifest = json.loads(iteration_manifest_path.read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    for index, row in enumerate(iteration_manifest.get("scenes") or [], start=1):
        source = iteration_manifest_path.parent / row["monitor_wav"]
        if not source.is_file():
            raise FileNotFoundError(source)
        scene = str(row.get("scene") or row.get("output_scene") or f"scene_{index:02d}")
        destination = output_root / f"{index:02d}_{scene}.wav"
        shutil.copy2(source, destination)
        files.append({
            "index": index,
            "scene": scene,
            "file": destination.name,
            "sha256": _sha256(destination),
        })

    package = {
        "schema": "s12.stage_ad.audition_package.v1",
        "source_loop_root": str(loop_root),
        "source_summary_sha256": _sha256(summary_path),
        "final_iteration": final_iteration.get("iteration"),
        "final_objective": summary.get("final_objective"),
        "final_absolute_reference_distance": summary.get("final_absolute_reference_distance"),
        "final_config_sha256": summary.get("final_config_sha256"),
        "files": files,
        "blind": False,
        "official_v3_modified": False,
        "instruction": "Listen to these monitor WAVs and report scene-level realism/identity problems. Do not treat this package as Profile Freeze.",
    }
    (output_root / "audition_manifest.json").write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    package = build_audition_package(args.loop_root, args.output_root)
    print(json.dumps(package, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
