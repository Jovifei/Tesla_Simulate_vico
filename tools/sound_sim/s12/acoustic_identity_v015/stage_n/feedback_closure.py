"""Convert explicitly confirmed SHA-bound Stage-N feedback into an audit view."""
from __future__ import annotations

from typing import Mapping


def prepare_feedback_closure(
    import_receipt: Mapping[str, object],
    package_binding: Mapping[str, object],
    comparator_results: Mapping[str, object],
    *,
    confirmed_by_jovi: bool,
) -> dict[str, object]:
    """Build a no-source-change feedback view only after explicit user confirmation."""

    if not confirmed_by_jovi:
        return {
            "schema_version": "s12-stage-n-feedback-closure-1",
            "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
            "human_feedback_available": False,
            "promotion_block": "listener provenance must be explicitly confirmed by Jovi; no source changes are authorized here",
        }
    if import_receipt.get("status") != "IMPORTED_JOVI_FEEDBACK_PENDING_REVIEW":
        raise ValueError("only a SHA-bound pending Jovi feedback receipt can be confirmed")
    trials = package_binding.get("trials")
    rows = import_receipt.get("rows")
    vehicles = comparator_results.get("vehicles")
    if not isinstance(trials, Mapping) or not isinstance(rows, list) or not isinstance(vehicles, Mapping):
        raise ValueError("feedback closure needs trial binding, imported rows, and unified comparator results")
    if import_receipt.get("accepted_rows") != len(rows) or import_receipt.get("rejected_rows") != 0 or not rows:
        raise ValueError("feedback closure requires accepted, rejection-free rows")
    manifest_sha = str(package_binding.get("package_manifest_sha256", ""))
    vehicle_ids = {str(trial.get("vehicle_id")) for trial in trials.values() if isinstance(trial, Mapping)}
    confusion: dict[str, dict[str, int]] = {vehicle: {guess: 0 for guess in sorted(vehicle_ids)} for vehicle in sorted(vehicle_ids)}
    objective_bindings: dict[str, dict[str, object]] = {}
    human_scores: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or str(row.get("listener_id", "")).strip().lower() != "jovi":
            raise ValueError("all confirmed feedback rows must identify Jovi")
        anonymous_id = str(row.get("anonymous_id", ""))
        trial = trials.get(anonymous_id)
        if not isinstance(trial, Mapping):
            raise ValueError("feedback row has unknown anonymous_id")
        actual = str(trial.get("vehicle_id", ""))
        scenario = str(trial.get("scenario", ""))
        if (
            row.get("package_manifest_sha256") != manifest_sha
            or row.get("candidate_sha256") != trial.get("candidate_sha256")
            or str(row.get("identity_guess", "")) not in vehicle_ids
        ):
            raise ValueError("feedback row violates its package/file identity binding")
        predicted = str(row["identity_guess"])
        confusion[actual][predicted] += 1
        scenario_result = vehicles.get(actual, {})
        if not isinstance(scenario_result, Mapping) or not isinstance(scenario_result.get(scenario), Mapping):
            raise ValueError("feedback row has no matching unified comparator scenario")
        objective_bindings.setdefault(actual, {})[scenario] = dict(scenario_result[scenario])
        human_scores.setdefault(actual, []).append({
            key: value
            for key, value in row.items()
            if key not in {"listener_id", "anonymous_id", "package_manifest_sha256", "candidate_sha256", "identity_guess"}
        })
    return {
        "schema_version": "s12-stage-n-feedback-closure-1",
        "status": "CONFIRMED_JOVI_FEEDBACK_IMPORTED",
        "human_feedback_available": True,
        "package_manifest_sha256": manifest_sha,
        "identity_confusion_matrix": confusion,
        "human_scores_by_vehicle": human_scores,
        "objective_residual_bindings": objective_bindings,
        "no_source_change": True,
        "promotion_block": "create a separate sound-fix branch before any parameter change; this comparator branch remains evidence-only",
    }
