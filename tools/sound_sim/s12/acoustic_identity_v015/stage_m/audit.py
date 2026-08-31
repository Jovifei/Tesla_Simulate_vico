"""Stage-M public audit/feedback façade."""
from __future__ import annotations

from collections.abc import Mapping

from .callgraph import audit_qualification_callgraph, gate_source_matrix, signal_domain_matrix

VEHICLES = ("ferrari_458", "hellcat", "rx7_fd", "supra_jza80", "aventador_lp700", "c63_w204", "gtr_r35", "lfa")
QUALIFICATION_STATUSES = frozenset(("DIAGNOSTIC_ONLY", "AUTOMATED_PASS_HUMAN_PENDING", "HUMAN_FAIL_REPAIR_REQUIRED", "PROFILE_CANDIDATE", "PROFILE_FREEZE_READY"))
REQUIRED_FEEDBACK_FIELDS = frozenset(("listener_id", "playback_device", "windows_volume", "playback_endpoint", "vehicle_id", "scenario", "baseline_file", "candidate_file", "candidate_sha256", "package_manifest_sha256", "identity_score", "realism_score", "low_frequency_score", "mechanical_score", "shift_score", "afterfire_score", "artifact_score", "preference", "notes"))


def build_gate_matrix(automatic: Mapping[str, bool], feedback: Mapping[str, object]) -> dict[str, str]:
    """Do not infer a human pass; only expose the five permitted statuses."""

    result: dict[str, str] = {}
    for vehicle in VEHICLES:
        if automatic.get(vehicle) is not True:
            result[vehicle] = "DIAGNOSTIC_ONLY"
        elif feedback.get("accepted") is not True:
            result[vehicle] = "AUTOMATED_PASS_HUMAN_PENDING"
        else:
            result[vehicle] = "PROFILE_CANDIDATE"
    return result


from .feedback import validate_named_feedback  # noqa: E402  (constants above are feedback contract inputs)

__all__ = [
    "QUALIFICATION_STATUSES", "REQUIRED_FEEDBACK_FIELDS", "VEHICLES", "audit_qualification_callgraph", "build_gate_matrix",
    "gate_source_matrix", "signal_domain_matrix", "validate_named_feedback",
]
