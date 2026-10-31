"""Static contract for the exact isolated Simulink texture insertion plan."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = Path(__file__).resolve().parents[4] / "reports" / "simulink-texture-topology-20261028" / "MODEL_EDIT_PLAN.json"


class ModelEditPlanStaticContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_source_isolation_and_runtime_gates(self) -> None:
        self.assertTrue(self.plan["sourceModelMustRemainUnchanged"])
        self.assertIn("Active Compile", self.plan["runtimeGates"])
        self.assertIn("90s Simulation x2", self.plan["runtimeGates"])
        self.assertIn("PCM/WAV SHA repeatability", self.plan["runtimeGates"])

    def test_plan_disconnects_only_source_to_radiation_and_inserts_mixer(self) -> None:
        operations = self.plan["operations"]
        self.assertEqual([op["target"] for op in operations if op["op"] == "disconnect"],
                         ["blk_11.y1 -> blk_12.u1"])
        self.assertIn("#textureMixer.y1 -> blk_12.u1",
                      [op["target"] for op in operations if op["op"] == "connect"])
        self.assertEqual(self.plan["defaultInputContract"]["textureWeights"], "zeros(1,3)")
        self.assertEqual(self.plan["schema"], "s12.v12.texture.simulink.model-edit-plan.v2")
        operations = self.plan["operations"]
        self.assertTrue(any("textureBroadband" in str(op) for op in operations))
        self.assertTrue(any("u5" in str(op) for op in operations))


if __name__ == "__main__":
    unittest.main()
