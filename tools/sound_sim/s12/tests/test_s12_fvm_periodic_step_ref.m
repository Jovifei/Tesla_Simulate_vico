function tests = test_s12_fvm_periodic_step_ref
%TEST_S12_FVM_PERIODIC_STEP_REF Verify one conservative periodic FVM step.
tests = functiontests(localfunctions);
end

function testUniformStateIsPreserved(testCase)
modelName = openStepModel(testCase);
gamma = 1.4;
state = primitiveToConservative(1.1 * ones(1, 8), ...
    15 * ones(1, 8), 110000 * ones(1, 8), gamma);
result = runStepCase(modelName, state, gamma, 0.02, 1e-3, 0.45);
verifyEqual(testCase, result.state, state, ...
    "RelTol", 1e-12, "AbsTol", 1e-9);
verifyEqual(testCase, result.residual, zeros(1, 3), "AbsTol", 1e-9);
end

function testPeriodicStepConservesAllEulerStates(testCase)
modelName = openStepModel(testCase);
gamma = 1.4;
phase = 2 * pi * (0:7) / 8;
rho = 1 + 0.1 * sin(phase);
velocity = 5 + 2 * cos(phase);
pressure = 1e5 + 5e3 * sin(phase + 0.2);
state = primitiveToConservative(rho, velocity, pressure, gamma);
result = runStepCase(modelName, state, gamma, 0.02, 1e-7, 0.45);

actualResidual = sum(result.state - state, 2).';
scale = max(abs(sum(state, 2).'), 1);
verifyLessThan(testCase, abs(actualResidual) ./ scale, 1e-12);
verifyEqual(testCase, result.residual, actualResidual, "AbsTol", 1e-8);
end

function testCflLimitedSodStepRemainsPositive(testCase)
modelName = openStepModel(testCase);
gamma = 1.4;
rho = [ones(1, 4), 0.125 * ones(1, 4)];
velocity = zeros(1, 8);
pressure = [1e5 * ones(1, 4), 1e4 * ones(1, 4)];
state = primitiveToConservative(rho, velocity, pressure, gamma);
result = runStepCase(modelName, state, gamma, 0.01, 1e-3, 0.45);

nextRho = result.state(1, :);
nextVelocity = result.state(2, :) ./ nextRho;
nextPressure = (gamma - 1) * (result.state(3, :) - ...
    0.5 * nextRho .* nextVelocity.^2);
verifyGreaterThan(testCase, result.dtUsed, 0);
verifyLessThan(testCase, result.dtUsed, 1e-3);
expectedDt = 0.45 * 0.01 / sqrt(gamma * 1e5);
verifyEqual(testCase, result.dtUsed, expectedDt, "RelTol", 1e-12);
verifyGreaterThan(testCase, norm(result.state - state, "fro"), 0);
verifyGreaterThan(testCase, min(nextRho), 0);
verifyGreaterThan(testCase, min(nextPressure), 0);
verifyLessThan(testCase, max(abs(result.residual)), 1e-8);
fprintf("FVM Sod dt us: %.6f; min rho/p: %.6g / %.6g\n", ...
    1e6 * result.dtUsed, min(nextRho), min(nextPressure));
end

function modelName = openStepModel(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "fvm_ref", ...
    "s12_euler_fvm_periodic_step_ref.slx");
assertEqual(testCase, exist(modelFile, "file"), 2, ...
    "The embedded periodic FVM step model must exist.");
modelName = "s12_euler_fvm_periodic_step_ref";
load_system(modelFile);
testCase.addTeardown(@() close_system(modelName, 0));
end

function result = runStepCase(modelName, state, gamma, dx, dtRequest, cfl)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_FVM_State", state);
setParameterValue(workspace, "S12_FVM_Gamma", gamma);
setParameterValue(workspace, "S12_FVM_Dx", dx);
setParameterValue(workspace, "S12_FVM_DtRequest", dtRequest);
setParameterValue(workspace, "S12_FVM_CFL", cfl);
output = sim(modelName);
result.state = squeeze(output.S12_FVMStateNext);
result.dtUsed = output.S12_FVMDtUsed(end);
result.residual = squeeze(output.S12_FVMConservationResidual);
result.residual = result.residual(:).';
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho .* velocity; ...
    pressure / (gamma - 1) + 0.5 * rho .* velocity.^2];
end

function setParameterValue(workspace, name, value)
parameter = workspace.getVariable(name);
parameter.Value = value;
workspace.assignin(name, parameter);
end
