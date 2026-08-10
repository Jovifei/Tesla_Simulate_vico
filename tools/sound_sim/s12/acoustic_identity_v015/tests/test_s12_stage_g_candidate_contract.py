from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_g.candidate_profiles import (
    BASE_COMMIT,
    SCHEMA_VERSION,
    load_stage_g_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "targets" / "stage_g_candidates"


def test_three_stage_g_candidates_are_strict_and_reference_bound() -> None:
    for filename, vehicle_id in (
        ("Ferrari_candidate_v4.json", "ferrari_458"),
        ("Hellcat_candidate_v4.json", "hellcat"),
        ("RX7_candidate_v4.json", "rx7_fd"),
    ):
        profile = load_stage_g_candidate(TARGETS / filename)
        assert profile.payload["schema_version"] == SCHEMA_VERSION
        assert profile.payload["base_commit"] == BASE_COMMIT
        assert profile.vehicle_id == vehicle_id
        assert profile.status == "Candidate"
        assert profile.requested_parameters()
        assert profile.reference_target["eligible_states"] == ["idle", "acceleration", "afterfire"]


def test_unknown_override_and_bad_range_fail_closed(tmp_path: Path) -> None:
    source = TARGETS / "Ferrari_candidate_v4.json"
    text = source.read_text(encoding="utf-8")
    path = tmp_path / source.name
    path.write_text(text.replace('"candidate_id":"ferrari_458_stage_g_v4"', '"candidate_id":"x"'), encoding="utf-8")
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    payload["source"]["unknown"] = payload["source"]["pulse_width_scale"]
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_stage_g_candidate(path)


def test_reference_sha_is_checked(tmp_path: Path) -> None:
    source = TARGETS / "Hellcat_candidate_v4.json"
    payload = __import__("json").loads(source.read_text(encoding="utf-8"))
    payload["reference_target"]["sha256"] = "0" * 64
    path = tmp_path / source.name
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="reference target SHA-256"):
        load_stage_g_candidate(path)


def test_candidate_none_is_stage_c_compatible() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_g.render_candidate import render_stage_g_candidate
    from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful
    from tools.sound_sim.s12.acoustic_identity_v015.stage_d.scenarios import build_stage_d_scenario_trace

    trace = build_stage_d_scenario_trace("rx7_fd", "idle", duration_s=2.0)
    expected = _render_stateful(_RENDERERS["rx7_fd"], "rx7_fd", trace)
    actual = render_stage_g_candidate("rx7_fd", trace, None)
    assert actual.pressure.shape == expected.pressure.shape
    assert actual.stems.keys() == expected.stems.keys()
    assert __import__("numpy").array_equal(actual.pressure, expected.pressure)
    for name in expected.stems:
        assert __import__("numpy").array_equal(actual.stems[name], expected.stems[name])
