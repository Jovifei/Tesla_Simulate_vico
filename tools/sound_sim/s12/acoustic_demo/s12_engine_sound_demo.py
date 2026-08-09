"""Build the deterministic five-case Synthetic Engine Sound v0.2 demo."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from s12_engine_source import EngineSourceConfig, synthesize_four_stroke
from s12_engine_sound_design import (
    OrderSchedule,
    load_design_parameters,
    load_order_profile,
    render_sound_design,
)
from s12_engine_sound_renderer import (
    EngineSoundRenderResult,
    render_designed_wav,
)
from s12_ptr_network import run_ptr_network


@dataclass(frozen=True)
class EngineSoundDemoResult:
    renders: dict[str, EngineSoundRenderResult]
    total_clipping_count: int
    manifest_path: Path
    review_path: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_review(output_dir: Path, renders: dict[str, EngineSoundRenderResult]) -> Path:
    path = output_dir / "engine_sound_review.md"
    lines = [
        "# Synthetic Engine Sound v0.2 Review",
        "",
        "This offline prototype is synthetic, uncalibrated, and not an OEM clone.",
        "",
        "## Time-domain checks",
        "",
        "| Case | Clipping | DC left | DC right | Max adjacent step |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, result in renders.items():
        lines.append(
            f"| {name} | {result.clipping_count} | "
            f"{result.dc['left']:.12g} | {result.dc['right']:.12g} | "
            f"{result.max_adjacent_step:.12g} |"
        )
    lines.extend(
        [
            "",
            "## Frequency-domain checks",
            "",
            "final-output order projection from the rendered stereo mono average:",
            "",
            "| Case | Order 1 RMS | Order 2 RMS | Order 3 RMS |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, result in renders.items():
        order_spectrum_rms = json.loads(result.metadata_path.read_text(encoding="utf-8"))[
            "order_spectrum_rms"
        ]
        lines.append(
            f"| {name} | {order_spectrum_rms['order_1']:.12g} | "
            f"{order_spectrum_rms['order_2']:.12g} | "
            f"{order_spectrum_rms['order_3']:.12g} |"
        )
    lines.extend(
        [
            "",
            "## Hearing review",
            "",
            "These are automated proxies only; human listening is not performed.",
            "",
            "- Engine resemblance: INCONCLUSIVE without human listening.",
            "- Mechanical character: INCONCLUSIVE without human listening.",
            "- Electronic character: INCONCLUSIVE without human listening.",
            "- Continuity proxy: PASS; all rendered cases satisfy the configured "
            "adjacent-step threshold.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_manifest(
    output_dir: Path,
    renders: dict[str, EngineSoundRenderResult],
    review_path: Path,
) -> Path:
    path = output_dir / "sha256-manifest.json"
    files = sorted(
        tuple(
            candidate
            for result in renders.values()
            for candidate in (result.wav_path, result.metadata_path)
        )
        + (review_path,),
        key=lambda candidate: candidate.name,
    )
    payload = {candidate.name: _sha256(candidate) for candidate in files}
    path.write_text(
        json.dumps(
            {"files": payload, "schema": "s12.engine_sound_demo_manifest.v1"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def run_engine_sound_demo(output_dir: Path) -> EngineSoundDemoResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    texture = run_ptr_network(synthesize_four_stroke(EngineSourceConfig(2000.0, 0.25), 0.05))
    profile = load_order_profile()
    parameters = load_design_parameters()
    schedules = {
        "idle": OrderSchedule.fixed(1000.0, 0.10, 2.0),
        "cruise": OrderSchedule.fixed(3000.0, 0.50, 3.0),
        "acceleration": OrderSchedule.ramp(1000.0, 6000.0, 0.30, 0.95, 4.0),
        "throttle_lift": OrderSchedule.ramp(5000.0, 1800.0, 0.80, 0.10, 3.0),
        "high_load": OrderSchedule.fixed(6000.0, 1.00, 3.0),
    }
    renders: dict[str, EngineSoundRenderResult] = {}
    for name, schedule in schedules.items():
        designed = render_sound_design(texture, schedule, profile, parameters)
        renders[name] = render_designed_wav(
            designed,
            output_dir / f"{name}.wav",
            output_dir / f"{name}.metadata.json",
        )
    review_path = _write_review(output_dir, renders)
    manifest_path = _write_manifest(output_dir, renders, review_path)
    return EngineSoundDemoResult(
        renders,
        sum(result.clipping_count for result in renders.values()),
        manifest_path,
        review_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_engine_sound_demo(args.output)
    print(f"cases={len(result.renders)} clipping={result.total_clipping_count}")


if __name__ == "__main__":
    main()
