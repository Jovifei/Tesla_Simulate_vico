function result = s12_engine_sound_render_cycle(profile, varargin)
%S12_ENGINE_SOUND_RENDER_CYCLE Render deterministic stereo PCM from one profile.

s12_engine_sound_validate_profile(profile);
parser = inputParser;
parser.addParameter("BackfireLevel", profile.backfire.default_level.value);
parser.addParameter("FrameIndices", []);
parser.parse(varargin{:});
cycle = s12_engine_sound_compile_drive_cycle(profile, parser.Results.BackfireLevel);
frameIndices = parser.Results.FrameIndices;
if isempty(frameIndices)
    frameIndices = 1:cycle.frame_count;
end
if ~isnumeric(frameIndices) || any(frameIndices ~= floor(frameIndices)) || ...
        any(frameIndices < 1) || any(frameIndices > cycle.frame_count)
    error("S12:EngineSoundV10:FrameIndices", "FrameIndices must be valid integer frame positions.");
end
frameIndices = reshape(frameIndices, 1, []);
s12_engine_sound_require_shared_adapter();
frameSamples = cycle.frame_samples;
pcm = zeros(numel(frameIndices) * frameSamples, 2);
excitationAll = zeros(numel(frameIndices) * frameSamples, 1);
context = [];
for position = 1:numel(frameIndices)
    frameIndex = frameIndices(position);
    [excitation, context] = s12_engine_sound_excitation_frame(profile, cycle.state(frameIndex, :), context);
    excitation = s12_engine_sound_add_backfire(excitation, cycle.backfire_events, frameIndex, ...
        cycle.sample_rate_hz, frameSamples);
    pressure = s12_sound_playground_ptr_tuning_step(excitation, profile.ptr.pipe_length_m.value, ...
        profile.ptr.area_m2.value, profile.ptr.reflection_coefficient.value, profile.ptr.damping.value, position == 1);
    samples = (position - 1) * frameSamples + (1:frameSamples);
    gain = 10^(profile.renderer.gain_db.value / 20);
    pcm(samples, :) = gain * [pressure, 0.985 * pressure];
    excitationAll(samples) = excitation;
end
if any(~isfinite(pcm), "all") || max(abs(pcm), [], "all") >= 1
    error("S12:EngineSoundV10:AudioSafety", "Synthetic renderer generated nonfinite or clipping PCM.");
end
result = struct("sample_rate_hz", cycle.sample_rate_hz, "frame_samples", frameSamples, ...
    "frame_indices", frameIndices, "pcm", pcm, "excitation", excitationAll, ...
    "analysis", s12_engine_sound_measure_order_energy(excitationAll, profile, cycle.state(frameIndices, 1)));
end
