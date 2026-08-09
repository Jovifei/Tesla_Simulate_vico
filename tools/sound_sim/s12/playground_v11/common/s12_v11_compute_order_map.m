function result = s12_v11_compute_order_map(pcm, rpmTrace, sampleRateHz)
%S12_V11_COMPUTE_ORDER_MAP Compute a deterministic 0.5-order energy map.

mono = validatePcm(pcm);
validateSampleRate(sampleRateHz);
rpm = validateRpmTrace(rpmTrace);
orders = 0.5:0.5:12;
frameLength = min(2048, numel(mono));
if frameLength < 32
    error("S12:EngineSoundV11:Analysis", "PCM must contain at least 32 samples.");
end
hopSamples = min(960, frameLength);
frameCount = max(1, 1 + floor((numel(mono) - frameLength) / hopSamples));
window = 0.5 - 0.5 * cos(2 * pi * (0:frameLength - 1).' / max(frameLength - 1, 1));
nfft = 2 ^ nextpow2(frameLength);
frequencyHz = (0:nfft / 2).' * sampleRateHz / nfft;
energy = zeros(frameCount, numel(orders));
timeS = zeros(frameCount, 1);
baseFrequencyHz = zeros(frameCount, 1);
rpmSamples = expandTrace(rpm, numel(mono));

for frameIndex = 1:frameCount
    first = (frameIndex - 1) * hopSamples + 1;
    last = first + frameLength - 1;
    segment = mono(first:last);
    spectrum = fft((segment - mean(segment)) .* window, nfft);
    power = abs(spectrum(1:nfft / 2 + 1)) .^ 2;
    frameRpm = mean(rpmSamples(first:last));
    baseFrequencyHz(frameIndex) = max(frameRpm, 0) / 60;
    for orderIndex = 1:numel(orders)
        targetHz = orders(orderIndex) * baseFrequencyHz(frameIndex);
        [~, bin] = min(abs(frequencyHz - targetHz));
        bins = max(1, bin - 1):min(numel(power), bin + 1);
        energy(frameIndex, orderIndex) = sum(power(bins)) / max(sum(power), eps);
    end
    timeS(frameIndex) = ((first - 1) + (frameLength - 1) / 2) / sampleRateHz;
end
result = struct("orders", orders, "time_s", timeS, ...
    "base_frequency_hz", baseFrequencyHz, "energy", energy, ...
    "frame_samples", frameLength, "hop_samples", hopSamples);
end

function mono = validatePcm(pcm)
if ~isnumeric(pcm) || isempty(pcm) || any(~isfinite(pcm), "all") || ndims(pcm) > 2
    error("S12:EngineSoundV11:Analysis", "PCM must be a finite numeric vector or matrix.");
end
if isvector(pcm)
    mono = double(pcm(:));
else
    mono = mean(double(pcm), 2);
end
end

function validateSampleRate(sampleRateHz)
if ~isnumeric(sampleRateHz) || ~isscalar(sampleRateHz) || ...
        ~isfinite(sampleRateHz) || sampleRateHz <= 0
    error("S12:EngineSoundV11:Analysis", "sampleRateHz must be positive and finite.");
end
end

function rpm = validateRpmTrace(rpmTrace)
if ~isnumeric(rpmTrace) || isempty(rpmTrace) || any(~isfinite(rpmTrace), "all") || any(rpmTrace < 0, "all")
    error("S12:EngineSoundV11:Analysis", "rpmTrace must contain finite nonnegative values.");
end
rpm = double(rpmTrace(:));
end

function values = expandTrace(trace, sampleCount)
if isscalar(trace)
    values = repmat(trace, sampleCount, 1);
elseif numel(trace) == sampleCount
    values = trace;
else
    source = linspace(0, 1, numel(trace));
    target = linspace(0, 1, sampleCount);
    values = interp1(source, trace, target, "linear").';
end
end
