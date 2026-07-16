function tests = test_s12_radiation_impedance_contract
%TEST_S12_RADIATION_IMPEDANCE_CONTRACT Specify Sprint 4D-A physics contracts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
benchmarkRoot = fullfile(s12Root, "benchmark");
radiationRoot = fullfile(s12Root, "validation", "radiation_impedance");
addpath(benchmarkRoot);
testCase.addTeardown(@() rmpath(benchmarkRoot));
if isfolder(radiationRoot)
    addpath(radiationRoot);
    testCase.addTeardown(@() rmpath(radiationRoot));
end
end

function testDefinitionFreezesUnflangedPlaneWaveContract(testCase)
if ~requireFunction(testCase, "s12_radiation_case_definition"); return; end
definition = s12_radiation_case_definition("full");
verifyEqual(testCase, definition.radiation_geometry, "circular_unflanged");
verifyEqual(testCase, definition.flange_condition, "unflanged");
verifyEqual(testCase, definition.mean_flow_mach, 0);
verifyEqual(testCase, definition.mode_id, "plane_wave");
verifyEqual(testCase, definition.time_harmonic_convention, "exp(+j*omega*t)");
verifyEqual(testCase, definition.impedance_definition, "pressure_over_volume_velocity");
verifyEqual(testCase, definition.normalization_id, "rho0_c0_over_area.v1");
verifyEqual(testCase, definition.reference_plane, "bore_end");
verifyEqual(testCase, definition.reference_method_id, "levine_schwinger_direct_quadrature.v1");
verifyEqual(testCase, definition.fit_method_id, "silva_2009_causal_pade_1_2.v1");
verifyEqual(testCase, definition.accepted_ka_band, [0.02, 2]);
verifyEqual(testCase, definition.plane_wave_cutoff_ka, 3.832, "AbsTol", 1e-12);
verifyEqual(testCase, definition.static_end_correction_over_radius, 0.6133, ...
    "AbsTol", 1e-12);
verifyFalse(testCase, any(ismember(definition.accepted_features, ...
    ["mean_flow", "viscothermal_loss", "time_domain_fvm_boundary"])));
end

function testVolumeVelocityNormalisationAndClosedOpenLimits(testCase)
if ~requireFunction(testCase, "s12_radiation_impedance_from_reflection"); return; end
rho0 = 1.18;
c0 = 343;
radius = 0.02;
area = pi * radius^2;
open = s12_radiation_impedance_from_reflection(-1, rho0, c0, radius);
closed = s12_radiation_impedance_from_reflection(1 - 1e-12, rho0, c0, radius);
verifyEqual(testCase, open.cross_section_area_m2, area, "AbsTol", 1e-15);
verifyEqual(testCase, open.characteristic_impedance, rho0 * c0 / area, ...
    "RelTol", 1e-14);
verifyEqual(testCase, open.normalized_impedance, 0, "AbsTol", 1e-14);
verifyEqual(testCase, open.impedance_pa_s_per_m3, 0, "AbsTol", 1e-9);
verifyGreaterThan(testCase, real(closed.normalized_impedance), 1e10);
verifyGreaterThan(testCase, abs(closed.impedance_pa_s_per_m3), 1e10);
end

function testDirectReferenceHasLowFrequencyEndCorrectionAndPassivity(testCase)
if ~requireFunction(testCase, "s12_radiation_unflanged_reference"); return; end
definition = s12_radiation_case_definition("quick");
reference = s12_radiation_unflanged_reference([0, 0.02, 0.2, 1.0, 2.0], definition);
verifyEqual(testCase, reference.reflection(1), -1, "AbsTol", 1e-14);
verifyEqual(testCase, reference.normalized_impedance(1), 0, "AbsTol", 1e-14);
verifyLessThan(testCase, abs(reference.end_correction_over_radius(2) - 0.6133), ...
    definition.acceptance.low_frequency_end_correction_abs_limit);
verifyGreaterThanOrEqual(testCase, min(real(reference.normalized_impedance)), ...
    -definition.acceptance.passivity_negative_tolerance);
verifyLessThanOrEqual(testCase, max(abs(reference.reflection)), ...
    1 + definition.acceptance.reflection_magnitude_tolerance);
verifyGreaterThan(testCase, imag(reference.normalized_impedance(2)), 0);
verifyLessThanOrEqual(testCase, reference.quadrature.maximum_reflection_difference, ...
    definition.acceptance.quadrature_reflection_limit);
verifyLessThanOrEqual(testCase, reference.quadrature.maximum_end_correction_difference, ...
    definition.acceptance.quadrature_end_correction_limit);
end

function testDirectReferenceIsHermitianAndRejectsPlaneWaveCutoff(testCase)
if ~requireFunction(testCase, "s12_radiation_unflanged_reference"); return; end
definition = s12_radiation_case_definition("quick");
pair = s12_radiation_unflanged_reference([-0.5, 0.5], definition);
verifyEqual(testCase, pair.reflection(1), conj(pair.reflection(2)), "AbsTol", 1e-12);
verifyEqual(testCase, pair.normalized_impedance(1), ...
    conj(pair.normalized_impedance(2)), "AbsTol", 1e-12);
diagnostic = s12_radiation_unflanged_reference(3.1, definition);
verifyEqual(testCase, diagnostic.applicability, "diagnostic_near_plane_wave_cutoff");
verifyError(testCase, @() s12_radiation_unflanged_reference(3.832, definition), ...
    "S12:Radiation:PlaneWaveCutoff");
end

function testDiagnosticReferenceQuadratureConvergesBeforeCutoff(testCase)
if ~requireFunction(testCase, "s12_radiation_unflanged_reference"); return; end
definition = s12_radiation_case_definition("full");
reference = s12_radiation_unflanged_reference(3.1, definition);
verifyLessThanOrEqual(testCase, reference.quadrature.maximum_reflection_difference, ...
    definition.acceptance.quadrature_reflection_limit);
verifyLessThanOrEqual(testCase, reference.quadrature.maximum_end_correction_difference, ...
    definition.acceptance.quadrature_end_correction_limit);
end

function testPublishedPadeCandidateIsStablePassiveAndConjugateSymmetric(testCase)
if ~requireFunction(testCase, "s12_radiation_unflanged_pade_fit"); return; end
definition = s12_radiation_case_definition("quick");
fit = s12_radiation_unflanged_pade_fit([-2, -0.3, 0.3, 2], definition);
verifyEqual(testCase, fit.fit_order, [1, 2]);
verifyTrue(testCase, isreal(fit.state_space.A));
verifyTrue(testCase, isreal(fit.state_space.B));
verifyTrue(testCase, isreal(fit.state_space.C));
verifyTrue(testCase, isreal(fit.state_space.D));
verifyLessThan(testCase, max(real(fit.poles)), 0);
verifyGreaterThan(testCase, fit.stability_margin, 0);
verifyEqual(testCase, fit.reflection(1), conj(fit.reflection(4)), "AbsTol", 1e-12);
verifyEqual(testCase, fit.reflection(2), conj(fit.reflection(3)), "AbsTol", 1e-12);
verifyGreaterThanOrEqual(testCase, min(real(fit.normalized_impedance)), ...
    -definition.acceptance.passivity_negative_tolerance);
verifyLessThanOrEqual(testCase, max(abs(fit.reflection)), ...
    1 + definition.acceptance.reflection_magnitude_tolerance);
end

function testSimilarityAndTrainingValidationSeparationAreExplicit(testCase)
if ~requireFunction(testCase, "s12_radiation_unflanged_reference"); return; end
definition = s12_radiation_case_definition("full");
reference = s12_radiation_unflanged_reference([0.05, 0.3, 1.4], definition);
similarity = reference.similarity;
verifyEqual(testCase, similarity.mapping_count, 3);
verifyLessThanOrEqual(testCase, similarity.maximum_normalized_impedance_difference, ...
    definition.acceptance.similarity_limit);
verifyEmpty(testCase, intersect(definition.fit_training_ka, definition.fit_validation_ka));
verifyTrue(testCase, all(definition.fit_validation_ka >= definition.accepted_ka_band(1)));
verifyTrue(testCase, all(definition.fit_validation_ka <= definition.accepted_ka_band(2)));
end

function testBoundaryPackageIsFrequencyOnlyAndIncludesStateSpace(testCase)
if ~requireFunction(testCase, "s12_radiation_boundary_package"); return; end
definition = s12_radiation_case_definition("quick");
package = s12_radiation_boundary_package(definition);
verifyEqual(testCase, package.schema, "radiation_boundary_package.v1");
verifyEqual(testCase, package.geometry, "circular_unflanged");
verifyEqual(testCase, package.normalization, "rho0_c0_over_area.v1");
verifyEqual(testCase, package.reference_plane, "bore_end");
verifyEqual(testCase, package.valid_ka_band, [0.02, 2]);
verifyTrue(testCase, isfield(package, "state_space_A"));
verifyTrue(testCase, isfield(package, "asset_sha256"));
verifyMatches(testCase, package.asset_sha256, "^[0-9A-F]{64}$");
verifyFalse(testCase, isfield(package, "fvm_boundary_connection"));
end

function available = requireFunction(testCase, name)
available = exist(name, "file") == 2;
if ~available
    verifyTrue(testCase, false, ...
        "Sprint 4D-A production capability is missing: " + string(name));
end
end
