function tests = test_s12_radiation_time_domain_reference_contract
%TEST_S12_RADIATION_TIME_DOMAIN_REFERENCE_CONTRACT Specify independent reference.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
root = fullfile(s12Root, "validation", "radiation_impedance");
addpath(root); testCase.addTeardown(@() rmpath(root));
end

function testIndependentReferenceHasZeroInputFixedPoint(testCase)
package = packageFixture();
time = linspace(0, 1e-4, 11);
result = s12_radiation_time_domain_reference(package, time, zeros(size(time)));
verifyEqual(testCase, result.incoming_pressure_pa, zeros(size(time)), "AbsTol", 2e-13);
verifyEqual(testCase, result.state(:, end), zeros(2, 1), "AbsTol", 2e-13);
verifyEqual(testCase, result.reference_integrator_id, "matrix_exponential_zoh_independent.v1");
end

function testStaticLimitDoesNotRequireInverseOfA(testCase)
package = struct("state_space_A", zeros(2), "state_space_B", zeros(2, 1), ...
    "state_space_C", zeros(1, 2), "state_space_D", -1, ...
    "initial_state", zeros(2, 1));
time = [0, 1e-6, 2e-6];
outgoing = [3, -2, 1];
result = s12_radiation_time_domain_reference(package, time, outgoing);
verifyEqual(testCase, result.state, zeros(2, numel(time)), "AbsTol", 2e-13);
verifyEqual(testCase, result.incoming_pressure_pa, -outgoing, "AbsTol", 2e-13);
end

function package = packageFixture()
definition = struct("accepted_ka_band", [0.02, 1.2], "radiation_geometry", ...
    "circular_constant_area_unflanged", "normalization_id", "rho0_c0_over_area.v1", ...
    "pipe_radius_m", 0.02, "rho0", 1.2, "c0", 343, ...
    "plane_wave_cutoff_ka", 1.841, "reference_plane", "pipe_exit_plane", ...
    "static_end_correction_over_radius", 0.6133, "fit_method_id", "silva_pade_1_2.v1");
package = s12_radiation_boundary_package(definition);
end
