function tests = test_s12_engine_sound_v10_drive_cycle
%TEST_S12_ENGINE_SOUND_V10_DRIVE_CYCLE Contract tests for the 90-second cycle.
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

function testCycleHasFixedFrameAndAudioContract(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
cycle = s12_engine_sound_compile_drive_cycle(profile, "subtle");
verifyEqual(testCase, cycle.sample_rate_hz, 48000);
verifyEqual(testCase, cycle.frame_samples, 960);
verifyEqual(testCase, cycle.frame_count, 4500);
verifySize(testCase, cycle.state, [4500, 6]);
verifyEqual(testCase, cycle.timestamp_s(1), 0, "AbsTol", 1e-12);
verifyEqual(testCase, cycle.timestamp_s(end), 89.98, "AbsTol", 1e-12);
verifyEqual(testCase, diff(cycle.timestamp_s), 0.02 * ones(4499, 1), "AbsTol", 1e-12);
verifyTrue(testCase, all(isfinite(cycle.state), "all"));
end

function testCycleHonorsApprovedSegmentsAndContinuousStates(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
cycle = s12_engine_sound_compile_drive_cycle(profile, "subtle");
verifyEqual(testCase, string({cycle.segments.id}), ["startup", "idle", "pull_away", "cruise", ...
    "wide_open_throttle", "high_load_hold", "lift_off", "downshift_blip", ...
    "second_acceleration", "rapid_lift", "settle_idle"]);
verifyLessThanOrEqual(testCase, max(abs(diff(cycle.state(:, 1)))), 60);
verifyGreaterThanOrEqual(testCase, min(cycle.state(:, 1)), profile.engine.idle_rpm.value);
verifyLessThanOrEqual(testCase, max(cycle.state(:, 1)), profile.engine.redline_rpm.value);
end

function testBackfireLevelsAreDeterministicAndRestrictedToOverrunWindows(testCase)
profile = s12_engine_sound_load_profile("hellcat_style_supercharged_v8");
off = s12_engine_sound_compile_drive_cycle(profile, "off");
subtle = s12_engine_sound_compile_drive_cycle(profile, "subtle");
aggressive = s12_engine_sound_compile_drive_cycle(profile, "aggressive");
verifyEmpty(testCase, off.backfire_events);
verifyGreaterThan(testCase, numel(subtle.backfire_events), 0);
verifyEqual(testCase, numel(subtle.backfire_events), numel(aggressive.backfire_events));
verifyLessThan(testCase, [subtle.backfire_events.energy], [aggressive.backfire_events.energy]);
times = [subtle.backfire_events.time_s];
verifyTrue(testCase, all((times >= 54 & times < 66) | (times >= 82 & times < 88)));
end

function testCycleIsReproducibleForSameProfileAndLevel(testCase)
profile = s12_engine_sound_load_profile("inline5_character");
first = s12_engine_sound_compile_drive_cycle(profile, "subtle");
second = s12_engine_sound_compile_drive_cycle(profile, "subtle");
verifyEqual(testCase, first.timestamp_s, second.timestamp_s);
verifyEqual(testCase, first.state, second.state);
verifyEqual(testCase, first.backfire_events, second.backfire_events);
end
