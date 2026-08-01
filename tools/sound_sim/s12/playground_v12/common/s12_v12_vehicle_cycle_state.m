function state = s12_v12_vehicle_cycle_state(time, profileId)
%S12_V12_VEHICLE_CYCLE_STATE Compile one frame of the fixed 90 s cycle.

arguments
    time (1, 1) double {mustBeFinite, mustBeNonnegative}
    profileId (1, 1) string
end
if time >= 90
    error("S12:EngineSoundV12:VehicleCycle", ...
        "Vehicle-cycle time must be in [0,90).");
end

scenario = loadScenario(profileId);
idle = scenario.idle_rpm;
redline = scenario.redline_rpm;
cruise = scenario.cruise_rpm;
shiftEvent = 0;
shiftProgress = 0;
afterfireCode = 0;
afterfireProgress = 0;

if time < 2
    rpm = idle;
    load = 0.08;
    throttle = 0.05 + 0.05 * smoothProgress(time, 0, 2);
    acceleration = 0;
elseif time < 12
    rpm = idle;
    load = 0.10;
    throttle = 0.10;
    acceleration = 0;
elseif time < 22
    progress = smoothProgress(time, 12, 22);
    rpm = blend(idle, cruise, progress);
    load = blend(0.20, 0.75, progress);
    throttle = blend(0.20, 0.85, progress);
    acceleration = 2.5;
elseif time < 32
    rpm = cruise;
    load = 0.35;
    throttle = 0.32;
    acceleration = 0;
elseif time < 48
    progress = smoothProgress(time, 32, 48);
    rpm = blend(cruise, redline, progress);
    load = blend(0.55, 1.00, progress);
    throttle = blend(0.60, 1.00, progress);
    acceleration = 4.0;
elseif time < 54
    rpm = redline;
    load = 0.95;
    throttle = 0.95;
    acceleration = 0;
elseif time < 66
    motionProgress = smoothProgress(time, 54, 66);
    eventProgress = smoothProgress(time, 54, 65);
    rpm = blend(redline, 1800, motionProgress);
    load = blend(0.30, 0.08, motionProgress);
    throttle = blend(0.10, 0.02, motionProgress);
    acceleration = -3.0;
    afterfireCode = 3;
    afterfireProgress = eventProgress;
elseif time < 72
    motionProgress = smoothProgress(time, 66, 72);
    eventProgress = smoothProgress(time, 66, 71);
    rpm = blend(1800, 3500, motionProgress);
    load = 0.28;
    throttle = blend(0.25, 0.55, motionProgress);
    acceleration = 1.0;
    shiftEvent = -1;
    shiftProgress = eventProgress;
    afterfireCode = 2;
    afterfireProgress = eventProgress;
elseif time < 82
    progress = smoothProgress(time, 72, 82);
    rpm = blend(3500, 0.85 * redline, progress);
    load = blend(0.55, 0.90, progress);
    throttle = blend(0.60, 0.95, progress);
    acceleration = 3.0;
elseif time < 88
    motionProgress = smoothProgress(time, 82, 88);
    eventProgress = smoothProgress(time, 82, 87);
    rpm = blend(0.85 * redline, 1800, motionProgress);
    load = blend(0.25, 0.08, motionProgress);
    throttle = blend(0.08, 0.02, motionProgress);
    acceleration = -4.0;
    afterfireCode = 3;
    afterfireProgress = eventProgress;
else
    progress = smoothProgress(time, 88, 90);
    rpm = blend(1800, idle, progress);
    load = blend(0.12, 0.10, progress);
    throttle = blend(0.12, 0.10, progress);
    acceleration = -1.0;
end
state = [rpm; load; throttle; acceleration; shiftEvent; shiftProgress; ...
    afterfireCode; afterfireProgress];
end

function scenario = loadScenario(profileId)
persistent cachedId cachedScenario
if isempty(cachedId) || cachedId ~= profileId
    path = fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
        "vehicles", profileId, "scenario_profile.json");
    if ~isfile(path)
        error("S12:EngineSoundV12:VehicleCycle", ...
            "Vehicle-cycle scenario profile does not exist.");
    end
    raw = jsondecode(fileread(path));
    if ~isstruct(raw) || string(raw.schema_version) ~= ...
            "s12-engine-sound-v12-scenario-1" || ...
            string(raw.profile_id) ~= profileId || raw.synthetic ~= true
        error("S12:EngineSoundV12:VehicleCycle", ...
            "Vehicle-cycle scenario identity is invalid.");
    end
    names = ["idle_rpm", "redline_rpm", "cruise_rpm"];
    values = zeros(1, numel(names));
    for index = 1:numel(names)
        record = raw.parameters.(names(index));
        if ~isstruct(record) || string(record.source_level) ~= "C" || ...
                string(record.source) ~= "synthetic" || ...
                ~isnumeric(record.value) || ~isscalar(record.value) || ...
                ~isfinite(record.value) || ~isnumeric(record.range) || ...
                numel(record.range) ~= 2 || record.value < record.range(1) || ...
                record.value > record.range(2)
            error("S12:EngineSoundV12:VehicleCycle", ...
                "Vehicle-cycle parameter provenance is invalid.");
        end
        values(index) = double(record.value);
    end
    cachedId = profileId;
    cachedScenario = struct( ...
        "idle_rpm", values(1), ...
        "redline_rpm", values(2), ...
        "cruise_rpm", values(3));
end
scenario = cachedScenario;
end

function value = smoothProgress(time, startTime, endTime)
fraction = min(1, max(0, (time - startTime) / (endTime - startTime)));
value = fraction * fraction * (3 - 2 * fraction);
end

function value = blend(first, second, fraction)
value = first + (second - first) * fraction;
end
