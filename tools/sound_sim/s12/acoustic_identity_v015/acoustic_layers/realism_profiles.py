"""Shared C-level synthetic profiles for Track-S realism layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShiftProfile:
    gearbox: str
    jerk_s: float
    impact_gain: float
    recovery_gain: float
    recovery_hz: float = 70.0


@dataclass(frozen=True)
class RumbleProfile:
    gain: float
    low_hz: float = 30.0
    high_hz: float = 90.0


@dataclass(frozen=True)
class AfterfireProfile:
    min_rpm: float
    cluster_stride: int
    gain: float
    low_hz: float
    high_hz: float
    stereo: float
    events_per_rev: float
    target_centroid_hz: float


@dataclass(frozen=True)
class RealismProfile:
    vehicle_id: str
    idle_rpm: float
    redline_rpm: float
    shift: ShiftProfile
    rumble: RumbleProfile
    afterfire: AfterfireProfile
    provenance: str = "C/synthetic"


_PROFILES = (
    RealismProfile("ferrari_458", 1050.0, 9000.0, ShiftProfile("dct", 0.035, 0.50, 0.60), RumbleProfile(0.50), AfterfireProfile(4200.0, 21, 0.18, 300.0, 1500.0, 0.72, 4.0, 656.0)),
    RealismProfile("hellcat", 820.0, 6200.0, ShiftProfile("torque_converter", 0.090, 0.90, 1.00), RumbleProfile(1.00), AfterfireProfile(3300.0, 17, 0.30, 80.0, 700.0, 0.62, 4.0, 303.0)),
    RealismProfile("rx7_fd", 920.0, 7800.0, ShiftProfile("manual", 0.110, 0.70, 0.70), RumbleProfile(0.70), AfterfireProfile(4300.0, 25, 0.16, 120.0, 420.0, 0.70, 3.0, 180.0)),
    RealismProfile("lfa", 900.0, 9000.0, ShiftProfile("sequential", 0.045, 0.45, 0.80), RumbleProfile(0.25), AfterfireProfile(4500.0, 23, 0.14, 400.0, 2000.0, 0.72, 5.0, 1006.0)),
    RealismProfile("aventador_lp700", 950.0, 8700.0, ShiftProfile("automated_manual", 0.065, 0.60, 0.75), RumbleProfile(0.40), AfterfireProfile(4200.0, 21, 0.055, 260.0, 1500.0, 0.70, 6.0, 760.0)),
    RealismProfile("c63_w204", 750.0, 7000.0, ShiftProfile("wet_clutch", 0.075, 0.85, 0.85), RumbleProfile(0.90), AfterfireProfile(3300.0, 17, 0.090, 90.0, 850.0, 0.62, 4.0, 360.0)),
    RealismProfile("gtr_r35", 1000.0, 7000.0, ShiftProfile("dct", 0.045, 0.65, 0.70), RumbleProfile(0.65), AfterfireProfile(3300.0, 18, 0.080, 110.0, 1050.0, 0.62, 3.0, 500.0)),
    RealismProfile("supra_jza80", 800.0, 7200.0, ShiftProfile("manual", 0.100, 0.75, 0.75), RumbleProfile(0.85), AfterfireProfile(3300.0, 18, 0.085, 95.0, 800.0, 0.62, 3.0, 420.0)),
)

REALISM_PROFILES = {profile.vehicle_id: profile for profile in _PROFILES}
SUPPORTED_REALISM_VEHICLE_IDS = tuple(profile.vehicle_id for profile in _PROFILES)


def get_realism_profile(vehicle_id: str) -> RealismProfile:
    try:
        return REALISM_PROFILES[vehicle_id]
    except KeyError as error:
        raise ValueError(f"unsupported realism vehicle_id: {vehicle_id!r}") from error


def validate_realism_profiles() -> None:
    if len(SUPPORTED_REALISM_VEHICLE_IDS) != 8 or len(REALISM_PROFILES) != 8:
        raise ValueError("realism profile registry must contain exactly eight vehicles")
    for profile in REALISM_PROFILES.values():
        if profile.provenance != "C/synthetic":
            raise ValueError(f"profile {profile.vehicle_id} has non-C provenance")
        if not 0.0 < profile.idle_rpm < profile.redline_rpm:
            raise ValueError(f"invalid RPM range for {profile.vehicle_id}")
        if profile.shift.jerk_s <= 0.0 or profile.rumble.gain < 0.0:
            raise ValueError(f"invalid dynamics profile for {profile.vehicle_id}")


validate_realism_profiles()

__all__ = (
    "AfterfireProfile",
    "REALISM_PROFILES",
    "RealismProfile",
    "RumbleProfile",
    "SUPPORTED_REALISM_VEHICLE_IDS",
    "ShiftProfile",
    "get_realism_profile",
    "validate_realism_profiles",
)
