"""Offline Python oracle for the bounded APP-1 synthetic audio subset."""

from __future__ import annotations

import math
import zlib
from typing import Any, Mapping


SAMPLE_RATE_HZ = 48000
CONTROL_RATE_HZ = 100
FRAMES_PER_UPDATE = SAMPLE_RATE_HZ // CONTROL_RATE_HZ
TAU = 2.0 * math.pi


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


class SyntheticEngine:
    """Test-only phase/order renderer; not an accepted or vehicle-matched model."""

    def __init__(self, profile: Mapping[str, Any], seed: int) -> None:
        self.profile = profile
        self.mapping = profile["state_mapping"]
        self.transient = profile["transient"]
        self.output = profile["output_policy"]
        seed_bits = zlib.crc32(profile["profile_id"].encode("utf-8")) ^ seed
        self.phase = TAU * ((seed_bits & 0xFFFF) / 65536.0)
        self.gear = 0
        self.target_rpm = self.mapping["idle_rpm"]
        self.rpm = self.target_rpm
        self.target_load = self.mapping["idle_load"]
        self.load = self.target_load
        self.acceleration_mps2 = 0.0
        self.envelope = 0.0
        self.shift_tail = 0.0
        self.shift_events = 0
        self.last_event = "none"

    def update_motion(self, sample: Mapping[str, Any]) -> dict[str, Any]:
        speed = 0.0 if sample["direction"] == "stationary" else sample["speed_mps"]
        acceleration = sample["longitudinal_acceleration_mps2"]
        rates = self.mapping["rpm_per_mps_by_gear"]
        predicted_rpm = self.mapping["idle_rpm"] + speed * rates[self.gear]
        predicted_rpm += max(0.0, acceleration) * self.mapping["acceleration_rpm_per_mps2"]
        event = "none"
        if predicted_rpm > self.mapping["upshift_rpm"] and self.gear < len(rates) - 1:
            self.gear += 1
            event = "shift_up"
        elif predicted_rpm < self.mapping["downshift_rpm"] and self.gear > 0:
            self.gear -= 1
            event = "shift_down"
        target = self.mapping["idle_rpm"] + speed * rates[self.gear]
        target += max(0.0, acceleration) * self.mapping["acceleration_rpm_per_mps2"]
        if event != "none":
            target *= self.mapping["shift_rpm_drop"]
            self.shift_events += 1
            self.shift_tail = self.transient["shift_impulse"]
        self.target_rpm = _clamp(target, self.mapping["idle_rpm"], self.mapping["max_rpm"])
        self.target_load = _clamp(
            self.mapping["idle_load"]
            + max(0.0, acceleration) * self.mapping["positive_acceleration_load_per_mps2"]
            - max(0.0, -acceleration) * self.mapping["negative_acceleration_load_per_mps2"],
            0.0,
            1.0,
        )
        self.acceleration_mps2 = acceleration
        self.last_event = event
        return {
            "sequence": sample["sequence"],
            "measurement_time_ns": sample["measurement_time_ns"],
            "virtual_rpm": round(self.target_rpm, 6),
            "load": round(self.target_load, 6),
            "gear": self.gear + 1,
            "event": event,
            "shift_event_count": self.shift_events,
            "qualification": "EXPERIMENTAL_SYNTHETIC_NOT_QUALIFIED",
        }

    def render_frames(self, frame_count: int) -> list[float]:
        if frame_count <= 0:
            raise ValueError("frame_count must be positive")
        rpm_smoothing = 1.0 / (0.05 * SAMPLE_RATE_HZ)
        load_smoothing = 1.0 / (0.04 * SAMPLE_RATE_HZ)
        rendered = []
        for _ in range(frame_count):
            self.rpm += (self.target_rpm - self.rpm) * rpm_smoothing
            self.load += (self.target_load - self.load) * load_smoothing
            self.phase = math.fmod(
                self.phase + TAU * self.rpm / 60.0 / SAMPLE_RATE_HZ,
                TAU,
            )
            harmonic = 0.0
            for partial in self.profile["orders"]:
                load_shape = 0.70 + self.load * 0.55 * max(1.0, partial["order"] / 4.0)
                harmonic += partial["amplitude"] * load_shape * math.sin(
                    partial["order"] * self.phase + partial["phase_rad"]
                )
            target_envelope = min(
                1.0,
                abs(self.acceleration_mps2) / self.transient["acceleration_reference_mps2"]
                + self.shift_tail,
            )
            duration = self.transient["attack_s"] if target_envelope > self.envelope else self.transient["release_s"]
            self.envelope += (target_envelope - self.envelope) / max(1.0, duration * SAMPLE_RATE_HZ)
            self.shift_tail *= math.exp(-1.0 / (0.08 * SAMPLE_RATE_HZ))
            transient = self.transient["gain"] * self.envelope * math.sin(
                self.transient["carrier_order"] * self.phase
            )
            raw = self.output["gain"] * (harmonic + transient)
            rendered.append(self.output["peak_limit"] * math.tanh(raw / self.output["peak_limit"]))
        return rendered
