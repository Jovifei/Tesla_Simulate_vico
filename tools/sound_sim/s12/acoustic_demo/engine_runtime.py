"""Runtime mode classification and smoothing for the synthetic PC simulator."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from enum import Enum
import math

from engine_excitation import ORDER_PROFILE_PATH, PARAMETERS_PATH, load_json_package
from engine_operating_points.library import load_operating_point_library
from runtime_pcm import BLOCK_SAMPLES, PCMFrame, RuntimePcmRenderer
from runtime_ptr_adapter import RuntimePtrAdapter
from sound_renderer.s12_product_renderer import renderer_profile_from_library
from vehicle_state_runtime.stream import VehicleState


class RuntimeMode(str, Enum):
    IDLE = "IDLE"
    CRUISE = "CRUISE"
    ACCELERATION = "ACCELERATION"
    DECELERATION = "DECELERATION"
    HIGH_LOAD = "HIGH_LOAD"


@dataclass(frozen=True)
class RuntimeTransition:
    mode: RuntimeMode
    target_mode: RuntimeMode
    progress: float


class RuntimeStateMachine:
    """Classify operating modes while crossfading mode identity over time."""

    def __init__(self, transition_s: float = 0.25) -> None:
        if transition_s <= 0.0:
            raise ValueError("transition time must be positive")
        self.transition_s = float(transition_s)
        self._mode: RuntimeMode | None = None
        self._target_mode: RuntimeMode | None = None
        self._progress = 1.0
        self._previous_timestamp_s: float | None = None

    @staticmethod
    def classify(state: VehicleState) -> RuntimeMode:
        if state.load >= 0.75:
            return RuntimeMode.HIGH_LOAD
        if state.acceleration_mps2 >= 0.05:
            return RuntimeMode.ACCELERATION
        if state.acceleration_mps2 <= -0.05:
            return RuntimeMode.DECELERATION
        if state.rpm <= 1000.0 and state.speed_mps <= 0.5 and state.load <= 0.10:
            return RuntimeMode.IDLE
        return RuntimeMode.CRUISE

    def update(self, state: VehicleState) -> RuntimeTransition:
        target = self.classify(state)
        if self._mode is None:
            self._mode = target
            self._target_mode = target
            self._previous_timestamp_s = state.timestamp_s
            return RuntimeTransition(self._mode, target, 1.0)
        if state.timestamp_s <= self._previous_timestamp_s:
            raise ValueError("runtime state timestamps must be strictly increasing")
        delta_s = state.timestamp_s - self._previous_timestamp_s
        self._previous_timestamp_s = state.timestamp_s
        if target != self._target_mode:
            self._target_mode = target
            self._progress = 0.0
        if self._mode != self._target_mode:
            self._progress = min(1.0, self._progress + delta_s / self.transition_s)
            if self._progress == 1.0:
                self._mode = self._target_mode
        return RuntimeTransition(self._mode, self._target_mode, self._progress)


def _parameter_values() -> tuple[dict[str, float], tuple[tuple[float, float, float], ...]]:
    parameters = load_json_package(PARAMETERS_PATH)["parameters"]
    values = {name: float(parameter["value"]) for name, parameter in parameters.items()}
    profile = load_json_package(ORDER_PROFILE_PATH)["parameters"].values()
    orders = tuple((float(entry["order"]), float(entry["amplitude"]), float(entry["phase_rad"])) for entry in profile)
    return values, orders


class _StateSanitizer:
    """Reject invalid or implausibly discontinuous external runtime controls."""

    max_rpm_per_s = 30000.0

    def __init__(self) -> None:
        self.fallback_count = 0

    def accept(self, candidate: VehicleState, previous: VehicleState | None) -> tuple[VehicleState, bool]:
        values = (candidate.timestamp_s, candidate.rpm, candidate.speed_mps, candidate.acceleration_mps2, candidate.load, candidate.throttle)
        valid = (
            all(math.isfinite(value) for value in values)
            and candidate.timestamp_s >= 0.0
            and 800.0 <= candidate.rpm <= 6000.0
            and 0.0 <= candidate.speed_mps <= 100.0
            and abs(candidate.acceleration_mps2) <= 20.0
            and 0.0 <= candidate.load <= 1.0
            and 0.0 <= candidate.throttle <= 1.0
        )
        if previous is not None:
            elapsed_s = candidate.timestamp_s - previous.timestamp_s
            valid = valid and elapsed_s > 0.0 and abs(candidate.rpm - previous.rpm) <= self.max_rpm_per_s * elapsed_s
        if valid:
            return candidate, False
        self.fallback_count += 1
        if previous is None:
            timestamp_s = candidate.timestamp_s if math.isfinite(candidate.timestamp_s) and candidate.timestamp_s >= 0.0 else 0.0
            return VehicleState.synthetic_idle(timestamp_s), True
        timestamp_s = candidate.timestamp_s if math.isfinite(candidate.timestamp_s) and candidate.timestamp_s > previous.timestamp_s else previous.timestamp_s + BLOCK_SAMPLES / 48000.0
        return replace(previous, timestamp_s=timestamp_s), True


class _RuntimeExcitation:
    """Pre-PTR order/transient synthesis retaining phase and smoothing state."""

    def __init__(self) -> None:
        self.library = load_operating_point_library()
        self.sample_rate_hz = 48000
        self.parameters, self.orders = _parameter_values()
        self.phase = 0.0
        self.transient = 0.0
        self.smoothed_rpm: float | None = None
        self.smoothed_load: float | None = None
        self.previous_rpm: float | None = None

    def render_block(self, previous: VehicleState, current: VehicleState, frame_count: int = BLOCK_SAMPLES) -> list[float]:
        samples = []
        smoothing = 1.0 / (0.050 * self.sample_rate_hz)
        for index in range(frame_count):
            fraction = (index + 1) / frame_count
            target_rpm = previous.rpm + (current.rpm - previous.rpm) * fraction
            target_load = (previous.load + (current.load - previous.load) * fraction + previous.throttle + (current.throttle - previous.throttle) * fraction) * 0.5
            self.smoothed_rpm = target_rpm if self.smoothed_rpm is None else self.smoothed_rpm + (target_rpm - self.smoothed_rpm) * smoothing
            self.smoothed_load = target_load if self.smoothed_load is None else self.smoothed_load + (target_load - self.smoothed_load) * smoothing
            operating_point = self.library.evaluate(self.smoothed_rpm, self.smoothed_load)
            self.phase = math.fmod(self.phase + 2.0 * math.pi * self.smoothed_rpm / 60.0 / self.sample_rate_hz, 2.0 * math.pi)
            order_sum = 0.0
            for order, amplitude, phase_rad in self.orders:
                high_order = max(0.0, order - 1.0)
                harmonic_scale = operating_point.harmonic_gain if order > 1.0 else 1.0
                balance = 1.0 + high_order * self.smoothed_load * self.parameters["high_order_load_gain"]
                order_sum += amplitude * operating_point.excitation_gain * harmonic_scale * balance * math.sin(order * self.phase + phase_rad)
            rpm_rate = 0.0 if self.previous_rpm is None else (self.smoothed_rpm - self.previous_rpm) * self.sample_rate_hz
            acceleration = previous.acceleration_mps2 + (current.acceleration_mps2 - previous.acceleration_mps2) * fraction
            target_transient = self.parameters["transient_gain"] * operating_point.transient_gain * (
                abs(acceleration) / self.parameters["acceleration_reference_mps2"]
                + abs(rpm_rate) / self.parameters["rpm_rate_reference"]
            ) * (self.parameters["transient_load_floor"] + self.smoothed_load * self.parameters["transient_load_span"])
            time_constant = self.parameters["attack_s"] if target_transient > self.transient else self.parameters["decay_s"]
            self.transient += (target_transient - self.transient) / max(1.0, time_constant * self.sample_rate_hz)
            speed = previous.speed_mps + (current.speed_mps - previous.speed_mps) * fraction
            speed_mode = self.parameters["speed_mode_floor"] + self.parameters["speed_mode_span"] * min(1.0, speed / self.parameters["speed_cruise_mps"])
            samples.append(speed_mode * order_sum + self.transient * math.sin(self.parameters["transient_carrier_order"] * self.phase))
            self.previous_rpm = self.smoothed_rpm
        return samples


class EngineSoundRuntime:
    """Continuous 20 ms synthetic PCM generator for the PC-only runtime simulator."""

    def __init__(self) -> None:
        library = load_operating_point_library()
        self._excitation = _RuntimeExcitation()
        self._ptr = RuntimePtrAdapter()
        self._renderer = RuntimePcmRenderer(renderer_profile_from_library(library))
        self._state_machine = RuntimeStateMachine()
        self._sanitizer = _StateSanitizer()
        self._previous_audio_state: VehicleState | None = None
        self._previous_ingested_state: VehicleState | None = None
        self._pending_states: deque[tuple[VehicleState, bool, RuntimeTransition]] = deque()
        self._sequence_index = 0
        self.state_updates_consumed = 0

    @property
    def fallback_count(self) -> int:
        return self._sanitizer.fallback_count

    def _accept_state(self, state: VehicleState) -> tuple[VehicleState, bool, RuntimeTransition]:
        accepted, fallback = self._sanitizer.accept(state, self._previous_ingested_state)
        self._previous_ingested_state = accepted
        return accepted, fallback, self._state_machine.update(accepted)

    def update_vehicle_state(self, state: VehicleState) -> None:
        """Ingest one 100 Hz vehicle-state update for the next PCM callback."""
        self._pending_states.append(self._accept_state(state))

    def _render(self, segments: tuple[tuple[VehicleState, VehicleState, int], ...], fallback: bool, transition: RuntimeTransition) -> PCMFrame:
        excitation = []
        for previous, current, frame_count in segments:
            excitation.extend(self._excitation.render_block(previous, current, frame_count))
        pressure = self._ptr.process(excitation)
        frame = self._renderer.render(pressure, self._sequence_index)
        self._sequence_index += 1
        return replace(
            frame,
            fallback_applied=fallback,
            runtime_mode=transition.mode.value,
            transition_progress=transition.progress,
        )

    def audio_callback(self, state: VehicleState | None = None) -> PCMFrame:
        """Render one 20 ms PCM frame from a direct state or two 100 Hz updates."""
        if state is not None:
            accepted, fallback, transition = self._accept_state(state)
            previous = self._previous_audio_state or accepted
            self._previous_audio_state = accepted
            return self._render(((previous, accepted, BLOCK_SAMPLES),), fallback, transition)
        if len(self._pending_states) < 2:
            raise RuntimeError("audio callback requires two queued 100 Hz state updates")
        first, first_fallback, first_transition = self._pending_states.popleft()
        second, second_fallback, second_transition = self._pending_states.popleft()
        previous = self._previous_audio_state or first
        self._previous_audio_state = second
        self.state_updates_consumed += 2
        return self._render(
            ((previous, first, BLOCK_SAMPLES // 2), (first, second, BLOCK_SAMPLES // 2)),
            first_fallback or second_fallback,
            second_transition if second_transition.progress >= first_transition.progress else first_transition,
        )
