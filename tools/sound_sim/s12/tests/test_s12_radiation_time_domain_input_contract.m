function tests = test_s12_radiation_time_domain_input_contract
%TEST_S12_RADIATION_TIME_DOMAIN_INPUT_CONTRACT Specify left characteristic drive.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
radiationRoot = fullfile(s12Root, "validation", "radiation_impedance");
addpath(radiationRoot);
testCase.addTeardown(@() rmpath(radiationRoot));
end

function testDrivePrescribesOnlyIncomingLinearCharacteristic(testCase)
gamma = 1.4;
ambient = ambientState(gamma);
incomingPressure = 12;
result = s12_radiation_left_driven_boundary_state(ambient, ambient, gamma, ...
    incomingPressure, 0.02);
rho0 = ambient(1);
p0 = pressureOf(ambient, gamma);
c0 = sqrt(gamma * p0 / rho0);
verifyEqual(testCase, result.incoming_pressure_pa, incomingPressure, "AbsTol", 2e-12);
verifyEqual(testCase, result.outgoing_pressure_pa, 0, "AbsTol", 2e-12);
verifyEqual(testCase, result.boundary_pressure_pa, p0 + incomingPressure, "AbsTol", 2e-12);
verifyEqual(testCase, result.boundary_velocity_mps, incomingPressure / (rho0 * c0), ...
    "AbsTol", 2e-12);
verifyEqual(testCase, result.state(2) / result.state(1), result.boundary_velocity_mps, ...
    "AbsTol", 2e-12);
end

function testDrivePreservesInteriorOutgoingCharacteristic(testCase)
gamma = 1.4;
ambient = ambientState(gamma);
interior = ambient;
interior(2) = 0.15 * interior(1);
incomingPressure = 7;
result = s12_radiation_left_driven_boundary_state(interior, ambient, gamma, ...
    incomingPressure, 0.02);
verifyEqual(testCase, result.incoming_pressure_pa, incomingPressure, "AbsTol", 2e-12);
verifyEqual(testCase, result.outgoing_characteristic, ...
    outgoingLinearPressure(interior, ambient, gamma), "AbsTol", 2e-12);
verifyGreaterThan(testCase, result.state(1), 0);
verifyGreaterThan(testCase, pressureOf(result.state, gamma), 0);
end

function testDriveRejectsNonlinearInputRatherThanClipping(testCase)
gamma = 1.4;
ambient = ambientState(gamma);
verifyError(testCase, @() s12_radiation_left_driven_boundary_state( ...
    ambient, ambient, gamma, 0.03 * pressureOf(ambient, gamma), 0.02), ...
    "S12:Radiation:SmallSignalLimit");
end

function testDeterministicWaveformDefinitions(testCase)
tone = struct("id", "single_tone.v1", "amplitude_pa", 8, ...
    "frequency_hz", 1200, "phase_rad", pi / 2);
verifyEqual(testCase, s12_radiation_input_signal(tone, 0), 8, "AbsTol", 2e-12);
multi = struct("id", "multisine.v1", "amplitude_pa", [2, 3], ...
    "frequency_hz", [500, 700], "phase_rad", [pi / 2, pi / 2]);
verifyEqual(testCase, s12_radiation_input_signal(multi, 0), 5, "AbsTol", 2e-12);
chirp = struct("id", "chirp_linear.v1", "amplitude_pa", 4, ...
    "start_frequency_hz", 100, "end_frequency_hz", 1000, ...
    "duration_s", 0.02, "phase_rad", pi / 2);
verifyEqual(testCase, s12_radiation_input_signal(chirp, 0), 4, "AbsTol", 2e-12);
pulse = struct("id", "gaussian_pulse.v1", "amplitude_pa", 6, ...
    "center_time_s", 0.01, "sigma_time_s", 0.002);
verifyEqual(testCase, s12_radiation_input_signal(pulse, 0.01), 6, "AbsTol", 2e-12);
end

function state = ambientState(gamma)
rho = 1.2; p = 101325;
state = [rho; 0; p / (gamma - 1)];
end

function value = pressureOf(state, gamma)
rho = state(1); velocity = state(2) / rho;
value = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
end

function value = outgoingLinearPressure(state, ambient, gamma)
rho0 = ambient(1); p0 = pressureOf(ambient, gamma);
velocity = state(2) / state(1);
value = 0.5 * ((pressureOf(state, gamma) - p0) - ...
    rho0 * sqrt(gamma * p0 / rho0) * velocity);
end
