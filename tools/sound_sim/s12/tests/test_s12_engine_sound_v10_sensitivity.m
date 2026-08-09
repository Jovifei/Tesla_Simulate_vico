function tests = test_s12_engine_sound_v10_sensitivity
%TEST_S12_ENGINE_SOUND_V10_SENSITIVITY Exercise synthetic control causality.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
source = fullfile(fileparts(fileparts(mfilename("fullpath"))), "playground_v10");
testCase.TestData.source = source;
addpath(source);
addpath(fullfile(fileparts(source), "playground"));
load_system(fullfile(source, "S12_I3_Turbo_v10.slx"));
end

function teardownOnce(testCase)
if isfolder(testCase.TestData.source)
    rmpath(testCase.TestData.source);
end
end

function testLoadAndAccelerationChangeExcitation(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
state = [3000, 0, 0, 0.5, 60, 0];
low = excitation(profile, state);
state(2) = 1;
high = excitation(profile, state);
verifyGreaterThan(testCase, norm(low - high), 1e-3);
state = [3000, 0.5, 0, 0.5, 60, 0];
steady = excitation(profile, state);
state(3) = 3;
accelerating = excitation(profile, state);
verifyGreaterThan(testCase, norm(steady - accelerating), 1e-3);
end

function testBackfireLevelsAreOrderedAndLimitedToOverrun(testCase)
profile = s12_engine_sound_load_profile("v6_sport");
off = s12_engine_sound_compile_drive_cycle(profile, "off");
subtle = s12_engine_sound_compile_drive_cycle(profile, "subtle");
aggressive = s12_engine_sound_compile_drive_cycle(profile, "aggressive");
verifyEmpty(testCase, off.backfire_events);
verifyGreaterThan(testCase, numel(subtle.backfire_events), 0);
verifyLessThan(testCase, sum([subtle.backfire_events.energy]), sum([aggressive.backfire_events.energy]));
eventFrames = floor([subtle.backfire_events.time_s] / ...
    (subtle.frame_samples / subtle.sample_rate_hz)) + 1;
verifyTrue(testCase, all(subtle.state(eventFrames, 6) > 0));
end

function testDashboardModeChangesModelPcm(testCase)
model = "S12_I3_Turbo_v10";
s12_engine_sound_assign_model_workspace(model, "inline3_turbo", "subtle");
workspace = get_param(model, "ModelWorkspace");
assignin(workspace, "v10_interactive_mode", true);
assignin(workspace, "v10_dashboard_rpm", 1200);
assignin(workspace, "v10_dashboard_load", 0.2);
assignin(workspace, "v10_dashboard_acceleration", 0);
first = shortRun(model);
assignin(workspace, "v10_dashboard_rpm", 4200);
assignin(workspace, "v10_dashboard_load", 1.0);
assignin(workspace, "v10_dashboard_acceleration", 3.0);
second = shortRun(model);
verifyEqual(testCase, size(first, 1), 960);
verifyGreaterThan(testCase, norm(first(:) - second(:)), 1e-3);
s12_engine_sound_assign_model_workspace(model, "inline3_turbo", "subtle");
end

function signal = excitation(profile, state)
context = [];
parts = zeros(profile.renderer.frame_samples.value, 20);
for index = 1:size(parts, 2)
    [parts(:, index), context] = s12_engine_sound_excitation_frame(profile, state, context);
end
signal = parts(:);
end

function pcm = shortRun(model)
input = Simulink.SimulationInput(model);
input = input.setModelParameter("StopTime", "2");
output = sim(input);
pcm = output.v10_pcm.signals.values;
end
