"""Drive X5 Hellcat engineering search and preselection (offline, deterministic).

Reads the X4 reachability receipt, builds the scenario-bound R2 reference
pool, runs the two-stage search per architecture and evaluates the
engineering preselection gates.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO_ROOT))

from tools.sound_sim.s12.acoustic_identity_v015.stage_x import reference_caseset as rc  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.candidate_search import run_engineering_search  # noqa: E402
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.engineering_gate import evaluate_engineering_preselection  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[6]
MANIFEST = REPO_ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "reference_database" / "realism_reference_manifest.json"
R2_AUDIO_DIR = Path("E:/Claude_allow/Download/s12-acoustic-realism-v10")
RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x"


def main() -> int:
    started = time.perf_counter()
    reachability = json.loads((RUNTIME / "x4_reachability" / "parameter_reachability.json").read_text(encoding="utf-8"))
    allowed = [item["parameter"] for item in reachability["results"] if item["status"] == "PARAMETER_REACHABLE"]
    caseset = rc.build_reference_caseset("hellcat", MANIFEST, R2_AUDIO_DIR)
    reference_audio: dict[str, tuple["np.ndarray", int]] = {}
    import numpy as np

    for case in caseset["cases"]:
        if case["status"] == "BOUND":
            audio, sample_rate = rc.load_case_segment_audio(case)
            reference_audio[case["scenario"]] = (audio, sample_rate)
    print(f"bound references: {sorted(reference_audio)}; searchable parameters: {len(allowed)}", flush=True)
    preselections = {}
    for architecture in ("P2H", "P3", "P5"):
        arch_started = time.perf_counter()
        search_root = RUNTIME / "x5_search" / architecture
        outcome = run_engineering_search(
            search_root,
            reference_audio,
            architecture=architecture,
            coarse_count=64,
            refine_count=32,
            allowed_parameter_names=allowed,
        )
        best = outcome["best"]
        gate = evaluate_engineering_preselection(
            best if best is not None else {},
            architecture=architecture,
            valid_reference_count=caseset["valid_reference_count"],
            reference_evidence_level=caseset["reference_evidence_level"],
        )
        gate["best_overrides"] = best["overrides"] if best is not None else None
        gate["best_objective"] = best["objective"] if best is not None else None
        gate["search_seconds"] = round(time.perf_counter() - arch_started, 1)
        preselections[architecture] = gate
        (search_root / "preselection_gate.json").write_text(json.dumps(gate, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{architecture}: status={gate['status']} objective={gate['objective']}", flush=True)
    ranking = sorted(
        ((arch, gate["objective"] if gate["objective"] is not None else -1.0) for arch, gate in preselections.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    summary = {
        "schema": "s12.stage_x.hellcat_preselection_summary.v1",
        "valid_reference_count": caseset["valid_reference_count"],
        "reference_scenarios": sorted(reference_audio),
        "searchable_parameter_count": len(allowed),
        "preselections": preselections,
        "architecture_ranking": [arch for arch, _ in ranking],
        "selected_engineering_architecture": ranking[0][0] if ranking and preselections[ranking[0][0]]["eligibility"]["selection_eligible"] else None,
        "wall_seconds": round(time.perf_counter() - started, 1),
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    (RUNTIME / "x5_hellcat_preselection_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"selected": summary["selected_engineering_architecture"], "ranking": summary["architecture_ranking"], "seconds": summary["wall_seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
