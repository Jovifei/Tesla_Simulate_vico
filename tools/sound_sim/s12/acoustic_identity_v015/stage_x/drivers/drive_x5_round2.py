"""Drive X5 round-2 Hellcat search after structural redesign."""

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
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.structural_redesign import analyze_failure_dimensions, build_round2_plan  # noqa: E402

MANIFEST = REPO_ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "reference_database" / "realism_reference_manifest.json"
R2_AUDIO_DIR = Path("E:/Claude_allow/Download/s12-acoustic-realism-v10")
RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-x"


def main() -> int:
    started = time.perf_counter()
    round1 = json.loads((RUNTIME / "x5_hellcat_preselection_summary.json").read_text(encoding="utf-8"))
    if round1.get("selected_engineering_architecture"):
        print(json.dumps({"skipped": True, "reason": "round1 already selected"}))
        return 0
    analysis = analyze_failure_dimensions(round1)
    plan = build_round2_plan(round1)
    (RUNTIME / "x5_round2" / "failure_analysis.json").write_text(json.dumps(analysis, indent=1, ensure_ascii=False), encoding="utf-8")
    caseset = rc.build_reference_caseset("hellcat", MANIFEST, R2_AUDIO_DIR)
    reference_audio: dict[str, tuple] = {}
    for case in caseset["cases"]:
        if case["status"] == "BOUND":
            audio, sample_rate = rc.load_case_segment_audio(case)
            reference_audio[case["scenario"]] = (audio, sample_rate)
    architecture = plan["architecture"]
    search_root = RUNTIME / "x5_round2" / architecture
    outcome = run_engineering_search(
        search_root,
        reference_audio,
        architecture=architecture,
        coarse_count=plan["coarse_count"],
        refine_count=plan["refine_count"],
        seed=plan["seed"],
        allowed_parameter_names=[item.name for item in plan["parameters"]],
        base_config=plan["base_config"],
        parameters_override=plan["parameters"],
    )
    best = outcome["best"]
    gate = evaluate_engineering_preselection(
        best if best is not None else {},
        architecture=architecture,
        valid_reference_count=caseset["valid_reference_count"],
        reference_evidence_level=caseset["reference_evidence_level"],
    )
    gate["round"] = 2
    gate["structural_redesign"] = analysis
    gate["best_overrides"] = best["overrides"] if best is not None else None
    gate["best_objective"] = best["objective"] if best is not None else None
    (search_root / "preselection_gate.json").write_text(json.dumps(gate, indent=1, ensure_ascii=False), encoding="utf-8")
    round1["round2"] = {
        "failure_analysis": analysis,
        "architecture": architecture,
        "preselection_gate": gate,
        "selected_engineering_architecture": architecture if gate["eligibility"]["selection_eligible"] else None,
    }
    if gate["eligibility"]["selection_eligible"]:
        round1["selected_engineering_architecture"] = architecture
        round1["preselections"][architecture] = gate
        round1["final_status"] = "R2_ENGINEERING_SELECTION_COMPLETE"
    else:
        round1["final_status"] = "NO_MEASURABLE_IMPROVEMENT_AFTER_REDESIGN"
        round1["model_redesign_required"] = True
    round1["wall_seconds_round2"] = round(time.perf_counter() - started, 1)
    (RUNTIME / "x5_hellcat_preselection_summary.json").write_text(json.dumps(round1, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"round2_status": gate["status"], "objective": gate.get("objective"), "selected": round1.get("selected_engineering_architecture"), "seconds": round1["wall_seconds_round2"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
