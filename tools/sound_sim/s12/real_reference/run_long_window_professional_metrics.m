function receipt = run_long_window_professional_metrics(manifestPath, outputRoot)
%RUN_LONG_WINDOW_PROFESSIONAL_METRICS Run MATLAB metrics on 15/30s windows.
arguments
    manifestPath (1,:) char
    outputRoot (1,:) char
end
if ~isfile(manifestPath)
    error('s12:Professional:LongManifestMissing', 'Long-window manifest is missing.');
end
if isfolder(outputRoot)
    error('s12:Professional:LongOutputExists', 'Refusing to overwrite long-window MATLAB output.');
end
mkdir(outputRoot);
scriptRoot = fileparts(mfilename('fullpath'));
adapterRoot = fullfile(scriptRoot, '..', 'acoustic_comparator', 'matlab');
addpath(adapterRoot);
cleanupPath = onCleanup(@() rmpath(adapterRoot)); %#ok<NASGU>
manifest = jsondecode(fileread(manifestPath));
if ~isfield(manifest, 'pairs') || isempty(manifest.pairs)
    error('s12:Professional:LongPairMissing', 'Long-window manifest has no pairs.');
end
rows = cell(1, numel(manifest.pairs) * 2);
rowIndex = 0;
for pairIndex = 1:numel(manifest.pairs)
    pair = manifest.pairs(pairIndex);
    sides = {'reference', 'candidate'};
    paths = {char(pair.reference_path), char(pair.candidate_path)};
    shaNames = {'reference_sha256', 'candidate_sha256'};
    for sideIndex = 1:2
        inputPath = paths{sideIndex};
        if ~isfile(inputPath)
            error('s12:Professional:LongClipMissing', 'Long-window clip missing: %s', inputPath);
        end
        [signal, sampleRateHz] = audioread(inputPath);
        signal = mean(double(signal), 2);
        durationSeconds = double(pair.window.duration_s);
        windowSamples = min(numel(signal), round(durationSeconds * sampleRateHz));
        if windowSamples <= 1
            error('s12:Professional:LongWindowTooShort', 'Long-window clip too short: %s', inputPath);
        end
        signal = signal(1:windowSamples);
        side = sides{sideIndex};
        caseRoot = fullfile(outputRoot, char(pair.pair_id), side);
        result = s12_psychoacoustic_analysis(struct('signal', signal, 'sample_rate_hz', sampleRateHz), caseRoot);
        if ~strcmp(result.status, 'EXECUTED_ON_PROJECT_DATA')
            error('s12:Professional:LongToolBlocked', 'Audio Toolbox did not execute: %s/%s', char(pair.pair_id), side);
        end
        rowIndex = rowIndex + 1;
        row = struct();
        row.pair_id = char(pair.pair_id);
        row.file_id = char(pair.file_id);
        row.side = side;
        row.vehicle_id = char(pair.vehicle_id);
        row.scenario = char(pair.scenario);
        row.window_profile = char(pair.window.profile);
        row.sample_rate_hz = sampleRateHz;
        row.window = struct('start_s', 0.0, 'duration_s', windowSamples / sampleRateHz);
        row.input_path = inputPath;
        row.input_sha256 = char(pair.(shaNames{sideIndex}));
        row.metrics = result.metrics;
        row.units = struct('loudness_sone', 'sone', 'sharpness_acum', 'acum', 'roughness_asper', 'asper', 'fluctuation_vacil', 'vacil', 'tone_to_noise_ratio_db', 'dB', 'tone_to_noise_frequency_hz', 'Hz', 'prominence_ratio_db', 'dB', 'prominence_frequency_hz', 'Hz');
        row.tool_domain = 'Professional MATLAB';
        row.calibration = 'digital-domain relative only; not absolute SPL';
        row.order_status = 'ORDER_COMPARISON_NOT_QUALIFIED';
        rowIndexValue = row;
        rows{rowIndex} = rowIndexValue;
    end
end
receipt = struct('schema_version', 's12-professional-matlab-long-window-receipt-v1', 'status', 'EXECUTED_ON_LONG_WINDOWS', 'matlab_release', version('-release'), 'analysis_signal', 'unaltered digital-domain signal; not calibrated SPL', 'toolchain', {{'acousticLoudness', 'acousticSharpness', 'acousticRoughness', 'acousticFluctuation', 'acousticToneToNoiseRatio', 'acousticProminenceRatio'}}, 'manifest_path', manifestPath, 'clip_count', numel(rows), 'results', {rows}, 'order_status', 'ORDER_COMPARISON_NOT_QUALIFIED', 'automatic_tuning_eligible', false, 'profile_candidate_ready', false);
s12_export_matlab_comparator_result(receipt, outputRoot, 'matlab_long_window_metrics');
end
