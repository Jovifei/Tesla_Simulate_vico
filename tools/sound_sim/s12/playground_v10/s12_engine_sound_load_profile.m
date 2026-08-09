function profile = s12_engine_sound_load_profile(identifier)
%S12_ENGINE_SOUND_LOAD_PROFILE Load, normalize, and validate one JSON profile.

identifier = string(identifier);
if ~isscalar(identifier) || strlength(identifier) == 0
    error("S12:EngineSoundV10:ProfileId", "Profile identifier must be one nonempty text scalar.");
end
root = fileparts(mfilename("fullpath"));
if isfile(identifier)
    path = identifier;
else
    path = fullfile(root, "profiles", identifier + ".json");
end
if ~isfile(path)
    error("S12:EngineSoundV10:ProfileNotFound", "Unknown profile or JSON path: %s", identifier);
end
profile = s12_engine_sound_normalize_profile_text(jsondecode(fileread(path)));
profile.engine.firing_order.value = reshape(profile.engine.firing_order.value, 1, []);
profile.engine.firing_phase_deg.value = reshape(profile.engine.firing_phase_deg.value, 1, []);
profile.engine.bank_map.value = reshape(profile.engine.bank_map.value, 1, []);
profile.synthesis.order_gains.value = reshape(profile.synthesis.order_gains.value, 1, []);
s12_engine_sound_validate_profile(profile);
end
