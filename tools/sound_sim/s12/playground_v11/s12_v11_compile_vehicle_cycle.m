function cycle = s12_v11_compile_vehicle_cycle(profileInput)
%S12_V11_COMPILE_VEHICLE_CYCLE Compile the fixed synthetic 90-second cycle.

profile = resolveProfile(profileInput);
sampleRateHz = profile.renderer.sample_rate_hz;
frameSamples = profile.renderer.frame_samples;
durationS = 90;
frameCount = durationS * sampleRateHz / frameSamples;
sampleCount = frameCount * frameSamples;
if frameCount ~= floor(frameCount) || sampleCount ~= 4320000 || ...
        frameSamples * frameCount / sampleRateHz ~= durationS
    error("S12:EngineSoundV11:FrameContract", "The v1.1 cycle contract is internally inconsistent.");
end
timestampS = (0:frameCount - 1).' * frameSamples / sampleRateHz;
framePeriodS = frameSamples / sampleRateHz;
% Fixed acceptance sequence.  Do not split the 32--48 WOT or 48--54 hold
% windows for synthetic gear effects: those effects belong to the source
% state, while this contract remains stable across all eight profiles.
boundaries = [0, 2, 12, 22, 32, 48, 54, 66, 72, 82, 88, 90];
idle = profile.character.idle_rpm;
redline = profile.character.redline_rpm;
rpm = interpolateSegments(timestampS, boundaries, [idle, idle, 0.38 * redline, ...
    0.42 * redline, redline, redline, redline, 0.42 * redline, ...
    0.58 * redline, 0.78 * redline, 0.40 * redline, idle]);
loadValue = interpolateSegments(timestampS, boundaries, [0.04, 0.08, 0.12, 0.38, ...
    0.98, 0.98, 0.98, 0.10, 0.46, 0.84, 0.08, 0.04, 0.04]);
throttle = interpolateSegments(timestampS, boundaries, [0.00, 0.08, 0.12, 0.42, ...
    1.00, 1.00, 1.00, 0.02, 0.50, 0.88, 0.01, 0.00, 0.00]);
speedKph = interpolateSegments(timestampS, boundaries, [0, 0, 0, 42, 130, 130, ...
    130, 78, 82, 132, 64, 25, 0]);
% Keep the accepted 11-window contract fixed.  The following bounded source
% transitions create state edges inside the existing shift windows so the
% JSON-owned afterfire eligibility gates can observe a real gear event.
[rpm, throttle, speedKph] = applyProfileDrivenShiftTransients( ...
    timestampS, rpm, throttle, speedKph, profile);
acceleration = gradient(speedKph / 3.6, frameSamples / sampleRateHz);
dthrottleDt = deriveRate(throttle, framePeriodS, profile.vehicle_state.derivative_min_dt_s);
drpmDt = deriveRate(rpm, framePeriodS, profile.vehicle_state.derivative_min_dt_s);
gear = ones(frameCount, 1);
gear(timestampS >= 12) = 2;
gear(timestampS >= 22) = 3;
gear(timestampS >= 32) = 4;
gear(timestampS >= 48) = 5;
gear(timestampS >= 66 & timestampS < 72) = 4;
gear(timestampS >= 72) = 5;
shiftType = repmat("none", frameCount, 1);
shiftType(timestampS >= 48 & timestampS < 54) = "upshift";
shiftType(timestampS >= 66 & timestampS < 72) = "downshift";
dfco = (timestampS >= 54 & timestampS < 66) | (timestampS >= 82 & timestampS < 88);
thermalEligibility = deriveThermalEligibility(rpm, loadValue, framePeriodS, ...
    profile.vehicle_state);
thermalState = repmat("cold", frameCount, 1);
thermalState(thermalEligibility >= profile.afterfire.minimum_thermal_eligibility) = "warm";
oxygenState = repmat("normal", frameCount, 1);
state = table(rpm, loadValue, throttle, acceleration, speedKph, gear, ...
    shiftType, dfco, thermalState, oxygenState, dthrottleDt, drpmDt, thermalEligibility, VariableNames=[ ...
    "rpm", "load", "throttle", "acceleration", "speed_kph", ...
    "gear", "shift_type", "dfco", "thermal_state", "oxygen_state", ...
    "dthrottle_dt", "drpm_dt", "thermal_eligibility"]);
segments = makeSegments(boundaries);
cycle = struct( ...
    "schema_version", "s12-engine-sound-v11-cycle-1", ...
    "profile_id", profile.vehicle_id, ...
    "synthetic", true, ...
    "duration_s", durationS, ...
    "sample_rate_hz", sampleRateHz, ...
    "frame_samples", frameSamples, ...
    "frame_count", frameCount, ...
    "sample_count", 4320000, ...
    "timestamp_s", timestampS, ...
    "state", state, ...
    "segments", {segments});
end

function [rpm, throttle, speedKph] = applyProfileDrivenShiftTransients( ...
        timestampS, rpm, throttle, speedKph, profile)
% The window bounds are acceptance-contract constants.  Only duration and
% targets below are JSON-owned vehicle parameters; no audio is post-processed.
upshiftWindowS = [48, 54];
downshiftWindowS = [66, 72];
vehicleState = requireShiftVehicleState(profile);
afterfire = requireShiftAfterfire(profile);
halfDurationS = boundedShiftHalfDuration(vehicleState.shift_hold_s, ...
    upshiftWindowS, downshiftWindowS);

upshiftPulse = triangularShiftPulse(timestampS, upshiftWindowS, halfDurationS);
upshiftThrottleTarget = min(afterfire.upshift_max_throttle, ...
    afterfire.overrun_max_throttle);
throttle = blendTransientTarget(throttle, upshiftPulse, upshiftThrottleTarget);

downshiftPulse = triangularShiftPulse(timestampS, downshiftWindowS, halfDurationS);
downshiftThrottleTarget = max([afterfire.downshift_min_throttle, ...
    afterfire.minimum_shift_load, requireMaximumLoad(profile)]);
downshiftRpmTarget = min(profile.character.redline_rpm, ...
    rpm + vehicleState.gear_rpm_step);
downshiftSpeedTarget = max(0, speedKph - ...
    vehicleState.speed_kph_per_rpm * vehicleState.gear_rpm_step);
rpm = blendTransientTarget(rpm, downshiftPulse, downshiftRpmTarget);
throttle = blendTransientTarget(throttle, downshiftPulse, downshiftThrottleTarget);
speedKph = blendTransientTarget(speedKph, downshiftPulse, downshiftSpeedTarget);
end

function vehicleState = requireShiftVehicleState(profile)
required = ["shift_hold_s", "gear_rpm_step", "speed_kph_per_rpm"];
if ~isstruct(profile) || ~isfield(profile, "vehicle_state") || ...
        ~isstruct(profile.vehicle_state)
    error("S12:EngineSoundV11:VehicleState", ...
        "profile.vehicle_state must define the shift transient contract.");
end
vehicleState = profile.vehicle_state;
for field = required
    if ~isfield(vehicleState, field) || ~isnumeric(vehicleState.(field)) || ...
            ~isscalar(vehicleState.(field)) || ~isfinite(vehicleState.(field)) || ...
            vehicleState.(field) <= 0
        error("S12:EngineSoundV11:VehicleState", ...
            "profile.vehicle_state.%s must be one positive finite numeric value.", field);
    end
end
end

function afterfire = requireShiftAfterfire(profile)
required = ["upshift_max_throttle", "overrun_max_throttle", ...
    "minimum_event_rpm", "downshift_min_throttle", "minimum_shift_load"];
if ~isstruct(profile) || ~isfield(profile, "afterfire") || ~isstruct(profile.afterfire)
    error("S12:EngineSoundV11:Afterfire", ...
        "profile.afterfire must define the shift transient eligibility contract.");
end
afterfire = profile.afterfire;
for field = required
    if ~isfield(afterfire, field) || ~isnumeric(afterfire.(field)) || ...
            ~isscalar(afterfire.(field)) || ~isfinite(afterfire.(field))
        error("S12:EngineSoundV11:Afterfire", ...
            "profile.afterfire.%s must be one finite numeric value.", field);
    end
end
if afterfire.upshift_max_throttle < 0 || afterfire.upshift_max_throttle > 1 || ...
        afterfire.overrun_max_throttle < 0 || afterfire.overrun_max_throttle > 1 || ...
        afterfire.downshift_min_throttle < 0 || afterfire.downshift_min_throttle > 1 || ...
        afterfire.minimum_shift_load < 0 || afterfire.minimum_shift_load > 1 || ...
        afterfire.minimum_event_rpm <= 0
    error("S12:EngineSoundV11:Afterfire", ...
        "profile afterfire shift transient tuning is outside its bounded contract.");
end
end

function maximumLoad = requireMaximumLoad(profile)
if ~isstruct(profile) || ~isfield(profile, "character") || ...
        ~isstruct(profile.character) || ~isfield(profile.character, "maximum_load") || ...
        ~isnumeric(profile.character.maximum_load) || ...
        ~isscalar(profile.character.maximum_load) || ...
        ~isfinite(profile.character.maximum_load) || ...
        profile.character.maximum_load < 0 || profile.character.maximum_load > 1
    error("S12:EngineSoundV11:VehicleState", ...
        "profile.character.maximum_load must be one finite value in [0,1].");
end
maximumLoad = double(profile.character.maximum_load);
end

function halfDurationS = boundedShiftHalfDuration(shiftHoldS, upshiftWindowS, downshiftWindowS)
% A triangle has two legs.  Reserving one further leg preserves an interior
% source event and cannot alter either accepted window boundary.
windowDurationS = min(upshiftWindowS(2) - upshiftWindowS(1), ...
    downshiftWindowS(2) - downshiftWindowS(1));
halfDurationS = min(double(shiftHoldS), windowDurationS / 3);
if ~isfinite(halfDurationS) || halfDurationS <= 0
    error("S12:EngineSoundV11:VehicleState", "profile.vehicle_state.shift_hold_s is invalid.");
end
end

function pulse = triangularShiftPulse(timestampS, windowS, halfDurationS)
pulse = zeros(size(timestampS));
startS = windowS(1) + halfDurationS;
peakS = startS + halfDurationS;
endS = peakS + halfDurationS;
rising = timestampS >= startS & timestampS < peakS;
falling = timestampS >= peakS & timestampS < endS;
pulse(rising) = (timestampS(rising) - startS) / halfDurationS;
pulse(falling) = 1 - (timestampS(falling) - peakS) / halfDurationS;
end

function values = blendTransientTarget(values, pulse, target)
if isscalar(target)
    target = repmat(target, size(values));
end
if ~isnumeric(target) || ~isequal(size(target), size(values)) || any(~isfinite(target))
    error("S12:EngineSoundV11:VehicleState", ...
        "A shift transient target must match the finite vehicle-state vector.");
end
inside = pulse > 0;
values(inside) = values(inside) + pulse(inside) .* (target(inside) - values(inside));
end

function rate = deriveRate(values, framePeriodS, minimumDtS)
if ~isnumeric(minimumDtS) || ~isscalar(minimumDtS) || ~isfinite(minimumDtS) || minimumDtS <= 0
    error("S12:EngineSoundV11:VehicleState", "profile.vehicle_state.derivative_min_dt_s must be positive.");
end
denominatorS = max(framePeriodS, double(minimumDtS));
rate = [0; diff(values)] / denominatorS;
end

function eligibility = deriveThermalEligibility(rpm, loadValue, framePeriodS, tuning)
required = ["thermal_initial_eligibility", "thermal_heating_rate_per_s", ...
    "thermal_cooling_rate_per_s", "thermal_load_gain", "thermal_rpm_reference_rpm"];
for field = required
    if ~isfield(tuning, field)
        error("S12:EngineSoundV11:VehicleState", ...
            "profile.vehicle_state.%s is required for the synthetic thermal state.", field);
    end
end
if tuning.thermal_initial_eligibility < 0 || tuning.thermal_initial_eligibility > 1 || ...
        tuning.thermal_heating_rate_per_s <= 0 || tuning.thermal_cooling_rate_per_s <= 0 || ...
        tuning.thermal_load_gain < 0 || tuning.thermal_load_gain > 1 || ...
        tuning.thermal_rpm_reference_rpm <= 0
    error("S12:EngineSoundV11:VehicleState", "Synthetic thermal tuning is outside its bounded contract.");
end
eligibility = zeros(size(rpm));
eligibility(1) = tuning.thermal_initial_eligibility;
for index = 2:numel(eligibility)
    normalizedRpm = min(1, max(0, rpm(index) / tuning.thermal_rpm_reference_rpm));
    normalizedLoad = min(1, max(0, loadValue(index)));
    thermalTarget = min(1, max(0, tuning.thermal_load_gain * normalizedLoad + ...
        (1 - tuning.thermal_load_gain) * normalizedRpm));
    previous = eligibility(index - 1);
    if thermalTarget >= previous
        ratePerS = tuning.thermal_heating_rate_per_s;
    else
        ratePerS = tuning.thermal_cooling_rate_per_s;
    end
    eligibility(index) = min(1, max(0, previous + ...
        ratePerS * framePeriodS * (thermalTarget - previous)));
end
end

function profile = resolveProfile(value)
if isstruct(value) && isscalar(value) && isfield(value, "vehicle_id") && isfield(value, "character")
    profile = value;
else
    profile = s12_v11_load_profile(value);
end
end

function values = interpolateSegments(timestampS, boundaries, nodes)
values = zeros(size(timestampS));
for index = 1:numel(boundaries) - 1
    inside = timestampS >= boundaries(index) & timestampS < boundaries(index + 1);
    fraction = (timestampS(inside) - boundaries(index)) / ...
        (boundaries(index + 1) - boundaries(index));
    smooth = fraction .^ 2 .* (3 - 2 * fraction);
    values(inside) = nodes(index) + (nodes(index + 1) - nodes(index)) .* smooth;
end
end

function segments = makeSegments(boundaries)
names = ["startup", "idle", "launch", "cruise", "wot_to_redline", ...
    "high_load_hold", "lift", "downshift_blip", "second_acceleration", ...
    "rapid_lift", "return_idle"];
template = struct("id", "", "start_s", 0, "end_s", 0);
segments = repmat(template, 1, numel(names));
for index = 1:numel(names)
    segments(index) = struct("id", names(index), ...
        "start_s", boundaries(index), "end_s", boundaries(index + 1));
end
end
