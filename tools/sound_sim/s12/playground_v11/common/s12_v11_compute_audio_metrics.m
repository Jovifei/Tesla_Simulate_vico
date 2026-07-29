function metrics = s12_v11_compute_audio_metrics(pcm, sampleRateHz)
%S12_V11_COMPUTE_AUDIO_METRICS Compute fixed synthetic-audio descriptors.

mono = validateInputs(pcm, sampleRateHz);
mono = mono - mean(mono);
nfft = 2 ^ nextpow2(max(numel(mono), 32));
spectrum = fft(mono, nfft);
power = abs(spectrum(1:nfft / 2 + 1)) .^ 2;
frequencyHz = (0:nfft / 2).' * sampleRateHz / nfft;
fixedBands = [20, 120; 120, 500; 500, 2000; 2000, 8000];
bandEnergy = zeros(1, 4);
for index = 1:4
    if index < 4
        inside = frequencyHz >= fixedBands(index, 1) & frequencyHz < fixedBands(index, 2);
    else
        inside = frequencyHz >= fixedBands(index, 1) & frequencyHz <= fixedBands(index, 2);
    end
    bandEnergy(index) = sum(power(inside));
end
bandTotal = sum(bandEnergy);
if bandTotal > 0
    bandRatios = bandEnergy / bandTotal;
else
    bandRatios = zeros(1, 4);
end

audible = frequencyHz >= 20 & frequencyHz <= min(20000, sampleRateHz / 2);
audiblePower = power(audible);
audibleFrequency = frequencyHz(audible);
powerTotal = sum(audiblePower);
if powerTotal > 0
    centroidHz = sum(audibleFrequency .* audiblePower) / powerTotal;
    cumulative = cumsum(audiblePower);
    rolloffIndex = find(cumulative >= 0.85 * powerTotal, 1, "first");
    rolloffHz = audibleFrequency(rolloffIndex);
    flatness = exp(mean(log(audiblePower + eps))) / (mean(audiblePower) + eps);
else
    centroidHz = 0;
    rolloffHz = 0;
    flatness = 0;
end

envelopeWindow = max(1, round(0.010 * sampleRateHz));
envelope = conv(abs(mono), ones(envelopeWindow, 1) / envelopeWindow, "same");
low = empiricalQuantile(envelope, 0.05);
high = empiricalQuantile(envelope, 0.95);
modulationDepth = (high - low) / max(high + low, eps);
pulseAmplitudeCv = measurePulseAmplitudeCv(envelope);
metrics = struct( ...
    "fixed_bands_hz", fixedBands, ...
    "band_energy_ratios", bandRatios, ...
    "centroid_hz", centroidHz, ...
    "rolloff_hz", rolloffHz, ...
    "flatness", flatness, ...
    "modulation_depth", modulationDepth, ...
    "pulse_amplitude_cv", pulseAmplitudeCv);
end

function mono = validateInputs(pcm, sampleRateHz)
if ~isnumeric(pcm) || isempty(pcm) || any(~isfinite(pcm), "all") || ndims(pcm) > 2
    error("S12:EngineSoundV11:Analysis", "PCM must be a finite numeric vector or matrix.");
end
if ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || ...
        ~isfinite(sampleRateHz) || sampleRateHz <= 0
    error("S12:EngineSoundV11:Analysis", "sampleRateHz must be positive and finite.");
end
if isvector(pcm)
    mono = double(pcm(:));
else
    mono = mean(double(pcm), 2);
end
end

function value = empiricalQuantile(values, fraction)
ordered = sort(values(:));
index = max(1, min(numel(ordered), round(1 + fraction * (numel(ordered) - 1))));
value = ordered(index);
end

function coefficient = measurePulseAmplitudeCv(envelope)
if numel(envelope) < 3
    coefficient = 0;
    return;
end
threshold = median(envelope) + 0.5 * std(envelope);
peakMask = envelope(2:end - 1) > envelope(1:end - 2) & ...
    envelope(2:end - 1) >= envelope(3:end) & envelope(2:end - 1) > threshold;
amplitudes = envelope(find(peakMask) + 1); %#ok<FNDSB>
if numel(amplitudes) < 2 || mean(amplitudes) <= eps
    coefficient = 0;
else
    coefficient = std(amplitudes) / mean(amplitudes);
end
end
