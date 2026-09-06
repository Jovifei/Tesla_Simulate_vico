"""Regenerate the *existing* Stage-AD A/B workbench with Stage-AF fit results.

No new dashboard/backend is implemented here.  The module deliberately imports
``stage_ad.build_unified_dashboards`` and replaces only its EngineAcoustics
constructor with the tuned adapter, preserving the proven UI/service workflow.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .physical_closed_loop import TunableEngineAcoustics

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")


def _load_fit(path: Path | None) -> dict[str, float]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("overrides", payload)
    return {str(k): float(v) for k, v in source.items()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the existing 4-car A/B dashboards using Stage-AF tuned EngineAcoustics")
    parser.add_argument("--fit-root", type=Path, help="root containing <vehicle>/final_r3_diagnostic_fit.json")
    parser.add_argument("--output-root", type=Path, default=Path(r"E:\Tesla_speed\review_packages"))
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args(argv)

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
        path = args.fit_root / vehicle / "final_r3_diagnostic_fit.json" if args.fit_root else None
        fit_by_vehicle[vehicle] = _load_fit(path)

    class _Factory:
        def __new__(cls, vehicle_type: str = "ferrari_458", sr: int = 48000) -> TunableEngineAcoustics:
            return TunableEngineAcoustics(vehicle_type, sr=sr, overrides=fit_by_vehicle.get(vehicle_type, {}), seed=args.seed)

    dashboards.EngineAcoustics = _Factory

    # Keep the proven directory names/ports expected by serve_dashboards.py, but
    # make the root portable/configurable.
    dir_names = {
        "hellcat": "s12-stage-ad-hellcat-closed-loop-v1",
        "ferrari_458": "s12-stage-ad-ferrari-458-closed-loop-v1",
        "lfa": "s12-stage-ad-lfa-closed-loop-v1",
        "gtr_r35": "s12-stage-ad-gtr-r35-closed-loop-v1",
    }
    for vehicle, cfg in dashboards.VEHICLE_CONFIGS.items():
        cfg["dir"] = args.output_root / dir_names[vehicle]
        cfg["dir"].mkdir(parents=True, exist_ok=True)
        dashboards.render_vehicle_audio(vehicle, cfg)
        dashboards.build_dashboard(vehicle, cfg)
        fit_path = args.fit_root / vehicle / "final_r3_diagnostic_fit.json" if args.fit_root else None
        receipt: dict[str, Any] = {
            "schema": "s12.stage_af.dashboard_binding.v1",
            "vehicle": vehicle,
            "renderer": "stage_ad.engine_sim_acoustics.EngineAcoustics",
            "fit_path": str(fit_path) if fit_path and fit_path.is_file() else None,
            "overrides": fit_by_vehicle[vehicle],
            "seed": args.seed,
        }
        (cfg["dir"] / "stage_af_binding.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
