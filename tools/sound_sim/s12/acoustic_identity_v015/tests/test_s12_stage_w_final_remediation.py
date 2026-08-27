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


def _copy_bakeoff_for_validation(tmp_path):
    import shutil
    from pathlib import Path
    source = Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "s12-stage-w" / "bakeoff_final_remediation_v5"
    destination = tmp_path / "bakeoff"
    shutil.copytree(source, destination)
    return destination


def test_bakeoff_validator_rejects_non_null_selection(tmp_path) -> None:
    import json
    root = _copy_bakeoff_for_validation(tmp_path)
    path = root / "bakeoff_results.json"
    payload = json.loads(path.read_text(encoding="utf-8")); payload["selected_architecture"] = "P3"; path.write_text(json.dumps(payload), encoding="utf-8")
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import validate_bakeoff_manifest
    assert "selection" in " ".join(validate_bakeoff_manifest(root))


def test_bakeoff_validator_rejects_unexpected_status_or_reference(tmp_path) -> None:
    import json
    root = _copy_bakeoff_for_validation(tmp_path)
    path = root / "bakeoff_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8")); payload["status"] = "R2_DIAGNOSTIC_READY"; payload["reference_status"] = "EXTERNAL_R2_POINTER"; path.write_text(json.dumps(payload), encoding="utf-8")
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import validate_bakeoff_manifest
    errors = " ".join(validate_bakeoff_manifest(root))
    assert "status" in errors and "reference_status" in errors


def test_bakeoff_validator_rejects_missing_state_file(tmp_path) -> None:
    root = _copy_bakeoff_for_validation(tmp_path)
    (root / "ablation_results.json").unlink()
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import validate_bakeoff_manifest
    assert any("ablation_results" in item for item in validate_bakeoff_manifest(root))


def test_bakeoff_validator_rejects_contradictory_summary_fields(tmp_path) -> None:
    import json
    root = _copy_bakeoff_for_validation(tmp_path)
    path = root / "selected_architecture.json"
    payload = json.loads(path.read_text(encoding="utf-8")); payload["status"] = "R2_DIAGNOSTIC_READY"; path.write_text(json.dumps(payload), encoding="utf-8")
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import validate_bakeoff_manifest
    assert any("selected_architecture" in item or "status" in item for item in validate_bakeoff_manifest(root))


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


def test_geometry_and_firing_order_are_phase_authorities_for_piston() -> None:
    import copy
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.event_scheduler import derive_event_phase_deg
    base = load_config("hellcat_v1")
    altered_order = copy.deepcopy(base)
    altered_order["firing_order_evidence"]["value"] = list(reversed(altered_order["firing_order_evidence"]["value"]))
    altered_geometry = copy.deepcopy(base)
    altered_geometry["crankpin_geometry"]["value"][0] += 13.0
    assert derive_event_phase_deg(base) != derive_event_phase_deg(altered_order)
    assert derive_event_phase_deg(base) != derive_event_phase_deg(altered_geometry)


def test_rotary_uses_explicit_rotor_geometry_without_piston_firing_order() -> None:
    import copy
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.event_scheduler import derive_event_phase_deg
    base = load_config("rx7_fd_v1")
    altered = copy.deepcopy(base)
    altered["rotor_geometry"]["value"][1] = 210.0
    altered["firing_order_evidence"]["value"] = [2, 1]
    assert derive_event_phase_deg(base) != derive_event_phase_deg(altered)


def test_transfer_ir_and_collector_assignment_are_consumed() -> None:
    import copy
    import hashlib
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    state = {"rpm": np.array([2400.0]), "load": np.array([0.5]), "throttle": np.array([0.6]), "acceleration_mps2": np.array([2.0])}
    base = load_config("hellcat_v1")
    changed = copy.deepcopy(base)
    changed["collector_assignment"]["value"] = "central_first"
    changed["transfer_ir"]["value"] = "synthetic_long_damped_transfer"
    first = PersistentEventDomainEngine(base, 48000, 960)
    second = PersistentEventDomainEngine(changed, 48000, 960)
    assert hashlib.sha256(first.process(state).raw_pcm.tobytes()).hexdigest() != hashlib.sha256(second.process(state).raw_pcm.tobytes()).hexdigest()
    assert second.diagnostics()["parameter_consumption"]["collector_assignment"] is True
    assert second.diagnostics()["parameter_consumption"]["transfer_ir"] is True


def test_collector_assignment_and_transfer_ir_are_independent_consumption_controls() -> None:
    import copy
    import hashlib
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    state = {"rpm": np.array([2400.0]), "load": np.array([0.5]), "throttle": np.array([0.6]), "acceleration_mps2": np.array([2.0])}
    base = load_config("hellcat_v1")
    topology = copy.deepcopy(base)
    ir = copy.deepcopy(base)
    topology["collector_assignment"]["value"] = "central_first"
    ir["transfer_ir"]["value"] = "synthetic_long_damped_transfer"
    base_audio = PersistentEventDomainEngine(base, 48000, 960).process(state).raw_pcm
    topology_engine = PersistentEventDomainEngine(topology, 48000, 960)
    ir_engine = PersistentEventDomainEngine(ir, 48000, 960)
    topology_audio = topology_engine.process(state).raw_pcm
    ir_audio = ir_engine.process(state).raw_pcm
    assert hashlib.sha256(base_audio.tobytes()).hexdigest() != hashlib.sha256(topology_audio.tobytes()).hexdigest()
    assert hashlib.sha256(base_audio.tobytes()).hexdigest() != hashlib.sha256(ir_audio.tobytes()).hexdigest()
    assert topology_engine.diagnostics()["parameter_consumption"]["collector_assignment"] is True
    assert ir_engine.diagnostics()["parameter_consumption"]["transfer_ir"] is True


def test_legacy_config_missing_path_parameters_uses_recorded_identity_fallbacks() -> None:
    import copy
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    config = load_config("hellcat_v1")
    config.pop("transfer_ir", None)
    config.pop("collector_assignment", None)
    engine = PersistentEventDomainEngine(config, 48000, 960)
    engine.process({"rpm": np.array([2400.0]), "load": np.array([0.5]), "throttle": np.array([0.6]), "acceleration_mps2": np.array([2.0])})
    assert set(engine.diagnostics()["parameter_fallbacks"]) == {"transfer_ir", "collector_assignment"}


def test_cycle_definition_and_bank_assignment_drive_explicit_path_readback_not_false_phase() -> None:
    import copy
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.event_scheduler import derive_event_phase_deg, derive_event_path_schedule
    base = load_config("hellcat_v1")
    cycle = copy.deepcopy(base)
    cycle["cycle_definition"]["value"] = "four_stroke_1080"
    banks = copy.deepcopy(base)
    banks["bank_assignment"]["value"] = [1, 0, 1, 0, 1, 0, 1, 0]
    assert derive_event_phase_deg(base) != derive_event_phase_deg(cycle)
    assert derive_event_phase_deg(base) == derive_event_phase_deg(banks)
    assert derive_event_path_schedule(base) != derive_event_path_schedule(banks)


def test_timbre_bypass_and_crank_inertia_are_persistent_and_finite() -> None:
    import copy
    import hashlib
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    base = load_config("hellcat_v1")
    heavy = copy.deepcopy(base)
    heavy["crank_inertia"]["value"] = 1.8
    high = {"rpm": np.array([5200.0]), "load": np.array([0.92]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([4.0])}
    closure = {"rpm": np.array([4700.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    normal = PersistentEventDomainEngine(base, 48000, 960, forced_induction_model="timbre_map_v1")
    altered = PersistentEventDomainEngine(heavy, 48000, 960, forced_induction_model="timbre_map_v1")
    normal.process(high); altered.process(high)
    normal_audio = normal.process(closure).raw_pcm
    altered_audio = altered.process(closure).raw_pcm
    assert hashlib.sha256(normal_audio.tobytes()).hexdigest() != hashlib.sha256(altered_audio.tobytes()).hexdigest()
    assert np.all(np.isfinite(altered_audio))
    assert altered.diagnostics()["timbre_inertia_state"] >= 0.0


def test_timbre_inertia_changes_all_layers_without_gain_confound() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import render_timbre_map
    config = load_config("hellcat_v1")
    phase = np.linspace(0.0, 10.0 * np.pi, 960)
    inputs = (phase, np.full(960, 4200.0), np.full(960, 0.7), np.full(960, 0.6), np.full(960, 0.8))
    low = render_timbre_map(*inputs, config, inertia_state=0.0)
    high = render_timbre_map(*inputs, config, inertia_state=1.0)
    for key in ("blower", "sidebands", "broadband", "casing", "intake"):
        assert not np.array_equal(low[key], high[key])
        assert np.all(np.isfinite(high[key]))


def test_timbre_bypass_changes_all_forced_layers_without_inertia_confound() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import render_timbre_map
    config = load_config("hellcat_v1")
    phase = np.linspace(0.0, 10.0 * np.pi, 960)
    common = (phase, np.full(960, 4200.0), np.full(960, 0.7), np.full(960, 0.6))
    open_map = render_timbre_map(*common, np.full(960, 0.95), config, inertia_state=0.5)
    closed_map = render_timbre_map(*common, np.full(960, 0.02), config, inertia_state=0.5)
    for key in ("blower", "sidebands", "broadband", "casing", "intake"):
        assert not np.array_equal(open_map[key], closed_map[key])


def test_click_metrics_use_block_boundaries_and_versioned_contract() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960)
    block = engine.process({"rpm": np.array([2400.0, 2500.0]), "load": np.array([0.4, 0.5]), "throttle": np.array([0.5, 0.6]), "acceleration_mps2": np.array([1.0, 1.0])})
    click = block.diagnostics["click_metrics"]
    assert click["definition"] == "block_boundary_only"
    assert click["contract_version"]
    assert click["provenance"] == "bounded_synthetic_engineering_acceptance_threshold"


def test_p5_transient_is_part_of_persistent_engine_monitor_result() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, ptr_enabled=True)
    state = {"rpm": np.array([4200.0]), "load": np.array([0.7]), "throttle": np.array([0.8]), "acceleration_mps2": np.array([3.0])}
    transient = np.zeros((960, 2), dtype=np.float64)
    transient[10] = [0.1, 0.2]
    baseline = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, ptr_enabled=True).process(state)
    block = engine.process(state, external_transient=transient)
    assert block.diagnostics["monitor_source"] == "PersistentEventDomainEngine.monitor_pcm"
    assert not np.array_equal(block.post_ptr_raw, baseline.post_ptr_raw)
    assert not np.array_equal(block.monitor_pcm, baseline.monitor_pcm)


def test_click_contract_rejects_metadata_drift_but_accepts_finite_threshold_override() -> None:
    import copy
    import pytest
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import click_gate_contract
    base = click_gate_contract()
    changed = copy.deepcopy(base)
    changed["threshold"] = 0.20
    assert click_gate_contract({"click_gate": changed})["threshold"] == 0.20
    for key in ("contract_version", "definition", "scope", "provenance"):
        bad = copy.deepcopy(base)
        bad[key] = "drift"
        with pytest.raises(ValueError, match="click gate"):
            click_gate_contract({"click_gate": bad})


def test_shared_click_helper_uses_only_block_boundary_indices() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
    signal = np.zeros((1920, 2), dtype=np.float64)
    signal[100] = 1.0
    signal[960] = 0.2
    metrics = block_boundary_click_metrics(signal, 960)
    assert metrics["max_boundary_jump"] == 0.2
    assert metrics["definition"] == "block_boundary_only"


def test_shared_click_helper_uses_nonzero_previous_block_end_sample() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
    signal = np.zeros((1920, 2), dtype=np.float64)
    signal[959] = [0.1, -0.1]
    signal[960] = [0.4, -0.4]
    assert block_boundary_click_metrics(signal, 960)["max_boundary_jump"] == pytest.approx(0.3)


def test_click_helper_normalized_boundary_rms_is_numeric() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
    signal = np.zeros((1920, 2), dtype=np.float64)
    signal[959] = [0.1, 0.1]
    signal[960] = [0.3, 0.3]
    metrics = block_boundary_click_metrics(signal, 960)
    assert metrics["normalized_rms_boundary"] == pytest.approx(np.sqrt(2.0 * 0.2**2) / np.sqrt(2.0 * (0.3**2 + 0.1**2) / 1920.0), rel=1e-12)


def test_click_contract_scope_explicitly_covers_raw_post_ptr_and_monitor() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import click_gate_contract
    contract = click_gate_contract()
    assert all(token in contract["scope"] for token in ("raw", "post_ptr", "monitor"))


def test_click_contract_rejects_nan_threshold() -> None:
    import math
    import pytest
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import click_gate_contract
    with pytest.raises(ValueError, match="threshold"):
        click_gate_contract({"click_gate": {"threshold": math.nan}})


def test_click_contract_rejects_positive_infinite_threshold() -> None:
    import math
    import pytest
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import click_gate_contract
    with pytest.raises(ValueError, match="threshold"):
        click_gate_contract({"click_gate": {"threshold": math.inf}})


def test_click_contract_rejects_negative_infinite_threshold() -> None:
    import math
    import pytest
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import click_gate_contract
    with pytest.raises(ValueError, match="threshold"):
        click_gate_contract({"click_gate": {"threshold": -math.inf}})


def test_click_contract_rejects_nonpositive_thresholds() -> None:
    import pytest
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import click_gate_contract
    for value in (0.0, -0.01):
        with pytest.raises(ValueError, match="threshold"):
            click_gate_contract({"click_gate": {"threshold": value}})


def test_collector_assignment_alone_changes_path_readback_not_combustion_phase() -> None:
    import copy
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.event_scheduler import derive_event_path_schedule, derive_event_phase_deg
    base = load_config("hellcat_v1")
    changed = copy.deepcopy(base)
    changed["collector_assignment"]["value"] = "central_first"
    assert derive_event_phase_deg(base) == derive_event_phase_deg(changed)
    base_paths = derive_event_path_schedule(base)
    changed_paths = derive_event_path_schedule(changed)
    assert [(item["collector_slot"], item["path_id"]) for item in base_paths] != [(item["collector_slot"], item["path_id"]) for item in changed_paths]


def test_afterfire_route_uses_scheduled_entity_bank_and_stereo_topology() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    config = load_config("hellcat_v1")
    high = {"rpm": np.array([6200.0]), "load": np.array([0.90]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([0.0])}
    lift = {"rpm": np.array([5800.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    seen = {}
    for policy in ("primary", "bank_collector", "central_collector"):
        engine = PersistentEventDomainEngine(config, 48000, 960, path_model="waveguide_v1")
        engine.afterfire_location_policy = policy
        engine.process(high)
        outputs = [engine.process(lift).raw_pcm for _ in range(30)]
        block = type("Block", (), {"diagnostics": engine.diagnostics()})()
        route = block.diagnostics["afterfire_route"]
        seen[policy] = np.concatenate(outputs, axis=0)
        assert route["entity"] in range(engine.entity_count)
        if policy != "central_collector":
            assert route["bank_id"] == config["bank_assignment"]["value"][route["entity"]]
            assert route["path_id"].endswith(str(route["bank_id"])) or policy == "primary"
    assert not np.array_equal(seen["primary"], seen["bank_collector"])
    assert not np.array_equal(seen["bank_collector"], seen["central_collector"])


def test_afterfire_route_stereo_contributions_are_directly_topology_bound() -> None:
    import copy
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    high = {"rpm": np.array([6200.0]), "load": np.array([0.90]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([0.0])}
    lift = {"rpm": np.array([5800.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    base = load_config("hellcat_v1")
    silent = copy.deepcopy(base); silent["afterfire"]["gain"]["value"] = 0.0
    deltas = {}
    for policy in ("primary", "bank_collector", "central_collector"):
        route = PersistentEventDomainEngine(base, 48000, 960, path_model="waveguide_v1"); route.afterfire_location_policy = policy
        control = PersistentEventDomainEngine(silent, 48000, 960, path_model="waveguide_v1"); control.afterfire_location_policy = policy
        route.process(high); control.process(high)
        routed = [route.process(lift).raw_pcm for _ in range(30)]
        baseline = [control.process(lift).raw_pcm for _ in range(30)]
        deltas[policy] = np.concatenate(routed) - np.concatenate(baseline)
    assert np.max(np.abs(deltas["central_collector"][:, 0] - deltas["central_collector"][:, 1])) < 1.0e-12
    assert np.max(np.abs(deltas["primary"][:, 0] - deltas["primary"][:, 1])) > 1.0e-8
    assert np.max(np.abs(deltas["bank_collector"][:, 0] - deltas["bank_collector"][:, 1])) > 1.0e-8


def test_local_bounded_jitter_rng_snapshots_and_resets_deterministically() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    config = load_config("hellcat_v1")
    state = {"rpm": np.array([6200.0]), "load": np.array([0.9]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([0.0])}
    lift = {"rpm": np.array([5800.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])}
    engine = PersistentEventDomainEngine(config, 48000, 960, random_seed=17, jitter_fraction=0.1)
    engine.process(state); snapshot = engine.snapshot_state(); expected = engine.process(lift).raw_pcm
    engine.restore_state(snapshot)
    assert np.array_equal(expected, engine.process(lift).raw_pcm)
    engine.reset("hard"); first = engine.process(state).raw_pcm
    engine.reset("hard"); assert np.array_equal(first, engine.process(state).raw_pcm)
    assert engine.diagnostics()["random_state"]["provenance"] == "bounded_local_pcg64_only"


def test_timbre_map_is_bounded_four_dimensional_and_order_synchronous() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import TimbreMap4D
    table = TimbreMap4D.default()
    low = table.sample(1200.0, 0.2, 0.1, 2.0)
    high = table.sample(6200.0, 0.8, 0.9, 4.0)
    assert np.isfinite(low) and np.isfinite(high)
    assert low != high
    assert table.sample(3200.0, 0.5, 0.4, 2.0) != table.sample(3200.0, 0.5, 0.4, 4.0)


def test_engine_records_block_boundary_click_metrics_and_monitor_state() -> None:
    import numpy as np
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
    from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960)
    state = {"rpm": np.array([2400.0, 2500.0]), "load": np.array([0.4, 0.5]), "throttle": np.array([0.5, 0.6]), "acceleration_mps2": np.array([1.0, 1.0])}
    block = engine.process(state)
    metrics = block.diagnostics["click_metrics"]
    assert {"max_boundary_jump", "normalized_rms_boundary", "threshold", "passed"} <= set(metrics)
    assert np.isfinite(metrics["max_boundary_jump"])
    assert block.monitor_pcm.shape == block.raw_pcm.shape
