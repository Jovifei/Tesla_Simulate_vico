from __future__ import annotations

import json

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.canonical_renderer import CanonicalStageAERenderer, apply_package_monitor_gain, package_gain_db
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.ir_assets import IrAssetSpec, load_ir_asset
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.parameter_fit import family_parameters, apply_overrides, validate_caseset_identity
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.partitioned_convolver import UniformPartitionedConvolver
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.package_audition import _standalone_html, _resolve_fit_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.vehicle_profiles import build_standard_trace


def test_partitioned_convolver_matches_direct_fir_prefix():
    rng=np.random.default_rng(4); x=rng.normal(size=137); h=rng.normal(size=31); conv=UniformPartitionedConvolver(h,partition_size=16).process(x); expected=np.convolve(x,h)[:x.size]; assert np.allclose(conv,expected,atol=1e-9,rtol=1e-9)


def test_package_gain_is_one_attenuation_only_value_for_all_scenes():
    scenes={"idle":np.ones((64,2))*0.2,"wot":np.ones((64,2))*1.4}; gain=package_gain_db(scenes,0.94); out,reported=apply_package_monitor_gain(scenes,0.94); assert gain==reported and gain<0.0; assert np.isclose(np.max(np.abs(out["wot"])),0.94); assert np.isclose(np.max(np.abs(out["idle"]))/np.max(np.abs(out["wot"])),0.2/1.4)


def test_stage_ae_vehicle_configs_validate():
    assert load_config("lfa_v1")["vehicle_id"]=="lfa_v1"; assert load_config("gtr_r35_v1")["vehicle_id"]=="gtr_r35_v1"


def test_standard_trace_is_deterministic_and_finite():
    first=build_standard_trace("lfa","full_pull",1.0); second=build_standard_trace("lfa","full_pull",1.0)
    for key in first: assert np.array_equal(first[key],second[key]) and np.all(np.isfinite(first[key]))


def test_unverified_ir_is_rejected_for_product(tmp_path):
    spec=IrAssetSpec("x",tmp_path/"x.wav","0"*64,"https://example.invalid","RESEARCH_DIAGNOSTIC_ONLY","diagnostic","none")
    with pytest.raises(PermissionError): load_ir_asset(spec,use="product")


def test_generic_family_parameters_and_overrides_are_config_valid():
    cfg=load_config("gtr_r35_v1"); params=family_parameters(cfg,"induction"); assert params
    changed=apply_overrides(cfg,{params[0].name:(params[0].minimum+params[0].maximum)/2.0},params); assert changed["vehicle_id"]=="gtr_r35_v1"


def test_canonical_renderer_is_deterministic_for_same_seed():
    trace=build_standard_trace("hellcat","hot_idle",0.08); a=CanonicalStageAERenderer("hellcat_v1",random_seed=77).render(trace).post_ptr_pcm; b=CanonicalStageAERenderer("hellcat_v1",random_seed=77).render(trace).post_ptr_pcm; assert np.array_equal(a,b)


def test_stage_ae_dashboard_has_no_remote_runtime_dependency():
    html=_standalone_html("test",[{"scene":"idle","candidate_b64":"data:audio/wav;base64,AA==","reference_b64":""}]); assert "https://" not in html and "http://" not in html and "<script src=" not in html


def test_caseset_vehicle_identity_is_fail_closed():
    validate_caseset_identity({"vehicle_id":"lfa"},"lfa")
    with pytest.raises(ValueError): validate_caseset_identity({"vehicle_id":"gtr_r35"},"lfa")


def test_audition_resolves_final_family_fit_and_hashes_it(tmp_path):
    config_path=tmp_path/"lfa"/"afterfire"/"final_r3_diagnostic_fit.json"; config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(load_config("lfa_v1"),ensure_ascii=False),encoding="utf-8")
    config, source, digest=_resolve_fit_config(tmp_path,"lfa")
    assert config is not None and config["vehicle_id"]=="lfa_v1"
    assert source==str(config_path)
    assert digest and len(digest)==64
