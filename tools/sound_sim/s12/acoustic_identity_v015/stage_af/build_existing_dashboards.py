"""Regenerate the *existing* Stage-AD A/B workbench with Stage-AF fit results.

No new dashboard/backend is implemented here. The module deliberately imports
``stage_ad.build_unified_dashboards`` and replaces only its EngineAcoustics
constructor with the tuned adapter, preserving the proven UI/service workflow.

Because generated review packages are no longer committed to Git, this adapter
also copies already-existing governed ``ref_*.wav`` files into the exact
``web_audio`` locations expected by the original dashboard generator. It never
downloads or invents reference audio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .physical_closed_loop import TunableEngineAcoustics

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
DIR_NAMES = {
    "hellcat": "s12-stage-ad-hellcat-closed-loop-v1",
    "ferrari_458": "s12-stage-ad-ferrari-458-closed-loop-v1",
    "lfa": "s12-stage-ad-lfa-closed-loop-v1",
    "gtr_r35": "s12-stage-ad-gtr-r35-closed-loop-v1",
}


def _load_fit(path: Path | None) -> dict[str, float]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("overrides", payload)
    return {str(key): float(value) for key, value in source.items()}


def _reference_candidates(root: Path, vehicle: str, filename: str) -> tuple[Path, ...]:
    package = DIR_NAMES[vehicle]
    return (
        root / vehicle / filename,
        root / vehicle / "web_audio" / filename,
        root / package / filename,
        root / package / "web_audio" / filename,
    )


def _bind_references(
    vehicle: str,
    cfg: dict[str, Any],
    reference_root: Path,
) -> dict[str, dict[str, str]]:
    """Copy known reference bytes into the original dashboard's web_audio dir.

    Existing destination references are preserved. Missing references remain
    missing and the original workbench will display them as unavailable.
    """
    web_dir = Path(cfg["dir"]) / "web_audio"
    web_dir.mkdir(parents=True, exist_ok=True)
    filenames = sorted(
        {
            str(scene.get("ref_file"))
            for scene in cfg["scenes"]
            if scene.get("ref_file")
        }
    )
    bound: dict[str, dict[str, str]] = {}
    for filename in filenames:
        destination = web_dir / filename
        source: Path | None = destination if destination.is_file() else None
        if source is None:
            for candidate in _reference_candidates(reference_root, vehicle, filename):
                if candidate.is_file() and candidate.resolve() != destination.resolve():
                    shutil.copy2(candidate, destination)
                    source = candidate
                    break
        if destination.is_file():
            bound[filename] = {
                "source": str(source or destination),
                "destination": str(destination),
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
    return bound


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the existing 4-car A/B dashboards using Stage-AF tuned "
            "EngineAcoustics"
        )
    )
    parser.add_argument(
        "--fit-root",
        type=Path,
        help="root containing <vehicle>/final_r3_diagnostic_fit.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"E:\Tesla_speed\review_packages"),
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        help=(
            "existing governed reference root; defaults to --output-root. "
            "No network download is performed"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args(argv)
    reference_root = args.reference_root or args.output_root

    stage_ad_dir = Path(__file__).resolve().parents[1] / "stage_ad"
    sys.path.insert(0, str(stage_ad_dir))
    try:
        from ..stage_ad import build_unified_dashboards as dashboards
    finally:
        if sys.path and sys.path[0] == str(stage_ad_dir):
            sys.path.pop(0)

    # Eliminate the old absolute-worktree template dependency while preserving
    # the exact same template and dashboard generator.
    dashboards.TEMPLATE_PATH = stage_ad_dir / "audition_dashboard_template.html"

    fit_by_vehicle: dict[str, dict[str, float]] = {}
    for vehicle in VEHICLES:
        path = (
            args.fit_root / vehicle / "final_r3_diagnostic_fit.json"
            if args.fit_root
            else None
        )
        fit_by_vehicle[vehicle] = _load_fit(path)

    class _Factory:
        def __new__(
            cls,
            vehicle_type: str = "ferrari_458",
            sr: int = 48000,
        ) -> TunableEngineAcoustics:
            return TunableEngineAcoustics(
                vehicle_type,
                sr=sr,
                overrides=fit_by_vehicle.get(vehicle_type, {}),
                seed=args.seed,
            )

    dashboards.EngineAcoustics = _Factory

    # Keep the proven directory names/ports expected by serve_dashboards.py.
    for vehicle, cfg in dashboards.VEHICLE_CONFIGS.items():
        cfg["dir"] = args.output_root / DIR_NAMES[vehicle]
        cfg["dir"].mkdir(parents=True, exist_ok=True)

        # The original builder assumes reference files are already present in
        # web_audio. Stage AF explicitly binds existing governed bytes before it
        # calls the original rendering/dashboard functions.
        references = _bind_references(vehicle, cfg, reference_root)

        dashboards.render_vehicle_audio(vehicle, cfg)
        dashboards.build_dashboard(vehicle, cfg)

        fit_path = (
            args.fit_root / vehicle / "final_r3_diagnostic_fit.json"
            if args.fit_root
            else None
        )
        receipt: dict[str, Any] = {
            "schema": "s12.stage_af.dashboard_binding.v2",
            "vehicle": vehicle,
            "renderer": "stage_ad.engine_sim_acoustics.EngineAcoustics",
            "fit_path": str(fit_path) if fit_path and fit_path.is_file() else None,
            "overrides": fit_by_vehicle[vehicle],
            "seed": args.seed,
            "reference_root": str(reference_root),
            "references": references,
            "reference_policy": "EXISTING_GOVERNED_BYTES_ONLY_NO_NETWORK_DOWNLOAD",
        }
        (cfg["dir"] / "stage_af_binding.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
