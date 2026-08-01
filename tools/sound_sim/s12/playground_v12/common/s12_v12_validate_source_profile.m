function sourceProfile = s12_v12_validate_source_profile(profile)
%S12_V12_VALIDATE_SOURCE_PROFILE Validate one synthetic pre-PTR source profile.
% The structural contract mirrors source_profile_v12.schema.json. Every value
% that can affect rendering must carry C/synthetic provenance in JSON before it
% is unwrapped for numerical rendering.

profileFields = ["schema_version", "source", "transient", "gearbox", "afterfire"];
if ~isstruct(profile) || ~isscalar(profile) || ~hasExactFields(profile, profileFields) || ...
        ~isTextScalar(profile.schema_version) || ...
        string(profile.schema_version) ~= "s12-engine-sound-v12-source-profile-1"
    error("S12:EngineSoundV12:SourceProfile", "Profile does not satisfy source_profile_v12.");
end

source = profile.source;
requiredSource = ["engine_kind", "cylinders", "rotor_count", ...
    "chambers_per_rotor", "shaft_turns_per_rotor_turn", "layout", ...
    "firing_order", "firing_phases_deg", "bank_map", "pulse_sharpness", ...
    "combustion_gain", "intake_gain", "induction_gain", "mechanical_gain", ...
    "flow_gain", "order_surface"];
if ~isstruct(source) || ~isscalar(source) || ~hasExactFields(source, requiredSource)
    error("S12:EngineSoundV12:SourceProfile", "source is incomplete.");
end

sourceProfile = struct();
sourceProfile.engine_kind = enumText(source.engine_kind, "source.engine_kind");
sourceProfile.layout = enumText(source.layout, "source.layout");
sourceProfile.cylinders = scalarInteger(source.cylinders, "source.cylinders", 0, 12);
sourceProfile.rotor_count = scalarInteger(source.rotor_count, "source.rotor_count", 0, 2);
sourceProfile.chambers_per_rotor = scalarInteger(source.chambers_per_rotor, ...
    "source.chambers_per_rotor", 0, 3);
sourceProfile.shaft_turns_per_rotor_turn = scalarNumber(source.shaft_turns_per_rotor_turn, ...
    "source.shaft_turns_per_rotor_turn", 1, 3);
sourceProfile.firing_order = rowVector(source.firing_order, "source.firing_order");
sourceProfile.firing_phases_deg = rowVector(source.firing_phases_deg, "source.firing_phases_deg");
sourceProfile.bank_map = rowVector(source.bank_map, "source.bank_map");
sourceProfile.pulse_sharpness = scalarNumber(source.pulse_sharpness, "source.pulse_sharpness", 0, 1);
sourceProfile.combustion_gain = scalarNumber(source.combustion_gain, "source.combustion_gain", 0, 1);
sourceProfile.intake_gain = scalarNumber(source.intake_gain, "source.intake_gain", 0, 1);
sourceProfile.induction_gain = scalarNumber(source.induction_gain, "source.induction_gain", 0, 1);
sourceProfile.mechanical_gain = scalarNumber(source.mechanical_gain, "source.mechanical_gain", 0, 1);
sourceProfile.flow_gain = scalarNumber(source.flow_gain, "source.flow_gain", 0, 1);
sourceProfile.order_surface = unwrapOrderSurface(source.order_surface);
sourceProfile.transient = unwrapSection(profile.transient, ...
    ["acceleration_attack_gain", "lift_decay_gain"], "transient");
sourceProfile.gearbox = unwrapSection(profile.gearbox, ...
    ["torque_cut_gain", "shift_bark_gain"], "gearbox");
sourceProfile.afterfire = unwrapSection(profile.afterfire, ...
    ["upshift_bark_gain", "downshift_blip_pop_gain", "overrun_crackle_gain"], "afterfire");

validateTopology(sourceProfile);
end

function value = parameterValue(parameter, label)
required = ["value", "unit", "range", "source_level", "source", "source_url", ...
    "source_scope", "verification_state"];
if ~isstruct(parameter) || ~isscalar(parameter) || ~hasExactFields(parameter, required) || ...
        ~isTextScalar(parameter.source_level) || ~isTextScalar(parameter.source) || ...
        ~isTextScalarOrEmpty(parameter.source_url) || ~isTextScalar(parameter.verification_state) || ...
        ~isTextScalar(parameter.unit) || ~isTextScalar(parameter.source_scope) || ...
        string(parameter.source_level) ~= "C" || string(parameter.source) ~= "synthetic" || ...
        string(parameter.source_url) ~= "" || ...
        string(parameter.verification_state) ~= "synthetic_assumption" || ...
        strlength(string(parameter.unit)) == 0 || strlength(string(parameter.source_scope)) == 0 || ...
        numel(parameter.range) < 2
    error("S12:EngineSoundV12:SourceProfile", "%s provenance record is invalid.", label);
end
value = parameter.value;
if isnumeric(value)
    if ~isnumeric(parameter.range) || ~isvector(parameter.range) || ...
            any(~isfinite(parameter.range), "all") || ...
            any(~isfinite(value), "all") || ...
            any(value < min(parameter.range) | value > max(parameter.range), "all")
        error("S12:EngineSoundV12:SourceProfile", "%s numeric range is invalid.", label);
    end
elseif isTextScalar(value)
    if ~(iscellstr(parameter.range) || isstring(parameter.range)) || ...
            ~any(string(parameter.range) == string(value))
        error("S12:EngineSoundV12:SourceProfile", "%s enum range is invalid.", label);
    end
else
    error("S12:EngineSoundV12:SourceProfile", "%s value type is unsupported.", label);
end
end

function value = scalarNumber(parameter, label, lower, upper)
value = parameterValue(parameter, label);
if ~isnumeric(value) || ~isscalar(value) || ~isfinite(value) || value < lower || value > upper
    error("S12:EngineSoundV12:SourceProfile", "%s is outside the bounded source contract.", label);
end
value = double(value);
end

function value = enumText(parameter, label)
value = parameterValue(parameter, label);
if ~isTextScalar(value)
    error("S12:EngineSoundV12:SourceProfile", "%s must be one text enum value.", label);
end
value = string(value);
end

function value = scalarInteger(parameter, label, lower, upper)
value = scalarNumber(parameter, label, lower, upper);
if value ~= floor(value)
    error("S12:EngineSoundV12:SourceProfile", "%s must be an integer.", label);
end
end

function values = rowVector(parameter, label)
values = parameterValue(parameter, label);
if ~isnumeric(values) || ~isvector(values) || isempty(values) || any(~isfinite(values), "all")
    error("S12:EngineSoundV12:SourceProfile", "%s must be a finite vector.", label);
end
values = reshape(double(values), 1, []);
end

function section = unwrapSection(raw, fields, label)
if ~isstruct(raw) || ~isscalar(raw) || ~hasExactFields(raw, fields)
    error("S12:EngineSoundV12:SourceProfile", "%s is incomplete.", label);
end
section = struct();
for index = 1:numel(fields)
    field = fields(index);
    section.(field) = scalarNumber(raw.(field), label + "." + field, 0, 1);
end
end

function entries = unwrapOrderSurface(raw)
required = ["order", "rpm_nodes", "low_load_gains", "high_load_gains", "phase_rad"];
if ~isstruct(raw) || isempty(raw) || ~hasExactFields(raw, required)
    error("S12:EngineSoundV12:SourceProfile", "source.order_surface is incomplete.");
end
entries = repmat(struct("order", 0, "rpm_nodes", [], "low_load_gains", [], ...
    "high_load_gains", [], "phase_rad", []), 1, numel(raw));
for index = 1:numel(raw)
    entries(index).order = scalarNumber(raw(index).order, "source.order_surface.order", 0.5, 18);
    entries(index).rpm_nodes = rowVector(raw(index).rpm_nodes, "source.order_surface.rpm_nodes");
    entries(index).low_load_gains = rowVector(raw(index).low_load_gains, "source.order_surface.low_load_gains");
    entries(index).high_load_gains = rowVector(raw(index).high_load_gains, "source.order_surface.high_load_gains");
    entries(index).phase_rad = rowVector(raw(index).phase_rad, "source.order_surface.phase_rad");
    if numel(entries(index).rpm_nodes) < 2 || ...
            any(diff(entries(index).rpm_nodes) <= 0) || ...
            any(entries(index).rpm_nodes < 0 | entries(index).rpm_nodes > 12000) || ...
            numel(entries(index).low_load_gains) ~= numel(entries(index).rpm_nodes) || ...
            numel(entries(index).high_load_gains) ~= numel(entries(index).rpm_nodes) || ...
            numel(entries(index).phase_rad) ~= numel(entries(index).rpm_nodes) || ...
            any(entries(index).low_load_gains < 0 | entries(index).low_load_gains > 1) || ...
            any(entries(index).high_load_gains < 0 | entries(index).high_load_gains > 1) || ...
            any(entries(index).phase_rad < -pi | entries(index).phase_rad > pi)
        error("S12:EngineSoundV12:SourceProfile", "source.order_surface entry is invalid.");
    end
end
end

function validateTopology(source)
if ~ismember(source.engine_kind, ["piston", "rotary"]) || ...
        ~ismember(source.layout, ["inline", "V", "rotary"])
    error("S12:EngineSoundV12:SourceProfile", "engine_kind/layout are unsupported.");
end
if source.engine_kind == "piston"
    count = source.cylinders;
    invalidBankMap = any(~ismember(source.bank_map, [-1, 0, 1]));
    if source.layout == "V"
        invalidBankMap = invalidBankMap || ~any(source.bank_map == -1) || ...
            ~any(source.bank_map == 1);
    else
        invalidBankMap = invalidBankMap || ~all(source.bank_map == 0);
    end
    if count < 1 || ~ismember(source.layout, ["inline", "V"]) || ...
            source.rotor_count ~= 0 || source.chambers_per_rotor ~= 0 || ...
            numel(source.firing_order) ~= count || numel(source.firing_phases_deg) ~= count || ...
            numel(source.bank_map) ~= count || any(source.firing_order ~= floor(source.firing_order)) || ...
            ~isequal(sort(source.firing_order), 1:count) || ...
            ~isequal(source.firing_order, sortIndexByPhase(source.firing_phases_deg)) || ...
            numel(unique(source.firing_phases_deg)) ~= count || ...
            any(source.firing_phases_deg < 0 | source.firing_phases_deg >= 720) || invalidBankMap
        error("S12:EngineSoundV12:SourceProfile", "Piston cylinder/bank event map is invalid.");
    end
else
    count = source.rotor_count;
    if source.cylinders ~= 0 || source.layout ~= "rotary" || count ~= 2 || ...
            source.chambers_per_rotor ~= 3 || source.shaft_turns_per_rotor_turn ~= 3 || ...
            numel(source.firing_order) ~= count || ...
            numel(source.firing_phases_deg) ~= count || numel(source.bank_map) ~= count || ...
            ~isequal(sort(source.firing_order), 1:count) || ...
            ~isequal(source.firing_order, sortIndexByPhase(source.firing_phases_deg)) || ...
            numel(unique(source.firing_phases_deg)) ~= count || ...
            any(source.firing_phases_deg < 0 | source.firing_phases_deg >= 720) || ...
            ~isequal(sort(source.bank_map), [-1, 1])
        error("S12:EngineSoundV12:SourceProfile", "Rotary event map is invalid.");
    end
end
end

function result = hasExactFields(value, fields)
result = isequal(sort(string(fieldnames(value))).', sort(string(fields)));
end

function result = isTextScalar(value)
result = (ischar(value) && isrow(value)) || (isstring(value) && isscalar(value));
end

function result = isTextScalarOrEmpty(value)
result = isTextScalar(value) || (ischar(value) && isempty(value));
end

function indices = sortIndexByPhase(phases)
[~, indices] = sort(phases);
end
