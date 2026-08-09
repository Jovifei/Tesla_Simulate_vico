function excitation = s12_sound_playground_excitation_step(rpm, loadValue, acceleration, throttle, cylinderCount, firingOrder, orderGain, reset)
%S12_SOUND_PLAYGROUND_EXCITATION_STEP Phase-continuous synthetic excitation.
% This is deliberately synthetic and is not an OEM firing or pressure model.

persistent phase transient lastThrottle
frameSamples = 960;
sampleRate = 48000;
if isempty(phase) || reset
    phase = zeros(1, 5);
    transient = 0;
    lastThrottle = throttle;
end

if cylinderCount ~= 4 || numel(firingOrder) ~= 4 || ~isequal(sort(reshape(firingOrder, 1, [])), 1:4)
    error("S12:Playground:CylinderScope", "Synthetic excitation requires cylinder_count=4 and firing_order=1:4 permutation.");
end
rpm = min(max(rpm, 800), 7000);
loadValue = min(max(loadValue, 0), 1);
acceleration = min(max(acceleration, -2), 5);
throttle = min(max(throttle, 0), 1);
orderGain = reshape(orderGain, 1, 4);
timeIndex = (0:frameSamples - 1).';
baseFrequency = rpm / 60;
excitation = zeros(frameSamples, 1);
loadBalance = [1.00, 0.50 + 0.50 * loadValue, 0.20 + 0.80 * loadValue, 0.10 + 0.90 * loadValue];

for order = 1:4
    omega = 2 * pi * baseFrequency * order / sampleRate;
    excitation = excitation + orderGain(order) * loadBalance(order) * sin(phase(order) + omega * timeIndex);
    phase(order) = mod(phase(order) + omega * frameSamples, 2 * pi);
end

firingFrequency = baseFrequency * (cylinderCount / 2);
firingOmega = 2 * pi * firingFrequency / sampleRate;
firingOrder = reshape(firingOrder, 1, []);
syntheticCylinderColor = [1.00, 0.92, 1.06, 0.88];
for cylinder = 1:4
    phaseOffset = 2 * pi * (firingOrder(cylinder) - 1) / 4;
    excitation = excitation + 0.08 * syntheticCylinderColor(cylinder) * ...
        sin(phase(5) + phaseOffset + firingOmega * timeIndex);
end
phase(5) = mod(phase(5) + firingOmega * frameSamples, 2 * pi);

throttleStep = max(throttle - lastThrottle, 0);
lastThrottle = throttle;
targetTransient = 0.08 * max(acceleration, 0) / 5 + 0.05 * max(-acceleration, 0) / 2 + 0.10 * throttleStep;
transient = 0.88 * transient + 0.12 * targetTransient;
excitation = 0.12 * excitation + transient * sin(phase(2) + 2 * pi * baseFrequency * 2 * timeIndex / sampleRate);
end
