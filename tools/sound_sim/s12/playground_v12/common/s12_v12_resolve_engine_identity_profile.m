function identity = s12_v12_resolve_engine_identity_profile(source, profileId)
%S12_V12_RESOLVE_ENGINE_IDENTITY_PROFILE Bind a source topology to v0.4 identity.
% The optional profileId is supplied by the Simulink adapter.  The structural
% fallback keeps the existing offline frame APIs backward compatible.

if nargin < 2 || isempty(profileId)
    profileId = inferProfileId(source);
else
    if ~((ischar(profileId) && isrow(profileId)) || ...
            (isstring(profileId) && isscalar(profileId)))
        error("S12:EngineIdentity:Route", "profileId must be one text value.");
    end
    profileId = string(profileId);
end

identity = s12_v12_load_engine_identity_profile(profileId);
if identity.profile_id == "rx7_fd_1991_stock"
    matched = source.engine_kind == "rotary" && source.rotor_count == 2;
else
    matched = source.engine_kind == "piston" && source.cylinders == 8;
end
if ~matched
    error("S12:EngineIdentity:Route", ...
        "Engine identity does not match the validated source topology.");
end
end

function profileId = inferProfileId(source)
if source.engine_kind == "rotary" && source.rotor_count == 2
    profileId = "rx7_fd_1991_stock";
    return
end
if source.engine_kind ~= "piston" || source.cylinders ~= 8 || ...
        isempty(source.order_surface)
    error("S12:EngineIdentity:Route", ...
        "A v0.4 identity profile cannot be inferred from this source topology.");
end

primaryOrder = source.order_surface(1).order;
if primaryOrder == 2
    profileId = "hellcat_2022_stock";
elseif primaryOrder == 4
    profileId = "ferrari_458_stock";
else
    error("S12:EngineIdentity:Route", ...
        "A v0.4 piston identity requires an explicit profileId for this order surface.");
end
end
