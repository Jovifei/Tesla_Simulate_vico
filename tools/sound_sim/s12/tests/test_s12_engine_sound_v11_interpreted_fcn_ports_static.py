"""Static port contracts for v1.1 Interpreted MATLAB Fcn blocks."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"


class S12EngineSoundV11InterpretedFcnPortsStaticTests(unittest.TestCase):
    def test_builder_packs_every_multi_signal_interpreted_function_into_one_port(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        for mux_name, inputs in (("Excitation Clock Mux", "2"), ("Renderer Input Mux", "2"), ("PTR Input Mux", "3")):
            self.assertIn(mux_name, builder)
            self.assertIn(f'addMuxBlock(model + "/{mux_name}", {inputs},', builder)
        self.assertIn('"Inputs", num2str(inputs)', function_body(builder, "addMuxBlock"))
        for forbidden in (
            '"Timeline Clock/1", "Vehicle Excitation Afterfire/2"',
            '"Renderer Gain Selector/1", "Stereo Renderer/3"',
            '"Profile Index/1", "PTR Radiation Adapter/2"',
            '"PTR Controls/1", "PTR Radiation Adapter/3"',
        ):
            self.assertNotIn(forbidden, builder)
        for required in (
            '"Vehicle State/1", "Excitation Clock Mux/1"',
            '"Timeline Clock/1", "Excitation Clock Mux/2"',
            '"Excitation Clock Mux/1", "Vehicle Excitation Afterfire/1"',
            '"PTR Radiation Model Reference/1", "Renderer Input Mux/1"',
            '"Renderer Gain Selector/1", "Renderer Input Mux/2"',
            '"Renderer Input Mux/1", "Stereo Renderer/1"',
            '"PTR Input Mux/1", "PTR Radiation Adapter/1"',
        ):
            self.assertIn(required, builder)

    def test_helper_signatures_accept_one_packed_vector_per_interpreted_block(self) -> None:
        excitation = source("s12_v11_model_excitation_afterfire_step.m")
        ptr = source("s12_v11_model_ptr_radiation_step.m")
        renderer = source("s12_v11_model_stereo_renderer_step.m")
        self.assertRegex(excitation, r"s12_v11_model_excitation_afterfire_step\(packedInput,\s*vehicleId\)")
        self.assertRegex(ptr, r"s12_v11_model_ptr_radiation_step\(packedInput\)")
        self.assertRegex(renderer, r"s12_v11_model_stereo_renderer_step\(packedInput,\s*profileIndex\)")
        for text, width in ((excitation, 22), (ptr, 965), (renderer, 961)):
            self.assertIn(f"[{width}, 1]", text)
            self.assertIn("packedInput", text)

    def test_builder_runtime_guard_reads_block_type_ports_and_line_destinations(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        guard = function_body(builder, "validateSingleInputInterpretedFcn")
        for token in ('"BlockType"', '"MATLABFcn"', '"PortHandles"', "ports.Inport", "numel(ports.Inport)", '"Line"', '"DstPortHandle"'):
            self.assertIn(token, guard)
        self.assertIn("validateSingleInputInterpretedFcn", builder)

    def test_authored_runtime_suite_reads_real_interpreted_port_count_and_mux_widths(self) -> None:
        suite = (ROOT / "tests" / "test_s12_engine_sound_v11_simulink_models.m").read_text(encoding="utf-8")
        for token in ("PortHandles", "Excitation Clock Mux", "Renderer Input Mux", "PTR Input Mux", "numel(ports.Inport)", "[960 2]"):
            self.assertIn(token, suite)


def source(name: str) -> str:
    return (V11 / name).read_text(encoding="utf-8")


def function_body(text: str, name: str) -> str:
    match = re.search(rf"(?m)^function\b[^\n]*\b{re.escape(name)}\b[^\n]*\n", text)
    if not match:
        return ""
    next_function = re.search(r"(?m)^function\b", text[match.end():])
    end = match.end() + next_function.start() if next_function else len(text)
    return text[match.start():end]


if __name__ == "__main__":
    unittest.main(verbosity=2)
