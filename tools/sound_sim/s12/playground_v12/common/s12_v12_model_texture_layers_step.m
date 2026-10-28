function frame = s12_v12_model_texture_layers_step( ...
        prePtr, bodyTexture, mechanicalTexture, broadbandTexture, weights)
%S12_V12_MODEL_TEXTURE_LAYERS_STEP Fixed-frame layered research texture block.
% Three independent weights are smoothed across frames; all-zero bypass is exact.

persistent weightState
if ~isnumeric(prePtr) || ~isequal(size(prePtr), [960, 1]) || any(~isfinite(prePtr), "all") || ...
        ~isnumeric(bodyTexture) || ~isequal(size(bodyTexture), [960, 1]) || any(~isfinite(bodyTexture), "all") || ...
        ~isnumeric(mechanicalTexture) || ~isequal(size(mechanicalTexture), [960, 1]) || any(~isfinite(mechanicalTexture), "all") || ...
        ~isnumeric(broadbandTexture) || ~isequal(size(broadbandTexture), [960, 1]) || any(~isfinite(broadbandTexture), "all")
    error("S12:EngineSoundV12:ModelTextureLayers", "layer inputs must be finite [960,1] vectors.");
end
if ~isnumeric(weights) || ~isequal(size(weights), [1, 3]) || any(~isfinite(weights)) || any(weights < 0 | weights > 1)
    error("S12:EngineSoundV12:ModelTextureLayers", "weights must be a bounded [1,3] row.");
end
if isempty(weightState) || all(weights == 0)
    weightState = zeros(1, 3);
end
weightState = weightState + 0.25 * (double(weights) - weightState);
if all(weights == 0), weightState = zeros(1, 3); end
textures = [bodyTexture, mechanicalTexture, broadbandTexture];
baseRms = sqrt(mean(prePtr .^ 2));
layerRms = sqrt(mean(textures .^ 2, 1));
for index = 1:3
    if layerRms(index) > eps && baseRms > eps
        textures(:, index) = textures(:, index) * min(1, baseRms / layerRms(index));
    end
end
frame = prePtr + textures * weightState.';
if ~isequal(size(frame), [960, 1]) || any(~isfinite(frame), "all") || any(abs(frame) > 1, "all")
    error("S12:EngineSoundV12:ModelTextureLayers", "layered output is invalid.");
end
end
