function metrics = v6_audio_metrics(audio, time, rpm, sampleRate)
%V6_AUDIO_METRICS Return deterministic metrics for V6 fit and regression checks.

audio = audio - mean(audio);
window = hann(min(8192, numel(audio)), "periodic").';
segment = audio(1:numel(window)) .* window;
spectrum = abs(fft(segment));
frequency = (0:numel(segment) - 1) * sampleRate / numel(segment);
positive = frequency <= sampleRate / 2;
frequency = frequency(positive);
power = spectrum(positive).^2;
total = sum(power) + eps;
centroid = sum(frequency .* power) / total;
bands = [20, 250; 250, 1000; 1000, 4000; 4000, 12000; 12000, 20000];
shares = zeros(1, size(bands, 1));
for index = 1:size(bands, 1)
    mask = frequency >= bands(index, 1) & frequency < bands(index, 2);
    shares(index) = sum(power(mask)) / total;
end
metrics = struct();
metrics.rms = sqrt(mean(audio.^2));
metrics.peak = max(abs(audio));
metrics.spectral_centroid_hz = centroid;
metrics.band_shares = shares;
metrics.mean_rpm = mean(rpm);
metrics.duration_s = time(end) + 1 / sampleRate;
end
