function tests = test_s12_engine_sound_v10_renderer
%TEST_S12_ENGINE_SOUND_V10_RENDERER Contract tests for deterministic PCM synthesis.
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

function testRendererProducesFiniteStereoPcmWithoutClipping(testCase)
profile = s12_engine_sound_load_profile("inline4_sport");
result = s12_engine_sound_render_cycle(profile, "BackfireLevel", "off", "FrameIndices", 1:8);
verifyEqual(testCase, result.sample_rate_hz, 48000);
verifySize(testCase, result.pcm, [8 * 960, 2]);
verifyTrue(testCase, all(isfinite(result.pcm), "all"));
verifyLessThan(testCase, max(abs(result.pcm), [], "all"), 1);
verifyLessThan(testCase, max(abs(result.pcm(961, :) - result.pcm(960, :))), 0.20);
end

function testAggressiveBackfireChangesPrePtrExcitationWithoutClipping(testCase)
profile = s12_engine_sound_load_profile("hellcat_style_supercharged_v8");
frames = 2753:2764;
off = s12_engine_sound_render_cycle(profile, "BackfireLevel", "off", "FrameIndices", frames);
aggressive = s12_engine_sound_render_cycle(profile, "BackfireLevel", "aggressive", "FrameIndices", frames);
verifyNotEqual(testCase, off.excitation, aggressive.excitation);
verifyGreaterThan(testCase, rms(aggressive.excitation - off.excitation), 0.001);
verifyLessThan(testCase, max(abs(aggressive.pcm), [], "all"), 1);
end

function testEngineProfilesProduceMeasurablyDifferentOrderFingerprints(testCase)
frames = 1601:1620;
inlineFive = s12_engine_sound_render_cycle(s12_engine_sound_load_profile("inline5_character"), ...
    "BackfireLevel", "off", "FrameIndices", frames);
highRev = s12_engine_sound_render_cycle(s12_engine_sound_load_profile("ferrari_style_high_rev_v8"), ...
    "BackfireLevel", "off", "FrameIndices", frames);
verifyNotEqual(testCase, inlineFive.analysis.order_energy, highRev.analysis.order_energy);
verifyGreaterThan(testCase, norm(inlineFive.analysis.order_energy - highRev.analysis.order_energy), 1e-4);
end

function testRendererIsBitwiseDeterministicForSameProfileAndFrames(testCase)
profile = s12_engine_sound_load_profile("v6_sport");
first = s12_engine_sound_render_cycle(profile, "BackfireLevel", "subtle", "FrameIndices", 1:12);
second = s12_engine_sound_render_cycle(profile, "BackfireLevel", "subtle", "FrameIndices", 1:12);
verifyEqual(testCase, first.pcm, second.pcm);
verifyEqual(testCase, first.excitation, second.excitation);
end
