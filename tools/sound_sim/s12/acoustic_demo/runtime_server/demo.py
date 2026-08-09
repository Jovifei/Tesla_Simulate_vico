"""Repeatable PC simulation of the Android v0.8 WebSocket protocol."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess
import time

from websockets.sync.client import ClientConnection, connect

from audio_parameter_package.runtime_package import (
    build_runtime_audio_parameter_package,
    validate_runtime_audio_parameter_package,
)
from engine_operating_points.library import load_operating_point_library
from runtime_server.websocket_server import VehicleRuntimeWebSocketServer
from sound_renderer.s12_product_renderer import renderer_profile_from_library
from vehicle_interface.engine_runtime_api import EngineRuntimeApi
from vehicle_state_runtime.stream import UPDATE_HZ
from vehicle_interface.vehicle_state_stream import SyntheticVehicleStateStream


GENERATOR_VERSION = "S12 Android Vehicle Sound Controller v0.8"


@dataclass(frozen=True)
class AndroidProtocolDemoReport:
    runtime_report_path: Path
    latency_report_path: Path
    pcm_sha256: str
    packet_count: int
    pcm_frame_count: int


def _source_commit() -> str:
    project_root = Path(__file__).resolve().parents[5]
    return subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("latency percentile requires at least one sample")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return path


def _runtime_parameter_package(source_commit: str) -> dict[str, object]:
    library = load_operating_point_library()
    package = build_runtime_audio_parameter_package(
        library, renderer_profile_from_library(library), source_commit
    )
    validate_runtime_audio_parameter_package(package)
    return package


def _write_readme(path: Path, runtime: dict[str, object], latency: dict[str, object]) -> None:
    audio = runtime["audio"]
    path.write_text(
        "\n".join(
            (
                "# S12 Android Vehicle Sound Controller v0.8 Demo",
                "",
                "This is a C/synthetic PC-hosted Android-protocol simulation. The APK is a debug controller build; this report is not an Android device-runtime qualification, CAN/OBD input, vehicle installation, or OEM sound claim.",
                "",
                "## Evidence",
                "",
                f"- paced duration: {runtime['duration_s']} s",
                f"- packets: {runtime['packet_count']}",
                f"- PCM frames: {runtime['pcm_frame_count']}",
                f"- controlled reconnects: {runtime['reconnect_count']}",
                f"- PCM SHA-256: {audio['sha256']}",
                f"- clipping: {audio['clipping_count']}",
                f"- underruns: {runtime['buffer']['underrun_count']}",
                f"- p99 Android-protocol-to-PCM acknowledgement: {latency['p99_ms']:.6f} ms",
                "",
                "## Boundary",
                "",
                "Not completed: Android device installation/runtime qualification, CAN, OBD, ESP32, I2S, vehicle integration, calibration and mobile DSP qualification.",
                "",
            )
        ),
        encoding="utf-8",
    )


def run_android_protocol_demo(
    output_root: Path,
    duration_s: float = 600.0,
    *,
    pace_100hz: bool = True,
    enforce_latency_target: bool = True,
) -> AndroidProtocolDemoReport:
    """Drive the WebSocket protocol at 100 Hz with one controlled reconnect."""
    stream = SyntheticVehicleStateStream(duration_s)
    if stream.update_count % 2:
        raise ValueError("duration must yield an even 100 Hz packet count")
    api = EngineRuntimeApi()
    packet_latencies_ms: list[float] = []
    ingress_intervals_ms: list[float] = []
    schedule_lag_ms: list[float] = []
    trace: list[dict[str, float]] = []
    pending_sent_s: list[float] = []
    reconnect_count = 0
    delivery_started_s = time.perf_counter()

    with VehicleRuntimeWebSocketServer(api) as server:
        connection: ClientConnection = connect(server.url, open_timeout=5.0, close_timeout=5.0)
        try:
            for index, packet in enumerate(stream.iter_packets()):
                if index == stream.update_count // 2:
                    connection.close()
                    connection = connect(server.url, open_timeout=5.0, close_timeout=5.0)
                    reconnect_count += 1
                if pace_100hz:
                    deadline_s = delivery_started_s + index / UPDATE_HZ
                    remaining_s = deadline_s - time.perf_counter()
                    if remaining_s > 0.0:
                        time.sleep(remaining_s)
                    schedule_lag_ms.append(max(0.0, (time.perf_counter() - deadline_s) * 1000.0))
                sent_s = time.perf_counter()
                mapping = packet.as_mapping()
                connection.send(json.dumps(mapping, separators=(",", ":"), allow_nan=False))
                response = json.loads(connection.recv())
                completed_s = time.perf_counter()
                if (
                    response.get("status") != "ok"
                    or response.get("timestamp") != packet.timestamp_s
                ):
                    raise RuntimeError(
                        "Android protocol client received an invalid runtime acknowledgement"
                    )
                pending_sent_s.append(sent_s)
                trace.append(mapping)
                if response["pcm_available"]:
                    if len(pending_sent_s) != 2:
                        raise RuntimeError(
                            "WebSocket PCM acknowledgement lost the two-packet cadence"
                        )
                    packet_latencies_ms.append((completed_s - pending_sent_s[0]) * 1000.0)
                    packet_latencies_ms.append((completed_s - pending_sent_s[1]) * 1000.0)
                    pending_sent_s.clear()
            ingress_intervals_ms.extend(api.ingress_intervals_ms)
        finally:
            connection.close()
    delivery_elapsed_s = time.perf_counter() - delivery_started_s

    if pending_sent_s or (api.packet_count, api.pcm_frame_count) != (
        stream.update_count,
        stream.update_count // 2,
    ):
        raise RuntimeError("Android protocol packet-to-PCM cadence is incorrect")
    if api.clipping_count or api.underrun_count:
        raise RuntimeError("Android protocol demo must not clip or underrun")
    if len(packet_latencies_ms) != stream.update_count:
        raise RuntimeError("Android protocol latency must cover every packet")
    latency = {
        "schema": "s12.android_runtime_latency.v0.8",
        "measurement": "synthetic Android-protocol client monotonic send to WebSocket PCM-ready acknowledgement; every 100 Hz packet",
        "sample_count": len(packet_latencies_ms),
        "p50_ms": _percentile(packet_latencies_ms, 0.50),
        "p95_ms": _percentile(packet_latencies_ms, 0.95),
        "p99_ms": _percentile(packet_latencies_ms, 0.99),
        "max_ms": max(packet_latencies_ms),
    }
    if pace_100hz and enforce_latency_target and latency["p99_ms"] >= 50.0:
        raise RuntimeError(f"paced Android-protocol p99 exceeds 50 ms: {latency['p99_ms']:.6f} ms")
    source_commit = _source_commit()
    runtime = {
        "schema": "s12.android_vehicle_sound_demo.v0.8",
        "generator_version": GENERATOR_VERSION,
        "source_commit": source_commit,
        "synthetic": True,
        "calibrated": False,
        "offline": True,
        "realtime_qualified": False,
        "client_kind": "synthetic_android_protocol_simulator",
        "transport": "websocket_v0.8",
        "endpoint_scope": "127.0.0.1 only",
        "duration_s": duration_s,
        "state_update_hz": UPDATE_HZ,
        "reconnect_count": reconnect_count,
        "packet_count": api.packet_count,
        "pcm_frame_count": api.pcm_frame_count,
        "state_transitions": list(api.state_transitions),
        "fallback_count": api.fallback_count,
        "delivery": {
            "paced_100hz": pace_100hz,
            "wall_elapsed_s": delivery_elapsed_s,
            "schedule_lag_p99_ms": _percentile(schedule_lag_ms, 0.99) if schedule_lag_ms else None,
            "schedule_lag_max_ms": max(schedule_lag_ms) if schedule_lag_ms else None,
            "ingress_interval_p99_ms": _percentile(ingress_intervals_ms, 0.99),
            "ingress_interval_max_ms": max(ingress_intervals_ms),
        },
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
    runtime_report_path = _write_json(root / "runtime_report.json", runtime)
    latency_report_path = _write_json(root / "latency_report.json", latency)
    _write_json(root / "android_runtime_latency.json", latency)
    _write_json(
        root / "vehicle_trace.json",
        {
            "schema": "s12.android_vehicle_trace.v0.8",
            "synthetic": True,
            "state_update_hz": UPDATE_HZ,
            "states": trace,
        },
    )
    _write_readme(root / "README.md", runtime, latency)
    return AndroidProtocolDemoReport(
        runtime_report_path,
        latency_report_path,
        api.pcm_sha256,
        api.packet_count,
        api.pcm_frame_count,
    )
