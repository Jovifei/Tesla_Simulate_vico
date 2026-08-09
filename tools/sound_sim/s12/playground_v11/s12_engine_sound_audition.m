function result = s12_engine_sound_audition(profileInput, varargin)
%S12_ENGINE_SOUND_AUDITION Compatibility audition for one v1.1 package.
% Variant and Perspective are declarations, not OEM calibration controls.

parser = inputParser;
parser.addParameter("BackfireLevel", "subtle");
parser.addParameter("Variant", "stock");
parser.addParameter("Perspective", "exterior_rear");
parser.addParameter("Play", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("RunId", "");
parser.addParameter("ScenarioKey", "s12-v11-compatibility-audition");
parser.parse(varargin{:});
profile = resolveCanonicalProfile(profileInput);
validateDeclaredText(parser.Results.Variant, "Variant", "stock");
validateDeclaredText(parser.Results.Perspective, "Perspective", "exterior_rear");
level = validateAfterfireLevel(parser.Results.BackfireLevel);
result = s12_v11_audition_profile(profile, ...
    "AfterfireLevel", level, ...
    "Play", parser.Results.Play, ...
    "RunId", parser.Results.RunId, ...
    "ScenarioKey", parser.Results.ScenarioKey);
result.variant = "stock";
result.perspective = "exterior_rear";
end

function profile = resolveCanonicalProfile(value)
if isstruct(value)
    if ~isscalar(value) || ~isfield(value, "vehicle_id")
        error("S12:EngineSoundV11:ProfileId", ...
            "A compatibility profile struct must contain one canonical vehicle_id.");
    end
    profile = s12_v11_load_profile(s12_v11_validate_canonical_vehicle_id(value.vehicle_id));
else
    profile = s12_v11_load_profile(s12_v11_validate_canonical_vehicle_id(value));
end
end

function value = validateAfterfireLevel(value)
if ~((ischar(value) && isrow(value)) || (isstring(value) && isscalar(value)))
    error("S12:EngineSoundV11:Option", "BackfireLevel must be one text scalar.");
end
value = lower(string(value));
if ~ismember(value, ["off", "subtle", "aggressive"])
    error("S12:EngineSoundV11:Option", ...
        "BackfireLevel must be off, subtle, or aggressive.");
end
end

function validateDeclaredText(value, name, expected)
if ~((ischar(value) && isrow(value)) || (isstring(value) && isscalar(value))) || ...
        lower(string(value)) ~= expected
    error("S12:EngineSoundV11:Option", "%s must remain %s for v1.1.", name, expected);
end
end
