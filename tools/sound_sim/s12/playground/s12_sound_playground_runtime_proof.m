function result = s12_sound_playground_runtime_proof(runId, execute, outputRoot, preflight)
%S12_SOUND_PLAYGROUND_RUNTIME_PROOF One-shot proof in a user-started existing session.

if nargin < 2, execute = false; end
if nargin < 3, outputRoot = ""; end
if nargin < 4, preflight = struct(); end
plan = s12_sound_playground_runtime_proof_plan(runId);
result = struct("run_id", string(runId), "status", "MANUAL_RUNTIME_REQUIRED", ...
    "runtime_executed", false, "candidate", plan.candidate, "progress", s12_sound_playground_empty_progress(), ...
    "runtime_only_unknowns", ["build", "update_diagram", "compile", "simulation", ...
        "pcm", "sensitivity", "repeatability", "device_audio_smoke"]);
if ~execute
    return;
end

assertOutputRoot(outputRoot, plan.runtime.transaction_root);
if isfolder(plan.runtime.transaction_root)
    error("S12:Playground:TransactionExists", "Runtime Proof run ID already exists.");
end
if isempty(fieldnames(preflight))
    preflight = s12_sound_playground_runtime_proof_preflight(plan);
end
result.preflight = preflight;
mkdir(plan.runtime.transaction_root);
plan.execution_policy = "EXISTING_SESSION_RUNTIME_PROOF";
result.status = "RUNTIME_PROOF_RUNNING";
result.runtime_executed = true;

[result, artifact] = runtimeStage(result, plan, "temporary_build", ...
    @() s12_sound_playground_build_temp(plan));
plan.candidate = struct("model_name", artifact.model_name, "path", artifact.model_path, ...
    "role", "RUN_SPECIFIC_TEMPORARY_CANDIDATE", "mutable", true);
[result, ~] = runtimeStage(result, plan, "port_contract", ...
    @() s12_sound_playground_inspect_model(artifact, plan, false));
[result, ~] = runtimeStage(result, plan, "cold_reload", ...
    @() s12_sound_playground_runtime_proof_model_gate(artifact, plan, "cold_reload"));
[result, ~] = runtimeStage(result, plan, "update_diagram", ...
    @() s12_sound_playground_runtime_proof_model_gate(artifact, plan, "update_diagram"));
[result, ~] = runtimeStage(result, plan, "active_compile_dimension_readback", ...
    @() s12_sound_playground_runtime_proof_model_gate(artifact, plan, "active_compile_dimension_readback"));
[result, idle] = runtimeStage(result, plan, "idle_simulation", ...
    @() s12_sound_playground_run_simulink_case("idle", plan, true, fullfile(outputRoot, "idle")));
[result, cruise] = runtimeStage(result, plan, "cruise_simulation", ...
    @() s12_sound_playground_run_simulink_case("cruise", plan, true, fullfile(outputRoot, "cruise")));
[result, acceleration] = runtimeStage(result, plan, "acceleration_simulation", ...
    @() s12_sound_playground_run_simulink_case("acceleration", plan, true, fullfile(outputRoot, "acceleration")));
[result, ~] = runtimeStage(result, plan, "pcm_validation", ...
    @() s12_sound_playground_require_validated([idle, cruise, acceleration]));
[result, ~] = runtimeStage(result, plan, "parameter_sensitivity", ...
    @() runtimeProofParameterSensitivity(plan, fullfile(outputRoot, "sensitivity")));
[result, ~] = runtimeStage(result, plan, "repeatability", ...
    @() s12_sound_playground_repeatability_gate(plan, fullfile(outputRoot, "repeatability")));
[result, device] = runtimeStage(result, plan, "device_audio_smoke", ...
    @() s12_sound_playground_device_smoke(plan, 2, fullfile(outputRoot, "device_smoke")));
result.status = "RUNTIME_PROOF_PASSED";
result.runtime_only_unknowns = strings(1, 0);
result.device_playback_executed = device.device_playback_executed;
result.user_audible_confirmation = device.user_audible_confirmation;
result = writeRuntimeProofReport(result, plan);
end

function result = runtimeProofParameterSensitivity(plan, outputRoot)
result = struct( ...
    "rpm", s12_sound_playground_sensitivity_gate(plan, fullfile(outputRoot, "rpm"), "rpm"), ...
    "load", s12_sound_playground_sensitivity_gate(plan, fullfile(outputRoot, "load"), "load"), ...
    "acceleration", s12_sound_playground_sensitivity_gate(plan, fullfile(outputRoot, "acceleration"), "acceleration"));
end

function [result, artifact] = runtimeStage(result, plan, stage, operation)
record = s12_sound_playground_stage_record(result.run_id, stage, "RUNNING", struct(), []);
try
    artifact = operation();
    record = s12_sound_playground_complete_stage_record(record, "PASSED", artifact, []);
catch cause
    artifact = struct();
    record = s12_sound_playground_complete_stage_record(record, "FAILED", artifact, cause);
    result.status = "RUNTIME_PROOF_FAILED";
    result.failed_stage = string(stage);
    result.progress = s12_sound_playground_append_stage_record(result.progress, record);
    s12_sound_playground_atomic_write_json(fullfile(plan.runtime.transaction_root, string(stage) + ".json"), record);
    writeRuntimeProofReport(result, plan);
    rethrow(cause);
end
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
s12_sound_playground_atomic_write_json(fullfile(plan.runtime.transaction_root, string(stage) + ".json"), record);
end

function result = writeRuntimeProofReport(result, plan)
recordStatus = "PASSED";
if ~strcmp(result.status, "RUNTIME_PROOF_PASSED")
    recordStatus = "FAILED";
end
record = s12_sound_playground_stage_record(result.run_id, "runtime_proof_report", recordStatus, ...
    struct("path", plan.runtime_proof_report_path), []);
record = s12_sound_playground_complete_stage_record(record, recordStatus, record.artifact, []);
result.progress = s12_sound_playground_append_stage_record(result.progress, record);
if isfield(result, "preflight")
    canonical = plan.artifacts.workspace_unvalidated_intermediate;
    result.preflight.canonical_sha256_after = upper(s12_sound_playground_sha256(canonical.path));
end
result.report = struct("status", result.status, "runtime_executed", result.runtime_executed, ...
    "candidate_path", plan.candidate.path, "candidate_sha256", currentCandidateSha(plan), ...
    "device_playback_executed", valueOrFalse(result, "device_playback_executed"), ...
    "user_audible_confirmation", valueOrPending(result, "user_audible_confirmation"), ...
    "preflight", valueOrEmptyStruct(result, "preflight"), ...
    "synthetic", true, "calibrated", false, "vehicle_qualified", false, ...
    "stage_records", result.progress);
s12_sound_playground_atomic_write_json(plan.runtime_proof_report_path, result);
end

function value = valueOrEmptyStruct(result, field)
value = struct();
if isfield(result, field), value = result.(field); end
end

function value = currentCandidateSha(plan)
value = "";
if isfile(plan.candidate.path)
    value = s12_sound_playground_sha256(plan.candidate.path);
end
end

function value = valueOrFalse(result, field)
value = false;
if isfield(result, field), value = logical(result.(field)); end
end

function value = valueOrPending(result, field)
value = "pending";
if isfield(result, field), value = string(result.(field)); end
end

function assertOutputRoot(outputRoot, transactionRoot)
if strlength(string(outputRoot)) == 0
    error("S12:Playground:OutputRootRequired", "Runtime Proof outputRoot is required.");
end
outputPath = char(java.io.File(outputRoot).getCanonicalPath());
transactionPath = char(java.io.File(transactionRoot).getCanonicalPath());
if strcmpi(outputPath, transactionPath) || ~startsWith(outputPath, [transactionPath filesep], "IgnoreCase", true)
    error("S12:Playground:OutputRoot", "Runtime Proof outputRoot must be a strict transaction child.");
end
end
