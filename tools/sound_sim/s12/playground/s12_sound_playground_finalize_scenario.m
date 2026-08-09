function scenario = s12_sound_playground_finalize_scenario(scenario)
%S12_SOUND_PLAYGROUND_FINALIZE_SCENARIO Create the sole model-workspace view of configuration frames.

signal = s12_sound_playground_signal_contract();
if ~isfield(scenario, "configuration_frames") || ~isnumeric(scenario.configuration_frames)
    error("S12:Playground:ScenarioFrames", "Scenario requires numeric configuration_frames.");
end
frames = double(scenario.configuration_frames);
frameCount = size(frames, 2);
if size(frames, 1) ~= 18 || frameCount < 1
    error("S12:Playground:ScenarioShape", "configuration_frames must have shape 18xframeCount.");
end
if isfield(scenario, "frame_count") && double(scenario.frame_count) ~= frameCount
    error("S12:Playground:ScenarioFrameCount", "Scenario frame_count does not match configuration_frames.");
end
if any(~isfinite(frames), "all")
    error("S12:Playground:ScenarioFinite", "configuration_frames must contain only finite values.");
end
if ~isfield(scenario, "timestamps_seconds") || numel(scenario.timestamps_seconds) ~= frameCount
    error("S12:Playground:ScenarioTimestamps", "Scenario timestamps must match frame_count.");
end
timestamps = double(reshape(scenario.timestamps_seconds, [], 1));
if any(~isfinite(timestamps)) || any(diff(timestamps) <= 0)
    error("S12:Playground:ScenarioTimestamps", "Scenario timestamps must be finite and strictly increasing.");
end
values = reshape(frames, 18, 1, frameCount);
scenario.configuration_frames = frames;
scenario.frame_count = frameCount;
scenario.workspace_signal = struct("time", timestamps, ...
    "signals", struct("values", values, "dimensions", [18, 1]));
roundTrip = reshape(scenario.workspace_signal.signals.values, 18, frameCount);
if ~isequal(roundTrip, scenario.configuration_frames)
    error("S12:Playground:ScenarioRoundTrip", "Scenario workspace round-trip does not match configuration_frames.");
end
scenario.scenario_sha256 = scenarioHash(scenario, signal.configuration.shape);
end

function value = scenarioHash(scenario, expectedShape)
payload = struct("name", string(scenario.name), "frame_count", double(scenario.frame_count), ...
    "timestamps_seconds", reshape(double(scenario.timestamps_seconds), 1, []), ...
    "configuration_frames", scenario.configuration_frames, "shape", expectedShape);
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(uint8(jsonencode(payload)));
value = upper(string(reshape(dec2hex(typecast(digest.digest, "uint8"), 2).', 1, [])));
end
