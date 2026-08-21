function result = s12_order_analysis(inputSpec, outputDirectory)
%S12_ORDER_ANALYSIS Run auditable Signal Processing Toolbox order analysis.
%   inputSpec.mode = 'fixture' creates a known RPM/order signal.  Project
%   mode requires signal, sample_rate_hz, RPM, and state_trace of equal
%   sample count.  It never guesses RPM from an external reference recording.

arguments
    inputSpec (1,1) struct
    outputDirectory (1,:) char
end

required = {'rpmordermap','rpmfreqmap','orderspectrum','ordertrack'};
available = cell2struct(cellfun(@(name) exist(name, 'file') > 0, required, 'UniformOutput', false), required, 2);
result = struct('schema_version', 's12-stage-n-matlab-order-1', ...
    'status', 'BLOCKED', 'function_availability', available, ...
    'matlab_release', version('-release'), 'toolboxes', {ver}, ...
    'reference_status', 'REFERENCE_RPM_UNAVAILABLE', ...
    'order_comparison_status', 'ORDER_COMPARISON_NOT_QUALIFIED');
if ~all(structfun(@logical, available))
    result.blocked_reason = 'Signal Processing Toolbox order functions unavailable';
    s12_export_matlab_comparator_result(result, outputDirectory, 'order_metrics');
    return
end

if isfield(inputSpec, 'mode') && strcmp(inputSpec.mode, 'fixture')
    [signal, sampleRateHz, rpm, stateTrace, expectedOrders, expectedAmplitudes] = knownFixture();
    result.input_kind = 'known_order_fixture';
    result.reference_status = 'SYNTHETIC_FIXTURE_RPM_AVAILABLE';
    result.order_comparison_status = 'FIXTURE_ORDER_ANALYSIS';
else
    requiredFields = {'signal','sample_rate_hz','rpm','state_trace'};
    if ~all(isfield(inputSpec, requiredFields))
        result.blocked_reason = 'Project candidate needs signal, sample_rate_hz, RPM, and state_trace.';
        s12_export_matlab_comparator_result(result, outputDirectory, 'order_metrics');
        return
    end
    signal = inputSpec.signal(:);
    sampleRateHz = inputSpec.sample_rate_hz;
    rpm = inputSpec.rpm(:);
    stateTrace = inputSpec.state_trace(:);
    expectedOrders = [];
    expectedAmplitudes = [];
    if numel(signal) ~= numel(rpm) || numel(signal) ~= numel(stateTrace) || any(~isfinite(rpm)) || any(rpm <= 0)
        result.blocked_reason = 'RPM/state trace must be finite, positive, and sample-aligned with candidate PCM.';
        s12_export_matlab_comparator_result(result, outputDirectory, 'order_metrics');
        return
    end
    result.input_kind = 'project_candidate_with_actual_trace';
    result.reference_status = 'EXTERNAL_REFERENCE_NOT_SUPPLIED';
    result.order_comparison_status = 'CANDIDATE_ORDER_ANALYSIS_ONLY';
end

[orderMap, orderAxis, mapRpm, mapTime, orderResolution] = rpmordermap(signal, sampleRateHz, rpm, 0.025);
[frequencyMap, frequencyAxis, frequencyRpm, frequencyTime, frequencyResolution] = rpmfreqmap(signal, sampleRateHz, rpm, 5);
[orderSpectrum, spectrumOrder] = orderspectrum(orderMap, orderAxis);
trackOrders = expectedOrders;
if isempty(trackOrders)
    [~, location] = max(orderSpectrum);
    trackOrders = spectrumOrder(location);
end
[trackedMagnitude, trackedRpm, trackedTime] = ordertrack(signal, sampleRateHz, rpm, trackOrders);

matPath = fullfile(outputDirectory, 'order_rpm_map.mat');
save(matPath, 'orderMap', 'orderAxis', 'mapRpm', 'mapTime', 'orderResolution', ...
    'frequencyMap', 'frequencyAxis', 'frequencyRpm', 'frequencyTime', 'frequencyResolution', ...
    'orderSpectrum', 'spectrumOrder', 'trackedMagnitude', 'trackedRpm', 'trackedTime');
figureHandle = figure('Visible', 'off');
imagesc(mapRpm, orderAxis, 20 * log10(max(orderMap, eps)));
axis xy; xlabel('RPM'); ylabel('Order'); title('S12 order-RPM map'); colorbar;
pngPath = fullfile(outputDirectory, 'order_rpm_map.png');
exportgraphics(figureHandle, pngPath, 'Resolution', 150);
close(figureHandle);

ridges = ridgeSummary(orderSpectrum, spectrumOrder, expectedOrders, expectedAmplitudes);
ridgePath = fullfile(outputDirectory, 'order_ridges.json');
writeJson(ridgePath, ridges);
fixtureValidation = validateFixture(ridges, trackedMagnitude, expectedOrders);
result.status = 'EXECUTED_ON_FIXTURE';
if ~isempty(expectedOrders) && fixtureValidation.passed
    result.status = 'VALIDATED';
end
result.order_rpm_map = matPath;
result.order_rpm_map_png = pngPath;
result.order_ridges = ridgePath;
result.order_resolution = orderResolution;
result.frequency_resolution_hz = frequencyResolution;
result.fixture_validation = fixtureValidation;
result.state_trace_samples = numel(stateTrace);
s12_export_matlab_comparator_result(result, outputDirectory, 'order_metrics');
end

function [signal, sampleRateHz, rpm, stateTrace, orders, amplitudes] = knownFixture()
sampleRateHz = 12000;
durationSeconds = 6;
time = (0:1/sampleRateHz:durationSeconds - 1/sampleRateHz)';
rpm = linspace(900, 4500, numel(time))';
phase = 2 * pi * cumtrapz(rpm / 60) / sampleRateHz;
orders = [0.5 1 4 6];
amplitudes = [0.35 0.65 1.00 0.50];
signal = zeros(size(time));
for index = 1:numel(orders)
    signal = signal + amplitudes(index) * cos(orders(index) * phase);
end
stateTrace = repmat("fixture_acceleration", numel(time), 1);
end

function ridges = ridgeSummary(spectrum, orderAxis, expectedOrders, expectedAmplitudes)
if isempty(expectedOrders)
    [amplitude, location] = max(spectrum);
    ridges = struct('expected_order', [], 'measured_order', orderAxis(location), ...
        'amplitude', amplitude, 'amplitude_rank', 1, 'order_error', []);
    return
end
ridges = repmat(struct('expected_order', 0, 'expected_amplitude', 0, 'measured_order', 0, ...
    'amplitude', 0, 'amplitude_rank', 0, 'order_error', 0), numel(expectedOrders), 1);
amplitudes = zeros(numel(expectedOrders), 1);
for index = 1:numel(expectedOrders)
    nearby = abs(orderAxis - expectedOrders(index)) <= 0.08;
    indices = find(nearby);
    [amplitude, relativeLocation] = max(spectrum(indices));
    location = indices(relativeLocation);
    amplitudes(index) = amplitude;
    ridges(index).expected_order = expectedOrders(index);
    ridges(index).expected_amplitude = expectedAmplitudes(index);
    ridges(index).measured_order = orderAxis(location);
    ridges(index).amplitude = amplitude;
    ridges(index).order_error = abs(orderAxis(location) - expectedOrders(index));
end
[~, ranking] = sort(amplitudes, 'descend');
for rank = 1:numel(ranking)
    ridges(ranking(rank)).amplitude_rank = rank;
end
end

function validation = validateFixture(ridges, trackedMagnitude, expectedOrders)
if isempty(expectedOrders)
    validation = struct('passed', false, 'reason', 'project candidate has no known fixture target');
    return
end
errors = [ridges.order_error];
order4 = find([ridges.expected_order] == 4, 1);
amplitudeRankingCorrect = ridges(order4).amplitude_rank == 1;
relativeVariation = std(trackedMagnitude, 0, 2) ./ max(mean(trackedMagnitude, 2), eps);
validation = struct('passed', all(errors <= 0.08) && amplitudeRankingCorrect && all(relativeVariation < 0.25), ...
    'order_tolerance', 0.08, 'order_errors', errors, ...
    'amplitude_ranking_correct', amplitudeRankingCorrect, ...
    'tracked_relative_variation', relativeVariation);
end

function writeJson(path, value)
fileId = fopen(path, 'w', 'n', 'UTF-8');
if fileId < 0
    error('s12:StageN:OrderJsonFailed', 'Cannot open order ridge artifact.');
end
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', jsonencode(value));
end
