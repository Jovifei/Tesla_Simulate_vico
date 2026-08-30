from pathlib import Path
import json
import hashlib
import copy
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_map_fit import fit_harmonic_map, MAP_SCHEMA
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.timbre_map import TimbreMap4D


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
