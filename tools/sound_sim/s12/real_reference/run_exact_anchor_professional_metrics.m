function receipt = run_exact_anchor_professional_metrics(manifestPath, outputRoot)
%RUN_EXACT_ANCHOR_PROFESSIONAL_METRICS Measure the page's exact 9 A/B pairs.
%   This function runs MATLAB Audio Toolbox on both sides of every 5-second
%   clip. It writes only external metadata/metric receipts and never changes
%   a source, profile, frozen model, or feedback contract.

arguments
    manifestPath (1,:) char
    outputRoot (1,:) char
end

if ~isfile(manifestPath)
    error('s12:Professional:ManifestMissing', 'Exact A/B manifest is missing: %s', manifestPath);
end
if isfolder(outputRoot)
    error('s12:Professional:OutputExists', 'Refusing to overwrite exact MATLAB receipt output: %s', outputRoot);
end
mkdir(outputRoot);

scriptRoot = fileparts(mfilename('fullpath'));
matlabAdapterRoot = fullfile(scriptRoot, '..', 'acoustic_comparator', 'matlab');
addpath(matlabAdapterRoot);
cleanupPath = onCleanup(@() rmpath(matlabAdapterRoot)); %#ok<NASGU>
manifest = jsondecode(fileread(manifestPath));
if ~isfield(manifest, 'trials') || numel(manifest.trials) ~= 9
    error('s12:Professional:TrialCount', 'Expected exactly 9 exact anchor trials.');
end

rows = cell(1, numel(manifest.trials) * 2);
rowIndex = 0;
for trialIndex = 1:numel(manifest.trials)
    trial = manifest.trials(trialIndex);
    sides = {'reference', 'candidate'};
    paths = {char(trial.reference_audition_path), char(trial.candidate_audition_path)};
    shaNames = {'reference_audition_sha256', 'candidate_audition_sha256'};
    for sideIndex = 1:2
        side = sides{sideIndex};
        inputPath = paths{sideIndex};
        if ~isfile(inputPath)
            error('s12:Professional:ClipMissing', 'Exact clip missing: %s', inputPath);
        end
        [signal, sampleRateHz] = audioread(inputPath);
        signal = mean(double(signal), 2);
        if sampleRateHz <= 0 || isempty(signal) || ~all(isfinite(signal))
            error('s12:Professional:ClipInvalid', 'Exact clip is invalid: %s', inputPath);
        end
        windowSamples = min(numel(signal), round(5 * sampleRateHz));
        if windowSamples <= 1
            error('s12:Professional:WindowTooShort', 'Exact clip has no 5-second analysis window: %s', inputPath);
        end
        signal = signal(1:windowSamples);
        caseRoot = fullfile(outputRoot, char(trial.trial_id), side);
        result = s12_psychoacoustic_analysis( ...
            struct('signal', signal, 'sample_rate_hz', sampleRateHz), caseRoot);
        if ~strcmp(result.status, 'EXECUTED_ON_PROJECT_DATA')
            error('s12:Professional:ToolBlocked', 'Audio Toolbox did not execute for %s/%s.', char(trial.trial_id), side);
        end
        rowIndex = rowIndex + 1;
        rowIndexValue = struct();
        rowIndexValue.pair_id = char(trial.trial_id);
        rowIndexValue.file_id = char(trial.file_id);
        rowIndexValue.side = side;
        rowIndexValue.vehicle_id = char(trial.vehicle_id);
        rowIndexValue.sample_rate_hz = sampleRateHz;
        rowIndexValue.window = struct('start_s', 0.0, 'duration_s', windowSamples / sampleRateHz);
        rowIndexValue.input_path = inputPath;
        rowIndexValue.input_sha256 = char(trial.(shaNames{sideIndex}));
        rowIndexValue.metrics = result.metrics;
        rowIndexValue.units = struct( ...
            'loudness_sone', 'sone', 'sharpness_acum', 'acum', ...
            'roughness_asper', 'asper', 'fluctuation_vacil', 'vacil', ...
            'tone_to_noise_ratio_db', 'dB', ...
            'tone_to_noise_frequency_hz', 'Hz', ...
            'prominence_ratio_db', 'dB', ...
            'prominence_frequency_hz', 'Hz');
        rowIndexValue.tool_domain = 'Professional MATLAB';
        rowIndexValue.calibration = 'digital-domain relative only; not absolute SPL';
        rowIndexValue.order_status = 'ORDER_COMPARISON_NOT_QUALIFIED';
        rowIndexValue.state_status = 'MISSING_SYNCHRONIZED_RPM_LOAD_THROTTLE_GEAR_SHIFT';
        rows{rowIndex} = rowIndexValue;
    end
end

receipt = struct( ...
    'schema_version', 's12-professional-matlab-exact-clip-receipt-v1', ...
    'status', 'EXECUTED_ON_EXACT_CLIPS', ...
    'matlab_release', version('-release'), ...
    'analysis_signal', 'unaltered digital-domain signal; not calibrated SPL', ...
    'toolchain', {{'acousticLoudness', 'acousticSharpness', 'acousticRoughness', ...
        'acousticFluctuation', 'acousticToneToNoiseRatio', 'acousticProminenceRatio'}}, ...
    'manifest_path', manifestPath, ...
    'manifest_sha256', 'BOUND_BY_PYTHON_CLIP_INTEGRITY_RECEIPT', ...
    'clip_count', numel(rows), ...
    'results', {rows}, ...
    'order_status', 'ORDER_COMPARISON_NOT_QUALIFIED', ...
    'automatic_tuning_eligible', false, ...
    'profile_candidate_ready', false);
s12_export_matlab_comparator_result(receipt, outputRoot, 'matlab_exact_clip_metrics');
end
