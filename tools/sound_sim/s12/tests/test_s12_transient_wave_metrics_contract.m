function tests = test_s12_transient_wave_metrics_contract
%TEST_S12_TRANSIENT_WAVE_METRICS_CONTRACT Specify reflection measurements.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
transientRoot = fullfile(s12Root, "validation", "transient_wave");
if isfolder(transientRoot)
    addpath(transientRoot);
    testCase.addTeardown(@() rmpath(transientRoot));
end
end

function testClosedAndOpenSignsUseFixedWindows(testCase)
if ~requireFunction(testCase, "s12_transient_wave_reflection_metrics"); return; end
time = linspace(0, 4, 4001);
incident = exp(-0.5 * ((time - 1) / 0.08).^2);
velocityIncident = incident / 400;
windows = struct("incident", [0.7, 1.3], "reflected", [2.7, 3.3], ...
    "ambient_pressure", 101325, "ambient_density", 1.2, "wave_speed", 400);

closed = s12_transient_wave_reflection_metrics(time, ...
    101325 + incident + 0.98 * exp(-0.5 * ((time - 3) / 0.08).^2), ...
    velocityIncident - 0.98 * exp(-0.5 * ((time - 3) / 0.08).^2) / 400, windows);
verifyEqual(testCase, closed.pressure_reflection_coefficient, 0.98, ...
    "AbsTol", 2e-3);
verifyEqual(testCase, closed.velocity_reflection_coefficient, -0.98, ...
    "AbsTol", 2e-3);

open = s12_transient_wave_reflection_metrics(time, ...
    101325 + incident - 0.98 * exp(-0.5 * ((time - 3) / 0.08).^2), ...
    velocityIncident + 0.98 * exp(-0.5 * ((time - 3) / 0.08).^2) / 400, windows);
verifyEqual(testCase, open.pressure_reflection_coefficient, -0.98, ...
    "AbsTol", 2e-3);
verifyEqual(testCase, open.velocity_reflection_coefficient, 0.98, ...
    "AbsTol", 2e-3);
verifyLessThan(testCase, open.boundary_energy_residual, 0.05);
end

function testMetricsRejectOverlappingOrEmptyWindows(testCase)
if ~requireFunction(testCase, "s12_transient_wave_reflection_metrics"); return; end
time = [0, 1, 2];
windows = struct("incident", [0, 1], "reflected", [0.5, 2], ...
    "ambient_pressure", 1, "ambient_density", 1, "wave_speed", 1);
verifyError(testCase, @() s12_transient_wave_reflection_metrics( ...
    time, [1, 1, 1], [0, 0, 0], windows), ...
    "S12:TransientWave:InvalidWindow");
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 4C production function must exist: " + name);
end
