function result = s12_engine_sound_validate_profile(profile)
%S12_ENGINE_SOUND_VALIDATE_PROFILE Enforce synthetic-only v1.0 profile contract.

schema = jsondecode(fileread(fullfile(fileparts(mfilename("fullpath")), "engine_sound_profile_schema.json")));
schema = s12_engine_sound_normalize_profile_text(schema);
requireExactFields(profile, string(schema.required_top_level), "profile");
groups = fieldnames(schema.groups);
for index = 1:numel(groups)
    group = groups{index};
    requireExactFields(profile.(group), string(schema.groups.(group)), group);
end

[parameterCount, provenancedCount] = validateTree(profile);
if provenancedCount ~= parameterCount
    error("S12:EngineSoundV10:Provenance", "Every profile parameter requires synthetic provenance.");
end
requireScalarText(profile.profile_id.value, "profile_id");
if ~isequal(profile.synthetic.value, true) || ~isequal(profile.calibrated.value, false) || ...
        ~isequal(profile.offline.value, true) || ~isequal(profile.realtime_qualified.value, false)
    error("S12:EngineSoundV10:Identity", "Profiles must remain synthetic, uncalibrated, offline, and not realtime-qualified.");
end

cylinders = profile.engine.cylinder_count.value;
if ~isnumeric(cylinders) || ~isscalar(cylinders) || ~ismember(cylinders, double(schema.allowed_cylinder_counts))
    error("S12:EngineSoundV10:CylinderCount", "Cylinder count must be one of 3, 4, 5, 6, or 8.");
end
firingOrder = profile.engine.firing_order.value;
if ~isnumeric(firingOrder) || numel(firingOrder) ~= cylinders || ...
        ~isequal(sort(reshape(firingOrder, 1, [])), 1:cylinders)
    error("S12:EngineSoundV10:FiringOrder", "Firing order must be a permutation of 1:cylinder_count.");
end
if numel(profile.engine.firing_phase_deg.value) ~= cylinders || numel(profile.engine.bank_map.value) ~= cylinders
    error("S12:EngineSoundV10:EngineArrayLength", "Firing phase and bank map must match cylinder_count.");
end
idleRpm = profile.engine.idle_rpm.value;
redlineRpm = profile.engine.redline_rpm.value;
if ~isnumeric(idleRpm) || ~isnumeric(redlineRpm) || ~isscalar(idleRpm) || ~isscalar(redlineRpm) || ...
        ~isfinite(idleRpm) || ~isfinite(redlineRpm) || idleRpm < 500 || redlineRpm > 10000 || idleRpm >= redlineRpm
    error("S12:EngineSoundV10:RpmRange", "RPM range must be finite, ordered, and within 500..10000 rpm.");
end
orderGains = profile.synthesis.order_gains.value;
if ~isnumeric(orderGains) || numel(orderGains) ~= 6 || any(~isfinite(orderGains)) || any(orderGains < 0)
    error("S12:EngineSoundV10:OrderGainLength", "Exactly six nonnegative synthetic order gains are required.");
end
level = string(profile.backfire.default_level.value);
if ~isscalar(level) || ~ismember(level, string(schema.allowed_backfire_levels))
    error("S12:EngineSoundV10:BackfireLevel", "Backfire level must be off, subtle, or aggressive.");
end
if profile.renderer.sample_rate_hz.value ~= 48000 || profile.renderer.frame_samples.value ~= 960
    error("S12:EngineSoundV10:AudioFormat", "v1.0 is fixed at 48 kHz and 960 samples per frame.");
end
result = struct("valid", true, "parameter_count", parameterCount, ...
    "provenance_coverage", provenancedCount / parameterCount);
end

function requireExactFields(value, expected, context)
if ~isstruct(value) || numel(value) ~= 1
    error("S12:EngineSoundV10:Schema", "%s must be a scalar struct.", context);
end
actual = string(fieldnames(value));
if ~isequal(sort(actual), sort(expected))
    unknown = setdiff(actual, expected);
    if ~isempty(unknown)
        error("S12:EngineSoundV10:UnknownField", "Unknown field in %s: %s", context, join(unknown, ", "));
    end
    error("S12:EngineSoundV10:Schema", "Missing or invalid fields in %s.", context);
end
end

function [count, provenanced] = validateTree(value)
if ~isstruct(value)
    error("S12:EngineSoundV10:Schema", "Profile content must be structs of descriptors.");
end
count = 0;
provenanced = 0;
for element = 1:numel(value)
    names = reshape(string(fieldnames(value(element))), 1, []);
    if any(names == "value")
        expected = ["value", "unit", "range", "source_level", "source"];
        if ~isequal(sort(names), sort(expected))
            error("S12:EngineSoundV10:Provenance", "Each descriptor needs value, unit, range, source_level, and source.");
        end
        count = count + 1;
        if string(value(element).source_level) == "C" && string(value(element).source) == "synthetic"
            provenanced = provenanced + 1;
        else
            error("S12:EngineSoundV10:Provenance", "Only source_level C / synthetic parameters are allowed.");
        end
        continue
    end
    for index = 1:numel(names)
        [childCount, childProvenanced] = validateTree(value(element).(names(index)));
        count = count + childCount;
        provenanced = provenanced + childProvenanced;
    end
end
end

function requireScalarText(value, name)
value = string(value);
if ~isscalar(value) || strlength(value) == 0
    error("S12:EngineSoundV10:Schema", "%s must be one nonempty text scalar.", name);
end
end
