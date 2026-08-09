function tests = test_s12_radiation_time_domain_pp_step_contract
%TEST_S12_RADIATION_TIME_DOMAIN_PP_STEP_CONTRACT Specify frozen PP reuse.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
for root = [fullfile(s12Root,"validation","radiation_impedance"), fullfile(s12Root,"validation","transient_wave")]
    addpath(root); testCase.addTeardown(@() rmpath(root));
end
end

function testUniformStepRecordsRadiationStageStability(testCase)
gamma = 1.4; ambient = [1.2; 0; 101325/(gamma-1)];
result = s12_radiation_pp_characteristic_step(repmat(ambient,1,5), gamma, 0.01, 1e-6, ...
    "Package", packageFixture(), "RadiationState", zeros(2,1), "AmbientState", ambient, ...
    "AmbientPrimitives", struct("pressure_pa",101325,"density_kg_m3",1.2,"sound_speed_mps",343), ...
    "SmallSignalLimit",0.02,"Cfl",0.45);
verifyEqual(testCase, result.final_state, repmat(ambient,1,5), "AbsTol", 2e-10);
verifyEqual(testCase, result.stage_dt_s, [1e-6,1e-6,1e-6], "AbsTol", 2e-15);
verifyLessThanOrEqual(testCase, result.maximum_radiation_stage_pole_amplification, 1 + 1e-10);
end

function package = packageFixture()
definition = struct("accepted_ka_band",[0.02,1.2],"radiation_geometry","circular_constant_area_unflanged", ...
    "normalization_id","rho0_c0_over_area.v1","pipe_radius_m",0.02,"rho0",1.2,"c0",343, ...
    "plane_wave_cutoff_ka",1.841,"reference_plane","pipe_exit_plane", ...
    "static_end_correction_over_radius",0.6133,"fit_method_id","silva_pade_1_2.v1");
package = s12_radiation_boundary_package(definition);
end
