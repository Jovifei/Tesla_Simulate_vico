function [pcm, trace, params] = s12_sound_playground_render_case(name, durationSeconds, overrides)
%S12_SOUND_PLAYGROUND_RENDER_CASE Deterministic offline renderer for v0.9.

if nargin < 2
    durationSeconds = 5;
end
if nargin < 3
    overrides = struct();
end
params = s12_sound_playground_parameters(overrides);
state = s12_sound_playground_scenarios(name, durationSeconds);
frameDuration = params.frame_samples / params.sample_rate_hz;
frameCount = floor(durationSeconds / frameDuration);
pcm = zeros(frameCount * params.frame_samples, 2);
trace = struct("timestamp_s", zeros(frameCount, 1), "rpm", zeros(frameCount, 1), ...
    "load", zeros(frameCount, 1), "acceleration_mps2", zeros(frameCount, 1), "throttle", zeros(frameCount, 1));
gain = 10^(params.gain_db / 20);

for frame = 1:frameCount
    timestamp = (frame - 1) * frameDuration;
    rpm = interp1(state.timestamp_s, state.rpm, timestamp, "linear", "extrap");
    loadValue = interp1(state.timestamp_s, state.load, timestamp, "linear", "extrap");
    acceleration = interp1(state.timestamp_s, state.acceleration_mps2, timestamp, "linear", "extrap");
    throttle = interp1(state.timestamp_s, state.throttle, timestamp, "linear", "extrap");
    reset = frame == 1;
    excitation = s12_sound_playground_excitation_step(rpm, loadValue, acceleration, throttle, ...
        params.cylinder_count, params.firing_order, params.order_gain, reset);
    pressure = s12_sound_playground_ptr_tuning_step(excitation, params.pipe_length_m, params.area_m2, ...
        params.reflection_coefficient, params.damping, reset);
    index = (frame - 1) * params.frame_samples + (1:params.frame_samples);
    pcm(index, :) = gain * [pressure, pressure];
    trace.timestamp_s(frame) = timestamp;
    trace.rpm(frame) = rpm;
    trace.load(frame) = loadValue;
    trace.acceleration_mps2(frame) = acceleration;
    trace.throttle(frame) = throttle;
end
end
