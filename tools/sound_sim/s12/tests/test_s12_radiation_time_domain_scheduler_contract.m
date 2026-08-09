function tests = test_s12_radiation_time_domain_scheduler_contract
%TEST_S12_RADIATION_TIME_DOMAIN_SCHEDULER_CONTRACT Specify augmented SSP-RK3.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
root = fullfile(s12Root, "validation", "radiation_impedance");
addpath(root); testCase.addTeardown(@() rmpath(root));
end

function testAugmentedStateUsesOneSharedDtAtAllThreeStages(testCase)
package = packageFixture();
state0 = [1e-8; -2e-5];
dt = 2e-7;
outgoing = [2, 3, 5];
result = s12_radiation_boundary_ssprk3_state(package, state0, outgoing, dt);
d0 = package.state_space_A * state0 + package.state_space_B * outgoing(1);
state1 = state0 + dt * d0;
d1 = package.state_space_A * state1 + package.state_space_B * outgoing(2);
state2 = 0.75 * state0 + 0.25 * (state1 + dt * d1);
d2 = package.state_space_A * state2 + package.state_space_B * outgoing(3);
expected = (1 / 3) * state0 + (2 / 3) * (state2 + dt * d2);
verifyEqual(testCase, result.stage_dt_s, [dt, dt, dt], "AbsTol", 2e-15);
verifyEqual(testCase, result.stage_state(:, 1), state1, "AbsTol", 2e-12);
verifyEqual(testCase, result.stage_state(:, 2), state2, "AbsTol", 2e-12);
verifyEqual(testCase, result.final_state, expected, "AbsTol", 2e-12);
end

function package = packageFixture()
definition = struct("accepted_ka_band", [0.02, 1.2], "radiation_geometry", ...
    "circular_constant_area_unflanged", "normalization_id", "rho0_c0_over_area.v1", ...
    "pipe_radius_m", 0.02, "rho0", 1.2, "c0", 343, ...
    "plane_wave_cutoff_ka", 1.841, "reference_plane", "pipe_exit_plane", ...
    "static_end_correction_over_radius", 0.6133, "fit_method_id", "silva_pade_1_2.v1");
package = s12_radiation_boundary_package(definition);
end
