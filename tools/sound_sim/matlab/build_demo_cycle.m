function [time, rpm, throttle, gear, speedKmh] = build_demo_cycle(profile, sampleRate)
%BUILD_DEMO_CYCLE Simulate launch, 1-2-3 upshifts, roll-on, and overrun.

arguments
    profile (1,1) struct
    sampleRate (1,1) double {mustBePositive, mustBeInteger}
end

duration = 22;
time = 0:1 / sampleRate:duration - 1 / sampleRate;
thirdRedlineSpeed = profile.redline_rpm / 60 / ...
    (profile.gear_ratios(3) * profile.final_drive) * ...
    (2 * pi * profile.wheel_radius_m);
pullEnd = min(9.4, 0.8 + thirdRedlineSpeed / (0.80 * profile.max_accel_mps2));
throttle = 0.04 * ones(size(time));
throttle(time >= 0.8 & time < pullEnd) = 0.97;
throttle(time >= pullEnd & time < pullEnd + 1.5) = 0.16;
throttle(time >= pullEnd + 1.5 & time < pullEnd + 3.2) = 0.74;
throttle(time >= pullEnd + 3.2) = 0.03;

acceleration = zeros(size(time));
pullOne = time >= 0.8 & time < pullEnd;
acceleration(pullOne) = profile.max_accel_mps2 .* ...
    (1 - 0.045 * (time(pullOne) - 0.8));
acceleration(time >= pullEnd & time < pullEnd + 1.5) = -2.0;
acceleration(time >= pullEnd + 1.5 & time < pullEnd + 3.2) = 0.55 * profile.max_accel_mps2;
acceleration(time >= pullEnd + 3.2) = -4.0;
speedMps = min(thirdRedlineSpeed, max(0, cumtrapz(time, acceleration)));
speedKmh = 3.6 * speedMps;

shiftSpeed = profile.shift_rpm / 60 ./ ...
    (profile.gear_ratios(1:2) * profile.final_drive) * ...
    (2 * pi * profile.wheel_radius_m);
gear = ones(size(time));
currentGear = 1;
lastShiftIndex = -inf;
minimumShiftGap = round(0.35 * sampleRate);
for index = 2:numel(time)
    canShift = index - lastShiftIndex >= minimumShiftGap;
    if canShift && acceleration(index) > 0.15 && currentGear < 3 ...
            && speedMps(index) >= shiftSpeed(currentGear)
        currentGear = currentGear + 1;
        lastShiftIndex = index;
    elseif canShift && acceleration(index) < -0.15 && currentGear > 1 ...
            && speedMps(index) <= 0.68 * shiftSpeed(currentGear - 1)
        currentGear = currentGear - 1;
        lastShiftIndex = index;
    end
    gear(index) = currentGear;
end

downshiftIndices = find(diff(gear) < 0) + 1;
for shiftIndex = downshiftIndices
    blipLength = min(round(0.11 * sampleRate), numel(throttle) - shiftIndex + 1);
    blip = 0.34 * sin(linspace(0, pi, blipLength)).^2;
    throttle(shiftIndex:shiftIndex + blipLength - 1) = min(1, ...
        throttle(shiftIndex:shiftIndex + blipLength - 1) + blip);
end

wheelRpm = speedMps / (2 * pi * profile.wheel_radius_m) * 60;
rpm = wheelRpm .* profile.final_drive .* profile.gear_ratios(gear);
launchBlend = min(1, speedMps / max(1, 0.75 * shiftSpeed(1)));
launchSlip = profile.idle_rpm + throttle .* ...
    (profile.launch_rpm - profile.idle_rpm) .* (1 - launchBlend);
rpm = max(profile.idle_rpm, max(rpm, launchSlip));
rpm = min(profile.redline_rpm, rpm);

shiftIndices = find(diff(gear) ~= 0) + 1;
shiftSamples = max(2, round(profile.shift_duration_s * sampleRate));
for shiftIndex = shiftIndices
    finishIndex = min(numel(rpm), shiftIndex + shiftSamples - 1);
    targetRpm = max(profile.idle_rpm, wheelRpm(finishIndex) * ...
        profile.final_drive * profile.gear_ratios(gear(shiftIndex)));
    progress = linspace(0, 1, finishIndex - shiftIndex + 1);
    blend = 0.5 - 0.5 * cos(pi * progress);
    rpmBeforeShift = rpm(shiftIndex - 1);
    rpm(shiftIndex:finishIndex) = rpmBeforeShift + ...
        (targetRpm - rpmBeforeShift) .* blend;
end
end
