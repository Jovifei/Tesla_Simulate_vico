"""Run the S12 v0.6 PC runtime simulator without writing WAV audio."""

from __future__ import annotations

import argparse
from pathlib import Path

from s12_engine_sound_runtime import run_runtime_demo


def main() -> None:
    project_root = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=600.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root.parent / "tasks" / "reports" / "runtime" / "s12-engine-sound-v0.6",
    )
    parser.add_argument(
        "--device-output",
        action="store_true",
        help="stream PCM to the Windows default audio device in real time",
    )
    args = parser.parse_args()
    result = run_runtime_demo(
        args.output, duration_s=args.duration_s, device_output=args.device_output
    )
    print(f"runtime report: {result.report_path}")
    print(
        f"PCM frames={result.pcm_frames} underruns={result.underrun_count} audio_sha256={result.audio_sha256}"
    )


if __name__ == "__main__":
    main()
