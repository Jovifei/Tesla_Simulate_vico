"""Archive-level topology check; does not claim MATLAB compile or simulation."""

from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "playground_v12" / "vehicles" / "hellcat_2022_stock" / "S12_hellcat_2022_stock_v12.slx"
AUDITOR = ROOT / "playground_v12" / "common" / "inspect_texture_simulink_topology.py"
CANDIDATE = ROOT.parents[2] / "reports" / "simulink-texture-topology-20261028" / "isolated" / "S12_hellcat_2022_stock_v12_texture_candidate.slx"


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
        self.assertTrue(result["frozenOutputChainUnchanged"])
        self.assertEqual(result["topology"], "source")
        self.assertEqual(result["rootInports"], {})
        self.assertEqual(len(result["modelSha256"]), 64)
        self.assertEqual(result["actualBlocks"]["Hellcat Synthetic Source"], "11")
        self.assertEqual(result["actualBlocks"]["Frozen 4D-B Radiation Adapter"], "12")

    def test_texture_plan_is_isolated_and_defaults_to_zero(self) -> None:
        result = self.module.audit(MODEL)
        plan = result["textureInsertionPlan"]
        self.assertTrue(plan["sourceModelMustRemainUnchanged"])
        self.assertEqual(plan["defaultInputContract"]["textureWeights"], "zeros(1,3)")
        self.assertIn("Active Compile", plan["runtimeGates"])

    @unittest.skipUnless(CANDIDATE.is_file(), "Isolated candidate has not been built")
    def test_actual_candidate_archive_has_all_layer_inputs_and_frozen_output_chain(self) -> None:
        result = self.module.audit(CANDIDATE)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["topology"], "candidate")
        self.assertFalse(result["sourceToFrozenRadiation"])
        self.assertTrue(result["sourceThroughMixerToFrozenRadiation"])
        self.assertTrue(result["rootInputContract"])
        self.assertTrue(result["frozenOutputChainUnchanged"])
        self.assertIn("NOT_COMPILE_OR_SIMULATION", result["evidenceLevel"])


if __name__ == "__main__":
    unittest.main()
