% Derive non-audio backfire parameters from temporary reference recordings.

scriptDir = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(scriptDir)));
inputDir = "E:\Claude_allow\Download\tesla-sound-research";
outputDir = fullfile(projectRoot, "build", "sound-sim", "backfire-calibration");
calibrationDir = fullfile(scriptDir, "calibration");
if ~isfolder(outputDir)
    mkdir(outputDir);
end
if ~isfolder(calibrationDir)
    mkdir(calibrationDir);
end

groups = [ ...
    struct("profile", "hellcat", "style", "low_boom", "sources", [ ...
        "hellcat_redeye_downshift", "hellcat_redeye_leave", "hellcat_burble_tune"]), ...
    struct("profile", "gtr_r35", "style", "metallic_crackle", "sources", [ ...
        "gtr_r35_tuned_backfire", "gtr_r35_tomei_close"]), ...
    struct("profile", "c63_w204", "style", "amg_bang", "sources", [ ...
        "c63_w204_headers_backfire", "c63_w204_close_downshift"]), ...
    struct("profile", "supra_jza80", "style", "turbo_burble", ...
        "sources", "supra_jza80_stock"), ...
    struct("profile", "rx7_fd", "style", "rotary_flame", ...
        "sources", "rx7_fd_13brew"), ...
    struct("profile", "lexus_lfa", "style", "v10_overrun", ...
        "sources", "lfa_full_accel"), ...
    struct("profile", "ferrari_458", "style", "flatplane_crack", ...
        "sources", "ferrari_458_accel"), ...
    struct("profile", "aventador_lp700", "style", "v12_bark", ...
        "sources", "aventador_lp700_accel")];

calibrations = cell(1, numel(groups));
catalog = table();
for groupIndex = 1:numel(groups)
    group = groups(groupIndex);
    fprintf("[%d/%d] Calibrate %s\n", groupIndex, numel(groups), group.profile);
    maximumSegments = 14 * numel(group.sources);
    segments = cell(1, maximumSegments);
    segmentCount = 0;
    residualPower = [];
    attackValues = nan(1, maximumSegments);
    decayValues = nan(1, maximumSegments);
    intervalCells = cell(1, maximumSegments);
    clusterSizes = nan(1, maximumSegments);

    for sourceIndex = 1:numel(group.sources)
        source = group.sources(sourceIndex);
        [audio, sampleRate] = audioread(fullfile(inputDir, source + ".wav"));
        audio = mean(audio, 2);
        audio = audio - mean(audio);
        audio = audio / (max(abs(audio)) + eps);
        eventSamples = detect_backfire_events(audio, sampleRate, 14);
        eventTimes = (eventSamples - 1) / sampleRate;

        for eventIndex = 1:numel(eventSamples)
            [segment, residual, attackMs, decayMs, popIntervals, ...
                clusterSize, contrastDb] = extract_event( ...
                audio, sampleRate, eventSamples(eventIndex), group.style);
            if isempty(segment)
                continue
            end
            segmentCount = segmentCount + 1;
            segments{segmentCount} = segment;
            if isempty(residualPower)
                residualPower = residual;
            else
                residualPower = residualPower + residual;
            end
            attackValues(segmentCount) = attackMs;
            decayValues(segmentCount) = decayMs;
            intervalCells{segmentCount} = reshape(popIntervals, 1, []);
            clusterSizes(segmentCount) = clusterSize;
            row = table(group.profile, source, eventTimes(eventIndex), ...
                attackMs, decayMs, clusterSize, contrastDb, max(abs(segment)), ...
                VariableNames=["profile", "source", "time_s", ...
                "attack_ms", "decay_ms", "cluster_size", ...
                "contrast_db", "peak"]);
            catalog = [catalog; row]; %#ok<AGROW>
        end
    end

    segments = segments(1:segmentCount);
    attackValues = attackValues(1:segmentCount);
    decayValues = decayValues(1:segmentCount);
    intervalValues = [intervalCells{1:segmentCount}];
    clusterSizes = clusterSizes(1:segmentCount);
    calibration = fit_calibration(group, segments, residualPower, ...
        attackValues, decayValues, intervalValues, clusterSizes, sampleRate);
    calibrations{groupIndex} = calibration;
    plot_event_montage(outputDir, group, segments, sampleRate);
    plot_calibration(outputDir, calibration, sampleRate);
end

calibrationProfiles = [calibrations{:}];
payload = struct( ...
    "schema", "jovi.backfire_calibration.v1", ...
    "generated_at", string(datetime("now", TimeZone="Asia/Shanghai", ...
        Format="yyyy-MM-dd'T'HH:mm:ssXXX")), ...
    "source_audio_policy", "Derived parameters only; source audio is not redistributed.", ...
    "profiles", calibrationProfiles);
jsonPath = fullfile(calibrationDir, "backfire_calibration.json");
write_text(jsonPath, jsonencode(payload, PrettyPrint=true));
writetable(catalog, fullfile(outputDir, "event_catalog.csv"));
disp(struct2table(calibrationProfiles));
fprintf("Calibration JSON: %s\n", jsonPath);

function eventSamples = detect_backfire_events(audio, sampleRate, maxEvents)
filtered = highpass(audio, 35, sampleRate);
filtered = lowpass(filtered, 9000, sampleRate);
step = max(1, round(0.001 * sampleRate));
envelope = sqrt(movmean(filtered.^2, max(3, round(0.0025 * sampleRate))));
frameEnvelope = envelope(1:step:end);
frameDb = 20 * log10(frameEnvelope + 1e-7);
rise = max([0; diff(frameDb)], 0);
score = movmean(rise, 3);
scale = 1.4826 * median(abs(score - median(score))) + eps;
prominence = max(1.5, 4.0 * scale);
[~, locations, ~, prominences] = findpeaks(score, ...
    MinPeakDistance=55, MinPeakProminence=prominence);

valid = locations > 350 & locations < numel(frameEnvelope) - 300;
locations = locations(valid);
prominences = prominences(valid);
contrast = zeros(size(locations));
for index = 1:numel(locations)
    location = locations(index);
    baseline = median(frameDb(max(1, location - 80):max(1, location - 20)));
    eventPeak = max(frameDb(location:min(numel(frameDb), location + 35)));
    contrast(index) = eventPeak - baseline;
end
valid = contrast >= 5.5;
locations = locations(valid);
prominences = prominences(valid);
contrast = contrast(valid);
[~, order] = sort(prominences + 0.5 * contrast, "descend");
order = order(1:min(maxEvents, numel(order)));
eventSamples = sort((locations(order) - 1) * step + 1);
end

function [segment, residual, attackMs, decayMs, intervalsMs, ...
    clusterSize, contrastDb] = extract_event(audio, sampleRate, onset, style)
postLength = round(0.24 * sampleRate);
preLength = postLength;
guardLength = round(0.02 * sampleRate);
if onset - preLength - guardLength < 1 || onset + postLength - 1 > numel(audio)
    segment = [];
    residual = [];
    attackMs = NaN;
    decayMs = NaN;
    intervalsMs = [];
    clusterSize = 0;
    contrastDb = NaN;
    return
end

segment = audio(onset:onset + postLength - 1);
background = audio(onset - preLength - guardLength:onset - guardLength - 1);
switch style
    case "low_boom"
        eventBand = bandpass(segment, [35, 850], sampleRate);
        backgroundBand = bandpass(background, [35, 850], sampleRate);
        decayThreshold = 0.12;
        sustainMs = 8;
    case "metallic_crackle"
        eventBand = bandpass(segment, [500, 9000], sampleRate);
        backgroundBand = bandpass(background, [500, 9000], sampleRate);
        decayThreshold = 0.20;
        sustainMs = 3;
    case "turbo_burble"
        eventBand = bandpass(segment, [120, 5200], sampleRate);
        backgroundBand = bandpass(background, [120, 5200], sampleRate);
        decayThreshold = 0.15;
        sustainMs = 5;
    case "rotary_flame"
        eventBand = bandpass(segment, [80, 7500], sampleRate);
        backgroundBand = bandpass(background, [80, 7500], sampleRate);
        decayThreshold = 0.14;
        sustainMs = 5;
    case {"v10_overrun", "flatplane_crack"}
        eventBand = bandpass(segment, [350, 11000], sampleRate);
        backgroundBand = bandpass(background, [350, 11000], sampleRate);
        decayThreshold = 0.19;
        sustainMs = 3;
    case "v12_bark"
        eventBand = bandpass(segment, [100, 8500], sampleRate);
        backgroundBand = bandpass(background, [100, 8500], sampleRate);
        decayThreshold = 0.15;
        sustainMs = 4;
    otherwise
        eventBand = bandpass(segment, [120, 6500], sampleRate);
        backgroundBand = bandpass(background, [120, 6500], sampleRate);
        decayThreshold = 0.16;
        sustainMs = 4;
end
envelopeWindow = max(3, round(0.0015 * sampleRate));
eventRms = sqrt(movmean(eventBand.^2, envelopeWindow));
backgroundRms = sqrt(movmean(backgroundBand.^2, envelopeWindow));
baseline = median(backgroundRms);
residualEnvelope = sqrt(max(eventRms.^2 - baseline^2, 0));
residualEnvelope = movmean(residualEnvelope, max(3, round(0.001 * sampleRate)));
contrastDb = 20 * log10((max(eventRms) + eps) / (baseline + eps));
if contrastDb < 6 || max(residualEnvelope) < 0.015
    segment = [];
    residual = [];
    attackMs = NaN;
    decayMs = NaN;
    intervalsMs = [];
    clusterSize = 0;
    return
end

nfft = 16384;
eventWindow = hann(numel(segment), "periodic");
background = background(1:numel(segment));
backgroundWindow = hann(numel(background), "periodic");
eventSpectrum = abs(fft(segment .* eventWindow, nfft)).^2;
backgroundSpectrum = abs(fft(background .* backgroundWindow, nfft)).^2;
residual = max(eventSpectrum(1:nfft / 2 + 1) - backgroundSpectrum(1:nfft / 2 + 1), 0);

normalizedEnvelope = residualEnvelope / (max(residualEnvelope) + eps);
[~, peakIndex] = max(normalizedEnvelope(1:min(end, round(0.045 * sampleRate))));
attackMs = 1000 * (peakIndex - 1) / sampleRate;

tail = normalizedEnvelope(peakIndex:end);
sustainSamples = max(2, round(sustainMs * 0.001 * sampleRate));
futureMaximum = movmax(tail, [0, sustainSamples - 1]);
decayIndex = find(futureMaximum < decayThreshold, 1);
if isempty(decayIndex)
    decayIndex = min(numel(tail), round(0.14 * sampleRate));
end
decayMs = max(2, 1000 * (decayIndex - 1) / sampleRate);

clusterLimit = min(numel(normalizedEnvelope), round(0.20 * sampleRate));
transientBand = highpass(segment, 700, sampleRate);
transientEnvelope = sqrt(movmean(transientBand.^2, ...
    max(3, round(0.001 * sampleRate))));
transientPeak = max(transientEnvelope);
if transientPeak > eps
    transientEnvelope = transientEnvelope / transientPeak;
end
interiorPeak = max(transientEnvelope(2:max(2, clusterLimit - 1)));
if transientPeak > eps && interiorPeak >= 0.35
    popLocations = separated_local_peaks(transientEnvelope(1:clusterLimit), ...
        0.35, round(0.018 * sampleRate));
else
    popLocations = [];
end
clusterSize = max(1, numel(popLocations));
intervalsMs = 1000 * diff(popLocations) / sampleRate;
end

function locations = separated_local_peaks(values, minimumHeight, minimumDistance)
candidates = find(values(2:end - 1) > values(1:end - 2) & ...
    values(2:end - 1) >= values(3:end)) + 1;
candidates = candidates(values(candidates) >= minimumHeight);
[~, order] = sort(values(candidates), "descend");
selected = zeros(1, numel(candidates));
selectedCount = 0;
for index = reshape(order, 1, [])
    candidate = candidates(index);
    if selectedCount == 0 || all(abs(candidate - selected(1:selectedCount)) >= minimumDistance)
        selectedCount = selectedCount + 1;
        selected(selectedCount) = candidate;
    end
end
locations = sort(selected(1:selectedCount));
end

function calibration = fit_calibration(group, segments, residualPower, ...
    attacks, decays, intervals, clusterSizes, sampleRate)
if isempty(segments) || isempty(residualPower)
    error("jovi:sound:NoCalibrationEvents", "No valid events for %s", group.profile);
end

frequency = linspace(0, sampleRate / 2, numel(residualPower)).';
magnitude = sqrt(residualPower / numel(segments));
magnitude = movmean(magnitude, 41);
magnitude = magnitude / (max(magnitude) + eps);
frequencyNodes = linspace(0, sampleRate / 2, 257).';
magnitudeNodes = interp1(frequency, magnitude, frequencyNodes, "linear");
magnitudeNodes(frequencyNodes > 12000) = 0.01;
firCoefficients = fir2(64, frequencyNodes / (sampleRate / 2), ...
    max(0.01, magnitudeNodes)).';

modeMask = frequency >= 45 & frequency <= 2200;
[modeGain, modeHz] = findpeaks(magnitude(modeMask), frequency(modeMask), ...
    MinPeakDistance=85, SortStr="descend", NPeaks=5);
modeGain = modeGain / (max(modeGain) + eps);

calibration = struct( ...
    "name", group.profile, ...
    "style", group.style, ...
    "source_names", group.sources, ...
    "event_count", numel(segments), ...
    "attack_ms", median(attacks, "omitnan"), ...
    "decay_ms", median(decays, "omitnan"), ...
    "interval_ms", median(intervals, "omitnan"), ...
    "cluster_size", round(median(clusterSizes, "omitnan")), ...
    "mode_hz", modeHz.', ...
    "mode_gain", modeGain.', ...
    "fir", firCoefficients);
end

function plot_event_montage(outputDir, group, segments, sampleRate)
count = min(12, numel(segments));
figureHandle = figure(Visible="off", Color="white", Position=[100, 100, 1300, 850]);
cleanup = onCleanup(@() close(figureHandle));
layout = tiledlayout(4, 3, TileSpacing="compact", Padding="compact");
title(layout, group.profile + " detected backfire events");
for index = 1:count
    nexttile;
    segment = segments{index};
    plot((0:numel(segment) - 1) / sampleRate * 1000, segment);
    xlim([0, 180]);
    ylim([-1, 1]);
    title("event " + index);
end
exportgraphics(figureHandle, fullfile(outputDir, group.profile + "_events.png"), Resolution=130);
end

function plot_calibration(outputDir, calibration, sampleRate)
figureHandle = figure(Visible="off", Color="white", Position=[100, 100, 1100, 500]);
cleanup = onCleanup(@() close(figureHandle));
frequency = linspace(0, sampleRate / 2, 4096);
response = freqz(calibration.fir, 1, frequency, sampleRate);
plot(frequency, 20 * log10(abs(response) / max(abs(response)) + 1e-6));
xlim([0, 12000]);
ylim([-80, 3]);
xlabel("Frequency (Hz)");
ylabel("Relative magnitude (dB)");
title(calibration.name + " derived backfire FIR");
grid on;
exportgraphics(figureHandle, fullfile(outputDir, calibration.name + "_fir.png"), Resolution=130);
end

function write_text(path, content)
fileId = fopen(path, "w", "n", "UTF-8");
if fileId < 0
    error("jovi:sound:FileOpen", "Cannot write %s", path);
end
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, content, "char");
end
