function tests = test_s12_engine_sound_v11_cycle_api_start
%TEST_S12_ENGINE_SOUND_V11_CYCLE_API_START Authored Desktop-only P1 checks.
% These behavior checks are NOT RUN while the MATLAB MCP control plane is unsafe.

tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
v11 = fullfile(s12Root, "playground_v11");
addpath(v11);
testCase.TestData.v11 = string(v11);
end

function teardownOnce(testCase)
rmpath(testCase.TestData.v11);
end

function testFixedAcceptanceWindowsAreExact(testCase)
profile = s12_v11_load_profile("hellcat_2022_stock");
cycle = s12_v11_compile_vehicle_cycle(profile);
expectedNames = ["startup", "idle", "launch", "cruise", "wot_to_redline", ...
    "high_load_hold", "lift", "downshift_blip", "second_acceleration", ...
    "rapid_lift", "return_idle"];
expectedBoundaries = [0, 2, 12, 22, 32, 48, 54, 66, 72, 82, 88, 90];
verifyEqual(testCase, string({cycle.segments.id}), expectedNames);
verifyEqual(testCase, [cycle.segments.start_s], expectedBoundaries(1:end - 1));
verifyEqual(testCase, [cycle.segments.end_s], expectedBoundaries(2:end));
verifyEqual(testCase, cycle.frame_count, 4500);
verifyEqual(testCase, cycle.sample_count, 4320000);
verifyEqual(testCase, height(cycle.state), 4500);
verifyTrue(testCase, all(ismember(["rpm", "load", "throttle", "acceleration", ...
    "speed_kph", "gear", "shift_type", "dfco", "thermal_state", "oxygen_state"], ...
    string(cycle.state.Properties.VariableNames))));
verifyEqual(testCase, cycle.state.rpm(cycle.timestamp_s >= 48 & cycle.timestamp_s < 54), ...
    repmat(profile.character.redline_rpm, 300, 1));
end

function testStartupEnvelopeIsContinuousAndPrePtrScoped(testCase)
base = ones(960, 1);
[tail, tailDiagnostics] = s12_v11_apply_startup_source_envelope(base, 1.98, 48000);
[steady, steadyDiagnostics] = s12_v11_apply_startup_source_envelope(base, 2.00, 48000);
verifyEqual(testCase, tailDiagnostics.stage, "engine_excitation_before_ptr_radiation");
verifyFalse(testCase, tailDiagnostics.post_pcm_effect);
verifyTrue(testCase, tailDiagnostics.applied);
verifyFalse(testCase, steadyDiagnostics.applied);
verifyLessThan(testCase, abs(tail(end) - steady(1)), 1e-3);
verifyEqual(testCase, steady, base);
end

function testCompatibilityRoutesEveryCanonicalProfile(testCase)
listed = s12_engine_sound_list_profiles();
expected = s12_v11_canonical_vehicle_ids();
verifyEqual(testCase, string({listed.profile_id}), expected);
for identifier = expected
    profile = s12_engine_sound_load_profile(identifier);
    reference = s12_engine_sound_compare_reference(identifier);
    modelPath = s12_engine_sound_open_model(identifier, "Open", false);
    verifyEqual(testCase, profile.vehicle_id, identifier);
    verifyEqual(testCase, reference.profile_id, identifier);
    verifyFalse(testCase, reference.raw_reference_audio_used);
    verifyTrue(testCase, endsWith(modelPath, ".slx"));
end
end

function testAllEightBatchApiAuthoredNotRun(testCase)
% This intentionally skips until safe existing-session Desktop authorization.
assumeTrue(testCase, false, [ ...
    "NOT_RUNTIME_VERIFIED: all-eight publication is withheld until one safe ", ...
    "user-started shared MATLAB Desktop is available."]);
results = s12_engine_sound_render_all_v11("Play", false); %#ok<UNRCH>
verifyEqual(testCase, numel(results), 8); %#ok<UNRCH>
end
