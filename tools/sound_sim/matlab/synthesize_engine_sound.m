function [audio, trace, events] = synthesize_engine_sound( ...
    profile, time, rpm, throttle, gear, sampleRate)
%SYNTHESIZE_ENGINE_SOUND Render cylinder pulses through vehicle-specific acoustics.

arguments
    profile (1,1) struct
    time (1,:) double
    rpm (1,:) double
    throttle (1,:) double
    gear (1,:) double
    sampleRate (1,1) double {mustBePositive, mustBeInteger}
end

sampleCount = numel(time);
if any([numel(rpm), numel(throttle), numel(gear)] ~= sampleCount)
    error("jovi:sound:SizeMismatch", "All drive-cycle vectors must have equal length.");
end

rng(profile.seed, "twister");
rpmNorm = min(1, max(0, (rpm - profile.idle_rpm) / ...
    (profile.redline_rpm - profile.idle_rpm)));
shiftDirections = diff(gear);
shiftIndices = find(shiftDirections ~= 0) + 1;
shiftDirections = shiftDirections(shiftIndices - 1);
shiftGain = build_shift_gain(sampleCount, shiftIndices, shiftDirections, ...
    profile, sampleRate);
loadGain = (0.18 + 0.82 * throttle) .* shiftGain;

[bankOne, bankTwo] = firing_pulse_banks(profile, rpm, sampleRate);
bankOne = bankOne .* loadGain;
bankTwo = bankTwo .* loadGain;
exhaustOne = resonator_bank(bankOne, profile.resonance_hz, ...
    profile.resonance_q, profile.resonance_gain, sampleRate);
exhaustTwo = resonator_bank(delay_signal(bankTwo, bank_delay(profile)), ...
    1.018 * profile.resonance_hz, profile.resonance_q, ...
    0.94 * profile.resonance_gain, sampleRate);
rawPulse = bankOne + bankTwo;
switch profile.name
    case "hellcat"
        exhaust = 0.82 * (exhaustOne + exhaustTwo) + 0.18 * rawPulse;
    case "gtr_r35"
        exhaust = 0.68 * (exhaustOne + exhaustTwo) + 0.12 * rawPulse;
    otherwise
        exhaust = 0.72 * (exhaustOne + exhaustTwo) + 0.30 * rawPulse;
end
exhaust = scale_rms(exhaust, 0.31);

induction = render_induction(profile, rpm, rpmNorm, throttle, shiftGain, ...
    shiftIndices, sampleRate);
shiftLayer = render_shift_transients(profile, shiftIndices, shiftDirections, ...
    sampleCount, sampleRate);
if profile.backfire_enabled
    [backfire, events] = render_vehicle_backfire( ...
        profile, rpm, throttle, shiftIndices, shiftDirections, sampleRate);
else
    backfire = zeros(1, sampleCount);
    events = struct("style", profile.backfire_style, ...
        "calibration", profile.backfire_calibration, "time_s", [], ...
        "strength", [], "type", strings(1, 0));
end

audio = exhaust + induction + shiftLayer + backfire;
audio = audio - mean(audio);
audio = tanh(1.18 * audio);
peak = max(abs(audio));
if peak > 0
    audio = 0.96 * audio / peak;
end

firingHz = rpm / 60 * numel(profile.firing_order) / profile.cycle_revolutions;
trace = table(time.', rpm.', throttle.', gear.', firingHz.', shiftGain.', ...
    bankOne.', bankTwo.', exhaust.', induction.', shiftLayer.', backfire.', ...
    VariableNames=["time_s", "rpm", "throttle", "gear", "firing_hz", ...
    "shift_gain", "bank_1", "bank_2", "exhaust", "induction", ...
    "shift_transient", "backfire"]);
end

function gain = build_shift_gain( ...
    sampleCount, shiftIndices, shiftDirections, profile, sampleRate)
gain = ones(1, sampleCount);
switch profile.shift_style
    case "zf_burble"
        timingMs = [22, 30, 100, 80];
        minimumGain = 0.25;
    case "dct_cut"
        timingMs = [6, 8, 22, 25];
        minimumGain = 0.62;
    case "mct_bark"
        timingMs = [12, 28, 65, 45];
        minimumGain = 0.28;
    case "manual_clutch"
        timingMs = [35, 45, 120, 90];
        minimumGain = 0.12;
    case "asg_jerk"
        timingMs = [25, 70, 110, 80];
        minimumGain = 0.08;
    case "f1_dct"
        timingMs = [5, 7, 18, 20];
        minimumGain = 0.70;
    otherwise
        timingMs = [12, 28, 55, 40];
        minimumGain = 0.18;
end
for eventIndex = 1:numel(shiftIndices)
    shiftIndex = shiftIndices(eventIndex);
    localMinimum = minimumGain;
    overshoot = profile.shift_reengage_gain;
    if shiftDirections(eventIndex) < 0
        localMinimum = max(0.55, minimumGain);
        overshoot = overshoot + 0.05;
    end
    attackSamples = max(2, round(timingMs(1) * 0.001 * sampleRate));
    holdSamples = max(1, round(timingMs(2) * 0.001 * sampleRate));
    recoverySamples = max(2, round(timingMs(3) * 0.001 * sampleRate));
    settleSamples = max(2, round(timingMs(4) * 0.001 * sampleRate));
    startIndex = max(1, shiftIndex - attackSamples + 1);
    attack = cosine_blend(1, localMinimum, shiftIndex - startIndex + 1);
    holdFinish = min(sampleCount, shiftIndex + holdSamples - 1);
    recoveryFinish = min(sampleCount, holdFinish + recoverySamples);
    settleFinish = min(sampleCount, recoveryFinish + settleSamples);
    recovery = cosine_blend(localMinimum, overshoot, ...
        recoveryFinish - holdFinish + 1);
    settle = cosine_blend(overshoot, 1, settleFinish - recoveryFinish + 1);
    gain(startIndex:shiftIndex) = attack;
    gain(shiftIndex:holdFinish) = localMinimum;
    gain(holdFinish:recoveryFinish) = recovery;
    gain(recoveryFinish:settleFinish) = settle;
end
end

function values = cosine_blend(startValue, finishValue, count)
progress = linspace(0, 1, count);
blend = 0.5 - 0.5 * cos(pi * progress);
values = startValue + (finishValue - startValue) .* blend;
end

function [bankOne, bankTwo] = firing_pulse_banks(profile, rpm, sampleRate)
cyclePhase = 2 * pi * cumsum(rpm / ...
    (60 * profile.cycle_revolutions)) / sampleRate;
firingAngles = zeros(1, profile.cylinders);
for eventIndex = 1:profile.cylinders
    cylinder = profile.firing_order(eventIndex);
    firingAngles(cylinder) = 2 * pi * (eventIndex - 1) / profile.cylinders;
end

bankOne = zeros(size(rpm));
bankTwo = zeros(size(rpm));
for cylinder = 1:profile.cylinders
    pulse = exp(profile.pulse_sharpness * ...
        (cos(cyclePhase - firingAngles(cylinder)) - 1));
    pulse = pulse - mean(pulse);
    if profile.bank_by_cylinder(cylinder) == 1
        bankOne = bankOne + pulse;
    else
        bankTwo = bankTwo + pulse;
    end
end
bankOne = bankOne / max(1, nnz(profile.bank_by_cylinder == 1));
bankTwo = bankTwo / max(1, nnz(profile.bank_by_cylinder == 2));
end

function output = resonator_bank(input, frequencies, quality, gains, sampleRate)
output = zeros(size(input));
for resonanceIndex = 1:numel(frequencies)
    frequency = frequencies(resonanceIndex);
    radius = exp(-pi * frequency / (quality(resonanceIndex) * sampleRate));
    angle = 2 * pi * frequency / sampleRate;
    numerator = (1 - radius) * [1, 0, -1];
    denominator = [1, -2 * radius * cos(angle), radius^2];
    output = output + gains(resonanceIndex) * ...
        filter(numerator, denominator, input);
end
end

function delayed = delay_signal(input, delaySamples)
if delaySamples <= 0
    delayed = input;
else
    delayed = [zeros(1, delaySamples), input(1:end - delaySamples)];
end
end

function delay = bank_delay(profile)
switch profile.name
    case "hellcat"
        delay = 7;
    case "gtr_r35"
        delay = 2;
    otherwise
        delay = 4;
end
end

function induction = render_induction(profile, rpm, rpmNorm, throttle, shiftGain, ...
    shiftIndices, sampleRate)
sampleCount = numel(rpm);
noise = randn(1, sampleCount);
switch profile.induction
    case "supercharger"
        whineHz = rpm / 60 * profile.induction_order;
        whinePhase = 2 * pi * cumsum(whineHz) / sampleRate;
        induction = profile.induction_gain * rpmNorm .* throttle .* shiftGain .* ...
            (sin(whinePhase) + 0.32 * sin(2 * whinePhase) ...
            + 0.10 * sin(3 * whinePhase));
    case {"twin_turbo", "sequential_turbo"}
        spool = sqrt(rpmNorm) .* throttle .* shiftGain;
        if profile.induction == "sequential_turbo"
            secondStage = min(1, max(0, (rpmNorm - 0.42) / 0.40));
            spool = spool .* (0.72 + 0.28 * secondStage);
        end
        turboHz = 1700 + 6500 * spool;
        turboPhase = 2 * pi * cumsum(turboHz) / sampleRate;
        hiss = filter([1, -1], [1, -0.92], noise);
        induction = profile.induction_gain * spool .* ...
            (sin(turboPhase) + 0.18 * sin(1.65 * turboPhase) + 0.012 * hiss);
        induction = induction + render_blowoff(shiftIndices, throttle, sampleRate);
    otherwise
        intakeHz = rpm / 60 * max(1, profile.induction_order);
        intakePhase = 2 * pi * cumsum(intakeHz) / sampleRate;
        roar = sin(intakePhase) + 0.38 * sin(2 * intakePhase) ...
            + 0.16 * sin(3 * intakePhase) + 0.08 * sin(0.5 * intakePhase);
        pole = exp(-2 * pi * 1800 / sampleRate);
        texture = filter(1 - pole, [1, -pole], noise);
        induction = profile.induction_gain * (0.15 + 0.85 * throttle) .* ...
            (0.25 + 0.75 * rpmNorm) .* ...
            (0.94 * roar + profile.texture_noise_gain * texture);
end
end

function layer = render_blowoff(shiftIndices, throttle, sampleRate)
sampleCount = numel(throttle);
window = max(1, round(0.035 * sampleRate));
drop = zeros(1, sampleCount);
drop(window + 1:end) = throttle(1:end - window) - throttle(window + 1:end);
liftIndices = find(drop > 0.45 & ~[false, drop(1:end - 1) > 0.45]);
triggers = unique([shiftIndices, liftIndices]);
layer = zeros(1, sampleCount);
for trigger = triggers
    burstLength = min(round(0.18 * sampleRate), sampleCount - trigger + 1);
    localTime = (0:burstLength - 1) / sampleRate;
    envelope = (1 - exp(-localTime / 0.004)) .* exp(-localTime / 0.060);
    air = filter([1, -1], [1, -0.86], randn(1, burstLength));
    layer(trigger:trigger + burstLength - 1) = ...
        layer(trigger:trigger + burstLength - 1) + 0.09 * envelope .* air;
end
end

function layer = render_shift_transients( ...
    profile, shiftIndices, shiftDirections, sampleCount, sampleRate)
layer = zeros(1, sampleCount);
for eventIndex = 1:numel(shiftIndices)
    shiftIndex = shiftIndices(eventIndex);
    isDownshift = shiftDirections(eventIndex) < 0;
    duration = 0.055 + 0.025 * isDownshift;
    decay = 0.018 + 0.010 * isDownshift;
    detailGain = 0.018 + 0.010 * isDownshift;
    burstLength = min(round(duration * sampleRate), ...
        sampleCount - shiftIndex + 1);
    localTime = (0:burstLength - 1) / sampleRate;
    envelope = (1 - exp(-localTime / 0.002)) .* exp(-localTime / decay);
    impulse = zeros(1, burstLength);
    impulse(1) = 1;
    burst = zeros(1, burstLength);
    bodyHz = profile.resonance_hz(1:min(3, end));
    bodyGain = profile.resonance_gain(1:numel(bodyHz));
    for toneIndex = 1:numel(bodyHz)
        radius = exp(-1 / max(1, decay * sampleRate));
        denominator = [1, -2 * radius * cos(2 * pi * bodyHz(toneIndex) / sampleRate), ...
            radius^2];
        burst = burst + bodyGain(toneIndex) * ...
            filter(1 - radius, denominator, impulse);
    end
    layer(shiftIndex:shiftIndex + burstLength - 1) = ...
        layer(shiftIndex:shiftIndex + burstLength - 1) + ...
        detailGain * envelope .* burst;
end
end

function [layer, events] = render_vehicle_backfire( ...
    profile, rpm, throttle, shiftIndices, shiftDirections, sampleRate)
sampleCount = numel(rpm);
window = max(1, round(0.040 * sampleRate));
drop = zeros(1, sampleCount);
drop(window + 1:end) = throttle(1:end - window) - throttle(window + 1:end);
liftIndices = find(drop > 0.48 & rpm > 2600 & ...
    ~[false, drop(1:end - 1) > 0.48]);

calibration = load_backfire_calibration(profile.backfire_calibration);
[layer, eventTimes, strengths, eventTypes] = calibrated_backfires( ...
    profile, calibration, liftIndices, shiftIndices, shiftDirections, ...
    sampleCount, sampleRate);
events = struct("style", profile.backfire_style, ...
    "calibration", calibration.name, "time_s", eventTimes, ...
    "strength", strengths, "type", eventTypes);
end

function [layer, times, strengths, types] = calibrated_backfires( ...
    profile, calibration, lifts, shifts, shiftDirections, sampleCount, sampleRate)
layer = zeros(1, sampleCount);
times = [];
strengths = [];
types = strings(1, 0);
baseInterval = max(0.012, 0.001 * calibration.interval_ms);

for shiftEvent = 1:numel(shifts)
    direction = shiftDirections(shiftEvent);
    popCount = shift_pop_count(profile.backfire_style, direction);
    cursor = shifts(shiftEvent);
    for popIndex = 1:popCount
        cursor = cursor + round(baseInterval * (0.85 + 0.35 * rand) * sampleRate);
        if cursor > sampleCount
            break
        end
        [burst, strength] = calibrated_burst( ...
            profile, calibration, sampleRate, sampleCount - cursor + 1, ...
            popIndex / max(1, popCount), 0.75);
        layer = add_burst(layer, cursor, burst);
        times(end + 1) = (cursor - 1) / sampleRate; %#ok<AGROW>
        strengths(end + 1) = strength; %#ok<AGROW>
        if direction > 0
            types(end + 1) = "upshift"; %#ok<AGROW>
        else
            types(end + 1) = "downshift"; %#ok<AGROW>
        end
    end
end

for trigger = lifts
    cursor = trigger;
    maximumPops = min(28, max(calibration.cluster_size, ...
        round(profile.backfire_overrun_s / (2.1 * baseInterval))));
    finishIndex = min(sampleCount, trigger + ...
        round(profile.backfire_overrun_s * sampleRate));
    for popIndex = 1:maximumPops
        progress = (cursor - trigger) / max(1, finishIndex - trigger);
        interval = baseInterval * (0.85 + 0.65 * progress) * ...
            (0.78 + 0.44 * rand);
        cursor = cursor + round(interval * sampleRate);
        if cursor > finishIndex
            break
        end
        strengthScale = 0.98 - 0.58 * progress;
        [burst, strength] = calibrated_burst( ...
            profile, calibration, sampleRate, sampleCount - cursor + 1, ...
            progress, strengthScale);
        layer = add_burst(layer, cursor, burst);
        times(end + 1) = (cursor - 1) / sampleRate; %#ok<AGROW>
        strengths(end + 1) = strength; %#ok<AGROW>
        types(end + 1) = "overrun"; %#ok<AGROW>
    end
end
end

function count = shift_pop_count(style, direction)
if direction < 0
    switch style
        case {"amg_bang", "rotary_flame"}
            count = 5;
        case {"metallic_crackle", "flatplane_crack"}
            count = 4;
        otherwise
            count = 3;
    end
else
    count = 1 + any(style == ["low_boom", "amg_bang", "v12_bark"]);
end
end

function [burst, strength] = calibrated_burst( ...
    profile, calibration, sampleRate, remainingSamples, progress, strengthScale)
switch profile.backfire_style
    case "low_boom"
        decaySeconds = max(0.080, 0.001 * calibration.decay_ms);
        duration = min(0.24, 2.0 * decaySeconds);
        mix = [0.28, 1.00];
        strength = 0.52 + 0.20 * rand;
        drive = 1.35;
    case "metallic_crackle"
        decaySeconds = max(0.009, 0.001 * calibration.decay_ms);
        duration = 0.032 + 0.018 * rand;
        mix = [1.10, 0.48];
        strength = 0.34 + 0.22 * rand;
        drive = 2.80;
    case "amg_bang"
        decaySeconds = max(0.024, 0.001 * calibration.decay_ms);
        duration = 0.060 + 0.025 * rand;
        mix = [0.72, 0.88];
        strength = 0.50 + 0.28 * rand;
        drive = 2.10;
    case "turbo_burble"
        decaySeconds = max(0.032, 0.001 * calibration.decay_ms);
        duration = 0.080 + 0.030 * rand;
        mix = [0.48, 0.82];
        strength = 0.42 + 0.22 * rand;
        drive = 1.80;
    case "rotary_flame"
        decaySeconds = max(0.016, 0.001 * calibration.decay_ms);
        duration = 0.050 + 0.025 * rand;
        mix = [0.95, 0.58];
        strength = 0.46 + 0.28 * rand;
        drive = 3.10;
    case "v10_overrun"
        decaySeconds = max(0.012, 0.001 * calibration.decay_ms);
        duration = 0.040 + 0.018 * rand;
        mix = [0.38, 0.92];
        strength = 0.30 + 0.18 * rand;
        drive = 1.75;
    case "flatplane_crack"
        decaySeconds = max(0.017, 0.001 * calibration.decay_ms);
        duration = 0.052 + 0.022 * rand;
        mix = [0.65, 0.78];
        strength = 0.42 + 0.22 * rand;
        drive = 2.45;
    otherwise
        decaySeconds = max(0.030, 0.001 * calibration.decay_ms);
        duration = 0.075 + 0.025 * rand;
        mix = [0.45, 0.98];
        strength = 0.50 + 0.24 * rand;
        drive = 2.00;
end
strength = strength * strengthScale;
burstLength = min(max(2, round(duration * sampleRate)), remainingSamples);
localTime = (0:burstLength - 1) / sampleRate;
attackSeconds = max(0.00035, 0.001 * calibration.attack_ms);
envelope = (1 - exp(-localTime / attackSeconds)) .* ...
    exp(-localTime / decaySeconds);

noise = filter(reshape(calibration.fir, 1, []), 1, randn(1, burstLength));
noise = noise / (max(abs(noise)) + eps);
modal = zeros(1, burstLength);
pitchScale = (0.90 + 0.20 * rand) * (1 - 0.08 * progress);
for modeIndex = 1:numel(calibration.mode_hz)
    modeDecay = decaySeconds * (0.70 + 0.12 * modeIndex);
    modeHz = calibration.mode_hz(modeIndex) * pitchScale;
    sweep = modeHz * (0.10 * rand - 0.05) / max(duration, eps);
    phase = 2 * pi * (modeHz * localTime + 0.5 * sweep * localTime.^2);
    modal = modal + calibration.mode_gain(modeIndex) * (0.82 + 0.36 * rand) * ...
        exp(-localTime / modeDecay) .* sin(phase + 2 * pi * rand);
end
modal = modal / (max(abs(modal)) + eps);
burst = strength * tanh(drive * envelope .* ...
    (mix(1) * noise + mix(2) * modal));
delaySamples = randi([2, 9]);
if numel(burst) > delaySamples
    burst(delaySamples + 1:end) = burst(delaySamples + 1:end) + ...
        (0.10 + 0.12 * rand) * burst(1:end - delaySamples);
end
end

function output = add_burst(output, startIndex, burst)
finishIndex = min(numel(output), startIndex + numel(burst) - 1);
count = finishIndex - startIndex + 1;
output(startIndex:finishIndex) = output(startIndex:finishIndex) + burst(1:count);
end

function output = scale_rms(input, targetRms)
value = sqrt(mean(input.^2));
if value > 0
    output = input * targetRms / value;
else
    output = input;
end
end
