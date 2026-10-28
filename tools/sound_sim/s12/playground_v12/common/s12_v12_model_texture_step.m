function frame = s12_v12_model_texture_step(prePtr, textureResidual, textureWeight)
%S12_V12_MODEL_TEXTURE_STEP Fixed-frame research texture MATLAB Function entry.
% This block is optional and defaults to the legacy pre-PTR path at weight 0.

persistent weightState
if ~isnumeric(prePtr) || ~isequal(size(prePtr), [960, 1]) || any(~isfinite(prePtr), "all")
    error("S12:EngineSoundV12:ModelTexture", "prePtr must be one finite [960,1] vector.");
end
if ~isnumeric(textureResidual) || ~isequal(size(textureResidual), [960, 1]) || ...
        any(~isfinite(textureResidual), "all")
    error("S12:EngineSoundV12:ModelTexture", ...
        "textureResidual must be one finite [960,1] vector.");
end
if ~isnumeric(textureWeight) || ~isscalar(textureWeight) || ~isfinite(textureWeight) || ...
        textureWeight < 0 || textureWeight > 1
    error("S12:EngineSoundV12:ModelTexture", "textureWeight must be within [0,1].");
end
if isempty(weightState) || textureWeight == 0
    % Zero weight is the explicit run/reset boundary for the research layer.
    weightState = 0;
end
textureRms = sqrt(mean(textureResidual .^ 2));
baseRms = sqrt(mean(prePtr .^ 2));
if textureRms > eps && baseRms > eps
    textureResidual = textureResidual * min(1, baseRms / textureRms);
end
weightState = weightState + 0.25 * (double(textureWeight) - weightState);
if textureWeight == 0
    weightState = 0;
end
frame = (1 - weightState) * prePtr + weightState * textureResidual;
if ~isequal(size(frame), [960, 1]) || any(~isfinite(frame), "all") || any(abs(frame) > 1, "all")
    error("S12:EngineSoundV12:ModelTexture", "Texture MATLAB Function output is invalid.");
end
end
