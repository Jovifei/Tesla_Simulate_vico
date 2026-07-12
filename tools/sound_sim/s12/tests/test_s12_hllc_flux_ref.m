function tests = test_s12_hllc_flux_ref
%TEST_S12_HLLC_FLUX_REF Verify the embedded Simulink HLLC flux component.
tests = functiontests(localfunctions);
end

function testUniformStateMatchesAnalyticEulerFlux(testCase)
modelName = openFluxModel(testCase);
state = [1.2, 30, 101325];
[flux, speeds] = runFluxCase(modelName, state, state, 1.4);

rho = state(1);
velocity = state(2);
pressure = state(3);
totalEnergy = pressure / (1.4 - 1) + 0.5 * rho * velocity^2;
expected = [rho * velocity, rho * velocity^2 + pressure, ...
    velocity * (totalEnergy + pressure)];
verifyEqual(testCase, flux, expected, "RelTol", 1e-10);
verifyTrue(testCase, all(isfinite(speeds)));
end

function testStationaryContactIsPreserved(testCase)
modelName = openFluxModel(testCase);
[flux, speeds] = runFluxCase(modelName, [1.0, 0, 1e5], ...
    [0.125, 0, 1e5], 1.4);
verifyEqual(testCase, flux, [0, 1e5, 0], "AbsTol", 1e-9);
verifyLessThan(testCase, speeds(1), speeds(2));
verifyLessThan(testCase, speeds(2), speeds(3));
end

function testMirrorStatesGiveMirroredFlux(testCase)
modelName = openFluxModel(testCase);
left = [1.0, 20, 1e5];
right = [0.8, -5, 8e4];
[forwardFlux, forwardSpeeds] = runFluxCase(modelName, left, right, 1.4);
mirroredLeft = [right(1), -right(2), right(3)];
mirroredRight = [left(1), -left(2), left(3)];
[mirrorFlux, mirrorSpeeds] = runFluxCase(modelName, ...
    mirroredLeft, mirroredRight, 1.4);

verifyEqual(testCase, mirrorFlux, ...
    [-forwardFlux(1), forwardFlux(2), -forwardFlux(3)], ...
    "RelTol", 1e-10, "AbsTol", 1e-8);
verifyEqual(testCase, mirrorSpeeds, ...
    [-forwardSpeeds(3), -forwardSpeeds(2), -forwardSpeeds(1)], ...
    "RelTol", 1e-10, "AbsTol", 1e-10);
end

function modelName = openFluxModel(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "fvm_ref", ...
    "s12_euler_hllc_flux_ref.slx");
assertEqual(testCase, exist(modelFile, "file"), 2, ...
    "The embedded HLLC flux reference model must exist.");
modelName = "s12_euler_hllc_flux_ref";
load_system(modelFile);
testCase.addTeardown(@() close_system(modelName, 0));
end

function [flux, speeds] = runFluxCase(modelName, left, right, gamma)
workspace = get_param(modelName, "ModelWorkspace");
setParameterValue(workspace, "S12_HLLC_RhoL", left(1));
setParameterValue(workspace, "S12_HLLC_UL", left(2));
setParameterValue(workspace, "S12_HLLC_PL", left(3));
setParameterValue(workspace, "S12_HLLC_RhoR", right(1));
setParameterValue(workspace, "S12_HLLC_UR", right(2));
setParameterValue(workspace, "S12_HLLC_PR", right(3));
setParameterValue(workspace, "S12_HLLC_Gamma", gamma);
output = sim(modelName);
flux = output.S12_HLLCFlux(end, :);
speeds = output.S12_HLLCWaveSpeeds(end, :);
end

function setParameterValue(workspace, name, value)
parameter = workspace.getVariable(name);
parameter.Value = value;
workspace.assignin(name, parameter);
end
