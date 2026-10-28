function [mixed, context, diagnostics] = s12_v12_mix_texture_residual( ...
        prePtr, texture, weight, context)
%S12_V12_MIX_TEXTURE_RESIDUAL Optional research-only pre-PTR texture layer.
% The default weight is zero. This layer never infers vehicle state and does
% not alter the frozen PTR/Radiation adapter or product qualification gates.

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
        ~isfinite(context.frame_index) || context.frame_index < 0
    error("S12:EngineSoundV12:TextureResidual", "context.frame_index is invalid.");
end
if ~isfield(context, "weight_state") || ~isnumeric(context.weight_state) || ...
        ~isscalar(context.weight_state) || ~isfinite(context.weight_state) || ...
        context.weight_state < 0 || context.weight_state > 1
    error("S12:EngineSoundV12:TextureResidual", "context.weight_state is invalid.");
end

% Keep the research residual bounded relative to the existing pre-PTR signal.
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
diagnostics = struct( ...
    "source_class", "PUBLIC_TEXTURE_RESEARCH_ONLY", ...
    "qualification", "INSUFFICIENT_EVIDENCE", ...
    "product_candidate", false, ...
    "weight", double(weight), ...
    "effective_weight", double(weightState), ...
    "texture_rms", double(textureRms), ...
    "base_rms", double(baseRms));
end
