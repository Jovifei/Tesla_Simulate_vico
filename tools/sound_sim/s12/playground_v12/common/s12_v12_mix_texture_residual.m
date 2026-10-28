function [mixed, context, diagnostics] = s12_v12_mix_texture_residual( ...
        prePtr, texture, weight, context)
%S12_V12_MIX_TEXTURE_RESIDUAL Optional research-only pre-PTR texture layer.

if nargin < 4 || isempty(context)
    context = struct("frame_index", 0, "weight_state", 0);
end
if ~isnumeric(prePtr) || ~isequal(size(prePtr), [960, 1]) || any(~isfinite(prePtr), "all")
    error("S12:EngineSoundV12:TextureResidual", "prePtr must be one finite [960,1] frame.");
end
if ~isnumeric(texture) || ~isequal(size(texture), [960, 1]) || any(~isfinite(texture), "all")
    error("S12:EngineSoundV12:TextureResidual", "texture must be one finite [960,1] frame.");
end
if ~isnumeric(weight) || ~isscalar(weight) || ~isfinite(weight) || weight < 0 || weight > 1
    error("S12:EngineSoundV12:TextureResidual", "weight must be within [0,1].");
end
if ~isstruct(context) || ~isscalar(context) || ~isfield(context, "frame_index") || ...
        ~isnumeric(context.frame_index) || ~isscalar(context.frame_index) || ...
        ~isfinite(context.frame_index) || context.frame_index < 0 || ...
        ~isfield(context, "weight_state") || ~isscalar(context.weight_state) || ...
        ~isfinite(context.weight_state) || context.weight_state < 0 || context.weight_state > 1
    error("S12:EngineSoundV12:TextureResidual", "context is invalid.");
end
textureRms = sqrt(mean(texture .^ 2));
baseRms = sqrt(mean(prePtr .^ 2));
if textureRms > eps && baseRms > eps
    texture = texture * min(1, baseRms / textureRms);
end
weightState = context.weight_state + 0.25 * (double(weight) - context.weight_state);
if weight == 0
    weightState = 0;
end
mixed = (1 - weightState) * prePtr + weightState * texture;
if any(~isfinite(mixed), "all") || any(abs(mixed) > 1, "all")
    error("S12:EngineSoundV12:TextureResidual", "mixed frame is outside the finite PCM contract.");
end
context.frame_index = context.frame_index + 1;
context.weight_state = weightState;
diagnostics = struct("source_class", "PUBLIC_TEXTURE_RESEARCH_ONLY", ...
    "qualification", "INSUFFICIENT_EVIDENCE", "product_candidate", false, ...
    "weight", double(weight), "effective_weight", double(weightState), ...
    "texture_rms", double(textureRms), "base_rms", double(baseRms));
end

function [mixed, context, diagnostics] = s12_v12_mix_texture_layers( ...
        prePtr, bodyTexture, mechanicalTexture, broadbandTexture, weights, context)
%S12_V12_MIX_TEXTURE_LAYERS Research-only layered residual before frozen PTR.
if nargin < 6 || isempty(context)
    context = struct("frame_index", 0, "weight_state", zeros(1, 3));
end
textures = [bodyTexture, mechanicalTexture, broadbandTexture];
if ~isnumeric(prePtr) || ~isequal(size(prePtr), [960, 1]) || ...
        ~isequal(size(textures), [960, 3]) || any(~isfinite(prePtr), "all") || any(~isfinite(textures), "all") || ...
        ~isnumeric(weights) || ~isequal(size(weights), [1, 3]) || any(~isfinite(weights)) || any(weights < 0 | weights > 1) || ...
        ~isfield(context, "weight_state") || ~isequal(size(context.weight_state), [1, 3])
    error("S12:EngineSoundV12:TextureLayers", "layered texture contract is invalid.");
end
baseRms = sqrt(mean(prePtr .^ 2));
layerRms = sqrt(mean(textures .^ 2, 1));
for index = 1:3
    if layerRms(index) > eps && baseRms > eps
        textures(:, index) = textures(:, index) * min(1, baseRms / layerRms(index));
    end
end
effective = context.weight_state + 0.25 * (double(weights) - context.weight_state);
if all(weights == 0), effective = zeros(1, 3); end
mixed = prePtr + textures * effective.';
if any(~isfinite(mixed), "all") || any(abs(mixed) > 1, "all")
    error("S12:EngineSoundV12:TextureLayers", "layered mix is outside finite/peak contract.");
end
context.frame_index = context.frame_index + 1;
context.weight_state = effective;
diagnostics = struct("source_class", "PUBLIC_TEXTURE_LAYERS_RESEARCH_ONLY", ...
    "qualification", "INSUFFICIENT_EVIDENCE", "product_candidate", false, ...
    "weights", double(weights), "effective_weights", double(effective), ...
    "layer_rms", double(layerRms), "base_rms", double(baseRms));
end
