function pressure = s12_v11_model_ptr_radiation_step(packedInput)
%S12_V11_MODEL_PTR_RADIATION_STEP Unpack one input before frozen PTR.

if ~isnumeric(packedInput) || ~isequal(size(packedInput), [965, 1]) || ...
        any(~isfinite(packedInput), "all")
    error("S12:EngineSoundV11:ModelPTR", ...
        "PTR input must pack [960,1] excitation, profile index, and [4,1] controls.");
end
excitation = double(packedInput(1:960));
profileIndex = double(packedInput(961));
ptrControls = double(packedInput(962:965));
profile = profileForIndex(profileIndex);
frameSamples = profile.renderer.frame_samples;
adapter = s12_v11_resolve_frozen_ptr_adapter();
addpath(adapter.source_folder, "-begin");
resolvedPath = string(which(adapter.function_name));
if resolvedPath ~= adapter.source_path
    error("S12:EngineSoundV11:ModelPTR", ...
        "The resolved PTR adapter is not the verified canonical frozen source.");
end
persistent reset lastProfileId
if isempty(reset) || isempty(lastProfileId) || string(lastProfileId) ~= string(profile.vehicle_id)
    reset = true;
    lastProfileId = profile.vehicle_id;
end
pressure = s12_sound_playground_ptr_tuning_step(excitation, ...
    ptrControls(1), ptrControls(2), ptrControls(3), ptrControls(4), reset);
reset = false;
if ~isequal(size(pressure), [frameSamples, 1]) || any(~isfinite(pressure), "all")
    error("S12:EngineSoundV11:ModelPTR", ...
        "Frozen PTR/Radiation adapter did not return one finite profile renderer frame.");
end
end

function profile = profileForIndex(profileIndex)
if ~isnumeric(profileIndex) || ~isscalar(profileIndex) || ~isfinite(profileIndex) || ...
        profileIndex ~= floor(profileIndex)
    error("S12:EngineSoundV11:ModelPTR", "profileIndex must be one finite integer.");
end
ids = s12_v11_canonical_vehicle_ids();
if profileIndex < 1 || profileIndex > numel(ids)
    error("S12:EngineSoundV11:ModelPTR", "profileIndex is outside the canonical vehicle list.");
end
profile = s12_v11_load_profile(ids(profileIndex));
end
