# 回归锁测试：锁定 Ferrari 两项 deep-realism 不变量。
#
# 本文件不重新实现既有断言，而是通过 subprocess 运行既有 identity 套件中
# 的两个已通过测试，并断言其整体退出码为 0。这样后续任何 deep-realism
# 编辑若回退了这两项行为，本锁测试会失败，从而防止静默回归。
#
# 注意：既有测试实际位于 tools/sound_sim/s12/tests/ 下；这里通过
# `_V015.parent` 将 cwd 解析到 tools/sound_sim/s12，使套件相对路径正确。
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest

_V015 = Path(__file__).resolve().parents[1]
_SUITE = "tests/test_s12_engine_acoustic_identity_v015.py"


def _run(args: list[str]) -> int:
    return subprocess.run([sys.executable, "-m", "pytest", _SUITE, *args, "-q"],
                           cwd=str(_V015.parent)).returncode


class RegressionLockFerrariTests(unittest.TestCase):
    def test_ferrari_rms_bounded_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_ferrari_rms_stays_bounded_from_idle_to_redline_without_output_normalization"]), 0)

    def test_ferrari_high_freq_grows_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_ferrari_high_frequency_energy_grows_with_rpm_without_normalization"]), 0)


class RegressionLockHellcatTests(unittest.TestCase):
    def test_hellcat_blower_shaft_lobe_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_hellcat_blower_has_shaft_lobe_and_upper_families_with_audible_stem_balance"]), 0)


class RegressionLockRx7Tests(unittest.TestCase):
    def test_rx7_housing_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_rx7_housing_resonance_is_event_and_engine_phase_coupled"]), 0)

    def test_rx7_turbo_lift_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_rx7_uses_phase_offset_rotary_events_and_stateful_turbo_lift"]), 0)

    def test_rx7_acceleration_stem_balance_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_rx7_acceleration_stem_balance_keeps_turbo_and_turbine_audible"]), 0)

    def test_rx7_constant_state_locked(self) -> None:
        self.assertEqual(_run(["-k", "test_rx_constant_state_full_pressure_qualifies_order_shape_and_stem_balance"]), 0)


class RegressionLockLufsRmsIntegrationTests(unittest.TestCase):
    def test_same_load_rpm_probes_locked(self) -> None:
        # 锁定 5+ 个集成子测试（LUFS/RMS spread）位于 SourceToPtrBundleLoudnessIntegrationTests::
        # test_same_load_rpm_probes_change_timbre_without_gross_level_spread。
        self.assertEqual(_run(["-k", "test_same_load_rpm_probes_change_timbre_without_gross_level_spread"]), 0)
