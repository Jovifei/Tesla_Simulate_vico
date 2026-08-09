function [excitation, context] = s12_engine_sound_excitation_frame(profile, state, context)
%S12_ENGINE_SOUND_EXCITATION_FRAME Synthetic phase-continuous multi-cylinder source.

frameSamples = profile.renderer.frame_samples.value;
sampleRate = profile.renderer.sample_rate_hz.value;
if nargin < 3 || isempty(context)
    context = struct("order_phase", zeros(1, 6), "firing_phase", 0, ...
        "intake_phase", 0, "supercharger_phase", 0, "transient_phase", 0, ...
        "transient", 0, "last_throttle", state(4));
end
rpm = min(max(state(1), profile.engine.idle_rpm.value), profile.engine.redline_rpm.value);
loadValue = min(max(state(2), 0), 1);
acceleration = min(max(state(3), -8), 8);
throttle = min(max(state(4), 0), 1);
timeIndex = (0:frameSamples - 1).';
baseFrequency = rpm / 60;
gains = profile.synthesis.order_gains.value;
excitation = zeros(frameSamples, 1);

for order = 1:6
    omega = 2 * pi * baseFrequency * order / sampleRate;
    loadBalance = 1 + loadValue * profile.synthesis.harmonic_tilt.value * (order - 1) / 5;
    excitation = excitation + gains(order) * loadBalance * sin(context.order_phase(order) + omega * timeIndex);
    context.order_phase(order) = mod(context.order_phase(order) + omega * frameSamples, 2 * pi);
end

cylinders = profile.engine.cylinder_count.value;
firingFrequency = baseFrequency * cylinders / 2;
firingOmega = 2 * pi * firingFrequency / sampleRate;
firingOrder = profile.engine.firing_order.value;
firingPhase = profile.engine.firing_phase_deg.value;
bankMap = profile.engine.bank_map.value;
sharpness = profile.synthesis.pulse_sharpness.value;
for cylinder = 1:cylinders
    phaseOffset = 2 * pi * firingPhase(firingOrder(cylinder)) / 360;
    bankColor = 1 + 0.07 * (bankMap(cylinder) - mean(bankMap));
    phase = context.firing_phase + phaseOffset + firingOmega * timeIndex;
    excitation = excitation + bankColor * (0.11 * sin(phase) + 0.05 * sharpness * sin(2 * phase));
end
context.firing_phase = mod(context.firing_phase + firingOmega * frameSamples, 2 * pi);

intakeOmega = 2 * pi * baseFrequency * 0.5 / sampleRate;
excitation = excitation + profile.synthesis.intake_tone.value * (0.05 + 0.05 * loadValue) * ...
    sin(context.intake_phase + intakeOmega * timeIndex);
context.intake_phase = mod(context.intake_phase + intakeOmega * frameSamples, 2 * pi);
if profile.synthesis.supercharger_tone.value > 0
    superchargerOmega = 2 * pi * baseFrequency * 10 / sampleRate;
    excitation = excitation + profile.synthesis.supercharger_tone.value * (0.03 + 0.05 * throttle) * ...
        sin(context.supercharger_phase + superchargerOmega * timeIndex);
    context.supercharger_phase = mod(context.supercharger_phase + superchargerOmega * frameSamples, 2 * pi);
end

throttleStep = max(throttle - context.last_throttle, 0);
context.last_throttle = throttle;
targetTransient = profile.transient.acceleration_gain.value * max(acceleration, 0) / 8 + ...
    profile.transient.lift_gain.value * max(-acceleration, 0) / 8 + profile.transient.attack.value * throttleStep;
context.transient = profile.transient.decay.value * context.transient + ...
    (1 - profile.transient.decay.value) * targetTransient;
transientOmega = 2 * pi * baseFrequency * 2 / sampleRate;
excitation = 0.12 * excitation + context.transient * sin(context.transient_phase + transientOmega * timeIndex);
context.transient_phase = mod(context.transient_phase + transientOmega * frameSamples, 2 * pi);
end
