import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_g.response_contract import (
    BlindResponse,
    PairResponse,
    PlaybackContext,
    StageGSubmission,
    score_stage_g_submission,
)


def test_stage_g_scoring_uses_role_and_five_trial_vehicle_denominators(tmp_path):
    trials = {}
    rows = []
    vehicles = ("ferrari_458", "hellcat", "rx7_fd")
    scenes = ("idle", "cruise", "acceleration", "shift", "lift")
    for round_id, role in ((1, "baseline"), (2, "candidate")):
        index = 1
        for vehicle in vehicles:
            for scene in scenes:
                trial_id = f"R{round_id}_T{index:02d}"
                trials[trial_id] = {"vehicle_id": vehicle, "scene_id": scene, "role": role}
                guess = "hellcat" if role == "baseline" and vehicle != "hellcat" else vehicle
                rows.append(
                    BlindResponse(
                        {
                            "trial_id": trial_id,
                            "round_id": str(round_id),
                            "guessed_vehicle_id": guess,
                            "confidence_1_5": "5",
                            "identity_strength_1_5": "5",
                            "realism_1_5": "4",
                            "artifact_freedom_1_5": "5",
                        }
                    )
                )
                index += 1
    answer_key = tmp_path / "answer_key.json"
    answer_key.write_text(json.dumps({"trials": trials}), encoding="utf-8")
    pair_key = tmp_path / "pair_key.json"
    pair_key.write_text(
        json.dumps({"pairs": {f"P{i:02d}": {"A_role": "baseline", "B_role": "candidate"} for i in range(1, 4)}}),
        encoding="utf-8",
    )
    pairs = tuple(
        PairResponse(
            {
                "pair_id": f"P{i:02d}",
                "preferred_option": "B",
                "artifact_blocker": "false",
                "notes": "",
            }
        )
        for i in range(1, 4)
    )
    score = score_stage_g_submission(
        answer_key,
        pair_key,
        StageGSubmission(tuple(rows), pairs, PlaybackContext({})),
    )

    assert score.baseline["correct"] == 5
    assert score.baseline["rounds"]["1"]["per_vehicle_correct"] == {"ferrari_458": 0, "hellcat": 5, "rx7_fd": 0}
    assert score.candidate["correct"] == 15
    assert score.candidate["rounds"]["2"]["per_vehicle_recall"] == {vehicle: 1.0 for vehicle in vehicles}
    assert score.gates["candidate_overall_12_of_15"] is True
    assert score.gates["ab_candidate_better_or_equal_without_blocker"] is True
    assert score.status == "JOVI_SINGLE_LISTENER_BLIND_CANDIDATE_PASS"
