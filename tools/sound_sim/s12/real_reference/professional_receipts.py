"""Validation and merge contracts for exact-clip professional tool receipts."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


class ProfessionalReceiptError(ValueError):
    """Raised when a professional receipt is incomplete or mislabelled."""


METRIC_NAMES = (
    "loudness_sone",
    "sharpness_acum",
    "roughness_asper",
    "fluctuation_vacil",
    "tone_to_noise_ratio_db",
    "tone_to_noise_frequency_hz",
    "prominence_ratio_db",
    "prominence_frequency_hz",
)


def _finite_or_none(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfessionalReceiptError(f"professional metric must be numeric or null: {label}")
    return float(value)


def _validate_rows(receipt: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]], tool_domain: str) -> dict[str, Any]:
    if receipt.get("status") != "EXECUTED_ON_EXACT_CLIPS":
        raise ProfessionalReceiptError(f"{tool_domain} receipt is not exact-clip executed")
    rows = receipt.get("results")
    if not isinstance(rows, list):
        raise ProfessionalReceiptError(f"{tool_domain} receipt has no results")
    expected = {str(pair["pair_id"]): pair for pair in pairs}
    if len(rows) != len(expected) * 2:
        raise ProfessionalReceiptError(f"{tool_domain} receipt must contain reference and candidate for every pair")
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ProfessionalReceiptError(f"{tool_domain} result {index} is malformed")
        pair_id = str(row.get("pair_id") or "")
        side = str(row.get("side") or "")
        if pair_id not in expected or side not in {"reference", "candidate"}:
            raise ProfessionalReceiptError(f"{tool_domain} result has unknown pair/side: {pair_id}/{side}")
        key = (pair_id, side)
        if key in seen:
            raise ProfessionalReceiptError(f"{tool_domain} result is duplicated: {pair_id}/{side}")
        seen.add(key)
        pair = expected[pair_id]
        declared_sha = str(row.get("input_sha256") or "").lower()
        expected_sha = str(pair[f"{side}_sha256"]).lower()
        if declared_sha != expected_sha:
            raise ProfessionalReceiptError(f"{tool_domain} input SHA mismatch: {pair_id}/{side}")
        metrics = row.get("metrics")
        if not isinstance(metrics, Mapping):
            raise ProfessionalReceiptError(f"{tool_domain} metrics missing: {pair_id}/{side}")
        for metric in METRIC_NAMES:
            if metric not in metrics:
                raise ProfessionalReceiptError(f"{tool_domain} metric missing: {pair_id}/{side}/{metric}")
            _finite_or_none(metrics[metric], f"{pair_id}/{side}/{metric}")
        if tool_domain == "Professional MATLAB" and "Legacy Proxy" in str(receipt.get("toolchain")):
            raise ProfessionalReceiptError("MATLAB receipt toolchain contains Legacy Proxy")
    expected_keys = {(pair_id, side) for pair_id in expected for side in ("reference", "candidate")}
    if seen != expected_keys:
        raise ProfessionalReceiptError(f"{tool_domain} receipt is missing reference and candidate results")
    return {
        "status": "VALIDATED_EXACT_CLIPS",
        "tool_domain": tool_domain,
        "clip_count": len(rows),
        "pair_count": len(expected),
        "rows": [dict(row) for row in rows],
        "order_status": receipt.get("order_status") or "ORDER_COMPARISON_NOT_QUALIFIED",
        "calibration": receipt.get("analysis_signal") or receipt.get("input_calibration") or "digital-domain relative only; no absolute SPL",
        "provenance": {
            key: receipt.get(key)
            for key in ("schema_version", "matlab_release", "toolchain", "tool", "mosqito_version")
            if receipt.get(key) is not None
        },
    }


def validate_matlab_receipt(receipt: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    toolchain = receipt.get("toolchain")
    if not isinstance(toolchain, list) or any(name not in toolchain for name in (
        "acousticLoudness", "acousticSharpness", "acousticRoughness", "acousticFluctuation", "acousticToneToNoiseRatio", "acousticProminenceRatio"
    )):
        raise ProfessionalReceiptError("MATLAB receipt toolchain is incomplete")
    return _validate_rows(receipt, pairs, "Professional MATLAB")


def validate_mosqito_receipt(receipt: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if receipt.get("tool") != "MoSQITo" or not str(receipt.get("mosqito_version") or "").strip():
        raise ProfessionalReceiptError("MoSQITo receipt tool/version is missing")
    return _validate_rows(receipt, pairs, "Professional MoSQITo")


def merge_professional_receipts(
    pairs: Sequence[Mapping[str, Any]],
    matlab: Mapping[str, Any],
    mosqito: Mapping[str, Any],
    legacy_proxy: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Merge three explicitly labelled domains into pair-level records."""

    matlab_rows = validate_matlab_receipt(matlab, pairs)["rows"]
    mosqito_rows = validate_mosqito_receipt(mosqito, pairs)["rows"]
    matlab_map = {(str(row["pair_id"]), str(row["side"])): row for row in matlab_rows}
    mosqito_map = {(str(row["pair_id"]), str(row["side"])): row for row in mosqito_rows}
    proxy_map = {str(row["pair_id"]): row for row in legacy_proxy}
    merged: list[dict[str, Any]] = []
    for pair in pairs:
        pair_id = str(pair["pair_id"])
        matlab_ref = matlab_map[(pair_id, "reference")]
        matlab_cand = matlab_map[(pair_id, "candidate")]
        mosqito_ref = mosqito_map[(pair_id, "reference")]
        mosqito_cand = mosqito_map[(pair_id, "candidate")]
        deltas = {
            domain: {
                metric: (
                    (cand.get("metrics", {}).get(metric) - ref.get("metrics", {}).get(metric))
                    if isinstance(cand.get("metrics", {}).get(metric), (int, float)) and isinstance(ref.get("metrics", {}).get(metric), (int, float))
                    else None
                )
                for metric in METRIC_NAMES
            }
            for domain, ref, cand in (
                ("matlab", matlab_ref, matlab_cand),
                ("mosqito", mosqito_ref, mosqito_cand),
            )
        }
        proxy_row = proxy_map.get(pair_id, {})
        legacy_domain = proxy_row.get("legacy_proxy", proxy_row) if isinstance(proxy_row, Mapping) else {}
        if isinstance(legacy_domain, Mapping):
            legacy_domain = dict(legacy_domain)
            legacy_domain.setdefault("tool_domain", "Legacy Proxy")
        merged.append({
            "pair_id": pair_id,
            "file_id": pair["file_id"],
            "vehicle_id": pair["vehicle_id"],
            "scenario": pair["scenario"],
            "reference_class": pair["reference_class"],
            "reference_sha256": pair["reference_sha256"],
            "candidate_sha256": pair["candidate_sha256"],
            "reference_path": pair["reference_path"],
            "candidate_path": pair["candidate_path"],
            "window": pair["window"],
            "microphone_uncertainty": pair["microphone_uncertainty"],
            "order": pair["order"],
            "integrity": proxy_row.get("integrity") if isinstance(proxy_row, Mapping) else None,
            "matlab": {"reference": matlab_ref, "candidate": matlab_cand, "delta": deltas["matlab"], "tool_domain": "Professional MATLAB"},
            "mosqito": {"reference": mosqito_ref, "candidate": mosqito_cand, "delta": deltas["mosqito"], "tool_domain": "Professional MoSQITo"},
            "legacy_proxy": legacy_domain or {"tool_domain": "Legacy Proxy", "status": "MISSING"},
            "spectrogram_residual": proxy_row.get("spectrogram_residual") if isinstance(proxy_row, Mapping) else None,
            "uncertainty": {
                "digital_domain_only": True,
                "absolute_spl": "NOT_AVAILABLE",
                "microphone_agc": pair["microphone_uncertainty"],
                "rpm_state": "MISSING",
                "reference_license_class": pair["reference_class"],
            },
        })
    return {
        "schema_version": "s12-professional-pair-metrics-v1",
        "status": "R2_PROFESSIONAL_COMPARISON_COMPLETE",
        "manifest_sha256": pairs[0].get("manifest_sha256") if pairs else None,
        "pair_count": len(merged),
        "clip_count": len(merged) * 2,
        "tool_domains": ["Professional MATLAB", "Professional MoSQITo", "Legacy Proxy", "Not Qualified"],
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "pairs": merged,
    }


__all__ = ["METRIC_NAMES", "ProfessionalReceiptError", "merge_professional_receipts", "validate_matlab_receipt", "validate_mosqito_receipt"]
