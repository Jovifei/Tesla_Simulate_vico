function excitation = s12_engine_sound_model_excitation_step(state, reset, cylinderCount, firingOrder, firingPhaseDeg, bankMap, orderGains, pulseSharpness, harmonicTilt, intakeTone, superchargerTone, attack, decay, accelerationGain, liftGain, backfireEnergy)
%S12_ENGINE_SOUND_MODEL_EXCITATION_STEP Codegen-friendly top-model excitation.

persistent orderPhase firingPhase intakePhase superchargerPhase transientPhase transient lastThrottle backfireTail
frameSamples = 960;
sampleRate = 48000;
if isempty(orderPhase) || reset
    orderPhase = zeros(1, 6);
    firingPhase = 0;
    intakePhase = 0;
    superchargerPhase = 0;
    transientPhase = 0;
    transient = 0;
    lastThrottle = state(4);
    backfireTail = 0;
end
rpm = state(1);
loadValue = min(max(state(2), 0), 1);
acceleration = min(max(state(3), -8), 8);
throttle = min(max(state(4), 0), 1);
timeIndex = (0:frameSamples - 1).';
baseFrequency = max(rpm, 1) / 60;
excitation = zeros(frameSamples, 1);
for order = 1:6
    omega = 2 * pi * baseFrequency * order / sampleRate;
    balance = 1 + loadValue * harmonicTilt * (order - 1) / 5;
    excitation = excitation + orderGains(order) * balance * sin(orderPhase(order) + omega * timeIndex);
    orderPhase(order) = mod(orderPhase(order) + omega * frameSamples, 2 * pi);
end
firingOmega = 2 * pi * baseFrequency * cylinderCount / 2 / sampleRate;
for cylinder = 1:cylinderCount
    phaseOffset = 2 * pi * firingPhaseDeg(firingOrder(cylinder)) / 360;
    bankColor = 1 + 0.07 * (bankMap(cylinder) - mean(bankMap));
    phase = firingPhase + phaseOffset + firingOmega * timeIndex;
    excitation = excitation + bankColor * (0.11 * sin(phase) + 0.05 * pulseSharpness * sin(2 * phase));
end
firingPhase = mod(firingPhase + firingOmega * frameSamples, 2 * pi);
intakeOmega = 2 * pi * baseFrequency * 0.5 / sampleRate;
excitation = excitation + intakeTone * (0.05 + 0.05 * loadValue) * sin(intakePhase + intakeOmega * timeIndex);
intakePhase = mod(intakePhase + intakeOmega * frameSamples, 2 * pi);
if superchargerTone > 0
    superchargerOmega = 2 * pi * baseFrequency * 10 / sampleRate;
    excitation = excitation + superchargerTone * (0.03 + 0.05 * throttle) * sin(superchargerPhase + superchargerOmega * timeIndex);
    superchargerPhase = mod(superchargerPhase + superchargerOmega * frameSamples, 2 * pi);
end
throttleStep = max(throttle - lastThrottle, 0);
lastThrottle = throttle;
targetTransient = accelerationGain * max(acceleration, 0) / 8 + liftGain * max(-acceleration, 0) / 8 + attack * throttleStep;
transient = decay * transient + (1 - decay) * targetTransient;
transientOmega = 2 * pi * baseFrequency * 2 / sampleRate;
excitation = 0.12 * excitation + transient * sin(transientPhase + transientOmega * timeIndex);
transientPhase = mod(transientPhase + transientOmega * frameSamples, 2 * pi);
backfireTail = 0.86 * backfireTail + backfireEnergy;
if backfireTail > 0
    envelope = backfireTail * decay .^ ((0:frameSamples - 1).' / (0.08 * sampleRate));
    phase = 2 * pi * (440 * timeIndex / sampleRate + 0.0008 * timeIndex .^ 2 / sampleRate);
    excitation = excitation + envelope .* (sin(phase) + 0.35 * sin(2 * phase));
end
end
