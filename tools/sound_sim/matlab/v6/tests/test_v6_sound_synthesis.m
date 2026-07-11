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
verifyGreaterThan(testCase, profile.rasp.nonlinear_gain, 0);
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
overrun = result.events(result.events.type == "overrun", :);
verifyGreaterThanOrEqual(testCase, height(overrun), 24);
verifyGreaterThanOrEqual(testCase, max(overrun.time_s) - min(overrun.time_s), 0.8);
features = v6_reference_features(result.layers.afterfire, profile.audio.sample_rate_hz);
verifyGreaterThan(testCase, features.band_shares(3), 0.05);
verifyGreaterThan(testCase, features.band_shares(4), 5e-4);
peakRatioDb = 20 * log10(max(abs(result.layers.afterfire)) / ...
    sqrt(mean(result.layers.exhaust .^ 2)) + eps);
verifyLessThan(testCase, peakRatioDb, 10);
end

function testTorqueDrivesMainExhaust(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
loaded = v6_build_cycle(profile, "steady_4000", 1000);
unloaded = loaded;
unloaded.state.torque_nm(:) = 0;
[~, loadedResult] = v6_synthesize_engine_sound(profile, loaded);
[~, unloadedResult] = v6_synthesize_engine_sound(profile, unloaded);
verifyGreaterThan(testCase, sqrt(mean(loadedResult.layers.exhaust .^ 2)), ...
    2 * sqrt(mean(unloadedResult.layers.exhaust .^ 2)));
end

function testFullDemoPreservesAccelerationBody(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
scenario = v6_build_cycle(profile, "full_demo", 1000);
[audio, result] = v6_synthesize_engine_sound(profile, scenario);
acceleration = result.time_s >= 1 & result.time_s < 3.5;
verifyGreaterThanOrEqual(testCase, sqrt(mean(audio(acceleration) .^ 2)), 0.40);
verifyEqual(testCase, result.normalization_gain, 1, AbsTol=1e-12);
end

function testRaspAddsLoadGatedMidBandEnergy(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profile = v6_vehicle_profile("c63_w204");
scenario = v6_build_cycle(profile, "full_demo", 1000);
[~, result] = v6_synthesize_engine_sound(profile, scenario);
acceleration = result.time_s >= 1 & result.time_s < 8.5;
features = v6_reference_features(result.layers.rasp(acceleration), ...
    profile.audio.sample_rate_hz);
verifyGreaterThan(testCase, sqrt(mean(result.layers.rasp(acceleration) .^ 2)), 0.10);
verifyGreaterThan(testCase, features.band_shares(3), 0.35);
verifyGreaterThan(testCase, features.band_shares(4), 0.015);
lowLoad = result.state.load < 0.08;
verifyLessThan(testCase, sqrt(mean(result.layers.rasp(lowLoad) .^ 2)), 0.005);
end

function testProfileIsVehicleOwned(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
profilePath = fullfile(root, "vehicles", "c63_w204", "c63_w204_v6_profile.m");
verifyTrue(testCase, isfile(profilePath));
verifyError(testCase, @() v6_vehicle_profile("unknown_vehicle"), ...
    "jovi:soundv6:UnsupportedProfile");
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
