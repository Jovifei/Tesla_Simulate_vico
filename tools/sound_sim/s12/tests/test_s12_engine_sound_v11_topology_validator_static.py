"""Static regression checks for the v1.1 wrapper topology preflight.

These checks parse the MATLAB source because the shared Desktop is deliberately
not used for this repair.  They exercise the validator's declared dashboard
contract sufficiently to prove that four or eleven controls fail and the
canonical twelve-control contract is accepted.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"


class S12EngineSoundV11TopologyValidatorStaticTests(unittest.TestCase):
    def test_central_contract_declares_exactly_twelve_unique_dashboard_blocks(self) -> None:
        dashboard_blocks = central_dashboard_blocks()

        self.assertEqual(len(dashboard_blocks), 12)
        self.assertEqual(len(set(dashboard_blocks)), 12)
        self.assertEqual(dashboard_blocks[:4], (
            "Dashboard RPM",
            "Dashboard Load",
            "Dashboard Acceleration",
            "Dashboard Throttle",
        ))

    def test_validator_derives_dashboard_expectation_from_the_json_backed_helper(self) -> None:
        validator = source("s12_v11_validate_model_topology.m")

        self.assertIn('profile = s12_v11_load_profile(contract.vehicle_id);', validator)
        self.assertIn('dashboardControls = s12_v11_model_dashboard_controls(profile);', validator)
        self.assertIn('expectedDashboard = string({dashboardControls.dashboard_name});', validator)
        self.assertNotIn('expectedDashboard = ["Dashboard RPM", "Dashboard Load", ...', validator)

    def test_parsed_validator_contract_accepts_twelve_and_rejects_four_or_eleven(self) -> None:
        expected = validator_dashboard_blocks()
        central = central_dashboard_blocks()

        self.assertEqual(expected, central)
        self.assertTrue(validator_accepts(expected, central))
        self.assertFalse(validator_accepts(central[:4], central))
        self.assertFalse(validator_accepts(central[:-1], central))

    def test_builder_requires_each_declared_dashboard_block_to_have_a_real_binding(self) -> None:
        builder = source("s12_v11_build_simulink_models.m")
        topology = function_body(builder, "validateWrapperTopology")
        binding = function_body(builder, "validateDashboardBinding")

        self.assertIn('if ~isequal(string({controls.dashboard_name}), string(contract.dashboard_blocks))', builder)
        self.assertIn('for index = 1:numel(contract.dashboard_blocks)', topology)
        self.assertIn('validateDashboardBinding(dashboardPath, expectedControlPath)', topology)
        for token in ('binding.BlockPath', 'binding.ParamName', '"Value"', 'getBlock'):
            self.assertIn(token, binding)


def central_dashboard_blocks() -> tuple[str, ...]:
    contracts = source("s12_v11_model_contracts.m")
    match = re.search(r'dashboardBlocks\s*=\s*\[(.*?)\];', contracts, re.DOTALL)
    if not match:
        raise AssertionError("Central dashboardBlocks contract is missing.")
    return tuple(re.findall(r'"(Dashboard [^"]+)"', match.group(1)))


def validator_dashboard_blocks() -> tuple[str, ...]:
    validator = source("s12_v11_validate_model_topology.m")
    if 'dashboardControls = s12_v11_model_dashboard_controls(profile);' in validator:
        return central_dashboard_blocks()
    match = re.search(r'expectedDashboard\s*=\s*\[(.*?)\];', validator, re.DOTALL)
    if not match:
        raise AssertionError("Validator does not declare a dashboard expectation.")
    return tuple(re.findall(r'"(Dashboard [^"]+)"', match.group(1)))


def validator_accepts(actual: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    """Python equivalent of MATLAB's ordered ``isequal`` dashboard gate."""

    return len(expected) == 12 and len(set(expected)) == 12 and actual == expected


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
