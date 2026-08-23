function receipt = run_stage_u_audio_feature_batch(manifestPath, outputRoot)
%RUN_STAGE_U_AUDIO_FEATURE_BATCH Export per-frame MATLAB features for Stage-U triads.
arguments
    manifestPath (1,:) char
    outputRoot (1,:) char
end
if ~isfile(manifestPath)
    error('s12:StageU:SelectedManifestMissing', 'Selected clip manifest is missing.');
end
if isfolder(outputRoot)
    error('s12:StageU:FeatureBatchExists', 'Refusing to overwrite feature output root.');
end
mkdir(outputRoot);
manifest = jsondecode(fileread(manifestPath));
clips = manifest.clips;
rows = cell(1, numel(clips));
for index = 1:numel(clips)
    if iscell(clips)
        clip = clips{index};
    else
        clip = clips(index);
    end
    safeClipId = regexprep(char(clip.clip_id), '[^A-Za-z0-9_-]', '_');
    featurePath = fullfile(outputRoot, [safeClipId '.json']);
    run_stage_u_audio_features(char(clip.path), featurePath);
    row = struct();
    row.clip_id = char(clip.clip_id);
    row.role = char(clip.role);
    row.reference_id = char(clip.reference_id);
    row.candidate_id = '';
    if isfield(clip, 'candidate_id')
        row.candidate_id = char(clip.candidate_id);
    end
    row.vehicle_id = char(clip.vehicle_id);
    row.scenario = char(clip.scenario);
    row.input_sha256 = char(clip.sha256);
    row.feature_receipt_path = featurePath;
    rows{index} = row;
    fprintf('[%d/%d] audioFeatureExtractor %s\n', index, numel(clips), char(clip.clip_id));
end
receipt = struct('schema_version', 's12-stage-u-matlab-audio-feature-batch-v1', 'status', 'EXECUTED_ON_STAGE_U_TRIAD_CLIPS', 'manifest_path', manifestPath, 'clip_count', numel(rows), 'results', {rows}, 'tool', 'audioFeatureExtractor', 'matlab_release', version('-release'), 'classification', 'PROFESSIONAL_ANALYSIS_NOT_R1_ORDER_GATE');
fid = fopen(fullfile(outputRoot, 'audio_feature_batch_receipt.json'), 'w');
if fid < 0
    error('s12:StageU:FeatureBatchWrite', 'Cannot write batch receipt.');
end
cleaner = onCleanup(@() fclose(fid));
fwrite(fid, jsonencode(receipt), 'char');
end
