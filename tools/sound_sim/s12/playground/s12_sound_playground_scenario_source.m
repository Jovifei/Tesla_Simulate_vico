function scenario = s12_sound_playground_scenario_source(name, durationSeconds, overrides)
%S12_SOUND_PLAYGROUND_SCENARIO_SOURCE Frozen 20 ms model-consumed frames.

signal = s12_sound_playground_signal_contract();
if nargin < 2 || isempty(durationSeconds)
    durationSeconds = signal.qualification_audio_duration_s;
end
if nargin < 3
    overrides = struct();
end
if abs(durationSeconds - signal.qualification_audio_duration_s) > eps(signal.qualification_audio_duration_s)
    error("S12:Playground:QualificationDuration", ...
        "Qualification is fixed at %.17g seconds of PCM.", signal.qualification_audio_duration_s);
end
params = s12_sound_playground_parameters(overrides);
state = s12_sound_playground_scenarios(name, durationSeconds);
frameCount = signal.qualification_frame_count;
timestamps = (0:frameCount - 1).' * signal.frame_duration_s;
frames = zeros(signal.configuration.shape(1), frameCount);
for frame = 1:frameCount
    frames(:, frame) = packFrame(state, timestamps(frame), params, signal);
end
scenario = struct( ...
    "source", "model_consumed_frame_state", ...
    "mode", "qualification", ...
    "name", string(name), ...
    "sample_time_seconds", signal.frame_period_s, ...
    "frame_count", frameCount, ...
    "stop_time_s", signal.qualification_stop_time_s, ...
    "audio_duration_s", signal.qualification_audio_duration_s, ...
    "timestamps_seconds", timestamps, ...
    "configuration_frames", frames, ...
    "speed_projection", "NOT_CONSUMED_BY_V09_18_ELEMENT_CONTRACT", ...
    "runtime_status", "REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION");
scenario = s12_sound_playground_finalize_scenario(scenario);
end

function packed = packFrame(state, timestamp, params, signal)
index = signal.indices;
packed = zeros(signal.configuration.shape(1), 1);
packed(index.rpm) = sample(state.timestamp_s, state.rpm, timestamp);
packed(index.load) = sample(state.timestamp_s, state.load, timestamp);
packed(index.acceleration) = sample(state.timestamp_s, state.acceleration_mps2, timestamp);
packed(index.throttle) = sample(state.timestamp_s, state.throttle, timestamp);
packed(index.cylinder_count) = params.cylinder_count;
packed(index.firing_order) = reshape(params.firing_order, [], 1);
packed(index.order_gain) = reshape(params.order_gain, [], 1);
packed(index.pipe_length) = params.pipe_length_m;
packed(index.area) = params.area_m2;
packed(index.reflection) = params.reflection_coefficient;
packed(index.damping) = params.damping;
packed(index.gain_db) = params.gain_db;
end

function value = sample(time, data, timestamp)
value = interp1(time, data, timestamp, "linear", "extrap");
end
