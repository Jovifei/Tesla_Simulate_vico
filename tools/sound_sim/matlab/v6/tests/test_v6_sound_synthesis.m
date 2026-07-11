function tests = test_v6_sound_synthesis
tests = functiontests(localfunctions);
end

function testProfileHasPhysicalLayers(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
verifyEqual(testCase, profile.schema, "jovi.engine_sound.v6");
verifyEqual(testCase, profile.engine.displacement_l, 6.208, AbsTol=1e-12);
verifyEqual(testCase, profile.engine.firing_order, [1, 5, 4, 2, 6, 3, 7, 8]);
verifyEqual(testCase, profile.audio.sample_rate_hz, 96000);
verifyGreaterThan(testCase, profile.afterfire.crack_gain, 1.0);
end

function testSteadyStateRender(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
scenario = v6_build_cycle(profile, "steady_4000", 1000);
[audio, result] = v6_synthesize_engine_sound(profile, scenario);
verifySize(testCase, audio, [1, 3 * profile.audio.sample_rate_hz]);
verifyTrue(testCase, all(isfinite(audio)));
verifyLessThanOrEqual(testCase, max(abs(audio)), profile.audio.peak_limit + 1e-9);
verifyGreaterThan(testCase, sqrt(mean(audio.^2)), 0.01);
verifyGreaterThan(testCase, max(abs(result.layers.exhaust)), 0.001);
verifyGreaterThan(testCase, max(result.state.sound_speed_mps), 450);
verifyLessThan(testCase, height(result.events), 1);
end

function testTipoutCreatesThermalAfterfire(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
scenario = v6_build_cycle(profile, "tipout_5500", 1000);
[audio, result] = v6_synthesize_engine_sound(profile, scenario);
verifyTrue(testCase, all(isfinite(audio)));
verifyGreaterThan(testCase, height(result.events), 1);
verifyTrue(testCase, any(result.events.type == "overrun"));
verifyGreaterThan(testCase, max(abs(result.layers.afterfire)), 0.001);
verifyTrue(testCase, any(result.state.dfco));
end

function testDeterministicRender(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
scenario = v6_build_cycle(profile, "upshift_12", 1000);
[audioA, resultA] = v6_synthesize_engine_sound(profile, scenario);
[audioB, resultB] = v6_synthesize_engine_sound(profile, scenario);
verifyEqual(testCase, audioA, audioB);
verifyEqual(testCase, resultA.events, resultB.events);
verifyGreaterThan(testCase, max(abs(resultA.layers.afterfire)), 0.001);
end

function testReferenceFeaturesPreserveMonoSamples(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
sampleRate = 96000;
time = 0:1 / sampleRate:0.20 - 1 / sampleRate;
audio = sin(2 * pi * 620 * time);
rowFeatures = v6_reference_features(audio, sampleRate);
columnFeatures = v6_reference_features(audio.', sampleRate);
verifyEqual(testCase, rowFeatures.centroid_hz, columnFeatures.centroid_hz, AbsTol=1e-9);
verifyGreaterThan(testCase, rowFeatures.centroid_hz, 500);
verifyLessThan(testCase, rowFeatures.centroid_hz, 750);
end
