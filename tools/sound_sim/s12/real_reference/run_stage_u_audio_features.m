function receipt = run_stage_u_audio_features(inputPath, outputPath, expectedSha256)
%RUN_STAGE_U_AUDIO_FEATURES Execute Audio Toolbox frame features on one raw WAV.
arguments
    inputPath (1,:) char
    outputPath (1,:) char
    expectedSha256 (1,:) char = ''
end
if ~isfile(inputPath)
    error('s12:StageU:FeatureInputMissing', 'Input WAV is missing: %s', inputPath);
end
if isfile(outputPath)
    error('s12:StageU:FeatureOutputExists', 'Refusing to overwrite receipt: %s', outputPath);
end
actualSha256 = sha256File(inputPath);
if ~isempty(expectedSha256) && ~strcmpi(actualSha256, expectedSha256)
    error('s12:StageU:FeatureInputShaMismatch', 'Input WAV SHA-256 does not match the manifest: %s', inputPath);
end
[signal, sampleRateHz] = audioread(inputPath);
signal = mean(double(signal), 2);
extractor = audioFeatureExtractor( ...
    SampleRate=sampleRateHz, ...
    SpectralDescriptorInput="linearSpectrum", ...
    barkSpectrum=true, erbSpectrum=true, mfcc=true, gtcc=true, ...
    spectralFlux=true, spectralFlatness=true, spectralEntropy=true, ...
    pitch=true, harmonicRatio=true, shortTimeEnergy=true);
features = extract(extractor, signal);
featureInfo = info(extractor);
receipt = struct( ...
    'schema_version', 's12-stage-u-matlab-audio-feature-receipt-v1', ...
    'status', 'EXECUTED_ON_RAW_ANALYSIS_SIGNAL', ...
    'tool_domain', 'Professional MATLAB audioFeatureExtractor', ...
    'matlab_release', version('-release'), ...
    'input_path', inputPath, ...
    'input_sha256', actualSha256, ...
    'sample_rate_hz', sampleRateHz, ...
    'frame_count', size(features, 1), ...
    'feature_vector_length', size(features, 2), ...
    'feature_info', featureInfo, ...
    'features', features, ...
    'analysis_signal', 'raw unmodified digital-domain signal; not loudness-matched audition copy', ...
    'classification', 'PROFESSIONAL_ANALYSIS_NOT_R1_ORDER_GATE');
fid = fopen(outputPath, 'w');
if fid < 0
    error('s12:StageU:FeatureOutputOpen', 'Cannot write receipt: %s', outputPath);
end
cleaner = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(receipt), 'char');
end

function digest = sha256File(pathValue)
import java.security.*
[fileId, message] = fopen(pathValue, 'rb');
if fileId < 0
    error('s12:StageU:HashInputOpen', 'Cannot read file for SHA-256: %s (%s)', pathValue, message);
end
cleaner = onCleanup(@() fclose(fileId)); %#ok<NASGU>
bytes = fread(fileId, Inf, '*uint8');
algorithm = MessageDigest.getInstance('SHA-256');
algorithm.update(typecast(bytes, 'int8'));
hash = typecast(algorithm.digest(), 'uint8');
digest = lower(reshape(dec2hex(hash, 2).', 1, []));
end
