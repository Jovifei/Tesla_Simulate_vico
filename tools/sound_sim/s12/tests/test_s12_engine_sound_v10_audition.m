function tests = test_s12_engine_sound_v10_audition
%TEST_S12_ENGINE_SOUND_V10_AUDITION Contract test for published 90-second WAV runs.
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

function testAuditionPublishesRequiredDeterministicArtifactShape(testCase)
result = s12_engine_sound_audition("inline3_turbo", "BackfireLevel", "off", "Play", false);
required = ["full_drive_cycle.wav", "idle.wav", "acceleration.wav", "deceleration.wav", ...
    "overrun_backfire.wav", "vehicle_trace.csv", "profile_snapshot.json", "sound_analysis.json", ...
    "manifest.json", "SHA256.txt", "full_drive_cycle_pcm_f32le.bin"];
verifyTrue(testCase, all(isfile(fullfile(result.output_directory, required))));
audio = audioinfo(fullfile(result.output_directory, "full_drive_cycle.wav"));
verifyEqual(testCase, audio.SampleRate, 48000);
verifyEqual(testCase, audio.NumChannels, 2);
verifyEqual(testCase, audio.BitsPerSample, 24);
verifyEqual(testCase, audio.TotalSamples, 90 * 48000);
analysis = jsondecode(fileread(fullfile(result.output_directory, "sound_analysis.json")));
verifyEqual(testCase, string(analysis.profile_id), "inline3_turbo");
verifyEqual(testCase, logical(analysis.synthetic), true);
verifyEqual(testCase, double(analysis.clipping_count), 0);
end
