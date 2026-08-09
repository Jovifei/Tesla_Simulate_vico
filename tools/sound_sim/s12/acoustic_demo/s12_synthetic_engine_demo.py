"""Render deterministic, offline S12 synthetic engine audition cases."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from s12_acoustic_audition import AuditionResult, render_audition
from s12_engine_source import (
    EngineSourceConfig,
    synthesize_four_stroke,
    synthesize_four_stroke_profile,
)
from s12_ptr_network import PtrNetworkConfig, load_radiation_package, run_ptr_network


@dataclass(frozen=True)
class DemoResult:
    cases: dict[str, AuditionResult]
    total_clipping_count: int
    manifest_path: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(output_dir: Path) -> Path:
    manifest_path = output_dir / "sha256-manifest.json"
    files = sorted(
        path for path in output_dir.rglob("*") if path.is_file() and path != manifest_path
    )
    payload = {
        str(path.relative_to(output_dir)).replace("\\", "/"): _sha256(path) for path in files
    }
    manifest_path.write_text(
        json.dumps(
            {"files": payload, "schema": "s12_synthetic_engine_demo_manifest.v1"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def run_demo(output_dir: Path) -> DemoResult:
    """Render fixed, ramp, and load-step synthetic cases through the PTR."""
    output_dir.mkdir(parents=True, exist_ok=True)
    config = PtrNetworkConfig()
    package = load_radiation_package(config.package_path)
    cases = {
        "fixed-4000-rpm-load-025": synthesize_four_stroke(EngineSourceConfig(4000.0, 0.25), 0.05),
        "fixed-4000-rpm-load-060": synthesize_four_stroke(EngineSourceConfig(4000.0, 0.60), 0.05),
        "fixed-4000-rpm-load-100": synthesize_four_stroke(EngineSourceConfig(4000.0, 1.0), 0.05),
        "rpm-ramp-2000-to-6000": synthesize_four_stroke_profile(
            (EngineSourceConfig(2000.0, 0.25), EngineSourceConfig(6000.0, 1.0)), 4800, "linear"
        ),
        "load-step-025-to-100": synthesize_four_stroke_profile(
            (EngineSourceConfig(4000.0, 0.25), EngineSourceConfig(4000.0, 1.0)), 4800, "step"
        ),
    }
    results = {
        name: render_audition(run_ptr_network(trace, config), output_dir / name)
        for name, trace in cases.items()
    }
    demo_config = {
        "schema": "s12_synthetic_engine_demo.v1",
        "labels": ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"],
        "case_sources": {
            name: {"case_id": trace.case_id, "provenance": list(trace.provenance)}
            for name, trace in cases.items()
        },
        "ptr_config": {**asdict(config), "package_path": str(config.package_path.name)},
        "radiation_package": {
            "sha256": package.sha256,
            "source_commit": package.source_commit,
            "reference_plane": package.reference_plane,
        },
    }
    (output_dir / "demo-config.json").write_text(
        json.dumps(demo_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path = _write_manifest(output_dir)
    return DemoResult(
        results, sum(result.clipping_count for result in results.values()), manifest_path
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_demo(args.output)
    print(f"cases={len(result.cases)} clipping={result.total_clipping_count}")


if __name__ == "__main__":
    main()
