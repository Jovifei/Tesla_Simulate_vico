"""RED contracts for the deterministic Stage C realism layers."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

S12_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(S12_ROOT))

from acoustic_identity_v015 import SourceRender, VehicleStateTrace  # noqa: E402
from acoustic_identity_v015.acoustic_layers import (  # noqa: E402
    apply_afterfire,
    apply_exhaust_rumble,
    apply_pre_ptr_equalization,
    apply_shift_dynamics,
    detect_shift_events,
)
from acoustic_identity_v015.acoustic_layers.realism_profiles import (  # noqa: E402
    SUPPORTED_REALISM_VEHICLE_IDS,
    get_realism_profile,
)
from acoustic_identity_v015.acoustic_analysis.realism_metrics import compute_realism_metrics  # noqa: E402


def _trace(duration_s: float = 1.5, sample_rate_hz: int = 8000, hot: bool = False) -> VehicleStateTrace:
    time_s = np.arange(int(duration_s * sample_rate_hz) + 1, dtype=np.float64) / sample_rate_hz
    rpm = np.full(time_s.size, 5600.0 if hot else 2200.0)
    load = np.full(time_s.size, 0.78 if hot else 0.35)
    throttle = np.full(time_s.size, 0.03 if hot else 0.65)
    if hot:
        throttle[time_s < 0.55] = 0.82
        load[time_s < 0.55] = 0.80
        rpm[time_s >= 0.55] -= 900.0 * (time_s[time_s >= 0.55] - 0.55)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _shift_trace(sample_rate_hz: int = 8000) -> VehicleStateTrace:
    time_s = np.arange(0.0, 1.2 + 1.0 / sample_rate_hz, 1.0 / sample_rate_hz)
    rpm = np.interp(time_s, (0.0, 0.35, 0.40, 0.72, 1.2), (3000.0, 4200.0, 3000.0, 3400.0, 4300.0))
    load = np.full(time_s.size, 0.82)
    throttle = np.full(time_s.size, 0.88)
    return VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()


def _render(trace: VehicleStateTrace, sample_rate_hz: int = 8000) -> SourceRender:
    t = trace.time_s
    mono = 0.15 * np.sin(2.0 * np.pi * 55.0 * t) + 0.03 * np.sin(2.0 * np.pi * 4200.0 * t)
    stereo = np.column_stack((mono, 0.92 * mono))
    return SourceRender(
        pressure=stereo,
        stems={"pressure_pulse": stereo.copy(), "exhaust": stereo.copy()},
        diagnostics={},
    ).validate()


class StageCProfileTests(unittest.TestCase):
    def test_profile_registry_covers_reference_and_renderer_vehicle_set(self) -> None:
        from acoustic_identity_v015.acoustic_layers.idle_dynamics import _PROFILES as idle_profiles
        from acoustic_identity_v015.acoustic_layers.low_frequency_body import _BODY_PROFILES as body_profiles
        from acoustic_identity_v015.render_drive_cycle_v10 import _PROFILE as drive_profiles
        from acoustic_identity_v015.render_realism_v10 import _RENDERERS as renderers

        manifest = json.loads(
            (S12_ROOT / "acoustic_identity_v015" / "reference_database" / "realism_reference_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(SUPPORTED_REALISM_VEHICLE_IDS), set(manifest["vehicles"]))
        self.assertEqual(len(SUPPORTED_REALISM_VEHICLE_IDS), 8)
        self.assertEqual(set(SUPPORTED_REALISM_VEHICLE_IDS), set(renderers))
        self.assertEqual(set(SUPPORTED_REALISM_VEHICLE_IDS), set(idle_profiles))
        self.assertEqual(set(SUPPORTED_REALISM_VEHICLE_IDS), set(body_profiles))
        self.assertEqual(set(SUPPORTED_REALISM_VEHICLE_IDS), set(drive_profiles))
        for vehicle_id in SUPPORTED_REALISM_VEHICLE_IDS:
            profile = get_realism_profile(vehicle_id)
            self.assertEqual(profile.provenance, "C/synthetic")

    def test_unknown_vehicle_fails_closed_and_formal_drive_cycle_has_eight_profiles(self) -> None:
        from acoustic_identity_v015.render_drive_cycle_v10 import _PROFILE, build_drive_cycle_trace

        self.assertEqual(set(_PROFILE), set(SUPPORTED_REALISM_VEHICLE_IDS))
        with self.assertRaises(ValueError):
            get_realism_profile("unknown_vehicle")
        for vehicle_id in SUPPORTED_REALISM_VEHICLE_IDS:
            trace = build_drive_cycle_trace(vehicle_id, duration_s=30.0)
            self.assertEqual(len(detect_shift_events(trace)), 3)


class StageCLayerTests(unittest.TestCase):
    def test_pre_equalization_transforms_pressure_and_stems_with_same_linear_filter(self) -> None:
        trace = _trace()
        render = _render(trace)
        equalized = apply_pre_ptr_equalization(render, "ferrari_458", trace, 8000)
        self.assertEqual(equalized.pressure.shape, render.pressure.shape)
        self.assertNotEqual(equalized.pressure.tobytes(), render.pressure.tobytes())
        self.assertTrue(np.all(np.isfinite(equalized.pressure)))
        self.assertEqual(equalized.diagnostics["pre_equalization_high_shelf_db"], -17.0)
        self.assertEqual(equalized.stems["pressure_pulse"].shape, render.pressure.shape)

    def test_shift_detection_requires_a_local_rpm_step_and_emits_named_stems(self) -> None:
        trace = _shift_trace()
        events = detect_shift_events(trace, 8000)
        self.assertEqual(len(events), 1)
        shifted = apply_shift_dynamics(_render(trace), "hellcat", trace, 8000)
        self.assertIn("shift_torque_interruption", shifted.stems)
        self.assertIn("shift_impact", shifted.stems)
        self.assertIn("shift_recovery_boom", shifted.stems)
        self.assertEqual(shifted.diagnostics["shift_event_count"], 1)

    def test_exhaust_rumble_is_pressure_coupled_and_load_dependent(self) -> None:
        trace = _trace()
        high = apply_exhaust_rumble(_render(trace), "hellcat", trace, 8000)
        low_trace = VehicleStateTrace(trace.time_s, trace.rpm, np.full(trace.rpm.size, 0.05), np.full(trace.rpm.size, 0.05), trace.acceleration_mps2)
        low = apply_exhaust_rumble(_render(low_trace), "hellcat", low_trace, 8000)
        self.assertGreater(high.diagnostics["rumble_energy"], low.diagnostics["rumble_energy"])
        zero = SourceRender(np.zeros_like(high.pressure), {"pressure_pulse": np.zeros_like(high.pressure)}, {}).validate()
        zeroed = apply_exhaust_rumble(zero, "hellcat", trace, 8000)
        self.assertEqual(zeroed.diagnostics["rumble_energy"], 0.0)

    def test_afterfire_requires_hot_closed_throttle_and_is_deterministic(self) -> None:
        trace = _trace(hot=True)
        first = apply_afterfire(_render(trace), "ferrari_458", trace, 8000)
        second = apply_afterfire(_render(trace), "ferrari_458", trace, 8000)
        np.testing.assert_array_equal(first.stems["afterfire"], second.stems["afterfire"])
        self.assertGreater(first.diagnostics["afterfire_event_count"], 0)
        self.assertGreater(first.diagnostics["afterfire_centroid_hz"], 0.0)
        cold = apply_afterfire(_render(_trace(hot=False)), "ferrari_458", _trace(hot=False), 8000)
        self.assertEqual(cold.diagnostics["afterfire_event_count"], 0)


class StageCIntegrationTests(unittest.TestCase):
    def test_metrics_expose_shift_rumble_and_afterfire_features(self) -> None:
        trace = _trace(hot=True)
        render = apply_afterfire(_render(trace), "hellcat", trace, 8000)
        render = apply_exhaust_rumble(render, "hellcat", trace, 8000)
        render = apply_shift_dynamics(render, "hellcat", trace, 8000)
        metrics = compute_realism_metrics("hellcat", render, trace, 8000)
        self.assertIn("rumble_energy_30_90hz", metrics["transients"])
        self.assertIn("shift_event_count", metrics["transients"])
        self.assertIn("afterfire_centroid_hz", metrics["transients"])

    def test_deterministic_render_is_independent_of_python_hash_seed(self) -> None:
        code = (
            "import numpy as np; "
            "from acoustic_identity_v015.acoustic_layers import apply_exhaust_rumble; "
            "from acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace; "
            "t=np.arange(801)/8000.0; tr=VehicleStateTrace(t,np.full(801,2200.),np.full(801,.6),np.full(801,.6),np.zeros(801)); "
            "x=np.zeros((801,2)); r=apply_exhaust_rumble(SourceRender(x,{'pressure_pulse':x},{}),'hellcat',tr,8000); "
            "print(np.asarray(r.stems['exhaust_rumble']).tobytes().hex())"
        )
        env = dict(__import__("os").environ, PYTHONPATH=str(S12_ROOT), PYTHONHASHSEED="random")
        a = subprocess.check_output([sys.executable, "-c", code], env=env, text=True)
        b = subprocess.check_output([sys.executable, "-c", code], env=env, text=True)
        self.assertEqual(a, b)

    def test_formal_stateful_chain_records_all_layers_before_frozen_ptr(self) -> None:
        from acoustic_identity_v015.render_realism_v10 import _RENDERERS, _render_stateful

        trace = _trace(duration_s=0.25)
        rendered = _render_stateful(_RENDERERS["ferrari_458"], "ferrari_458", trace)
        self.assertIn("exhaust_rumble", rendered.stems)
        self.assertIn("shift_torque_interruption", rendered.stems)
        self.assertIn("pre_equalization_band_shares_before", rendered.diagnostics)
        self.assertEqual(
            rendered.diagnostics["realism_layer_order"].split(" -> ")[-1],
            "frozen_ptr",
        )


if __name__ == "__main__":
    unittest.main()
