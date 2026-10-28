"""Static contract for the optional v1.2 Simulink research texture input."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class TextureResidualStaticContract(unittest.TestCase):
    def test_pre_ptr_route_exposes_optional_texture_without_changing_radiation(self) -> None:
        route = (COMMON / "s12_v12_render_pre_ptr_frame.m").read_text(encoding="utf-8")
        mixer = (COMMON / "s12_v12_mix_texture_residual.m").read_text(encoding="utf-8")
        radiation = (COMMON / "s12_v12_model_radiation_step.m").read_text(encoding="utf-8")
        self.assertIn("textureResidual, textureWeight", route)
        self.assertIn("s12_v12_mix_texture_residual", route)
        self.assertIn("textureResidual = zeros(frameSamples, 1)", route)
        self.assertIn("textureWeight = 0", route)
        self.assertIn("INSUFFICIENT_EVIDENCE", mixer)
        self.assertIn("PUBLIC_TEXTURE_RESEARCH_ONLY", mixer)
        self.assertNotIn("texture", radiation.lower())

    def test_research_texture_preserves_fixed_pre_ptr_shape_and_frozen_boundary(self) -> None:
        route = (COMMON / "s12_v12_render_pre_ptr_frame.m").read_text(encoding="utf-8")
        mixer = (COMMON / "s12_v12_mix_texture_residual.m").read_text(encoding="utf-8")
        self.assertIn("[frameSamples, 1]", route)
        self.assertIn("[960, 1]", mixer)
        self.assertIn("product_candidate", mixer)
        self.assertIn("prePtrExcitation = s12_v12_mix_bank_excitation", route)


if __name__ == "__main__":
    unittest.main()
