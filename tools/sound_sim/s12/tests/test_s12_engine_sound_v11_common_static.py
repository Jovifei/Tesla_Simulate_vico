"""Offline static contract checks for v1.1 shared afterfire and analysis code."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
COMMON = ROOT / "playground_v11" / "common"


class S12EngineSoundV11CommonStaticTests(unittest.TestCase):
    def test_required_shared_helpers_exist(self) -> None:
        required = {
            "s12_v11_schedule_afterfire.m",
            "s12_v11_render_afterfire_pressure_frame.m",
            "s12_v11_compute_order_map.m",
            "s12_v11_compute_audio_metrics.m",
            "s12_v11_compute_afterfire_statistics.m",
            "s12_v11_analyze_sound.m",
            "s12_v11_apply_afterfire_before_ptr.m",
        }
        self.assertSetEqual({path.name for path in COMMON.glob("s12_v11_*.m")} & required, required)

    def test_scheduler_declares_state_event_and_level_contracts(self) -> None:
        text = source("s12_v11_schedule_afterfire.m")
        for field in (
            "rpm", "load", "throttle", "acceleration", "gear", "shift_type",
            "dfco", "thermal_state", "oxygen_state", "timestamp_s",
        ):
            self.assertIn(f'"{field}"', text)
        self.assertIn("config.base_energy <= 0", text)
        self.assertIn("config.interval_jitter_fraction <= 0", text)
        self.assertIn("config.cluster_energy_decay >= 0.90", text)
        for kind in ("upshift_bark", "downshift_blip_pop", "overrun_crackle"):
            self.assertIn(f'"{kind}"', text)
        for level in ("off", "subtle", "aggressive"):
            self.assertIn(f'"{level}"', text)
        for field in (
            "time_s", "kind", "location", "energy", "cluster_id",
            "variation", "eligibility_explanation",
        ):
            self.assertIn(f'"{field}"', text)

    def test_pressure_is_explicitly_pre_ptr_and_has_no_resonant_sine_ring(self) -> None:
        text = source("s12_v11_render_afterfire_pressure_frame.m")
        self.assertIn('"before_ptr_radiation"', text)
        self.assertIn('"pre_ptr_pressure_excitation"', text)
        self.assertIn('"post_pcm_append", false', text)
        self.assertNotRegex(text, re.compile(r"\bsin\s*\(", re.IGNORECASE))
        self.assertNotIn("audiowrite", text.lower())

    def test_analysis_declares_fixed_half_order_and_four_bands(self) -> None:
        order_map = source("s12_v11_compute_order_map.m")
        metrics = source("s12_v11_compute_audio_metrics.m")
        self.assertIn("0.5:0.5:12", order_map)
        self.assertIn("[20, 120; 120, 500; 500, 2000; 2000, 8000]", metrics)
        for field in (
            "band_energy_ratios", "centroid_hz", "rolloff_hz", "flatness",
            "modulation_depth", "pulse_amplitude_cv",
        ):
            self.assertIn(f'"{field}"', metrics)

    def test_adapter_sums_before_calling_existing_ptr_contract(self) -> None:
        text = source("s12_v11_apply_afterfire_before_ptr.m")
        resolver = V11 / "s12_v11_resolve_frozen_ptr_adapter.m"
        self.assertTrue(resolver.is_file())
        self.assertIn("prePtrExcitation = baseExcitation + afterfirePressure", text)
        self.assertIn("s12_v11_resolve_frozen_ptr_adapter", text)
        self.assertIn('addpath(adapter.source_folder, "-begin")', text)
        self.assertIn("resolvedPath = string(which(adapter.function_name))", text)
        self.assertIn("resolvedPath ~= adapter.source_path", text)
        self.assertIn(
            "s12_sound_playground_ptr_tuning_step(prePtrExcitation, pipeLengthM,",
            text,
        )
        self.assertIn('"ptr_function", "s12_sound_playground_ptr_tuning_step"', text)
        self.assertIn('"ptr_source_path", adapter.source_path', text)
        self.assertIn('"ptr_source_sha256", adapter.sha256', text)
        self.assertIn('"pre_ptr_excitation", prePtrExcitation', text)
        self.assertIn('"post_pcm_append", false', text)
        self.assertNotIn("fixtures", text.lower())

    def test_runtime_behavior_suites_do_not_put_same_name_ptr_fixture_on_path(self) -> None:
        for name in (
            "test_s12_engine_sound_v11_afterfire.m",
            "test_s12_engine_sound_v11_pilot_render.m",
        ):
            text = (ROOT / "tests" / name).read_text(encoding="utf-8")
            self.assertNotIn('"fixtures", "s12_v11"', text)
            self.assertNotIn("S12_V11_PTR_FIXTURE_CALL", text)
            self.assertIn("s12_v11_resolve_frozen_ptr_adapter", text)

    def test_render_to_ptr_runtime_call_chain_is_hash_gated_and_fixture_free(self) -> None:
        renderer = (V11 / "s12_v11_render_profile.m").read_text(encoding="utf-8")
        helper = source("s12_v11_apply_afterfire_before_ptr.m")
        resolver = (V11 / "s12_v11_resolve_frozen_ptr_adapter.m").read_text(
            encoding="utf-8"
        )
        self.assertIn("s12_v11_apply_afterfire_before_ptr", renderer)
        self.assertIn("s12_v11_resolve_frozen_ptr_adapter", helper)
        self.assertIn("resolvedPath ~= adapter.source_path", helper)
        self.assertIn('canonicalFolder = "E:\\Tesla_speed\\prj\\tools\\sound_sim\\s12\\playground"', resolver)
        self.assertIn("actualSha256 ~= expectedSha256", resolver)
        self.assertIn("sha256File(canonicalPath)", resolver)
        self.assertNotIn("fixtures", renderer.lower())
        self.assertNotIn("fixtures", helper.lower())

    def test_common_code_has_no_raw_audio_or_post_render_append_path(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in COMMON.glob("*.m"))
        self.assertNotIn("websave(", combined.lower())
        self.assertNotIn("webread(", combined.lower())
        self.assertNotIn("audioread(", combined.lower())
        self.assertNotIn("append_after", combined.lower())


def source(name: str) -> str:
    path = COMMON / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


if __name__ == "__main__":
    unittest.main(verbosity=2)
