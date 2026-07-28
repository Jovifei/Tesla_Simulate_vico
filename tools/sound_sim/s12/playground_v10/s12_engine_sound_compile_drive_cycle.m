function cycle = s12_engine_sound_compile_drive_cycle(profile, backfireLevel)
%S12_ENGINE_SOUND_COMPILE_DRIVE_CYCLE Compile the fixed synthetic 90-second drive.

if nargin < 2 || strlength(string(backfireLevel)) == 0
    backfireLevel = profile.backfire.default_level.value;
end
s12_engine_sound_validate_profile(profile);
backfireLevel = string(backfireLevel);
if ~isscalar(backfireLevel) || ~ismember(backfireLevel, ["off", "subtle", "aggressive"])
    error("S12:EngineSoundV10:BackfireLevel", "BackfireLevel must be off, subtle, or aggressive.");
end

sampleRate = profile.renderer.sample_rate_hz.value;
frameSamples = profile.renderer.frame_samples.value;
frameDuration = frameSamples / sampleRate;
frameCount = 90 / frameDuration;
if frameCount ~= 4500
    error("S12:EngineSoundV10:FrameContract", "The fixed cycle must contain exactly 4,500 frames.");
end
timestamp = (0:frameCount - 1).' * frameDuration;
boundaries = [0, 2, 12, 22, 32, 48, 54, 66, 72, 82, 88, 90];
ids = ["startup", "idle", "pull_away", "cruise", "wide_open_throttle", "high_load_hold", ...
    "lift_off", "downshift_blip", "second_acceleration", "rapid_lift", "settle_idle"];
segments = repmat(struct("id", "", "start_s", 0, "end_s", 0), 1, numel(ids));
for index = 1:numel(ids)
    segments(index) = struct("id", ids(index), "start_s", boundaries(index), "end_s", boundaries(index + 1));
end

idle = profile.engine.idle_rpm.value;
redline = profile.engine.redline_rpm.value;
rpm = interpolateSegments(timestamp, boundaries, [idle, idle, idle, 0.42 * redline, 0.38 * redline, ...
    redline, redline, 0.36 * redline, 0.55 * redline, 0.82 * redline, idle, idle]);
loadValue = interpolateSegments(timestamp, boundaries, [0.02, 0.08, 0.10, 0.42, 0.28, 1.00, 1.00, 0.06, 0.36, 0.78, 0.03, 0.08]);
throttle = interpolateSegments(timestamp, boundaries, [0.00, 0.08, 0.10, 0.46, 0.30, 1.00, 1.00, 0.00, 0.38, 0.80, 0.00, 0.08]);
speedKph = interpolateSegments(timestamp, boundaries, [0, 0, 0, 40, 60, 132, 132, 82, 88, 126, 70, 30]);
acceleration = gradient(speedKph / 3.6, frameDuration);
overrun = double((timestamp >= 54 & timestamp < 66) | (timestamp >= 82 & timestamp < 88));
events = compileBackfireEvents(profile, backfireLevel);
cycle = struct( ...
    "version", "Synthetic Engine Sound Playground v1.0", ...
    "synthetic", true, ...
    "sample_rate_hz", sampleRate, ...
    "frame_samples", frameSamples, ...
    "frame_count", frameCount, ...
    "timestamp_s", timestamp, ...
    "state_columns", ["rpm", "load", "acceleration_mps2", "throttle", "speed_kph", "overrun_gate"], ...
    "state", [rpm, loadValue, acceleration, throttle, speedKph, overrun], ...
    "segments", segments, ...
    "backfire_level", backfireLevel, ...
    "backfire_events", events);
end

function values = interpolateSegments(timestamp, boundaries, nodes)
values = zeros(size(timestamp));
for index = 1:numel(boundaries) - 1
    mask = timestamp >= boundaries(index) & timestamp < boundaries(index + 1);
    fraction = (timestamp(mask) - boundaries(index)) / (boundaries(index + 1) - boundaries(index));
    smoothFraction = fraction .^ 2 .* (3 - 2 * fraction);
    values(mask) = nodes(index) + (nodes(index + 1) - nodes(index)) * smoothFraction;
end
end

function events = compileBackfireEvents(profile, backfireLevel)
events = repmat(struct("time_s", 0, "energy", 0, "decay", 0, "level", ""), 1, 0);
if backfireLevel == "off"
    return
end
times = [55.10, 57.00, 60.40, 83.20, 85.10];
if backfireLevel == "subtle"
    energy = profile.backfire.subtle_gain.value;
else
    energy = profile.backfire.aggressive_gain.value;
end
for index = 1:numel(times)
    events(end + 1) = struct("time_s", times(index), "energy", energy, ...
        "decay", profile.backfire.pulse_decay.value, "level", backfireLevel); %#ok<AGROW>
end
end
