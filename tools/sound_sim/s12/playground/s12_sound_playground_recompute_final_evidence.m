function evidence = s12_sound_playground_recompute_final_evidence(plan, promotion, qualificationCases)
%S12_SOUND_PLAYGROUND_RECOMPUTE_FINAL_EVIDENCE Rehash every protected future-runtime artifact at a report boundary.

if ~hasFormalAfterSha(promotion) || ...
        ~isfile(plan.formal.path)
    error("S12:Playground:FinalEvidence", "A present formal candidate is required for final evidence.");
end
roles = plan.artifacts;
source = s12_sound_playground_source_tree_sha256();
historical = s12_sound_playground_sha256(roles.historical_pre_repair_invalid.path);
workspace = s12_sound_playground_sha256(roles.workspace_unvalidated_intermediate.path);
formal = s12_sound_playground_sha256(plan.formal.path);
reviewedPackage = s12_sound_playground_sha256(plan.authorization.reviewed_package_path);
approvingReport = s12_sound_playground_sha256(plan.authorization.approving_audit_report_path);
assertEqual("current source tree", source.sha256, plan.authorization.reviewed_source_tree_sha256);
assertEqual("current source tree versus blocked plan", source.sha256, plan.source_tree.sha256);
assertEqual("historical invalid evidence", historical, roles.historical_pre_repair_invalid.sha256);
assertEqual("historical invalid authorization", historical, plan.authorization.historical_invalid_sha256);
assertEqual("workspace intermediate evidence", workspace, roles.workspace_unvalidated_intermediate.sha256);
assertEqual("workspace intermediate authorization", workspace, plan.authorization.workspace_intermediate_sha256);
assertEqual("formal candidate promotion", formal, promotion.formal_after_sha256);
assertEqual("reviewed package authorization", reviewedPackage, plan.authorization.reviewed_package_sha256);
assertEqual("approving report authorization", approvingReport, plan.authorization.approving_audit_report_sha256);
evidence = struct("source_tree_sha256", source.sha256, ...
    "historical_invalid_sha256", historical, "workspace_intermediate_sha256", workspace, ...
    "formal_candidate_sha256", formal, "reviewed_package_sha256", reviewedPackage, ...
    "approving_audit_report_sha256", approvingReport, ...
    "preflight_evidence_sha256", upper(string(plan.preflight.sha256)), ...
    "case_artifacts", collectCaseArtifacts(qualificationCases));
end

function cases = collectCaseArtifacts(qualificationCases)
if isempty(qualificationCases)
    cases = struct([]);
    return;
end
cases = repmat(struct("scenario_path", "", "scenario_sha256", "", ...
    "parameter_snapshot_path", "", "parameter_snapshot_sha256", ""), 1, numel(qualificationCases));
for index = 1:numel(qualificationCases)
    item = qualificationCases(index).evidence;
    scenario = s12_sound_playground_sha256(item.scenario_path);
    parameters = s12_sound_playground_sha256(item.parameter_snapshot_path);
    assertEqual("scenario evidence", scenario, item.scenario_sha256);
    assertEqual("parameter snapshot evidence", parameters, item.parameter_snapshot_sha256);
    cases(index) = struct("scenario_path", string(item.scenario_path), "scenario_sha256", scenario, ...
        "parameter_snapshot_path", string(item.parameter_snapshot_path), "parameter_snapshot_sha256", parameters);
end
end

function assertEqual(role, actual, expected)
s12_sound_playground_require_sha256_equal(actual, expected, string(role) + " mismatch");
end

function value = hasFormalAfterSha(promotion)
value = isstruct(promotion) && isscalar(promotion) && isfield(promotion, "formal_after_sha256") && ...
    s12_sound_playground_sha256_equal(promotion.formal_after_sha256, promotion.formal_after_sha256);
end
