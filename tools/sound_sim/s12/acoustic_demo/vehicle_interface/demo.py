"""Deterministic virtual-time demo for the v0.7 localhost vehicle interface."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
from pathlib import Path
import subprocess
import time

from audio_parameter_package.runtime_package import build_runtime_audio_parameter_package, validate_runtime_audio_parameter_package
from engine_operating_points.library import load_operating_point_library
from sound_renderer.s12_product_renderer import renderer_profile_from_library
from vehicle_interface.engine_runtime_api import EngineRuntimeApi
from vehicle_interface.localhost_api import LocalhostVehicleStateServer
from vehicle_interface.vehicle_state_stream import SyntheticVehicleStateStream


GENERATOR_VERSION = "S12 Runtime Vehicle Interface v0.7"


@dataclass(frozen=True)
class VehicleInterfaceReport:
    runtime_report_path: Path
    latency_report_path: Path
    pcm_sha256: str
    packet_count: int
    pcm_frame_count: int


def _source_commit() -> str:
    project_root = Path(__file__).resolve().parents[5]
    return subprocess.run(["git", "-C", str(project_root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def _percentile(values: tuple[float, ...], fraction: float) -> float:
    if not values:
        raise ValueError("latency percentile requires at least one sample")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return path


def _runtime_parameter_package(source_commit: str) -> dict[str, object]:
    library = load_operating_point_library()
    package = build_runtime_audio_parameter_package(library, renderer_profile_from_library(library), source_commit)
    validate_runtime_audio_parameter_package(package)
    return package


def _write_markdown(path: Path, report: dict[str, object], latency: dict[str, object]) -> None:
    audio = report["audio"]
    buffer = report["buffer"]
    path.write_text(
        "\n".join(
            (
                "# S12 Runtime Vehicle Interface v0.7 Report",
                "",
                "Synthetic PC localhost simulation only. It is uncalibrated, offline and not realtime-qualified; it is not real vehicle data or an OEM sound clone.",
                "",
                "## Completed",
                "",
                "- C/synthetic Vehicle State Packet v0.1 and 100 Hz external stream",
                "- localhost-only POST /vehicle_state interface",
                "- two 100 Hz packets to one 20 ms PCM frame through the unchanged v0.6 runtime path",
                "- packet-to-PCM p50/p95/p99 latency report and deterministic PCM SHA",
                "",
                "## Evidence",
                "",
                f"- paced drive duration: {report['duration_s']} s",
                f"- state packets: {report['packet_count']}",
                f"- PCM frames: {report['pcm_frame_count']}",
                f"- audio SHA-256: {audio['sha256']}",
                f"- clipping: {audio['clipping_count']}",
                f"- underruns: {buffer['underrun_count']}",
                f"- p99 packet-to-PCM latency: {latency['p99_ms']:.6f} ms",
                "",
                "## Not completed",
                "",
                "- Android integration",
                "- CAN, OBD, ESP32, I2S and vehicle deployment",
                "- real vehicle calibration",
                "- realtime mobile DSP qualification",
                "",
            )
        ),
        encoding="utf-8",
    )


def run_vehicle_interface_demo(
    output_root: Path,
    duration_s: float = 600.0,
    *,
    pace_100hz: bool = True,
    enforce_latency_target: bool = True,
) -> VehicleInterfaceReport:
    """Send a 100 Hz synthetic drive through the actual localhost HTTP interface."""
    stream = SyntheticVehicleStateStream(duration_s)
    api = EngineRuntimeApi()
    schedule_lag_ms: list[float] = []
    delivery_started_s = time.perf_counter()
    with LocalhostVehicleStateServer(api) as server:
        connection = http.client.HTTPConnection(server.url.removeprefix("http://"), timeout=5.0)
        try:
            for index, packet in enumerate(stream.iter_packets()):
                if pace_100hz:
                    deadline_s = delivery_started_s + index / 100.0
                    remaining_s = deadline_s - time.perf_counter()
                    if remaining_s > 0.0:
                        time.sleep(remaining_s)
                    schedule_lag_ms.append(max(0.0, (time.perf_counter() - deadline_s) * 1000.0))
                body = json.dumps(packet.as_mapping(), separators=(",", ":"), allow_nan=False)
                connection.request("POST", "/vehicle_state", body=body, headers={"Content-Type": "application/json"})
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                if response.status != 200 or payload["packet_index"] != api.packet_count:
                    raise RuntimeError("localhost vehicle-state API rejected a synthetic demo packet")
        finally:
            connection.close()
    delivery_elapsed_s = time.perf_counter() - delivery_started_s

    if (api.packet_count, api.pcm_frame_count) != (stream.update_count, stream.update_count // 2):
        raise RuntimeError("vehicle interface packet-to-PCM cadence is incorrect")
    if api.clipping_count or api.underrun_count:
        raise RuntimeError("vehicle interface demo must not clip or underrun")
    latencies = api.packet_latencies_ms
    ingress_intervals = api.ingress_intervals_ms
    latency = {
        "schema": "s12.vehicle_interface.latency.v0.2",
        "measurement": "server ingress before JSON parsing to corresponding PCMFrame readiness; every 100 Hz packet",
        "cadence": "two 100 Hz packets produce one 20 ms PCM frame; each frame contributes first- and second-packet samples",
        "sample_count": len(latencies),
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
        "max_ms": max(latencies),
    }
    if pace_100hz and enforce_latency_target and latency["p99_ms"] >= 20.0:
        raise RuntimeError(f"paced packet-to-PCM p99 exceeds 20 ms: {latency['p99_ms']:.6f} ms")
    source_commit = _source_commit()
    report = {
        "schema": "s12.runtime_vehicle_interface.v07",
        "generator_version": GENERATOR_VERSION,
        "source_commit": source_commit,
        "synthetic": True,
        "calibrated": False,
        "offline": True,
        "realtime_qualified": False,
        "transport": "localhost_http_v0.1",
        "endpoint_scope": "127.0.0.1 only",
        "duration_s": duration_s,
        "state_update_hz": 100,
        "delivery": {
            "paced_100hz": pace_100hz,
            "wall_elapsed_s": delivery_elapsed_s,
            "schedule_lag_p99_ms": _percentile(tuple(schedule_lag_ms), 0.99) if schedule_lag_ms else None,
            "schedule_lag_max_ms": max(schedule_lag_ms) if schedule_lag_ms else None,
            "ingress_interval_p99_ms": _percentile(ingress_intervals, 0.99),
            "ingress_interval_max_ms": max(ingress_intervals),
        },
        "packet_count": api.packet_count,
        "pcm_frame_count": api.pcm_frame_count,
        "state_transitions": list(api.state_transitions),
        "fallback_count": api.fallback_count,
        "audio": {
            "sample_rate_hz": 48000,
            "channels": 2,
            "bits_per_sample": 24,
            "block_samples": 960,
            "clipping_count": api.clipping_count,
            "sha256": api.pcm_sha256,
        },
        "buffer": {
            "capacity_frames": api.queue_capacity_frames,
            "max_depth_frames": api.queue_max_depth_frames,
            "underrun_count": api.underrun_count,
        },
        "audio_parameter_package": _runtime_parameter_package(source_commit),
    }
    root = Path(output_root)
    runtime_report_path = _write_json(root / "runtime_report.json", report)
    latency_report_path = _write_json(root / "latency_report.json", latency)
    _write_markdown(root / "S12_Runtime_Vehicle_Interface_v07_Report.md", report, latency)
    return VehicleInterfaceReport(runtime_report_path, latency_report_path, api.pcm_sha256, api.packet_count, api.pcm_frame_count)
