function stateVector = s12_v11_model_vehicle_state_step(controls, profileIndex)
%S12_V11_MODEL_VEHICLE_STATE_STEP Convert continuous JSON-driven HMI state.
% Input is the twelve Dashboard values followed by the Simulink Clock.  Shift
% and DFCO are derived from profile-owned vehicle-state records, not literals.

profile = profileForIndex(profileIndex);
dashboard = s12_v11_model_dashboard_controls(profile);
if ~isnumeric(controls) || ~isequal(size(controls), [numel(dashboard) + 1, 1]) || ...
        any(~isfinite(controls), "all")
    error("S12:EngineSoundV11:ModelState", ...
        "Dashboard controls plus continuous timeline must be a finite [13,1] vector.");
end
values = double(controls(:));
timelineS = values(end);
controlValues = struct();
for index = 1:numel(dashboard)
    field = char(dashboard(index).field);
    controlValues.(field) = clampToRange(values(index), dashboard(index).range);
end
stateTuning = profile.vehicle_state;
rpm = max(profile.character.idle_rpm, min(profile.character.redline_rpm, controlValues.rpm));
loadValue = max(profile.character.minimum_load, min(profile.character.maximum_load, controlValues.load));
throttle = controlValues.throttle;
acceleration = controlValues.acceleration;
speedKph = max(0, stateTuning.speed_kph_per_rpm * rpm + ...
    stateTuning.speed_acceleration_gain * acceleration);
targetGear = determineGear(rpm, stateTuning);
[gear, shiftCode] = determineShiftCode(targetGear, rpm, timelineS, stateTuning, profile.vehicle_id);
dfco = double(throttle <= stateTuning.dfco_throttle_threshold && ...
    acceleration <= stateTuning.dfco_acceleration_threshold);
[dthrottleDt, drpmDt, thermalEligibility] = deriveDynamicState( ...
    rpm, loadValue, throttle, timelineS, stateTuning, profile.vehicle_id);
thermalState = double(thermalEligibility >= profile.afterfire.minimum_thermal_eligibility);
oxygenState = 1;
stateVector = [rpm; loadValue; throttle; acceleration; speedKph; gear; shiftCode; dfco; ...
    thermalState; oxygenState; controlValues.order_balance; controlValues.transient; ...
    controlValues.backfire_level; controlValues.ptr_pipe_length_m; ...
    controlValues.ptr_area_m2; controlValues.ptr_reflection; controlValues.ptr_damping; ...
    controlValues.gain; dthrottleDt; drpmDt; thermalEligibility];
if ~isequal(size(stateVector), [21, 1]) || any(~isfinite(stateVector), "all")
    error("S12:EngineSoundV11:ModelState", ...
        "Vehicle State must provide one finite [21,1] pre-PTR afterfire vector.");
end
end

function [dthrottleDt, drpmDt, thermalEligibility] = deriveDynamicState( ...
        rpm, loadValue, throttle, timelineS, tuning, vehicleId)
persistent lastVehicleId lastTimestampS lastThrottle lastRpm lastThermalEligibility
required = ["derivative_min_dt_s", "thermal_initial_eligibility", ...
    "thermal_heating_rate_per_s", "thermal_cooling_rate_per_s", ...
    "thermal_load_gain", "thermal_rpm_reference_rpm"];
for field = required
    if ~isfield(tuning, field)
        error("S12:EngineSoundV11:ModelState", ...
            "profile.vehicle_state.%s is required for dynamic afterfire state.", field);
    end
end
if tuning.derivative_min_dt_s <= 0 || tuning.thermal_initial_eligibility < 0 || ...
        tuning.thermal_initial_eligibility > 1 || tuning.thermal_heating_rate_per_s <= 0 || ...
        tuning.thermal_cooling_rate_per_s <= 0 || tuning.thermal_load_gain < 0 || ...
        tuning.thermal_load_gain > 1 || tuning.thermal_rpm_reference_rpm <= 0
    error("S12:EngineSoundV11:ModelState", "Dynamic afterfire tuning violates its bounded JSON contract.");
end
reset = isempty(lastVehicleId) || string(lastVehicleId) ~= string(vehicleId) || ...
    isempty(lastTimestampS) || timelineS <= 0 || timelineS < lastTimestampS;
if reset
    dthrottleDt = 0;
    drpmDt = 0;
    thermalEligibility = tuning.thermal_initial_eligibility;
else
    deltaS = max(timelineS - lastTimestampS, tuning.derivative_min_dt_s);
    dthrottleDt = (throttle - lastThrottle) / deltaS;
    drpmDt = (rpm - lastRpm) / deltaS;
    normalizedRpm = min(1, max(0, rpm / tuning.thermal_rpm_reference_rpm));
    thermalTarget = min(1, max(0, tuning.thermal_load_gain * loadValue + ...
        (1 - tuning.thermal_load_gain) * normalizedRpm));
    if thermalTarget >= lastThermalEligibility
        ratePerS = tuning.thermal_heating_rate_per_s;
    else
        ratePerS = tuning.thermal_cooling_rate_per_s;
    end
    thermalEligibility = min(1, max(0, lastThermalEligibility + ...
        ratePerS * deltaS * (thermalTarget - lastThermalEligibility)));
end
lastVehicleId = string(vehicleId);
lastTimestampS = timelineS;
lastThrottle = throttle;
lastRpm = rpm;
lastThermalEligibility = thermalEligibility;
end

function value = clampToRange(value, bounds)
if ~isnumeric(bounds) || ~isequal(size(bounds), [1, 2]) || bounds(1) > bounds(2)
    error("S12:EngineSoundV11:ModelState", "Dashboard tuning range is invalid.");
end
value = max(bounds(1), min(bounds(2), value));
end

function gear = determineGear(rpm, tuning)
gear = ceil(rpm / tuning.gear_rpm_step);
gear = max(tuning.minimum_gear, min(tuning.maximum_gear, gear));
end

function [gear, shiftCode] = determineShiftCode(targetGear, rpm, timelineS, tuning, vehicleId)
persistent lastGear lastShiftS lastTimestampS lastVehicleId
if isempty(lastVehicleId) || string(lastVehicleId) ~= string(vehicleId) || ...
        isempty(lastTimestampS) || timelineS < lastTimestampS || timelineS <= 0
    lastVehicleId = string(vehicleId);
    lastGear = targetGear;
    lastShiftS = timelineS;
    lastTimestampS = timelineS;
end
gear = lastGear;
shiftCode = 0;
eligible = timelineS >= lastShiftS + tuning.shift_hold_s;
if eligible && rpm >= tuning.upshift_rpm_threshold && targetGear > lastGear
    gear = targetGear;
    shiftCode = 1;
elseif eligible && rpm <= tuning.downshift_rpm_threshold && targetGear < lastGear
    gear = targetGear;
    shiftCode = 2;
end
lastGear = gear;
if shiftCode ~= 0
    lastShiftS = timelineS;
end
lastTimestampS = timelineS;
end

function profile = profileForIndex(profileIndex)
ids = s12_v11_canonical_vehicle_ids();
if ~isnumeric(profileIndex) || ~isscalar(profileIndex) || ~isfinite(profileIndex) || ...
        profileIndex ~= floor(profileIndex) || profileIndex < 1 || profileIndex > numel(ids)
    error("S12:EngineSoundV11:ModelState", "profileIndex is outside the canonical vehicle list.");
end
profile = s12_v11_load_profile(ids(profileIndex));
end
