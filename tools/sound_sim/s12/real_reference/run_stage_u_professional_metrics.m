function receipt = run_stage_u_professional_metrics(manifestPath, outputPath)
%RUN_STAGE_U_PROFESSIONAL_METRICS Execute MATLAB psychoacoustics for unique Stage-U raw clips.
arguments
    manifestPath (1,:) char
    outputPath (1,:) char
end
if ~isfile(manifestPath)
    error('s12:StageU:ManifestMissing', 'Stage U clip manifest is missing: %s', manifestPath);
end
if isfile(outputPath)
    error('s12:StageU:OutputExists', 'Refusing to overwrite receipt: %s', outputPath);
end
scriptRoot = fileparts(mfilename('fullpath'));
adapterRoot = fullfile(scriptRoot, '..', 'acoustic_comparator', 'matlab');
addpath(adapterRoot);
cleaner = onCleanup(@() rmpath(adapterRoot)); %#ok<NASGU>
manifest = jsondecode(fileread(manifestPath));
if ~isfield(manifest, 'clips') || isempty(manifest.clips)
    error('s12:StageU:ClipMissing', 'Stage U clip manifest has no clips.');
end
clips = manifest.clips;
rows = cell(1, numel(clips));
for index = 1:numel(clips)
    if iscell(clips)
        clip = clips{index};
    else
        clip = clips(index);
    end
    inputPath = char(clip.path);
    if ~isfile(inputPath)
        error('s12:StageU:ClipMissing', 'Stage U clip missing: %s', inputPath);
    end
    [signal, sampleRateHz] = audioread(inputPath);
    signal = mean(double(signal), 2);
    safeClipId = regexprep(char(clip.clip_id), '[^A-Za-z0-9_-]', '_');
    caseRoot = fullfile(fileparts(outputPath), 'matlab_cases', safeClipId);
    result = s12_psychoacoustic_analysis(struct('signal', signal, 'sample_rate_hz', sampleRateHz), caseRoot);
    if ~strcmp(result.status, 'EXECUTED_ON_PROJECT_DATA')
        error('s12:StageU:ToolBlocked', 'MATLAB Audio Toolbox did not execute: %s', char(clip.clip_id));
    end
    row = struct();
    row.clip_id = char(clip.clip_id);
    row.role = char(clip.role);
    row.reference_id = char(clip.reference_id);
    if isfield(clip, 'candidate_id')
        row.candidate_id = char(clip.candidate_id);
    else
        row.candidate_id = '';
    end
    row.vehicle_id = char(clip.vehicle_id);
    row.scenario = char(clip.scenario);
    row.input_path = inputPath;
    row.input_sha256 = char(clip.sha256);
    row.sample_rate_hz = sampleRateHz;
    row.metrics = result.metrics;
    row.units = struct('loudness_sone', 'sone', 'sharpness_acum', 'acum', 'roughness_asper', 'asper', 'fluctuation_vacil', 'vacil', 'tone_to_noise_ratio_db', 'dB', 'tone_to_noise_frequency_hz', 'Hz', 'prominence_ratio_db', 'dB', 'prominence_frequency_hz', 'Hz');
    row.tool_domain = 'Professional MATLAB';
    row.calibration = 'digital-domain relative only; not calibrated SPL';
    row.analysis_signal = 'raw common-safety PCM; not loudness-matched audition copy';
    row.order_status = 'ORDER_COMPARISON_NOT_QUALIFIED';
    rows{index} = row;
    fprintf('[%d/%d] MATLAB %s\n', index, numel(clips), char(clip.clip_id));
end
receipt = struct('schema_version', 's12-stage-u-matlab-receipt-v1', 'status', 'EXECUTED_ON_STAGE_U_RAW_CLIPS', 'matlab_release', version('-release'), 'toolchain', {{'acousticLoudness', 'acousticSharpness', 'acousticRoughness', 'acousticFluctuation', 'acousticToneToNoiseRatio', 'acousticProminenceRatio'}}, 'manifest_sha256', sha256File(manifestPath), 'clip_count', numel(rows), 'results', {rows}, 'order_status', 'ORDER_COMPARISON_NOT_QUALIFIED', 'automatic_tuning_eligible', false, 'profile_candidate_ready', false);
fid = fopen(outputPath, 'w');
if fid < 0
    error('s12:StageU:OutputOpen', 'Cannot write Stage U MATLAB receipt.');
end
fileCleaner = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(receipt), 'char');
end

function digest = sha256File(pathValue)
import java.security.*
import java.io.*
stream = FileInputStream(pathValue);
cleaner = onCleanup(@() stream.close()); %#ok<NASGU>
algorithm = MessageDigest.getInstance('SHA-256');
buffer = zeros(1, 1024 * 1024, 'int8');
while true
    count = stream.read(buffer, 0, numel(buffer));
    if count < 0
        break;
    end
    algorithm.update(buffer(1:count));
end
hash = typecast(algorithm.digest(), 'uint8');
digest = lower(reshape(dec2hex(hash, 2).', 1, []));
end
