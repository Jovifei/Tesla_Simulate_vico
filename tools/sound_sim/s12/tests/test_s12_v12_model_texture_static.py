"""Static contract for the fixed-frame Simulink MATLAB Function entry."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class ModelTextureStaticContract(unittest.TestCase):
    def test_fixed_frame_entry_has_expected_shape_and_fail_closed_checks(self) -> None:
        text = (COMMON / "s12_v12_model_texture_step.m").read_text(encoding="utf-8")
        self.assertIn("function frame = s12_v12_model_texture_step(prePtr, textureResidual, textureWeight)", text)
        self.assertIn("[960, 1]", text)
        self.assertIn("textureWeight < 0 || textureWeight > 1", text)
        self.assertIn("persistent weightState", text)
        self.assertIn("weightState = weightState + 0.25", text)
        self.assertNotIn("persistent context", text)
        self.assertNotIn("isfield(", text)
        self.assertNotIn("diagnostics", text)
        self.assertIn("any(abs(frame) > 1", text)
        self.assertNotIn("s12_v11", text)

    def test_candidate_plan_names_the_fixed_frame_entry(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_simulink_candidate.m").read_text(encoding="utf-8")
        self.assertIn("s12_v12_model_texture_step", text)


if __name__ == "__main__":
    unittest.main()
