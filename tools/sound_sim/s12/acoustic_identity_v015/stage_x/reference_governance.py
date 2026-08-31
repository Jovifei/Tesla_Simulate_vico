"""Reference provenance and independence governance for Stage X/Y.

A scenario window is not an independent recording.  This module prevents one
file split into several windows from satisfying a multi-reference gate and
prevents video-derived material from being promoted to R2/R1 by a local label.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REFERENCE_GOVERNANCE_SCHEMA = "s12.stage_y.reference_governance.v1"

_VIDEO_HOST_MARKERS = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "bilibili.com",
)
_VIDEO_DERIVATION_MARKERS = (
    "yt-dlp",
    "youtube",
    "video_extract",
    "video-derived",
    "decoded_wav",
)


def _text_fields(record: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "source_url",
        "audio_path",
        "source_kind",
        "extraction",
        "derivation",
        "provenance",
        "notes",
        "title",
    ):
        value = record.get(key)
        if value is not None:
            values.append(str(value))
    external = record.get("external_media")
    if isinstance(external, dict):
        values.extend(str(value) for value in external.values() if value is not None)
    return " ".join(values).lower()


def is_video_derived(record: dict[str, Any]) -> bool:
    """Return True for public-video extraction or a video-host source."""
    text = _text_fields(record)
    if any(marker in text for marker in _VIDEO_DERIVATION_MARKERS):
        return True
    source_url = str(record.get("source_url") or "")
    if not source_url and isinstance(record.get("external_media"), dict):
        source_url = str(record["external_media"].get("source_url") or "")
    host = urlparse(source_url).netloc.lower()
    return any(marker in host for marker in _VIDEO_HOST_MARKERS)


def classify_reference_evidence(record: dict[str, Any]) -> dict[str, Any]:
    """Classify one source without allowing a local evidence promotion."""
    declared = str(
        record.get("evidence_level")
        or record.get("source_level")
        or record.get("reference_class")
        or "R3"
    ).upper()
    video_derived = is_video_derived(record)
    rights = str(
        record.get("rights_status")
        or record.get("license_status")
        or record.get("license")
        or ""
    ).upper()
    raw_audio = bool(record.get("raw_audio_confirmed")) or str(
        record.get("source_kind") or ""
    ).lower() in {"controlled_raw_audio", "authorized_raw_audio"}
    synchronized = all(
        record.get(name)
        for name in ("rpm_trace", "load_trace", "gear_trace")
    ) or bool(record.get("synchronized_state"))

    reasons: list[str] = []
    if video_derived:
        effective = "R3"
        reasons.append("VIDEO_DERIVED_REFERENCE_CANNOT_BE_PROMOTED")
    elif declared == "R1":
        rights_clear = any(token in rights for token in ("CLEARED", "CONFIRMED", "AUTHORIZED"))
        if raw_audio and rights_clear and synchronized:
            effective = "R1"
        else:
            effective = "R2" if rights_clear else "R3"
            if not raw_audio:
                reasons.append("R1_RAW_AUDIO_RECEIPT_MISSING")
            if not rights_clear:
                reasons.append("R1_RIGHTS_NOT_CLEARED")
            if not synchronized:
                reasons.append("R1_SYNCHRONIZED_STATE_MISSING")
    elif declared == "R2":
        rights_known = bool(rights) and not any(
            token in rights for token in ("UNKNOWN", "UNVERIFIED", "PENDING")
        )
        effective = "R2" if rights_known else "R3"
        if not rights_known:
            reasons.append("R2_RIGHTS_EVIDENCE_INSUFFICIENT")
    else:
        effective = "R3"

    return {
        "schema": REFERENCE_GOVERNANCE_SCHEMA,
        "declared_evidence_level": declared,
        "effective_evidence_level": effective,
        "video_derived": video_derived,
        "raw_audio_confirmed": raw_audio,
        "synchronized_state": synchronized,
        "rights_status": rights or "UNKNOWN",
        "downgrade_reasons": reasons,
    }


def source_identity(record: dict[str, Any]) -> dict[str, str]:
    """Build stable source and recording-session identities."""
    audio_sha = str(
        record.get("audio_sha256")
        or record.get("sha256")
        or record.get("source_audio_sha256")
        or ""
    ).lower()
    explicit_source = str(
        record.get("source_id")
        or record.get("recording_id")
        or record.get("reference_id_base")
        or ""
    ).strip()
    source_url = str(record.get("source_url") or "").strip()
    if not source_url and isinstance(record.get("external_media"), dict):
        source_url = str(record["external_media"].get("source_url") or "").strip()
    audio_path = str(record.get("audio_path") or "").strip()

    if explicit_source:
        source_id = explicit_source
    elif audio_sha:
        source_id = f"sha256:{audio_sha}"
    elif source_url:
        source_id = f"url:{source_url}"
    else:
        source_id = f"path:{Path(audio_path).as_posix()}"

    session_hint = str(
        record.get("recording_session_id")
        or record.get("session_id")
        or record.get("recording_id")
        or source_id
    )
    recording_session_id = hashlib.sha256(session_hint.encode("utf-8")).hexdigest()
    return {
        "source_id": source_id,
        "recording_session_id": recording_session_id,
        "audio_sha256": audio_sha,
    }


def summarize_reference_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize bound windows and truly independent recordings separately."""
    bound = [case for case in cases if case.get("status") == "BOUND"]
    source_ids = {
        str(case.get("source_id"))
        for case in bound
        if case.get("source_id")
    }
    sessions = {
        str(case.get("recording_session_id"))
        for case in bound
        if case.get("recording_session_id")
    }
    audio_shas = {
        str(case.get("audio_sha256")).lower()
        for case in bound
        if case.get("audio_sha256")
    }
    scenarios = {str(case.get("scenario")) for case in bound if case.get("scenario")}
    evidence_counts: dict[str, int] = {}
    for case in bound:
        level = str(case.get("evidence_level") or "R3")
        evidence_counts[level] = evidence_counts.get(level, 0) + 1
    independent_count = len(sessions or source_ids or audio_shas)
    return {
        "schema": REFERENCE_GOVERNANCE_SCHEMA,
        "bound_scenario_count": len(scenarios),
        "bound_case_count": len(bound),
        "unique_audio_sha_count": len(audio_shas),
        "unique_source_count": len(source_ids),
        "independent_recording_session_count": independent_count,
        "selection_reference_count": independent_count,
        "evidence_case_counts": evidence_counts,
        "independent_source_gate_passed": independent_count >= 2,
        "note": (
            "scenario windows from one recording count once for engineering "
            "multi-reference eligibility"
        ),
    }


def effective_caseset_evidence(cases: list[dict[str, Any]]) -> str:
    """Return the strongest level shared by at least one bound case."""
    levels = {
        str(case.get("evidence_level") or "R3")
        for case in cases
        if case.get("status") == "BOUND"
    }
    if "R1" in levels:
        return "R1"
    if "R2" in levels or "R2_AUDIO_DIAGNOSTIC" in levels:
        return "R2_AUDIO_DIAGNOSTIC"
    return "R3_AUDIO_DIAGNOSTIC"


__all__ = [
    "REFERENCE_GOVERNANCE_SCHEMA",
    "classify_reference_evidence",
    "effective_caseset_evidence",
    "is_video_derived",
    "source_identity",
    "summarize_reference_cases",
]
