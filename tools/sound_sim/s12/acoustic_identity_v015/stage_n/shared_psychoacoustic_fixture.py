"""Create one deterministic MAT payload for MATLAB/MoSQITo cross-validation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


FIXTURE_ID = "s12-stage-n-shared-psychoacoustic-fixture-v1"
SAMPLE_RATE_HZ = 48_000
DURATION_S = 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signals() -> dict[str, np.ndarray]:
    time = np.arange(SAMPLE_RATE_HZ * DURATION_S, dtype=np.float64) / SAMPLE_RATE_HZ
    base = 0.02 * np.sin(2.0 * np.pi * 1_000.0 * time)
    noise = 0.01 * np.random.default_rng(17).normal(size=time.size)
    return {
        "base": base,
        "gain": 2.0 * base,
        "high_frequency_boost": base + 0.08 * np.sin(2.0 * np.pi * 7_000.0 * time),
        "fast_am": (1.0 + 0.7 * np.sin(2.0 * np.pi * 70.0 * time)) * base,
        "slow_am": (1.0 + 0.7 * np.sin(2.0 * np.pi * 4.0 * time)) * base,
        "prominent_tone": noise + 0.15 * np.sin(2.0 * np.pi * 1_000.0 * time),
    }


def write_shared_fixture(output_root: Path) -> dict[str, object]:
    """Write a new immutable shared fixture root and its hash-bound manifest."""

    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite shared psychoacoustic fixture: {output_root}")
    try:
        from scipy.io import savemat
    except ImportError as exc:  # pragma: no cover - dependency is verified in integration use
        raise RuntimeError("SciPy is required to write the shared psychoacoustic MAT fixture") from exc
    output_root.mkdir(parents=True)
    signals = _signals()
    mat_path = output_root / "shared_psychoacoustic_fixture.mat"
    savemat(
        mat_path,
        {"sample_rate_hz": np.asarray([[SAMPLE_RATE_HZ]], dtype=np.float64), **signals},
        do_compression=True,
        long_field_names=True,
    )
    manifest = {
        "schema_version": "s12-stage-n-shared-psychoacoustic-fixture-1",
        "fixture_id": FIXTURE_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "duration_s": DURATION_S,
        "fixture_mat": mat_path.name,
        "fixture_mat_sha256": _sha256(mat_path),
        "signals": {
            name: {"samples": int(value.size), "float64_sha256": hashlib.sha256(value.tobytes()).hexdigest()}
            for name, value in signals.items()
        },
        "directions": {
            "gain_increases_loudness": ["base", "gain"],
            "high_frequency_increases_sharpness": ["base", "high_frequency_boost"],
            "fast_am_increases_roughness": ["base", "fast_am"],
            "slow_am_increases_fluctuation": ["base", "slow_am"],
            "prominent_tone_increases_tonality": ["base", "prominent_tone"],
        },
    }
    manifest_path = output_root / "fixture_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        **manifest,
        "fixture_root": str(output_root),
        "fixture_manifest_path": str(manifest_path),
        "fixture_manifest_sha256": _sha256(manifest_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    print(json.dumps(write_shared_fixture(arguments.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
