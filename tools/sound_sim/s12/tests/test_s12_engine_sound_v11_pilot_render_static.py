"""Static contracts for the v1.1 pilot render and publication path."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
PILOTS = (
    "hellcat_2022_stock",
    "c63_w204_facelift_stock",
    "ferrari_458_stock",
)
PUBLIC_APIS = {
    "s12_v11_list_profiles.m",
    "s12_v11_load_profile.m",
    "s12_v11_compile_vehicle_cycle.m",
    "s12_v11_render_profile.m",
    "s12_v11_audition_profile.m",
    "s12_v11_render_pilot_profiles.m",
    "s12_v11_compare_audio_analysis.m",
}
ARTIFACTS = {
    "full_drive_cycle.wav",
    "idle.wav",
    "acceleration.wav",
    "upshift.wav",
    "downshift.wav",
    "deceleration.wav",
    "afterfire.wav",
    "vehicle_trace.csv",
    "profile_snapshot.json",
    "sound_analysis.json",
    "manifest.json",
    "SHA256.txt",
}


class S12EngineSoundV11PilotRenderStaticTests(unittest.TestCase):
    def test_public_api_surface_exists_and_uses_v11_prefix(self) -> None:
        self.assertSetEqual(
            {path.name for path in V11.glob("s12_v11_*.m")} & PUBLIC_APIS,
            PUBLIC_APIS,
        )
        for name in PUBLIC_APIS:
            text = source(name)
            self.assertRegex(
                text,
                rf"(?m)(?:^function(?:\s+\[[^\]]+\]|\s+\w+)?\s*=\s*{re.escape(name[:-2])}\b"
                rf"|^function\s+{re.escape(name[:-2])}\b)",
            )

    def test_cycle_declares_fixed_90_second_frame_contract(self) -> None:
        text = source("s12_v11_compile_vehicle_cycle.m")
        for contract in (
            "sampleRateHz = profile.renderer.sample_rate_hz",
            "frameSamples = profile.renderer.frame_samples",
            "frameCount = durationS * sampleRateHz / frameSamples",
            "durationS = 90",
            "sampleCount ~= 4320000",
            '"sample_count", 4320000',
        ):
            self.assertIn(contract, text)
        for field in (
            "rpm", "load", "throttle", "acceleration", "speed_kph",
            "gear", "shift_type", "dfco", "thermal_state", "oxygen_state",
        ):
            self.assertIn(f'"{field}"', text)

    def test_renderer_preserves_phase_and_injects_afterfire_before_ptr(self) -> None:
        text = source("s12_v11_render_profile.m")
        self.assertIn("phase_start_rad", text)
        self.assertIn("phase_next_rad", text)
        self.assertIn("context.phase_rad", text)
        self.assertIn("zeros(1, 9)", text)
        self.assertIn("context.supercharger_phase_rad", text)
        self.assertIn("s12_v11_compile_afterfire_schedule", text)
        self.assertNotIn("s12_v11_schedule_afterfire(state", text)
        self.assertIn("s12_v11_render_afterfire_pressure_frame", text)
        apply_call = text.index(
            "[pressureFrame, ptrDiagnostics] = s12_v11_apply_afterfire_before_ptr"
        )
        stereo_write = text.index("pcm(samples, :)")
        self.assertLess(apply_call, stereo_write)
        self.assertIn('"insertion_stage", "before_ptr_radiation"', text)
        self.assertIn('"post_pcm_append", false', text)
        self.assertIn("frameSamples = profile.renderer.frame_samples", text)
        self.assertIn("channels = profile.renderer.channels", text)
        self.assertIn("size(framePcm), [frameSamples, channels]", text)

    def test_renderer_fails_closed_on_audio_safety_without_hard_limiter(self) -> None:
        text = source("s12_v11_render_profile.m")
        self.assertIn('error("S12:EngineSoundV11:AudioSafety"', text)
        self.assertRegex(text, r"peak\s*>=\s*1")
        self.assertIn("any(~isfinite(pcm), \"all\")", text)
        self.assertIn("profile.renderer.hard_limiter", text)
        self.assertIn('error("S12:EngineSoundV11:Renderer"', text)
        self.assertNotIn("hard_limiter(", text.lower())
        self.assertNotIn("limiter(", text.lower())
        self.assertNotRegex(text, r"pcm\s*=\s*(?:min|max)\s*\(")
        self.assertNotIn("audiowrite", text.lower())

    def test_publication_is_exact_24_bit_stereo_and_hashes_same_bytes(self) -> None:
        text = source("s12_v11_audition_profile.m")
        for artifact in ARTIFACTS:
            self.assertIn(f'"{artifact}"', text)
        self.assertIn("bitsPerSample = profile.renderer.bits_per_sample", text)
        self.assertIn("BitsPerSample=bitsPerSample", text)
        self.assertIn('"sample_rate_hz", profile.renderer.sample_rate_hz', text)
        self.assertIn('"frame_samples", profile.renderer.frame_samples', text)
        self.assertIn('"frame_count", 4500', text)
        self.assertIn('"sample_count", 4320000', text)
        self.assertIn('"channels", profile.renderer.channels', text)
        self.assertIn('"hard_limiter", profile.renderer.hard_limiter', text)
        self.assertIn('"post_pcm_append", false', text)
        self.assertIn(
            'root = "E:\\Tesla_speed\\tasks\\reports\\runtime\\s12-engine-sound-v11"',
            text,
        )
        self.assertIn("s12_v11_validate_canonical_vehicle_id", text)
        early_validation = (
            "profile.vehicle_id = s12_v11_validate_canonical_vehicle_id(profile.vehicle_id)"
        )
        self.assertIn(early_validation, text)
        self.assertLess(
            text.index(early_validation),
            text.index("rendered = s12_v11_render_profile"),
        )
        self.assertLess(
            text.index("profileId = s12_v11_validate_canonical_vehicle_id(profileId)"),
            text.index("candidate = fullfile(runtimeRoot, runId, profileId)"),
        )
        self.assertIn("s12_v11_sha256_file", text)
        self.assertIn("sort(names)", text)
        self.assertNotIn("full_drive_cycle_pcm", text)

    def test_pilot_set_and_analysis_comparison_are_explicit(self) -> None:
        combined = "\n".join(
            source(name)
            for name in (
                "s12_v11_load_profile.m",
                "s12_v11_render_pilot_profiles.m",
                "s12_v11_compare_audio_analysis.m",
            )
        )
        for pilot in PILOTS:
            self.assertIn(f'"{pilot}"', combined)
        for feature in (
            "order_signature", "band_energy_ratios", "centroid_hz",
            "modulation_depth", "pairwise_distance", "distinguishable",
        ):
            self.assertIn(f'"{feature}"', combined)
        self.assertIn('"distinguishable_threshold"', combined)
        self.assertIn("signatureThreshold = 0.05", combined)
        self.assertIn("orderSignature = orderSignature / max(sum(orderSignature), eps)", combined)
        self.assertIn("numel(featureNames) ~= size(features, 2)", combined)
        self.assertIn("s12_v11_analyze_sound", source("s12_v11_render_profile.m"))

    def test_runtime_suite_exercises_causality_and_publication_surfaces(self) -> None:
        text = (
            ROOT / "tests" / "test_s12_engine_sound_v11_pilot_render.m"
        ).read_text(encoding="utf-8")
        for token in (
            '"AfterfireLevel", "off"',
            "pre_ptr_changed",
            "pre_ptr_excitation",
            "s12_v11_audition_profile",
            "s12_v11_render_pilot_profiles",
            "audioinfo",
            "BitsPerSample",
            "4320000",
            "SHA256.txt",
            "secondPublished",
            "testPublicationRejectsPathTraversalBeforeRender",
            "s12_v11_resolve_frozen_ptr_adapter",
            "ptr_source_sha256",
        ):
            self.assertIn(token, text)

    def test_render_path_contains_no_raw_audio_or_network_acquisition(self) -> None:
        combined = "\n".join(source(name).lower() for name in PUBLIC_APIS)
        for forbidden in ("audioread(", "webread(", "websave(", "urlread("):
            self.assertNotIn(forbidden, combined)


def source(name: str) -> str:
    path = V11 / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


if __name__ == "__main__":
    unittest.main(verbosity=2)
