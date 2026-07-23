function tests = test_s12_radiation_time_domain_runner_contract
%TEST_S12_RADIATION_TIME_DOMAIN_RUNNER_CONTRACT Specify 4D-B FVM adapter.
tests = functiontests(localfunctions);
end

function testUniformRadiationRunRemainsFixedAndHasExplicitState(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root,"validation","radiation_impedance"));
addpath(fullfile(s12Root,"validation","transient_wave"));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","radiation_impedance")));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","transient_wave")));
gamma=1.4; ambient=[1.2;0;101325/(gamma-1)];
config=struct("gamma",gamma,"pipe_length_m",0.01,"initial_state",repmat(ambient,1,5), ...
    "ambient_state",ambient,"end_time_s",4e-5,"cfl",0.45,"max_steps",128, ...
    "small_signal_limit",0.02,"radiation_package",packageFixture());
result=s12_run_radiation_boundary_fvm(config);
verifyEqual(testCase,result.final_state,repmat(ambient,1,5),"AbsTol",2e-10);
verifyEqual(testCase,result.final_radiation_state,zeros(2,1),"AbsTol",2e-12);
verifyEqual(testCase,result.qualification.retry_count,0);
verifyLessThanOrEqual(testCase,result.qualification.maximum_radiation_stage_pole_amplification,1+1e-10);
verifyGreaterThanOrEqual(testCase,numel(result.trace_time_s),2);
verifyEqual(testCase,result.trace_time_s(end),config.end_time_s,"AbsTol",2e-15);
verifyEqual(testCase,result.trace_outgoing_pressure_pa,zeros(size(result.trace_time_s)),"AbsTol",2e-10);
verifyEqual(testCase,result.trace_incoming_pressure_pa,zeros(size(result.trace_time_s)),"AbsTol",2e-10);
verifyEqual(testCase,result.qualification.radiation_state_dimension,2);
end

function testPoleRejectedStepRollsBackBothStatesBeforeRetry(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root,"validation","radiation_impedance"));
addpath(fullfile(s12Root,"validation","transient_wave"));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","radiation_impedance")));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","transient_wave")));
gamma=1.4; ambient=[1.2;0;101325/(gamma-1)];
config=struct("gamma",gamma,"pipe_length_m",10,"initial_state",repmat(ambient,1,5), ...
    "ambient_state",ambient,"end_time_s",2e-4,"cfl",0.45,"max_steps",64, ...
    "small_signal_limit",0.02,"radiation_package",packageFixture());
result=s12_run_radiation_boundary_fvm(config);
verifyGreaterThan(testCase,result.qualification.retry_count,0);
verifyEqual(testCase,result.qualification.rejected_step_count, ...
    result.qualification.retry_count);
verifyEqual(testCase,result.qualification.rollback_count, ...
    result.qualification.retry_count);
verifyEqual(testCase,result.final_state,repmat(ambient,1,5),"AbsTol",2e-10);
verifyEqual(testCase,result.final_radiation_state,zeros(2,1),"AbsTol",2e-12);
end

function testDrivenInputIsAppliedAtAllSspRk3StageTimes(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root,"validation","radiation_impedance"));
addpath(fullfile(s12Root,"validation","transient_wave"));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","radiation_impedance")));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","transient_wave")));
gamma=1.4; ambient=[1.2;0;101325/(gamma-1)];
config=struct("gamma",gamma,"pipe_length_m",0.01,"initial_state",repmat(ambient,1,5), ...
    "ambient_state",ambient,"end_time_s",4e-5,"cfl",0.45,"max_steps",128, ...
    "small_signal_limit",0.02,"radiation_package",packageFixture(), ...
    "input_signal",struct("id","single_tone.v1","amplitude_pa",8, ...
    "frequency_hz",1200,"phase_rad",pi/2));
result=s12_run_radiation_boundary_fvm(config);
verifyEqual(testCase,result.trace_input_pressure_pa(1),8,"AbsTol",2e-12);
verifyGreaterThan(testCase,max(abs(result.trace_input_pressure_pa)),0);
verifyEqual(testCase,result.qualification.retry_count,0);
verifyEqual(testCase,result.qualification.input_stage_time_id, ...
    "ssprk3_c_0_1_half.v1");
end

function testFixedRunnerUsesBoundary3StageRadiationStateForIncomingTrace(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
addpath(fullfile(s12Root,"validation","radiation_impedance"));
testCase.addTeardown(@() rmpath(fullfile(s12Root,"validation","radiation_impedance")));
gamma = 1.4;
ambient = [1.2; 0; 101325 / (gamma - 1)];
package = packageFixture();
config = struct("gamma",gamma,"pipe_length_m",0.01, ...
    "initial_state",repmat(ambient,1,5),"ambient_state",ambient, ...
    "end_time_s",4e-5,"cfl",0.45,"max_steps",128, ...
    "small_signal_limit",0.02,"radiation_package",package, ...
    "input_signal",struct("id","single_tone.v1","amplitude_pa",8, ...
    "frequency_hz",1200,"phase_rad",pi/2));
result = s12_run_radiation_boundary_fixed_driver(config);
verifyEqual(testCase,size(result.trace_boundary3_radiation_state), ...
    [2,numel(result.trace_time_s)]);
ambientPrimitives = struct("density_kg_m3",ambient(1), ...
    "pressure_pa",101325,"sound_speed_mps",sqrt(gamma * 101325 / ambient(1)));
expected = zeros(size(result.trace_incoming_pressure_pa));
for index = 1:numel(expected)
    boundary = s12_radiation_boundary_stage(package, ...
        result.trace_boundary3_radiation_state(:,index), ...
        result.trace_outgoing_pressure_pa(index), ambientPrimitives, gamma, 0.02);
    expected(index) = boundary.incoming_pressure_pa;
end
verifyEqual(testCase,result.trace_incoming_pressure_pa,expected,"AbsTol",2e-12);
end

function package=packageFixture()
definition=struct("accepted_ka_band",[0.02,1.2],"radiation_geometry","circular_constant_area_unflanged", ...
    "normalization_id","rho0_c0_over_area.v1","pipe_radius_m",0.02,"rho0",1.2,"c0",343, ...
    "plane_wave_cutoff_ka",1.841,"reference_plane","pipe_exit_plane", ...
    "static_end_correction_over_radius",0.6133,"fit_method_id","silva_pade_1_2.v1");
package=s12_radiation_boundary_package(definition);
end
