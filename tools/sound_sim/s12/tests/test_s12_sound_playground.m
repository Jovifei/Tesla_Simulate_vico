function tests = test_s12_sound_playground
%TEST_S12_SOUND_PLAYGROUND Direct-reference tests; no SLX execution.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root, "playground"));
testCase.addTeardown(@() rmpath(fullfile(s12Root, "playground")));
end

function testBuilderEntryIsPlanOnlyByDefault(testCase)
result = s12_sound_playground_build("static_contract_test");
verifyEqual(testCase, result.status, "PLAN_ONLY_NOT_EXECUTED");
verifyEqual(testCase, result.plan.artifacts.workspace_unvalidated_intermediate.role, "WORKSPACE_UNVALIDATED_INTERMEDIATE");
verifyEqual(testCase, result.plan.readiness, "NOT_READY_FOR_CONTROLLED_REBUILD");
verifyNotEqual(testCase, result.plan.formal.path, result.plan.artifacts.workspace_unvalidated_intermediate.path);
end

function testDirectReferenceIsContinuousAndDeterministic(testCase)
overrides = struct("gain_db", -18, "pipe_length_m", 1.25);
[pcmA, traceA] = s12_sound_playground_render_case("acceleration", 0.20, overrides);
[pcmB, traceB] = s12_sound_playground_render_case("acceleration", 0.20, overrides);
verifyEqual(testCase, pcmA, pcmB);
verifyEqual(testCase, traceA.rpm, traceB.rpm);
verifySize(testCase, pcmA, [10 * 960, 2]);
verifyFalse(testCase, any(isnan(pcmA), "all"));
verifyLessThan(testCase, max(abs(pcmA), [], "all"), 1);
end

function testDirectReferenceExportDeclaresItsEvidenceScope(testCase)
firstDirectory = tempname;
secondDirectory = tempname;
first = s12_sound_playground_run_case("cruise", 0.20, firstDirectory, struct("gain_db", -18));
second = s12_sound_playground_run_case("cruise", 0.20, secondDirectory, struct("gain_db", -18));
verifyEqual(testCase, first.wav_sha256, second.wav_sha256);
verifyEqual(testCase, first.evidence_scope, "DIRECT_REFERENCE_ONLY");
metadata = jsondecode(fileread(fullfile(firstDirectory, "metadata.json")));
verifyEqual(testCase, metadata.source, "direct_matlab_reference");
end
