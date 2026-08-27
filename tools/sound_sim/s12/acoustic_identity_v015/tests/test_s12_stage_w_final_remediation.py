"""RED contracts for the final Stage-W-C remediation wave."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[5]


def test_stage_w_raw_logs_have_scoped_opaque_attributes() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "tasks/reports/runtime/s12-stage-w/logs/*.log" in attributes
    assert "-text" in attributes
    assert "-diff" in attributes
    assert "-whitespace" in attributes


def test_final_track_p_guard_is_clean_after_committed_log_attributes() -> None:
    guard = ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "scripts" / "assert_track_p_unchanged.py"
    result = subprocess.run(["python", str(guard)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_w9_named_raw_log_bytes_are_not_rewritten() -> None:
    receipt = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w" / "phase_receipts" / "W9_FINAL_QUALIFICATION.json"
    import json
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    for name, expected in payload.get("checks", {}).get("logs", {}).items():
        path = ROOT / "tasks" / "reports" / "runtime" / "s12-stage-w" / "logs" / name
        if path.is_file():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_track_s_boundary_adapter_accepts_expected_frozen_package_sha() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.boundary_adapter import StageWBoundaryAdapter
    adapter = StageWBoundaryAdapter(48000)
    assert adapter.provenance()["radiation_package_sha256"] == StageWBoundaryAdapter.EXPECTED_PACKAGE_SHA256


def test_track_s_boundary_adapter_rejects_mismatched_frozen_package_sha() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.boundary_adapter import StageWBoundaryAdapter
    with pytest.raises(ValueError, match="radiation package SHA"):
        StageWBoundaryAdapter(48000, expected_package_sha256="0" * 64)


def test_afterfire_queue_preserves_delay_across_blocks_and_snapshot_restore() -> None:
    import copy
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    config = load_config("hellcat_v1")
    config["afterfire"]["ignition_delay_s"]["value"] = 0.045
    engine = PersistentEventDomainEngine(config, 48000, 960)
    high = {"rpm": np.array([6200.0]), "load": np.array([0.90]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([0.0])}
    lift = {"rpm": np.array([5800.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    engine.process(high)
    engine.process(lift)
    queued = engine.diagnostics()["afterfire_pending_events"]
    assert queued and queued[0]["scheduled_sample"] - engine.sample_counter > 0
    snapshot = engine.snapshot_state()
    expected = engine.process(high).raw_pcm
    engine.restore_state(snapshot)
    assert np.array_equal(expected, engine.process(high).raw_pcm)


def test_waveguide_has_frequency_dependent_loss() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.waveguide import StatefulWaveguide, WaveguideConfig
    t = np.arange(4096, dtype=np.float64) / 48000.0
    low = np.sin(2 * np.pi * 180 * t)
    high = np.sin(2 * np.pi * 12000 * t)
    guide = StatefulWaveguide(WaveguideConfig(length_m=0.30, area_ratio=0.7, sample_rate_hz=48000))
    low_out = guide.process(low)
    guide = StatefulWaveguide(WaveguideConfig(length_m=0.30, area_ratio=0.7, sample_rate_hz=48000))
    high_out = guide.process(high)
    assert np.std(high_out[1000:]) < np.std(low_out[1000:])
