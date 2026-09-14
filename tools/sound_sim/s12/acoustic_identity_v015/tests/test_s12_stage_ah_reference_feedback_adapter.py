"""Actual engine adapter with controlled IR and synthetic references, not R3 media."""
from dataclasses import replace
import json

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback import (
    ReferenceCase, SearchConfig, SR, audio_sha, optimize_reference_feedback,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback_cli import (
    PLAN_SCHEMA, RemainingFeedbackRenderer, load_plan, numeric_ok,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.remaining_vehicle_pipeline import RemainingVehicleEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.output_guard import LINKED_SOFT_CEILING_V1


def adapter(vehicle):
    scene, duration = "07_steady_high", 0.4
    count = round(duration * SR)
    context = {"rpm": np.full(count, 6000.0), "throttle": np.full(count, 0.7),
               "duration": duration, "shift_events": None, "afterfire_events": None,
               "bov_events": None}
    ir = np.array([1.0, 0.12, -0.04])
    base = RemainingVehicleEngine(vehicle, SR, output_policy=LINKED_SOFT_CEILING_V1,
                                  ir=ir, scene_ids=(scene,))
    audio = base.render_track(**{"rpm_curve": context["rpm"], "throttle_curve": context["throttle"],
                                "duration": duration})
    context["trace_sha256"] = base.reports[-1]["trace_sha256"]
    return RemainingFeedbackRenderer(vehicle, {scene: context}, base.parent_peaks, ir), audio, base.reports[-1]


@pytest.mark.parametrize("vehicle", ["rx7_fd", "aventador_lp700"])
def test_actual_renderer_off_switch_and_frozen_parent(vehicle):
    renderer, base_audio, report = adapter(vehicle)
    result = renderer(renderer.baseline, "07_steady_high")
    np.testing.assert_array_equal(result.audio, base_audio)
    assert result.numeric_ok
    changed = dict(renderer.baseline)
    name = "rotary_pulse_width_scale" if vehicle == "rx7_fd" else "v12_scream_mix"
    changed[name] += 0.03
    candidate = renderer(changed, "07_steady_high")
    assert audio_sha(candidate.audio) != audio_sha(base_audio)
    assert candidate.diagnostics["normalization_denominator"] == report["normalization_denominator"]
    assert candidate.diagnostics["trace_sha256"] == report["trace_sha256"]
    assert candidate.diagnostics["output_policy"] == LINKED_SOFT_CEILING_V1


def test_actual_v12_engine_closed_loop_known_target():
    renderer, _, _ = adapter("aventador_lp700")
    target_params = dict(renderer.baseline)
    target_params["v12_scream_mix"] = 1.2
    reference = renderer(target_params, "07_steady_high").audio
    # Deliberately synthetic different phase realization; no real-recording claim.
    refs = [ReferenceCase("train", "07_steady_high", "synthetic-a", "a"*64, "train", reference,
                         (0.0, 0.4), True, "synthetic known source target at fixed 6000 RPM"),
            ReferenceCase("validation", "07_steady_high", "synthetic-b", "b"*64, "validation",
                         np.roll(reference, 11, axis=0), (0.0, 0.4), True,
                         "synthetic phase-shift validation, not field audio")]
    result = optimize_reference_feedback(renderer.baseline, renderer.bounds, refs, renderer,
                                         config=SearchConfig(max_trials=13, rounds=2))
    assert result["proposed_train_loss"] < result["baseline_train_loss"]
    assert any(row["decision"] == "TRAIN_ACCEPTED" for row in result["history"])
    assert result["promotable"] is False


def test_numeric_missing_values_never_pass():
    _, _, record = adapter("aventador_lp700")
    assert numeric_ok(record)
    for key in ("identity_layer_clip_count", "post_identity_clip_error", "peak_estimate_4x"):
        broken = dict(record)
        broken.pop(key)
        assert not numeric_ok(broken)
    broken = dict(record, peak_estimate_4x={"peak": float("nan")})
    assert not numeric_ok(broken)


def test_whitelist_cannot_change_gain_or_ir():
    renderer, _, _ = adapter("aventador_lp700")
    invalid = dict(renderer.baseline, ir_volume=0.02)
    with pytest.raises(ValueError, match="whitelist"):
        renderer(invalid, "07_steady_high")
