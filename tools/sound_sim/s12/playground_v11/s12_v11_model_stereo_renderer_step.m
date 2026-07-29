function pcm = s12_v11_model_stereo_renderer_step(packedInput, profileIndex)
%S12_V11_MODEL_STEREO_RENDERER_STEP Unpack pressure/gain from one input.

profile = profileForIndex(profileIndex);
frameSamples = profile.renderer.frame_samples;
channels = profile.renderer.channels;
if ~isnumeric(packedInput) || ~isequal(size(packedInput), [961, 1]) || ...
        any(~isfinite(packedInput), "all")
    error("S12:EngineSoundV11:ModelRenderer", ...
        "Renderer input must pack [960,1] pressure plus one gain value.");
end
pressure = double(packedInput(1:960));
gain = double(packedInput(961));
if ~isnumeric(gain) || ~isscalar(gain) || ~isfinite(gain) || gain < 0 || gain > 0.2
    error("S12:EngineSoundV11:ModelRenderer", ...
        "Dashboard renderer gain must be one finite JSON-bounded scalar.");
end
pcm = gain * [ ...
    pressure, (1 - profile.character.stereo_offset) * pressure];
if ~isequal(size(pcm), [frameSamples, channels]) || any(~isfinite(pcm), "all") || ...
        max(abs(pcm), [], "all") >= 1
    error("S12:EngineSoundV11:ModelRenderer", ...
        "Renderer must produce finite non-clipping profile-configured PCM without limiting.");
end
end

function profile = profileForIndex(profileIndex)
if ~isnumeric(profileIndex) || ~isscalar(profileIndex) || ~isfinite(profileIndex) || ...
        profileIndex ~= floor(profileIndex)
    error("S12:EngineSoundV11:ModelRenderer", "profileIndex must be one finite integer.");
end
ids = s12_v11_canonical_vehicle_ids();
if profileIndex < 1 || profileIndex > numel(ids)
    error("S12:EngineSoundV11:ModelRenderer", "profileIndex is outside the canonical vehicle list.");
end
profile = s12_v11_load_profile(ids(profileIndex));
end
