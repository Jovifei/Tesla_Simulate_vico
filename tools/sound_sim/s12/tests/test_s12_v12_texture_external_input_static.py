"""Static contract for the MATLAB fixed-frame external texture input bridge."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class TextureExternalInputStaticContract(unittest.TestCase):
    def test_bridge_declares_fixed_frame_and_research_only_boundary(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_external_input.m").read_text(encoding="utf-8")
        for token in ("sampleRateHz = 48000", "frameSamples = 960", "crossfadeSamples", "texture_residual", "texture_weight", "source_sha256"):
            self.assertIn(token, text)
        self.assertIn("INSUFFICIENT_EVIDENCE", text)
        self.assertIn("RESEARCH_ONLY_NOT_PRODUCT_AUDIO", text)
        self.assertIn("rpm_load_gear_phase", text)
        self.assertIn("stateSchedule", text)
        self.assertIn("buildWeightSchedule", text)
        self.assertIn("target = baseWeight", text)

    def test_bridge_does_not_write_audio_or_start_simulation(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_external_input.m").read_text(encoding="utf-8").lower()
        self.assertNotIn("sim(", text)
        self.assertNotIn("audiowrite", text)
        self.assertNotIn("open_system", text)

    def test_weight_schedule_contract_is_monotone_with_load_direction(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_external_input.m").read_text(encoding="utf-8")
        self.assertIn("0.25 + 0.65 * load + 0.10", text)
        self.assertIn("weights(index) = weights(index - 1) + 0.25", text)


if __name__ == "__main__":
    unittest.main()
