from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import struct
import wave
from dataclasses import dataclass
from typing import Iterable, Sequence


DEFAULT_SAMPLE_RATE = 44100
DEFAULT_BLOCK_HZ = 50
IDLE_RPM = 800.0
MAX_RPM = 6800.0
OVERSPEED_MUTE_KMH = 150.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class DrivePoint:
    time_s: float
    speed_kmh: float
    throttle: float
    accel_mps2: float
    brake: bool = False


@dataclass(frozen=True)
class SoundState:
    time_s: float
    rpm: float
    frequency_hz: float
    amplitude: float
    brightness: float
    harmonics: tuple[float, float, float, float, float]
    muted: bool


class SoundModel:
    """Small offline EV sound model that can be ported to ESP32 later."""

    def __init__(self, smoothing: float = 0.18) -> None:
        self._smoothing = _clamp(smoothing, 0.0, 1.0)
        self._smooth_rpm = IDLE_RPM
        self._phase = 0.0

    def map_point(self, point: DrivePoint) -> SoundState:
        throttle = _clamp(point.throttle, 0.0, 1.0)
        speed = max(0.0, point.speed_kmh)
        positive_accel = _clamp(point.accel_mps2 / 3.0, 0.0, 1.0)
        braking = point.brake or point.accel_mps2 < -1.2

        speed_rpm = IDLE_RPM + _clamp(speed / 180.0, 0.0, 1.0) * (6000.0 - IDLE_RPM)
        throttle_factor = 0.30 + 0.70 * throttle
        target_rpm = IDLE_RPM + (speed_rpm - IDLE_RPM) * throttle_factor
        target_rpm += positive_accel * 850.0
        if braking:
            target_rpm = max(IDLE_RPM, target_rpm * 0.45)

        target_rpm = _clamp(target_rpm, IDLE_RPM, MAX_RPM)
        self._smooth_rpm += self._smoothing * (target_rpm - self._smooth_rpm)

        rpm_norm = _clamp((self._smooth_rpm - IDLE_RPM) / (MAX_RPM - IDLE_RPM), 0.0, 1.0)
        brightness = _clamp(0.20 + throttle * 0.45 + positive_accel * 0.35, 0.0, 1.0)
        amplitude = _clamp(0.12 + throttle * 0.32 + positive_accel * 0.18, 0.0, 0.72)
        if braking:
            brightness *= 0.55
            amplitude *= 0.65

        harmonics = (
            1.00,
            _clamp(0.34 + brightness * 0.26, 0.0, 1.0),
            _clamp(0.12 + brightness * 0.35, 0.0, 1.0),
            _clamp(0.05 + positive_accel * 0.22, 0.0, 1.0),
            _clamp(0.025 + throttle * 0.10, 0.0, 1.0),
        )

        frequency_hz = 40.0 + rpm_norm * 180.0
        muted = speed >= OVERSPEED_MUTE_KMH
        return SoundState(
            time_s=point.time_s,
            rpm=self._smooth_rpm,
            frequency_hz=frequency_hz,
            amplitude=0.0 if muted else amplitude,
            brightness=brightness,
            harmonics=harmonics,
            muted=muted,
        )

    def render_state(self, state: SoundState, frame_count: int, sample_rate: int) -> list[int]:
        if state.muted or state.amplitude <= 0.0:
            return [0] * frame_count

        out: list[int] = []
        norm = sum(abs(gain) for gain in state.harmonics)
        amplitude = state.amplitude * 0.78 / max(norm, 1.0)
        dphi = 2.0 * math.pi * state.frequency_hz / sample_rate

        for _ in range(frame_count):
            sample = 0.0
            for index, gain in enumerate(state.harmonics, start=1):
                sample += gain * math.sin(self._phase * index)
            value = int(_clamp(sample * amplitude, -1.0, 1.0) * 32767.0)
            out.append(value)
            self._phase += dphi
            if self._phase >= 2.0 * math.pi:
                self._phase -= 2.0 * math.pi
        return out


def build_demo_drive_cycle(duration_s: float = 12.0, step_s: float = 0.02) -> list[DrivePoint]:
    points: list[DrivePoint] = []
    speed = 0.0
    last_speed_mps = 0.0
    steps = max(1, int(duration_s / step_s))

    for i in range(steps):
        t = i * step_s
        if t < duration_s * 0.35:
            throttle = 0.82
            accel = 2.7
        elif t < duration_s * 0.62:
            throttle = 0.34
            accel = 0.2
        elif t < duration_s * 0.82:
            throttle = 0.08
            accel = -1.6
        else:
            throttle = 0.48
            accel = 1.1

        speed_mps = max(0.0, last_speed_mps + accel * step_s)
        speed = speed_mps * 3.6
        derived_accel = (speed_mps - last_speed_mps) / step_s
        last_speed_mps = speed_mps
        points.append(
            DrivePoint(
                time_s=t,
                speed_kmh=speed,
                throttle=throttle,
                accel_mps2=derived_accel,
                brake=derived_accel < -1.2,
            )
        )
    return points


def render_drive_cycle(
    cycle: Sequence[DrivePoint],
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    block_hz: int = DEFAULT_BLOCK_HZ,
    model: SoundModel | None = None,
) -> tuple[list[int], list[SoundState]]:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if block_hz <= 0:
        raise ValueError("block_hz must be positive")

    model = model or SoundModel()
    frames_per_block = max(1, sample_rate // block_hz)
    samples: list[int] = []
    trace: list[SoundState] = []

    for point in cycle:
        state = model.map_point(point)
        trace.append(state)
        samples.extend(model.render_state(state, frames_per_block, sample_rate))
    return samples, trace


def write_wav(path: pathlib.Path, samples: Sequence[int], sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(struct.pack("<h", int(_clamp(sample, -32768, 32767))) for sample in samples)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(payload)


def write_trace_csv(path: pathlib.Path, trace: Iterable[SoundState]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["time_s", "rpm", "frequency_hz", "amplitude", "brightness", "muted", "h1", "h2", "h3", "h4", "h5"]
        )
        for state in trace:
            writer.writerow(
                [
                    f"{state.time_s:.3f}",
                    f"{state.rpm:.2f}",
                    f"{state.frequency_hz:.2f}",
                    f"{state.amplitude:.4f}",
                    f"{state.brightness:.4f}",
                    int(state.muted),
                    *(f"{gain:.5f}" for gain in state.harmonics),
                ]
            )


def export_firmware_params(path: pathlib.Path, trace: Sequence[SoundState]) -> None:
    if not trace:
        raise ValueError("trace must not be empty")

    sorted_trace = sorted(trace, key=lambda item: item.rpm)
    picks = [0.0, 0.33, 0.66, 1.0]
    selected = [sorted_trace[min(len(sorted_trace) - 1, int(pick * (len(sorted_trace) - 1)))] for pick in picks]
    avg_harmonics = [
        sum(state.harmonics[index] for state in selected) / len(selected)
        for index in range(len(selected[0].harmonics))
    ]
    payload = {
        "schema": "jovi.sound_model.v1",
        "sample_rate_hz": DEFAULT_SAMPLE_RATE,
        "rpm_breakpoints": [round(state.rpm, 1) for state in selected],
        "frequency_hz": [round(state.frequency_hz, 2) for state in selected],
        "amplitude": [round(state.amplitude, 4) for state in selected],
        "brightness": [round(state.brightness, 4) for state in selected],
        "harmonic_gains_q15": [int(_clamp(gain, 0.0, 1.0) * 32767) for gain in avg_harmonics],
        "notes": [
            "Offline prototype for ESP32 porting.",
            "Keep fixed-point tables small; do not run Python/MATLAB logic on firmware.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_demo(output_dir: pathlib.Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> dict[str, pathlib.Path]:
    cycle = build_demo_drive_cycle()
    samples, trace = render_drive_cycle(cycle, sample_rate=sample_rate)

    wav_path = output_dir / "jovi_ev_sound_demo.wav"
    csv_path = output_dir / "jovi_ev_sound_trace.csv"
    params_path = output_dir / "jovi_sound_params_v1.json"
    write_wav(wav_path, samples, sample_rate=sample_rate)
    write_trace_csv(csv_path, trace)
    export_firmware_params(params_path, trace)
    return {"wav": wav_path, "csv": csv_path, "params": params_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Jovi EV sound simulation artifacts.")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("build/sound-sim"))
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    args = parser.parse_args(argv)

    artifacts = run_demo(args.out, sample_rate=args.sample_rate)
    for kind, path in artifacts.items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
