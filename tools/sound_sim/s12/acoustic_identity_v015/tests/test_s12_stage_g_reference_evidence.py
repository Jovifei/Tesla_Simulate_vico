from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import (
    _read_pcm24_wav,
    _write_pcm24_wav,
)
from tools.sound_sim.s12.acoustic_identity_v015.render_realism_v10 import (
    _RENDERERS,
    _render_stateful,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.reference_evidence import (
    DEFAULT_REFERENCE_WINDOWS,
    build_stage_g_reference_evidence,
    extract_final_pcm_reference_features,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_pcm_extractor_preserves_full_spectrum_denominator(tmp_path: Path) -> None:
    sample_rate_hz = 48000
    duration_s = 2.0
    time_s = np.arange(int(sample_rate_hz * duration_s), dtype=np.float64) / sample_rate_hz
    # Half of the signal energy is deliberately above the highest audited band.
    mono = 0.2 * np.sin(2.0 * np.pi * 100.0 * time_s) + 0.2 * np.sin(2.0 * np.pi * 15000.0 * time_s)
    wav_path = _write_pcm24_wav(tmp_path / "final_pcm.wav", np.column_stack((mono, mono)))

    result = extract_final_pcm_reference_features(
        wav_path,
        {"idle": (0.0, 0.5), "acceleration": (0.5, 1.25), "afterfire": (1.25, 2.0)},
    )

    assert result["analysis_domain"] == "relative_recording_features_only"
    assert tuple(result["segments"]) == ("idle", "acceleration", "afterfire")
    assert sum(result["segments"]["idle"]["band_shares"]) < 0.55


def test_reference_evidence_uses_one_trace_one_gain_and_final_pcm_windows(tmp_path: Path) -> None:
    windows = {"idle": (0.0, 0.30), "acceleration": (0.30, 0.65), "afterfire": (0.65, 1.0)}

    def same_as_stage_c(vehicle_id, trace):
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)

    evidence = build_stage_g_reference_evidence(
        "hellcat",
        tmp_path / "run_1",
        stage_g_renderer=same_as_stage_c,
        duration_s=1.0,
        windows=windows,
        candidate_sha256="1" * 64,
    )

    assert evidence["trace_sha256"]["stage_c"] == evidence["trace_sha256"]["stage_g"]
    assert evidence["reference_windows_s"] == {name: list(window) for name, window in windows.items()}
    assert evidence["pipeline_order"][-3:] == ["one_fixed_whole_cycle_gain", "pcm24", "reference_feature_extractor"]
    for role in ("stage_c", "stage_g"):
        role_root = tmp_path / "run_1" / "hellcat" / role
        full_cycle_path = role_root / "full_cycle.wav"
        full_cycle = _read_pcm24_wav(full_cycle_path)
        assert _sha256(full_cycle_path) == evidence["roles"][role]["full_cycle_sha256"]
        assert np.isfinite(evidence["roles"][role]["whole_cycle_gain_db"])
        assert evidence["roles"][role]["feature_extractor"]["segments"].keys() == windows.keys()
        for state, (start_s, end_s) in windows.items():
            state_audio = _read_pcm24_wav(role_root / f"{state}.wav")
            expected = full_cycle[int(start_s * 48000) : int(end_s * 48000)]
            assert np.array_equal(state_audio, expected)

    # The injected Stage-G renderer is deliberately Stage-C identical.  Equal
    # final PCM hashes prove that role differences are not introduced by the
    # evidence path itself.
    assert evidence["roles"]["stage_c"]["full_cycle_sha256"] == evidence["roles"]["stage_g"]["full_cycle_sha256"]


def test_default_reference_windows_are_the_canonical_60_second_windows() -> None:
    assert DEFAULT_REFERENCE_WINDOWS == {
        "idle": (0.0, 8.0),
        "acceleration": (8.0, 26.0),
        "afterfire": (36.0, 46.0),
    }
