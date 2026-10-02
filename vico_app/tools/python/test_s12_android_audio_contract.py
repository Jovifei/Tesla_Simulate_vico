import json
from pathlib import Path

import numpy as np
import export_s12_android_sound_banks as exporter
import soundfile as sf


APP_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = APP_ROOT / "Project" / "android" / "app" / "src" / "main" / "assets" / "s12_v10"


def test_mobile_and_desktop_contract_uses_mono_48k_fixed_loudness():
    assert exporter.APP_RATE == 48000
    assert exporter.APP_CHANNELS == 1
    assert exporter.TARGET_LUFS == -16.0
    assert exporter.PEAK_LIMIT_DBFS == -1.5


def test_each_vehicle_manifest_declares_common_trace_and_state_layers():
    vehicle_keys = (
        "hellcat_v6",
        "ferrari_458",
        "lfa",
        "gtr_r35",
        "c63_w204_v6",
        "supra_jza80",
    )
    for key in vehicle_keys:
        manifest = json.loads((ASSET_ROOT / key / "manifest.json").read_text(encoding="utf-8"))
        contract = manifest["audio_contract"]
        assert contract == {
            "sample_rate_hz": 48000,
            "channels": 1,
            "channel_layout": "mono",
            "target_integrated_lufs": -16.0,
            "peak_limit_dbfs": -1.5,
            "downmix": "arithmetic_mean_left_right",
            "gain_policy": "one_fixed_vehicle_gain_from_common_drive_cycle",
        }
        assert manifest["common_input_trace"]["fields"] == [
            "time_s",
            "rpm",
            "load",
            "throttle",
            "acceleration_mps2",
        ]
        assert manifest["layer_contract"] == {
            "continuous": "final_s12_pressure_including_low_frequency_body_and_exhaust_rumble",
            "low_frequency": ["low_frequency_body", "exhaust_rumble"],
            "shift": ["shift_impact", "shift_recovery_boom"],
            "afterfire": "afterfire",
        }
        assert manifest["shift_events"]


def test_each_vehicle_wav_matches_contract_without_clipping():
    peak_limit = 10 ** (exporter.PEAK_LIMIT_DBFS / 20.0)
    for vehicle_root in sorted(path for path in ASSET_ROOT.iterdir() if path.is_dir()):
        wavs = sorted(vehicle_root.glob("*.wav"))
        assert len(wavs) == 20
        for wav in wavs:
            samples, sample_rate = sf.read(wav, always_2d=True, dtype="float32")
            assert sample_rate == exporter.APP_RATE
            assert samples.shape[1] == exporter.APP_CHANNELS
            assert np.all(np.isfinite(samples))
            assert float(np.max(np.abs(samples))) <= peak_limit + 1e-5

