function result = s12_sound_playground_controlled_rebuild_and_qualify(runId, authorization, execute, preflightEvidencePath, outputRoot)
%S12_SOUND_PLAYGROUND_CONTROLLED_REBUILD_AND_QUALIFY Future one-shot visible-Desktop flow.
% execute=false is the only permitted offline source-review use.

if nargin < 3, execute = false; end
if nargin < 4, preflightEvidencePath = ""; end
if nargin < 5, outputRoot = ""; end
if nargin < 2, authorization = struct(); end
blockedPlan = s12_sound_playground_build_plan(runId);
result = struct("run_id", string(runId), "status", "PLAN_ONLY_NOT_EXECUTED", ...
    "execution_policy", blockedPlan.execution_policy, "progress", s12_sound_playground_empty_progress());
if ~execute
    return;
end
assertControlledOutputRoot(outputRoot, blockedPlan.runtime.transaction_root);
if isfolder(blockedPlan.runtime.transaction_root)
    error("S12:Playground:TransactionExists", "Transaction run_id already exists.");
end
assertImmutableSourceTree(blockedPlan.source_tree.sha256, "before_environment_preflight");
try
    preflight = s12_sound_playground_verify_environment_preflight(preflightEvidencePath, authorization);
catch cause
    result.status = "ENVIRONMENT_GATE_FAILED";
    result.error = errorRecord(cause);
    return;
end
lockRequest = activeRunLockRecord(blockedPlan, authorization, preflight);
try
    lock = s12_sound_playground_acquire_global_run_lock(blockedPlan.runtime.active_run_lock_path, lockRequest);
catch cause
    if strcmp(string(cause.identifier), "S12:Playground:ACTIVE_RUN_LOCKED")
        result.status = "ACTIVE_RUN_LOCKED";
        result.error = errorRecord(cause);
        return;
    end
    rethrow(cause);
end
transactionRoot = blockedPlan.runtime.transaction_root;
mkdir(transactionRoot);
result.status = "CONTROLLED_FLOW_RUNNING";
result = appendCompletedArtifact(result, transactionRoot, "environment_preflight", preflight);
result = appendCompletedArtifact(result, transactionRoot, "global_lock_acquire", lock);
promotion = struct();
qualificationCases = struct([]);

assertImmutableSourceTree(blockedPlan.source_tree.sha256, "before_authorization");
[result, failed, runtimePlan] = runArtifactStage(result, transactionRoot, "authorization_verification", ...
    @() authorizeAndClaim(blockedPlan, authorization, preflight));
if failed, result = finishFailed(result, transactionRoot, "authorization_verification", blockedPlan, promotion, qualificationCases, lock); return; end
assertImmutableSourceTree(runtimePlan.authorization.reviewed_source_tree_sha256, "after_authorization_claim");
[result, failed] = runStage(result, transactionRoot, "evidence_sha_verification", @() verifyArtifacts(runtimePlan));
if failed, result = finishFailed(result, transactionRoot, "evidence_sha_verification", runtimePlan, promotion, qualificationCases, lock); return; end
assertImmutableSourceTree(runtimePlan.authorization.reviewed_source_tree_sha256, "before_temporary_build");
[result, failed, artifact] = runArtifactStage(result, transactionRoot, "temporary_build", @() s12_sound_playground_build_temp(runtimePlan));
if failed, result = finishFailed(result, transactionRoot, "temporary_build", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed] = runStage(result, transactionRoot, "post_build_port_contract", @() s12_sound_playground_inspect_model(artifact, runtimePlan, false));
if failed, result = finishFailed(result, transactionRoot, "post_build_port_contract", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed, compiled] = runArtifactStage(result, transactionRoot, "cold_reload_compile", @() s12_sound_playground_inspect_model(artifact, runtimePlan, true));
if failed, result = finishFailed(result, transactionRoot, "cold_reload_compile", runtimePlan, promotion, qualificationCases, lock); return; end
assertImmutableSourceTree(runtimePlan.authorization.reviewed_source_tree_sha256, "before_promotion");
[result, failed, promotion] = runArtifactStage(result, transactionRoot, "promote_repaired_candidate", @() s12_sound_playground_promote_temp(artifact, compiled, runtimePlan));
if failed, result = finishFailed(result, transactionRoot, "promote_repaired_candidate", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed, idle] = runArtifactStage(result, transactionRoot, "idle_simulation", @() s12_sound_playground_run_simulink_case("idle", runtimePlan, true, fullfile(outputRoot, "idle")));
if failed, result = finishFailed(result, transactionRoot, "idle_simulation", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed, cruise] = runArtifactStage(result, transactionRoot, "cruise_simulation", @() s12_sound_playground_run_simulink_case("cruise", runtimePlan, true, fullfile(outputRoot, "cruise")));
if failed, result = finishFailed(result, transactionRoot, "cruise_simulation", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed, acceleration] = runArtifactStage(result, transactionRoot, "acceleration_simulation", @() s12_sound_playground_run_simulink_case("acceleration", runtimePlan, true, fullfile(outputRoot, "acceleration")));
if failed, result = finishFailed(result, transactionRoot, "acceleration_simulation", runtimePlan, promotion, qualificationCases, lock); return; end
qualificationCases = [idle, cruise, acceleration];
[result, failed, pcmValidation] = runArtifactStage(result, transactionRoot, "pcm_validation", @() requireValidated(qualificationCases));
if failed || ~strcmp(s12_sound_playground_require_text_scalar(pcmValidation.status, "PCM validation status"), "PCM_VALIDATION_PASSED"), result = finishFailed(result, transactionRoot, "pcm_validation", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed] = runStage(result, transactionRoot, "rpm_sensitivity", @() s12_sound_playground_sensitivity_gate(runtimePlan, fullfile(outputRoot, "sensitivity", "rpm"), "rpm"));
if failed, result = finishFailed(result, transactionRoot, "rpm_sensitivity", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed] = runStage(result, transactionRoot, "load_sensitivity", @() s12_sound_playground_sensitivity_gate(runtimePlan, fullfile(outputRoot, "sensitivity", "load"), "load"));
if failed, result = finishFailed(result, transactionRoot, "load_sensitivity", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed] = runStage(result, transactionRoot, "acceleration_sensitivity", @() s12_sound_playground_sensitivity_gate(runtimePlan, fullfile(outputRoot, "sensitivity", "acceleration"), "acceleration"));
if failed, result = finishFailed(result, transactionRoot, "acceleration_sensitivity", runtimePlan, promotion, qualificationCases, lock); return; end
[result, failed] = runStage(result, transactionRoot, "repeatability", @() s12_sound_playground_repeatability_gate(runtimePlan, outputRoot));
if failed, result = finishFailed(result, transactionRoot, "repeatability", runtimePlan, promotion, qualificationCases, lock); return; end
result = appendSkippedStage(result, transactionRoot, "optional_device_smoke_skipped", optionalDeviceSmoke());
result.status = "CONTROLLED_FLOW_PASSED";
result.direct_listening_gate = "INCOMPLETE";
[result, failed, formalQualification] = runArtifactStage(result, transactionRoot, "formal_qualification", ...
    @() s12_sound_playground_finalize_formal_qualification(runtimePlan, promotion, result, qualificationCases));
if failed, result = finishFailed(result, transactionRoot, "formal_qualification", runtimePlan, promotion, qualificationCases, lock); return; end
result.formal_qualification = formalQualification;
assertImmutableSourceTree(runtimePlan.authorization.reviewed_source_tree_sha256, "before_qualification_report");
[result, qualificationReport] = writeQualificationReport(result, transactionRoot, runtimePlan, promotion, qualificationCases);
result = releaseLockAndRecord(result, transactionRoot, lock);
result = writeCompletionReceipt(result, transactionRoot, qualificationReport);
end

function record = activeRunLockRecord(blockedPlan, authorization, preflight)
required = ["authorization_id", "reviewed_package_sha256"];
for index = 1:numel(required)
    if ~isfield(authorization, required(index)) || isEmptyAuthorizationValue(authorization.(required(index)))
        error("S12:Playground:LockAuthorization", "Cannot acquire global lock without %s.", required(index));
    end
end
record = struct("run_id", blockedPlan.run_id, "authorization_id", string(authorization.authorization_id), ...
    "desktop_pid", double(preflight.desktop_pid), "source_tree_sha256", blockedPlan.source_tree.sha256, ...
    "audit_zip_sha256", upper(string(authorization.reviewed_package_sha256)), "start_time", nowString(), ...
    "owner_process", "MATLAB_PID_" + string(matlabProcessID));
end

function value = verifyArtifacts(plan)
roles = plan.artifacts;
s12_sound_playground_require_sha256_equal(s12_sound_playground_sha256(roles.historical_pre_repair_invalid.path), ...
    roles.historical_pre_repair_invalid.sha256, "Historical read-only SLX evidence changed");
s12_sound_playground_require_sha256_equal(s12_sound_playground_sha256(roles.workspace_unvalidated_intermediate.path), ...
    roles.workspace_unvalidated_intermediate.sha256, "Workspace read-only SLX evidence changed");
value = struct("historical_invalid_sha256", roles.historical_pre_repair_invalid.sha256, ...
    "workspace_intermediate_sha256", roles.workspace_unvalidated_intermediate.sha256);
end

function runtimePlan = authorizeAndClaim(blockedPlan, authorization, preflight)
registryRoot = blockedPlan.runtime.authorization_registry_root;
[runtimePlan, receipt] = s12_sound_playground_controlled_rebuild_authorization( ...
    blockedPlan, authorization, usedAuthorizationIds(registryRoot), preflight);
claimAuthorization(registryRoot, runtimePlan.runtime.transaction_root, receipt);
runtimePlan.authorization_receipt = receipt;
end

function claimAuthorization(registryRoot, transactionRoot, receipt)
if isempty(regexp(char(receipt.authorization_id), "^[A-Za-z][A-Za-z0-9_]{0,63}$", "once"))
    error("S12:Playground:AuthorizationId", "Authorization ID must be a filesystem-safe identifier.");
end
if ~isfolder(registryRoot), mkdir(registryRoot); end
path = fullfile(registryRoot, receipt.authorization_id + ".json");
if isfile(path), error("S12:Playground:AuthorizationReuse", "Authorization ID %s is already used.", receipt.authorization_id); end
s12_sound_playground_atomic_write_json(path, receipt, false);
s12_sound_playground_atomic_write_json(fullfile(transactionRoot, "authorization_claim.json"), receipt, false);
end

function ids = usedAuthorizationIds(registryRoot)
if ~isfolder(registryRoot), ids = strings(1, 0); return; end
claims = dir(fullfile(registryRoot, "*.json"));
ids = strings(1, numel(claims));
for index = 1:numel(claims)
    claim = jsondecode(fileread(fullfile(claims(index).folder, claims(index).name)));
    ids(index) = string(claim.authorization_id);
end
end

function assertImmutableSourceTree(expectedSha, boundary)
actual = s12_sound_playground_source_tree_sha256();
s12_sound_playground_require_sha256_equal(actual.sha256, expectedSha, ...
    "Immutable source-tree SHA changed at " + string(boundary));
end

function assertControlledOutputRoot(outputRoot, transactionRoot)
if strlength(string(outputRoot)) == 0
    error("S12:Playground:OutputRootRequired", "outputRoot is mandatory for controlled qualification.");
end
outputPath = char(java.io.File(outputRoot).getCanonicalPath());
transactionPath = char(java.io.File(transactionRoot).getCanonicalPath());
if strcmpi(outputPath, transactionPath) || ~startsWith(outputPath, [transactionPath filesep], "IgnoreCase", true)
    error("S12:Playground:OutputRoot", "outputRoot must be a strict child of the controlled transaction root.");
end
end

function [result, failed] = runStage(result, root, stage, operation)
[result, failed, ~] = runArtifactStage(result, root, stage, operation);
end

function [result, failed, artifact] = runArtifactStage(result, root, stage, operation)
record = stageRecord(result, stage);
artifact = struct();
try
    artifact = s12_sound_playground_invoke_stage_operation(operation, "artifact");
    record = s12_sound_playground_complete_stage_record(record, "COMPLETED", artifact, []);
    failed = false;
catch cause
    record = s12_sound_playground_complete_stage_record(record, "FAILED", struct(), cause);
    failed = true;
end
s12_sound_playground_atomic_write_json(fullfile(root, string(stage) + ".json"), record);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
end

function result = appendCompletedArtifact(result, root, stage, artifact)
record = stageRecord(result, stage);
record = s12_sound_playground_complete_stage_record(record, "COMPLETED", artifact, []);
s12_sound_playground_atomic_write_json(fullfile(root, string(stage) + ".json"), record);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
end

function record = stageRecord(result, stage)
record = s12_sound_playground_stage_record(result.run_id, stage, "RUNNING", struct(), []);
end

function result = finishFailed(result, root, failedStage, plan, promotion, qualificationCases, lock)
result.status = "CONTROLLED_FLOW_FAILED";
result.failed_stage = string(failedStage);
result.direct_listening_gate = "INCOMPLETE";
if hasFormalAfterSha(promotion)
    [result, formalFailed, formalQualification] = runArtifactStage(result, root, "formal_qualification", ...
        @() s12_sound_playground_finalize_formal_qualification(plan, promotion, result, qualificationCases));
    if formalFailed
        result.failed_stage = "formal_qualification";
    else
        result.formal_qualification = formalQualification;
    end
else
    result.formal_qualification = struct("stage", "formal_qualification", ...
        "qualification_status", "NOT_CREATED_NO_PROMOTED_CANDIDATE", "formal_candidate_sha256", "");
end
[result, qualificationReport] = writeQualificationReport(result, root, plan, promotion, qualificationCases);
result = releaseLockAndRecord(result, root, lock);
result = writeCompletionReceipt(result, root, qualificationReport);
end

function [result, report] = writeQualificationReport(result, root, plan, promotion, qualificationCases)
evidence = struct("status", "UNAVAILABLE_NO_FORMAL_CANDIDATE");
if hasFormalAfterSha(promotion)
    evidence = s12_sound_playground_recompute_final_evidence(plan, promotion, qualificationCases);
end
status = "CONTROLLED_FLOW_INCOMPLETE";
if strcmp(s12_sound_playground_require_text_scalar(result.status, "controlled flow status"), "CONTROLLED_FLOW_PASSED") && ...
        strcmp(s12_sound_playground_require_text_scalar(result.direct_listening_gate, "direct listening gate"), "PASSED")
    status = "PASS";
end
path = fullfile(root, "qualification_report.json");
report = struct("run_id", result.run_id, "qualification_status", status, ...
    "formal_qualification", result.formal_qualification, "formal_candidate_sha256", stringOrEmpty(evidence, "formal_candidate_sha256"), ...
    "source_evidence", evidence, "direct_listening_gate", result.direct_listening_gate, ...
    "lock_status", "ACTIVE_PENDING_RELEASE", "stage_records", result.progress, "report_path", string(path));
s12_sound_playground_atomic_write_json(path, report);
report.sha256 = s12_sound_playground_sha256(path);
result.qualification_report = report;
result.global_lock_status = "ACTIVE_PENDING_RELEASE";
record = stageRecord(result, "qualification_report");
record = s12_sound_playground_complete_stage_record(record, "COMPLETED", report, []);
s12_sound_playground_atomic_write_json(fullfile(root, "qualification_report_stage_record.json"), record);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
end

function result = releaseLockAndRecord(result, root, lock)
record = stageRecord(result, "global_lock_release");
try
    releaseArtifact = s12_sound_playground_release_global_run_lock(lock, lock.run_id, lock.authorization_id);
    record = s12_sound_playground_complete_stage_record(record, "COMPLETED", releaseArtifact, []);
    result.global_lock_status = string(record.artifact.status);
catch cause
    record = s12_sound_playground_complete_stage_record(record, "FAILED", struct(), cause);
    result.status = "CONTROLLED_FLOW_INCOMPLETE";
    result.failed_stage = "global_lock_release";
    result.global_lock_status = "RELEASE_FAILED";
end
s12_sound_playground_atomic_write_json(fullfile(root, "global_lock_release.json"), record);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
end

function result = writeCompletionReceipt(result, root, qualificationReport)
status = "CONTROLLED_FLOW_INCOMPLETE";
releaseReceiptSha = "";
if strcmp(s12_sound_playground_require_text_scalar(result.global_lock_status, "global lock status"), "RELEASED") && ...
        isfield(qualificationReport, "qualification_status") && ...
        strcmp(s12_sound_playground_require_text_scalar(qualificationReport.qualification_status, "qualification status"), "PASS")
    status = "RELEASED_AND_COMPLETED";
end
if strcmp(s12_sound_playground_require_text_scalar(result.global_lock_status, "global lock status"), "RELEASED") && ~isempty(result.progress)
    release = result.progress(end);
    if isfield(release, "artifact") && isfield(release.artifact, "release_receipt_sha256")
        releaseReceiptSha = release.artifact.release_receipt_sha256;
    end
end
receipt = struct("run_id", result.run_id, "qualification_report_sha256", qualificationReport.sha256, ...
    "global_lock_release_status", result.global_lock_status, "release_receipt_sha256", releaseReceiptSha, ...
    "overall_completion_status", status, "completed_at", nowString());
s12_sound_playground_atomic_write_json(fullfile(root, "completion_receipt.json"), receipt);
result.completion_receipt = receipt;
if ~strcmp(status, "RELEASED_AND_COMPLETED")
    result.status = "CONTROLLED_FLOW_INCOMPLETE";
end
record = stageRecord(result, "completion_receipt");
record = s12_sound_playground_complete_stage_record(record, "COMPLETED", receipt, []);
s12_sound_playground_atomic_write_json(fullfile(root, "completion_receipt_stage_record.json"), record);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
end

function result = requireValidated(cases)
result = s12_sound_playground_require_validated(cases);
end

function value = optionalDeviceSmoke()
value = struct("status", "SKIPPED_NOT_AUTHORIZED", "direct_listening_gate", "INCOMPLETE", ...
    "reason", "Audio Device Writer smoke is not authorized by this controlled rebuild.");
end

function result = appendSkippedStage(result, root, stage, artifact)
record = stageRecord(result, stage);
record = s12_sound_playground_complete_stage_record(record, "SKIPPED_NOT_AUTHORIZED", artifact, []);
s12_sound_playground_atomic_write_json(fullfile(root, string(stage) + ".json"), record);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
end

function value = stringOrEmpty(record, field)
if isstruct(record) && isfield(record, field)
    value = string(record.(field));
else
    value = "";
end
end

function value = errorRecord(cause)
value = struct("identifier", string(cause.identifier), "message", string(cause.message), ...
    "report", string(getReport(cause, "extended", "hyperlinks", "off")));
end

function value = isEmptyAuthorizationValue(value)
if isempty(value)
    value = true;
    return;
end
if ischar(value) || isstring(value)
    value = all(strlength(string(value)) < 1);
    return;
end
value = false;
end

function value = hasFormalAfterSha(promotion)
value = isstruct(promotion) && isscalar(promotion) && isfield(promotion, "formal_after_sha256") && ...
    s12_sound_playground_sha256_equal(promotion.formal_after_sha256, promotion.formal_after_sha256);
end

function value = nowString()
value = string(datetime("now", "Format", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"));
end
