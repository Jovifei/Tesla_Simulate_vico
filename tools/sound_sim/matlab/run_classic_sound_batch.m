% Generate the first batch of classic engine-sound simulation artifacts.

scriptDir = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(scriptDir)));
outputDir = fullfile(projectRoot, "build", "sound-sim", "matlab-classics-v4");
addpath(scriptDir);
if ~isfolder(outputDir)
    mkdir(outputDir);
end

sampleRate = 48000;
profileNames = ["hellcat", "gtr_r35", "c63_w204", "supra_jza80", ...
    "rx7_fd", "lexus_lfa", "ferrari_458", "aventador_lp700"];
summaryRows = cell(numel(profileNames), 10);
comparisonRows = cell(numel(profileNames), 12);

for profileIndex = 1:numel(profileNames)
    profile = vehicle_profile(profileNames(profileIndex));
    [time, rpm, throttle, gear, speed] = build_demo_cycle(profile, sampleRate);
    [audio, trace, events] = synthesize_engine_sound( ...
        profile, time, rpm, throttle, gear, sampleRate);
    trace.speed_kmh = speed.';

    stem = char(profile.name);
    wavPath = fullfile(outputDir, stem + "_demo.wav");
    csvPath = fullfile(outputDir, stem + "_trace.csv");
    jsonPath = fullfile(outputDir, stem + "_params.json");
    pngPath = fullfile(outputDir, stem + "_analysis.png");
    backfirePath = fullfile(outputDir, stem + "_backfire_solo.wav");
    inductionPath = fullfile(outputDir, stem + "_induction_solo.wav");
    shiftPath = fullfile(outputDir, stem + "_shift_solo.wav");

    audiowrite(wavPath, audio.', sampleRate, BitsPerSample=16);
    audiowrite(backfirePath, normalize_stem(trace.backfire), sampleRate, BitsPerSample=16);
    audiowrite(inductionPath, normalize_stem(trace.induction), sampleRate, BitsPerSample=16);
    audiowrite(shiftPath, normalize_stem(trace.shift_transient), sampleRate, BitsPerSample=16);
    traceStep = max(1, round(sampleRate / 100));
    writetable(trace(1:traceStep:end, :), csvPath);

    payload = struct( ...
        "schema", "jovi.classic_engine_sound.v3", ...
        "sample_rate_hz", sampleRate, ...
        "duration_s", time(end) + 1 / sampleRate, ...
        "profile", profile, ...
        "backfire_events", events);
    write_text(jsonPath, jsonencode(payload, PrettyPrint=true));
    write_analysis_plot(pngPath, profile, time, speed, rpm, throttle, gear, audio, sampleRate);

    wavInfo = dir(wavPath);
    summaryRows(profileIndex, :) = {profile.name, time(end) + 1 / sampleRate, ...
        max(speed), nnz(diff(gear) ~= 0), nnz(diff(gear) < 0), ...
        max(abs(audio)), sqrt(mean(audio.^2)), ...
        numel(events.time_s), events.style, wavInfo.bytes};

    calibration = load_backfire_calibration(profile.name);
    targetFeatures = calibration_features(calibration, sampleRate);
    generatedFeatures = spectral_features(trace.backfire, sampleRate);
    comparisonRows(profileIndex, :) = {profile.name, events.style, ...
        targetFeatures(1), generatedFeatures(1), ...
        targetFeatures(2), generatedFeatures(2), ...
        targetFeatures(3), generatedFeatures(3), ...
        targetFeatures(4), generatedFeatures(4), ...
        targetFeatures(5), generatedFeatures(5)};
end

summary = cell2table(summaryRows, VariableNames=["profile", "duration_s", ...
    "max_speed_kmh", "shift_count", "downshift_count", "peak", "rms", ...
    "backfire_count", "backfire_style", "wav_bytes"]);
comparison = cell2table(comparisonRows, VariableNames=["profile", "backfire_style", ...
    "target_centroid_hz", "generated_centroid_hz", ...
    "target_share_20_250", "generated_share_20_250", ...
    "target_share_250_1000", "generated_share_250_1000", ...
    "target_share_1000_4000", "generated_share_1000_4000", ...
    "target_share_4000_12000", "generated_share_4000_12000"]);
writetable(summary, fullfile(outputDir, "summary.csv"));
writetable(comparison, fullfile(outputDir, "backfire_feature_comparison.csv"));
v3ComparisonPath = fullfile(projectRoot, "build", "sound-sim", ...
    "matlab-classics-v3", "backfire_feature_comparison.csv");
if isfile(v3ComparisonPath)
    v3 = readtable(v3ComparisonPath, TextType="string");
    commonProfiles = intersect(v3.profile, comparison.profile, "stable");
    v3 = v3(ismember(v3.profile, commonProfiles), :);
    v4 = comparison(ismember(comparison.profile, commonProfiles), :);
    v3v4 = table(v4.profile, v4.backfire_style, ...
        v3.generated_centroid_hz, v4.generated_centroid_hz, ...
        v3.generated_share_20_250, v4.generated_share_20_250, ...
        v3.generated_share_250_1000, v4.generated_share_250_1000, ...
        VariableNames=["profile", "backfire_style", "v3_centroid_hz", ...
        "v4_centroid_hz", "v3_share_20_250", "v4_share_20_250", ...
        "v3_share_250_1000", "v4_share_250_1000"]);
    writetable(v3v4, fullfile(outputDir, "v3_v4_backfire_comparison.csv"));
end
disp(summary);
disp(comparison);
fprintf("Artifacts: %s\n", outputDir);

function write_text(path, content)
fileId = fopen(path, "w", "n", "UTF-8");
if fileId < 0
    error("jovi:sound:FileOpen", "Cannot write %s", path);
end
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, content, "char");
end

function write_analysis_plot(path, profile, time, speed, rpm, throttle, gear, audio, sampleRate)
figureHandle = figure(Visible="off", Color="white", Position=[100, 100, 1200, 820]);
cleanup = onCleanup(@() close(figureHandle));
layout = tiledlayout(4, 1, TileSpacing="compact", Padding="compact");
title(layout, profile.display_name + " - MATLAB sound simulation");

nexttile;
plot(time, audio, Color=[0.12, 0.25, 0.45]);
xlabel("Time (s)");
ylabel("Amplitude");
grid on;

nexttile;
yyaxis left;
plot(time, speed, LineWidth=1.1);
ylabel("Speed (km/h)");
yyaxis right;
stairs(time, gear, LineWidth=1.0);
ylabel("Gear");
yticks(1:3);
xlabel("Time (s)");
grid on;

nexttile;
yyaxis left;
plot(time, rpm, LineWidth=1.1);
ylabel("RPM");
yyaxis right;
plot(time, throttle, LineWidth=1.0);
ylabel("Throttle");
xlabel("Time (s)");
grid on;

nexttile;
sampleCount = numel(audio);
window = 0.5 - 0.5 * cos(2 * pi * (0:sampleCount - 1) / max(1, sampleCount - 1));
spectrum = abs(fft(audio .* window));
frequency = (0:sampleCount - 1) * sampleRate / sampleCount;
limit = frequency <= 10000;
plot(frequency(limit), 20 * log10(spectrum(limit) / max(spectrum) + 1e-8));
xlabel("Frequency (Hz)");
ylabel("Magnitude (dB)");
ylim([-80, 0]);
grid on;

exportgraphics(figureHandle, path, Resolution=140);
end

function output = normalize_stem(input)
peak = max(abs(input));
if peak > 0
    output = 0.90 * input / peak;
else
    output = input;
end
end

function features = spectral_features(audio, sampleRate)
if ~any(audio)
    features = zeros(1, 5);
    return
end
windowLength = 4096;
[spectrum, frequency] = spectrogram(audio, hann(windowLength, "periodic"), ...
    round(0.75 * windowLength), windowLength, sampleRate);
powerSpectrum = abs(spectrum).^2;
totalByFrame = sum(powerSpectrum, 1) + eps;
centroid = sum(frequency .* powerSpectrum, 1) ./ totalByFrame;
active = totalByFrame >= prctile(totalByFrame, 90) ...
    & totalByFrame > max(totalByFrame) * 1e-8;
activePower = powerSpectrum(:, active);
total = sum(activePower, "all") + eps;
bands = [20, 250; 250, 1000; 1000, 4000; 4000, 12000];
shares = zeros(1, 4);
for index = 1:size(bands, 1)
    mask = frequency >= bands(index, 1) & frequency < bands(index, 2);
    shares(index) = sum(activePower(mask, :), "all") / total;
end
features = [median(centroid(active)), shares];
end

function features = calibration_features(calibration, sampleRate)
[response, frequency] = freqz(calibration.fir, 1, 8192, sampleRate);
powerSpectrum = abs(response).^2;
total = sum(powerSpectrum) + eps;
centroid = sum(frequency .* powerSpectrum) / total;
bands = [20, 250; 250, 1000; 1000, 4000; 4000, 12000];
shares = zeros(1, 4);
for index = 1:size(bands, 1)
    mask = frequency >= bands(index, 1) & frequency < bands(index, 2);
    shares(index) = sum(powerSpectrum(mask)) / total;
end
features = [centroid, shares];
end
