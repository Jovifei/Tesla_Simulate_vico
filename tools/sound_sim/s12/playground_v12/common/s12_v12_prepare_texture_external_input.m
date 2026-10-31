function external = s12_v12_prepare_texture_external_input(f32lePath, durationSeconds, textureWeight, stateSchedule, layerPaths, layerWeights)
%S12_V12_PREPARE_TEXTURE_EXTERNAL_INPUT Build fixed-size research input data.
% The returned matrices are suitable for a copied Simulink candidate only.
% Source state remains UNKNOWN and no product qualification is granted.

if nargin < 3, textureWeight = 0; end
if nargin < 4, stateSchedule = struct(); end
if nargin < 5, layerPaths = strings(1, 0); end
if ischar(f32lePath) && isrow(f32lePath)
    f32lePath = string(f32lePath);
end
if ~isstring(f32lePath) || ~isscalar(f32lePath) || ismissing(f32lePath)
    error("S12:EngineSoundV12:TextureInput", "f32lePath must be a scalar path.");
end
if ~isnumeric(durationSeconds) || ~isreal(durationSeconds) || ~isscalar(durationSeconds) || ...
        ~isfinite(durationSeconds) || durationSeconds <= 0
    error("S12:EngineSoundV12:TextureInput", "Duration must be a finite positive scalar.");
end
frameTotal = double(durationSeconds) * 50;
if ~isfinite(frameTotal) || round(frameTotal) < 1 || ...
        abs(frameTotal - round(frameTotal)) > 8 * eps(max(1, frameTotal))
    error("S12:EngineSoundV12:TextureInput", "Duration must contain a positive integer number of frames.");
end
if ~isnumeric(textureWeight) || ~isreal(textureWeight) || ~isscalar(textureWeight) || ...
        ~isfinite(textureWeight) || textureWeight < 0 || textureWeight > 1
    error("S12:EngineSoundV12:TextureInput", "textureWeight must be finite and in [0,1].");
end
textureWeight = double(textureWeight);
if nargin < 6, layerWeights = [textureWeight, 0, 0]; end
if ~isnumeric(layerWeights) || ~isreal(layerWeights) || ~isequal(size(layerWeights), [1, 3]) || ...
        any(~isfinite(layerWeights)) || any(layerWeights < 0 | layerWeights > 1)
    error("S12:EngineSoundV12:TextureInput", "layerWeights must be a finite 1x3 row in [0,1].");
end
if ~isstring(layerPaths) || (~isequal(size(layerPaths), [1, 0]) && ~isequal(size(layerPaths), [1, 3])) || ...
        any(ismissing(layerPaths), "all")
    error("S12:EngineSoundV12:TextureInput", "layerPaths must be an empty or 1x3 string row.");
end

if ~isfile(f32lePath)
    error("S12:EngineSoundV12:TextureInput", "F32LE texture source is missing.");
end
bytes = readBytes(f32lePath);
if mod(numel(bytes), 4) ~= 0
    error("S12:EngineSoundV12:TextureInput", "F32LE source byte length must be divisible by four.");
end
source = typecast(uint8(bytes), "single");
source = double(source(:));
if isempty(source) || any(~isfinite(source)) || any(abs(source) > 1)
    error("S12:EngineSoundV12:TextureInput", "Texture source must be finite and bounded.");
end

sampleRateHz = 48000;
frameSamples = 960;
frameRateHz = sampleRateHz / frameSamples;
frameCount = round(frameTotal);
weights = buildWeightSchedule(frameCount, textureWeight, stateSchedule);
crossfadeSamples = round(0.120 * sampleRateHz);
if numel(source) <= 2 * crossfadeSamples
    error("S12:EngineSoundV12:TextureInput", "Texture source is too short for the fixed crossfade.");
end

textureResidual = buildLayerFrames(source, frameCount, frameSamples, crossfadeSamples);

% Keep a fixed three-layer input contract. Without explicit layer files the
% legacy single texture is assigned only to the body layer; other layers stay zero.
textureLayers = zeros(frameCount, frameSamples, 3, "single");
textureLayers(:, :, 1) = textureResidual;
scheduledLayerWeights = zeros(frameCount, 3);
for layerIndex = 1:3
    scheduledLayerWeights(:, layerIndex) = buildWeightSchedule(frameCount, double(layerWeights(layerIndex)), stateSchedule);
end
layerSourceSha256 = strings(1, 3);
layerSourceSha256(1) = sha256Bytes(bytes);
if ~isempty(layerPaths)
    for layerIndex = 1:3
        if strlength(layerPaths(layerIndex)) == 0
            continue;
        end
        layerBytes = readBytes(layerPaths(layerIndex));
        if mod(numel(layerBytes), 4) ~= 0
            error("S12:EngineSoundV12:TextureInput", "Layer F32LE byte length must be divisible by four.");
        end
        layerSource = typecast(uint8(layerBytes), "single");
        layerSource = double(layerSource(:));
        if isempty(layerSource) || any(~isfinite(layerSource)) || any(abs(layerSource) > 1)
            error("S12:EngineSoundV12:TextureInput", "Layer texture must be finite and bounded.");
        end
        textureLayers(:, :, layerIndex) = buildLayerFrames(layerSource, frameCount, frameSamples, crossfadeSamples);
        layerSourceSha256(layerIndex) = sha256Bytes(layerBytes);
    end
end
for layerIndex = 2:3
    if layerWeights(layerIndex) > 0 && strlength(layerSourceSha256(layerIndex)) == 0
        error("S12:EngineSoundV12:TextureInput", "Nonzero layer weight requires a texture source.");
    end
end

external = struct( ...
    "schema", "s12.v12.texture-external-input.v1", ...
    "sample_rate_hz", sampleRateHz, ...
    "frame_samples", frameSamples, ...
    "frame_rate_hz", frameRateHz, ...
    "duration_seconds", frameCount / frameRateHz, ...
    "frame_count", frameCount, ...
    "texture_residual", textureResidual, ...
    "texture_weight", single(weights), ...
    "texture_layers", textureLayers, ...
    "texture_layer_weights", single(scheduledLayerWeights), ...
    "layer_source_sha256", layerSourceSha256, ...
    "source_sha256", sha256Bytes(bytes), ...
    "state_qualification", "INSUFFICIENT_EVIDENCE", ...
    "purpose", "RESEARCH_ONLY_NOT_PRODUCT_AUDIO", ...
    "rpm_load_gear_phase", "UNKNOWN");
end

function frames = buildLayerFrames(source, frameCount, frameSamples, crossfadeSamples)
if numel(source) <= 2 * crossfadeSamples
    error("S12:EngineSoundV12:TextureInput", "Layer texture is too short for the fixed crossfade.");
end
frames = zeros(frameCount, frameSamples, "single");
periodSamples = numel(source) - crossfadeSamples;
for frameIndex = 0:frameCount - 1
    startSample = frameIndex * frameSamples;
    for sampleIndex = 0:frameSamples - 1
        cursor = mod(startSample + sampleIndex, periodSamples);
        if cursor < periodSamples - crossfadeSamples
            value = source(cursor + crossfadeSamples + 1);
        else
            blendIndex = cursor - (periodSamples - crossfadeSamples);
            alpha = (blendIndex + 1) / crossfadeSamples;
            value = (1 - alpha) * source(periodSamples + blendIndex + 1) + alpha * source(blendIndex + 1);
        end
        frames(frameIndex + 1, sampleIndex + 1) = single(value);
    end
end
end

function weights = buildWeightSchedule(frameCount, baseWeight, stateSchedule)
weights = repmat(double(baseWeight), frameCount, 1);
required = ["time_s", "load", "acceleration"];
if ~isstruct(stateSchedule) || ~isscalar(stateSchedule)
    error("S12:EngineSoundV12:TextureInput", "stateSchedule must be a scalar struct.");
end
if isempty(fieldnames(stateSchedule))
    return;
end
if ~all(isfield(stateSchedule, required))
    error("S12:EngineSoundV12:TextureInput", "stateSchedule requires time_s/load/acceleration.");
end
for field = required
    value = stateSchedule.(field);
    if ~isnumeric(value) || ~isreal(value) || ~isvector(value) || ...
            numel(value) ~= frameCount || any(~isfinite(value))
        error("S12:EngineSoundV12:TextureInput", "State fields must be finite real frame vectors.");
    end
end
time = reshape(double(stateSchedule.time_s), [], 1);
load = reshape(double(stateSchedule.load), [], 1);
acceleration = reshape(double(stateSchedule.acceleration), [], 1);
expectedTime = (0:frameCount - 1).' * 0.02;
if any(load < 0 | load > 1) || ...
        any(abs(time - expectedTime) > 8 * eps(max(1, abs(expectedTime))))
    error("S12:EngineSoundV12:TextureInput", "stateSchedule dimensions or ranges are invalid.");
end
% Research-only state coupling: texture follows load and transient effort.
target = baseWeight * (0.25 + 0.65 * load + 0.10 * min(1, abs(acceleration) / 3));
weights(1) = target(1);
for index = 2:frameCount
    weights(index) = weights(index - 1) + 0.25 * (target(index) - weights(index - 1));
end
weights = min(1, max(0, weights));
end

function bytes = readBytes(path)
fileId = fopen(path, "r", "ieee-le");
if fileId < 0
    error("S12:EngineSoundV12:TextureInput", "Cannot open F32LE texture source.");
end
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, inf, "*uint8").';
clear cleanup
end

function digest = sha256Bytes(bytes)
engine = java.security.MessageDigest.getInstance("SHA-256");
digestBytes = typecast(engine.digest(bytes), "uint8");
digest = lower(reshape(dec2hex(digestBytes, 2).', 1, []));
end
