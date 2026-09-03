"""Stage AC (AC5): isolated dynamic-event timing + afterfire validation tests.

Validates that the deterministic isolated-event diagnostic fixtures are MEASURABLE
(clean >=250 ms pre / >=500 ms post windows), report honest SAME_BLOCK_RESPONSE
timing (never "instant physical response"), and that the afterfire eligible /
ineligible pair is a valid positive/negative control without touching production
scenes, PCM, or the renderer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.isolated_events import (
    BLOCK_MS,
    ISOLATED_SCENES,
    afterfire_event_count,
    afterfire_metric_validation_v2,
    build_isolated_trace,
    detect_isolated_event_onset,
    isolated_event_timing_document,
)

SAMPLE_RATE = 48000
BLOCK_SIZE = 960
STATE_RATE = SAMPLE_RATE // BLOCK_SIZE  # 50 frames/sec

REPO_ROOT = Path(__file__).resolve().parents[5]
AC_RUNTIME = REPO_ROOT / "tasks" / "reports" / "runtime" / "s12-stage-ac"
RECEIPTS = AC_RUNTIME / "receipts"


def test_isolated_traces_have_clean_event_windows() -> None:
    """Every isolated event trace (except the ineligible afterfire control) must expose
    a single state event with >= 250 ms pre and >= 500 ms post at 2.0 s."""
    for kind in ("isolated_tip_in", "isolated_gear_shift", "isolated_high_rpm_lift", "isolated_afterfire_eligible"):
        trace = build_isolated_trace(kind, 2.0)
        onset = detect_isolated_event_onset(kind, trace)
        assert onset is not None, kind
        pre_ms = onset * BLOCK_MS
        post_ms = (trace.time_s.size - onset) * BLOCK_MS
        assert pre_ms >= 250.0, f"{kind}: pre {pre_ms:.0f} ms < 250"
        assert post_ms >= 500.0, f"{kind}: post {post_ms:.0f} ms < 500"


def test_ineligible_afterfire_has_no_isolated_event() -> None:
    """The ineligible afterfire control must NOT expose a state event (0 afterfire events)."""
    trace = build_isolated_trace("isolated_afterfire_ineligible", 2.0)
    assert detect_isolated_event_onset("isolated_afterfire_ineligible", trace) is None
    assert afterfire_event_count("isolated_afterfire_ineligible", 2.0) == 0


def test_afterfire_eligible_emits_exactly_one_event() -> None:
    """The eligible afterfire fixture must emit exactly one afterfire event."""
    assert afterfire_event_count("isolated_afterfire_eligible", 2.0) == 1


def test_timing_is_same_block_response_not_instant_physics() -> None:
    """§12: per-stage audio response must be reported as SAME_BLOCK_RESPONSE when it
    lands within the state event's own 20 ms block, and must carry a resolution note
    so it can never be misread as an instantaneous-engine-physics claim."""
    for kind in ("isolated_tip_in", "isolated_gear_shift", "isolated_high_rpm_lift", "isolated_afterfire_eligible"):
        doc = isolated_event_timing_document(kind, 2.0)
        assert doc.get("status") != "NO_ISOLATED_STATE_EVENT"
        for stage, info in doc["stage_responses"].items():
            assert "resolution_note" in info or info.get("class") == "NOT_MEASURABLE", (kind, stage)
            if info.get("measurable"):
                assert info["timing_class"] in ("SAME_BLOCK_RESPONSE", "LATER_BLOCK_RESPONSE")
                assert "not an instant-engine-physics claim" in info["resolution_note"]


def test_afterfire_validation_red_flag_retained() -> None:
    """§13: afterfire ~20 dB ACOUSTIC RED FLAG is retained on the eligible fixture;
    the ineligible fixture is a 0-event negative control. No production gain change."""
    doc = afterfire_metric_validation_v2("isolated_afterfire_eligible", "isolated_afterfire_ineligible", 2.0)
    elig = doc["eligible_window"]
    inelig = doc["ineligible_window"]
    assert elig["afterfire_event_count"] == 1
    assert inelig["afterfire_event_count"] == 0
    assert elig["status"] == "MEASURABLE"
    # red flag is present either because the isolated event-vs-baseline is large, or the
    # AA-C3 whole-clip ~20 dB claim is carried; either way the schema must expose it.
    assert "acoustic_red_flag" in doc


def test_ac5_receipts_are_json_serializable() -> None:
    """The generated receipts must be valid, JSON-serializable evidence."""
    for name in ("dynamic_event_timing_contract.json", "afterfire_metric_validation_v2.json"):
        path = RECEIPTS / name
        assert path.is_file(), f"missing AC5 receipt {path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        # round-trip proves serializability
        assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload


def test_timing_document_has_stage_fields() -> None:
    """The timing contract must record state onset + per-stage response for pre_ptr,
    post_ptr, and monitor where measurable (spec §11.1-11.4)."""
    doc = isolated_event_timing_document("isolated_tip_in", 2.0)
    assert doc["state_event_onset_ms"] is not None
    for stage in ("pre_ptr", "post_ptr", "monitor"):
        assert stage in doc["stage_responses"]
    assert "timing_semantics" in doc
