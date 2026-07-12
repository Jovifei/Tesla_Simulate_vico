function features = v6_modulation_features(audio, sampleRate)
%V6_MODULATION_FEATURES Measure intermittent pulse-envelope behavior.

if isvector(audio)
    audio = audio(:).';
else
    audio = mean(audio, 2).';
end
audio = audio - mean(audio);
band = band_limit(audio, 250, 4000, sampleRate);
energy = lowpass_one_pole(band .^ 2, 260, sampleRate);
envelope = sqrt(max(0, energy));
envelope = resample(envelope, 1000, sampleRate);
envelope = envelope / max(max(envelope), eps);

lower = prctile(envelope, 10);
upper = prctile(envelope, 90);
features.modulation_depth = (upper - lower) / max(upper + lower, eps);
features.dropout_ratio = mean(envelope < 0.40 * median(envelope));
[spectrum, frequency] = pwelch(envelope - mean(envelope), ...
    hann(min(1024, numel(envelope)), "periodic"), [], [], 1000);
mask = frequency >= 5 & frequency <= 250;
[~, peakIndex] = max(spectrum(mask));
maskedFrequency = frequency(mask);
features.modulation_peak_hz = maskedFrequency(peakIndex);
features.modulation_energy = sum(spectrum(mask)) / max(sum(spectrum), eps);

[peaks, locations] = findpeaks(envelope, MinPeakDistance=3, ...
    MinPeakProminence=0.025);
if numel(peaks) < 2
    features.pulse_amplitude_cv = 0;
    features.pulse_interval_cv = 0;
else
    features.pulse_amplitude_cv = std(peaks) / max(mean(peaks), eps);
    intervals = diff(locations);
    features.pulse_interval_cv = std(intervals) / max(mean(intervals), eps);
end
features.crest_factor = max(abs(audio)) / max(sqrt(mean(audio .^ 2)), eps);
end

function output = band_limit(input, highpassHz, lowpassHz, sampleRate)
highPole = exp(-2 * pi * highpassHz / sampleRate);
highpassed = filter([highPole, -highPole], [1, -highPole], input);
output = lowpass_one_pole(highpassed, lowpassHz, sampleRate);
end

function output = lowpass_one_pole(input, cutoffHz, sampleRate)
pole = exp(-2 * pi * cutoffHz / sampleRate);
output = filter(1 - pole, [1, -pole], input);
end
