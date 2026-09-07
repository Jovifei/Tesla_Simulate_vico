"""Stage AG vehicle-identity experiments built around the existing EngineAcoustics core."""

from .vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1,
    VEHICLE_IDENTITY_PROFILES,
    VehicleIdentityEngine,
    vehicle_identity_signature,
)

__all__ = [
    "IDENTITY_MODE_LEGACY",
    "IDENTITY_MODE_V1",
    "VEHICLE_IDENTITY_PROFILES",
    "VehicleIdentityEngine",
    "vehicle_identity_signature",
]
