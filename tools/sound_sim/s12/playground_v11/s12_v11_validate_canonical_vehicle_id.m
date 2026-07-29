function vehicleId = s12_v11_validate_canonical_vehicle_id(value)
%S12_V11_VALIDATE_CANONICAL_VEHICLE_ID Reject traversal and unknown packages.

if ~((ischar(value) && isrow(value)) || (isstring(value) && isscalar(value)))
    error("S12:EngineSoundV11:ProfileId", "profile_id must be one text scalar.");
end
vehicleId = string(value);
if isempty(regexp(char(vehicleId), "^[a-z0-9_]+$", "once")) || ...
        ~ismember(vehicleId, s12_v11_canonical_vehicle_ids())
    error("S12:EngineSoundV11:ProfileId", ...
        "profile_id must be one canonical v1.1 vehicle package identifier.");
end
end
