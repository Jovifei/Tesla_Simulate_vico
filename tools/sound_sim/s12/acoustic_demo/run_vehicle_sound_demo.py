"""Command-line entry point for the S12 v0.7 localhost vehicle interface demo."""

from __future__ import annotations

import argparse
from pathlib import Path

from vehicle_interface.demo import run_vehicle_interface_demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic S12 v0.7 vehicle-state localhost demo.")
    parser.add_argument("--duration-s", type=float, default=600.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[5] / "tasks" / "reports" / "runtime" / "v07_demo",
    )
    args = parser.parse_args()
    report = run_vehicle_interface_demo(args.output, args.duration_s)
    print(f"runtime report: {report.runtime_report_path}")
    print(f"PCM frames={report.pcm_frame_count} packets={report.packet_count} pcm_sha256={report.pcm_sha256}")


if __name__ == "__main__":
    main()
