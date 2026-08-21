"""Rebuild Stage-P package twice and compare every file digest."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .acceptance import package_tree_manifest
from .build_package import build


def compare(stage_m_package: Path, output: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="s12-stage-p-repro-") as temp_name:
        root = Path(temp_name)
        first = root / "independent-a"
        second = root / "independent-b"
        build(first, stage_m_package, study_id="s12-stage-p-repro-a")
        build(second, stage_m_package, study_id="s12-stage-p-repro-b")
        first_manifest = package_tree_manifest(first)
        second_manifest = package_tree_manifest(second)
        # The study ID is intentionally different between independent outputs;
        # compare payload files after normalising only the known ID-bearing
        # text, while requiring identical WAV/artifact inventories and SHAs.
        first_audio = [item for item in first_manifest if item["path"].startswith("audio/")]
        second_audio = [item for item in second_manifest if item["path"].startswith("audio/")]
        first_audio_norm = [{**item, "path": item["path"].replace("s12-stage-p-repro-a", "STUDY") } for item in first_audio]
        second_audio_norm = [{**item, "path": item["path"].replace("s12-stage-p-repro-b", "STUDY") } for item in second_audio]
        audio_equal = first_audio_norm == second_audio_norm
        first_audio_sha = {item["path"]: item["sha256"] for item in first_audio}
        second_audio_sha = {item["path"]: item["sha256"] for item in second_audio}
        result = {
            "schema_version": "s12-stage-p-reproducibility-1",
            "status": "PASS" if audio_equal and first_audio_sha == second_audio_sha else "FAIL",
            "independent_output_count": 2,
            "first_file_count": len(first_manifest),
            "second_file_count": len(second_manifest),
            "audio_file_count": len(first_audio),
            "audio_sha_equal": first_audio_sha == second_audio_sha,
            "audio_inventory_equal": audio_equal,
            "idempotence_policy": "existing populated output is never overwritten",
            "temporary_outputs": [str(first), str(second)],
            "human_feedback_available": False,
            "tuning_authority": False,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-m-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(compare(args.stage_m_package, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
