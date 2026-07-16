function tests = test_s12_transient_wave_reference_contract
%TEST_S12_TRANSIENT_WAVE_REFERENCE_CONTRACT Specify linear-wave primitives.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addTransientPath(testCase);
end

function testReferenceUsesIdealGasSoundSpeedAndGaussianTranslation(testCase)
if ~requireFunction(testCase, "s12_transient_wave_linear_reference"); return; end
definition = fixtureDefinition;
reference = s12_transient_wave_linear_reference(definition, ...
    [definition.pulse_center, definition.pulse_center + 0.03], 0, "incident");
expectedSpeed = sqrt(definition.gamma * definition.ambient_pressure / ...
    definition.ambient_density);
verifyEqual(testCase, reference.wave_speed, expectedSpeed, "RelTol", 32 * eps);
verifyEqual(testCase, reference.pressure_perturbation(1), ...
    definition.pressure_amplitude, "AbsTol", 32 * eps);

time = 0.001;
translated = s12_transient_wave_linear_reference(definition, ...
    definition.pulse_center + expectedSpeed * time, time, "incident");
verifyEqual(testCase, translated.pressure_perturbation, ...
    definition.pressure_amplitude, "RelTol", 2e-14);
verifyEqual(testCase, translated.velocity_perturbation, ...
    definition.pressure_amplitude / ...
    (definition.ambient_density * expectedSpeed), "RelTol", 2e-14);
end

function testArrivalTimeUsesDeterministicLeadingLevelInterpolation(testCase)
if ~requireFunction(testCase, "s12_transient_wave_arrival_time"); return; end
time = [0, 1, 2, 3];
signal = [0, 0.4, 1.0, 0.2];
arrival = s12_transient_wave_arrival_time(time, signal, 0.5);
verifyEqual(testCase, arrival, 1 + (0.5 - 0.4) / (1.0 - 0.4), ...
    "AbsTol", 32 * eps);
end

function testReferenceRejectsNonlinearOrNonphysicalDefinition(testCase)
if ~requireFunction(testCase, "s12_transient_wave_linear_reference"); return; end
definition = fixtureDefinition;
definition.pressure_amplitude = 0.2 * definition.ambient_pressure;
verifyError(testCase, @() s12_transient_wave_linear_reference( ...
    definition, definition.pulse_center, 0, "incident"), ...
    "S12:TransientWave:OutsideLinearRegime");
definition = fixtureDefinition;
definition.gamma = 1;
verifyError(testCase, @() s12_transient_wave_linear_reference( ...
    definition, definition.pulse_center, 0, "incident"), ...
    "S12:TransientWave:InvalidDefinition");
end

function definition = fixtureDefinition
definition = struct( ...
    "gamma", 1.4, ...
    "ambient_density", 1.2, ...
    "ambient_pressure", 101325, ...
    "pipe_length", 2.0, ...
    "pulse_center", 0.25, ...
    "pulse_sigma", 0.04, ...
    "pressure_amplitude", 100.0);
end

function addTransientPath(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
transientRoot = fullfile(s12Root, "validation", "transient_wave");
if isfolder(transientRoot)
    addpath(transientRoot);
    testCase.addTeardown(@() rmpath(transientRoot));
end
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyEqual(testCase, exist(name, "file"), 2, ...
    "Sprint 4C production function must exist: " + name);
end
