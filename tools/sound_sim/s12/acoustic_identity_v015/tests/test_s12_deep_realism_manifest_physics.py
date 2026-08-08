# tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_deep_realism_manifest_physics.py
"""deep-realism tuning manifest 的物理一致性护栏（Task 3.0）。

本文件守两件事：

1. **manifest 数据本身自洽**：六态不塌陷、高频占比随 rpm 单调上移、怠速低频
   占主导、归一、provenance 逐态如实标注、渲染必需字段不丢。
2. **重建目标所用的物理先验站得住**：转子机主序是 2 阶不是 4 阶、十字曲轴 V8
   有半阶分量而平面曲轴没有、band 能量随 rpm 从低频向高频迁移。

第 2 组断言直接测 `tuning/reference_reconstruction.py` 的正演模型，避免"只要
数字好看就行"——数字必须由一个可复现、可审计的物理模型产生。
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

_V015 = Path(__file__).resolve().parents[1]
if str(_V015.parent) not in sys.path:
    sys.path.insert(0, str(_V015.parent))

from acoustic_identity_v015.tuning.reference_reconstruction import (
    ENGINE_PRIORS,
    fit_recording_chain,
    firing_frequency_hz,
    order_components,
    physics_band_shares,
    state_targets,
)

_MANIFEST = json.loads(
    (_V015 / "targets" / "deep_realism_tuning_manifest.json").read_text(encoding="utf-8")
)

_VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
_STATES = (
    "idle",
    "idle_return",
    "steady_cruise",
    "acceleration",
    "full_pull",
    "lift_afterfire",
)
# 高频占比随 rpm 单调不减的检查链（按工况点 rpm 升序）。
_RPM_ORDERED_STATES = ("idle", "idle_return", "steady_cruise", "acceleration", "full_pull")
_ALLOWED_PROVENANCE = {"compensated_reference", "physics_derived", "hybrid"}


def _target(vehicle: str, state: str) -> list[float]:
    return _MANIFEST["vehicles"][vehicle]["states"][state]["band_shares_target"]


def _high_share(shares: list[float]) -> float:
    """band 2 + band 3 = >=1000 Hz 的能量占比。"""
    return shares[2] + shares[3]


class ManifestStateDifferentiationTests(unittest.TestCase):
    """缺陷 1 的回归防线：六态不得塌陷成三态。"""

    def test_all_six_states_have_distinct_band_targets(self) -> None:
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                seen = {tuple(_target(vehicle, state)) for state in _STATES}
                self.assertEqual(
                    len(seen),
                    len(_STATES),
                    f"{vehicle} 的六态 band 目标出现重复（塌陷）: "
                    + "; ".join(f"{s}={_target(vehicle, s)}" for s in _STATES),
                )

    def test_load_dependent_states_are_mutually_distinct(self) -> None:
        """steady_cruise / acceleration / full_pull 三者互不相同（brief 断言 1）。"""
        trio = ("steady_cruise", "acceleration", "full_pull")
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                self.assertEqual(len({tuple(_target(vehicle, s)) for s in trio}), 3)


class ManifestSpectralTrendTests(unittest.TestCase):
    def test_high_band_share_grows_monotonically_with_rpm(self) -> None:
        """阶次谐波级数随 rpm 整体上移，band 边界固定 => 高频占比单调不减。"""
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                shares = [_high_share(_target(vehicle, s)) for s in _RPM_ORDERED_STATES]
                for lower, upper, low_state, high_state in zip(
                    shares, shares[1:], _RPM_ORDERED_STATES, _RPM_ORDERED_STATES[1:]
                ):
                    self.assertLess(
                        lower,
                        upper,
                        f"{vehicle}: {low_state} 高频占比 {lower:.4f} 未低于 {high_state} 的 {upper:.4f}",
                    )

    def test_ferrari_high_band_ratio_clears_identity_suite_requirement(self) -> None:
        """对齐身份套件 test_ferrari_high_frequency_energy_grows_with_rpm...:454 的 >=1.35。"""
        ratio = _high_share(_target("ferrari_458", "full_pull")) / _high_share(
            _target("ferrari_458", "steady_cruise")
        )
        self.assertGreaterEqual(ratio, 1.35, f"full_pull/steady_cruise 高频比 = {ratio:.3f}")

    def test_idle_low_band_share_is_physically_plausible(self) -> None:
        """缺陷 2 的回归防线：怠速点火基频在 20-250 Hz 内，低频不可能只占 1%。"""
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                low = _target(vehicle, "idle")[0]
                self.assertGreater(low, 0.30, f"{vehicle} 怠速低频占比仅 {low:.4f}")


class ManifestIntegrityTests(unittest.TestCase):
    def test_band_shares_are_normalised(self) -> None:
        for vehicle in _VEHICLES:
            for state in _STATES:
                with self.subTest(vehicle=vehicle, state=state):
                    self.assertAlmostEqual(sum(_target(vehicle, state)), 1.0, delta=1e-6)

    def test_every_state_declares_an_allowed_provenance(self) -> None:
        for vehicle in _VEHICLES:
            for state in _STATES:
                with self.subTest(vehicle=vehicle, state=state):
                    entry = _MANIFEST["vehicles"][vehicle]["states"][state]
                    self.assertIn("provenance", entry)
                    self.assertIn(entry["provenance"], _ALLOWED_PROVENANCE)

    def test_rx7_states_without_reference_are_marked_physics_derived(self) -> None:
        """参考库对 RX-7 只承认 idle 段，其余五态不得谎称有实测来源。"""
        for state in _STATES:
            if state == "idle":
                continue
            with self.subTest(state=state):
                self.assertEqual(
                    _MANIFEST["vehicles"]["rx7_fd"]["states"][state]["provenance"],
                    "physics_derived",
                )

    def test_render_critical_fields_survive_the_rebuild(self) -> None:
        """apply_deep_realism 依赖 uniform_ratio_scale / level_scale，重建不得丢。"""
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                self.assertIn("uniform_ratio_scale", _MANIFEST["vehicles"][vehicle])
                for state in _STATES:
                    entry = _MANIFEST["vehicles"][vehicle]["states"][state]
                    self.assertIn("level_scale", entry)
                    self.assertIn("order_couplings", entry)

    def test_scope_and_provenance_declarations_are_not_weakened(self) -> None:
        self.assertEqual(_MANIFEST["scope"], "synthetic; uncalibrated; not OEM reproduction")
        self.assertIn("derived", _MANIFEST["reference_provenance"].lower())

    def test_recording_chain_fit_is_recorded_for_audit(self) -> None:
        """滚降补偿是估计值，其参数与残差必须可审计。"""
        block = _MANIFEST["recording_chain_compensation"]
        self.assertIn("assumption", block)
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                fit = block["vehicles"][vehicle]
                for key in ("fc_hz", "order_n", "in_sample_residual", "out_of_sample_residual"):
                    self.assertIn(key, fit)
                self.assertIn("single_chain_consistent", fit)

    def test_physics_prior_parameters_are_recorded_for_audit(self) -> None:
        block = _MANIFEST["physics_prior"]
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                prior = block["vehicles"][vehicle]
                self.assertIn("firing_order", prior)
                self.assertIn("harmonic_rolloff_db_per_octave", prior)
        self.assertEqual(block["vehicles"]["rx7_fd"]["firing_order"], 2.0)
        self.assertEqual(block["vehicles"]["ferrari_458"]["firing_order"], 4.0)


class PhysicsPriorTests(unittest.TestCase):
    """正演模型的物理先验必须真的物理，而不是凑数。"""

    def test_band_shares_sum_to_one(self) -> None:
        for vehicle in _VEHICLES:
            for rpm, load in ((1100.0, 0.12), (3600.0, 0.42), (7200.0, 0.94)):
                with self.subTest(vehicle=vehicle, rpm=rpm):
                    shares = physics_band_shares(vehicle, rpm, load)
                    self.assertEqual(len(shares), 4)
                    self.assertAlmostEqual(sum(shares), 1.0, delta=1e-9)

    def test_rotary_fires_twice_per_shaft_revolution_not_four_times(self) -> None:
        """13B 双转子：每个偏心轴转一圈 2 次燃烧 => 2 阶主序，不是四冲程 V8 的 4 阶。"""
        self.assertAlmostEqual(firing_frequency_hz("rx7_fd", 3000.0), 100.0, delta=1e-9)
        self.assertAlmostEqual(firing_frequency_hz("ferrari_458", 3000.0), 200.0, delta=1e-9)
        self.assertAlmostEqual(firing_frequency_hz("hellcat", 3000.0), 200.0, delta=1e-9)
        self.assertEqual(ENGINE_PRIORS["rx7_fd"].firing_order, 2.0)

    def test_cross_plane_v8_carries_half_order_content_flat_plane_does_not(self) -> None:
        """十字曲轴两 bank 点火不均 => 半阶分量，这是 Hellcat lope 质感的来源。"""
        def half_order_energy(vehicle: str) -> float:
            return sum(
                energy
                for order, _freq, energy in order_components(vehicle, 3000.0, 0.5)
                if abs(order - round(order)) > 1e-9
            )

        self.assertGreater(half_order_energy("hellcat"), 0.0)
        self.assertEqual(half_order_energy("ferrari_458"), 0.0)
        self.assertEqual(half_order_energy("rx7_fd"), 0.0)

    def test_energy_migrates_from_low_to_high_band_as_rpm_rises(self) -> None:
        """band 边界固定而阶次谐波级数随 rpm 线性上移 => 高频占比单调增。"""
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                highs = [
                    sum(physics_band_shares(vehicle, rpm, 0.5)[2:])
                    for rpm in (1000.0, 2000.0, 4000.0, 8000.0)
                ]
                for lower, upper in zip(highs, highs[1:]):
                    self.assertLess(lower, upper, f"{vehicle}: 高频占比未随 rpm 上升 {highs}")

    def test_idle_energy_is_dominated_by_the_low_band(self) -> None:
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                self.assertGreater(physics_band_shares(vehicle, 1100.0, 0.12)[0], 0.5)


class RecordingChainFitTests(unittest.TestCase):
    def test_fit_is_deterministic(self) -> None:
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                first, second = fit_recording_chain(vehicle), fit_recording_chain(vehicle)
                self.assertEqual(first.fc_hz, second.fc_hz)
                self.assertEqual(first.order_n, second.order_n)
                self.assertEqual(first.out_of_sample_residual, second.out_of_sample_residual)

    def test_idle_fit_is_validated_against_the_remaining_segments(self) -> None:
        """brief 的核心自洽性假设（同一录音链）必须被真的检验，而不是被假定。"""
        for vehicle in _VEHICLES:
            with self.subTest(vehicle=vehicle):
                fit = fit_recording_chain(vehicle)
                self.assertGreaterEqual(fit.out_of_sample_residual, fit.in_sample_residual)

    def test_ferrari_single_chain_holds_after_reference_repair(self) -> None:
        """Ferrari 的 idle 与 acceleration 段现在可由同一条 LTI 高通解释。

        历史：本用例原先断言「单链假设必须被拒绝」（out/in > 3）。那个结论是坏
        参考数据的产物，而非物理事实——旧的 idle 靶子并不是引擎怠速，而是 pull
        之间的风噪（谱心 980 Hz，20-250 Hz 仅占 0.9%）。风噪与引擎当然不可能由
        同一条录音链解释，于是拟合器忠实地报告了「多链」。

        修正切段（见 test_s12_reference_idle_physics.py）后，idle 与 acceleration
        取自同一段录音的同一条链，残差比从 >3 降到约 1.8，单链假设成立。该反转
        本身就是参考修复正确性的独立佐证，因此这里把它固化为正向断言。
        """
        fit = fit_recording_chain("ferrari_458")
        self.assertLess(fit.out_of_sample_residual, 3.0 * fit.in_sample_residual)
        self.assertTrue(fit.single_chain_consistent)

    def test_multi_source_vehicles_still_report_multiple_chains(self) -> None:
        """确认单链检测器没有退化成恒真——多源车辆仍须被判为多链。

        hellcat 混合了三段不同录音，rx7_fd 的单一音源被严重低通（8.4 kHz 截止），
        两者都不应通过单链检验。
        """
        for vehicle in ("hellcat", "rx7_fd"):
            with self.subTest(vehicle=vehicle):
                fit = fit_recording_chain(vehicle)
                self.assertGreater(fit.out_of_sample_residual, 3.0 * fit.in_sample_residual)
                self.assertFalse(fit.single_chain_consistent)


class StateTargetAssemblyTests(unittest.TestCase):
    def test_every_state_gets_a_normalised_target_and_provenance(self) -> None:
        for vehicle in _VEHICLES:
            targets = state_targets(vehicle)
            self.assertEqual(set(targets), set(_STATES))
            for state, entry in targets.items():
                with self.subTest(vehicle=vehicle, state=state):
                    self.assertAlmostEqual(sum(entry["band_shares_target"]), 1.0, delta=1e-9)
                    self.assertIn(entry["provenance"], _ALLOWED_PROVENANCE)


if __name__ == "__main__":
    unittest.main()
