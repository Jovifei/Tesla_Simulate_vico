% Render four engine layouts on the same normalized RPM/throttle cycle.

scriptDir = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(scriptDir)));
outputDir = fullfile(projectRoot, "build", "sound-sim", ...
    "engine-layout-comparison");
addpath(scriptDir);
if ~isfolder(outputDir)
    mkdir(outputDir);
end

sampleRate = 48000;
duration = 14;
time = 0:1 / sampleRate:duration - 1 / sampleRate;
profileNames = ["corvette_ls3", "supra_jza80", ...
    "lexus_lfa", "aventador_lp700"];
categoryNames = ["american_na_v8", "turbo_inline_6", ...
    "high_rev_v10", "high_rev_v12"];
summaryRows = cell(numel(profileNames), 10);
reel = [];
cueRows = cell(numel(profileNames), 4);

for profileIndex = 1:numel(profileNames)
    profile = vehicle_profile(profileNames(profileIndex));
    profile.backfire_enabled = false;
    [rpm, throttle] = comparison_cycle(profile, time);
    gear = ones(size(time));
    [audio, trace] = synthesize_engine_sound( ...
        profile, time, rpm, throttle, gear, sampleRate);

    stem = categoryNames(profileIndex);
    mainPath = fullfile(outputDir, stem + "_demo.wav");
    exhaustPath = fullfile(outputDir, stem + "_exhaust_solo.wav");
    inductionPath = fullfile(outputDir, stem + "_induction_solo.wav");
    tracePath = fullfile(outputDir, stem + "_trace.csv");
    audiowrite(mainPath, audio.', sampleRate, BitsPerSample=16);
    audiowrite(exhaustPath, normalize_layer(trace.exhaust), ...
        sampleRate, BitsPerSample=16);
    audiowrite(inductionPath, normalize_layer(trace.induction), ...
        sampleRate, BitsPerSample=16);
    writetable(trace(1:round(sampleRate / 100):end, :), tracePath);

    features = audio_features(audio, sampleRate);
    summaryRows(profileIndex, :) = {categoryNames(profileIndex), ...
        profile.name, profile.display_name, profile.layout, ...
        max(trace.firing_hz), features(1), features(2), features(3), ...
        features(4), rms(trace.induction) / (rms(trace.exhaust) + eps)};
    startSeconds = numel(reel) / sampleRate;
    cueRows(profileIndex, :) = {categoryNames(profileIndex), ...
        profile.display_name, startSeconds, duration};
    reel = [reel, audio, zeros(1, round(0.8 * sampleRate))]; %#ok<AGROW>
end

summary = cell2table(summaryRows, VariableNames=["category", "profile", ...
    "vehicle", "layout", "max_firing_hz", "centroid_hz", ...
    "share_20_250", "share_250_1000", "share_1000_6000", ...
    "induction_exhaust_rms_ratio"]);
cues = cell2table(cueRows, VariableNames=["category", "vehicle", ...
    "start_s", "duration_s"]);
writetable(summary, fullfile(outputDir, "layout_summary.csv"));
writetable(cues, fullfile(outputDir, "comparison_reel_cues.csv"));
audiowrite(fullfile(outputDir, "engine_layout_comparison_reel.wav"), ...
    reel.', sampleRate, BitsPerSample=16);
disp(summary);
disp(cues);
fprintf("Artifacts: %s\n", outputDir);

function [rpm, throttle] = comparison_cycle(profile, time)
rpm = profile.idle_rpm * ones(size(time));
throttle = 0.06 * ones(size(time));

pull = time >= 1 & time < 7;
u = (time(pull) - 1) / 6;
blend = u.^2 .* (3 - 2 * u);
rpm(pull) = profile.idle_rpm + ...
    (0.96 * profile.redline_rpm - profile.idle_rpm) .* blend;
throttle(pull) = 0.82;

hold = time >= 7 & time < 8;
rpm(hold) = 0.96 * profile.redline_rpm;
throttle(hold) = 0.94;

overrun = time >= 8 & time < 12;
u = (time(overrun) - 8) / 4;
blend = u.^2 .* (3 - 2 * u);
rpm(overrun) = 0.96 * profile.redline_rpm + ...
    (profile.idle_rpm - 0.96 * profile.redline_rpm) .* blend;
throttle(overrun) = 0.08;
end

function output = normalize_layer(input)
peak = max(abs(input));
if peak > 0
    output = 0.9 * input / peak;
else
    output = input;
end
end

function features = audio_features(audio, sampleRate)
[spectrum, frequency] = spectrogram(audio, hann(4096, "periodic"), ...
    3072, 4096, sampleRate);
powerSpectrum = abs(spectrum).^2;
framePower = sum(powerSpectrum, 1) + eps;
active = framePower >= prctile(framePower, 60);
powerSpectrum = powerSpectrum(:, active);
total = sum(powerSpectrum, "all") + eps;
centroid = sum(frequency .* sum(powerSpectrum, 2)) / total;
bands = [20, 250; 250, 1000; 1000, 6000];
shares = zeros(1, 3);
for index = 1:size(bands, 1)
    mask = frequency >= bands(index, 1) & frequency < bands(index, 2);
    shares(index) = sum(powerSpectrum(mask, :), "all") / total;
end
features = [centroid, shares];
end
