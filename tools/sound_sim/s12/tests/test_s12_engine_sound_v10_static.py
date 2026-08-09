"""Static contracts for the S12 v1.0 synthetic sound package."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


V10 = Path(__file__).resolve().parents[1] / "playground_v10"
PROFILE_IDS = (
    "inline3_turbo",
    "inline4_sport",
    "inline5_character",
    "inline6_smooth",
    "v6_sport",
    "hellcat_style_supercharged_v8",
    "ferrari_style_high_rev_v8",
)
MODEL_NAMES = (
    "S12_I3_Turbo_v10.slx",
    "S12_I4_Sport_v10.slx",
    "S12_I5_Character_v10.slx",
    "S12_I6_Smooth_v10.slx",
    "S12_V6_Sport_v10.slx",
    "S12_V8_Muscle_v10.slx",
    "S12_V8_HighRev_v10.slx",
)


def provenance_leaves(value: object):
    if isinstance(value, dict):
        if "value" in value:
            yield value
        else:
            for child in value.values():
                yield from provenance_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from provenance_leaves(child)


class S12EngineSoundV10StaticTest(unittest.TestCase):
    def test_builtin_profiles_have_complete_synthetic_provenance(self) -> None:
        for profile_id in PROFILE_IDS:
            profile = json.loads(
                (V10 / "profiles" / f"{profile_id}.json").read_text(encoding="utf-8")
            )
            leaves = list(provenance_leaves(profile))
            self.assertGreater(len(leaves), 0, profile_id)
            for leaf in leaves:
                self.assertTrue({"value", "unit", "range", "source_level", "source"} <= leaf.keys())
                self.assertEqual("C", leaf["source_level"])
                self.assertEqual("synthetic", leaf["source"])

    def test_seven_independent_models_and_public_api_exist(self) -> None:
        self.assertTrue((V10 / "S12_PTR_Renderer_Core_v10.slx").is_file())
        for name in MODEL_NAMES:
            self.assertTrue((V10 / name).is_file(), name)
        for name in (
            "s12_engine_sound_audition.m",
            "s12_engine_sound_render_all.m",
            "s12_engine_sound_open_model.m",
            "s12_engine_sound_model_path.m",
        ):
            self.assertTrue((V10 / name).is_file(), name)

    def test_public_document_preserves_synthetic_boundary(self) -> None:
        document = (V10 / "S12_Engine_Sound_Playground_v10.md").read_text(encoding="utf-8").lower()
        for marker in ("synthetic", "uncalibrated", "offline", "not realtime-qualified"):
            self.assertIn(marker, document)
        self.assertIn("not contain vehicle recordings", document)
        self.assertIn("oem calibration data", document)
        self.assertIn("oem sound clone", document)


if __name__ == "__main__":
    unittest.main()
