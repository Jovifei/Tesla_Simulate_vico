function scenario = v6_build_cycle(profile, scenarioName, controlRate)
%V6_BUILD_CYCLE Build a control-rate driving cycle and physical state trace.

arguments
    profile (1,1) struct
    scenarioName (1,1) string = "full_demo"
    controlRate (1,1) double {mustBePositive, mustBeInteger} = 1000
end

switch lower(scenarioName)
    case "full_demo"
        duration = 22;
    case "steady_4000"
        duration = 3;
    case "tipout_5500"
        duration = 4;
    case "upshift_12"
        duration = 4;
    case "downshift_32"
        duration = 4;
    otherwise
        error("jovi:soundv6:UnknownScenario", "Unknown scenario: %s", scenarioName);
end

time = 0:1 / controlRate:duration - 1 / controlRate;
count = numel(time);
throttle = 0.04 * ones(1, count);
acceleration = zeros(1, count);

switch lower(scenarioName)
    case "full_demo"
        thirdRedlineSpeed = profile.engine.redline_rpm / 60 / ...
            (profile.driveline.gear_ratios(3) * profile.driveline.final_drive) * ...
            (2 * pi * profile.driveline.wheel_radius_m);
        pullEnd = min(9.4, 0.8 + thirdRedlineSpeed / ...
            (0.80 * profile.driveline.max_accel_mps2));
        throttle(time >= 0.8 & time < pullEnd) = 0.97;
        throttle(time >= pullEnd & time < pullEnd + 1.5) = 0.16;
        throttle(time >= pullEnd + 1.5 & time < pullEnd + 3.2) = 0.74;
        throttle(time >= pullEnd + 3.2) = 0.03;
        pullMask = time >= 0.8 & time < pullEnd;
        acceleration(pullMask) = profile.driveline.max_accel_mps2 .* ...
            (1 - 0.045 * (time(pullMask) - 0.8));
        acceleration(time >= pullEnd & time < pullEnd + 1.5) = -2.0;
        acceleration(time >= pullEnd + 1.5 & time < pullEnd + 3.2) = ...
            0.55 * profile.driveline.max_accel_mps2;
        acceleration(time >= pullEnd + 3.2) = -4.0;
    case "steady_4000"
        throttle(:) = 0.46;
    case "tipout_5500"
        throttle(time < 1.0) = 0.72;
        throttle(time >= 1.0) = 0.02;
    case "upshift_12"
        throttle(:) = 0.92;
        acceleration(:) = 2.0;
    case "downshift_32"
        throttle(:) = 0.05;
        acceleration(:) = -1.8;
end

if scenarioName == "steady_4000"
    gear = 2 * ones(1, count);
    wheelRpm = 4000 / (profile.driveline.final_drive * profile.driveline.gear_ratios(2));
    speedMps = wheelRpm / 60 * 2 * pi * profile.driveline.wheel_radius_m * ones(1, count);
elseif scenarioName == "tipout_5500"
    gear = 2 * ones(1, count);
    wheelRpm = 5500 / (profile.driveline.final_drive * profile.driveline.gear_ratios(2));
    speedMps = wheelRpm / 60 * 2 * pi * profile.driveline.wheel_radius_m * ones(1, count);
elseif scenarioName == "upshift_12"
    gear = ones(1, count);
    gear(time >= 1.35) = 2;
    wheelRpm = 6200 / (profile.driveline.final_drive * profile.driveline.gear_ratios(1));
    speedMps = wheelRpm / 60 * 2 * pi * profile.driveline.wheel_radius_m + cumtrapz(time, acceleration);
elseif scenarioName == "downshift_32"
    gear = 3 * ones(1, count);
    gear(time >= 1.25) = 2;
    wheelRpm = 3800 / (profile.driveline.final_drive * profile.driveline.gear_ratios(3));
    speedMps = max(0, wheelRpm / 60 * 2 * pi * profile.driveline.wheel_radius_m + cumtrapz(time, acceleration));
else
    speedMps = max(0, cumtrapz(time, acceleration));
    gear = select_gears(profile, speedMps, acceleration);
end

speedKmh = 3.6 * speedMps;
state = build_powertrain_state(profile, time, throttle, speedMps, gear);
scenario = struct("name", scenarioName, "control_rate_hz", controlRate, ...
    "time_s", time, "throttle", throttle, "acceleration_mps2", acceleration, ...
    "speed_kmh", speedKmh, "gear", gear, "state", state);
end

function gear = select_gears(profile, speedMps, acceleration)
count = numel(speedMps);
gear = ones(1, count);
shiftSpeed = profile.driveline.shift_rpm / 60 ./ ...
    (profile.driveline.gear_ratios(1:2) * profile.driveline.final_drive) * ...
    (2 * pi * profile.driveline.wheel_radius_m);
currentGear = 1;
lastShift = -inf;
minimumGap = round(0.35 * numel(speedMps) / 22);
for index = 2:count
    canShift = index - lastShift >= minimumGap;
    if canShift && acceleration(index) > 0.15 && currentGear < 3 && ...
            speedMps(index) >= shiftSpeed(currentGear)
        currentGear = currentGear + 1;
        lastShift = index;
    elseif canShift && acceleration(index) < -0.15 && currentGear > 1 && ...
            speedMps(index) <= 0.68 * shiftSpeed(currentGear - 1)
        currentGear = currentGear - 1;
        lastShift = index;
    end
    gear(index) = currentGear;
end
end

function state = build_powertrain_state(profile, time, throttle, speedMps, gear)
dt = time(2) - time(1);
count = numel(time);
wheelRpm = speedMps / (2 * pi * profile.driveline.wheel_radius_m) * 60;
kinematicRpm = wheelRpm .* profile.driveline.final_drive .* profile.driveline.gear_ratios(gear);
rpm = zeros(1, count);
torqueGain = ones(1, count);
rpm(1) = max(profile.engine.idle_rpm, profile.driveline.launch_rpm * throttle(1));
shiftStart = find(diff(gear) ~= 0) + 1;
for index = 2:count
    target = max(profile.engine.idle_rpm, kinematicRpm(index));
    currentShift = shiftStart(find(shiftStart <= index, 1, "last"));
    if ~isempty(currentShift)
        elapsed = time(index) - time(currentShift);
    else
        elapsed = inf;
    end
    [gain, coupling] = shift_state(profile.driveline, elapsed);
    torqueGain(index) = gain;
    if isfinite(elapsed) && elapsed < total_shift_time(profile.driveline)
        rpm(index) = rpm(index - 1) + coupling * (target - rpm(index - 1));
    else
        rpm(index) = target;
    end
    launchBlend = min(1, speedMps(index) / max(1, 4));
    launchSlip = profile.engine.idle_rpm + throttle(index) * ...
        (profile.driveline.launch_rpm - profile.engine.idle_rpm) * (1 - launchBlend);
    rpm(index) = min(profile.engine.redline_rpm, max(rpm(index), launchSlip));
end
load = min(1, max(0, throttle .* torqueGain));
baseTorque = interp1(profile.engine.torque_rpm, profile.engine.torque_nm, rpm, "linear", "extrap");
torqueNm = max(0, baseTorque .* load);
spark = interp1(profile.ecu.spark_rpm, profile.ecu.full_load_spark_deg, rpm, "linear", "extrap") + 16 * (1 - load);
lambda = 1 - (1 - profile.ecu.full_load_lambda) .* load;
dfco = false(1, count);
belowThreshold = throttle < profile.ecu.dfco_throttle & rpm > profile.ecu.dfco_rpm;
runLength = 0;
for index = 1:count
    runLength = belowThreshold(index) * (runLength + 1);
    dfco(index) = runLength * dt >= profile.ecu.dfco_delay_s;
end
lambda(dfco) = 1.35;
spark(dfco) = 0;
targetEgt = interp2(profile.thermal.rpm_axis, profile.thermal.load_axis, ...
    profile.thermal.egt_table_k, rpm, max(0.10, load), "linear");
targetEgt(dfco) = 520;
egt = zeros(1, count);
egt(1) = targetEgt(1);
for index = 2:count
    tau = profile.thermal.cooling_tau_s;
    egt(index) = egt(index - 1) + dt / tau * (targetEgt(index) - egt(index - 1));
end
fuelResidual = zeros(1, count);
for index = 2:count
    lift = max(0, throttle(index - 1) - throttle(index));
    fuelResidual(index) = fuelResidual(index - 1) * exp(-dt / profile.ecu.fuel_film_tau_s) + lift;
end
state = struct("rpm", rpm, "torque_gain", torqueGain, "load", load, ...
    "torque_nm", torqueNm, "spark_deg", spark, "lambda", lambda, ...
    "dfco", dfco, "egt_k", egt, "fuel_residual", fuelResidual, ...
    "shift_indices", shiftStart);
end

function [gain, coupling] = shift_state(shift, elapsed)
if ~isfinite(elapsed) || elapsed < 0
    gain = 1;
    coupling = 1;
    return
end
attack = shift.shift_attack_s;
hold = shift.shift_hold_s;
recovery = shift.shift_recovery_s;
settle = shift.shift_settle_s;
if elapsed < attack
    progress = elapsed / attack;
    gain = cosine_blend(1, shift.shift_min_torque, progress);
    coupling = 0.08 + 0.18 * progress;
elseif elapsed < attack + hold
    gain = shift.shift_min_torque;
    coupling = 0.22;
elseif elapsed < attack + hold + recovery
    progress = (elapsed - attack - hold) / recovery;
    gain = cosine_blend(shift.shift_min_torque, shift.shift_reengage_gain, progress);
    coupling = 0.24 + 0.56 * progress;
elseif elapsed < attack + hold + recovery + settle
    progress = (elapsed - attack - hold - recovery) / settle;
    gain = cosine_blend(shift.shift_reengage_gain, 1, progress);
    coupling = 0.80 + 0.20 * progress;
else
    gain = 1;
    coupling = 1;
end
end

function value = total_shift_time(shift)
value = shift.shift_attack_s + shift.shift_hold_s + shift.shift_recovery_s + shift.shift_settle_s;
end

function value = cosine_blend(startValue, finishValue, progress)
blend = 0.5 - 0.5 * cos(pi * min(1, max(0, progress)));
value = startValue + (finishValue - startValue) * blend;
end
