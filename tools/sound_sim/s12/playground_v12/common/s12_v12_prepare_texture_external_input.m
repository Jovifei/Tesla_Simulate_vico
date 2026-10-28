function external = s12_v12_prepare_texture_external_input(f32lePath, durationSeconds, textureWeight, stateSchedule)
%S12_V12_PREPARE_TEXTURE_EXTERNAL_INPUT Build fixed-size research input data.
% The returned matrices are suitable for a copied Simulink candidate only.
% Source state remains UNKNOWN and no product qualification is granted.

arguments
    f32lePath (1,1) string
    durationSeconds (1,1) double {mustBeFinite, mustBePositive}
    textureWeight (1,1) double {mustBeFinite, mustBeGreaterThanOrEqual(textureWeight, 0), mustBeLessThanOrEqual(textureWeight)} = 0
    stateSchedule = struct()
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
frameCount = round(durationSeconds * frameRateHz);
weights = buildWeightSchedule(frameCount, textureWeight, stateSchedule);
crossfadeSamples = round(0.120 * sampleRateHz);
if numel(source) <= 2 * crossfadeSamples
    error("S12:EngineSoundV12:TextureInput", "Texture source is too short for the fixed crossfade.");
end

textureResidual = zeros(frameCount, frameSamples, "single");
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
            tail = source(periodSamples + blendIndex + 1);
            head = source(blendIndex + 1);
            value = (1 - alpha) * tail + alpha * head;
        end
        textureResidual(frameIndex + 1, sampleIndex + 1) = single(value);
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
    "source_sha256", sha256Bytes(bytes), ...
    "state_qualification", "INSUFFICIENT_EVIDENCE", ...
    "purpose", "RESEARCH_ONLY_NOT_PRODUCT_AUDIO", ...
    "rpm_load_gear_phase", "UNKNOWN");
end

function weights = buildWeightSchedule(frameCount, baseWeight, stateSchedule)
weights = repmat(double(baseWeight), frameCount, 1);
if isempty(fieldnames(stateSchedule))
    return;
end
required = ["time_s", "load", "acceleration"];
if ~isstruct(stateSchedule) || ~all(isfield(stateSchedule, required))
    error("S12:EngineSoundV12:TextureInput", "stateSchedule requires time_s/load/acceleration.");
end
time = reshape(double(stateSchedule.time_s), [], 1);
load = reshape(double(stateSchedule.load), [], 1);
acceleration = reshape(double(stateSchedule.acceleration), [], 1);
if numel(time) ~= frameCount || numel(load) ~= frameCount || numel(acceleration) ~= frameCount || ...
        any(~isfinite(time)) || any(~isfinite(load)) || any(~isfinite(acceleration)) || ...
        any(load < 0 | load > 1) || any(diff(time) < 0)
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
