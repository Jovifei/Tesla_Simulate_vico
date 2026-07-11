function features = v6_reference_features(audio, sampleRate)
%V6_REFERENCE_FEATURES Extract compact spectral targets without retaining audio.

if isvector(audio)
    audio = audio(:).';
else
    audio = mean(audio, 2).';
end
audio = audio - mean(audio);
audio = audio / max(max(abs(audio)), eps);
windowLength = min(4096, max(256, 2^floor(log2(numel(audio)))));
overlap = floor(0.75 * windowLength);
[spectrum, frequency] = spectrogram(audio, hann(windowLength, "periodic"), ...
    overlap, windowLength, sampleRate);
powerSpectrum = abs(spectrum).^2;
framePower = sum(powerSpectrum, 1);
activeThreshold = max(prctile(framePower, 75), max(framePower) * 1e-4);
active = framePower >= activeThreshold;
powerSpectrum = powerSpectrum(:, active);
meanPower = mean(powerSpectrum, 2) + eps;
total = sum(meanPower);
features = struct();
features.centroid_hz = sum(frequency .* meanPower) / total;
features.flatness = exp(mean(log(meanPower))) / mean(meanPower);
features.band_shares = band_shares(meanPower, frequency);
end

function shares = band_shares(power, frequency)
bands = [20, 250; 250, 1000; 1000, 4000; 4000, 12000];
shares = zeros(1, size(bands, 1));
for index = 1:size(bands, 1)
    mask = frequency >= bands(index, 1) & frequency < bands(index, 2);
    shares(index) = sum(power(mask)) / sum(power);
end
end
