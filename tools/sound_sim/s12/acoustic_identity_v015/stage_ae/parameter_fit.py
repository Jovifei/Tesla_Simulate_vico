"""Generic Stage-AE family fit on the canonical renderer.

This is diagnostic analysis-by-synthesis. It accepts governed R2/R3 references,
keeps monitor gain out of the objective, and never promotes evidence levels.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile
from scipy.stats import qmc

from ..event_domain.config_schema import load_config, validate_config, unwrap
from ..stage_w.click_contract import block_boundary_click_metrics
from ..stage_x.multi_reference_comparator import compare_case
from .canonical_renderer import CanonicalStageAERenderer
from .vehicle_profiles import VEHICLES, build_standard_trace

_METRIC_FLOORS = {"rms_dbfs":1.0,"peak_dbfs":1.0,"crest_db":1.0,"dynamic_range_db":1.0,"spectral_centroid_hz":100.0,"spectral_flux":0.01,"roughness_proxy":0.05,"sharpness_proxy":0.05,"tonality_proxy":0.05,"persistent_tone_ratio":0.05,"narrowband_whine_proxy":0.02}

@dataclass(frozen=True)
class SearchParameter:
    name: str
    path: str
    family: str
    minimum: float
    maximum: float
    baseline: float


def _node(config: Mapping[str,Any], path: str) -> Any:
    cur: Any = config
    for part in path.split("."):
        cur = cur[part]
    return cur


def _numeric_parameter(config: Mapping[str,Any], path: str, family: str) -> SearchParameter | None:
    try: node=_node(config,path)
    except (KeyError,TypeError): return None
    if not isinstance(node,Mapping) or "value" not in node or not isinstance(node["value"],(int,float)) or isinstance(node["value"],bool): return None
    bounds=node.get("range")
    if not (isinstance(bounds,list) and len(bounds)==2 and all(isinstance(x,(int,float)) for x in bounds)): return None
    lo,hi=float(bounds[0]),float(bounds[1]); base=float(node["value"])
    # Keep searches local even when schema ranges are intentionally broad.
    span=max(abs(base)*0.45, (hi-lo)*0.08, 1e-6)
    return SearchParameter(path.replace(".","_"),path,family,max(lo,base-span),min(hi,base+span),base)


def family_parameters(config: Mapping[str,Any], family: str) -> list[SearchParameter]:
    paths={
        "body":["combustion_event.event_energy","combustion_event.rise_time_s","combustion_event.decay_time_s","cycle_variation"],
        "path":["collector_loss","intake_model","collector_length_m"],
        "induction":["forced_induction.gain","forced_induction.ratio","primary_spool_tau","secondary_spool_tau","blow_off_gain","blow_off_decay"],
        "afterfire":["afterfire.gain","afterfire.cooldown_s","afterfire.ignition_delay_s"],
    }
    if family not in paths: raise ValueError(f"unknown family: {family}")
    params=[p for path in paths[family] if (p:=_numeric_parameter(config,path,family)) is not None]
    if family=="induction" and str(unwrap(config,"forced_induction.type"))=="none": return []
    return params


def apply_overrides(config: Mapping[str,Any], overrides: Mapping[str,float], parameters: list[SearchParameter]) -> dict[str,Any]:
    result=copy.deepcopy(dict(config)); lookup={p.name:p for p in parameters}
    for name,value in overrides.items():
        p=lookup[name]; cur=result; parts=p.path.split(".")
        for part in parts[:-1]: cur=cur[part]
        cur[parts[-1]]["value"]=float(value)
    return validate_config(result)


def _read_reference(case: Mapping[str,Any], sample_rate: int=48000) -> np.ndarray:
    sr,data=wavfile.read(Path(case["audio_path"]))
    if int(sr)!=sample_rate: raise ValueError(f"reference sample rate must be {sample_rate}, got {sr}")
    if data.ndim==1: data=np.column_stack((data,data))
    if np.issubdtype(data.dtype,np.integer): data=data.astype(np.float64)/float(max(abs(np.iinfo(data.dtype).min),np.iinfo(data.dtype).max))
    else: data=data.astype(np.float64)
    start=max(0,int(round(float(case.get("start_s",0.0))*sr))); end=min(data.shape[0],int(round(float(case.get("end_s",data.shape[0]/sr))*sr)))
    return data[start:end]


def _distance(comparison: Mapping[str,Any]) -> float:
    values=[]
    for name,row in dict(comparison.get("metrics") or {}).items():
        ref=float(row["reference"]); cand=float(row["candidate"])
        if not np.isfinite(ref) or not np.isfinite(cand): continue
        floor=0.02 if name.startswith("band_share_") else _METRIC_FLOORS.get(name,0.01)
        values.append(float(np.clip(abs(cand-ref)/max(abs(ref),floor),0.0,10.0)))
    return float(np.median(values)) if values else float("nan")


def load_caseset(path: str|Path, vehicle_key: str) -> tuple[dict[str,np.ndarray],str]:
    payload=json.loads(Path(path).read_text(encoding="utf-8")); effective=str(payload.get("reference_evidence_level") or "UNKNOWN")
    refs={}
    for case in payload.get("cases",[]):
        if case.get("status") not in {None,"BOUND","ACCEPTED"}: continue
        if case.get("evidence_level") not in {"R2","R3"}: continue
        refs[str(case["scenario"])]=_read_reference(case)
    if not refs: raise ValueError("no eligible R2/R3 references in caseset")
    return refs,effective


def evaluate_config(vehicle_key: str, config: Mapping[str,Any], references: Mapping[str,np.ndarray], seed: int=20260905, duration_s: float=2.0) -> dict[str,Any]:
    profile=VEHICLES[vehicle_key]; distances=[]; scene_rows={}; all_clicks=True; all_finite=True
    renderer=CanonicalStageAERenderer(profile.config_id,random_seed=seed,config_override=config)
    for scene,ref in references.items():
        if scene not in {"afterfire","full_pull","hot_idle","idle_return","lift","shift","steady_high","steady_low","steady_mid","tip_in"}: continue
        cand=renderer.render(build_standard_trace(vehicle_key,scene,duration_s)).post_ptr_pcm
        n=min(len(ref),len(cand)); ref_trim=ref[:n]; cand_trim=cand[:n]
        finite=bool(np.all(np.isfinite(cand_trim))); click=block_boundary_click_metrics(cand_trim,960); all_finite &= finite; all_clicks &= bool(click["passed"])
        comp=compare_case(ref_trim,cand_trim,cand_trim,48000,candidate_id=f"{vehicle_key}_stage_ae")
        dist=_distance(comp); scene_rows[scene]={"distance":dist,"peak":float(np.max(np.abs(cand_trim))) if n else 0.0,"click_passed":bool(click["passed"])}
        if np.isfinite(dist): distances.append(dist)
    return {"median_distance":float(np.median(distances)) if distances else float("nan"),"scene_results":scene_rows,"passed_gates":bool(all_finite and all_clicks)}


def run_family_fit(vehicle_key: str, caseset_path: str|Path, family: str, output_dir: str|Path, samples: int=16, seed: int=20260905, base_config_path: str|Path|None=None) -> dict[str,Any]:
    if vehicle_key not in VEHICLES: raise ValueError(vehicle_key)
    profile=VEHICLES[vehicle_key]
    config=json.loads(Path(base_config_path).read_text(encoding="utf-8")) if base_config_path else load_config(profile.config_id)
    config=validate_config(config); refs,evidence=load_caseset(caseset_path,vehicle_key); params=family_parameters(config,family)
    baseline=evaluate_config(vehicle_key,config,refs,seed); best_cfg=copy.deepcopy(config); best_eval=baseline; best_overrides={}
    if params:
        exponent=int(np.ceil(np.log2(max(2,samples)))); points=qmc.Sobol(d=len(params),scramble=True,seed=seed).random_base2(exponent)[:samples]
        for point in points:
            overrides={p.name:float(p.minimum+u*(p.maximum-p.minimum)) for p,u in zip(params,point)}
            trial=apply_overrides(config,overrides,params); result=evaluate_config(vehicle_key,trial,refs,seed)
            if result["passed_gates"] and np.isfinite(result["median_distance"]) and result["median_distance"] < best_eval["median_distance"]:
                best_cfg,best_eval,best_overrides=trial,result,overrides
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    final_path=out/"final_r3_diagnostic_fit.json"; final_path.write_text(json.dumps(best_cfg,indent=2,ensure_ascii=False),encoding="utf-8")
    receipt={"schema":"s12.stage_ae.family_fit.v1","vehicle":vehicle_key,"family":family,"reference_evidence":evidence,"evidence_promotion":False,"baseline_distance":baseline["median_distance"],"final_absolute_reference_distance":best_eval["median_distance"],"best_overrides":best_overrides,"passed_gates":best_eval["passed_gates"],"output_config":str(final_path)}
    (out/"family_fit_receipt.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding="utf-8")
    return receipt
