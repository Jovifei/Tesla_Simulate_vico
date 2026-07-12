function tests = test_c63_coupled_blowdown_ref
%TEST_C63_COUPLED_BLOWDOWN_REF Verify cylinder-to-valve state coupling.
tests = functiontests(localfunctions);
end

function testMassEnergyAndValveCoupling(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "cylinder_ref", ...
    "c63_cylinder_blowdown_ref.slx");
verifyEqual(testCase, exist(modelFile, "file"), 2, ...
    "The coupled cylinder blowdown model must exist.");

modelName = "c63_cylinder_blowdown_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));
output = sim(modelName);

time = output.S12_BlowdownTime;
angle = output.S12_BlowdownAngle;
mass = output.S12_CylinderMass;
temperature = output.S12_CoupledTemperature;
pressure = output.S12_CoupledPressure;
massFlow = output.S12_ExhaustMassFlow;
area = output.S12_CoupledValveArea;
gamma = output.S12_MixtureGamma;
gasConstant = output.S12_MixtureGasConstant;

signals = {time, angle, mass, temperature, pressure, massFlow, ...
    area, gamma, gasConstant};
for k = 1:numel(signals)
    verifyTrue(testCase, all(isfinite(signals{k})));
end

beforeEvo = angle < 129.5;
afterEvo = angle > 135 & area > 0;
verifyLessThan(testCase, max(abs(massFlow(beforeEvo))), 1e-10);
verifyEqual(testCase, max(mass(beforeEvo)) - min(mass(beforeEvo)), ...
    0, "AbsTol", 1e-10);
verifyGreaterThan(testCase, max(massFlow(afterEvo)), 0.05);
verifyLessThan(testCase, mass(end), mass(1));
verifyGreaterThan(testCase, mass(end), 0);

expelledByState = mass(1) - mass(end);
expelledByFlow = trapz(time, massFlow);
verifyEqual(testCase, expelledByFlow, expelledByState, "RelTol", 2e-3);

[peakPressure, peakIndex] = max(pressure);
verifyGreaterThan(testCase, peakPressure, 4e6);
verifyLessThan(testCase, peakPressure, 15e6);
verifyGreaterThan(testCase, angle(peakIndex), -5);
verifyLessThan(testCase, angle(peakIndex), 35);
verifyGreaterThan(testCase, max(temperature), 1500);
verifyLessThan(testCase, max(temperature), 3300);
verifyGreaterThan(testCase, min(gamma), 1.18);
verifyLessThan(testCase, max(gamma), 1.42);
verifyGreaterThan(testCase, min(gasConstant), 285);
verifyLessThan(testCase, max(gasConstant), 295);
clear cleanup
end
