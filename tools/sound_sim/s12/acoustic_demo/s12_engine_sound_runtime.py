"""Run the S12 v0.6 continuous PC runtime simulator in deterministic virtual time."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from audio_parameter_package.runtime_package import (
    build_runtime_audio_parameter_package,
    validate_runtime_audio_parameter_package,
)
from engine_operating_points.library import load_operating_point_library
from engine_runtime import EngineSoundRuntime
from runtime_pcm import PcmRingBuffer, SimulatedPcmSink, WindowsWaveOutSink
from sound_renderer.s12_product_renderer import renderer_profile_from_library
from vehicle_state_runtime.stream import RuntimeDriveCycle


GENERATOR_VERSION = "S12 Engine Sound Runtime Simulator v0.6"
BLOCK_DURATION_S = 0.020
STATE_UPDATE_HZ = 100


@dataclass(frozen=True)
class RuntimeReport:
    report_path: Path
    audio_sha256: str
    pcm_frames: int
    underrun_count: int
    state_update_hz: int


def _current_source_commit() -> str:
    project_root = Path(__file__).resolve().parents[4]
    return subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _process_working_set_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCountersEx),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    result = psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    return int(counters.WorkingSetSize) if result else None


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_markdown_report(path: Path, report: dict) -> Path:
    device_summary = (
        "- Windows waveOut PCM device output used for this run"
        if report["device_output"] == "windows_waveout"
        else "- optional Windows waveOut PCM device adapter is implemented; this deterministic run uses the simulated PC PCM sink"
    )
    path.write_text(
        "\n".join(
            [
                "# S12 Runtime Engine Sound v0.6 Report",
                "",
                "Synthetic PC runtime simulation only. It is uncalibrated and not realtime-qualified; it is not an OEM or real-vehicle clone.",
                "",
                "## Completed",
                "",
                "- continuous virtual-time runtime",
                "- 20 ms 48 kHz/24-bit/stereo PCM streaming",
                "- 100 Hz synthetic vehicle-state interface",
                "- phase-continuous order tracking",
                "- stateful frozen PTR/radiation adapter",
                "- bounded simulated PCM queue with latency, underrun, CPU and memory metrics",
                device_summary,
                "- future App JSON contract and AudioParameterPackage v0.2",
                "",
                "## Evidence",
                "",
                f"- virtual duration: {report['duration_s']} s",
                f"- PCM frames: {report['pcm_frames']}",
                f"- underruns: {report['buffer']['underrun_count']}",
                f"- audio SHA-256: {report['audio']['sha256']}",
                f"- output sink: {report['device_output']}",
                "",
                "## Not completed",
                "",
                "- Android integration",
                "- end-to-end realtime audio-device qualification",
                "- vehicle calibration",
                "- ESP32, I2S, CAN, and phone hardware integration",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def run_runtime_demo(
    output_root: Path, duration_s: float = 600.0, device_output: bool = False
) -> RuntimeReport:
    """Render a deterministic 20 ms PCM stream without retaining complete audio."""
    frame_count = round(duration_s / BLOCK_DURATION_S)
    update_count = round(duration_s * STATE_UPDATE_HZ)
    if (
        not math.isfinite(duration_s)
        or duration_s <= 0.0
        or not math.isclose(frame_count * BLOCK_DURATION_S, duration_s, abs_tol=1.0e-9)
        or update_count != frame_count * 2
    ):
        raise ValueError("runtime duration must be a positive multiple of 20 ms")
    cycle = RuntimeDriveCycle(duration_s=duration_s)
    library = load_operating_point_library()
    parameter_package = build_runtime_audio_parameter_package(
        library, renderer_profile_from_library(library), _current_source_commit()
    )
    validate_runtime_audio_parameter_package(parameter_package)
    runtime = EngineSoundRuntime()
    queue = PcmRingBuffer(capacity_frames=50)
    sink = SimulatedPcmSink(BLOCK_DURATION_S)
    device_sink = WindowsWaveOutSink() if device_output else None
    audio_hash = hashlib.sha256()
    transitions = []
    last_mode = None
    clipping_count = 0
    working_set_before = _process_working_set_bytes()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    for update_index in range(update_count):
        state = cycle.sample_at(update_index / STATE_UPDATE_HZ)
        runtime.update_vehicle_state(state)
        if update_index % 2 == 0:
            continue
        frame_index = update_index // 2
        frame = runtime.audio_callback()
        audio_hash.update(frame.pcm_s24le_stereo)
        clipping_count += sum(abs(sample) > 1.0 for sample in frame.normalized_samples)
        if frame.runtime_mode != last_mode:
            transitions.append(
                {
                    "frame_index": frame_index,
                    "timestamp_s": state.timestamp_s,
                    "mode": frame.runtime_mode,
                }
            )
            last_mode = frame.runtime_mode
        queue.push(frame)
        if device_sink is None:
            if queue.depth > 3:
                sink.consume(queue)
        else:
            device_sink.submit(queue.pop())
    while queue.depth:
        if device_sink is None:
            sink.consume(queue)
        else:
            device_sink.submit(queue.pop())
    if device_sink is not None:
        device_sink.drain_and_close()
    cpu_elapsed_s = time.process_time() - cpu_start
    wall_elapsed_s = time.perf_counter() - wall_start
    working_set_after = _process_working_set_bytes()
    report = {
        "schema": "s12.runtime_report.v06",
        "generator_version": GENERATOR_VERSION,
        "source_commit": _current_source_commit(),
        "synthetic": True,
        "calibrated": False,
        "realtime_qualified": False,
        "device_output": "windows_waveout" if device_output else "simulated_pc_pcm_sink",
        "duration_s": duration_s,
        "state_update_hz": STATE_UPDATE_HZ,
        "state_updates_consumed": runtime.state_updates_consumed,
        "state_transitions": transitions,
        "pcm_frames": frame_count,
        "audio": {
            "sample_rate_hz": 48000,
            "channels": 2,
            "bits_per_sample": 24,
            "block_samples": 960,
            "clipping_count": clipping_count,
            "sha256": audio_hash.hexdigest(),
        },
        "buffer": {
            "capacity_frames": queue.capacity_frames,
            "max_depth_frames": queue.max_depth,
            "underrun_count": sink.underrun_count,
        },
        "latency": {
            "block_duration_ms": BLOCK_DURATION_S * 1000.0,
            "mean_simulated_ms": sink.mean_latency_s * 1000.0,
            "max_simulated_ms": sink.max_latency_s * 1000.0,
        },
        "performance": {
            "wall_elapsed_s": wall_elapsed_s,
            "cpu_elapsed_s": cpu_elapsed_s,
            "process_cpu_percent": 100.0 * cpu_elapsed_s / max(wall_elapsed_s, 1.0e-12),
        },
        "memory": {
            "measurement": "Windows process working set sampled before and after the virtual-time run; no per-sample allocation tracer is enabled.",
            "process_working_set_before_bytes": working_set_before,
            "process_working_set_after_bytes": working_set_after,
        },
        "audio_parameter_package": parameter_package,
        "app_interface": "Runtime_APP_Interface_v01.md",
    }
    output_root = Path(output_root)
    report_path = _write_json(output_root / "runtime_report.json", report)
    _write_markdown_report(output_root / "S12_Runtime_Engine_Sound_v06_Report.md", report)
    return RuntimeReport(
        report_path, report["audio"]["sha256"], frame_count, sink.underrun_count, STATE_UPDATE_HZ
    )
