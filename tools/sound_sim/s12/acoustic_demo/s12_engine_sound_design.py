"""Deterministic offline sound-design layer for Synthetic Engine Sound v0.2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterator

from s12_acoustic_audition import PressureTrace


DEFAULT_ORDER_PROFILE_PATH = Path(__file__).with_name("engine_order_profile.json")
DEFAULT_PARAMETER_LEDGER_PATH = Path(__file__).with_name(
    "engine_sound_parameter_ledger.json"
)
LABELS = ("synthetic", "uncalibrated", "offline", "not_realtime_qualified")
GENERATOR_VERSION = "Synthetic Engine Sound v0.2"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path.name} must contain valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value, _sha256(raw)


def load_order_profile(path: Path = DEFAULT_ORDER_PROFILE_PATH) -> dict:
    profile, digest = _load_json(path)
    if (
        profile.get("schema") != "s12.engine_order_profile.v1"
        or profile.get("source") != "synthetic"
        or profile.get("cylinders") != 4
        or profile.get("firing_order") != "1-3-4-2"
    ):
        raise ValueError("unsupported engine order profile")
    orders = profile.get("orders")
    if not isinstance(orders, list) or {
        item.get("name") for item in orders if isinstance(item, dict)
    } != {"fundamental", "second", "third", "firing"}:
        raise ValueError("engine order profile requires four named entries")
    for entry in orders:
        if (
            entry.get("source") != "synthetic"
            or not math.isfinite(float(entry.get("order")))
            or not math.isfinite(float(entry.get("amplitude")))
            or not math.isfinite(float(entry.get("phase_rad")))
        ):
            raise ValueError("engine order entries require finite synthetic parameters")
    return {**profile, "_sha256": digest}


def load_design_parameters(path: Path = DEFAULT_PARAMETER_LEDGER_PATH) -> dict:
    ledger, digest = _load_json(path)
    required = {
        "fixed_output_gain",
        "texture_mix",
        "stereo_width",
        "attack_s",
        "decay_s",
        "crossfade_s",
        "transient_gain",
        "max_adjacent_step",
        "max_dc",
    }
    parameters = ledger.get("parameters")
    if (
        ledger.get("schema") != "s12.engine_sound_parameter_ledger.v1"
        or ledger.get("generator_version") != GENERATOR_VERSION
        or not isinstance(parameters, dict)
        or set(parameters) != required
    ):
        raise ValueError("unsupported engine sound parameter ledger")
    for entry in parameters.values():
        if (
            entry.get("classification") != "C/synthetic"
            or entry.get("source") != "synthetic"
            or not entry.get("rationale")
            or not math.isfinite(float(entry.get("value")))
        ):
            raise ValueError("design parameters require synthetic provenance")
    return {**ledger, "_sha256": digest}


def fundamental_frequency_hz(rpm: float) -> float:
    if not math.isfinite(rpm) or rpm <= 0.0:
        raise ValueError("RPM must be finite and positive")
    return rpm / 60.0


@dataclass(frozen=True)
class OrderSchedule:
    rpm_start: float
    rpm_end: float
    load_start: float
    load_end: float
    frame_count: int
    sample_rate_hz: int
    schedule_type: str

    @classmethod
    def fixed(
        cls,
        rpm: float,
        load: float,
        duration_s: float,
        sample_rate_hz: int = 48000,
    ) -> OrderSchedule:
        return cls._create(
            rpm, rpm, load, load, duration_s, sample_rate_hz, "fixed"
        )

    @classmethod
    def ramp(
        cls,
        rpm_start: float,
        rpm_end: float,
        load_start: float,
        load_end: float,
        duration_s: float,
        sample_rate_hz: int = 48000,
    ) -> OrderSchedule:
        return cls._create(
            rpm_start,
            rpm_end,
            load_start,
            load_end,
            duration_s,
            sample_rate_hz,
            "ramp",
        )

    @classmethod
    def _create(
        cls,
        rpm_start: float,
        rpm_end: float,
        load_start: float,
        load_end: float,
        duration_s: float,
        sample_rate_hz: int,
        schedule_type: str,
    ) -> OrderSchedule:
        if (
            not all(math.isfinite(value) for value in (rpm_start, rpm_end))
            or min(rpm_start, rpm_end) <= 0.0
            or not all(
                math.isfinite(value) and 0.0 <= value <= 1.0
                for value in (load_start, load_end)
            )
            or not math.isfinite(duration_s)
            or duration_s <= 0.0
            or isinstance(sample_rate_hz, bool)
            or not isinstance(sample_rate_hz, int)
            or sample_rate_hz <= 0
        ):
            raise ValueError("schedule values are outside their finite domains")
        frame_count = round(duration_s * sample_rate_hz)
        if frame_count <= 0:
            raise ValueError("schedule duration must produce at least one frame")
        return cls(
            rpm_start,
            rpm_end,
            load_start,
            load_end,
            frame_count,
            sample_rate_hz,
            schedule_type,
        )

    def samples(self) -> Iterator[tuple[float, float]]:
        denominator = max(1, self.frame_count - 1)
        for index in range(self.frame_count):
            fraction = index / denominator
            yield (
                self.rpm_start + (self.rpm_end - self.rpm_start) * fraction,
                self.load_start + (self.load_end - self.load_start) * fraction,
            )


@dataclass(frozen=True)
class DesignedStereoTrace:
    left: list[float]
    right: list[float]
    sample_rate_hz: int
    instantaneous_rpm: list[float]
    fundamental_phase_rad: list[float]
    rpm_range: tuple[float, float]
    load_range: tuple[float, float]
    firing_frequency_hz: float | None
    generator_version: str
    labels: tuple[str, ...]
    source_hash: str
    profile_sha256: str
    parameter_ledger_sha256: str
    fixed_output_gain: float
    source_component_rms: dict[str, float]
    order_spectrum_rms: dict[str, float]
    max_adjacent_step_limit: float
    max_dc_limit: float


def _parameter(parameters: dict, name: str) -> float:
    try:
        return float(parameters["parameters"][name]["value"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"missing design parameter {name}") from error


def _smooth(previous: float, target: float, attack_s: float, decay_s: float,
            sample_rate_hz: int) -> float:
    time_s = attack_s if target >= previous else decay_s
    coefficient = 1.0 - math.exp(-1.0 / (time_s * sample_rate_hz))
    return previous + coefficient * (target - previous)


def _texture_at(samples: list[float], index: int, fade_frames: int) -> float:
    position = index % len(samples)
    if len(samples) == 1:
        return samples[0]
    edge = min(position, len(samples) - 1 - position)
    envelope = min(1.0, edge / max(1, fade_frames))
    return samples[position] * envelope


def _rms(samples: list[float]) -> float:
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def _project_order_spectrum(
    left: list[float],
    right: list[float],
    fundamental_phase_rad: list[float],
    orders: set[float],
) -> dict[str, float]:
    mono = [(left_value + right_value) / 2.0
            for left_value, right_value in zip(left, right)]
    scale = 2.0 / len(mono)
    spectrum = {}
    for order in sorted(orders):
        sine = scale * sum(
            sample * math.sin(order * phase)
            for sample, phase in zip(mono, fundamental_phase_rad)
        )
        cosine = scale * sum(
            sample * math.cos(order * phase)
            for sample, phase in zip(mono, fundamental_phase_rad)
        )
        spectrum[f"order_{order:g}"] = math.hypot(sine, cosine) / math.sqrt(2.0)
    return spectrum


def render_sound_design(
    texture: PressureTrace,
    schedule: OrderSchedule,
    profile: dict,
    parameters: dict,
) -> DesignedStereoTrace:
    expected_interval_s = 1.0 / 48000.0
    if (
        texture.sample_rate_hz != 48000
        or schedule.sample_rate_hz != 48000
        or len(texture.pressure_pa) < 2
        or len(texture.time_s) != len(texture.pressure_pa)
        or not all(math.isfinite(value) for value in texture.pressure_pa)
        or not all(math.isfinite(value) for value in texture.time_s)
        or any(
            later <= earlier
            or abs((later - earlier) - expected_interval_s) > 1.0e-12
            for earlier, later in zip(texture.time_s, texture.time_s[1:])
        )
    ):
        raise ValueError("sound design requires uniform finite 48 kHz texture")
    if not texture.source_identity_sha256:
        raise ValueError("physical texture requires a source identity")

    gain = _parameter(parameters, "fixed_output_gain")
    texture_mix = _parameter(parameters, "texture_mix")
    stereo_width = _parameter(parameters, "stereo_width")
    attack_s = _parameter(parameters, "attack_s")
    decay_s = _parameter(parameters, "decay_s")
    crossfade_s = _parameter(parameters, "crossfade_s")
    transient_gain = _parameter(parameters, "transient_gain")
    if (
        gain <= 0.0
        or texture_mix < 0.0
        or not 0.0 <= stereo_width <= 1.0
        or min(attack_s, decay_s, crossfade_s) <= 0.0
        or transient_gain < 0.0
    ):
        raise ValueError("design gains and smoothing times are invalid")

    order_entries = [
        (
            str(entry["name"]),
            float(entry["order"]),
            float(entry["amplitude"]),
            float(entry["phase_rad"]),
        )
        for entry in profile["orders"]
    ]
    order_phases = {name: 0.0 for name, _, _, _ in order_entries}
    order_components = {name: [] for name, _, _, _ in order_entries}
    texture_mean = sum(texture.pressure_pa) / len(texture.pressure_pa)
    texture_samples = [value - texture_mean for value in texture.pressure_pa]
    fade_frames = max(1, round(crossfade_s * schedule.sample_rate_hz))
    schedule_samples = list(schedule.samples())
    instantaneous_rpm = [rpm for rpm, _ in schedule_samples]
    fundamental_phase: list[float] = []
    mono: list[float] = []
    side_values: list[float] = []
    smoothed_load = schedule_samples[0][1]
    transient_state = 0.0
    previous_rpm, previous_load = schedule_samples[0]

    for index, (rpm, load) in enumerate(schedule_samples):
        smoothed_load = _smooth(
            smoothed_load, load, attack_s, decay_s, schedule.sample_rate_hz
        )
        rpm_rate = (rpm - previous_rpm) * schedule.sample_rate_hz
        load_rate = (load - previous_load) * schedule.sample_rate_hz
        transient_target = min(
            1.0, abs(rpm_rate) / 5000.0 + abs(load_rate) / 2.0
        )
        transient_state = _smooth(
            transient_state,
            transient_target,
            attack_s,
            decay_s,
            schedule.sample_rate_hz,
        )
        sample = 0.0
        for name, order, amplitude, phase_offset in order_entries:
            order_phases[name] += (
                2.0 * math.pi * order * rpm / (60.0 * schedule.sample_rate_hz)
            )
            load_weight = (
                0.25 + 0.50 * smoothed_load
                if order == 1.0
                else 0.12 + 0.88 * smoothed_load
            )
            component = amplitude * load_weight * math.sin(
                order_phases[name] + phase_offset
            )
            order_components[name].append(component * gain)
            sample += component
        fundamental_phase.append(order_phases["fundamental"])
        physical = _texture_at(texture_samples, index, fade_frames)
        global_edge = min(index, schedule.frame_count - 1 - index)
        physical *= min(1.0, global_edge / fade_frames)
        sample += texture_mix * physical
        sample += transient_gain * transient_state * math.sin(
            4.0 * order_phases["fundamental"] + 0.25
        )
        side = stereo_width * (
            0.22 * math.sin(3.0 * order_phases["fundamental"] + 0.7)
            + 0.08 * physical
        )
        mono.append(sample)
        side_values.append(side)
        previous_rpm, previous_load = rpm, load

    left_raw = [value + side for value, side in zip(mono, side_values)]
    right_raw = [value - side for value, side in zip(mono, side_values)]
    left_mean = sum(left_raw) / len(left_raw)
    right_mean = sum(right_raw) / len(right_raw)
    left = [(value - left_mean) * gain for value in left_raw]
    right = [(value - right_mean) * gain for value in right_raw]
    if not all(-1.0 <= value <= 1.0 for value in left + right):
        raise ValueError("fixed output gain exceeds the unclipped output range")

    fixed = schedule.schedule_type == "fixed"
    return DesignedStereoTrace(
        left=left,
        right=right,
        sample_rate_hz=schedule.sample_rate_hz,
        instantaneous_rpm=instantaneous_rpm,
        fundamental_phase_rad=fundamental_phase,
        rpm_range=(min(instantaneous_rpm), max(instantaneous_rpm)),
        load_range=(min(load for _, load in schedule_samples),
                    max(load for _, load in schedule_samples)),
        firing_frequency_hz=(
            2.0 * schedule.rpm_start / 60.0 if fixed else None
        ),
        generator_version=GENERATOR_VERSION,
        labels=LABELS,
        source_hash=texture.source_identity_sha256,
        profile_sha256=str(profile["_sha256"]),
        parameter_ledger_sha256=str(parameters["_sha256"]),
        fixed_output_gain=gain,
        source_component_rms={
            name: _rms(component) for name, component in order_components.items()
        },
        order_spectrum_rms=_project_order_spectrum(
            left,
            right,
            fundamental_phase,
            {order for _, order, _, _ in order_entries},
        ),
        max_adjacent_step_limit=_parameter(parameters, "max_adjacent_step"),
        max_dc_limit=_parameter(parameters, "max_dc"),
    )
