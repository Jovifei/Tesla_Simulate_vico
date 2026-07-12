%ANALYZE_HELLCAT_V6_REFERENCES Derive stock-biased Hellcat sound targets.

vehicleDir = fileparts(mfilename("fullpath"));
v6Root = fileparts(fileparts(vehicleDir));
addpath(v6Root);
downloadRoot = "E:\Claude_allow\Download\tesla-sound-research\hellcat_v6";
sources = [ ...
    source("eyzGRhXp0do", "stock road acceleration", true, [85, 140], [20, 48]); ...
    source("FvORN7EH2cc", "Redeye downshifts", true, [7, 14], [14, 25]); ...
    source("nnEaamqsieM", "near-field leave", true, [4, 25], [30, 38]); ...
    source("cKx-cb0fzeo", "stock sound review", true, [70, 90], [52, 68]); ...
    source("qiopd-QP2PE", "burble tune contrast", false, [0, 11], [0, 11]); ...
    source("A_hjItNZUAI", "exhaust and supercharger compilation", true, [20, 31], [35, 40])];

for index = 1:numel(sources)
    path = fullfile(downloadRoot, sources(index).id + ".mp3");
    sources(index).acceleration = segment_features(path, sources(index).acceleration_window_s);
    sources(index).afterfire = segment_features(path, sources(index).afterfire_window_s);
end
stock = sources([sources.include_in_stock_target]);
acceleration = vertcat(stock.acceleration);
afterfire = vertcat(stock.afterfire);
payload = struct("schema", "jovi.hellcat_reference_targets.v6", ...
    "note", "Derived metrics only; public audio remains outside the repository.", ...
    "sources", sources);
payload.stock_median.acceleration_band_shares = median(vertcat(acceleration.band_shares), 1);
payload.stock_median.acceleration_flux = median([acceleration.spectral_flux]);
payload.stock_median.acceleration_modulation_depth = median([acceleration.modulation_depth]);
payload.stock_median.acceleration_pulse_amplitude_cv = median([acceleration.pulse_amplitude_cv]);
payload.stock_median.afterfire_band_shares = median(vertcat(afterfire.band_shares), 1);
payload.stock_median.afterfire_flux = median([afterfire.spectral_flux]);
payload.stock_median.afterfire_modulation_depth = median([afterfire.modulation_depth]);

calibrationDir = fullfile(vehicleDir, "calibration");
if ~isfolder(calibrationDir)
    mkdir(calibrationDir);
end
outputPath = fullfile(calibrationDir, "hellcat_v6_reference_targets.json");
fileId = fopen(outputPath, "w", "n", "UTF-8");
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, jsonencode(payload, PrettyPrint=true), "char");
fprintf("Hellcat derived targets: %s\n", outputPath);

function value = source(id, setup, include, accelerationWindow, afterfireWindow)
value = struct("id", id, "url", "https://www.youtube.com/watch?v=" + id, ...
    "setup", setup, "include_in_stock_target", include, ...
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
features = struct("band_shares", shares, "spectral_flux", mean(flux));
modulation = v6_modulation_features(audio, sampleRate);
names = fieldnames(modulation);
for index = 1:numel(names)
    features.(names{index}) = modulation.(names{index});
end
end
