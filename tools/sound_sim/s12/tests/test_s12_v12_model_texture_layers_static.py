"""Static contract for the codegen-friendly layered texture block."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class ModelTextureLayersStaticContract(unittest.TestCase):
    def test_layered_block_has_fixed_inputs_and_persistent_scalar_state(self) -> None:
        text = (COMMON / "s12_v12_model_texture_layers_step.m").read_text(encoding="utf-8")
        self.assertIn("function frame = s12_v12_model_texture_layers_step", text)
        self.assertIn("persistent weightState", text)
        self.assertIn("[1, 3]", text)
        self.assertIn("[960, 1]", text)
        self.assertIn("all(weights == 0)", text)
        self.assertNotIn("struct(", text)

    def test_contract_uses_three_layers(self) -> None:
        text = (COMMON / "s12_v12_texture_simulink_contract.m").read_text(encoding="utf-8")
        for token in ("texture_body", "texture_mechanical", "texture_broadband", "texture_weights", "[1, 3]"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
