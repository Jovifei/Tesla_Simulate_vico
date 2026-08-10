from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.candidate_profiles import load_stage_h_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_h.render_candidate import render_stage_h_candidate


def _trace() -> VehicleStateTrace:
    sample_rate_hz = 48000
    duration_s = 1.2
    count = int(duration_s * sample_rate_hz) + 1
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    phase = time_s / duration_s
    rpm = 900.0 + 5200.0 * phase
    load = 0.15 + 0.80 * phase
    throttle = 0.15 + 0.83 * phase
    throttle[phase >= 0.62] = 0.0
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def test_each_stage_h_source_parameter_changes_consumed_whine_output() -> None:
    from copy import deepcopy
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "targets" / "stage_h_candidates" / "Hellcat_candidate_v5.json"
    base = load_stage_h_candidate(path)
    trace = _trace()
    baseline = render_stage_h_candidate("hellcat", trace, base)
    requested = [name for name in base.requested_parameters() if name.startswith("source.")]
    assert requested
    for qualified in requested:
        section, name = qualified.split(".", 1)
        entry = base.payload[section][name]
        low, high = entry["range"]
        probe = low if entry["value"] != low else high
        payload = deepcopy(base.payload)
        payload[section][name]["value"] = probe
        trial_path = path.with_name("_stage_h_probe.json")
        trial_path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            trial = load_stage_h_candidate(trial_path)
            rendered = render_stage_h_candidate("hellcat", trace, trial)
        finally:
            trial_path.unlink(missing_ok=True)
        assert not np.array_equal(rendered.stems["blower"], baseline.stems["blower"]), qualified
