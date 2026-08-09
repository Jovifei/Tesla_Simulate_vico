function [runtimePlan, receipt] = s12_sound_playground_controlled_rebuild_authorization(blockedPlan, authorization, usedAuthorizationIds, preflight)
%S12_SOUND_PLAYGROUND_CONTROLLED_REBUILD_AUTHORIZATION Derive one runtime plan after external gates.
% This function never starts MATLAB or mutates the blocked source plan.

if nargin < 3
    usedAuthorizationIds = strings(1, 0);
end
if nargin < 4 || ~isstruct(preflight) || ~isfield(preflight, "sha256")
    error("S12:Playground:AuthorizationPreflight", "A verified preflight evidence record is required.");
end
if ~strcmp(s12_sound_playground_require_text_scalar(blockedPlan.execution_policy, "blocked plan execution_policy"), ...
        "BLOCKED_PENDING_EXPLICIT_AUTHORIZATION_AND_INDEPENDENT_REVIEW")
    error("S12:Playground:AuthorizationBasePlan", "Expected a blocked base plan.");
end
required = ["decision", "authorization_schema_version", "reviewed_package_path", "reviewed_package_sha256", ...
    "reviewed_source_tree_sha256", "approving_audit_report_path", "approving_audit_report_sha256", ...
    "historical_invalid_sha256", ...
    "workspace_intermediate_sha256", "preflight_evidence_sha256", "allowed_mcp_root_count", ...
    "allowed_watchdog_count", "authorized_operations", "authorized_by", "authorization_id"];
for index = 1:numel(required)
    field = required(index);
    if ~isfield(authorization, field) || isempty(authorization.(field)) || ...
            all(strlength(string(authorization.(field))) < 1)
        error("S12:Playground:AuthorizationField", "Missing authorization field %s.", field);
    end
end
if ~strcmp(s12_sound_playground_require_text_scalar(authorization.decision, "authorization decision"), ...
        "READY_FOR_CONTROLLED_REBUILD")
    error("S12:Playground:AuthorizationDecision", "Authorization decision is not READY_FOR_CONTROLLED_REBUILD.");
end
if ~strcmp(s12_sound_playground_require_text_scalar(authorization.authorization_schema_version, "authorization schema version"), ...
        authorizationSchemaVersion())
    error("S12:Playground:AuthorizationSchema", "Authorization schema version is not supported.");
end
for field = ["reviewed_package_sha256", "reviewed_source_tree_sha256", "approving_audit_report_sha256", ...
        "historical_invalid_sha256", "workspace_intermediate_sha256", "preflight_evidence_sha256"]
    assertSha(field, authorization.(field));
end
if double(authorization.allowed_mcp_root_count) < 0 || double(authorization.allowed_watchdog_count) < 0
    error("S12:Playground:AuthorizationEnvironment", "Authorized MCP/watchdog counts must be nonnegative.");
end
assertApprovedFile("approving audit report", authorization.approving_audit_report_path, authorization.approving_audit_report_sha256);
assertApprovedFile("reviewed package", authorization.reviewed_package_path, authorization.reviewed_package_sha256);
s12_sound_playground_verify_audit_zip_source_identity( ...
    authorization.reviewed_package_path, authorization.reviewed_source_tree_sha256, authorization.reviewed_source_tree_sha256);
assertEqual("preflight evidence SHA", authorization.preflight_evidence_sha256, preflight.sha256);
if any(strcmp(string(usedAuthorizationIds), ...
        s12_sound_playground_require_text_scalar(authorization.authorization_id, "authorization_id")))
    error("S12:Playground:AuthorizationReuse", "Authorization ID %s is already used.", authorization.authorization_id);
end
if ~isequal(sort(string(authorization.authorized_operations)), sort(blockedPlan.required_authorized_operations))
    error("S12:Playground:AuthorizationOperations", "Authorization operations are missing, extra, or out of scope.");
end
roles = blockedPlan.artifacts;
assertEqual("historical invalid SHA", authorization.historical_invalid_sha256, roles.historical_pre_repair_invalid.sha256);
assertEqual("workspace intermediate SHA", authorization.workspace_intermediate_sha256, roles.workspace_unvalidated_intermediate.sha256);
actualHistorical = s12_sound_playground_sha256(roles.historical_pre_repair_invalid.path);
assertEqual("historical pre-repair invalid changed", actualHistorical, roles.historical_pre_repair_invalid.sha256);
actualWorkspace = s12_sound_playground_sha256(roles.workspace_unvalidated_intermediate.path);
assertEqual("workspace unvalidated intermediate changed", actualWorkspace, roles.workspace_unvalidated_intermediate.sha256);
actualTree = s12_sound_playground_source_tree_sha256();
assertEqual("blocked plan source tree SHA", blockedPlan.source_tree.sha256, actualTree.sha256);
assertEqual("reviewed source tree SHA", authorization.reviewed_source_tree_sha256, actualTree.sha256);
runtimePlan = blockedPlan;
runtimePlan.execution_policy = "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION";
runtimePlan.readiness = "AUTHORIZED_FOR_SINGLE_CONTROLLED_REBUILD";
runtimePlan.authorization = authorization;
runtimePlan.preflight = preflight;
receipt = struct("authorization_id", string(authorization.authorization_id), ...
    "authorized_by", string(authorization.authorized_by), "decision", string(authorization.decision), ...
    "authorization_schema_version", authorizationSchemaVersion(), ...
    "approving_audit_report_sha256", upper(string(authorization.approving_audit_report_sha256)), ...
    "reviewed_package_sha256", upper(string(authorization.reviewed_package_sha256)), ...
    "reviewed_source_tree_sha256", actualTree.sha256, ...
    "preflight_evidence_sha256", upper(string(preflight.sha256)));
end

function value = authorizationSchemaVersion()
value = "s12.playground.controlled-rebuild-authorization.v1";
end

function assertSha(role, value)
if isempty(regexp(char(string(value)), "^[A-Fa-f0-9]{64}$", "once"))
    error("S12:Playground:AuthorizationSha", "Invalid %s SHA-256.", role);
end
end

function assertEqual(role, actual, expected)
s12_sound_playground_require_sha256_equal(actual, expected, string(role) + " mismatch");
end

function assertApprovedFile(role, path, expectedSha)
path = string(path);
if ~isfile(path)
    error("S12:Playground:AuthorizationArtifact", "Approved %s file is absent: %s.", role, path);
end
actualSha = s12_sound_playground_sha256(path);
assertEqual(role + " SHA", actualSha, expectedSha);
end
