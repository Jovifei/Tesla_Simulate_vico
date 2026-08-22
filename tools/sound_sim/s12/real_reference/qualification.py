"""Stage Q/R qualification gates for external recordings."""
from __future__ import annotations

from typing import Any


R1_FIELDS = (
    "legal_permission",
    "exact_vehicle_trim",
    "stock_exhaust_confirmation",
    "synchronized_rpm_trace",
    "load_throttle_trace",
    "gear_shift_trace",
    "microphone_position",
    "recording_device_agc_contract",
)


class ReferenceQualificationError(ValueError):
    """Raised when a reference is not allowed into a qualified comparison."""


def qualify_r1_reference(record: dict[str, Any]) -> dict[str, Any]:
    """Return an auditable R1 gate result without changing the input record."""

    provenance = record.get("provenance", {})
    contract = record.get("analysis_contract", {})
    checks = {
        "legal_permission": provenance.get("legal_permission") == "CONFIRMED",
        "exact_vehicle_trim": provenance.get("stock_identity") == "VERIFIED_EXACT_TRIM",
        "stock_exhaust_confirmation": provenance.get("stock_identity") == "VERIFIED_EXACT_TRIM",
        "synchronized_rpm_trace": contract.get("rpm_state_status") == "SYNCED",
        "load_throttle_trace": contract.get("load_throttle_status") == "SYNCED",
        "gear_shift_trace": contract.get("gear_shift_status") == "SYNCED",
        "microphone_position": provenance.get("microphone_perspective") == "EXTERIOR_REAR",
        "recording_device_agc_contract": provenance.get("recording_device_agc") == "DOCUMENTED_NO_AGC",
    }
    missing = [name for name in R1_FIELDS if not checks[name]]
    return {
        "recording_id": record.get("recording_id"),
        "vehicle_id": record.get("vehicle_id"),
        "eligible": not missing and bool(record.get("file_present")) and bool(record.get("sha256")),
        "checks": checks,
        "missing": missing + (["raw_audio_file_or_sha256"] if not record.get("file_present") or not record.get("sha256") else []),
        "qualification": "R1" if not missing and record.get("file_present") and record.get("sha256") else "NOT_R1",
        "stage_r_eligible": not missing and bool(record.get("file_present")) and bool(record.get("sha256")),
        "automatic_tuning_eligible": False,
    }


def require_r1_reference(record: dict[str, Any]) -> dict[str, Any]:
    gate = qualify_r1_reference(record)
    if not gate["eligible"]:
        missing = ", ".join(gate["missing"])
        raise ReferenceQualificationError(
            f"reference {record.get('recording_id', '<unknown>')} is not R1-eligible: {missing}"
        )
    return gate


__all__ = ["R1_FIELDS", "ReferenceQualificationError", "qualify_r1_reference", "require_r1_reference"]
