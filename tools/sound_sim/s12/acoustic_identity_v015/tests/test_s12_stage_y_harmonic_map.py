from pathlib import Path
import json
import hashlib
import copy
import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
from tools.sound_sim.s12.acoustic_identity_v015.stage_y import harmonic_map_fit
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_map_fit import fit_harmonic_map, MAP_SCHEMA
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import _render_architecture, build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import TimbreMap4D


def test_committed_fixture_map_loader_is_deterministic_and_fail_closed(tmp_path) -> None:
    build = getattr(harmonic_map_fit, "build_committed_fixture_timbre_map", None)
    load = getattr(harmonic_map_fit, "load_committed_fixture_timbre_map", None)
    assert callable(build), "Y2 requires a deterministic committed-map builder"
    assert callable(load), "Y2 requires a fail-closed committed-map loader"

    path = tmp_path / "hellcat_fixture_timbre_map.json"
    created_from_commit = "a" * 40
    build(path, created_from_commit=created_from_commit)
    assert b"\r\n" not in path.read_bytes()
    payload, table = load(path)
    assert payload["schema"] == MAP_SCHEMA
    assert payload["vehicle_id"] == "hellcat"
    assert payload["source"] == "synthetic_fixture"
    assert payload["created_from_commit"] == created_from_commit
    assert payload["boundary"] == {
        "fixture_scope": "FIXTURE_ONLY",
        "oem_status": "NOT_OEM",
        "tuning_authority": "NOT_TUNING_AUTHORITY",
    }
    assert table.values.shape == (4, 3, 3, 5)
    assert np.all(table.values >= 0.0)

    for field, value in (("schema", "wrong.schema"), ("fixture_sha256", "0" * 64), ("amplitude", [[[[float("nan")]]]])):
        corrupt = copy.deepcopy(payload)
        corrupt[field] = value
        path.write_text(json.dumps(corrupt), encoding="utf-8")
        with pytest.raises(ValueError):
            load(path)


def test_fixture_bank_is_deterministic_and_not_pcm_in_map(tmp_path) -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    assert set(bank["rpm_hz"].keys()) >= {1200.0, 2000.0, 3000.0}
    again = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    assert hashlib.sha256(bank["cycles"][1200.0].tobytes()).hexdigest() == hashlib.sha256(again["cycles"][1200.0].tobytes()).hexdigest()
    mapped = fit_harmonic_map(bank, vehicle_id="hellcat")
    assert mapped["schema"] == MAP_SCHEMA
    assert mapped["source"] == "synthetic_fixture"
    assert "pcm" not in mapped
    text = json.dumps(mapped)
    assert "int16" not in text
    path = tmp_path / "hellcat_timbre_map.json"
    path.write_text(json.dumps(mapped), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["vehicle_id"] == "hellcat"


def test_hellcat_runtime_rejects_formula_default_when_map_required() -> None:
    config = load_config("hellcat_v1")
    config["require_fitted_timbre_map"] = True
    try:
        PersistentEventDomainEngine(config, 48000, 960, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1")
        raised = False
    except ValueError as error:
        raised = "fitted" in str(error).lower() or "timbre" in str(error).lower()
    assert raised is True


def test_fitted_map_changes_sha_versus_formula(tmp_path) -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    mapped = fit_harmonic_map(bank, vehicle_id="hellcat")
    formula = load_config("hellcat_v1")
    fitted = copy.deepcopy(formula)
    fitted["timbre_map"] = {
        "rpm_axis": mapped["rpm_axis"],
        "load_axis": mapped["load_axis"],
        "boost_axis": mapped["boost_axis"],
        "order_axis": mapped["order_axis"],
        "values": mapped["amplitude"],
    }
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    a = PersistentEventDomainEngine(formula, 48000, 960, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1").process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    b = PersistentEventDomainEngine(fitted, 48000, 960, ptr_enabled=True, path_model="waveguide_v1", forced_induction_model="timbre_map_v1").process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
    assert hashlib.sha256(a.post_ptr_raw.tobytes()).hexdigest() != hashlib.sha256(b.post_ptr_raw.tobytes()).hexdigest()


def test_bakeoff_injects_committed_map_only_for_stage_y_timbre_architectures() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 0.20)
    _p2_raw, _p2_post, _p2_monitor, p2_diagnostics = _render_architecture("P2", trace)
    _p3_raw, _p3_post, _p3_monitor, p3_diagnostics = _render_architecture("P3", trace)
    assert "fitted_timbre_map_schema" not in p2_diagnostics
    assert p3_diagnostics["fitted_timbre_map_schema"] == MAP_SCHEMA
    assert len(p3_diagnostics["fitted_timbre_map_fixture_sha256"]) == 64
