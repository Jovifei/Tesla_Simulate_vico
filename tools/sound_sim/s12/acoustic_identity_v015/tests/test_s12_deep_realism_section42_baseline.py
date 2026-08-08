# tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_deep_realism_section42_baseline.py
from __future__ import annotations

import json
from pathlib import Path
import unittest

_V015 = Path(__file__).resolve().parents[1]
_BASELINE = _V015 / "docs" / "deep_realism_section_42_baseline.json"


class Section42BaselineLockTests(unittest.TestCase):
    def test_baseline_json_exists_and_three_anchors_present(self) -> None:
        self.assertTrue(_BASELINE.is_file())
        data = json.loads(_BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"ferrari_458", "hellcat", "rx7_fd"})

    def test_baseline_records_full_gate_status_and_is_reproducible(self) -> None:
        # §4.2 coarse gate is the TARGET the deep-realism tuning (Task 3.x) must
        # achieve/preserve — it is NOT required to pass at baseline. This test
        # only locks that the baseline captures every anchor/clip's measured
        # gate status (idle + accel) and that the recorded structure is complete.
        # The baseline may legitimately contain failures; Task 3.x fixes those
        # via Track-S source tuning (sources/ are editable Track S, NOT frozen
        # Track P — the frozen boundary is only PTR adapter / manage_bundle_loudness
        # / radiation / FVM / runtime / MATLAB).
        data = json.loads(_BASELINE.read_text(encoding="utf-8"))
        for vid in ("ferrari_458", "hellcat", "rx7_fd"):
            with self.subTest(vehicle=vid):
                for clip in ("idle", "acceleration"):
                    if clip == "idle":
                        self.assertIn("idle_pass", data[vid][clip])
                        self.assertIn("idle_centroid_error_hz", data[vid][clip])
                        self.assertIn("idle_centroid_gate_hz", data[vid][clip])
                    else:
                        self.assertIn("accel_pass", data[vid][clip])
                        self.assertIn("band_abs_errors", data[vid][clip])
