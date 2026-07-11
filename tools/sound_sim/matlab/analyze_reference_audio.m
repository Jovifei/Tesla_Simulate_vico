% Extract comparable spectral and transient features from reference audio.

scriptDir = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(scriptDir)));
inputDir = "E:\Claude_allow\Download\tesla-sound-research";
outputDir = fullfile(projectRoot, "build", "sound-sim", "reference-analysis");
if ~isfolder(outputDir)
    mkdir(outputDir);
end

items = [ ...
    struct("name", "hellcat_stock_accel", "vehicle", "hellcat", "kind", "acceleration"), ...
    struct("name", "hellcat_redeye_downshift", "vehicle", "hellcat", "kind", "backfire"), ...
    struct("name", "gtr_r35_nismo_accel", "vehicle", "gtr_r35", "kind", "acceleration"), ...
    struct("name", "gtr_r35_tuned_backfire", "vehicle", "gtr_r35", "kind", "backfire"), ...
    struct("name", "c63_w204_performance_accel", "vehicle", "c63_w204", "kind", "acceleration"), ...
    struct("name", "c63_w204_headers_backfire", "vehicle", "c63_w204", "kind", "backfire")];

summaryRows = cell(numel(items), 11);
allEvents = table();
for itemIndex = 1:numel(items)
    item = items(itemIndex);
    inputPath = fullfile(inputDir, item.name + ".wav");
    fprintf("[%d/%d] Analyze %s\n", itemIndex, numel(items), item.name);
    [audio, sampleRate] = audioread(inputPath);
    audio = mean(audio, 2);
    audio = audio - mean(audio);
    peak = max(abs(audio));
    if peak > 0
        audio = audio / peak;
    end

    windowLength = 4096;
    hopLength = 1024;
    overlapLength = windowLength - hopLength;
    [spectrum, frequency, frameTime] = spectrogram( ...
        audio, hann(windowLength, "periodic"), overlapLength, windowLength, sampleRate);
    powerSpectrum = abs(spectrum).^2;
    framePower = mean(powerSpectrum, 1) + eps;
    frameDb = 10 * log10(framePower);
    spectralSum = sum(powerSpectrum, 1) + eps;
    centroid = sum(frequency .* powerSpectrum, 1) ./ spectralSum;

    normalizedSpectrum = powerSpectrum ./ spectralSum;
    flux = [0, sum(max(diff(sqrt(normalizedSpectrum), 1, 2), 0), 1)];
    positiveRise = [0, max(diff(frameDb), 0)];
    transientScore = robust_z(flux) + 0.65 * robust_z(positiveRise);
    eventFrames = select_events(transientScore, frameTime, 30, 0.08);
    events = build_event_table(item, eventFrames, frameTime, frameDb, centroid, ...
        powerSpectrum, frequency, audio, sampleRate);
    allEvents = [allEvents; events]; %#ok<AGROW>

    highEnergy = frameDb >= prctile(frameDb, 70);
    bandShares = frequency_band_shares(powerSpectrum(:, highEnergy), frequency);
    transientCentroid = NaN;
    transientDuration = NaN;
    if ~isempty(events)
        transientCentroid = median(events.centroid_hz);
        transientDuration = median(events.duration_ms);
    end
    summaryRows(itemIndex, :) = {item.name, item.vehicle, item.kind, ...
        numel(audio) / sampleRate, sqrt(mean(audio.^2)), ...
        median(centroid(highEnergy)), bandShares(1), bandShares(2), ...
        bandShares(3), bandShares(4), height(events)};

    plot_analysis(outputDir, item, audio, sampleRate, frameTime, frequency, ...
        powerSpectrum, transientScore, eventFrames, transientCentroid, transientDuration);
end

summary = cell2table(summaryRows, VariableNames=[ ...
    "source", "vehicle", "kind", "duration_s", "rms", "centroid_hz", ...
    "share_20_250", "share_250_1000", "share_1000_4000", "share_4000_12000", "event_count"]);
writetable(summary, fullfile(outputDir, "reference_summary.csv"));
writetable(allEvents, fullfile(outputDir, "reference_events.csv"));
disp(summary);
fprintf("Reference analysis: %s\n", outputDir);

function z = robust_z(values)
center = median(values);
scale = 1.4826 * median(abs(values - center)) + eps;
z = max(0, (values - center) / scale);
end

function selected = select_events(score, time, maxCount, minimumGap)
if numel(score) < 3
    selected = [];
    return
end
threshold = prctile(score, 94);
candidates = find(score(2:end - 1) >= score(1:end - 2) ...
    & score(2:end - 1) > score(3:end) & score(2:end - 1) >= threshold) + 1;
[~, order] = sort(score(candidates), "descend");
selected = [];
for candidate = candidates(order)
    if isempty(selected) || all(abs(time(candidate) - time(selected)) >= minimumGap)
        selected(end + 1) = candidate; %#ok<AGROW>
        if numel(selected) >= maxCount
            break
        end
    end
end
selected = sort(selected);
end

function events = build_event_table(item, eventFrames, frameTime, frameDb, centroid, ...
    powerSpectrum, frequency, audio, sampleRate)
count = numel(eventFrames);
source = repmat(item.name, count, 1);
vehicle = repmat(item.vehicle, count, 1);
kind = repmat(item.kind, count, 1);
time_s = zeros(count, 1);
peak_db = zeros(count, 1);
centroid_hz = zeros(count, 1);
high_band_share = zeros(count, 1);
duration_ms = zeros(count, 1);
for eventIndex = 1:count
    frame = eventFrames(eventIndex);
    time_s(eventIndex) = frameTime(frame);
    peak_db(eventIndex) = frameDb(frame);
    centroid_hz(eventIndex) = centroid(frame);
    column = powerSpectrum(:, frame);
    high_band_share(eventIndex) = sum(column(frequency >= 2500 & frequency < 12000)) / (sum(column) + eps);
    duration_ms(eventIndex) = transient_duration(audio, sampleRate, time_s(eventIndex));
end
events = table(source, vehicle, kind, time_s, peak_db, centroid_hz, high_band_share, duration_ms);
end

function durationMs = transient_duration(audio, sampleRate, eventTime)
center = max(1, round(eventTime * sampleRate));
startIndex = max(1, center - round(0.03 * sampleRate));
endIndex = min(numel(audio), center + round(0.30 * sampleRate));
segment = abs(audio(startIndex:endIndex));
envelope = movmean(segment, max(1, round(0.003 * sampleRate)));
[eventPeak, peakIndex] = max(envelope);
baseline = median(envelope(1:max(1, peakIndex - round(0.01 * sampleRate))));
threshold = max(2.5 * baseline, 0.12 * eventPeak);
tail = find(envelope(peakIndex:end) < threshold, 1, "first");
if isempty(tail)
    tail = numel(envelope) - peakIndex + 1;
end
durationMs = 1000 * max(1, tail - 1) / sampleRate;
end

function shares = frequency_band_shares(powerSpectrum, frequency)
bands = [20, 250; 250, 1000; 1000, 4000; 4000, 12000];
total = sum(powerSpectrum, "all") + eps;
shares = zeros(1, size(bands, 1));
for bandIndex = 1:size(bands, 1)
    mask = frequency >= bands(bandIndex, 1) & frequency < bands(bandIndex, 2);
    shares(bandIndex) = sum(powerSpectrum(mask, :), "all") / total;
end
end

function plot_analysis(outputDir, item, audio, sampleRate, frameTime, frequency, ...
    powerSpectrum, transientScore, eventFrames, transientCentroid, transientDuration)
figureHandle = figure(Visible="off", Color="white", Position=[100, 100, 1300, 850]);
cleanup = onCleanup(@() close(figureHandle));
layout = tiledlayout(3, 1, TileSpacing="compact", Padding="compact");
title(layout, item.name + " | median transient centroid=" + round(transientCentroid) ...
    + " Hz | duration=" + round(transientDuration) + " ms");

nexttile;
decimation = max(1, floor(numel(audio) / 150000));
plot((0:decimation:numel(audio) - 1) / sampleRate, audio(1:decimation:end));
xlabel("Time (s)");
ylabel("Amplitude");
grid on;

nexttile;
limit = frequency <= 12000;
imagesc(frameTime, frequency(limit), 10 * log10(powerSpectrum(limit, :) + eps));
axis xy;
clim(max(clim) + [-75, 0]);
xlabel("Time (s)");
ylabel("Frequency (Hz)");
colormap turbo;

nexttile;
plot(frameTime, transientScore, LineWidth=0.9);
hold on;
if ~isempty(eventFrames)
    scatter(frameTime(eventFrames), transientScore(eventFrames), 20, "filled");
end
xlabel("Time (s)");
ylabel("Transient score");
grid on;

exportgraphics(figureHandle, fullfile(outputDir, item.name + "_reference.png"), Resolution=130);
end
