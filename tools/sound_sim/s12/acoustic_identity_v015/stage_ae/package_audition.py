"""Render deterministic Stage-AE four-vehicle audition packages.

This is the local-AI execution entrypoint.  It renders through the canonical S12
engine, applies one attenuation-only package gain per vehicle, and writes a fully
standalone HTML A/B page with no remote CSS/JS dependency.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.io import wavfile

from .canonical_renderer import CanonicalStageAERenderer, apply_package_monitor_gain
from .ir_assets import load_ir_manifest
from .vehicle_profiles import VEHICLES, SCENES, build_standard_trace


def _wav_bytes(path: Path) -> str:
    return "data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode("ascii") if path.is_file() else ""


def _write_wav(path: Path, pcm: np.ndarray, sample_rate: int = 48000) -> None:
    values = np.clip(np.asarray(pcm,float), -0.999, 0.999)
    wavfile.write(path, sample_rate, (values*32767.0).astype(np.int16))


def _standalone_html(vehicle_name: str, records: list[dict]) -> str:
    cards = []
    store = {}
    for rec in records:
        cid=f"{rec['scene']}_candidate"; rid=f"{rec['scene']}_ref"
        store[cid]=rec['candidate_b64']; store[rid]=rec['reference_b64']
        ref_button = f'<button onclick="play(\'{rid}\')">▶ 真车原声 (B)</button>' if rec['reference_b64'] else '<button disabled>无真车对照</button>'
        cards.append(f'<section><h3>{rec["scene"]}</h3><div class="buttons"><button onclick="play(\'{cid}\')">▶ 算法声音 (A)</button>{ref_button}</div></section>')
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{vehicle_name} Stage AE A/B</title><style>body{{font-family:system-ui;background:#0b0f19;color:#e5e7eb;margin:0;padding:24px}}main{{max-width:980px;margin:auto}}header{{position:sticky;top:0;background:#0b0f19;padding:12px 0;border-bottom:1px solid #334155}}section{{background:#111827;border:1px solid #334155;border-radius:12px;padding:14px;margin:12px 0}}.buttons{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}button{{padding:12px;border-radius:8px;border:1px solid #475569;background:#1f2937;color:#fff;font-weight:700}}button:hover:not(:disabled){{background:#374151}}button:disabled{{opacity:.4}}audio{{width:100%;margin-top:10px}}</style><main><header><h1>{vehicle_name}</h1><p>Stage AE · canonical S12 renderer · package-wide gain · A/B diagnostic</p><audio id="player" controls></audio></header>{''.join(cards)}</main><script>const S={json.dumps(store)};function play(k){{const p=document.getElementById('player');if(!S[k])return;p.src=S[k];p.play();}}</script></html>'''


def render_vehicle(vehicle_key: str, output_dir: Path, reference_root: Path | None, ir_manifest: Path | None, seed: int) -> dict:
    profile = VEHICLES[vehicle_key]
    out = output_dir / vehicle_key
    out.mkdir(parents=True, exist_ok=True)
    ir_spec = load_ir_manifest(ir_manifest) if ir_manifest else None
    renderer = CanonicalStageAERenderer(profile.config_id, random_seed=seed, ir_spec=ir_spec)
    raw = {}
    diagnostics = {}
    for scene in SCENES:
        result = renderer.render(build_standard_trace(vehicle_key, scene))
        raw[scene] = result.post_ptr_pcm
        diagnostics[scene] = result.diagnostics.get("stage_ae", {})
    monitor, gain_db = apply_package_monitor_gain(raw)
    records=[]; files=[]
    for index,scene in enumerate(SCENES,1):
        candidate=out/f"{index:02d}_{scene}.wav"; _write_wav(candidate,monitor[scene]); files.append({"role":"candidate","scene":scene,"path":candidate.name,"sha256":hashlib.sha256(candidate.read_bytes()).hexdigest()})
        ref=None
        if reference_root:
            for candidate_ref in (reference_root/vehicle_key/f"ref_{scene}.wav", reference_root/vehicle_key/"web_audio"/f"ref_{scene}.wav"):
                if candidate_ref.is_file(): ref=candidate_ref; break
        records.append({"scene":scene,"candidate_b64":_wav_bytes(candidate),"reference_b64":_wav_bytes(ref) if ref else ""})
    (out/"index_standalone.html").write_text(_standalone_html(profile.display_name,records),encoding="utf-8")
    manifest={"schema":"s12.stage_ae.audition.v1","vehicle":vehicle_key,"config_id":profile.config_id,"random_seed":seed,"package_gain_db":gain_db,"gain_policy":"ONE_ATTENUATION_ONLY_GAIN_FOR_ALL_SCENES","canonical_renderer":"PersistentEventDomainEngine","ir_asset":ir_spec.asset_id if ir_spec else None,"files":files,"diagnostics":diagnostics}
    (out/"audition_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--vehicle",choices=["all",*VEHICLES],default="all"); parser.add_argument("--output-root",type=Path,required=True); parser.add_argument("--reference-root",type=Path); parser.add_argument("--ir-manifest",type=Path); parser.add_argument("--seed",type=int,default=20260905); args=parser.parse_args(argv)
    keys=list(VEHICLES) if args.vehicle=="all" else [args.vehicle]
    for key in keys: render_vehicle(key,args.output_root,args.reference_root,args.ir_manifest,args.seed)
    return 0

if __name__=="__main__": raise SystemExit(main())
