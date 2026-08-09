function names = s12_v12_identity_demo_names(profileId)
%S12_V12_IDENTITY_DEMO_NAMES Return the required v0.14 listening artifacts.

if ~((ischar(profileId) && isrow(profileId)) || (isstring(profileId) && isscalar(profileId)))
    error("S12:EngineIdentity:Demo", "profileId must be one text value.");
end
switch string(profileId)
    case "hellcat_2022_stock"
        stem = "hellcat";
    case "ferrari_458_stock"
        stem = "ferrari";
    case "rx7_fd_1991_stock"
        stem = "rx7";
    otherwise
        error("S12:EngineIdentity:Demo", "No v0.14 listening name is defined for this profile.");
end
names = [stem + "_identity_v01.wav", ...
    stem + "_identity_v01_idle.wav", ...
    stem + "_identity_v01_acceleration.wav", ...
    stem + "_identity_v01_lift.wav", ...
    stem + "_identity_v01_full_pull.wav"];
end
