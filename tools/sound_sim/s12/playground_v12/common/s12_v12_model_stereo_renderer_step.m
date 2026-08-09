function pcm = s12_v12_model_stereo_renderer_step(packed)
%S12_V12_MODEL_STEREO_RENDERER_STEP Fixed-frame linear stereo renderer.

if ~isnumeric(packed) || ~isequal(size(packed), [961, 1]) || ...
        any(~isfinite(packed), "all")
    error("S12:EngineSoundV12:ModelRenderer", ...
        "Model renderer input must be one finite [961,1] vector.");
end
gain = packed(end);
if gain < 0 || gain > 1
    error("S12:EngineSoundV12:ModelRenderer", ...
        "Renderer gain must be in [0,1].");
end
mono = gain * packed(1:960);
pcm = [mono, mono];
end
