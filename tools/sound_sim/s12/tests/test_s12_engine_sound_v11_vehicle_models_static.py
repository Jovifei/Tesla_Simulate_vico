"""Static contracts for the v1.1 eight-vehicle and Simulink-wrapper layer.

MATLAB/Simulink execution is deliberately covered by a separate, authored
suite.  This file only proves that source-level contracts are present while
the existing-session Desktop control plane is unsafe for runtime execution.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
VEHICLES = (
    "hellcat_2022_stock",
    "gtr_r35_2007_stock",
    "c63_w204_facelift_stock",
    "supra_jza80_rz_stock",
    "rx7_fd_1991_stock",
    "lexus_lfa_stock",
    "ferrari_458_stock",
    "aventador_lp700_stock",
)


class S12EngineSoundV11VehicleModelStaticTests(unittest.TestCase):
    def test_all_eight_vehicle_packages_map_render_character_from_json(self) -> None:
        loader = source("s12_v11_load_profile.m")
        listed = source("s12_v11_list_profiles.m")
        canonical = source("s12_v11_canonical_vehicle_ids.m")
        for vehicle_id in VEHICLES:
            self.assertIn(f'"{vehicle_id}"', canonical)
            profile = json.loads((V11 / "vehicles" / vehicle_id / "profile.json").read_text(encoding="utf-8"))
            self.assertIn("render_tuning", profile)
            self.assertIn("character", profile["render_tuning"])
            self.assertIn("afterfire", profile["render_tuning"])
        self.assertIn("s12_v11_canonical_vehicle_ids", listed)
        self.assertIn("s12_v11_validate_canonical_vehicle_id", loader)
        self.assertIn("mapRenderTuning(metadata.render_tuning)", loader)
        self.assertNotIn("switch identifier", loader)
        self.assertNotIn("vehicleCharacter(identifier)", loader)
        self.assertNotIn("Task 3 render behavior", loader)

    def test_public_audition_validates_all_eight_canonical_ids_before_render(self) -> None:
        audition = source("s12_v11_audition_profile.m")
        validator = source("s12_v11_validate_canonical_vehicle_id.m")
        canonical = source("s12_v11_canonical_vehicle_ids.m")
        for vehicle_id in VEHICLES:
            self.assertIn(f'"{vehicle_id}"', canonical)
        early_validation = "profile.vehicle_id = s12_v11_validate_canonical_vehicle_id(profile.vehicle_id)"
        self.assertIn(early_validation, audition)
        self.assertLess(
            audition.index(early_validation),
            audition.index("rendered = s12_v11_render_profile"),
        )
        self.assertIn("s12_v11_validate_canonical_vehicle_id(profileId)", audition)
        self.assertIn('error("S12:EngineSoundV11:ProfileId"', validator)
        self.assertNotIn("validateCanonicalPilotId", audition)

    def test_rx7_uses_a_separate_rotary_event_scheduler_not_piston_formula(self) -> None:
        scheduler = source("s12_v11_rotary_event_frequency.m")
        renderer = source("s12_v11_render_profile.m")
        self.assertRegex(scheduler, r"(?m)^function\s+\[.*\]\s*=\s*s12_v11_rotary_event_frequency\b")
        for token in ("rotor_count", "chambers_per_rotor", "shaft_turns_per_rotor_turn", "combustion_event_hz"):
            self.assertIn(token, scheduler)
        self.assertNotIn("cylinders / 2", scheduler)
        self.assertIn("s12_v11_render_rotary_excitation_frame", renderer)
        self.assertIn("character.engine_kind == \"rotary\"", renderer)
        self.assertIn("s12_v11_rotary_event_frequency", source("s12_v11_render_rotary_excitation_frame.m"))

    def test_model_contracts_cover_eight_independent_wrappers_and_shared_core(self) -> None:
        contracts = source("s12_v11_model_contracts.m")
        self.assertIn("vehicleIds = s12_v11_canonical_vehicle_ids()", contracts)
        self.assertIn('modelName = "S12_" + vehicleId + "_v11"', contracts)
        self.assertIn('fullfile(root, "vehicles", vehicleId, modelName + ".slx")', contracts)
        for token in (
            "S12_PTR_Radiation_Core_v11",
            "Vehicle State",
            "Dashboard RPM",
            "Dashboard Load",
            "Dashboard Acceleration",
            "Dashboard Throttle",
            "Vehicle Excitation Afterfire",
            "PTR Radiation Model Reference",
            "Stereo Renderer",
            "PCM Output",
            "[960,2]",
            "before_ptr_radiation",
        ):
            self.assertIn(token, contracts)

    def test_builder_is_opt_in_idempotent_and_fails_closed_before_save(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        topology = source("s12_v11_validate_model_topology.m")
        for token in ("AllowModelCreation", "usejava(\"desktop\")", "s12_v11_model_contracts", "s12_v11_validate_model_topology"):
            self.assertIn(token, builder)
        renderer = function_body(builder, "addStereoRenderer")
        self.assertNotIn("addDashboardBlocks", renderer)
        for token in (
            "simulink/User-Defined Functions/MATLAB Fcn",
            "s12_v11_model_vehicle_state_step",
            "s12_v11_model_excitation_afterfire_step",
            "s12_v11_model_ptr_radiation_step",
            "s12_v11_model_stereo_renderer_step",
            "Simulink.HMI.ParamSourceInfo",
            "set_param(knobPath, \"Binding\", binding)",
        ):
            self.assertIn(token, builder)
        self.assertLess(
            builder.index("s12_v11_validate_model_topology"),
            builder.index("save_system"),
        )
        for token in ("required_chain", "[960,2]", "before_ptr_radiation", "error(\"S12:EngineSoundV11:ModelTopology\""):
            self.assertIn(token, topology)
        self.assertNotIn("Post PTR", topology)
        self.assertNotIn("Audio Design", topology)

    def test_model_helpers_connect_live_state_afterfire_to_the_frozen_ptr_adapter(self) -> None:
        excitation = source("s12_v11_model_excitation_afterfire_step.m")
        ptr = source("s12_v11_model_ptr_radiation_step.m")
        renderer = source("s12_v11_model_stereo_renderer_step.m")
        for token in (
            "s12_v11_load_profile", "s12_v11_schedule_afterfire",
            "s12_v11_render_afterfire_pressure_frame", "prePtrExcitation",
        ):
            self.assertIn(token, excitation)
        self.assertIn("s12_sound_playground_ptr_tuning_step", ptr)
        self.assertIn("ptrControls(1)", ptr)
        self.assertIn("profile.renderer.frame_samples", ptr)
        self.assertNotIn("pressure = excitation", ptr)
        self.assertIn("s12_v11_load_profile", renderer)
        self.assertIn("profile.renderer.frame_samples", renderer)
        self.assertIn("gain *", renderer)
        self.assertIn("profile.character.stereo_offset", renderer)
        builder = source("s12_v11_build_simulink_models.m")
        self.assertIn('model + "/Vehicle Profile Index"', builder)
        self.assertNotIn('"Value", "zeros(960,1)"', builder)

    def test_frozen_ptr_adapter_is_canonical_hash_checked_and_never_uses_fixture_paths(self) -> None:
        resolver = source("s12_v11_resolve_frozen_ptr_adapter.m")
        helper = source("s12_v11_model_ptr_radiation_step.m")
        builder = source("s12_v11_build_simulink_models.m")
        for token in (
            "E:\\Tesla_speed\\prj\\tools\\sound_sim\\s12\\playground",
            "s12_sound_playground_ptr_tuning_step.m",
            "3ce53f44883686ed2fa10a6c5b20cfe15d11b813ff75fb164489c62a241020e1",
            "java.security.MessageDigest",
            'error("S12:EngineSoundV11:FrozenPtrAdapter"',
        ):
            self.assertIn(token, resolver)
        self.assertIn("s12_v11_resolve_frozen_ptr_adapter", helper)
        self.assertNotIn('fullfile(fileparts(root), "playground")', helper)
        self.assertNotIn("fixtures", helper.lower())
        self.assertIn("ExpectedFrozenPtrAdapterSha256", builder)
        self.assertIn("s12_v11_resolve_frozen_ptr_adapter", builder)
        self.assertIn('"frozen_ptr_adapter_path", frozenAdapter.source_path', builder)
        self.assertIn('"frozen_ptr_adapter_sha256", frozenAdapter.sha256', builder)

    def test_builder_validates_each_dashboard_binding_target_not_just_nonempty(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        validation = function_body(builder, "validateDashboardBinding")
        for token in (
            "validateDashboardBinding",
            "expectedControlPath",
        ):
            self.assertIn(token, builder)
        for token in ("binding.BlockPath", "binding.ParamName", '"Value"', "getBlock"):
            self.assertIn(token, validation)

    def test_profile_listing_derives_the_exact_three_item_pilot_subset(self) -> None:
        listing = source("s12_v11_list_profiles.m")
        for pilot in (
            "hellcat_2022_stock",
            "c63_w204_facelift_stock",
            "ferrari_458_stock",
        ):
            self.assertIn(f'"{pilot}"', listing)
        self.assertIn("pilot = ismember(ids(index), pilots)", listing)
        self.assertNotIn("supported = true", listing)

    def test_runtime_model_suite_is_authored_but_not_implicitly_executed(self) -> None:
        runtime_suite = ROOT / "tests" / "test_s12_engine_sound_v11_simulink_models.m"
        self.assertTrue(runtime_suite.is_file())
        text = runtime_suite.read_text(encoding="utf-8")
        for token in (
            "s12_v11_build_simulink_models",
            "load_system",
            "SimulationCommand', 'update'",
            "[960,2]",
            "cold reload",
            "CompiledPortDimensions",
            "BlockType",
            "ExpectedFrozenPtrAdapterSha256",
            "s12_v11_resolve_frozen_ptr_adapter",
            "frozen_ptr_adapter_sha256",
            "core_model_path",
            "PTR Radiation Adapter",
        ):
            self.assertIn(token, text)

    def test_v11_builder_source_neither_acquires_raw_audio_nor_writes_pcm_outputs(self) -> None:
        builder_sources = (
            "s12_v11_model_contracts.m",
            "s12_v11_validate_model_topology.m",
            "s12_v11_build_simulink_models.m",
        )
        combined = "\n".join(source(name).lower() for name in builder_sources)
        self.assertTrue(combined)
        for forbidden in ("audioread(", "webread(", "websave(", "audiowrite("):
            self.assertNotIn(forbidden, combined)


def source(name: str) -> str:
    path = V11 / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def function_body(text: str, name: str) -> str:
    match = re.search(rf"(?m)^function\b[^\n]*\b{re.escape(name)}\b[^\n]*\n", text)
    if not match:
        return ""
    next_function = re.search(r"(?m)^function\b", text[match.end():])
    end = match.end() + next_function.start() if next_function else len(text)
    return text[match.start():end]


if __name__ == "__main__":
    unittest.main(verbosity=2)
