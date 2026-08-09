import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.candidate_profiles import load_stage_f_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_f.render_candidate import render_stage_f_candidate


def _trace():
    t = np.arange(0.0, 0.25, 1.0 / 48000.0)
    rpm = np.linspace(900.0, 7800.0, t.size)
    load = np.where(t < 0.08, 0.2, 0.8)
    throttle = np.where(t < 0.16, 0.9, 0.05)
    return VehicleStateTrace(t, rpm, load, throttle, np.gradient(rpm / 60.0, t)).validate()


def _profile(name):
    from pathlib import Path
    return load_stage_f_candidate(Path(__file__).resolve().parents[1] / "targets" / "stage_f_candidates" / name)


def test_active_candidate_parameters_are_consumed():
    for name in ("Ferrari_candidate_v3.json", "Hellcat_candidate_v3.json", "RX7_candidate_v3.json"):
        render = render_stage_f_candidate(_profile(name).vehicle_id, _trace(), _profile(name))
        usage = render.diagnostics["candidate_parameter_usage"]
        assert usage["unused"] == []
        assert set(usage["requested"]) == set(usage["consumed"])


def test_rx7_rotary_pulse_width_changes_time_structure():
    profile = _profile("RX7_candidate_v3.json")
    changed = profile.with_parameter("source", "rotary_pulse_width_scale", 1.12)
    a = render_stage_f_candidate("rx7_fd", _trace(), profile)
    b = render_stage_f_candidate("rx7_fd", _trace(), changed)
    assert not np.array_equal(a.stems["rotary"], b.stems["rotary"])


def test_one_candidate_change_does_not_touch_other_vehicle():
    profile = _profile("Ferrari_candidate_v3.json")
    changed = profile.with_parameter("source", "bank_phase_offset_deg", 8.0)
    for vehicle_id, filename in (("hellcat", "Hellcat_candidate_v3.json"), ("rx7_fd", "RX7_candidate_v3.json")):
        unchanged = _profile(filename)
        a = render_stage_f_candidate(vehicle_id, _trace(), unchanged)
        b = render_stage_f_candidate(vehicle_id, _trace(), unchanged)
        np.testing.assert_array_equal(a.pressure, b.pressure)
