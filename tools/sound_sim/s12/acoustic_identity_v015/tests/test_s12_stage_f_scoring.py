import json

from tools.sound_sim.s12.acoustic_identity_v015.stage_f.response_contract import (
    BlindResponse,
    PairResponse,
    PlaybackContext,
    StageFSubmission,
    score_stage_f_submission,
)


def test_stage_f_scoring_uses_sealed_roles_and_fixed_denominators(tmp_path):
    trials = {}
    rows = []
    index = 0
    for round_id, role in ((1, "candidate"), (2, "baseline")):
        for vehicle in ("ferrari_458", "hellcat", "rx7_fd"):
            for _ in range(5):
                index += 1
                trial_id = f"R{round_id}_T{index - (round_id - 1) * 15:02d}"
                trials[trial_id] = {"vehicle_id": vehicle, "scene_id": "idle", "role": role}
                rows.append(BlindResponse({"trial_id": trial_id, "guessed_vehicle_id": vehicle, "confidence_1_5": "4", "realism_1_5": "4", "artifact_freedom_1_5": "4"}))
    answer_key = tmp_path / "answer_key.json"; answer_key.write_text(json.dumps({"trials": trials}), encoding="utf-8")
    pair_key = tmp_path / "pair_key.json"; pair_key.write_text(json.dumps({"pairs": {f"P{i:02d}": {"vehicle_id": v, "A_role": "baseline", "B_role": "candidate"} for i, v in enumerate(("ferrari_458", "hellcat", "rx7_fd"), 1)}}), encoding="utf-8")
    pairs = tuple(PairResponse({"pair_id": f"P{i:02d}", "preferred_option": "equal", "artifact_blocker": "false"}) for i in range(1, 4))
    score = score_stage_f_submission(answer_key, pair_key, StageFSubmission(tuple(rows), pairs, PlaybackContext({})))
    assert score.candidate["accuracy"] == 1.0
    assert score.baseline["accuracy"] == 1.0
    assert score.candidate["per_vehicle_recall"] == {"ferrari_458": 1.0, "hellcat": 1.0, "rx7_fd": 1.0}
