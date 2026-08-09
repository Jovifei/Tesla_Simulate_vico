function result = s12_v12_publish_identity_demo(profileId, outputDirectory)
%S12_V12_PUBLISH_IDENTITY_DEMO Publish v0.14 listening cuts from one simulation.
% The underlying render remains synthetic and uncalibrated. This function only
% labels/copies segments of the existing 90-second offline Simulink render.

arguments
    profileId (1, 1) string
    outputDirectory (1, 1) string
end

names = s12_v12_identity_demo_names(profileId);
result = s12_v12_publish_pilot_audio(profileId, outputDirectory);
outputDirectory = char(outputDirectory);
copyfile(fullfile(outputDirectory, "full_drive_cycle.wav"), ...
    fullfile(outputDirectory, names(1)));
copyfile(fullfile(outputDirectory, "idle.wav"), ...
    fullfile(outputDirectory, names(2)));
copyfile(fullfile(outputDirectory, "acceleration.wav"), ...
    fullfile(outputDirectory, names(3)));
copyfile(fullfile(outputDirectory, "deceleration.wav"), ...
    fullfile(outputDirectory, names(4)));

[pcm, sampleRateHz] = audioread(fullfile(outputDirectory, "full_drive_cycle.wav"));
if sampleRateHz ~= 48000 || size(pcm, 2) ~= 2 || size(pcm, 1) < 54 * sampleRateHz
    error("S12:EngineIdentity:Demo", "The pilot render cannot provide a full-pull segment.");
end
fullPull = pcm(48 * sampleRateHz + 1:54 * sampleRateHz, :);
audiowrite(fullfile(outputDirectory, names(5)), fullPull, sampleRateHz, ...
    "BitsPerSample", 24);
result.identity_demo_names = names;
result.identity_scope = "synthetic_uncalibrated_not_oem_clone";
end
