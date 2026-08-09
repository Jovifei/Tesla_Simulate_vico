"""Run the C/synthetic Android-protocol v0.8 demo on the PC runtime."""

from __future__ import annotations

import argparse
from pathlib import Path

from runtime_server.demo import run_android_protocol_demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic S12 v0.8 Android-protocol WebSocket demo.")
    parser.add_argument("--duration-s", type=float, default=600.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "v08_android_demo",
    )
    args = parser.parse_args()
    report = run_android_protocol_demo(args.output, args.duration_s)
    print(f"runtime report: {report.runtime_report_path}")
    print(f"PCM frames={report.pcm_frame_count} packets={report.packet_count} pcm_sha256={report.pcm_sha256}")


if __name__ == "__main__":
    main()
