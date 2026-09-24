from __future__ import annotations

import math
import shutil
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.qualification import numeric_ok
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import fit_eligibility
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback import (
    ReferenceCase,
    Rendered,
    SearchConfig,
    audio_sha,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ai8.c63_supra_feedback_adapter import (
    C63SupraFeedbackRenderer,
    feedback_parameter_contract,
    fit_reference_cases,
)


SR = 48_000
SCENE = "07_steady_high"


def _context(duration: float = 0.12) -> dict[str, object]:
    count = round(SR * duration)
    rpm = np.linspace(2_000.0, 6_200.0, count)
    throttle = np.linspace(0.45, 0.82, count)
    return {
        "rpm": rpm,
        "throttle": throttle,
        "duration": duration,
        "shift_events": None,
        "afterfire_events": None,
        "bov_events": None,
    }


def _adapter(vehicle: str) -> tuple[C63SupraFeedbackRenderer, np.ndarray]:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.c63_pipeline import C63Engine
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.supra_pipeline import SupraEngine

    context = _context()
    ir = np.array([1.0, 0.08, -0.025], dtype=np.float64)
    engine_type = C63Engine if vehicle == "c63_w204" else SupraEngine
    baseline_engine = engine_type(
        output_policy="linked_soft_ceiling_v1",
        ir=ir,
        scene_ids=(SCENE,),
    )
    baseline_audio = baseline_engine.render_track(
        context["rpm"], context["throttle"], context["duration"]
    )
    record = baseline_engine.reports[-1]
    context["trace_sha256"] = record["trace_sha256"]
    renderer = C63SupraFeedbackRenderer(
        vehicle,
        {SCENE: context},
        baseline_engine.parent_peaks,
        ir=ir,
    )
    return renderer, baseline_audio


@pytest.mark.parametrize("vehicle", ["c63_w204", "supra_jza80"])
def test_feedback_off_is_pcm_identical_and_numerically_qualified(vehicle):
    renderer, expected = _adapter(vehicle)
    actual = renderer(renderer.baseline, SCENE)
    np.testing.assert_array_equal(actual.audio, expected)
    assert actual.numeric_ok
    assert numeric_ok(actual.diagnostics)
    assert actual.diagnostics["reconstruction_peak"]["domain"] == "FINAL_DECODED_PCM_FLOAT"


@pytest.mark.parametrize(
    ("vehicle", "parameter"),
    [("c63_w204", "bark_upper_partial_mix"), ("supra_jza80", "edge_scale")],
)
def test_one_active_source_parameter_changes_real_pcm(vehicle, parameter):
    renderer, baseline_audio = _adapter(vehicle)
    changed = dict(renderer.baseline)
    low, high = renderer.bounds[parameter]
    changed[parameter] = high if changed[parameter] != high else low
    trial = renderer(changed, SCENE)
    assert audio_sha(trial.audio) != audio_sha(baseline_audio)
    assert trial.diagnostics["trace_sha256"] == renderer.contexts[SCENE]["trace_sha256"]
    assert trial.diagnostics["normalization_denominator"] == renderer.parent_peaks[
        trial.diagnostics["parent_peak_key"]
    ]


@pytest.mark.parametrize("vehicle", ["c63_w204", "supra_jza80"])
def test_contract_has_exactly_one_finite_source_parameter(vehicle):
    baseline, bounds = feedback_parameter_contract(vehicle)
    assert len(baseline) == len(bounds) == 1
    assert set(baseline) == set(bounds)
    name = next(iter(bounds))
    low, high = bounds[name]
    assert all(math.isfinite(value) for value in (baseline[name], low, high))
    assert low <= baseline[name] <= high


@pytest.mark.parametrize("vehicle", ["c63_w204", "supra_jza80"])
@pytest.mark.parametrize(
    "invalid",
    [
        {"unknown": 1.0},
        {"bark_upper_partial_mix": True},
        {"bark_upper_partial_mix": float("nan")},
        {"edge_scale": True},
        {"edge_scale": float("inf")},
    ],
)
def test_invalid_parameter_data_fails_closed(vehicle, invalid):
    renderer, _ = _adapter(vehicle)
    with pytest.raises(ValueError):
        renderer(invalid, SCENE)


def test_wrong_trace_bound_denominator_is_rejected():
    renderer, _ = _adapter("supra_jza80")
    renderer.contexts[SCENE]["rpm"][:] = 900.0
    with pytest.raises(ValueError, match="trace|denominator"):
        renderer(renderer.baseline, SCENE)


def test_actual_ir_path_is_loaded_and_hash_bound(tmp_path):
    context = _context()
    path = tmp_path / "measured_ir.wav"
    wavfile.write(path, SR, np.array([32767, 2048, -1024], dtype=np.int16))
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.supra_pipeline import SupraEngine

    anchor = SupraEngine(
        output_policy="linked_soft_ceiling_v1",
        ir=np.array([1.0, 2048 / 32768, -1024 / 32768]),
        scene_ids=(SCENE,),
    )
    anchor.render_track(context["rpm"], context["throttle"], context["duration"])
    context["trace_sha256"] = anchor.reports[-1]["trace_sha256"]
    renderer = C63SupraFeedbackRenderer(
        "supra_jza80", {SCENE: context}, anchor.parent_peaks, ir_path=path
    )
    assert renderer(renderer.baseline, SCENE).numeric_ok
    wavfile.write(path, SR, np.array([32767, 1024, -512], dtype=np.int16))
    with pytest.raises(ValueError, match="IR path changed"):
        renderer(renderer.baseline, SCENE)


def test_ir_array_and_path_are_mutually_exclusive(tmp_path):
    path = tmp_path / "ir.wav"
    wavfile.write(path, SR, np.array([32767, 1024], dtype=np.int16))
    with pytest.raises(ValueError, match="either injected IR or an actual IR path"):
        C63SupraFeedbackRenderer(
            "supra_jza80",
            {SCENE: _context()},
            {"unused": 1.0},
            ir=np.array([1.0]),
            ir_path=path,
        )


def test_boolean_parent_peak_is_rejected_before_conversion():
    with pytest.raises(ValueError, match="parent peaks"):
        C63SupraFeedbackRenderer(
            "supra_jza80", {SCENE: _context()}, {"invalid": True}, ir=np.array([1.0])
        )


def test_context_arrays_are_owned_and_external_mutation_cannot_change_trial():
    renderer, expected = _adapter("c63_w204")
    external = renderer.contexts[SCENE]["rpm"]
    replacement_context = _context()
    replacement_context["trace_sha256"] = renderer.contexts[SCENE]["trace_sha256"]
    isolated = C63SupraFeedbackRenderer(
        "c63_w204",
        {SCENE: replacement_context},
        renderer.parent_peaks,
        ir=renderer.ir,
    )
    replacement_context["rpm"][:] = 900.0
    np.testing.assert_array_equal(isolated(isolated.baseline, SCENE).audio, expected)
    assert not np.shares_memory(external, isolated.contexts[SCENE]["rpm"])


def test_default_ir_path_and_digest_are_bound_for_real_source_trials(tmp_path, monkeypatch):
    ir_root = tmp_path / "portable-ir-root"
    ir_path = ir_root / "new" / "mild_exhaust_reverb.wav"
    ir_path.parent.mkdir(parents=True)
    wavfile.write(ir_path, SR, np.array([32767, 2048, -1024], dtype=np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(ir_root))

    context = _context()
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.supra_pipeline import SupraEngine

    anchor = SupraEngine(output_policy="linked_soft_ceiling_v1", scene_ids=(SCENE,))
    anchor.render_track(context["rpm"], context["throttle"], context["duration"])
    context["trace_sha256"] = anchor.reports[-1]["trace_sha256"]
    default_bound = C63SupraFeedbackRenderer(
        "supra_jza80", {SCENE: context}, anchor.parent_peaks
    )
    assert default_bound._default_ir_path == ir_path.resolve()
    assert len(default_bound._bound_ir_sha256) == 64
    assert default_bound(default_bound.baseline, SCENE).numeric_ok


def test_synthetic_optimizer_moves_real_supra_source_parameter():
    renderer, _ = _adapter("supra_jza80")
    target = dict(renderer.baseline)
    target["edge_scale"] = renderer.bounds["edge_scale"][1]
    reference = renderer(target, SCENE).audio
    cases = [
        ReferenceCase(
            "train",
            SCENE,
            "synthetic-train",
            "a" * 64,
            "train",
            reference,
            (0.0, _context()["duration"]),
            True,
            "synthetic known-target source parameter",
        ),
        ReferenceCase(
            "validation",
            SCENE,
            "synthetic-validation",
            "b" * 64,
            "validation",
            np.roll(reference, 5, axis=0),
            (0.0, _context()["duration"]),
            True,
            "synthetic phase-shifted validation; not field evidence",
        ),
    ]
    result, scope = fit_reference_cases(
        "supra_jza80",
        renderer.contexts,
        renderer.parent_peaks,
        cases,
        ir=renderer.ir,
        config=SearchConfig(max_trials=9, rounds=3, initial_step_fraction=0.5),
    )
    assert result["proposed_train_loss"] < result["baseline_train_loss"]
    assert any(row["decision"] == "TRAIN_ACCEPTED" for row in result["history"])
    assert result["status"] == "ADAPTER_DIAGNOSTIC_ONLY"
    assert result["optimizer_status"] == "RELATIVE_IMPROVEMENT_VALIDATED"
    assert result["reference_provenance"] == "UNVERIFIED_IN_MEMORY"
    assert result["production_qualification"] is False
    assert fit_eligibility(result)["available"] is False
    assert result["promotable"] is False
    assert scope["parameter_count"] == 1
    assert scope["parameters"] == renderer.baseline
    assert scope["scenes"] == [SCENE]
    assert scope["feedback_off_pcm_equal"] is True


def test_fit_requires_explicit_cases_and_known_context_scene():
    renderer, _ = _adapter("c63_w204")
    with pytest.raises(ValueError, match="reference cases"):
        fit_reference_cases(
            "c63_w204", renderer.contexts, renderer.parent_peaks, [], ir=renderer.ir
        )
    bad = ReferenceCase(
        "train",
        "missing_scene",
        "synthetic-train",
        "a" * 64,
        "train",
        np.zeros((128, 2), dtype=np.float64),
        (0.0, 0.001),
        True,
        "synthetic only",
    )
    with pytest.raises(ValueError, match="scene context"):
        fit_reference_cases(
            "c63_w204", renderer.contexts, renderer.parent_peaks, [bad], ir=renderer.ir
        )


def test_fit_rolls_back_when_selected_parameter_fails_non_reference_scene(monkeypatch):
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.supra_pipeline import SupraEngine

    context = _context()
    extra_scene = "10_tip_in"
    ir = np.array([1.0, 0.08, -0.025], dtype=np.float64)
    anchor = SupraEngine(
        output_policy="linked_soft_ceiling_v1",
        ir=ir,
        scene_ids=(SCENE, extra_scene),
    )
    contexts = {}
    for scene in (SCENE, extra_scene):
        anchor.render_track(context["rpm"], context["throttle"], context["duration"])
        contexts[scene] = {**context, "trace_sha256": anchor.reports[-1]["trace_sha256"]}
    renderer = C63SupraFeedbackRenderer(
        "supra_jza80", contexts, anchor.parent_peaks, ir=ir
    )
    target = dict(renderer.baseline)
    target["edge_scale"] = renderer.bounds["edge_scale"][1]
    reference = renderer(target, SCENE).audio
    cases = [
        ReferenceCase("train", SCENE, "train", "c" * 64, "train", reference,
                      (0.0, context["duration"]), True, "synthetic target"),
        ReferenceCase("validation", SCENE, "validation", "d" * 64, "validation",
                      np.roll(reference, 5, axis=0), (0.0, context["duration"]),
                      True, "synthetic validation"),
    ]
    original_call = C63SupraFeedbackRenderer.__call__

    def fail_selected_non_reference(self, parameters, scene):
        rendered = original_call(self, parameters, scene)
        if scene == extra_scene and dict(parameters) != self.baseline:
            return Rendered(rendered.audio, False, {**rendered.diagnostics, "test_failure": True})
        return rendered

    monkeypatch.setattr(C63SupraFeedbackRenderer, "__call__", fail_selected_non_reference)
    result, scope = fit_reference_cases(
        "supra_jza80",
        contexts,
        anchor.parent_peaks,
        cases,
        ir=ir,
        config=SearchConfig(max_trials=9, rounds=3, initial_step_fraction=0.5),
    )
    assert result["status"] == "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK"
    assert result["selected_parameters"] == renderer.baseline
    assert result["rejected_parameters"] != renderer.baseline
    assert result["rejected_diagnostics"][extra_scene]["test_failure"] is True
    assert scope["provided_scenes"] == [SCENE, extra_scene]
    assert scope["reference_scenes"] == [SCENE]
    assert scope["canonical_ten_scene_coverage"] is False


def test_c63_candidate_profile_file_is_frozen_and_drift_rejected(tmp_path, monkeypatch):
    import tools.sound_sim.s12.acoustic_identity_v015.stage_ai8.c63_supra_feedback_adapter as adapter_module
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.c63_pipeline import C63_CANDIDATE_PATH

    frozen_path = tmp_path / "c63_candidate.json"
    shutil.copy2(C63_CANDIDATE_PATH, frozen_path)
    monkeypatch.setattr(adapter_module, "C63_CANDIDATE_PATH", frozen_path)
    renderer, _ = _adapter("c63_w204")
    bound = adapter_module.C63SupraFeedbackRenderer(
        "c63_w204", renderer.contexts, renderer.parent_peaks, ir=renderer.ir
    )
    frozen_path.write_text(frozen_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="candidate profile file changed"):
        bound(bound.baseline, SCENE)


def test_supra_source_module_is_frozen_and_drift_rejected(tmp_path, monkeypatch):
    import tools.sound_sim.s12.acoustic_identity_v015.stage_ai8.c63_supra_feedback_adapter as adapter_module

    source_path = Path(__file__).resolve().parents[1] / "sources" / "toyota_i6_turbo_source_v2.py"
    frozen_path = tmp_path / source_path.name
    shutil.copy2(source_path, frozen_path)
    monkeypatch.setattr(adapter_module, "SUPRA_SOURCE_PATH", frozen_path, raising=False)
    renderer, _ = _adapter("supra_jza80")
    bound = adapter_module.C63SupraFeedbackRenderer(
        "supra_jza80", renderer.contexts, renderer.parent_peaks, ir=renderer.ir
    )
    frozen_path.write_text(frozen_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Supra source file changed"):
        bound(bound.baseline, SCENE)
