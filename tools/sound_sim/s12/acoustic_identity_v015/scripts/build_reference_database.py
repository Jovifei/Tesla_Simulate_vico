"""S12 Acoustic Realism Phase 1 - build the per-vehicle real reference database.

Reads externally held R2 recordings from the research folder, extracts the
upgraded feature set for every vehicle, and writes one
``<vehicle>_reference_targets.json`` per car plus a stock_median aggregate.

Boundary: synthetic; uncalibrated; not OEM reproduction.
Public audio stays outside the repository; only derived relative metrics are saved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ACOUTIC_ANALYSIS = _HERE.parent / "acoustic_analysis"
sys.path.insert(0, str(_ACOUTIC_ANALYSIS))

from reference_feature_extractor import (
    extract_reference_features,
    build_vehicle_targets,
    write_targets_json,
)

RESEARCH_DIR = Path(r"E:\Claude_allow\Download\tesla-sound-research")
OUT_DIR = _HERE.parent / "reference_database"

VEHICLES = [
    {
        "vehicle_id": "ferrari_458",
        "display_name": "Ferrari 458 Italia",
        "schema": "s12.ferrari_reference_targets.v1",
        "recordings": [
            {
                "id": "X0yiRilcKME",
                "url": "https://www.youtube.com/watch?v=X0yiRilcKME",
                "setup": "AutoTopNL stock-bias acceleration",
                "include_in_stock_target": True,
                "file": "ferrari_458_accel.wav",
            },
        ],
    },
    {
        "vehicle_id": "rx7_fd",
        "display_name": "Mazda RX-7 FD (13B-REW)",
        "schema": "s12.rx7_reference_targets.v1",
        "recordings": [
            {
                "id": "Thh69Wc5uco",
                "url": "https://www.youtube.com/watch?v=Thh69Wc5uco",
                "setup": "RX-7 FD 13B-REW rotary acceleration",
                "include_in_stock_target": True,
                "file": "rx7_fd_13brew.wav",
            },
        ],
    },
    {
        "vehicle_id": "hellcat",
        "display_name": "Dodge Challenger SRT Hellcat",
        "schema": "s12.hellcat_reference_targets.v1",
        "recordings": [
            {
                "id": "eyzGRhXp0do",
                "url": "https://www.youtube.com/watch?v=eyzGRhXp0do",
                "setup": "AutoTopNL stock road acceleration",
                "include_in_stock_target": True,
                "file": "hellcat_stock_accel.wav",
            },
            {
                "id": "FvORN7EH2cc",
                "url": "https://www.youtube.com/watch?v=FvORN7EH2cc",
                "setup": "Hellcat Redeye brutal downshifts",
                "include_in_stock_target": True,
                "file": "hellcat_redeye_downshift.wav",
                # A downshift clip has no genuine acceleration window; letting it
                # vote would drag the aggregate accel centroid below idle.
                "stock_segments": ["idle", "afterfire"],
            },
            {
                "id": "nnEaamqsieM",
                "url": "https://www.youtube.com/watch?v=nnEaamqsieM",
                "setup": "Hellcat Redeye near-field leave",
                "include_in_stock_target": True,
                "file": "hellcat_redeye_leave.wav",
            },
        ],
    },
    {
        "vehicle_id": "aventador_lp700",
        "display_name": "Lamborghini Aventador LP700-4 (L539 V12 NA)",
        "schema": "s12.aventador_reference_targets.v1",
        "recordings": [
            {
                "id": "aventador_lp700_accel",
                "url": "local:tesla-sound-research/aventador_lp700_accel.wav",
                "setup": "Aventador LP700 full acceleration",
                "include_in_stock_target": True,
                "file": "aventador_lp700_accel.wav",
            },
        ],
    },
    {
        "vehicle_id": "c63_w204",
        "display_name": "Mercedes C63 AMG W204 (M156 V8 NA)",
        "schema": "s12.c63_reference_targets.v1",
        "recordings": [
            {
                "id": "c63_w204_performance_accel",
                "url": "local:tesla-sound-research/c63_w204_performance_accel.wav",
                "setup": "C63 W204 performance acceleration",
                "include_in_stock_target": True,
                "file": "c63_w204_performance_accel.wav",
            },
            {
                "id": "c63_w204_close_downshift",
                "url": "local:tesla-sound-research/c63_w204_close_downshift.wav",
                "setup": "C63 W204 close downshift (afterfire)",
                "include_in_stock_target": True,
                "file": "c63_w204_close_downshift.wav",
                "stock_segments": ["idle", "afterfire"],
            },
            {
                "id": "c63_w204_headers_backfire",
                "url": "local:tesla-sound-research/c63_w204_headers_backfire.wav",
                "setup": "C63 W204 headers backfire pops",
                "include_in_stock_target": False,
                "file": "c63_w204_headers_backfire.wav",
            },
        ],
    },
    {
        "vehicle_id": "gtr_r35",
        "display_name": "Nissan GT-R R35 (VR38DETT V6 twin-turbo)",
        "schema": "s12.gtr_reference_targets.v1",
        "recordings": [
            {
                "id": "gtr_r35_nismo_accel",
                "url": "local:tesla-sound-research/gtr_r35_nismo_accel.wav",
                "setup": "GT-R R35 Nismo acceleration",
                "include_in_stock_target": True,
                "file": "gtr_r35_nismo_accel.wav",
            },
            {
                "id": "gtr_r35_tomei_close",
                "url": "local:tesla-sound-research/gtr_r35_tomei_close.wav",
                "setup": "GT-R R35 Tomei exhaust close (afterfire)",
                "include_in_stock_target": True,
                "file": "gtr_r35_tomei_close.wav",
                "stock_segments": ["idle", "afterfire"],
            },
            {
                "id": "gtr_r35_tuned_backfire",
                "url": "local:tesla-sound-research/gtr_r35_tuned_backfire.wav",
                "setup": "GT-R R35 tuned backfire pops",
                "include_in_stock_target": False,
                "file": "gtr_r35_tuned_backfire.wav",
            },
        ],
    },
    {
        "vehicle_id": "lfa",
        "display_name": "Lexus LFA (1LR-GUE V10 NA)",
        "schema": "s12.lfa_reference_targets.v1",
        "recordings": [
            {
                "id": "lfa_full_accel",
                "url": "local:tesla-sound-research/lfa_full_accel.wav",
                "setup": "LFA full acceleration (angel's cry)",
                "include_in_stock_target": True,
                "file": "lfa_full_accel.wav",
            },
        ],
    },
    {
        "vehicle_id": "supra_jza80",
        "display_name": "Toyota Supra JZA80 (2JZ-GTE I6 twin-turbo)",
        "schema": "s12.supra_reference_targets.v1",
        "recordings": [
            {
                "id": "supra_jza80_stock",
                "url": "local:tesla-sound-research/supra_jza80_stock.wav",
                "setup": "Supra JZA80 2JZ-GTE stock acceleration",
                "include_in_stock_target": True,
                "file": "supra_jza80_stock.wav",
            },
        ],
    },
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for vehicle in VEHICLES:
        vid = vehicle["vehicle_id"]
        print(f"\n=== {vehicle['display_name']} ({vid}) ===")
        recordings = []
        for rec in vehicle["recordings"]:
            wav = RESEARCH_DIR / rec["file"]
            if not wav.exists():
                print(f"  [SKIP] missing: {wav}")
                continue
            print(f"  analyzing {rec['file']} ...")
            feats = extract_reference_features(wav)
            segs = feats["segments"]
            for name, m in segs.items():
                print(f"    {name:12s} [{m['duration_s']:.1f}s] centroid={m['spectral_centroid_hz']:.0f}Hz "
                      f"flux={m['spectral_flux']:.4f} mod={m['modulation_depth']:.3f}@{m['modulation_peak_hz']:.0f}Hz "
                      f"crest={m['crest_factor']:.2f} bands={[round(b, 3) for b in m['band_shares']]}")
            recordings.append({**rec, "features": feats})
        if not recordings:
            print("  no recordings analyzed, skipping")
            continue
        targets = build_vehicle_targets(
            vehicle_id=vid,
            display_name=vehicle["display_name"],
            recordings=recordings,
            schema=vehicle["schema"],
        )
        out_path = OUT_DIR / f"{vid}_reference_targets.json"
        write_targets_json(targets, out_path)
        print(f"  -> {out_path}")
        sm = targets["stock_median"]
        summary.append({
            "vehicle": vid,
            "display_name": vehicle["display_name"],
            "recordings": len(recordings),
            "out_path": str(out_path),
            "stock_median_accel_band_shares": [round(b, 4) for b in sm.get("acceleration_band_shares", [])],
            "stock_median_accel_flux": round(sm.get("acceleration_flux", 0.0), 5),
            "stock_median_afterfire_band_shares": [round(b, 4) for b in sm.get("afterfire_band_shares", [])],
            "stock_median_afterfire_flux": round(sm.get("afterfire_flux", 0.0), 5),
        })

    summary_path = OUT_DIR / "reference_database_build_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    print(f"\n=== build summary -> {summary_path} ===")
    for s in summary:
        print(f"  {s['display_name']}: {s['recordings']} rec, "
              f"accel_bands={s['stock_median_accel_band_shares']}, "
              f"afterfire_bands={s['stock_median_afterfire_band_shares']}")


if __name__ == "__main__":
    main()
