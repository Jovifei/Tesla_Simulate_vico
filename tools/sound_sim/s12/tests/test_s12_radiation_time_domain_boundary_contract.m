function tests = test_s12_radiation_time_domain_boundary_contract
%TEST_S12_RADIATION_TIME_DOMAIN_BOUNDARY_CONTRACT Specify 4D-B stage behavior.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root, "validation", "radiation_impedance"));
testCase.addTeardown(@() rmpath(fullfile(s12Root, "validation", "radiation_impedance")));
end

function testStageRealizesFrozenReflectionAndLinearGhost(testCase)
package = packageFixture();
ambient = ambientFixture();
state = [1e-8; -1e-5];
outgoing = 14;
result = s12_radiation_boundary_stage(package, state, outgoing, ambient, 1.4, 0.02);
expectedIncoming = package.state_space_C * state + package.state_space_D * outgoing;
verifyEqual(testCase, result.incoming_pressure_pa, expectedIncoming, "AbsTol", 2e-12);
verifyEqual(testCase, result.state_derivative, package.state_space_A * state + ...
    package.state_space_B * outgoing, "AbsTol", 2e-12);
verifyEqual(testCase, result.outgoing_pressure_pa, outgoing, "AbsTol", 2e-12);
verifyEqual(testCase, result.boundary_pressure_pa, ambient.pressure_pa + outgoing + expectedIncoming, ...
    "AbsTol", 2e-12);
verifyEqual(testCase, result.boundary_velocity_mps, ...
    (outgoing - expectedIncoming) / (ambient.density_kg_m3 * ambient.sound_speed_mps), ...
    "AbsTol", 2e-12);
end

function testStageRejectsNonlinearOrNonphysicalGhostInsteadOfClipping(testCase)
package = packageFixture();
ambient = ambientFixture();
verifyError(testCase, @() s12_radiation_boundary_stage(package, zeros(2, 1), ...
    0.25 * ambient.pressure_pa, ambient, 1.4, 0.02), ...
    "S12:Radiation:SmallSignalLimit");
verifyError(testCase, @() s12_radiation_boundary_stage(package, [NaN; 0], ...
    1, ambient, 1.4, 0.02), "S12:Radiation:InvalidState");
end

function testStagePoleMetricUsesSspRk3StabilityPolynomial(testCase)
package = packageFixture();
result = s12_radiation_boundary_step_stability(package, 1e-7);
lambda = eig(package.state_space_A);
expected = max(abs(1 + 1e-7 * lambda + (1e-7 * lambda).^2 / 2 + ...
    (1e-7 * lambda).^3 / 6));
verifyLessThanOrEqual(testCase, result.maximum_stage_pole_amplification, 1 + 1e-10);
verifyEqual(testCase, result.maximum_stage_pole_amplification, expected, "AbsTol", 2e-12);
verifyEqual(testCase, result.continuous_poles, eig(package.state_space_A), "AbsTol", 2e-12);
verifyTrue(testCase, result.continuous_stable);
end

function testStaticLimitHasNeutralButNonintegratingState(testCase)
package = struct("state_space_A", zeros(2), "state_space_B", zeros(2, 1), ...
    "state_space_C", zeros(1, 2), "state_space_D", -1);
result = s12_radiation_boundary_step_stability(package, 1e-7);
verifyTrue(testCase, result.static_limit);
verifyTrue(testCase, result.continuous_stable);
verifyEqual(testCase, result.maximum_stage_pole_amplification, 1, "AbsTol", 2e-12);
end

function package = packageFixture()
definition = struct("accepted_ka_band", [0.02, 1.2], "radiation_geometry", ...
    "circular_constant_area_unflanged", "normalization_id", "rho0_c0_over_area.v1", ...
    "pipe_radius_m", 0.02, "rho0", 1.2, "c0", 343, ...
    "plane_wave_cutoff_ka", 1.841, "reference_plane", "pipe_exit_plane", ...
    "static_end_correction_over_radius", 0.6133, "fit_method_id", "silva_pade_1_2.v1");
package = s12_radiation_boundary_package(definition);
end

function ambient = ambientFixture()
ambient = struct("pressure_pa", 101325, "density_kg_m3", 1.2, ...
    "sound_speed_mps", 343);
end
