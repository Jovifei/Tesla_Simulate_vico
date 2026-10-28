"""Archive-level topology check; does not claim MATLAB compile or simulation."""

from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "playground_v12" / "vehicles" / "hellcat_2022_stock" / "S12_hellcat_2022_stock_v12.slx"
AUDITOR = ROOT / "playground_v12" / "common" / "inspect_texture_simulink_topology.py"


class TextureSimulinkTopologyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("topology_audit", AUDITOR)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(cls.module)

    def test_existing_hellcat_archive_has_expected_source_to_radiation_chain(self) -> None:
        result = self.module.audit(MODEL)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["sourceToFrozenRadiation"])
        self.assertTrue(result["frozenRadiationToRendererMux"])
        self.assertEqual(result["actualBlocks"]["Hellcat Synthetic Source"], "11")
        self.assertEqual(result["actualBlocks"]["Frozen 4D-B Radiation Adapter"], "12")

    def test_texture_plan_is_isolated_and_defaults_to_zero(self) -> None:
        result = self.module.audit(MODEL)
        plan = result["textureInsertionPlan"]
        self.assertTrue(plan["copyModel"])
        self.assertTrue(plan["sourceModelUnchanged"])
        self.assertEqual(plan["defaultWeight"], 0)
        self.assertIn("Active Compile", plan["requiresRuntime"])


if __name__ == "__main__":
    unittest.main()
