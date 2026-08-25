"""Continuous, block-safe crank/rotor phase state."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .config_schema import unwrap

@dataclass(frozen=True)
class PhaseBlock:
    phase_rad: np.ndarray
    omega_rad_s: np.ndarray
    sync_error_rad_s: np.ndarray
    torque_ripple: np.ndarray
    load_torque: np.ndarray
    friction_torque: np.ndarray
    idle_governor_torque: np.ndarray
    combustion_torque: np.ndarray

class CrankPhasePLL:
    def __init__(self, sample_rate_hz: int, config: dict, mode: str = "measured_rpm"):
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        self.sample_rate_hz = int(sample_rate_hz)
        self.config = config
        if mode not in {"measured_rpm", "free_dynamics"}:
            raise ValueError("mode must be measured_rpm or free_dynamics")
        self.mode = mode
        self.phase_rad = 0.0
        self.omega_rad_s = 0.0
        self.initialized = False
        self.sample_count = 0

    def process_block(self, rpm: np.ndarray, load: np.ndarray, throttle: np.ndarray, acceleration: np.ndarray, combustion_torque_input: np.ndarray | None = None) -> PhaseBlock:
        rpm = np.asarray(rpm, dtype=np.float64)
        load = np.asarray(load, dtype=np.float64)
        throttle = np.asarray(throttle, dtype=np.float64)
        acceleration = np.asarray(acceleration, dtype=np.float64)
        if combustion_torque_input is None:
            combustion_torque_input = np.zeros_like(rpm)
        else:
            combustion_torque_input = np.asarray(combustion_torque_input, dtype=np.float64)
        if not (rpm.ndim == load.ndim == throttle.ndim == acceleration.ndim == combustion_torque_input.ndim == 1):
            raise ValueError("PLL inputs must be one-dimensional")
        if len({rpm.size, load.size, throttle.size, acceleration.size, combustion_torque_input.size}) != 1 or rpm.size == 0:
            raise ValueError("PLL inputs must have equal nonzero length")
        if not all(np.all(np.isfinite(x)) for x in (rpm, load, throttle, acceleration, combustion_torque_input)):
            raise ValueError("PLL inputs must be finite")
        if np.any(rpm < 0.0):
            raise ValueError("rpm must be nonnegative")
        dt = 1.0 / self.sample_rate_hz
        inertia = max(float(unwrap(self.config, "crank_inertia")), 1.0e-4)
        friction = float(unwrap(self.config, "friction_model"))
        entity_count = int(unwrap(self.config, "cylinder_or_rotor_count"))
        phases = np.empty(rpm.size, dtype=np.float64)
        omegas = np.empty_like(phases)
        errors = np.empty_like(phases)
        ripple_trace = np.empty_like(phases)
        load_trace = np.empty_like(phases)
        friction_trace = np.empty_like(phases)
        governor_trace = np.empty_like(phases)
        combustion_trace = np.empty_like(phases)
        for i, target_rpm in enumerate(rpm):
            target = max(0.0, target_rpm) * 2.0 * np.pi / 60.0
            if not self.initialized:
                self.omega_rad_s = target
                self.initialized = True
            sync_error = target - self.omega_rad_s
            load_torque = 0.03 * np.clip(load[i], 0.0, 1.0) * max(target, 1.0)
            friction_torque = friction * max(self.omega_rad_s, 1.0)
            governor = float(unwrap(self.config, "idle_governor")) * (1.0 - throttle[i]) if target_rpm <= float(unwrap(self.config, "idle_target_rpm")) * 1.25 else 0.0
            governor_torque = governor * 0.10 * max(target, 1.0)
            combustion_torque = 0.005 * (0.25 + np.clip(load[i], 0.0, 1.0)) * max(target, 1.0)
            ripple = 0.004 * max(target, 1.0) * np.sin(self.phase_rad * max(entity_count, 1) + (self.sample_count + i) * 0.017)
            tracking_torque = 96.0 * sync_error if self.mode == "measured_rpm" else 0.0
            acceleration_torque = 0.001 * float(acceleration[i]) * max(target, 1.0)
            combustion_torque += float(combustion_torque_input[i])
            torque_accel = (tracking_torque - friction_torque - load_torque + governor_torque + combustion_torque + acceleration_torque + ripple) / inertia
            self.omega_rad_s = max(0.0, self.omega_rad_s + torque_accel * dt)
            self.phase_rad += max(self.omega_rad_s, 1.0e-9) * dt
            phases[i] = self.phase_rad
            omegas[i] = self.omega_rad_s
            errors[i] = target - self.omega_rad_s
            ripple_trace[i] = ripple
            load_trace[i] = load_torque
            friction_trace[i] = friction_torque
            governor_trace[i] = governor_torque
            combustion_trace[i] = combustion_torque
        self.sample_count += rpm.size
        return PhaseBlock(phases, omegas, errors, ripple_trace, load_trace, friction_trace, governor_trace, combustion_trace)
