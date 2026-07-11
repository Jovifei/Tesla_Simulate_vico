function tests = test_sound_synthesis
tests = functiontests(localfunctions);
end

function testProfiles(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);

hellcat = vehicle_profile("hellcat");
gtr = vehicle_profile("gtr_r35");
c63 = vehicle_profile("c63_w204");
supra = vehicle_profile("supra_jza80");
rx7 = vehicle_profile("rx7_fd");
lfa = vehicle_profile("lexus_lfa");
ferrari = vehicle_profile("ferrari_458");
aventador = vehicle_profile("aventador_lp700");
corvette = vehicle_profile("corvette_ls3");

verifyEqual(testCase, hellcat.cylinders, 8);
verifyEqual(testCase, hellcat.induction, "supercharger");
verifyEqual(testCase, hellcat.backfire_style, "low_boom");
verifyEqual(testCase, gtr.cylinders, 6);
verifyEqual(testCase, gtr.induction, "twin_turbo");
verifyEqual(testCase, gtr.backfire_style, "metallic_crackle");
verifyEqual(testCase, c63.cylinders, 8);
verifyEqual(testCase, c63.induction, "naturally_aspirated");
verifyEqual(testCase, c63.backfire_style, "amg_bang");
verifyEqual(testCase, supra.firing_order, [1, 5, 3, 6, 2, 4]);
verifyEqual(testCase, rx7.cycle_revolutions, 3);
verifyEqual(testCase, lfa.cylinders, 10);
verifyEqual(testCase, ferrari.layout, "flat_plane_v8");
verifyEqual(testCase, aventador.cylinders, 12);
verifyEqual(testCase, corvette.firing_order, [1, 8, 7, 2, 6, 5, 4, 3]);
verifyEqual(testCase, corvette.layout, "cross_plane_v8");
end

function testCycleAndSynthesis(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
sampleRate = 48000;
profile = vehicle_profile("hellcat");
[time, rpm, throttle, gear, speed] = build_demo_cycle(profile, sampleRate);

verifyEqual(testCase, numel(time), numel(rpm));
verifyEqual(testCase, numel(time), numel(throttle));
verifyEqual(testCase, numel(time), numel(gear));
verifyEqual(testCase, numel(time), numel(speed));
verifyEqual(testCase, speed(1), 0, AbsTol=1e-9);
verifyGreaterThan(testCase, max(speed), 80);
verifyEqual(testCase, unique(gear), [1, 2, 3]);
verifyEqual(testCase, nnz(diff(gear) > 0), 2);
verifyEqual(testCase, nnz(diff(gear) < 0), 2);
verifyGreaterThanOrEqual(testCase, min(rpm), profile.idle_rpm - 1);
verifyLessThanOrEqual(testCase, max(rpm), profile.redline_rpm + 1);
verifyGreaterThanOrEqual(testCase, nnz(diff(throttle) < -0.35), 2);

[audio, trace, events] = synthesize_engine_sound( ...
    profile, time, rpm, throttle, gear, sampleRate);
verifySize(testCase, audio, size(time));
verifyTrue(testCase, all(isfinite(audio)));
verifyLessThanOrEqual(testCase, max(abs(audio)), 1.0);
verifyGreaterThan(testCase, sqrt(mean(audio.^2)), 0.02);
verifyGreaterThanOrEqual(testCase, numel(events.time_s), 2);
verifyTrue(testCase, all(ismember(["upshift", "downshift", "overrun"], ...
    unique(events.type))));
verifyEqual(testCase, height(trace), numel(time));
verifyTrue(testCase, ismember("shift_transient", string(trace.Properties.VariableNames)));
verifyGreaterThan(testCase, max(abs(trace.shift_transient)), 0);
end

function testDeterministicOutput(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
sampleRate = 48000;
profile = vehicle_profile("gtr_r35");
[time, rpm, throttle, gear] = build_demo_cycle(profile, sampleRate);
[audioA, ~, eventsA] = synthesize_engine_sound( ...
    profile, time, rpm, throttle, gear, sampleRate);
[audioB, ~, eventsB] = synthesize_engine_sound( ...
    profile, time, rpm, throttle, gear, sampleRate);

verifyEqual(testCase, audioA, audioB);
verifyEqual(testCase, eventsA.time_s, eventsB.time_s);
end

function testCalibrationAndShiftStyles(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
names = ["hellcat", "gtr_r35", "c63_w204", "supra_jza80", ...
    "rx7_fd", "lexus_lfa", "ferrari_458", "aventador_lp700"];
decays = zeros(size(names));
clusters = zeros(size(names));
minimumShiftGain = zeros(size(names));
for index = 1:numel(names)
    calibration = load_backfire_calibration(names(index));
    verifySize(testCase, calibration.fir, [65, 1]);
    verifyTrue(testCase, all(isfinite(calibration.fir)));
    decays(index) = calibration.decay_ms;
    clusters(index) = calibration.cluster_size;

    profile = vehicle_profile(names(index));
    [time, rpm, throttle, gear] = build_demo_cycle(profile, 48000);
    [~, trace] = synthesize_engine_sound( ...
        profile, time, rpm, throttle, gear, 48000);
    minimumShiftGain(index) = min(trace.shift_gain);
end

verifyGreaterThan(testCase, range(decays), 50);
verifyGreaterThanOrEqual(testCase, numel(unique(clusters)), 3);
verifyEqual(testCase, minimumShiftGain, ...
    [0.25, 0.62, 0.28, 0.12, 0.12, 0.08, 0.70, 0.18], AbsTol=1e-9);
end

function testVehicleBackfiresAreDistinct(testCase)
root = fileparts(fileparts(mfilename("fullpath")));
addpath(root);
sampleRate = 48000;
names = ["hellcat", "gtr_r35", "c63_w204", "supra_jza80", ...
    "rx7_fd", "lexus_lfa", "ferrari_458", "aventador_lp700"];
backfires = cell(1, numel(names));
styles = strings(1, numel(names));
for index = 1:numel(names)
    profile = vehicle_profile(names(index));
    [time, rpm, throttle, gear] = build_demo_cycle(profile, sampleRate);
    [~, trace, events] = synthesize_engine_sound( ...
        profile, time, rpm, throttle, gear, sampleRate);
    backfires{index} = trace.backfire;
    styles(index) = events.style;
end

verifyEqual(testCase, numel(unique(styles)), numel(names));
for left = 1:numel(names)
    for right = left + 1:numel(names)
        similarity = abs(corr(backfires{left}, backfires{right}));
        verifyLessThan(testCase, similarity, 0.75);
    end
end
end
