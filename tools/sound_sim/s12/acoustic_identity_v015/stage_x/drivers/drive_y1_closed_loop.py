"""Run the Stage-Y closed-loop engineering remediation.

This driver accepts either the legacy Stage-X media manifest or a canonical
external reference registry. It keeps external audio outside Git, binds Jovi's
validated feedback, searches steady and dynamic scenes, evaluates fail-closed
engineering gates, and publishes PCM24 finalist receipts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import write_json  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x import reference_caseset as rc  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.candidate_search import run_engineering_search  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.engineering_gate import evaluate_engineering_preselection  # noqa: E402

DEFAULT_MANIFEST = (
    REPO_ROOT
    / "tools"
    / "sound_sim"
    / "s12"
    / "acoustic_identity_v015"
    / "reference_database"
    / "realism_reference_manifest.json"
)
DEFAULT_FEEDBACK = (
    REPO_ROOT
    / "tools"
    / "sound_sim"
    / "s12"
    / "acoustic_identity_v015"
    / "stage_x"
    / "data"
    / "jovi_guided_feedback_v2.json"
)
DEFAULT_OUTPUT = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-y"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _load_feedback(path: Path, vehicle_id: str) -> dict[str, Any] | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = (payload.get("rows") or {}).get(vehicle_id)
    return dict(row) if isinstance(row, dict) else None


def _build_caseset(args: argparse.Namespace) -> dict[str, Any]:
    confirmations = {}
    if args.vehicle == "rx7_fd" and args.reject_rx7_speech:
        confirmations["rx7_fd"] = (
            "Jovi validated that the legacy reference contains speech, not engine sound"
        )
    if args.registry:
        return rc.build_reference_caseset_from_registry(
            args.vehicle,
            args.registry,
            human_speech_confirmations=confirmations,
        )
    if not args.audio_dir:
        raise ValueError("--audio-dir is required when --registry is not used")
    return rc.build_reference_caseset(
        args.vehicle,
        args.legacy_manifest,
        args.audio_dir,
        human_speech_confirmations=confirmations,
    )


def _reference_audio(caseset: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for case in caseset["cases"]:
        if case["status"] != "BOUND":
            continue
        audio, sample_rate = rc.load_case_segment_audio(
            case,
            target_sample_rate=48000,
        )
        result[case["scenario"]] = {
            "audio": audio,
            "sample_rate": sample_rate,
            "metadata": {
                "source_id": case["source_id"],
                "recording_session_id": case["recording_session_id"],
                "evidence_level": case["evidence_level"],
                "speech_contaminated": case["speech_music_contamination"]["speech_contaminated"],
                "segment_sha256": case["segment_sha256"],
            },
        }
    return result


def _allowed_parameters(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    receipt = json.loads(path.read_text(encoding="utf-8"))
    return [
        item["parameter"]
        for item in receipt.get("results", [])
        if item.get("status") == "PARAMETER_REACHABLE"
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vehicle",
        choices=("hellcat", "ferrari_458", "rx7_fd"),
        default="hellcat",
    )
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--legacy-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--audio-dir", type=Path)
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--reachability", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--architectures",
        nargs="+",
        choices=("P2H", "P3", "P5"),
        default=("P2H", "P3", "P5"),
    )
    parser.add_argument("--coarse", type=int, default=64)
    parser.add_argument("--refine", type=int, default=32)
    parser.add_argument("--seed", type=int, default=8675309)
    parser.add_argument(
        "--reject-rx7-speech",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    caseset = _build_caseset(args)
    references = _reference_audio(caseset)
    feedback = _load_feedback(args.feedback, args.vehicle)
    allowed = _allowed_parameters(args.reachability)

    vehicle_root = args.output / args.vehicle
    vehicle_root.mkdir(parents=True, exist_ok=True)
    write_json(vehicle_root / "reference_caseset.json", _safe(caseset))
    write_json(
        vehicle_root / "feedback_input.json",
        _safe({
            "schema": "s12.stage_y.feedback_input.v1",
            "vehicle_id": args.vehicle,
            "feedback": feedback,
            "source": str(args.feedback),
        }),
    )

    gates: dict[str, Any] = {}
    for index, architecture in enumerate(args.architectures):
        search_root = vehicle_root / architecture
        outcome = run_engineering_search(
            search_root,
            references,
            architecture=architecture,
            coarse_count=args.coarse,
            refine_count=args.refine,
            seed=args.seed + index,
            allowed_parameter_names=allowed,
            human_feedback=feedback,
            independent_reference_count=caseset["independent_recording_session_count"],
        )
        best = outcome["best"] or {}
        gate = evaluate_engineering_preselection(
            best,
            architecture=architecture,
            valid_reference_count=caseset["bound_case_count"],
            independent_reference_count=caseset["independent_recording_session_count"],
            reference_evidence_level=caseset["reference_evidence_level"],
            human_feedback=feedback,
        )
        gate["best_overrides"] = best.get("overrides")
        gate["ranking_objective"] = best.get("objective")
        gate["reference_objective"] = best.get("reference_objective")
        gates[architecture] = _safe(gate)
        write_json(search_root / "preselection_gate.json", _safe(gate))

    ranking = sorted(
        gates,
        key=lambda architecture: (
            gates[architecture].get("ranking_objective")
            if gates[architecture].get("ranking_objective") is not None
            else float("-inf")
        ),
        reverse=True,
    )
    selected = next(
        (
            architecture
            for architecture in ranking
            if gates[architecture]["eligibility"]["selection_eligible"]
        ),
        None,
    )
    summary = {
        "schema": "s12.stage_y.closed_loop_run.v1",
        "vehicle_id": args.vehicle,
        "reference_evidence_level": caseset["reference_evidence_level"],
        "bound_case_count": caseset["bound_case_count"],
        "bound_scenario_count": caseset["bound_scenario_count"],
        "unique_audio_sha_count": caseset["unique_audio_sha_count"],
        "independent_recording_session_count": caseset["independent_recording_session_count"],
        "reference_scenarios": sorted(references),
        "feedback_usable": bool(feedback),
        "gates": gates,
        "architecture_ranking": ranking,
        "selected_engineering_architecture": selected,
        "formal_selection": "FORMAL_R1_REFERENCE_MISSING",
        "wall_seconds": round(time.perf_counter() - started, 3),
        "scope": (
            "engineering diagnostic only; no OEM likeness, Profile Freeze, "
            "or productization claim"
        ),
    }
    write_json(vehicle_root / "stage_y_summary.json", _safe(summary))
    print(json.dumps(_safe(summary), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
