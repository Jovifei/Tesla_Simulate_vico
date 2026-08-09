function modelPath = s12_engine_sound_model_path(profileInput)
%S12_ENGINE_SOUND_MODEL_PATH Return the independent top-model for a profile.

if isstruct(profileInput)
    profile = profileInput;
    s12_engine_sound_validate_profile(profile);
else
    profile = s12_engine_sound_load_profile(profileInput);
end
ids = ["inline3_turbo", "inline4_sport", "inline5_character", "inline6_smooth", ...
    "v6_sport", "hellcat_style_supercharged_v8", "ferrari_style_high_rev_v8"];
models = ["S12_I3_Turbo_v10.slx", "S12_I4_Sport_v10.slx", "S12_I5_Character_v10.slx", ...
    "S12_I6_Smooth_v10.slx", "S12_V6_Sport_v10.slx", "S12_V8_Muscle_v10.slx", ...
    "S12_V8_HighRev_v10.slx"];
index = find(ids == profile.profile_id.value, 1);
if isempty(index)
    error("S12:EngineSoundV10:Model", "No top model is registered for profile %s.", profile.profile_id.value);
end
modelPath = string(fullfile(fileparts(mfilename("fullpath")), models(index)));
if ~isfile(modelPath)
    error("S12:EngineSoundV10:Model", "Top model does not exist: %s", modelPath);
end
end
