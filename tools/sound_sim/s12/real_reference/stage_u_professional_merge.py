"""Bind MATLAB and MoSQITo Stage U clip receipts to legacy triad results by SHA."""
from __future__ import annotations

from statistics import mean
from typing import Any, Mapping, Sequence


_METRICS = ("loudness_sone", "sharpness_acum", "roughness_asper", "fluctuation_vacil", "tone_to_noise_ratio_db", "prominence_ratio_db")


def _index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("clip_id")): row for row in rows if isinstance(row, Mapping) and str(row.get("clip_id") or "")}


def _triad_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(row.get("reference_id") or ""), str(row.get("candidate_id") or "")): row
        for row in rows
        if isinstance(row, Mapping) and str(row.get("reference_id") or "") and str(row.get("candidate_id") or "")
    }


def _distance(reference: Mapping[str, Any], other: Mapping[str, Any]) -> float | None:
    ref = reference.get("metrics") if isinstance(reference.get("metrics"), Mapping) else {}
    value = other.get("metrics") if isinstance(other.get("metrics"), Mapping) else {}
    terms = []
    for name in _METRICS:
        first, second = ref.get(name), value.get(name)
        if isinstance(first, (int, float)) and not isinstance(first, bool) and isinstance(second, (int, float)) and not isinstance(second, bool):
            terms.append(abs(float(second) - float(first)) / max(abs(float(first)), 1e-9))
    return float(mean(terms)) if terms else None


def merge_professional_triad_results(
    legacy_results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    matlab_receipt: Mapping[str, Any],
    mosqito_receipt: Mapping[str, Any],
    audio_feature_results: Mapping[str, Any],
) -> dict[str, Any]:
    """Produce a transparent relative composite only when every receipt SHA agrees."""

    expected = {str(row.get("clip_id")): str(row.get("sha256")) for row in manifest.get("clips", []) if isinstance(row, Mapping)}
    matlab = _index(matlab_receipt.get("results", []))
    mosqito = _index(mosqito_receipt.get("results", []))
    audio_features = _triad_index(audio_feature_results.get("results", []))
    rows = []
    for legacy in legacy_results:
        reference_id, candidate_id = (str(legacy["reference_id"]), str(legacy["candidate_id"]))
        clip_ids = {"reference": f"reference::{reference_id}", "parent": f"parent::{reference_id}", "candidate": f"candidate::{reference_id}::{candidate_id}"}
        expected_sha_by_role = {role: expected.get(clip_id) for role, clip_id in clip_ids.items()}
        legacy_bound = all(
            expected_sha_by_role[role]
            and str(legacy.get(f"{role}_sha256") or "") == expected_sha_by_role[role]
            for role in clip_ids
        )
        receipt_bound = all(
            clip_ids[role] in expected
            and clip_ids[role] in matlab
            and clip_ids[role] in mosqito
            and str(matlab[clip_ids[role]].get("input_sha256")) == expected[clip_ids[role]]
            and str(mosqito[clip_ids[role]].get("input_sha256")) == expected[clip_ids[role]]
            for role in clip_ids
        )
        audio = audio_features.get((reference_id, candidate_id))
        audio_bound = bool(audio and audio.get("professional_bound") and isinstance(audio.get("sha_binding"), Mapping) and all(str(audio["sha_binding"].get(role) or "") == expected_sha_by_role[role] for role in clip_ids))
        sha_bound = legacy_bound and receipt_bound and audio_bound
        if not legacy_bound:
            binding_status = "LEGACY_SHA_NOT_BOUND"
        elif not receipt_bound:
            binding_status = "PROFESSIONAL_RECEIPT_SHA_NOT_BOUND"
        elif not audio_bound:
            binding_status = "AUDIO_FEATURE_SHA_NOT_BOUND"
        else:
            binding_status = "ALL_COMPONENT_SHA_BOUND"
        components = [1.0]
        professional = {}
        if sha_bound:
            for name, source in (("matlab", matlab), ("mosqito", mosqito)):
                parent_distance = _distance(source[clip_ids["reference"]], source[clip_ids["parent"]])
                candidate_distance = _distance(source[clip_ids["reference"]], source[clip_ids["candidate"]])
                if parent_distance is None or candidate_distance is None:
                    sha_bound = False
                    break
                professional[name] = {"parent_distance": parent_distance, "candidate_distance": candidate_distance}
                components.append(candidate_distance / max(parent_distance, 1e-12))
            audio_parent = float(audio["parent_distance"])
            audio_candidate = float(audio["candidate_distance"])
            if audio_parent < 0.0 or audio_candidate < 0.0:
                sha_bound = False
            else:
                professional["audioFeatureExtractor"] = {
                    "parent_distance": audio_parent,
                    "candidate_distance": audio_candidate,
                    "state_context": dict(audio.get("state_context") or {}),
                    "selected_feature_families": list(audio.get("selected_feature_families") or []),
                }
                components.append(audio_candidate / max(audio_parent, 1e-12))
        legacy_ratio = float(legacy["candidate_distance"]) / max(float(legacy["parent_distance"]), 1e-12)
        components[0] = legacy_ratio
        candidate_score = float(mean(components))
        row = dict(legacy)
        row.update({
            "professional_bound": sha_bound,
            "professional_binding_status": binding_status,
            "professional_components": professional,
            "parent_distance": 1.0,
            "candidate_distance": candidate_score,
            "absolute_improvement": 1.0 - candidate_score,
            "relative_improvement": 1.0 - candidate_score,
            "sha_binding": {role: expected.get(clip_id) for role, clip_id in clip_ids.items()},
        })
        rows.append(row)
    return {
        "schema_version": "s12-stage-u-professional-triad-results-v1",
        "status": "PROFESSIONAL_TRIAD_COMPARISON_COMPLETE" if all(bool(row["professional_bound"]) for row in rows) else "PROFESSIONAL_TRIAD_COMPARISON_PARTIAL",
        "record_count": len(rows),
        "results": rows,
        "tool_domains": ["Professional MATLAB", "Professional MoSQITo", "MATLAB audioFeatureExtractor", "Legacy Proxy", "Not Qualified"],
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "abx_ready": False,
        "abx_reason": "raw analysis clips are not loudness-matched audition copies",
    }


__all__ = ["merge_professional_triad_results"]
