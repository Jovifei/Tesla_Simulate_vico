function rasp = v6_render_combustion_rasp(profile, state, exhaust, sampleRate)
%V6_RENDER_COMBUSTION_RASP Add pulse-synchronous mid-band exhaust roughness.

rpmGate = clamp((state.rpm - profile.rasp.start_rpm) / ...
    (profile.rasp.full_rpm - profile.rasp.start_rpm));
loadGate = clamp((state.load - 0.12) / 0.88) .^ 1.25;
gate = rpmGate .* loadGate .* state.torque_gain;
source = exhaust / max(max(abs(exhaust)), eps);

drive = 1 + (profile.rasp.nonlinear_drive - 1) .* rpmGate;
residual = tanh(drive .* source) - source;
residual = band_limit(residual, profile.rasp.highpass_hz, ...
    profile.rasp.lowpass_hz, sampleRate);
residual = residual / max(sqrt(mean(residual .^ 2)), eps);

texture = band_limit(randn(size(source)), profile.rasp.highpass_hz, ...
    profile.rasp.lowpass_hz, sampleRate);
texture = texture / max(sqrt(mean(texture .^ 2)), eps);
jitter = lowpass_one_pole(randn(size(source)), profile.rasp.jitter_hz, sampleRate);
jitter = jitter / max(max(abs(jitter)), eps);
pulseGate = sqrt(abs(source));

rasp = gate .* pulseGate .* (1 + profile.rasp.jitter_gain * jitter) .* ...
    (profile.rasp.nonlinear_gain * residual + ...
    profile.rasp.texture_gain * texture);
rasp(~isfinite(rasp)) = 0;
end

function output = band_limit(input, highpassHz, lowpassHz, sampleRate)
highPole = exp(-2 * pi * highpassHz / sampleRate);
highpassed = filter([highPole, -highPole], [1, -highPole], input);
output = lowpass_one_pole(highpassed, lowpassHz, sampleRate);
end

function output = lowpass_one_pole(input, cutoffHz, sampleRate)
pole = exp(-2 * pi * cutoffHz / sampleRate);
output = filter(1 - pole, [1, -pole], input);
end

function value = clamp(value)
value = min(1, max(0, value));
end
