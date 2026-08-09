"""S12 Phase 1 - reference database integrity tests (RED -> GREEN).

Validates that the per-vehicle real reference database built in Phase 1 contains
the full metric set required by the S12 Acoustic Realism Master Plan v1, and that
the three vehicles show measurable acoustic identity separation.

Run: python -m unittest test_reference_database_v1
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent / "acoustic_identity_v015"
DB = _BASE / "reference_database"
TARGETS = _BASE / "targets" / "realism_feature_targets.json"

VEHICLES = ["ferrari_458", "rx7_fd", "hellcat"]
REQUIRED_METRICS = [
    "band_shares", "spectral_flux", "modulation_depth", "modulation_peak_hz",
    "modulation_energy", "pulse_amplitude_cv", "pulse_interval_cv",
    "crest_factor", "dropout_ratio", "spectral_centroid_hz",
]
REQUIRED_SEGMENTS = ["idle", "acceleration", "afterfire"]
STOCK_MEDIAN_FIELDS = [
    "acceleration_band_shares", "afterfire_band_shares", "idle_band_shares",
    "acceleration_spectral_flux", "afterfire_spectral_flux",
    "acceleration_modulation_depth", "afterfire_modulation_depth",
    "idle_spectral_centroid_hz", "acceleration_crest_factor", "afterfire_crest_factor",
    "acceleration_modulation_peak_hz", "afterfire_modulation_peak_hz",
    "acceleration_pulse_interval_cv", "afterfire_pulse_interval_cv",
]


def _load(vid: str) -> dict:
    return json.loads((DB / f"{vid}_reference_targets.json").read_text(encoding="utf-8"))


class TestReferenceDatabaseV1(unittest.TestCase):
    def test_each_vehicle_has_targets_json(self):
        for vid in VEHICLES:
            self.assertTrue((DB / f"{vid}_reference_targets.json").exists(), f"{vid} missing reference_targets.json")

    def test_targets_have_schema_sources_and_stock_median(self):
        for vid in VEHICLES:
            ref = _load(vid)
            self.assertIn("schema", ref, f"{vid} missing schema")
            self.assertIn("sources", ref, f"{vid} missing sources")
            self.assertIn("stock_median", ref, f"{vid} missing stock_median")
            self.assertGreater(len(ref["sources"]), 0, f"{vid} has no sources")
            self.assertIn("boundary", ref, f"{vid} missing boundary")
            self.assertIn("not OEM", ref["boundary"])

    def test_every_segment_has_full_metric_set(self):
        for vid in VEHICLES:
            ref = _load(vid)
            for src in ref["sources"]:
                for seg_name in REQUIRED_SEGMENTS:
                    self.assertIn(seg_name, src["segments"], f"{vid} {src['id']} missing {seg_name}")
                    seg = src["segments"][seg_name]
                    for m in REQUIRED_METRICS:
                        self.assertIn(m, seg, f"{vid} {src['id']} {seg_name} missing metric {m}")
                    self.assertEqual(len(seg["band_shares"]), 4, f"{vid} {seg_name} band_shares not 4 bands")
                    total = sum(seg["band_shares"])
                    self.assertGreater(total, 0.0, f"{vid} {seg_name} band_shares sum to 0")

    def test_stock_median_has_aggregate_fields(self):
        for vid in VEHICLES:
            sm = _load(vid)["stock_median"]
            for field in STOCK_MEDIAN_FIELDS:
                self.assertIn(field, sm, f"{vid} stock_median missing {field}")
            self.assertEqual(len(sm["acceleration_band_shares"]), 4)

    def test_realism_feature_targets_upgraded(self):
        self.assertTrue(TARGETS.exists(), "realism_feature_targets.json missing")
        targets = json.loads(TARGETS.read_text(encoding="utf-8"))
        self.assertEqual(targets["schema_version"], "s12-acoustic-realism-targets-1.1")
        self.assertEqual(targets["metric_set"], "full_v1: band_shares(4) + spectral_flux + modulation_depth/peak_hz/energy + pulse_amplitude_cv/interval_cv + crest_factor + dropout_ratio")
        for vid in VEHICLES:
            feats = targets["vehicles"][vid]["r2_recording_dependent_features"]
            self.assertEqual(feats["schema"], "s12.realism_feature_targets.full_v1", f"{vid} targets not upgraded to full_v1")
            for seg in REQUIRED_SEGMENTS:
                self.assertIn(seg, feats, f"{vid} realism targets missing {seg}")
                for m in REQUIRED_METRICS:
                    self.assertIn(m, feats[seg], f"{vid} realism {seg} missing {m}")

    def test_index_document_exists(self):
        idx = DB / "real_recording_targets_index.md"
        self.assertTrue(idx.exists(), "real_recording_targets_index.md missing")
        text = idx.read_text(encoding="utf-8")
        for vid in VEHICLES:
            self.assertIn(vid, text, f"{vid} not mentioned in index")

    def test_vehicle_identity_separation_low_frequency(self):
        # RX-7 should carry the highest low-frequency (20-250Hz) share on acceleration
        # because the rotary concentrates energy in the low-frequency event band.
        bands = {vid: _load(vid)["stock_median"]["acceleration_band_shares"][0] for vid in VEHICLES}
        self.assertGreater(bands["rx7_fd"], bands["ferrari_458"], "RX-7 should have higher low-freq share than Ferrari")
        self.assertGreater(bands["rx7_fd"], bands["hellcat"], "RX-7 should have higher low-freq share than Hellcat")

    def test_vehicle_identity_separation_afterfire_high_freq(self):
        # Ferrari afterfire should carry more 1-4kHz energy than Hellcat/RX-7 because
        # the NA flat-plane V8 backfire is a sharper, higher-frequency transient.
        hf = {vid: _load(vid)["stock_median"]["afterfire_band_shares"][2] for vid in VEHICLES}
        self.assertGreater(hf["ferrari_458"], hf["hellcat"], "Ferrari afterfire should have more 1-4kHz than Hellcat")
        self.assertGreater(hf["ferrari_458"], hf["rx7_fd"], "Ferrari afterfire should have more 1-4kHz than RX-7")

    def test_idle_spectral_centroid_separation(self):
        # Ferrari idle should sit higher than RX-7 idle (metallic NA V8 vs low-freq rotary).
        centroid = {vid: _load(vid)["stock_median"]["idle_spectral_centroid_hz"] for vid in VEHICLES}
        self.assertGreater(centroid["ferrari_458"], centroid["rx7_fd"], "Ferrari idle centroid should exceed RX-7")


if __name__ == "__main__":
    unittest.main()
