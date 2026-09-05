from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.canonical_renderer import apply_package_monitor_gain, package_gain_db
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.ir_assets import IrAssetSpec, load_ir_asset
from tools.sound_sim.s12.acoustic_identity_v015.stage_ae.partitioned_convolver import UniformPartitionedConvolver
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
