%ANALYZE_C63_V6_2_REFERENCES Derive acceleration and afterfire targets.

vehicleDir = fileparts(mfilename("fullpath"));
v6Root = fileparts(fileparts(vehicleDir));
addpath(v6Root);
downloadRoot = "E:\Claude_allow\Download\tesla-sound-research\c63_v62";
sources = [ ...
    source("sbLXOEcAYMI", "sbLXOEcAYMI.wav", "W204", "unknown exhaust", [0, 8.8], [0, 8.8]); ...
    source("MlQoLofl5qU", "MlQoLofl5qU.mp3", "W205 contrast", "C63s Edition 1", [110, 130], [28, 50]); ...
    source("m5junjbk2eY", "m5junjbk2eY.mp3", "W204", "iPE exhaust", [150, 198], [200, 250]); ...
    source("zR_c4wHPqQc", "zR_c4wHPqQc.mp3", "W204", "raspy backfire", [0, 8], [15, 21]); ...
    source("R-pcSGjv8wM", "R-pcSGjv8wM.mp3", "W204", "catless headers", [15, 46], [47, 60]); ...
    source("S4_ybvcunKU", "S4_ybvcunKU.mp3", "W204", "de-catted", [13, 31], [1, 6])];

for index = 1:numel(sources)
    audioPath = fullfile(downloadRoot, sources(index).file);
    sources(index).acceleration = segment_features(audioPath, ...
        sources(index).acceleration_window_s);
    sources(index).afterfire = segment_features(audioPath, ...
        sources(index).afterfire_window_s);
end

w204 = sources(~contains(string({sources.generation}), "contrast"));
accelerationBands = vertcat(w204.acceleration);
afterfireBands = vertcat(w204.afterfire);
payload = struct();
payload.schema = "jovi.c63_reference_targets.v6_2";
payload.note = "Derived metrics only; raw public audio remains outside the repository.";
payload.sources = sources;
payload.w204_median.acceleration_band_shares = median(vertcat(accelerationBands.band_shares), 1);
payload.w204_median.acceleration_flatness = median([accelerationBands.flatness]);
payload.w204_median.acceleration_flux = median([accelerationBands.spectral_flux]);
payload.w204_median.acceleration_modulation_depth = ...
    median([accelerationBands.modulation_depth]);
payload.w204_median.acceleration_dropout_ratio = ...
    median([accelerationBands.dropout_ratio]);
payload.w204_median.acceleration_pulse_amplitude_cv = ...
    median([accelerationBands.pulse_amplitude_cv]);
payload.w204_median.acceleration_pulse_interval_cv = ...
    median([accelerationBands.pulse_interval_cv]);
payload.w204_median.afterfire_band_shares = median(vertcat(afterfireBands.band_shares), 1);
payload.w204_median.afterfire_flatness = median([afterfireBands.flatness]);
payload.w204_median.afterfire_flux = median([afterfireBands.spectral_flux]);
payload.w204_median.afterfire_modulation_depth = median([afterfireBands.modulation_depth]);
payload.w204_median.afterfire_dropout_ratio = median([afterfireBands.dropout_ratio]);

calibrationDir = fullfile(vehicleDir, "calibration");
if ~isfolder(calibrationDir)
    mkdir(calibrationDir);
end
outputPath = fullfile(calibrationDir, "c63_v6_2_reference_targets.json");
fileId = fopen(outputPath, "w", "n", "UTF-8");
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, jsonencode(payload, PrettyPrint=true), "char");
fprintf("C63 V6.2 derived targets: %s\n", outputPath);

function value = source(id, file, generation, setup, accelerationWindow, afterfireWindow)
value = struct("id", id, "url", "https://www.youtube.com/watch?v=" + id, ...
    "file", file, "generation", generation, "setup", setup, ...
    "acceleration_window_s", accelerationWindow, ...
    "afterfire_window_s", afterfireWindow, "acceleration", struct(), ...
    "afterfire", struct());
end

function features = segment_features(path, windowSeconds)
[audio, sampleRate] = audioread(path);
audio = mean(audio, 2);
first = max(1, floor(windowSeconds(1) * sampleRate) + 1);
last = min(numel(audio), ceil(windowSeconds(2) * sampleRate));
audio = audio(first:last);
[spectrum, frequency] = spectrogram(audio, hann(2048, "periodic"), ...
    1536, 4096, sampleRate);
power = abs(spectrum) .^ 2;
framePower = sum(power, 1);
active = framePower >= prctile(framePower, 70);
power = power(:, active);
meanPower = mean(power, 2) + eps;
normalized = power ./ (sum(power, 1) + eps);
flux = sqrt(sum(max(0, diff(normalized, 1, 2)) .^ 2, 1));
bands = [20, 250; 250, 1000; 1000, 4000; 4000, 12000];
shares = zeros(1, 4);
for index = 1:4
    mask = frequency >= bands(index, 1) & frequency < bands(index, 2);
    shares(index) = sum(meanPower(mask)) / sum(meanPower);
end
features = struct("band_shares", shares, ...
    "centroid_hz", sum(frequency .* meanPower) / sum(meanPower), ...
    "flatness", exp(mean(log(meanPower))) / mean(meanPower), ...
    "spectral_flux", mean(flux), "active_frames", sum(active));
modulation = v6_modulation_features(audio, sampleRate);
names = fieldnames(modulation);
for index = 1:numel(names)
    features.(names{index}) = modulation.(names{index});
end
end
