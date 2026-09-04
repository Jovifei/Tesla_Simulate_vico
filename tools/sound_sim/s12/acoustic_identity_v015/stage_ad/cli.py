"""CLI for Stage AD reference-driven closed-loop engineering calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..stage_x.reference_caseset import build_reference_caseset_from_registry
from ..stage_y.package import _fitted_config
from .aa_c3_search import AA_C3_SOURCE_CAUSAL_PARAMETERS, run_aa_c3_search
from .closed_loop import ClosedLoopPolicy, run_closed_loop


def _load_json(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--caseset-json", type=Path)
    source.add_argument("--reference-registry", type=Path)
    parser.add_argument("--vehicle-id", default="hellcat_v1")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--baseline",
        choices=("aa-c3", "stage-x"),
        default="aa-c3",
        help="AA-C3 preserves the current candidate processing; stage-x runs the generic P3 search.",
    )
    parser.add_argument(
        "--base-config-json",
        type=Path,
        help="start this loop from a prior Stage-AD final_config.json (useful for body→blower→afterfire staging)",
    )
    parser.add_argument("--architecture", default="P3", help="used only with --baseline stage-x")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--coarse-count", type=int, default=48)
    parser.add_argument("--refine-count", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--domain-shrink", type=float, default=0.55)
    parser.add_argument("--minimum-delta-fraction", type=float, default=0.20)
    parser.add_argument("--minimum-reference-distance-gain", type=float, default=0.005)
    parser.add_argument("--plateau-patience", type=int, default=1)
    parser.add_argument(
        "--target-reference-distance",
        type=float,
        default=None,
        help="optional absolute fixed-scale reference-distance stop threshold",
    )
    parser.add_argument(
        "--generic-iteration-target",
        type=float,
        default=0.15,
        help="fallback per-iteration improvement target for --baseline stage-x only",
    )
    parser.add_argument("--human-feedback-json", type=Path)
    parser.add_argument("--allow-parameter", action="append", default=None)
    args = parser.parse_args(argv)

    if args.caseset_json is not None:
        caseset = json.loads(args.caseset_json.read_text(encoding="utf-8"))
    else:
        caseset = build_reference_caseset_from_registry(args.vehicle_id, args.reference_registry)
        args.output_root.mkdir(parents=True, exist_ok=True)
        (args.output_root / "reference_caseset.json").write_text(
            json.dumps(caseset, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    policy = ClosedLoopPolicy(
        max_iterations=args.iterations,
        coarse_count=args.coarse_count,
        refine_count=args.refine_count,
        seed=args.seed,
        domain_shrink=args.domain_shrink,
        minimum_delta_fraction=args.minimum_delta_fraction,
        minimum_reference_distance_gain=args.minimum_reference_distance_gain,
        plateau_patience=args.plateau_patience,
        target_reference_distance=args.target_reference_distance,
        generic_iteration_target=args.generic_iteration_target,
    )
    feedback = _load_json(args.human_feedback_json)
    supplied_base_config = _load_json(args.base_config_json)

    if args.baseline == "aa-c3":
        search_fn = run_aa_c3_search
        base_config = supplied_base_config or _fitted_config()
        architecture = "AA-C3"
        allowed_parameters = args.allow_parameter or list(AA_C3_SOURCE_CAUSAL_PARAMETERS)
    else:
        search_fn = None
        base_config = supplied_base_config
        architecture = args.architecture
        allowed_parameters = args.allow_parameter

    kwargs: dict[str, Any] = {}
    if search_fn is not None:
        kwargs["search_fn"] = search_fn
    summary = run_closed_loop(
        args.output_root,
        caseset,
        vehicle_id=args.vehicle_id,
        architecture=architecture,
        policy=policy,
        allowed_parameter_names=allowed_parameters,
        human_feedback=feedback,
        base_config=base_config,
        **kwargs,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
