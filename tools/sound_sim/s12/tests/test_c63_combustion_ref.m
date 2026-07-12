function tests = test_c63_combustion_ref
%TEST_C63_COMBUSTION_REF Verify the closed-cylinder S12 combustion model.
tests = functiontests(localfunctions);
end

function testClosedCyclePhysics(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
modelFile = fullfile(root, "models", "cylinder_ref", ...
    "c63_cylinder_combustion_ref.slx");
verifyEqual(testCase, exist(modelFile, "file"), 2, ...
    "The closed-cylinder combustion model must exist.");

modelName = "c63_cylinder_combustion_ref";
load_system(modelFile);
cleanup = onCleanup(@() close_system(modelName, 0));
output = sim(modelName);

time = output.S12_Time;
angle = output.S12_CrankAngle;
volume = output.S12_CombustionVolume;
pressure = output.S12_CombustionPressure;
temperature = output.S12_CombustionTemperature;
burned = output.S12_BurnedMassFraction;
heatRate = output.S12_HeatReleaseRate;
wallHeatRate = output.S12_WallHeatRate;

signals = {time, angle, volume, pressure, temperature, burned, ...
    heatRate, wallHeatRate};
verifyGreaterThan(testCase, numel(time), 1000);
for k = 1:numel(signals)
    verifyTrue(testCase, all(isfinite(signals{k})));
end

verifyEqual(testCase, max(volume) / min(volume), 11.3, "RelTol", 2e-4);
verifyGreaterThanOrEqual(testCase, min(diff(burned)), -1e-10);
verifyLessThan(testCase, burned(1), 1e-6);
verifyGreaterThan(testCase, burned(end), 0.98);

[peakPressure, peakIndex] = max(pressure);
verifyGreaterThan(testCase, peakPressure, 4e6);
verifyLessThan(testCase, peakPressure, 15e6);
verifyGreaterThan(testCase, angle(peakIndex), -5);
verifyLessThan(testCase, angle(peakIndex), 35);
verifyGreaterThan(testCase, max(temperature), 1500);
verifyLessThan(testCase, max(temperature), 3500);

releasedEnergy = trapz(time, heatRate);
lostWallEnergy = trapz(time, max(wallHeatRate, 0));
verifyGreaterThan(testCase, releasedEnergy, 1800);
verifyLessThan(testCase, releasedEnergy, 2200);
verifyGreaterThan(testCase, lostWallEnergy, 0);
verifyLessThan(testCase, lostWallEnergy, releasedEnergy);
clear cleanup
end
