"""Static P1 contracts for the exact v1.1 cycle, source startup, and API layer."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
CANONICAL_IDS = (
    "hellcat_2022_stock",
    "gtr_r35_2007_stock",
    "c63_w204_facelift_stock",
    "supra_jza80_rz_stock",
    "rx7_fd_1991_stock",
    "lexus_lfa_stock",
    "ferrari_458_stock",
    "aventador_lp700_stock",
)


class S12EngineSoundV11CycleApiStartStaticTests(unittest.TestCase):
    def test_cycle_has_only_the_approved_eleven_windows(self) -> None:
        text = source("s12_v11_compile_vehicle_cycle.m")
        self.assertIn("boundaries = [0, 2, 12, 22, 32, 48, 54, 66, 72, 82, 88, 90]", text)
        self.assertNotIn("47.6", text)
        self.assertNotIn("49.0", text)
        for name in (
            "startup", "idle", "launch", "cruise", "wot_to_redline",
            "high_load_hold", "lift", "downshift_blip", "second_acceleration",
            "rapid_lift", "return_idle",
        ):
            self.assertIn(f'"{name}"', text)
        self.assertIn("redline, redline", text)
        self.assertIn("frameCount = durationS * sampleRateHz / frameSamples", text)
        self.assertIn('"frame_count", frameCount', text)

    def test_startup_is_a_deterministic_source_stage_not_pcm_processing(self) -> None:
        helper = source("s12_v11_apply_startup_source_envelope.m")
        render = source("s12_v11_render_profile.m")
        self.assertIn("startupDurationS = 2", helper)
        self.assertIn("normalizedTime .^ 2 .* (3 - 2 * normalizedTime)", helper)
        self.assertIn('"stage", "engine_excitation_before_ptr_radiation"', helper)
        self.assertIn('"post_pcm_effect", false', helper)
        call = render.index("s12_v11_apply_startup_source_envelope")
        ptr = render.index("[pressureFrame, ptrDiagnostics] = s12_v11_apply_afterfire_before_ptr")
        pcm = render.index("pcm(samples, :)")
        self.assertLess(call, ptr)
        self.assertLess(ptr, pcm)
        self.assertIn("startup_source_excitation", render)
        self.assertNotIn("startup_pcm", render.lower())

    def test_compatibility_api_is_local_to_v11_and_routes_all_eight(self) -> None:
        wrappers = (
            "s12_engine_sound_list_profiles.m",
            "s12_engine_sound_load_profile.m",
            "s12_engine_sound_audition.m",
            "s12_engine_sound_compare_reference.m",
            "s12_engine_sound_open_model.m",
            "s12_engine_sound_render_all_v11.m",
        )
        for name in wrappers:
            self.assertTrue((V11 / name).is_file(), name)
        combined = "\n".join(source(name) for name in wrappers)
        for identifier in CANONICAL_IDS:
            self.assertIn(identifier, source("s12_v11_canonical_vehicle_ids.m"))
        self.assertIn("s12_v11_validate_canonical_vehicle_id", combined)
        self.assertNotIn("playground_v10", combined)
        self.assertNotIn("addpath", combined)
        self.assertIn("ProfileIds", source("s12_engine_sound_render_all_v11.m"))
        self.assertIn("s12_v11_canonical_vehicle_ids()", source("s12_engine_sound_render_all_v11.m"))
        self.assertIn("NOT_RUNTIME_VERIFIED", source("s12_engine_sound_render_all_v11.m"))

    def test_api_declarations_remain_synthetic_and_reference_bounded(self) -> None:
        audition = source("s12_engine_sound_audition.m")
        reference = source("s12_engine_sound_compare_reference.m")
        self.assertIn('"stock"', audition)
        self.assertIn('"exterior_rear"', audition)
        self.assertIn('"off", "subtle", "aggressive"', audition)
        self.assertIn('"reference_audio_state", "not_acquired"', reference)
        self.assertIn('"raw_reference_audio_used", false', reference)
        self.assertNotIn("audioread", reference.lower())
        self.assertNotIn("webread", reference.lower())

    def test_desktop_runtime_suite_is_authored_but_explicitly_withheld(self) -> None:
        text = (ROOT / "tests" / "test_s12_engine_sound_v11_cycle_api_start.m").read_text(encoding="utf-8")
        for token in (
            "testFixedAcceptanceWindowsAreExact",
            "testStartupEnvelopeIsContinuousAndPrePtrScoped",
            "testCompatibilityRoutesEveryCanonicalProfile",
            "testAllEightBatchApiAuthoredNotRun",
            "NOT_RUNTIME_VERIFIED",
            "assumeTrue(testCase, false",
        ):
            self.assertIn(token, text)


def source(name: str) -> str:
    return (V11 / name).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
