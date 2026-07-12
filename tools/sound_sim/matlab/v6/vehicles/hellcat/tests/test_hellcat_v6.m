function tests = test_hellcat_v6
tests = functiontests(localfunctions);
end

function testIndependentProfile(testCase)
root = fileparts(fileparts(fileparts(fileparts(mfilename("fullpath")))));
addpath(root);
profile = v6_vehicle_profile("hellcat");
verifyEqual(testCase, profile.engine.displacement_l, 6.166, AbsTol=1e-12);
verifyEqual(testCase, profile.engine.firing_order, [1, 8, 4, 3, 6, 5, 7, 2]);
verifyEqual(testCase, profile.engine.redline_rpm, 6200);
verifyTrue(testCase, profile.induction.enabled);
verifyEqual(testCase, profile.afterfire.calibration, "hellcat");
end

function testFullDemoHasHellcatLayers(testCase)
root = fileparts(fileparts(fileparts(fileparts(mfilename("fullpath")))));
addpath(root);
profile = v6_vehicle_profile("hellcat");
scenario = v6_build_cycle(profile, "full_demo", 1000);
[audio, result] = v6_synthesize_engine_sound(profile, scenario);
verifyTrue(testCase, all(isfinite(audio)));
verifyLessThanOrEqual(testCase, max(abs(audio)), profile.audio.peak_limit + 1e-9);
verifyGreaterThan(testCase, sqrt(mean(result.layers.exhaust .^ 2)), 0.10);
verifyGreaterThan(testCase, sqrt(mean(result.layers.induction .^ 2)), 0.005);
verifyGreaterThan(testCase, max(abs(result.layers.afterfire)), 0.02);
verifyGreaterThan(testCase, std(result.state.combustion_variation), 0.03);
end

function testHellcatDiffersFromC63(testCase)
root = fileparts(fileparts(fileparts(fileparts(mfilename("fullpath")))));
addpath(root);
hellcat = v6_vehicle_profile("hellcat");
c63 = v6_vehicle_profile("c63_w204");
verifyNotEqual(testCase, hellcat.engine.firing_order, c63.engine.firing_order);
verifyLessThan(testCase, hellcat.engine.redline_rpm, c63.engine.redline_rpm);
verifyNotEqual(testCase, hellcat.exhaust.primary_left_m, c63.exhaust.primary_left_m);
end
