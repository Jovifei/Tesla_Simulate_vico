"""Probe reference targets for the 5 remaining vehicles."""
import json
from pathlib import Path

REF = Path(r"E:\Tesla_speed\worktrees\s12-v12\tools\sound_sim\s12\acoustic_identity_v015\reference_database")
for v in ["aventador_lp700", "c63_w204", "gtr_r35", "lfa", "supra_jza80"]:
    d = json.loads((REF / f"{v}_reference_targets.json").read_text(encoding="utf-8"))
    sm = d.get("stock_median", {})
    print(f"=== {v} ===")
    print("  accel bands :", sm.get("acceleration_band_shares"))
    print("  idle bands  :", sm.get("idle_band_shares"))
    print("  idle centroid:", sm.get("idle_spectral_centroid_hz"))
    print("  decel bands :", sm.get("deceleration_band_shares"))
