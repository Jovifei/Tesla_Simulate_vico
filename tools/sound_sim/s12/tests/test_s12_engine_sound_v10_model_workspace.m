function tests = test_s12_engine_sound_v10_model_workspace
%TEST_S12_ENGINE_SOUND_V10_MODEL_WORKSPACE Contract test for JSON-to-model binding.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v10");
testCase.TestData.source = source;
addpath(source);
end

function teardownOnce(testCase)
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
end

function testBinderPublishesProfileAndNinetySecondSources(testCase)
model = "S12_I3_Turbo_v10";
profile = s12_engine_sound_assign_model_workspace(model, "inline3_turbo", "subtle");
workspace = get_param(model, "ModelWorkspace");
verifyEqual(testCase, evalin(workspace, "v10_cylinder_count"), 3);
verifyEqual(testCase, evalin(workspace, "v10_firing_order"), [1, 3, 2]);
verifyEqual(testCase, evalin(workspace, "v10_pipe_length_m"), profile.ptr.pipe_length_m.value);
vehicle = evalin(workspace, "v10_vehicle_state");
backfire = evalin(workspace, "v10_backfire");
expected = s12_engine_sound_simulink_sources(profile, "subtle");
verifySize(testCase, vehicle.Data, [4500, 6]);
verifyEqual(testCase, backfire.Data ~= 0, expected.backfire_energy.Data ~= 0);
end

function testBinderProvidesInteractiveDashboardDefaults(testCase)
profile = s12_engine_sound_assign_model_workspace("S12_I3_Turbo_v10", "inline3_turbo", "subtle");
workspace = get_param("S12_I3_Turbo_v10", "ModelWorkspace");
verifyEqual(testCase, evalin(workspace, "v10_interactive_mode"), false);
verifyEqual(testCase, evalin(workspace, "v10_dashboard_rpm"), profile.engine.idle_rpm.value);
verifyEqual(testCase, evalin(workspace, "v10_dashboard_load"), 0.10);
verifyEqual(testCase, evalin(workspace, "v10_dashboard_order_balance"), 1.0);
verifyEqual(testCase, evalin(workspace, "v10_dashboard_backfire_scale"), 1.0);
end
