"""Static contract for the controlled v1.2 texture candidate runner."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class TextureCandidateRunnerStaticContract(unittest.TestCase):
    def test_runner_is_fail_closed_and_execute_false_by_default(self) -> None:
        text = (COMMON / "s12_v12_run_texture_candidate.m").read_text(encoding="utf-8")
        self.assertIn("execute = false", text)
        self.assertIn("Simulink.SimulationInput", text)
        self.assertIn("setVariable(\"texture_residual_frames\"", text)
        self.assertIn("setVariable(\"texture_weight_frames\"", text)
        self.assertIn("addpath(candidateFolder)", text)
        self.assertIn("pcm = out.playground_pcm", text)
        self.assertNotIn("isfield(out", text)
        self.assertIn("INSUFFICIENT_EVIDENCE", text)
        self.assertIn("RESEARCH_ONLY_NOT_PRODUCT_AUDIO", text)
        self.assertIn("product_candidate", text)

    def test_runner_does_not_touch_default_source_or_claim_oem(self) -> None:
        text = (COMMON / "s12_v12_run_texture_candidate.m").read_text(encoding="utf-8").lower()
        self.assertNotIn("save_system", text)
        self.assertNotIn("promote", text)
        self.assertNotIn("oem", text)


if __name__ == "__main__":
    unittest.main()
