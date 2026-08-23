function result = s12_v12_publish_pilot_audio(profileId, outputDirectory)
%S12_V12_PUBLISH_PILOT_AUDIO Simulate and publish one v1.2 pilot package.

arguments
    profileId (1, 1) string
    outputDirectory (1, 1) string
end
allowed = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock", ...
    "gtr_r35_2007_stock", "supra_jza80_rz_stock", "lexus_lfa_stock"];
if ~ismember(profileId, allowed)
    error("S12:EngineSoundV12:Publish", "Only v1.2 pilot profiles are publishable.");
end

commonFolder = fileparts(mfilename("fullpath"));
v12Folder = fileparts(commonFolder);
vehicleFolder = fullfile(v12Folder, "vehicles", profileId);
sharedFolder = fullfile(commonFolder, "shared_model");
addpath(commonFolder, sharedFolder, vehicleFolder);
cleanupPath = onCleanup(@() rmpath(commonFolder, sharedFolder, vehicleFolder));
model = "S12_" + profileId + "_v12";
load_system(model);
cleanupModel = onCleanup(@() closeLoadedModel(model));

simulation = sim(model, ...
    "ReturnWorkspaceOutputs", "on", ...
    "SaveOutput", "on", ...
    "OutputSaveName", "yout");
data = simulation.yout.getElement(1).Values.Data;
if ~isequal(size(data), [960, 2, 4500]) || any(~isfinite(data), "all")
    error("S12:EngineSoundV12:Publish", ...
        "Simulation must return 4500 finite [960,2] frames.");
end
pcm = reshape(permute(data, [1, 3, 2]), [], 2);
if max(abs(pcm), [], "all") >= 1
    error("S12:EngineSoundV12:Publish", "PCM must not clip.");
end

outputDirectory = char(outputDirectory);
if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
writeWave(fullfile(outputDirectory, "full_drive_cycle.wav"), pcm);
writeWave(fullfile(outputDirectory, "idle.wav"), segment(pcm, 2, 12));
writeWave(fullfile(outputDirectory, "acceleration.wav"), segment(pcm, 32, 48));
writeWave(fullfile(outputDirectory, "deceleration.wav"), segment(pcm, 54, 66));
writeWave(fullfile(outputDirectory, "afterfire.wav"), [ ...
    segment(pcm, 54, 66); segment(pcm, 82, 88)]);
copyfile(fullfile(vehicleFolder, "source_profile.json"), ...
    fullfile(outputDirectory, "source_profile_snapshot.json"));
copyfile(fullfile(vehicleFolder, "scenario_profile.json"), ...
    fullfile(outputDirectory, "scenario_profile_snapshot.json"));
copyfile(fullfile(vehicleFolder, "engine_identity_profile.json"), ...
    fullfile(outputDirectory, "engine_identity_profile_snapshot.json"));

metadata = struct( ...
    "schema_version", "s12-engine-sound-v12-pilot-package-1", ...
    "profile_id", profileId, ...
    "synthetic", true, ...
    "calibrated", false, ...
    "offline", true, ...
    "oem_clone", false, ...
    "sample_rate_hz", 48000, ...
    "bits_per_sample", 24, ...
    "channels", 2, ...
    "duration_s", 90, ...
    "frame_count", 4500, ...
    "sample_count", size(pcm, 1), ...
    "peak", max(abs(pcm), [], "all"), ...
    "clipping_samples", nnz(abs(pcm) >= 1), ...
    "architecture", ...
        "vehicle_cycle_to_engine_identity_to_source_to_frozen_4d_b_radiation_adapter_to_renderer", ...
    "engine_identity_profile_schema_version", "s12-engine-identity-profile-0.4", ...
    "engine_identity_scope", "synthetic_uncalibrated_not_oem_clone", ...
    "full_fvm_ptr_network", false);
writeJson(fullfile(outputDirectory, "metadata.json"), metadata);

names = ["full_drive_cycle.wav", "idle.wav", "acceleration.wav", ...
    "deceleration.wav", "afterfire.wav", ...
    "source_profile_snapshot.json", "scenario_profile_snapshot.json", ...
    "engine_identity_profile_snapshot.json", ...
    "metadata.json"];
lines = strings(numel(names), 1);
for index = 1:numel(names)
    lines(index) = upper(sha256File(fullfile(outputDirectory, names(index)))) + ...
        "  " + names(index);
end
writeText(fullfile(outputDirectory, "SHA256.txt"), strjoin(lines, newline) + newline);
result = metadata;
result.output_directory = string(outputDirectory);
result.full_wav_sha256 = sha256File(fullfile(outputDirectory, "full_drive_cycle.wav"));
end

function samples = segment(pcm, startTime, endTime)
first = startTime * 48000 + 1;
last = endTime * 48000;
samples = pcm(first:last, :);
end

function writeWave(path, pcm)
audiowrite(path, pcm, 48000, "BitsPerSample", 24);
end

function writeJson(path, value)
writeText(path, string(jsonencode(value, "PrettyPrint", true)) + newline);
end

function writeText(path, value)
file = fopen(path, "wt", "n", "UTF-8");
if file < 0
    error("S12:EngineSoundV12:Publish", "Cannot open output file.");
end
cleanup = onCleanup(@() fclose(file));
count = fprintf(file, "%s", value);
if count ~= strlength(value)
    error("S12:EngineSoundV12:Publish", "Cannot write complete output file.");
end
end

function value = sha256File(path)
file = fopen(path, "rb");
if file < 0
    error("S12:EngineSoundV12:Publish", "Cannot open file for hashing.");
end
cleanup = onCleanup(@() fclose(file));
bytes = fread(file, Inf, "*uint8");
digest = java.security.MessageDigest.getInstance("SHA-256");
digest.update(bytes);
value = lower(string(reshape(dec2hex( ...
    typecast(digest.digest(), "uint8"), 2).', 1, [])));
end

function closeLoadedModel(model)
if bdIsLoaded(model)
    close_system(model, 0);
end
end
