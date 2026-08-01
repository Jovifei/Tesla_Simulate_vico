function identity = s12_v12_load_engine_identity_profile(profileId)
%S12_V12_LOAD_ENGINE_IDENTITY_PROFILE Load one synthetic v0.4 identity profile.

if ~((ischar(profileId) && isrow(profileId)) || (isstring(profileId) && isscalar(profileId)))
    error("S12:EngineIdentity:Profile", "profileId must be one text value.");
end
profileId = string(profileId);
path = fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
    "vehicles", profileId, "engine_identity_profile.json");
if ~isfile(path)
    error("S12:EngineIdentity:Profile", "Engine identity profile does not exist.");
end
identity = s12_v12_validate_engine_identity_profile(jsondecode(fileread(path)));
if identity.profile_id ~= profileId
    error("S12:EngineIdentity:Profile", "Engine identity profile_id does not match its path.");
end
end
