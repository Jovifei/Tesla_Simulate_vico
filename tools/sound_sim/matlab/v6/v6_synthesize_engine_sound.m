function [audio, result] = v6_synthesize_engine_sound(profile, scenario)
%V6_SYNTHESIZE_ENGINE_SOUND Render a temperature-aware C63 V6 sound field.

arguments
    profile (1,1) struct
    scenario (1,1) struct
end

rng(profile.seed, "twister");
sampleRate = profile.audio.sample_rate_hz;
duration = scenario.time_s(end) + 1 / scenario.control_rate_hz;
time = 0:1 / sampleRate:duration - 1 / sampleRate;
state = interpolate_state(scenario, time);
[bankLeft, bankRight] = render_blowdown_banks(profile, state, sampleRate);
[exhaustLeft, exhaustRight] = render_exhaust_network(profile, bankLeft, bankRight, ...
    time, state.sound_speed_mps);
[afterfireRawLeft, afterfireRawRight, events] = render_afterfire(profile, scenario, time);
[afterfireLeft, afterfireRight] = render_exhaust_network(profile, ...
    afterfireRawLeft, afterfireRawRight, time, state.sound_speed_mps);
mechanical = render_mechanical(profile, state, sampleRate);
exhaust = profile.mix.exhaust_gain * (exhaustLeft + exhaustRight);
mechanical = profile.mix.mechanical_gain * mechanical;
afterfire = profile.mix.afterfire_gain * (afterfireLeft + afterfireRight);
rasp = v6_render_combustion_rasp(profile, state, exhaust, sampleRate);
exhaustRms = active_rms(exhaust);
afterfirePeakLimit = exhaustRms * db_to_mag( ...
    profile.mix.afterfire_peak_over_exhaust_db);
afterfire = limit_peak(afterfire, afterfirePeakLimit);
rawEngine = exhaust + mechanical + rasp + afterfire;
[external, cabin, speaker] = propagate_sound(profile, rawEngine, time);
audio = profile.audio.master_gain * tanh(external);
audio = audio - mean(audio);
peak = max(abs(audio));
normalizationGain = min(1, profile.audio.peak_limit / max(peak, eps));
audio = normalizationGain * audio;

result = struct();
result.time_s = time;
result.audio_sample_rate_hz = sampleRate;
result.audio_pre_normalization = external;
result.layers = struct("blowdown_left", bankLeft, "blowdown_right", bankRight, ...
    "exhaust_left", exhaustLeft, "exhaust_right", exhaustRight, ...
    "exhaust", exhaust, "afterfire_raw_left", afterfireRawLeft, ...
    "afterfire_raw_right", afterfireRawRight, "afterfire_left", afterfireLeft, ...
    "afterfire_right", afterfireRight, "afterfire", afterfire, ...
    "mechanical", mechanical, "rasp", rasp, "external", external, "cabin", cabin, ...
    "speaker", speaker);
result.events = events;
result.normalization_gain = normalizationGain;
result.state = state;
result.metrics = v6_audio_metrics(external, time, state.rpm, sampleRate);
end

function state = interpolate_state(scenario, time)
controlTime = scenario.time_s;
source = scenario.state;
names = ["rpm", "torque_gain", "load", "torque_nm", "spark_deg", ...
    "lambda", "egt_k", "fuel_residual"];
state = struct();
for index = 1:numel(names)
    name = names(index);
    state.(name) = interp1(controlTime, source.(name), time, "linear", "extrap");
end
state.dfco = interp1(controlTime, double(source.dfco), time, "previous", "extrap") > 0.5;
state.throttle = interp1(controlTime, scenario.throttle, time, "previous", "extrap");
state.gear = interp1(controlTime, scenario.gear, time, "previous", "extrap");
state.sound_speed_mps = sqrt(1.33 * 287.0 * max(300, state.egt_k));
end

function [left, right] = render_blowdown_banks(profile, state, sampleRate)
sampleCount = numel(state.rpm);
cyclePhase = 2 * pi * cumsum(state.rpm / ...
    (60 * profile.engine.cycle_revolutions)) / sampleRate;
left = zeros(1, sampleCount);
right = zeros(1, sampleCount);
torqueFraction = max(0, state.torque_nm) / max(profile.engine.torque_nm);
pressureScale = sqrt(max(profile.blowdown.evo_pressure_pa - 101325, 1) / 250000);
areaScale = sqrt(profile.blowdown.valve_area_m2 / 750e-6);
temperatureScale = sqrt(max(300, state.egt_k) / ...
    profile.blowdown.exhaust_temperature_k);
amplitude = pressureScale * areaScale .* (0.08 + 0.92 * sqrt(torqueFraction)) .* ...
    (0.30 + 0.70 * state.load) .* temperatureScale;
for orderIndex = 1:profile.engine.cylinders
    cylinder = profile.engine.firing_order(orderIndex);
    firingAngle = 2 * pi * (orderIndex - 1) / profile.engine.cylinders;
    pulse = exp(profile.blowdown.pulse_sharpness * ...
        (cos(cyclePhase - firingAngle) - 1));
    blowdown = amplitude .* pulse;
    if profile.engine.bank_by_cylinder(cylinder) == 1
        left = left + blowdown;
    else
        right = right + blowdown;
    end
end
left = left / 4;
right = right / 4;
end

function [left, right] = render_exhaust_network(profile, inputLeft, inputRight, time, soundSpeed)
loss = mean(profile.exhaust.loss_db_per_m);
left = render_bank(profile, inputLeft, time, soundSpeed, profile.exhaust.primary_left_m, loss);
right = render_bank(profile, inputRight, time, soundSpeed, profile.exhaust.primary_right_m, loss);
coupling = profile.exhaust.crossover_coupling;
leftDelayed = delay_time(left, time, 0.0022 * ones(size(time)));
rightDelayed = delay_time(right, time, 0.0022 * ones(size(time)));
left = (1 - coupling) * left + coupling * rightDelayed;
right = (1 - coupling) * right + coupling * leftDelayed;
end

function output = render_bank(profile, input, time, soundSpeed, primaryLengths, lossDb)
primary = zeros(size(input));
for index = 1:numel(primaryLengths)
    delayed = delay_time(input, time, primaryLengths(index) ./ soundSpeed);
    primary = primary + delayed * db_to_mag(-lossDb * primaryLengths(index));
end
primary = primary / numel(primaryLengths);
collector = delay_time(primary, time, profile.exhaust.collector_length_m ./ soundSpeed);
catalyst = delay_time(collector, time, profile.exhaust.catalyst_length_m ./ soundSpeed);
catalyst = profile.exhaust.catalyst_transmission * catalyst + ...
    profile.exhaust.catalyst_reflection * delay_time(catalyst, time, ...
    2 * profile.exhaust.catalyst_length_m ./ soundSpeed);
midpipe = delay_time(catalyst, time, profile.exhaust.midpipe_length_m ./ soundSpeed);
main = delay_time(midpipe, time, profile.exhaust.muffler_main_length_m ./ soundSpeed);
bypass = delay_time(midpipe, time, profile.exhaust.muffler_bypass_length_m ./ soundSpeed);
muffler = 0.72 * main + 0.28 * bypass;
muffler = muffler + profile.exhaust.muffler_reflection * delay_time(muffler, time, ...
    2 * profile.exhaust.muffler_main_length_m ./ soundSpeed);
output = delay_time(muffler, time, profile.exhaust.tailpipe_length_m ./ soundSpeed);
output = output + profile.exhaust.tail_reflection * delay_time(output, time, ...
    2 * profile.exhaust.tailpipe_length_m ./ soundSpeed);
end

function output = delay_time(input, time, delaySeconds)
queryTime = time - delaySeconds;
output = interp1(time, input, queryTime, "linear", 0);
end

function [left, right, events] = render_afterfire(profile, scenario, time)
left = zeros(size(time));
right = zeros(size(time));
eventTime = [];
eventType = strings(1, 0);
eventStrength = [];
control = scenario;
calibration = load_c63_calibration(profile.afterfire.calibration);
liftIndices = find([false, diff(control.throttle) < -0.24]);
shiftIndices = control.state.shift_indices;
for index = 1:numel(shiftIndices)
    trigger = shiftIndices(index);
    if control.state.egt_k(trigger) < profile.afterfire.egt_threshold_k
        continue
    end
    [left, right, eventTime, eventType, eventStrength] = add_afterfire_event( ...
        left, right, eventTime, eventType, eventStrength, profile, time, ...
        control.time_s(trigger) + 0.018, shift_type(control.gear, trigger), ...
        0.48, calibration, 0);
end
for index = 1:numel(liftIndices)
    trigger = liftIndices(index);
    if control.state.rpm(trigger) < profile.afterfire.minimum_rpm || ...
            control.state.egt_k(trigger) < profile.afterfire.egt_threshold_k
        continue
    end
    cursor = control.time_s(trigger) + 0.022;
    finish = cursor + profile.afterfire.overrun_duration_s;
    maximumBursts = max(profile.afterfire.cluster_size, ...
        ceil(profile.afterfire.overrun_duration_s / profile.afterfire.base_interval_s));
    for burstIndex = 1:maximumBursts
        progress = (cursor - control.time_s(trigger)) / profile.afterfire.overrun_duration_s;
        if cursor > finish
            break
        end
        strength = (0.72 - 0.40 * progress) * ...
            min(1, control.state.fuel_residual(trigger) + 0.25);
        [left, right, eventTime, eventType, eventStrength] = add_afterfire_event( ...
            left, right, eventTime, eventType, eventStrength, profile, time, ...
            cursor, "overrun", strength, calibration, progress);
        cursor = cursor + profile.afterfire.base_interval_s * ...
            (0.82 + 0.68 * progress + 0.22 * rand);
    end
end
events = table(eventTime.', eventType.', eventStrength.', ...
    VariableNames=["time_s", "type", "strength"]);
end

function [left, right, eventTime, eventType, eventStrength] = add_afterfire_event( ...
    left, right, eventTime, eventType, eventStrength, profile, time, startTime, ...
    type, strength, calibration, progress)
sampleRate = profile.audio.sample_rate_hz;
startIndex = max(1, round(startTime * sampleRate) + 1);
duration = min(0.14, max(0.055, 8 * profile.afterfire.body_decay_s));
count = min(round(duration * sampleRate), numel(time) - startIndex + 1);
if count < 4
    return
end
localTime = (0:count - 1) / sampleRate;
attack = 1 - exp(-localTime / profile.afterfire.attack_s);
body = zeros(1, count);
metal = zeros(1, count);
pitchScale = (0.91 + 0.18 * rand) * (1 - 0.07 * progress);
for frequency = profile.afterfire.body_hz
    body = body + sin(2 * pi * frequency * pitchScale * localTime + 2 * pi * rand);
end
for index = 1:numel(calibration.mode_hz)
    frequency = calibration.mode_hz(index) * pitchScale;
    sweep = frequency * (0.12 * rand - 0.06) / duration;
    phase = 2 * pi * (frequency * localTime + 0.5 * sweep * localTime .^ 2);
    metal = metal + calibration.mode_gain(index) * sin(phase + 2 * pi * rand);
end
body = body / max(max(abs(body)), eps);
metal = metal / max(max(abs(metal)), eps);
noise = filter(reshape(calibration.fir, 1, []), 1, randn(1, count));
noise = noise / max(max(abs(noise)), eps);
crack = filter([1, -2, 1], [1, -0.42], randn(1, count));
crack = crack / max(max(abs(crack)), eps);
burst = strength * attack .* ( ...
    profile.afterfire.body_gain * exp(-localTime / profile.afterfire.body_decay_s) .* body + ...
    profile.afterfire.metal_gain * exp(-localTime / profile.afterfire.metal_decay_s) .* metal + ...
    0.72 * profile.afterfire.crack_gain * exp(-localTime / ...
    profile.afterfire.crack_decay_s) .* crack + 0.55 * noise);
finishIndex = startIndex + count - 1;
if rand < 0.5
    left(startIndex:finishIndex) = left(startIndex:finishIndex) + burst;
else
    right(startIndex:finishIndex) = right(startIndex:finishIndex) + burst;
end

eventTime(end + 1) = time(startIndex);
eventType(end + 1) = type;
eventStrength(end + 1) = strength;
end

function type = shift_type(gear, trigger)
if trigger > 1 && gear(trigger) < gear(trigger - 1)
    type = "downshift";
else
    type = "upshift";
end
end

function calibration = load_c63_calibration(name)
if exist("load_backfire_calibration", "file") ~= 2
    addpath(fileparts(fileparts(mfilename("fullpath"))));
end
calibration = load_backfire_calibration(name);
end

function mechanical = render_mechanical(profile, state, sampleRate)
phase = 2 * pi * cumsum(state.rpm / 60) / sampleRate;
mechanical = zeros(size(phase));
for index = 1:numel(profile.mechanical.orders)
    gain = db_to_mag(profile.mechanical.band_gain_db(index));
    mechanical = mechanical + gain * state.load .* ...
        sin(profile.mechanical.orders(index) * phase + 2 * pi * rand);
end
texture = filter([1, -1], [1, -0.82], randn(size(phase)));
texture = texture / max(max(abs(texture)), eps);
mechanical = mechanical + db_to_mag(profile.mechanical.noise_gain_db) .* ...
    state.load .* state.torque_gain .* texture;
end

function [external, cabin, speaker] = propagate_sound(profile, input, time)
directDelay = profile.propagation.direct_distance_m / 343.0;
direct = delay_time(input, time, directDelay * ones(size(time)));
ground = delay_time(input, time, profile.propagation.ground_delay_s * ones(size(time)));
body = delay_time(input, time, profile.propagation.body_delay_s * ones(size(time)));
external = direct + profile.propagation.ground_gain * ground + ...
    profile.propagation.body_gain * body;
cabin = filter([0.14, 0.08], [1, -0.78], external);
speaker = filter([0.78, -0.70], [1, -0.72], cabin);
end

function value = db_to_mag(decibels)
value = 10 .^ (decibels / 20);
end

function value = active_rms(signal)
threshold = 0.05 * max(abs(signal));
active = signal(abs(signal) >= threshold);
if isempty(active)
    value = 0;
else
    value = sqrt(mean(active .^ 2));
end
end

function output = limit_peak(input, peakLimit)
peak = max(abs(input));
output = input * min(1, peakLimit / max(peak, eps));
end
