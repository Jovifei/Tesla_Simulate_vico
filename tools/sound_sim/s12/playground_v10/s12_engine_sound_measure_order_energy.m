function analysis = s12_engine_sound_measure_order_energy(excitation, profile, rpm)
%S12_ENGINE_SOUND_MEASURE_ORDER_ENERGY Measure six synthetic order correlations.

sampleRate = profile.renderer.sample_rate_hz.value;
sampleIndex = (0:numel(excitation) - 1).';
baseFrequency = mean(rpm) / 60;
orderEnergy = zeros(1, 6);
for order = 1:6
    basis = sin(2 * pi * baseFrequency * order * sampleIndex / sampleRate);
    orderEnergy(order) = abs(basis' * excitation) / numel(excitation);
end
analysis = struct("base_frequency_hz", baseFrequency, "order_energy", orderEnergy);
end
