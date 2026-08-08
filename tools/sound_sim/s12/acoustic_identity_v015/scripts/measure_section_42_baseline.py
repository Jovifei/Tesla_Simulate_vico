# tools/sound_sim/s12/acoustic_identity_v015/scripts/measure_section_42_baseline.py
"""测量三锚点 §4.2 粗调门禁基准，写出 deep_realism_section_42_baseline.json。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from acoustic_identity_v015.render_identity_v02 import _scenario_trace
from acoustic_identity_v015.sources.flat_plane_v8_source import render_ferrari_458
from acoustic_identity_v015.sources.supercharged_hemi_source import render_hellcat
from acoustic_identity_v015.sources.rotary_turbo_source import render_rx7_fd
from acoustic_identity_v015.acoustic_analysis.spectral_targets import render_state_band_shares

V015 = Path(__file__).resolve().parents[1]
TARGETS = json.loads((V015 / "targets" / "realism_feature_targets.json").read_text(encoding="utf-8"))
RENDERERS = {"ferrari_458": render_ferrari_458, "hellcat": render_hellcat, "rx7_fd": render_rx7_fd}
REF = {vid: TARGETS["vehicles"][vid]["r2_recording_dependent_features"] for vid in RENDERERS}


def main() -> None:
    result = {}
    for vid, renderer in RENDERERS.items():
        vid_res = {}
        for clip in ("idle", "acceleration"):
            trace = _scenario_trace(vid, clip, 3.0)
            render = renderer(trace)
            centroid, shares = render_state_band_shares(render)
            ref = REF[vid][clip]
            if clip == "idle":
                idle_target = ref["spectral_centroid_hz"]
                err_idle = abs(centroid - idle_target)
                gate_idle = max(25.0, idle_target * 0.10)
                vid_res[clip] = {"centroid_hz": centroid, "idle_centroid_error_hz": err_idle,
                                  "idle_centroid_gate_hz": gate_idle, "idle_pass": err_idle <= gate_idle}
            else:
                ref_shares = ref["band_shares"]
                errs = [abs(s - r) for s, r in zip(shares, ref_shares)]
                vid_res[clip] = {"band_shares": shares, "band_abs_errors": errs,
                                 "accel_pass": all(e <= 0.05 for e in errs)}
        result[vid] = vid_res
    out = V015 / "docs" / "deep_realism_section_42_baseline.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
