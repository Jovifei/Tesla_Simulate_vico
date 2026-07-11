function result = tune_classic_sound(profileName, overrides, playAudio)
%TUNE_CLASSIC_SOUND Render one profile with temporary parameter overrides.

arguments
    profileName (1,1) string
    overrides (1,1) struct = struct()
    playAudio (1,1) logical = false
end

profile = vehicle_profile(profileName);
names = fieldnames(overrides);
for index = 1:numel(names)
    name = names{index};
    if ~isfield(profile, name)
        error("jovi:sound:UnknownTuningField", ...
            "Unknown profile field: %s", name);
    end
    profile.(name) = overrides.(name);
end

sampleRate = 48000;
[time, rpm, throttle, gear, speed] = build_demo_cycle(profile, sampleRate);
[audio, trace, events] = synthesize_engine_sound( ...
    profile, time, rpm, throttle, gear, sampleRate);
trace.speed_kmh = speed.';

scriptDir = fileparts(mfilename("fullpath"));
projectRoot = fileparts(fileparts(fileparts(scriptDir)));
outputDir = fullfile(projectRoot, "build", "sound-sim", "tuning-preview");
if ~isfolder(outputDir)
    mkdir(outputDir);
end
stem = char(profile.name + "_tuned");
mainPath = fullfile(outputDir, stem + ".wav");
backfirePath = fullfile(outputDir, stem + "_backfire.wav");
shiftPath = fullfile(outputDir, stem + "_shift.wav");
tracePath = fullfile(outputDir, stem + "_trace.csv");
audiowrite(mainPath, audio.', sampleRate, BitsPerSample=16);
audiowrite(backfirePath, normalize_layer(trace.backfire), ...
    sampleRate, BitsPerSample=16);
audiowrite(shiftPath, normalize_layer(trace.shift_transient), ...
    sampleRate, BitsPerSample=16);
writetable(trace(1:round(sampleRate / 100):end, :), tracePath);

if playAudio
    soundsc(audio, sampleRate);
end
result = struct("profile", profile, "events", events, ...
    "main_wav", mainPath, "backfire_wav", backfirePath, ...
    "shift_wav", shiftPath, "trace_csv", tracePath);
disp(result);
end

function output = normalize_layer(input)
peak = max(abs(input));
if peak > 0
    output = 0.9 * input / peak;
else
    output = input;
end
end
