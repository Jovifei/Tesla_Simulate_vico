from __future__ import annotations

import json
import importlib
import hashlib
import socketserver
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics import (
    EngineAcoustics,
    causal_backward_difference,
    causal_fractional_delay,
    firing_phase_for_cycle,
    load_impulse_response,
    shift_cut_mask,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.build_existing_dashboards import (
    _load_fit,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.partitioned_convolver import (
    UniformPartitionedConvolver,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.physical_closed_loop import (
    per_scene_guard,
    renderer_identity,
    validate_fit_payload,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.scorecard_rows import (
    executable_row_count,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_af.spectral_guard import (
    multires_spectral_distance,
)


def _identity_ir(*args, **kwargs):
    return np.asarray([1.0], dtype=np.float64)


def _render(engine: EngineAcoustics, seed: int) -> np.ndarray:
    n = int(engine.sr * 0.12)
    rpm = np.full(n, 3000.0)
    throttle = np.full(n, 0.5)
    np.random.seed(seed)
    return engine.render_track(rpm, throttle, 0.12)


def test_disabled_numerical_fixes_preserve_original_engine_output(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    baseline = _render(EngineAcoustics("hellcat", sr=48000), seed=17)
    disabled = _render(EngineAcoustics("hellcat", sr=48000, numerical_fixes=()), seed=17)
    assert np.array_equal(baseline, disabled)


def test_cycle_phase_fix_converts_crank_angle_once(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    baseline = _render(EngineAcoustics("hellcat", numerical_fixes=()), seed=19)
    corrected = _render(EngineAcoustics("hellcat", numerical_fixes=("cycle_phase",)), seed=19)
    assert not np.array_equal(baseline, corrected)


def test_firing_phase_conversion_is_exactly_one_half_in_cycle_domain():
    assert firing_phase_for_cycle(3.0 * np.pi, frozenset({"cycle_phase"})) == pytest.approx(1.5 * np.pi)
    assert firing_phase_for_cycle(3.0 * np.pi, frozenset()) == pytest.approx(3.0 * np.pi)


def test_default_ir_search_keeps_root_asset_before_optional_subdirectories(tmp_path, monkeypatch):
    root = tmp_path / "ir"
    (root / "new").mkdir(parents=True)
    wavfile.write(root / "example.wav", 48000, np.asarray([1000], dtype=np.int16))
    wavfile.write(root / "new" / "example.wav", 48000, np.asarray([3000], dtype=np.int16))
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(root))
    loaded = load_impulse_response("example", target_sr=48000)
    assert loaded[0] == pytest.approx(1000.0 / 32768.0)


def test_renderer_identity_records_original_ir_path_and_sha():
    identity = renderer_identity("hellcat")
    source = Path(identity["ir_source_path"])
    assert source.is_file()
    assert identity["ir_source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert identity["ir_provenance"] == "LOCAL_ASSET_REQUIRES_SEPARATE_RIGHTS_RECEIPT"


def test_missing_ir_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("S12_ENGINE_SIM_IR_ROOT", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        EngineAcoustics("hellcat")


def test_causal_fractional_delay_never_wraps_future_samples():
    impulse = np.asarray([1.0, 0.0, 0.0, 0.0])
    assert np.array_equal(
        causal_fractional_delay(impulse, 2.5),
        np.asarray([0.0, 0.0, 0.5, 0.5]),
    )


def test_causal_derivative_has_no_lookahead():
    assert np.array_equal(
        causal_backward_difference(np.asarray([1.0, 2.0, 4.0]), 1.0),
        np.asarray([1.0, 1.0, 2.0]),
    )


def test_shift_cut_fix_is_unity_cut_unity_envelope():
    corrected = shift_cut_mask(9, corrected=True)
    legacy = shift_cut_mask(9, corrected=False)
    assert corrected[0] == pytest.approx(1.0)
    assert corrected[-1] == pytest.approx(1.0)
    assert corrected[4] < corrected[0]
    assert legacy[0] < corrected[0] and legacy[-1] < corrected[-1]


def test_partitioned_ir_convolution_is_causal():
    impulse_response = np.asarray([0.0, 0.0, 1.0])
    output = UniformPartitionedConvolver(impulse_response, partition_size=4).process(
        np.asarray([1.0, 0.0, 0.0, 0.0])
    )
    assert np.array_equal(output[:2], np.asarray([0.0, 0.0]))
    assert output[2] == pytest.approx(1.0)


def test_octave_separated_same_band_signals_have_nonzero_distance():
    sr = 48000
    t = np.arange(sr, dtype=np.float64) / sr
    a = np.sin(2 * np.pi * 500.0 * t)
    b = np.sin(2 * np.pi * 750.0 * t)
    assert multires_spectral_distance(a, b, sr) > 0.01


def test_fit_payload_rejects_numerical_fix_mismatch():
    payload = {
        "schema": "s12.stage_af.physical_fit.v4",
        "vehicle": "hellcat",
        "seed": 20260906,
        "numerical_fixes": [],
    }
    with pytest.raises(ValueError, match="numerical mode mismatch"):
        validate_fit_payload(payload, "hellcat", ("cycle_phase",), 20260906)


def test_missing_fit_is_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="refusing default-config fallback"):
        _load_fit(tmp_path / "missing.json", "hellcat", (), 20260906)


def test_per_scene_guard_rejects_one_degraded_scene():
    assert not per_scene_guard(
        {"idle": 1.0, "afterfire": 1.3},
        {"idle": 1.0, "afterfire": 1.0},
        0.10,
    )


def test_ci_scorecard_count_uses_rows_off_on_hashes_and_call_path():
    rows = [
        {"off_pcm_sha": "a" * 64, "on_pcm_sha": "b" * 64, "runtime_call_path": "engine -> on"},
        {"off_pcm_sha": "a" * 64, "on_pcm_sha": "a" * 64, "runtime_call_path": "engine -> on"},
        {"off_pcm_sha": "c" * 64, "on_pcm_sha": "d" * 64, "runtime_call_path": ""},
    ]
    assert executable_row_count(rows) == 1


def test_ci_scorecards_have_twelve_executable_rows():
    paths = (
        "tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json",
        "tasks/reports/runtime/s12-stage-aa/method_ablation_scorecard_v2.json",
    )
    for path in paths:
        payload = json.loads(open(path, encoding="utf-8").read())
        assert executable_row_count(payload["rows"]) >= 12


def test_existing_dashboard_port_base_is_overridable_without_changing_default(monkeypatch):
    import review_packages.serve_dashboards as dashboards

    monkeypatch.setenv("S12_REVIEW_PORT_BASE", "8188")
    overridden = importlib.reload(dashboards)
    assert [server["port"] for server in overridden.SERVERS[1:]] == [8188, 8189, 8190, 8191]

    monkeypatch.delenv("S12_REVIEW_PORT_BASE")
    restored = importlib.reload(dashboards)
    assert [server["port"] for server in restored.SERVERS[1:]] == [8088, 8089, 8090, 8091]


def test_review_server_accepts_concurrent_slow_html_clients():
    from review_packages.serve_dashboards import ReusableTCPServer

    assert issubclass(ReusableTCPServer, socketserver.ThreadingMixIn)
    assert ReusableTCPServer.daemon_threads is True
