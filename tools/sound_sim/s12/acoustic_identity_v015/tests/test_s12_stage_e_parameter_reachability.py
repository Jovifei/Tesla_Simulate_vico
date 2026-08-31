import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.candidate_profiles import load_stage_e_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_e.render_candidate import render_stage_e_candidate


def _trace():
    t = np.linspace(0.0, 0.35, 36)
    rpm = np.linspace(1050.0, 7200.0, t.size)
    return VehicleStateTrace(t, rpm, np.full(t.size, 0.8), np.full(t.size, 0.8), np.zeros(t.size))


def _profile(name):
    from pathlib import Path
    return load_stage_e_candidate(Path(__file__).resolve().parents[1] / "targets" / "stage_e_candidates" / name)


def test_candidate_parameter_usage_is_recorded():
    render = render_stage_e_candidate("ferrari_458", _trace(), _profile("Ferrari_candidate_v2.json"))
    usage = render.diagnostics["candidate_parameter_usage"]
    assert "source.bank_phase_offset_deg" in usage
    assert usage["source.bank_phase_offset_deg"] is True


def test_candidate_override_changes_audio():
    base = _profile("Ferrari_candidate_v2.json")
    changed = base.with_parameter("source", "bank_phase_offset_deg", base.parameter("source", "bank_phase_offset_deg", 0.0) + 5.0)
    a = render_stage_e_candidate("ferrari_458", _trace(), base)
    b = render_stage_e_candidate("ferrari_458", _trace(), changed)
    assert not np.array_equal(a.pressure, b.pressure)
