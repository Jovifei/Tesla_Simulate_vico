function [events, diagnostics, schedulerState] = s12_v11_schedule_afterfire( ...
        state, profile, afterfireLevel, scenarioKey, schedulerState)
%S12_V11_SCHEDULE_AFTERFIRE Schedule synthetic pre-PTR afterfire statefully.
% Pass the third returned schedulerState to the next chronological frame. The
% second output remains diagnostics for compatibility with the v1.1 contract.

if nargin < 5
    schedulerState = [];
end
requiredStateFields = ["rpm", "load", "throttle", "acceleration", "gear", ...
    "shift_type", "dfco", "thermal_state", "oxygen_state", "dthrottle_dt", ...
    "drpm_dt", "thermal_eligibility", "timestamp_s"];
validateState(state, requiredStateFields);
level = validateTextChoice(afterfireLevel, ["off", "subtle", "aggressive"], ...
    "S12:EngineSoundV11:AfterfireLevel", "afterfireLevel");
scenarioKey = validateTextScalar(scenarioKey, ...
    "S12:EngineSoundV11:ScenarioKey", "scenarioKey");
config = resolveConfig(profile);
schedulerState = validateOrInitializeScheduler(schedulerState, scenarioKey, profile);
if double(state.timestamp_s) < schedulerState.last_timestamp_s
    error("S12:EngineSoundV11:SchedulerTime", ...
        "state.timestamp_s must be monotonic across a stateful afterfire schedule.");
end

eventTemplate = emptyEventTemplate();
events = repmat(eventTemplate, 0, 1);
[eligible, kind, explanation, checks] = evaluateEligibility(state, level, config);
transitioned = eligible && (~schedulerState.previous_eligible || ...
    schedulerState.previous_kind ~= kind);
schedulerState = updateLiftState(schedulerState, state, eligible, kind);
[liftDurationS, liftEnergyScale, thermalEnergyScale] = dynamicEligibilityScales( ...
    schedulerState, state, config, kind);
refractoryElapsed = double(state.timestamp_s) >= ...
    schedulerState.next_cluster_not_before_s;
if kind == "overrun_crackle"
    shouldStartCluster = eligible && (transitioned || refractoryElapsed);
else
    % Shift bark/pop is edge-triggered: a sustained shift state is one event.
    shouldStartCluster = eligible && transitioned;
end
if shouldStartCluster
    schedulerState.cluster_sequence = schedulerState.cluster_sequence + 1;
    [events, clusterId] = makeCluster(state, profile, level, scenarioKey, config, ...
        kind, explanation, schedulerState.cluster_sequence, ...
        liftEnergyScale * thermalEnergyScale, liftDurationS);
    schedulerState.last_cluster_start_s = events(1).time_s;
    schedulerState.next_cluster_not_before_s = events(1).time_s + ...
        liftAdjustedRefractory(config, scenarioKey, profile, schedulerState.cluster_sequence, ...
        liftDurationS, state.thermal_eligibility, kind);
else
    clusterId = "";
end

schedulerState.last_timestamp_s = double(state.timestamp_s);
schedulerState.previous_eligible = eligible;
schedulerState.previous_kind = kind;
diagnostics = baseDiagnostics(state, level, scenarioKey, checks, eligible, kind, explanation);
diagnostics.event_count = numel(events);
diagnostics.total_energy = sum([events.energy]);
diagnostics.cluster_id = clusterId;
diagnostics.event_times_s = [events.time_s];
diagnostics.cluster_started = shouldStartCluster;
diagnostics.transitioned_into_window = transitioned;
diagnostics.refractory_elapsed = refractoryElapsed;
diagnostics.minimum_cluster_refractory_s = config.cluster_refractory_s;
diagnostics.next_cluster_not_before_s = schedulerState.next_cluster_not_before_s;
diagnostics.lift_duration_s = liftDurationS;
diagnostics.lift_energy_scale = liftEnergyScale;
diagnostics.thermal_energy_scale = thermalEnergyScale;
diagnostics.scheduler_state = schedulerState;
end

function schedulerState = validateOrInitializeScheduler(value, scenarioKey, profile)
vehicleId = profileIdentity(profile);
template = struct( ...
    "schema_version", "s12-v11-afterfire-scheduler-1", ...
    "scenario_key", scenarioKey, ...
    "vehicle_id", vehicleId, ...
    "last_timestamp_s", -inf, ...
    "last_cluster_start_s", -inf, ...
    "next_cluster_not_before_s", -inf, ...
    "lift_start_s", -inf, ...
    "cluster_sequence", 0, ...
    "previous_eligible", false, ...
    "previous_kind", "");
if isempty(value)
    schedulerState = template;
    return;
end
if ~isstruct(value) || ~isscalar(value) || ...
        ~all(isfield(value, fieldnames(template)))
    error("S12:EngineSoundV11:SchedulerState", ...
        "schedulerState must satisfy the v1.1 afterfire scheduler contract.");
end
if string(value.scenario_key) ~= scenarioKey || string(value.vehicle_id) ~= vehicleId
    error("S12:EngineSoundV11:SchedulerState", ...
        "schedulerState belongs to a different scenario or vehicle profile.");
end
numericFields = ["last_timestamp_s", "last_cluster_start_s", ...
    "next_cluster_not_before_s", "lift_start_s", "cluster_sequence"];
for field = numericFields
    fieldValue = value.(field);
    allowsInitialNegativeInfinity = isnumeric(fieldValue) && isscalar(fieldValue) && ...
        field ~= "cluster_sequence" && isinf(fieldValue) && fieldValue < 0;
    if ~isnumeric(fieldValue) || ~isscalar(fieldValue) || ...
            ~(isfinite(fieldValue) || allowsInitialNegativeInfinity)
        error("S12:EngineSoundV11:SchedulerState", ...
            "schedulerState.%s is invalid.", field);
    end
end
if value.cluster_sequence < 0 || value.cluster_sequence ~= floor(value.cluster_sequence) || ...
        ~isscalar(value.previous_eligible) || ...
        ~(islogical(value.previous_eligible) || isnumeric(value.previous_eligible)) || ...
        ~((ischar(value.previous_kind) && isrow(value.previous_kind)) || ...
        (isstring(value.previous_kind) && isscalar(value.previous_kind)))
    error("S12:EngineSoundV11:SchedulerState", "schedulerState has invalid state values.");
end
schedulerState = value;
end

function [events, clusterId] = makeCluster(state, profile, level, scenarioKey, config, ...
        kind, explanation, clusterSequence, dynamicEnergyScale, liftDurationS)
[eventCount, levelScale] = levelParameters(level, kind);
kindScale = kindEnergyScale(kind);
vehicleId = profileIdentity(profile);
clusterSeed = deterministicSeed(scenarioKey + "|" + vehicleId + "|" + kind + "|" + clusterSequence);
clusterId = kind + "-" + string(clusterSequence) + "-" + string(clusterSeed);
eventTemplate = emptyEventTemplate();
events = repmat(eventTemplate, eventCount, 1);
eventTimeS = double(state.timestamp_s) + config.onset_delay_s;
for index = 1:eventCount
    variation = deterministicVariation(clusterId, index);
    if index > 1
        intervalVariation = max(-1, min(1, variation + 0.08 * mod(index, 3) - 0.04));
        eventTimeS = eventTimeS + config.cluster_interval_s * ...
            (1 + config.interval_jitter_fraction * intervalVariation);
    end
    energy = config.base_energy * levelScale * kindScale * dynamicEnergyScale * ...
        config.cluster_energy_decay ^ (index - 1) * (1 + 0.04 * variation);
    events(index) = eventTemplate;
    events(index).time_s = eventTimeS;
    events(index).kind = kind;
    events(index).energy = energy;
    events(index).cluster_id = clusterId;
    events(index).variation = variation;
    events(index).eligibility_explanation = explanation;
    events(index).dynamic_energy_scale = dynamicEnergyScale;
    events(index).lift_duration_s = liftDurationS;
end
end

function durationS = refractoryDuration(config, scenarioKey, profile, sequence)
% The configured value is a strict lower bound; deterministic variation may
% only extend it, never shorten it below the profile's explicit refractory.
key = scenarioKey + "|" + profileIdentity(profile) + "|refractory|" + sequence;
variation01 = 0.5 * (deterministicVariation(key, 1) + 1);
durationS = config.cluster_refractory_s * ...
    (1 + config.refractory_jitter_fraction * variation01);
end

function durationS = liftAdjustedRefractory(config, scenarioKey, profile, sequence, ...
        liftDurationS, thermalEligibility, kind)
durationS = refractoryDuration(config, scenarioKey, profile, sequence);
if kind ~= "overrun_crackle"
    return;
end
thermalFloor = max(thermalEligibility, config.minimum_thermal_eligibility);
durationS = durationS * (1 + config.lift_refractory_growth_per_s * liftDurationS) / thermalFloor;
end

function schedulerState = updateLiftState(schedulerState, state, eligible, kind)
if eligible && kind == "overrun_crackle"
    if ~schedulerState.previous_eligible || schedulerState.previous_kind ~= "overrun_crackle"
        schedulerState.lift_start_s = double(state.timestamp_s);
    end
else
    schedulerState.lift_start_s = -inf;
end
end

function [liftDurationS, liftEnergyScale, thermalEnergyScale] = dynamicEligibilityScales( ...
        schedulerState, state, config, kind)
liftDurationS = 0;
liftEnergyScale = 1;
if kind == "overrun_crackle" && isfinite(schedulerState.lift_start_s)
    liftDurationS = max(0, double(state.timestamp_s) - schedulerState.lift_start_s);
    liftEnergyScale = exp(-config.lift_energy_decay_rate_per_s * liftDurationS);
end
thermalEnergyScale = min(1, max(0, double(state.thermal_eligibility)));
end

function template = emptyEventTemplate()
template = struct("time_s", 0, "kind", "", ...
    "location", "pre_ptr_exhaust_source", "energy", 0, ...
    "cluster_id", "", "variation", 0, ...
    "eligibility_explanation", "", "dynamic_energy_scale", 1, ...
    "lift_duration_s", 0);
end

function validateState(state, requiredFields)
if ~isstruct(state) || ~isscalar(state)
    error("S12:EngineSoundV11:State", "state must be a scalar struct.");
end
for field = requiredFields
    if ~isfield(state, field)
        error("S12:EngineSoundV11:State", "state is missing %s.", field);
    end
end
numericFields = ["rpm", "load", "throttle", "acceleration", "gear", ...
    "dthrottle_dt", "drpm_dt", "thermal_eligibility", "timestamp_s"];
for field = numericFields
    value = state.(field);
    if ~isnumeric(value) || ~isscalar(value) || ~isfinite(value)
        error("S12:EngineSoundV11:State", "state.%s must be one finite numeric value.", field);
    end
end
if state.thermal_eligibility < 0 || state.thermal_eligibility > 1
    error("S12:EngineSoundV11:State", "state.thermal_eligibility must remain in [0,1].");
end
validateTextScalar(state.shift_type, "S12:EngineSoundV11:State", "state.shift_type");
validateTextScalar(state.thermal_state, "S12:EngineSoundV11:State", "state.thermal_state");
validateTextScalar(state.oxygen_state, "S12:EngineSoundV11:State", "state.oxygen_state");
if ~isscalar(state.dfco) || ...
        ~(islogical(state.dfco) || (isnumeric(state.dfco) && isfinite(state.dfco) && ismember(state.dfco, [0, 1])))
    error("S12:EngineSoundV11:State", "state.dfco must be one logical value.");
end
end

function [eligible, kind, explanation, checks] = evaluateEligibility(state, level, config)
thermalValid = ismember(lower(string(state.thermal_state)), ["warm", "hot", "nominal"]);
oxygenValid = ismember(lower(string(state.oxygen_state)), ["normal", "available", "rich"]);
aboveIdle = state.rpm > config.idle_rpm_ceiling && state.gear > 0;
steadyCruise = lower(string(state.shift_type)) == "none" && ~logical(state.dfco) && ...
    abs(state.acceleration) <= config.steady_acceleration_limit && ...
    state.throttle >= config.cruise_min_throttle && state.throttle <= config.cruise_max_throttle;
checks = struct("level_enabled", level ~= "off", "above_idle", aboveIdle, ...
    "steady_cruise", steadyCruise, "thermal_valid", thermalValid, ...
    "thermal_eligibility", state.thermal_eligibility, ...
    "thermal_eligibility_valid", state.thermal_eligibility >= config.minimum_thermal_eligibility, ...
    "oxygen_valid", oxygenValid, ...
    "upshift_throttle_edge", state.dthrottle_dt <= config.upshift_max_throttle_rate_per_s, ...
    "upshift_rpm_edge", state.drpm_dt <= config.overrun_max_rpm_rate_per_s, ...
    "eligibility_window_open", false);
eligible = false;
kind = "";
if level == "off"
    explanation = "afterfire level is off";
    return;
elseif ~aboveIdle
    explanation = "idle or neutral state is outside the afterfire window";
    return;
elseif steadyCruise
    explanation = "steady cruise is outside the afterfire window";
    return;
elseif ~thermalValid
    explanation = "thermal state is invalid for synthetic afterfire";
    return;
elseif state.thermal_eligibility < config.minimum_thermal_eligibility
    explanation = "continuous synthetic thermal eligibility is below the profile threshold";
    return;
elseif ~oxygenValid
    explanation = "oxygen state is outside the synthetic eligibility window";
    return;
end

shiftType = lower(string(state.shift_type));
% The existing JSON-owned negative RPM threshold is valid for a torque-cut
% engine-speed edge as well as DFCO.  No unproven per-vehicle threshold is
% introduced: an upshift may qualify through either provenance-owned edge.
upshiftDerivativeEdge = state.dthrottle_dt <= config.upshift_max_throttle_rate_per_s || ...
    state.drpm_dt <= config.overrun_max_rpm_rate_per_s;
if shiftType == "upshift" && state.rpm >= config.minimum_event_rpm && ...
        state.throttle <= config.upshift_max_throttle && state.load >= config.minimum_shift_load && ...
        upshiftDerivativeEdge
    kind = "upshift_bark";
    explanation = "upshift throttle-cut window is open";
elseif shiftType == "downshift" && state.rpm >= config.minimum_event_rpm && ...
        state.throttle >= config.downshift_min_throttle && state.acceleration <= 0 && ...
        state.dthrottle_dt >= config.downshift_min_throttle_rate_per_s && ...
        state.drpm_dt >= config.downshift_min_rpm_rate_per_s
    kind = "downshift_blip_pop";
    explanation = "downshift blip window is open";
elseif shiftType == "none" && logical(state.dfco) && ...
        state.rpm >= config.minimum_event_rpm && ...
        state.throttle <= config.overrun_max_throttle && ...
        state.acceleration <= config.overrun_max_acceleration && ...
        state.dthrottle_dt <= config.overrun_max_throttle_rate_per_s && ...
        state.drpm_dt <= config.overrun_max_rpm_rate_per_s
    kind = "overrun_crackle";
    explanation = "DFCO overrun window is open";
else
    explanation = "state did not match an afterfire eligibility window";
    return;
end
eligible = true;
checks.eligibility_window_open = true;
end

function config = resolveConfig(profile)
if ~isstruct(profile) || ~isscalar(profile)
    error("S12:EngineSoundV11:Profile", "profile must be a scalar struct.");
end
profileAfterfire = requireProfileAfterfireFields(profile);
config = struct();
for field = requiredAfterfireFields()
    config.(field) = afterfireValue(profileAfterfire.(field), field);
end
validateAfterfireConfig(config);
end

function validateAfterfireConfig(config)
% With +/-4%% per-event variation, the worst adjacent ratio is
% decay*(1.04/0.96). Requiring decay < 0.90 is conservative versus 12/13.
if config.idle_rpm_ceiling < 0 || ...
        config.minimum_event_rpm <= config.idle_rpm_ceiling || ...
        config.upshift_max_throttle < 0 || config.upshift_max_throttle > 1 || ...
        config.downshift_min_throttle < 0 || config.downshift_min_throttle > 1 || ...
        config.overrun_max_throttle < 0 || config.overrun_max_throttle > 1 || ...
        config.overrun_max_acceleration >= 0 || ...
        config.minimum_shift_load < 0 || config.minimum_shift_load > 1 || ...
        config.steady_acceleration_limit < 0 || ...
        config.cruise_min_throttle < 0 || config.cruise_max_throttle > 1 || ...
        config.cruise_min_throttle > config.cruise_max_throttle || ...
        config.base_energy <= 0 || config.onset_delay_s < 0 || ...
        config.cluster_interval_s <= 0 || ...
        config.interval_jitter_fraction <= 0 || config.interval_jitter_fraction > 0.45 || ...
        config.cluster_energy_decay <= 0 || config.cluster_energy_decay >= 0.90 || ...
        config.cluster_refractory_s < config.cluster_interval_s || ...
        config.refractory_jitter_fraction <= 0 || config.refractory_jitter_fraction > 0.45 || ...
        config.upshift_max_throttle_rate_per_s > 0 || ...
        config.downshift_min_throttle_rate_per_s < 0 || ...
        config.downshift_min_rpm_rate_per_s < 0 || ...
        config.overrun_max_throttle_rate_per_s > 0 || ...
        config.overrun_max_rpm_rate_per_s > 0 || ...
        config.minimum_thermal_eligibility <= 0 || config.minimum_thermal_eligibility > 1 || ...
        config.lift_energy_decay_rate_per_s <= 0 || ...
        config.lift_refractory_growth_per_s < 0
    error("S12:EngineSoundV11:Profile", "profile afterfire parameters violate bounded synthesis limits.");
end
end

function afterfire = requireProfileAfterfireFields(profile)
if ~isfield(profile, "afterfire") || ~isstruct(profile.afterfire) || ...
        ~isscalar(profile.afterfire)
    error("S12:EngineSoundV11:Profile", ...
        "profile.afterfire must declare stateful scheduling parameters.");
end
afterfire = profile.afterfire;
for field = requiredAfterfireFields()
    if ~isfield(afterfire, field)
        error("S12:EngineSoundV11:Profile", ...
            "profile.afterfire.%s is required for stateful afterfire scheduling.", field);
    end
    afterfireValue(afterfire.(field), field);
end

end

function fields = requiredAfterfireFields()
fields = ["idle_rpm_ceiling", "minimum_event_rpm", "upshift_max_throttle", ...
    "downshift_min_throttle", "overrun_max_throttle", ...
    "overrun_max_acceleration", "minimum_shift_load", ...
    "steady_acceleration_limit", "cruise_min_throttle", ...
    "cruise_max_throttle", "base_energy", "onset_delay_s", ...
    "cluster_interval_s", "cluster_refractory_s", ...
    "refractory_jitter_fraction", "interval_jitter_fraction", ...
    "cluster_energy_decay", "upshift_max_throttle_rate_per_s", ...
    "downshift_min_throttle_rate_per_s", "downshift_min_rpm_rate_per_s", ...
    "overrun_max_throttle_rate_per_s", "overrun_max_rpm_rate_per_s", ...
    "minimum_thermal_eligibility", "lift_energy_decay_rate_per_s", ...
    "lift_refractory_growth_per_s"];
end

function value = afterfireValue(record, field)
if isstruct(record) && isscalar(record) && isfield(record, "value")
    record = record.value;
end
if ~isnumeric(record) || ~isscalar(record) || ~isfinite(record)
    error("S12:EngineSoundV11:Profile", ...
        "profile.afterfire.%s must be one finite numeric value.", field);
end
value = double(record);
end

function [count, scale] = levelParameters(level, kind)
if level == "subtle"
    scale = 0.68;
    if kind == "overrun_crackle"
        count = 3;
    else
        count = 2;
    end
else
    scale = 1.18;
    if kind == "overrun_crackle"
        count = 6;
    else
        count = 4;
    end
end
end

function scale = kindEnergyScale(kind)
if kind == "upshift_bark"
    scale = 1.00;
elseif kind == "downshift_blip_pop"
    scale = 0.78;
else
    scale = 0.58;
end
end

function value = deterministicVariation(key, index)
seed = deterministicSeed(string(key) + "|" + string(index));
next = mod(1664525 * double(seed) + 1013904223, 2 ^ 32);
value = 2 * (next / (2 ^ 32 - 1)) - 1;
end

function seed = deterministicSeed(key)
codes = double(char(string(key)));
accumulator = 216613;
for index = 1:numel(codes)
    accumulator = mod(accumulator * 131 + codes(index), 2147483647);
end
seed = accumulator;
end

function identity = profileIdentity(profile)
if isfield(profile, "vehicle_id")
    identity = validateTextScalar(profile.vehicle_id, ...
        "S12:EngineSoundV11:Profile", "profile.vehicle_id");
else
    identity = "anonymous_synthetic_profile";
end
end

function value = validateTextChoice(value, choices, identifier, name)
value = lower(validateTextScalar(value, identifier, name));
if ~ismember(value, choices)
    error(identifier, "%s must be one of: %s.", name, strjoin(choices, ", "));
end
end

function value = validateTextScalar(value, identifier, name)
if ~((ischar(value) && isrow(value)) || (isstring(value) && isscalar(value))) || ...
        strlength(string(value)) == 0
    error(identifier, "%s must be one nonempty text scalar.", name);
end
value = string(value);
end

function diagnostics = baseDiagnostics(state, level, scenarioKey, checks, eligible, kind, explanation)
diagnostics = struct( ...
    "state", state, ...
    "level", level, ...
    "scenario_key", scenarioKey, ...
    "checks", checks, ...
    "eligible", eligible, ...
    "selected_kind", kind, ...
    "eligibility_explanation", explanation, ...
    "event_count", 0, ...
    "total_energy", 0, ...
    "cluster_id", "", ...
    "event_times_s", zeros(1, 0), ...
    "cluster_started", false, ...
    "transitioned_into_window", false, ...
    "refractory_elapsed", false, ...
    "minimum_cluster_refractory_s", 0, ...
    "next_cluster_not_before_s", -inf, ...
    "lift_duration_s", 0, ...
    "lift_energy_scale", 1, ...
    "thermal_energy_scale", 1, ...
    "scheduler_state", struct(), ...
    "causality_chain", ["state", "eligibility", "events", ...
        "pre_ptr_pressure_excitation", "ptr_radiation"]);
end
