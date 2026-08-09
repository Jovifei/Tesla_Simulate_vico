function plan = s12_sound_playground_build_plan(runId)
%S12_SOUND_PLAYGROUND_BUILD_PLAN Create a permanently blocked base plan.

if nargin ~= 1 || strlength(string(runId)) == 0
    error("S12:Playground:RunIdRequired", "A caller-supplied unique run ID is required.");
end
runId = string(runId);
if isempty(regexp(char(runId), "^[A-Za-z][A-Za-z0-9_]{0,47}$", "once"))
    error("S12:Playground:RunId", "Run ID must be an identifier of at most 48 characters.");
end
root = string(fileparts(mfilename("fullpath")));
roles = s12_sound_playground_port_contract().artifacts;
temporaryName = "S12_Sound_Playground_repaired_candidate_tmp_" + runId;
runtime = s12_sound_playground_runtime_paths(runId);
temporaryRoot = runtime.temporary_root;
plan.version = "v0.9-offline-controlled-rebuild-contract";
plan.run_id = runId;
plan.source_root = root;
plan.source_tree = s12_sound_playground_source_tree_sha256();
plan.runtime = runtime;
plan.artifacts = roles;
plan.temporary = struct("root", temporaryRoot, "model_name", temporaryName, ...
    "model_path", fullfile(temporaryRoot, temporaryName + ".slx"), ...
    "failure_report_path", fullfile(temporaryRoot, "failure_report.json"));
plan.formal = roles.formal_repaired_candidate;
plan.formal.model_name = "S12_Sound_Playground_repaired_candidate";
plan.port_contract = s12_sound_playground_port_contract();
plan.signal_contract = s12_sound_playground_signal_contract();
plan.readiness = "NOT_READY_FOR_CONTROLLED_REBUILD";
plan.execution_policy = "BLOCKED_PENDING_EXPLICIT_AUTHORIZATION_AND_INDEPENDENT_REVIEW";
plan.required_authorized_operations = ["environment_preflight", "temporary_build", "structure_inspection", ...
    "compile", "promotion", "qualification_simulation", "sensitivity", "repeatability", "final_report"];
plan.idempotency = struct("reused_run_id", "REFUSED", "authorization_reuse", "REFUSED", ...
    "default_invocation_formal_mutation", false);
end
