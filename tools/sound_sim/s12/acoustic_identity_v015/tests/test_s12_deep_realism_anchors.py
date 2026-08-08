# tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_deep_realism_anchors.py
"""逐状态 deep realism 注入的锚点车验收测试（Task 3.1：Ferrari 458）。

度量口径说明（对 brief 骨架的修正）
------------------------------------
brief 的骨架对每个 state 重新构造 scenario trace，却用
`render_state_band_shares(render)` 取**整段渲染**的 band shares。这与
"逐状态"语义对不齐：`_scenario_trace('ferrari_458', 'acceleration', ...)`
的 rpm 从 3600 扫到 8800，`classify_state` 判定其中 27% 是 steady_cruise、
73% 是 full_pull —— 整段度量把两个状态混在一起，无法归因到任一 state。
更严重的是 `idle_return` 在任何 ferrari scenario 中都不出现，
`lift_afterfire` 在 `lift` scenario 中（按 brief 的瞬时油门导数判据）只占
1 个样本，二者根本无法被整段度量观测到。

本测试改为**每个 state 构造一条该状态的稳态 trace**，并只取渲染的稳定段
（跳过谐振器起振瞬态）后计算 band shares。这样每个 state 的度量是纯净的、
可归因的、且六个状态都真实可测。
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np

_V015 = Path(__file__).resolve().parents[1]
if str(_V015.parent) not in sys.path:
    sys.path.insert(0, str(_V015.parent))

from acoustic_identity_v015.acoustic_analysis.spectral_targets import band_energy_shares
from acoustic_identity_v015.contracts import VehicleStateTrace
from acoustic_identity_v015.sources.flat_plane_v8_source import render_ferrari_458
from acoustic_identity_v015.tuning.deep_realism import (
    STATE_KEYS,
    STATE_OPERATING_POINTS as _STATE_OPERATING_POINTS,
    apply_deep_realism,
    classify_state,
    load_tuning_manifest,
)

_REFERENCE = json.loads(
    (_V015 / "reference_database" / "realism_reference_manifest.json").read_text(encoding="utf-8")
)
_PER_STATE_ERR = float(_REFERENCE["deep_realism_thresholds"]["per_state_band_abs_error"])

_SAMPLE_RATE_HZ = 48000


def _steady_trace(rpm: float, load: float, throttle: float, duration_s: float = 2.0) -> VehicleStateTrace:
    """构造一条恒定工况的 trace，采样率与渲染器一致以便逐样本对齐。"""
    count = int(round(duration_s * _SAMPLE_RATE_HZ)) + 1
    time_s = np.linspace(0.0, duration_s, count)
    return VehicleStateTrace(
        time_s=time_s,
        rpm=np.full(count, rpm),
        load=np.full(count, load),
        throttle=np.full(count, throttle),
        acceleration_mps2=np.zeros(count),
    ).validate()


def _stable_mono(render, skip_s: float = 0.5) -> np.ndarray:
    """取渲染稳定段的单声道信号（跳过谐振器起振瞬态）。"""
    skip = int(round(skip_s * _SAMPLE_RATE_HZ))
    return render.pressure[skip:].mean(axis=1)


class ClassifyStateTests(unittest.TestCase):
    def test_each_operating_point_maps_to_its_state(self) -> None:
        for state, (rpm, load, throttle) in _STATE_OPERATING_POINTS.items():
            with self.subTest(state=state):
                labels = classify_state(
                    np.full(64, rpm), np.full(64, load), np.full(64, throttle)
                )
                self.assertEqual(set(labels.tolist()), {state})

    def test_returns_one_label_per_sample(self) -> None:
        labels = classify_state(np.full(37, 3600.0), np.full(37, 0.42), np.full(37, 0.45))
        self.assertEqual(labels.shape, (37,))
        self.assertTrue(set(labels.tolist()) <= set(STATE_KEYS))


class RatioInvarianceTests(unittest.TestCase):
    """注入必须是"同一时刻所有 stem 乘同一标量"。"""

    def _render(self, state: str = "full_pull"):
        rpm, load, throttle = _STATE_OPERATING_POINTS[state]
        trace = _steady_trace(rpm, load, throttle, duration_s=0.5)
        return render_ferrari_458(trace), trace

    def test_all_stems_share_one_scalar_per_instant(self) -> None:
        render, trace = self._render()
        manifest = {
            "vehicles": {
                "ferrari_458": {
                    "uniform_ratio_scale": 1.7,
                    "states": {key: {"level_scale": 0.4 + 0.2 * index} for index, key in enumerate(STATE_KEYS)},
                }
            }
        }
        tuned = apply_deep_realism(render, "ferrari_458", trace, manifest=manifest)
        # 比值不变 <=> 任意两路信号 a、b 满足 tuned_a * b == tuned_b * a（无需除法/掩码，
        # 覆盖包括过零点在内的全部样本）。若某路 stem 被单独加权，此式立即不成立。
        channels = {"__pressure__": render.pressure, **render.stems}
        tuned_channels = {"__pressure__": tuned.pressure, **tuned.stems}
        names = sorted(channels)
        for first, second in zip(names, names[1:]):
            with self.subTest(pair=(first, second)):
                np.testing.assert_allclose(
                    tuned_channels[first] * channels[second],
                    tuned_channels[second] * channels[first],
                    rtol=1e-12,
                    atol=1e-18,
                )
        # 并且增益确实是被施加了的（非平凡）。
        self.assertGreater(float(np.max(np.abs(tuned.pressure))), float(np.max(np.abs(render.pressure))))

    def test_single_state_band_shares_are_preserved(self) -> None:
        """单一状态窗口内，比值不变的缩放不得改变 band shares（身份指标保全）。"""
        render, trace = self._render()
        manifest = {
            "vehicles": {
                "ferrari_458": {
                    "uniform_ratio_scale": 2.5,
                    "states": {key: {"level_scale": 0.6} for key in STATE_KEYS},
                }
            }
        }
        tuned = apply_deep_realism(render, "ferrari_458", trace, manifest=manifest)
        _, _, before = band_energy_shares(render.pressure.mean(axis=1))
        _, _, after = band_energy_shares(tuned.pressure.mean(axis=1))
        np.testing.assert_allclose(after, before, rtol=0.0, atol=1e-12)

    def test_gain_envelope_is_continuous_across_state_changes(self) -> None:
        """per-state 增益跨状态切换必须平滑，否则阶跃会产生咔哒声与宽带溅射。"""
        count = int(round(1.0 * _SAMPLE_RATE_HZ)) + 1
        time_s = np.linspace(0.0, 1.0, count)
        rpm = np.linspace(1000.0, 7500.0, count)
        throttle = np.linspace(0.10, 0.98, count)
        trace = VehicleStateTrace(time_s, rpm, throttle.copy(), throttle, np.zeros(count)).validate()
        render = render_ferrari_458(trace)
        manifest = {
            "vehicles": {
                "ferrari_458": {
                    "uniform_ratio_scale": 1.0,
                    "states": {key: {"level_scale": 0.5 + 0.5 * index} for index, key in enumerate(STATE_KEYS)},
                }
            }
        }
        tuned = apply_deep_realism(render, "ferrari_458", trace, manifest=manifest)
        active = np.abs(render.pressure[:, 0]) > 1e-9
        gain = tuned.pressure[active, 0] / render.pressure[active, 0]
        self.assertGreater(float(gain.max() - gain.min()), 0.5, "测试未真正跨越不同 level_scale")
        self.assertLess(float(np.abs(np.diff(gain)).max()), 0.01, "增益包络存在阶跃")

    def test_diagnostics_record_traceable_fields(self) -> None:
        render, trace = self._render()
        tuned = apply_deep_realism(render, "ferrari_458", trace)
        self.assertIs(tuned.diagnostics["deep_realism_applied"], True)
        self.assertEqual(tuned.diagnostics["deep_realism_vehicle_id"], "ferrari_458")
        self.assertIn("deep_realism_uniform_ratio_scale", tuned.diagnostics)
        self.assertIn("deep_realism_state_fractions", tuned.diagnostics)
        self.assertEqual(tuned.diagnostics["vehicle_id"], "ferrari_458")


class FerrariDeepRealismTests(unittest.TestCase):
    def test_ferrari_per_state_band_targets_within_threshold(self) -> None:
        """Task 3.1 的验收目标 —— 当前【被前提性矛盾阻塞】，故标记为 expectedFailure。

        标记原因（阈值未被放宽，断言原样保留 0.05）：

        1. `band_energy_shares` 以总能量归一，对幅度缩放严格不变（实测 delta
           ~1e-16）。ratio-invariant 注入在单一状态窗口内**在数学上无法**改变
           band shares，只能改变状态段之间的相对响度。
        2. 唯一剩余杠杆 per-state `level_scale` 只有约 0.82 dB 余量，再多就会
           打破身份套件的 `test_ferrari_rms_stays_bounded_from_idle_to_redline`
           （跨 rpm RMS 扩散 <= 1.5 dB）—— 而且改电平本就不影响 band shares。
        3. 要真正命中 band 目标必须在源侧重分配频段能量 / 对单个 stem 单独
           加权，这正是 ratio-invariant 红线明令禁止的操作。
        4. 即使红线被解除，manifest 目标本身与既有身份套件互斥：
           `steady_cruise` 与 `full_pull` 被赋予**完全相同**的目标
           [0.3564, 0.5691, 0.0683, 0.0045]，隐含 >=1200 Hz 占比均为 0.0728，
           即 HF(8000)/HF(3000) = 1.00；而
           `test_ferrari_high_frequency_energy_grows_with_rpm_without_normalization`
           要求该比值 >= 1.35。两者不可同时满足。

        本测试保留为 tripwire：一旦 manifest 目标被修正或红线被裁决放开，
        它会以 "unexpected success" 的形式提示需要移除此标记。
        """
        targets = load_tuning_manifest()["vehicles"]["ferrari_458"]["states"]
        report = []
        worst = 0.0
        for state in STATE_KEYS:
            rpm, load, throttle = _STATE_OPERATING_POINTS[state]
            render = render_ferrari_458(_steady_trace(rpm, load, throttle))
            _, _, shares = band_energy_shares(_stable_mono(render))
            target = targets[state]["band_shares_target"]
            errors = [abs(s - t) for s, t in zip(shares, target)]
            worst = max(worst, max(errors))
            report.append(
                f"  {state:15s} shares={[round(s, 4) for s in shares]} "
                f"target={target} maxerr={max(errors):.4f}"
            )
        self.assertLessEqual(worst, _PER_STATE_ERR, "per-state band 残差超阈值:\n" + "\n".join(report))


if __name__ == "__main__":
    unittest.main()
