function tests = test_s12_sound_playground_v6_contract
%TEST_S12_SOUND_PLAYGROUND_V6_CONTRACT Future-only helper contracts; no SLX or device access.
tests = functiontests(localfunctions);
end

function test_crash_before_capture(testCase)
[path, cleanup] = writeEvidence(validEvidence("2026-07-26T08:00:00.000+08:00")); %#ok<ASGLU>
evidence = s12_sound_playground_verify_environment_preflight(path, authorization());
verifyEqual(testCase, evidence.status, "ENVIRONMENT_GATE_PASSED_READ_ONLY_EVIDENCE", "crash_before_capture");
end

function test_crash_after_capture(testCase)
record = validEvidence("2026-07-26T10:00:00.000+08:00");
record.captured_at = "2026-07-26T09:00:00.000+08:00";
record.expires_at = "2026-07-26T11:00:00.000+08:00";
[path, cleanup] = writeEvidence(record); %#ok<ASGLU>
verifyError(testCase, @() s12_sound_playground_verify_environment_preflight(path, authorization()), ...
    "S12:Playground:ENVIRONMENT_GATE_FAIL", "crash_after_capture");
end

function test_invalid_crash_timestamp(testCase)
record = validEvidence("not-a-timestamp");
[path, cleanup] = writeEvidence(record); %#ok<ASGLU>
verifyError(testCase, @() s12_sound_playground_verify_environment_preflight(path, authorization()), ...
    "S12:Playground:ENVIRONMENT_GATE_FAIL", "invalid_crash_timestamp");
end

function test_empty_crash_timestamp(testCase)
record = validEvidence("");
record.new_crash_detected = false;
[path, cleanup] = writeEvidence(record); %#ok<ASGLU>
evidence = s12_sound_playground_verify_environment_preflight(path, authorization());
verifyEqual(testCase, evidence.status, "ENVIRONMENT_GATE_PASSED_READ_ONLY_EVIDENCE", "empty_crash_timestamp");
end

function test_run_a_acquires_lock(testCase)
[root, cleanup] = temporaryRoot(); %#ok<ASGLU>
lock = s12_sound_playground_acquire_global_run_lock(fullfile(root, "ACTIVE_RUN_LOCK.json"), lockRecord("run_a", "auth_a"));
verifyEqual(testCase, lock.status, "ACTIVE", "run_a_acquires_lock");
s12_sound_playground_release_global_run_lock(lock, "run_a", "auth_a");
end

function test_run_b_is_locked(testCase)
[root, cleanup] = temporaryRoot(); %#ok<ASGLU>
lockPath = fullfile(root, "ACTIVE_RUN_LOCK.json");
lock = s12_sound_playground_acquire_global_run_lock(lockPath, lockRecord("run_a", "auth_a"));
verifyError(testCase, @() s12_sound_playground_acquire_global_run_lock(lockPath, lockRecord("run_b", "auth_b")), ...
    "S12:Playground:ACTIVE_RUN_LOCKED", "run_b_is_locked");
s12_sound_playground_release_global_run_lock(lock, "run_a", "auth_a");
end

function test_run_a_reentry_is_locked(testCase)
[root, cleanup] = temporaryRoot(); %#ok<ASGLU>
lockPath = fullfile(root, "ACTIVE_RUN_LOCK.json");
lock = s12_sound_playground_acquire_global_run_lock(lockPath, lockRecord("run_a", "auth_a"));
verifyError(testCase, @() s12_sound_playground_acquire_global_run_lock(lockPath, lockRecord("run_a", "auth_a")), ...
    "S12:Playground:ACTIVE_RUN_LOCKED", "run_a_reentry_is_locked");
s12_sound_playground_release_global_run_lock(lock, "run_a", "auth_a");
end

function test_wrong_owner_cannot_release(testCase)
[root, cleanup] = temporaryRoot(); %#ok<ASGLU>
lock = s12_sound_playground_acquire_global_run_lock(fullfile(root, "ACTIVE_RUN_LOCK.json"), lockRecord("run_a", "auth_a"));
verifyError(testCase, @() s12_sound_playground_release_global_run_lock(lock, "run_b", "auth_b"), ...
    "S12:Playground:LockOwnerMismatch", "wrong_owner_cannot_release");
s12_sound_playground_release_global_run_lock(lock, "run_a", "auth_a");
end

function test_cleanup_failure_visible(testCase)
[root, cleanup] = temporaryRoot(); %#ok<ASGLU>
lock = s12_sound_playground_acquire_global_run_lock(fullfile(root, "ACTIVE_RUN_LOCK.json"), lockRecord("run_a", "auth_a"));
releasePath = string(lock.lock_path) + ".releasing.run_a.auth_a.json";
mkdir(releasePath);
verifyError(testCase, @() s12_sound_playground_release_global_run_lock(lock, "run_a", "auth_a"), ...
    "S12:Playground:LockReleaseCleanupFailed", "cleanup_failure_visible");
verifyTrue(testCase, isfile(string(lock.lock_path) + ".release_error.run_a.auth_a.json"));
rmdir(releasePath);
s12_sound_playground_release_global_run_lock(lock, "run_a", "auth_a");
end

function test_output_operation(testCase)
artifact = s12_sound_playground_invoke_stage_operation(@outputOperation, "artifact");
verifyEqual(testCase, artifact.status, "OUTPUT_OPERATION", "output_operation");
end

function test_void_operation(testCase)
artifact = s12_sound_playground_invoke_stage_operation(@voidOperation, "void");
verifyEqual(testCase, artifact.status, "VOID_OPERATION_COMPLETED", "void_operation");
end

function test_operation_throws(testCase)
verifyError(testCase, @() s12_sound_playground_invoke_stage_operation(@throwingOperation, "artifact"), ...
    "S12:Playground:MockOperation", "operation_throws");
end

function test_pcm_validation_pass(testCase)
cases = [caseResult("idle", "SIMULATION_COMPLETED_AND_VALIDATED"), ...
    caseResult("cruise", "SIMULATION_COMPLETED_AND_VALIDATED")];
artifact = s12_sound_playground_require_validated(cases);
verifyEqual(testCase, artifact.status, "PCM_VALIDATION_PASSED", "pcm_validation_pass");
end

function test_pcm_validation_fail(testCase)
cases = [caseResult("idle", "SIMULATION_COMPLETED_AND_VALIDATED"), ...
    caseResult("cruise", "SIMULATION_FAILED")];
verifyError(testCase, @() s12_sound_playground_require_validated(cases), ...
    "S12:Playground:QualificationGate", "pcm_validation_fail");
end

function test_failure_stops_sensitivity(testCase)
orchestrator = fileread(which("s12_sound_playground_controlled_rebuild_and_qualify"));
pcm = strfind(orchestrator, "pcm_validation");
rpm = strfind(orchestrator, "rpm_sensitivity");
guard = orchestrator(pcm(1):rpm(1));
verifyTrue(testCase, contains(guard, "if failed") && contains(guard, "return;"), "failure_stops_sensitivity");
end

function result = outputOperation()
result = struct("status", "OUTPUT_OPERATION");
end

function voidOperation()
end

function throwingOperation()
error("S12:Playground:MockOperation", "Expected throwing operation.");
end

function result = caseResult(scenario, status)
result = struct("scenario", string(scenario), "status", string(status));
end

function value = authorization()
value = struct("allowed_mcp_root_count", 0, "allowed_watchdog_count", 0);
end

function record = validEvidence(crashTime)
record = struct("matlab_process_count", 1, "desktop_pid", 12345, ...
    "desktop_command_line", "MATLAB.exe", "desktop_responding", true, ...
    "mcp_root_count", 0, "watchdog_count", 0, "batch_process_count", 0, ...
    "engine_process_count", 0, "crash_dump_latest_time", string(crashTime), ...
    "new_crash_detected", false, "active_run_lock", false, ...
    "captured_at", "2026-07-26T09:00:00.000+08:00", ...
    "expires_at", "2026-07-27T09:00:00.000+08:00");
end

function record = lockRecord(runId, authorizationId)
record = struct("run_id", string(runId), "authorization_id", string(authorizationId), ...
    "desktop_pid", 12345, "source_tree_sha256", repmat("A", 1, 64), ...
    "audit_zip_sha256", repmat("B", 1, 64), "start_time", "2026-07-26T09:00:00.000+08:00", ...
    "owner_process", "MATLAB_PID_12345");
end

function [path, cleanup] = writeEvidence(record)
[root, cleanup] = temporaryRoot();
path = fullfile(root, "preflight.json");
file = fopen(path, "w");
fprintf(file, "%s\n", jsonencode(record));
fclose(file);
end

function [root, cleanup] = temporaryRoot()
root = tempname;
mkdir(root);
cleanup = onCleanup(@() rmdir(root, "s"));
end
