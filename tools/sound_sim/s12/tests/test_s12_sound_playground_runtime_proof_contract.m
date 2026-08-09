function tests = test_s12_sound_playground_runtime_proof_contract
%TEST_S12_SOUND_PLAYGROUND_RUNTIME_PROOF_CONTRACT Future existing-session tests.

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

function test_plan_is_temporary_only(testCase)
plan = s12_sound_playground_runtime_proof_plan("runtimeproofcontract");
verifyEqual(testCase, plan.execution_policy, "MANUAL_RUNTIME_REQUIRED");
verifyEqual(testCase, plan.candidate.model_name, "S12_Sound_Playground_RUNTIME_PROOF_TMP");
verifyEqual(testCase, plan.runtime.transaction_root, plan.runtime.runtime_root);
verifyEqual(testCase, plan.runtime.temporary_root, plan.runtime.runtime_root);
verifyTrue(testCase, endsWith(plan.runtime.runtime_base, fullfile("runtime", "s12-playground-runtime-proof")));
verifyFalse(testCase, isfield(plan, "formal"));
verifyFalse(testCase, isfield(plan, "promotion"));
end

function test_dry_run_is_non_mutating(testCase)
result = s12_sound_playground_runtime_proof("runtimeproofdryrun", false, "");
verifyEqual(testCase, result.status, "MANUAL_RUNTIME_REQUIRED");
verifyEqual(testCase, result.runtime_executed, false);
verifyEmpty(testCase, result.progress);
end

function test_device_smoke_duration_is_bounded(testCase)
plan = s12_sound_playground_runtime_proof_plan("runtimeproofduration");
verifyError(testCase, @() s12_sound_playground_device_smoke(plan, 0.5, plan.runtime.case_output_root), ...
    "S12:Playground:DeviceSmokeDuration");
verifyError(testCase, @() s12_sound_playground_device_smoke(plan, 4, plan.runtime.case_output_root), ...
    "S12:Playground:DeviceSmokeDuration");
end

function test_scenario_workspace_round_trip(testCase)
scenario = s12_sound_playground_scenario_source("idle");
values = reshape(scenario.workspace_signal.signals.values, 18, scenario.frame_count);
verifyEqual(testCase, values, scenario.configuration_frames);
verifyEqual(testCase, scenario.workspace_signal.signals.dimensions, [18 1]);
end

function test_compile_gate_prepares_model_workspace(testCase)
model = "S12_Runtime_Proof_Workspace_Test";
if bdIsLoaded(model)
    close_system(model, 0);
end
modelLease = onCleanup(@() closeIfLoaded(model));
new_system(model);

prepared = s12_sound_playground_prepare_model_workspace_for_compile(model);
workspace = get_param(model, "ModelWorkspace");
scenarioFrames = evalin(workspace, "s12_playground_scenario_frames");

verifyEqual(testCase, prepared.status, "COMPILE_SCENARIO_PREPARED");
verifyEqual(testCase, prepared.scenario, "idle");
verifyEqual(testCase, scenarioFrames.signals.dimensions, [18 1]);
verifySize(testCase, scenarioFrames.signals.values, [18 1 prepared.frame_count]);
verifyTrue(testCase, all(isfinite(scenarioFrames.signals.values), "all"));
end

function test_sensitivity_pairs_hold_other_controls_constant(testCase)
signal = s12_sound_playground_signal_contract();
variables = ["rpm", "load", "acceleration"];
baseValues = [800, 0.2, 0];
variedValues = [3000, 0.8, 2];
controlIndices = [signal.indices.rpm, signal.indices.load, ...
    signal.indices.acceleration, signal.indices.throttle];

for index = 1:numel(variables)
    variable = variables(index);
    base = s12_sound_playground_controlled_sensitivity_scenario(variable, baseValues(index));
    varied = s12_sound_playground_controlled_sensitivity_scenario(variable, variedValues(index));
    baseFrames = reshape(base.workspace_signal.signals.values, 18, base.frame_count);
    variedFrames = reshape(varied.workspace_signal.signals.values, 18, varied.frame_count);
    changed = find(any(baseFrames ~= variedFrames, 2));
    targetIndex = signal.indices.(char(variable));

    verifyEqual(testCase, changed, targetIndex);
    for controlIndex = setdiff(controlIndices, targetIndex)
        verifyTrue(testCase, all(baseFrames(controlIndex, :) == baseFrames(controlIndex, 1)));
        verifyEqual(testCase, baseFrames(controlIndex, :), variedFrames(controlIndex, :));
    end
end
end

function closeIfLoaded(model)
if bdIsLoaded(model)
    close_system(model, 0);
end
end
