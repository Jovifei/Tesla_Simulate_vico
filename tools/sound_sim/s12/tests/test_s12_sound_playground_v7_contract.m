function tests = test_s12_sound_playground_v7_contract
%TEST_S12_SOUND_PLAYGROUND_V7_CONTRACT Review-ordinal-independent authorization contracts.

tests = functiontests(localfunctions);
end

function test_pending_external_authorization_is_rejected(testCase)
authorization = baseAuthorization();
authorization.decision = "PENDING_EXTERNAL_INDEPENDENT_APPROVAL";
verifyError(testCase, @() authorize(authorization, "v7pending"), ...
    "S12:Playground:AuthorizationDecision");
end

function test_wrong_schema_is_rejected_without_review_ordinal_logic(testCase)
authorization = baseAuthorization();
authorization.authorization_schema_version = "s12.playground.controlled-rebuild-authorization.invalid";
verifyError(testCase, @() authorize(authorization, "v7schema"), ...
    "S12:Playground:AuthorizationSchema");
end

function test_package_source_identity_mismatch_is_rejected(testCase)
[root, cleanup] = temporaryRoot(); %#ok<ASGLU>
zipPath = writeIdentityZip(root, string(repmat('B', 1, 64)));
verifyError(testCase, @() s12_sound_playground_verify_audit_zip_source_identity( ...
    zipPath, string(repmat('A', 1, 64)), string(repmat('A', 1, 64))), ...
    "S12:Playground:AuthorizationMismatch");
end

function authorize(authorization, runId)
s12_sound_playground_controlled_rebuild_authorization( ...
    s12_sound_playground_build_plan(runId), authorization, strings(1, 0), preflight());
end

function authorization = baseAuthorization()
tree = s12_sound_playground_source_tree_sha256();
roles = s12_sound_playground_port_contract().artifacts;
authorization = struct( ...
    "decision", "READY_FOR_CONTROLLED_REBUILD", ...
    "authorization_schema_version", "s12.playground.controlled-rebuild-authorization.v1", ...
    "reviewed_package_path", "not_reached.zip", "reviewed_package_sha256", string(repmat('A', 1, 64)), ...
    "reviewed_source_tree_sha256", tree.sha256, ...
    "approving_audit_report_path", "not_reached.md", ...
    "approving_audit_report_sha256", string(repmat('B', 1, 64)), ...
    "historical_invalid_sha256", roles.historical_pre_repair_invalid.sha256, ...
    "workspace_intermediate_sha256", roles.workspace_unvalidated_intermediate.sha256, ...
    "preflight_evidence_sha256", string(repmat('C', 1, 64)), ...
    "allowed_mcp_root_count", 0, "allowed_watchdog_count", 0, ...
    "authorized_operations", s12_sound_playground_build_plan("v7operationcheck").required_authorized_operations, ...
    "authorized_by", "test", "authorization_id", "v7_test_authorization");
end

function value = preflight()
value = struct("sha256", string(repmat('C', 1, 64)));
end

function zipPath = writeIdentityZip(root, sourceSha)
metadata = fullfile(root, "metadata");
mkdir(metadata);
manifest = fullfile(metadata, "source_identity_manifest.json");
s12_sound_playground_atomic_write_json(manifest, struct("immutable_source_sha256", sourceSha));
zipPath = fullfile(root, "identity.zip");
zip(zipPath, metadata, root);
end

function [root, cleanup] = temporaryRoot()
root = tempname;
mkdir(root);
cleanup = onCleanup(@() rmdir(root, "s"));
end
