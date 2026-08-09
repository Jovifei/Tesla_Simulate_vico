function tests = test_s12_sound_playground_runtime_preflight
%TEST_S12_SOUND_PLAYGROUND_RUNTIME_PREFLIGHT Exercise Runtime Proof preflight contracts.

tests = functiontests(localfunctions);
end

function setupOnce(testCase)
playground = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground");
addpath(playground);
testCase.TestData.playground = playground;
end

function teardownOnce(testCase)
rmpath(testCase.TestData.playground);
end

function testStageProgressUsesStableTypedRecords(testCase)
progress = s12_sound_playground_empty_progress();
first = s12_sound_playground_stage_record("run-1", "temporary_build", "PASSED", ...
    struct("path", "candidate.slx"), []);
secondCause = MException("S12:Playground:ExpectedFailure", "expected failure");
second = s12_sound_playground_stage_record("run-1", "update_diagram", "FAILED", struct(), secondCause);

progress = s12_sound_playground_append_stage_record(progress, first);
progress = s12_sound_playground_append_stage_record(progress, second);

expectedFields = ["run_id", "stage", "status", "started_at", "ended_at", "artifact", ...
    "error_identifier", "error_message", "error_stack"];
verifyEqual(testCase, string(fieldnames(progress)).', expectedFields);
verifyEqual(testCase, numel(progress), 2);
verifyEqual(testCase, progress(1).status, "PASSED");
verifyEqual(testCase, progress(2).status, "FAILED");
verifyEqual(testCase, progress(2).error_identifier, "S12:Playground:ExpectedFailure");
verifyNotEmpty(testCase, progress(2).error_stack);
end

function testConditionAuditReportsNoUnsafeWholeTextConditions(testCase)
playground = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground");
audit = s12_sound_playground_condition_audit(playground);

verifyGreaterThan(testCase, audit.conditional_expressions_audited, 0);
verifyEqual(testCase, audit.unsafe_whole_text_comparisons, 0);
verifyEqual(testCase, audit.non_scalar_condition_risks, 0);
end
