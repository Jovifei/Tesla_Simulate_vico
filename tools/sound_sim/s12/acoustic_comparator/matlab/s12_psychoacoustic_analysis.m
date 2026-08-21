function result = s12_psychoacoustic_analysis(inputSpec, outputDirectory)
%S12_PSYCHOACOUSTIC_ANALYSIS Invoke MATLAB Audio Toolbox metrics without proxies.
%   Audio is uncalibrated digital-domain input unless calibration_factor is
%   explicitly present. Outputs therefore never claim absolute SPL.

arguments
    inputSpec (1,1) struct
    outputDirectory (1,:) char
end

required = {'acousticLoudness','acousticSharpness','acousticRoughness','acousticFluctuation','acousticToneToNoiseRatio','acousticProminenceRatio'};
available = cell2struct(cellfun(@(name) exist(name, 'file') > 0, required, 'UniformOutput', false), required, 2);
result = struct('schema_version', 's12-stage-n-matlab-psychoacoustic-1', ...
    'status', 'BLOCKED', 'matlab_release', version('-release'), 'toolboxes', {ver}, ...
    'function_availability', available, 'calibration', 'digital-domain relative only; not absolute SPL', ...
    'metrics', struct(), 'validation', struct());
if ~all(structfun(@logical, available))
    result.blocked_reason = 'One or more required MATLAB Audio Toolbox functions are unavailable.';
    s12_export_matlab_comparator_result(result, outputDirectory, 'matlab_psychoacoustic_metrics');
    return
end

if isfield(inputSpec, 'mode') && strcmp(inputSpec.mode, 'fixture')
    fixture = buildFixtures();
    values = struct();
    fields = fieldnames(fixture);
    for index = 1:numel(fields)
        values.(fields{index}) = measure(fixture.(fields{index}), fixture.sample_rate_hz);
    end
    result.metrics = values;
    result.validation = validateDirections(values);
    result.status = 'EXECUTED_ON_FIXTURE';
    if result.validation.passed
        result.status = 'VALIDATED';
    end
else
    if ~all(isfield(inputSpec, {'signal','sample_rate_hz'}))
        result.blocked_reason = 'Project mode requires signal and sample_rate_hz.';
        s12_export_matlab_comparator_result(result, outputDirectory, 'matlab_psychoacoustic_metrics');
        return
    end
    result.metrics = measure(inputSpec.signal(:), inputSpec.sample_rate_hz);
    result.status = 'EXECUTED_ON_PROJECT_DATA';
end
s12_export_matlab_comparator_result(result, outputDirectory, 'matlab_psychoacoustic_metrics');
end

function fixture = buildFixtures()
fixture.sample_rate_hz = 48000;
time = (0:1/fixture.sample_rate_hz:3 - 1/fixture.sample_rate_hz)';
base = 0.02 * sin(2*pi*1000*time);
fixture.base = base;
fixture.gain = 2.0 * base;
fixture.high_frequency_boost = base + 0.08 * sin(2*pi*7000*time);
fixture.fast_am = (1 + 0.7*sin(2*pi*70*time)) .* base;
fixture.slow_am = (1 + 0.7*sin(2*pi*4*time)) .* base;
fixture.prominent_tone = 0.01 * randn(size(time)) + 0.15 * sin(2*pi*1000*time);
end

function metric = measure(signal, sampleRateHz)
[loudness, specificLoudness] = acousticLoudness(signal, sampleRateHz);
metric = struct();
metric.loudness_sone = scalarValue(loudness);
metric.sharpness_acum = scalarValue(acousticSharpness(specificLoudness));
[~, specificLoudnessTv] = acousticLoudness(signal, sampleRateHz, 'TimeVarying', true, 'TimeResolution', 'high');
metric.roughness_asper = scalarValue(acousticRoughness(specificLoudnessTv));
metric.fluctuation_vacil = scalarValue(acousticFluctuation(specificLoudnessTv));
[tnr, tnrFrequency, prominent] = acousticToneToNoiseRatio(signal, sampleRateHz);
[prominence, prominenceFrequency] = acousticProminenceRatio(signal, sampleRateHz);
metric.tone_to_noise_ratio_db = scalarValue(tnr);
metric.tone_to_noise_frequency_hz = scalarValue(tnrFrequency);
metric.tone_prominent = any(logical(prominent(:)));
metric.prominence_ratio_db = scalarValue(prominence);
metric.prominence_frequency_hz = scalarValue(prominenceFrequency);
end

function validation = validateDirections(values)
validation = struct( ...
    'gain_increases_loudness', values.gain.loudness_sone > values.base.loudness_sone, ...
    'high_frequency_increases_sharpness', values.high_frequency_boost.sharpness_acum > values.base.sharpness_acum, ...
    'fast_am_increases_roughness', values.fast_am.roughness_asper > values.base.roughness_asper, ...
    'slow_am_increases_fluctuation', values.slow_am.fluctuation_vacil > values.base.fluctuation_vacil, ...
    'prominent_tone_increases_tonality', values.prominent_tone.tone_to_noise_ratio_db > values.base.tone_to_noise_ratio_db);
validation.passed = all(structfun(@logical, validation));
end

function value = scalarValue(input)
if iscell(input)
    input = [input{:}];
end
value = mean(double(input(:)), 'omitnan');
if isempty(value) || ~isfinite(value)
    value = NaN;
end
end
