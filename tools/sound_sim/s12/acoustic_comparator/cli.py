"""Run dependency-light Stage-M comparison of formal Stage-K PCM package members."""
from __future__ import annotations
import hashlib, io, json, sys, wave, zipfile
from pathlib import Path
import numpy as np
from .core import ComparisonCase, compare_signals

def _pcm24(raw: bytes) -> tuple[np.ndarray,int]:
    with wave.open(io.BytesIO(raw)) as w:
        if (w.getnchannels(),w.getsampwidth())!=(2,3): raise ValueError("expected stereo PCM24")
        data=np.frombuffer(w.readframes(w.getnframes()),np.uint8).reshape(-1,3)
        values=data[:,0].astype(np.int32)|(data[:,1].astype(np.int32)<<8)|(data[:,2].astype(np.int32)<<16)
        values=np.where(values&0x800000,values-(1<<24),values).astype(np.float64)/(1<<23)
        return values.reshape(-1,2),w.getframerate()

def compare_packages(roots: list[Path]) -> dict[str,object]:
    vehicles={}
    for root in roots:
        manifest=json.loads((root/"artifact_manifest.json").read_text(encoding="utf-8"))
        archive=next(root.glob("*.zip"))
        with zipfile.ZipFile(archive) as z:
            for vehicle_id, record in manifest["vehicles"].items():
                formal=record["formal"]; parent=formal.get("parent", formal["baseline"]); candidate=formal["candidate"]
                p_raw=z.read(parent["path"].replace("\\","/")); c_raw=z.read(candidate["path"].replace("\\","/"))
                p,sr=_pcm24(p_raw); c,sr2=_pcm24(c_raw)
                if sr!=sr2: raise ValueError("sample rate mismatch")
                case=ComparisonCase(vehicle_id,"full_cycle",f"stage_k_parent:{parent.get('sha256',parent.get('pcm_sha256'))}",f"stage_k_candidate:{candidate.get('sha256',candidate.get('pcm_sha256'))}",sr,(0.,0.),(0.,0.),(0.,0.),(0.,0.),"unaltered_analysis_signal")
                result=compare_signals(p,c,case)
                result["comparison_kind"]="synthetic_parent_to_candidate_not_real_reference"
                result["reference_limited"]=True
                result["parent_role"]="parent" if "parent" in formal else "baseline_fallback_parent_missing"
                result["parent_sha256"]=hashlib.sha256(p_raw).hexdigest()
                result["candidate_sha256"]=hashlib.sha256(c_raw).hexdigest()
                vehicles[vehicle_id]=result
    return {"schema_version":"s12-stage-m-comparator-results-1","analysis_domain":"unaltered_final_pcm","vehicles":vehicles,"limitations":["no legally/provenance-bound external reference waveform supplied","full-cycle package comparison is not a scenario/RPM matched real-reference comparison"]}

def main(argv: list[str] | None=None) -> int:
    args=sys.argv[1:] if argv is None else argv
    if len(args)<3: raise SystemExit("usage: python -m tools.sound_sim.s12.acoustic_comparator.cli OUTPUT PACKAGE_ROOT...")
    output=Path(args[0]); payload=compare_packages([Path(x) for x in args[1:]])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    return 0
if __name__=="__main__": raise SystemExit(main())
