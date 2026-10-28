function [prePtrExcitation, context, diagnostics] = s12_v12_render_pre_ptr_frame( ...
        state, sourceProfile, context, sampleRateHz, frameSamples, identityProfileId, ...
        textureResidual, textureWeight)
%S12_V12_RENDER_PRE_PTR_FRAME Route source banks to frozen one-port PTR input.
% This adapter is the explicit causal handoff: vehicle state -> source layers
% -> independent banks -> fixed mixer -> frozen PTR/Radiation. It does not
% call audio or alter any frozen physical-network mathematics.

if nargin < 6
    identityProfileId = [];
end
if nargin < 7 || isempty(textureResidual)
    textureResidual = zeros(frameSamples, 1);
end
if nargin < 8 || isempty(textureWeight)
    textureWeight = 0;
end
[bankExcitation, context, diagnostics] = s12_v12_render_source_frame( ...
    state, sourceProfile, context, sampleRateHz, frameSamples, identityProfileId);
prePtrExcitation = s12_v12_mix_bank_excitation(bankExcitation);
if ~isequal(size(textureResidual), [frameSamples, 1]) || any(~isfinite(textureResidual), "all")
    error("S12:EngineSoundV12:PrePtrTexture", ...
        "textureResidual must be one finite [frameSamples,1] frame.");
end
[prePtrExcitation, textureContext, textureDiagnostics] = ...
    s12_v12_mix_texture_residual(prePtrExcitation, textureResidual, textureWeight, ...
    context.texture_residual);
context.texture_residual = textureContext;
if ~isequal(size(prePtrExcitation), [frameSamples, 1]) || ...
        any(~isfinite(prePtrExcitation), "all")
    error("S12:EngineSoundV12:PrePtrRoute", ...
        "prePtrExcitation must be one finite [frameSamples, 1] pressure frame.");
end
diagnostics.pre_ptr_adapter = "bank_excitation_to_one_port_ptr_input";
diagnostics.texture_residual = textureDiagnostics;
end
