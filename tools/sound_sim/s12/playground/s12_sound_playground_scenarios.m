function state = s12_sound_playground_scenarios(name, durationSeconds)
%S12_SOUND_PLAYGROUND_SCENARIOS Continuous synthetic vehicle-state traces.

if nargin < 2
    durationSeconds = 5;
end
validateattributes(durationSeconds, {'numeric'}, {"scalar", "finite", ">=", 0.1});

timestamp = (0:0.01:durationSeconds).';
u = timestamp / durationSeconds;
smooth = u.^2 .* (3 - 2 .* u);

switch lower(string(name))
    case "idle"
        rpm = 800 + 30 * sin(2 * pi * 0.7 * timestamp);
        speed = zeros(size(timestamp));
        acceleration = zeros(size(timestamp));
        loadValue = 0.08 + 0.02 * sin(2 * pi * 0.5 * timestamp);
        throttle = 0.10 + 0.02 * sin(2 * pi * 0.5 * timestamp);
    case "cruise"
        rpm = 2000 + 80 * sin(2 * pi * 0.25 * timestamp);
        speed = 60 + 1.5 * sin(2 * pi * 0.25 * timestamp);
        acceleration = gradient(speed, 0.01) / 3.6;
        loadValue = 0.30 + 0.03 * sin(2 * pi * 0.25 * timestamp);
        throttle = 0.32 + 0.03 * sin(2 * pi * 0.25 * timestamp);
    case "acceleration"
        rpm = 1000 + 5000 * smooth;
        speed = 10 + 90 * smooth;
        acceleration = gradient(speed, 0.01) / 3.6;
        loadValue = 0.45 + 0.50 * smooth;
        throttle = 0.50 + 0.45 * smooth;
    case {"lift", "throttle_lift"}
        rpm = 4200 - 2800 * smooth;
        speed = 85 - 35 * smooth;
        acceleration = gradient(speed, 0.01) / 3.6;
        loadValue = 0.60 * (1 - smooth) + 0.05;
        throttle = 0.65 * (1 - smooth) + 0.02;
    otherwise
        error("S12:Playground:Scenario", "Unsupported scenario: %s", name);
end

state = struct("timestamp_s", timestamp, "rpm", rpm, "speed_kmh", speed, ...
    "acceleration_mps2", acceleration, "load", loadValue, "throttle", throttle, ...
    "source_level", "C", "provenance", "synthetic scenario");
end
