function metrics = s12_sound_playground_case_order_metrics(pcmPath, rpm)
%S12_SOUND_PLAYGROUND_CASE_ORDER_METRICS Measure frozen RPM-centered order bands from PCM evidence.

if ~isscalar(rpm) || ~isfinite(rpm) || rpm <= 0
    error("S12:Playground:CaseMetrics", "RPM must be one finite positive scalar.");
end
channel = readStereoPcm(pcmPath);
signal = s12_sound_playground_signal_contract();
contract = s12_sound_playground_sensitivity_contract();
sampleCount = numel(channel);
analysisWindow = periodicHann(sampleCount);
fftEnergy = abs(fft(channel .* analysisWindow)) .^ 2;
halfIndex = floor(sampleCount / 2);
oneSidedEnergy = fftEnergy(1:halfIndex + 1);
if sampleCount > 2
    oneSidedEnergy(2:end - 1) = 2 * oneSidedEnergy(2:end - 1);
end
frequencyHz = (0:halfIndex).' * signal.sample_rate_hz / sampleCount;
orders = contract.order_band_orders;
bands = repmat(struct("order", 0, "center_hz", 0, "half_bandwidth_hz", 0, "energy", 0), 1, numel(orders));
for index = 1:numel(orders)
    centerHz = double(rpm) / 60 * orders(index);
    bandwidthHz = contract.order_band_half_bandwidth_hz;
    bins = frequencyHz >= centerHz - bandwidthHz & frequencyHz <= centerHz + bandwidthHz;
    if ~any(bins)
        error("S12:Playground:CaseMetrics", "No FFT bins fall inside frozen order band %d.", orders(index));
    end
    bands(index) = struct("order", orders(index), "center_hz", centerHz, ...
        "half_bandwidth_hz", bandwidthHz, "energy", sum(oneSidedEnergy(bins)));
end
selected = bands(orders == contract.selected_order);
if numel(selected) ~= 1
    error("S12:Playground:CaseMetrics", "Selected order band is ambiguous.");
end
[~, selectedBin] = max(oneSidedEnergy(frequencyHz >= selected.center_hz - selected.half_bandwidth_hz & ...
    frequencyHz <= selected.center_hz + selected.half_bandwidth_hz));
selectedFrequencies = frequencyHz(frequencyHz >= selected.center_hz - selected.half_bandwidth_hz & ...
    frequencyHz <= selected.center_hz + selected.half_bandwidth_hz);
transientSamples = min(sampleCount, round(contract.transient_window_s * signal.sample_rate_hz));
metrics = struct("dominant_order_frequency_hz", selectedFrequencies(selectedBin), "rms", rms(channel), ...
    "order_bands", bands, "order2_to_order1_energy_ratio", bands(2).energy / max(bands(1).energy, realmin), ...
    "transient_window_s", contract.transient_window_s, "transient_window_energy", sum(channel(1:transientSamples) .^ 2), ...
    "transient_peak", max(abs(channel(1:transientSamples))));
end

function channel = readStereoPcm(pcmPath)
file = fopen(pcmPath, "r");
if file < 0
    error("S12:Playground:CaseMetrics", "Cannot read PCM evidence %s.", pcmPath);
end
cleanup = onCleanup(@() fclose(file));
raw = fread(file, inf, "double=>double");
if mod(numel(raw), 2) ~= 0
    error("S12:Playground:CaseMetrics", "PCM evidence is not stereo interleaved.");
end
pcm = reshape(raw, 2, []).';
channel = pcm(:, 1);
end

function window = periodicHann(sampleCount)
index = (0:sampleCount - 1).';
window = 0.5 - 0.5 * cos(2 * pi * index / sampleCount);
end
