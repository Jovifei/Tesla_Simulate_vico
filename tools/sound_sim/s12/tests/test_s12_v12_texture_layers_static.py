"""Static contract for layered research texture mixing."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class TextureLayersStaticContract(unittest.TestCase):
    def test_layered_helper_has_three_layers_and_research_boundary(self) -> None:
        text = (COMMON / "s12_v12_mix_texture_residual.m").read_text(encoding="utf-8")
        self.assertIn("s12_v12_mix_texture_layers", text)
        self.assertIn("bodyTexture, mechanicalTexture, broadbandTexture", text)
        self.assertIn("[1, 3]", text)
        self.assertIn("PUBLIC_TEXTURE_LAYERS_RESEARCH_ONLY", text)
        self.assertIn("INSUFFICIENT_EVIDENCE", text)
        self.assertIn("product_candidate", text)

    def test_layered_helper_does_not_change_frozen_radiation(self) -> None:
        text = (COMMON / "s12_v12_mix_texture_residual.m").read_text(encoding="utf-8").lower()
        self.assertNotIn("radiation", text)
        self.assertNotIn("sim(", text)


if __name__ == "__main__":
    unittest.main()
