"""Static contract for the three-layer MATLAB texture input bridge."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class TextureExternalLayersStaticContract(unittest.TestCase):
    def test_external_input_exposes_three_layers_and_three_weights(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_external_input.m").read_text(encoding="utf-8")
        self.assertIn("textureLayers = zeros(frameCount, frameSamples, 3", text)
        self.assertIn("texture_layer_weights", text)
        self.assertIn("textureLayers(:, :, 1) = textureResidual", text)
        self.assertIn("layerPaths", text)
        self.assertIn("layer_source_sha256", text)
        self.assertIn("buildLayerFrames", text)

    def test_legacy_single_texture_remains_body_only_by_default(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_external_input.m").read_text(encoding="utf-8")
        self.assertIn("other layers stay zero", text)
        self.assertIn("texture_weight", text)


if __name__ == "__main__":
    unittest.main()
