from __future__ import annotations

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_i.feedback_contract import (
    BOUND_EXPLICIT_FILE_ID,
    UNBOUND,
    bind_numbered_feedback,
)


_CATALOG = {
    "ferrari_458_stage_h_unchanged_60s": "ferrari_458",
    "rx7_fd_stage_h_unchanged_60s": "rx7_fd",
}


def test_stage_g_numbered_feedback_without_file_id_remains_unbound() -> None:
    feedback = bind_numbered_feedback(
        (
            {
                "feedback_id": "stage_g_number_2",
                "raw_feedback": "第2个声音高频有点刺耳，低频轰鸣很好。",
                "file_id": None,
            },
            {
                "feedback_id": "stage_g_number_3",
                "raw_feedback": "第3个声音特别好，但还有优化空间。",
                "file_id": "",
            },
        ),
        file_catalog=_CATALOG,
    )

    assert [item.binding_status for item in feedback] == [UNBOUND, UNBOUND]
    assert all(item.file_id is None for item in feedback)
    assert all(item.vehicle_id is None for item in feedback)
    assert all(item.modification_authorized is False for item in feedback)


def test_numbered_feedback_binds_only_with_explicit_known_file_id() -> None:
    feedback = bind_numbered_feedback(
        (
            {
                "feedback_id": "stage_g_number_2",
                "raw_feedback": "第2个声音高频有点刺耳。",
                "file_id": "ferrari_458_stage_h_unchanged_60s",
            },
        ),
        file_catalog=_CATALOG,
    )

    assert feedback[0].binding_status == BOUND_EXPLICIT_FILE_ID
    assert feedback[0].file_id == "ferrari_458_stage_h_unchanged_60s"
    assert feedback[0].vehicle_id == "ferrari_458"
    assert feedback[0].modification_authorized is True


def test_numbered_feedback_rejects_unknown_explicit_file_id() -> None:
    with pytest.raises(ValueError, match="unknown explicit file_id"):
        bind_numbered_feedback(
            (
                {
                    "feedback_id": "stage_g_number_2",
                    "raw_feedback": "第2个声音高频有点刺耳。",
                    "file_id": "R2_T02",
                },
            ),
            file_catalog=_CATALOG,
        )
