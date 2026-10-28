"""Static contract for the MATLAB/Simulink texture residual candidate."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "playground_v12" / "common"


class TextureSimulinkStaticContract(unittest.TestCase):
    def test_contract_declares_fixed_ports_and_runtime_gates(self) -> None:
        text = (COMMON / "s12_v12_texture_simulink_contract.m").read_text(encoding="utf-8")
        for token in ("[9, 1]", "[960, 1]", "[1, 3]", "[960, 2]", "default_texture_weight", "requires_active_compile", "requires_90s_simulation"):
            self.assertIn(token, text)
        self.assertIn("RESEARCH_ONLY_NOT_PRODUCT_AUDIO", text)

    def test_candidate_preparation_refuses_source_overwrite(self) -> None:
        text = (COMMON / "s12_v12_prepare_texture_simulink_candidate.m").read_text(encoding="utf-8")
        self.assertIn("sourceModel == outputModel", text)
        self.assertIn("model_edit", text)
        self.assertIn("INSUFFICIENT_EVIDENCE_UNTIL_RUNTIME_AND_ACOUSTIC_GATES", text)
        self.assertIn("copy source model to isolated candidate", text)


if __name__ == "__main__":
    unittest.main()
