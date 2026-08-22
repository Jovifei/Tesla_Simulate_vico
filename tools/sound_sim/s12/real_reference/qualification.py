"""Stage Q/R qualification gates for external recordings."""
from __future__ import annotations

from typing import Any


R1_FIELDS = (
    "vehicle_and_scenario_identity",
    "legal_permission",
    "source_and_license",
    "raw_audio_source",
    "exact_vehicle_trim",
    "stock_exhaust_confirmation",
    "sample_rate",
    "synchronized_rpm_trace",
    "load_throttle_trace",
    "gear_shift_trace",
    "microphone_position",
    "recording_device_agc_contract",
)

R2_FIELDS = (
    "legal_permission",
    "vehicle_and_scenario_identity",
)


class ReferenceQualificationError(ValueError):
    """Raised when a reference is not allowed into a qualified comparison."""


def _documented_capture_field(value: Any) -> bool:
    """Accept an explicit capture description without prescribing its value.

    S12 requires microphone placement and recorder/AGC handling to be
    documented, but it does not require a particular microphone perspective or
    that AGC be disabled.  Unknown/placeholder values remain fail-closed.
    """

    normalized = str(value or "").strip().upper()
    if not normalized or normalized in {"N/A", "NA"}:
        return False
    return not any(marker in normalized for marker in ("UNKNOWN", "UNSPECIFIED", "MISSING"))


def qualify_r1_reference(record: dict[str, Any]) -> dict[str, Any]:
    """Return an auditable R1 gate result without changing the input record.

    A video URL, even when a downloader reports success or the extracted
    stream is PCM, is not an original capture.  R1 therefore requires an
    explicit raw-audio receipt and a non-video-derived source kind in addition
    to the synchronized state and capture-contract fields.
    """

    provenance = record.get("provenance") or {}
    contract = record.get("analysis_contract") or {}
    audio = record.get("audio") or record.get("audio_stream") or {}
    codec = str(audio.get("codec") or audio.get("codec_name") or "").strip().lower()
    sample_rate = audio.get("sample_rate_hz") or audio.get("sample_rate")
    try:
        sample_rate_valid = float(sample_rate) > 0
    except (TypeError, ValueError):
        sample_rate_valid = False
    source_kind = str(provenance.get("source_kind") or "").strip().lower()
    video_derived = "video_extracted" in source_kind or source_kind in {
        "youtube_extracted",
        "video_extracted",
        "user_provided_url_video",
    }
    source_pointer = (
        provenance.get("source_url")
        or provenance.get("source_alias")
        or provenance.get("controlled_alias")
        or record.get("source_url")
        or record.get("source_alias")
    )
    raw_codec = codec.startswith("pcm") or codec in {"pcm", "flac"}
    checks = {
        "vehicle_and_scenario_identity": bool(record.get("vehicle_id")) and bool(record.get("scenario") or record.get("scenario_hint")),
        "legal_permission": provenance.get("legal_permission") == "CONFIRMED",
        "source_and_license": bool(source_pointer) and bool(provenance.get("rights_evidence")) and provenance.get("legal_permission") == "CONFIRMED",
        "raw_audio_source": bool(provenance.get("raw_audio_confirmed")) and bool(source_kind) and not video_derived and raw_codec,
        "exact_vehicle_trim": provenance.get("stock_identity") == "VERIFIED_EXACT_TRIM",
        "stock_exhaust_confirmation": provenance.get("stock_exhaust_confirmation") == "CONFIRMED_STOCK",
        "sample_rate": sample_rate_valid,
        "synchronized_rpm_trace": contract.get("rpm_state_status") == "SYNCED",
        "load_throttle_trace": contract.get("load_throttle_status") == "SYNCED",
        "gear_shift_trace": contract.get("gear_shift_status") == "SYNCED",
        "microphone_position": _documented_capture_field(provenance.get("microphone_perspective")),
        "recording_device_agc_contract": _documented_capture_field(provenance.get("recording_device_agc")),
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


def qualify_r2_reference(record: dict[str, Any]) -> dict[str, Any]:
    """Gate an authorised, scenario-labelled reference for limited metrics.

    R2 deliberately does not imply RPM/order qualification or tuning authority.
    """

    provenance = record.get("provenance", {})
    scenario = record.get("scenario") or record.get("scenario_hint")
    checks = {
        "legal_permission": provenance.get("legal_permission") == "CONFIRMED",
        "vehicle_and_scenario_identity": bool(record.get("vehicle_id")) and bool(scenario),
        "readable_audio_and_sha256": bool(record.get("file_present")) and bool(record.get("sha256")),
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "recording_id": record.get("recording_id"),
        "vehicle_id": record.get("vehicle_id"),
        "eligible": not missing,
        "checks": checks,
        "missing": missing,
        "qualification": "R2" if not missing else "NOT_R2",
        "allowed_metric_groups": ["spectrum", "loudness", "psychoacoustics", "transient_subjective"],
        "order_hard_gate": False,
        "rpm_synchronised_automatic_tuning": False,
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


__all__ = ["R1_FIELDS", "R2_FIELDS", "ReferenceQualificationError", "qualify_r1_reference", "qualify_r2_reference", "require_r1_reference"]
