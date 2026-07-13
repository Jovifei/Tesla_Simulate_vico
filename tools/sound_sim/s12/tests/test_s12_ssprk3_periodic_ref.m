function tests = test_s12_ssprk3_periodic_ref
%TEST_S12_SSPRK3_PERIODIC_REF Verify periodic SSP-RK3 composition.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
testCase.TestData.S12Root = s12Root;
end

function testStageModelImplementsCanonicalWeights(testCase)
modelName = openStageModel(testCase);
baseState = reshape(1:24, 3, 8);
eulerState = baseState + reshape(linspace(-0.2, 0.3, 24), 3, 8);

verifyEqual(testCase, runStage(modelName, baseState, eulerState, 1), ...
    eulerState, "AbsTol", 1e-14);
verifyEqual(testCase, runStage(modelName, baseState, eulerState, 2), ...
    0.75 * baseState + 0.25 * eulerState, "AbsTol", 1e-14);
verifyEqual(testCase, runStage(modelName, baseState, eulerState, 3), ...
    baseState / 3 + 2 * eulerState / 3, "AbsTol", 1e-14);
end

function testAdapterPreservesUniformPeriodicState(testCase)
gamma = 1.4;
cellCount = 8;
dx = 1 / cellCount;
dt = 0.01;
stepCount = 4;
rho = 1.1 * ones(1, cellCount);
velocity = 0.2 * ones(1, cellCount);
pressure = ones(1, cellCount);
initialState = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];

result = s12_run_periodic_ssprk3(initialState, gamma, dx, dt, ...
    stepCount, 0.45);

verifyEqual(testCase, result.final_state, initialState, ...
    "RelTol", 1e-12, "AbsTol", 1e-12);
verifyEqual(testCase, result.requested_dt, dt * ones(1, 3 * stepCount));
verifyEqual(testCase, result.used_dt, result.requested_dt, ...
    "RelTol", 1e-12, "AbsTol", 1e-14);
verifyLessThanOrEqual(testCase, max(abs(result.conservation_residual)), 1e-12);
verifyEqual(testCase, result.boundary, "periodic");
end

function modelName = openStageModel(testCase)
modelFile = fullfile(testCase.TestData.S12Root, "models", "fvm_ref", ...
    "s12_euler_ssprk3_periodic_ref.slx");
assertTrue(testCase, isfile(modelFile), ...
    "The periodic SSP-RK3 stage model must exist.");
modelName = "s12_euler_ssprk3_periodic_ref";
load_system(modelFile);
testCase.addTeardown(@() close_system(modelName, 0));
end

function state = runStage(modelName, baseState, eulerState, stageIndex)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_PRK3_BaseState", baseState);
setParameterValue(workspace, "S12_PRK3_EulerState", eulerState);
setParameterValue(workspace, "S12_PRK3_StageIndex", stageIndex);
output = sim(modelName);
state = squeeze(output.S12_PRK3StageState);
end

function setParameterValue(workspace, name, value)
parameter = workspace.getVariable(name);
parameter.Value = value;
workspace.assignin(name, parameter);
end
