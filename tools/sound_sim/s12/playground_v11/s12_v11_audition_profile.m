function result = s12_v11_audition_profile(profileInput, varargin)
%S12_V11_AUDITION_PROFILE Render, publish, and optionally play one v1.1 vehicle.

parser = inputParser;
parser.addParameter("AfterfireLevel", "subtle");
parser.addParameter("Play", false, @(value)islogical(value) && isscalar(value));
parser.addParameter("RunId", "");
parser.addParameter("ScenarioKey", "s12-v11-audition");
parser.parse(varargin{:});
profile = resolveProfile(profileInput);
profile.vehicle_id = s12_v11_validate_canonical_vehicle_id(profile.vehicle_id);
rendered = s12_v11_render_profile(profile, ...
    "AfterfireLevel", parser.Results.AfterfireLevel, ...
    "ScenarioKey", parser.Results.ScenarioKey);
if size(rendered.pcm, 1) ~= 4320000 || ...
        size(rendered.pcm, 2) ~= profile.renderer.channels || ...
        rendered.sample_rate_hz ~= profile.renderer.sample_rate_hz || ...
        rendered.bits_per_sample ~= profile.renderer.bits_per_sample
    error("S12:EngineSoundV11:Publication", ...
        "Published full-cycle PCM must contain 4,320,000 stereo samples.");
end
outputDirectory = createOutputDirectory(profile.vehicle_id, parser.Results.RunId);
publishArtifacts(outputDirectory, profile, rendered, rendered.afterfire_level);
if parser.Results.Play
    sound(rendered.pcm, rendered.sample_rate_hz);
end
result = struct( ...
    "profile_id", profile.vehicle_id, ...
    "output_directory", outputDirectory, ...
    "sample_rate_hz", rendered.sample_rate_hz, ...
    "frame_count", 4500, ...
    "sample_count", 4320000, ...
    "pcm_sha256", rendered.pcm_sha256, ...
    "manifest_sha256", s12_v11_sha256_file(fullfile(outputDirectory, "manifest.json")));
end

function profile = resolveProfile(value)
if isstruct(value) && isscalar(value) && isfield(value, "vehicle_id") && isfield(value, "character")
    profile = value;
else
    profile = s12_v11_load_profile(value);
end
end

function outputDirectory = createOutputDirectory(profileId, requestedRunId)
runtimeRoot = s12V11RuntimeRoot();
profileId = s12_v11_validate_canonical_vehicle_id(profileId);
if ~isfolder(runtimeRoot)
    [created, message] = mkdir(runtimeRoot);
    if ~created
        error("S12:EngineSoundV11:Publication", ...
            "Cannot create the bounded runtime root: %s", message);
    end
end
runId = string(requestedRunId);
if strlength(runId) == 0
    runId = "run_" + string(datetime("now", Format="yyyyMMdd_HHmmss_SSS"));
end
if ~isscalar(runId) || isempty(regexp(char(runId), "^[A-Za-z0-9_-]+$", "once"))
    error("S12:EngineSoundV11:RunId", ...
        "RunId must contain only letters, digits, underscores, or hyphens.");
end
candidate = fullfile(runtimeRoot, runId, profileId);
if isfolder(candidate) || isfile(candidate)
    error("S12:EngineSoundV11:PublicationExists", ...
        "Refusing to overwrite an existing run/profile publication.");
end
[created, message] = mkdir(candidate);
if ~created
    error("S12:EngineSoundV11:Publication", ...
        "Cannot create the run/profile publication directory: %s", message);
end
outputDirectory = string(candidate);
end

function root = s12V11RuntimeRoot()
root = "E:\Tesla_speed\tasks\reports\runtime\s12-engine-sound-v11";
end

function publishArtifacts(outputDirectory, profile, rendered, afterfireLevel)
sampleRateHz = profile.renderer.sample_rate_hz;
bitsPerSample = profile.renderer.bits_per_sample;
pcm = rendered.pcm;
audiowrite(fullfile(outputDirectory, "full_drive_cycle.wav"), pcm, sampleRateHz, BitsPerSample=bitsPerSample);
writeSegment(fullfile(outputDirectory, "idle.wav"), pcm, sampleRateHz, bitsPerSample, 2.0, 12.0);
writeSegment(fullfile(outputDirectory, "acceleration.wav"), pcm, sampleRateHz, bitsPerSample, 32.0, 47.6);
writeSegment(fullfile(outputDirectory, "upshift.wav"), pcm, sampleRateHz, bitsPerSample, 47.4, 49.4);
writeSegment(fullfile(outputDirectory, "downshift.wav"), pcm, sampleRateHz, bitsPerSample, 65.8, 67.8);
writeSegment(fullfile(outputDirectory, "deceleration.wav"), pcm, sampleRateHz, bitsPerSample, 54.0, 66.0);
writeSegment(fullfile(outputDirectory, "afterfire.wav"), pcm, sampleRateHz, bitsPerSample, 82.0, 88.0);
writetable(rendered.trace, fullfile(outputDirectory, "vehicle_trace.csv"));
writeJson(fullfile(outputDirectory, "profile_snapshot.json"), profile);
writeJson(fullfile(outputDirectory, "sound_analysis.json"), rendered.analysis);
manifest = struct( ...
    "schema_version", "s12-engine-sound-v11-manifest-1", ...
    "profile_id", profile.vehicle_id, ...
    "synthetic", true, ...
    "uncalibrated", true, ...
    "offline", true, ...
    "oem_status", "non-OEM", ...
    "architecture", "vehicle_excitation_plus_afterfire_before_ptr_radiation_to_stereo", ...
    "sample_rate_hz", profile.renderer.sample_rate_hz, ...
    "frame_samples", profile.renderer.frame_samples, ...
    "frame_count", 4500, ...
    "sample_count", 4320000, ...
    "duration_s", 90, ...
    "channels", profile.renderer.channels, ...
    "bits_per_sample", profile.renderer.bits_per_sample, ...
    "hard_limiter", profile.renderer.hard_limiter, ...
    "peak", max(abs(pcm), [], "all"), ...
    "finite_pcm", all(isfinite(pcm), "all"), ...
    "afterfire_level", afterfireLevel, ...
    "afterfire_insertion_stage", "before_ptr_radiation", ...
    "post_pcm_append", false, ...
    "pcm_sha256", rendered.pcm_sha256, ...
    "raw_reference_audio_used", false);
writeJson(fullfile(outputDirectory, "manifest.json"), manifest);
writeSha256(outputDirectory);
expected = ["full_drive_cycle.wav", "idle.wav", "acceleration.wav", ...
    "upshift.wav", "downshift.wav", "deceleration.wav", "afterfire.wav", ...
    "vehicle_trace.csv", "profile_snapshot.json", "sound_analysis.json", ...
    "manifest.json", "SHA256.txt"];
actual = string({dir(outputDirectory).name});
actual = sort(actual(~ismember(actual, [".", ".."])));
if ~isequal(actual, sort(expected))
    error("S12:EngineSoundV11:Publication", ...
        "Publication directory does not contain the exact artifact contract.");
end
end

function writeSegment(path, pcm, sampleRateHz, bitsPerSample, startSeconds, endSeconds)
first = floor(startSeconds * sampleRateHz) + 1;
last = min(floor(endSeconds * sampleRateHz), size(pcm, 1));
segment = pcm(first:last, :);
fadeSamples = min(round(0.010 * sampleRateHz), floor(size(segment, 1) / 2));
if fadeSamples > 0
    envelope = ones(size(segment, 1), 1);
    ramp = (0:fadeSamples - 1).' / fadeSamples;
    envelope(1:fadeSamples) = ramp;
    envelope(end - fadeSamples + 1:end) = flipud(ramp);
    segment = segment .* envelope;
end
audiowrite(path, segment, sampleRateHz, BitsPerSample=bitsPerSample);
end

function writeJson(path, value)
temporary = string(path) + ".tmp";
file = fopen(temporary, "w", "n", "UTF-8");
if file < 0
    error("S12:EngineSoundV11:Publication", "Cannot open JSON output: %s", path);
end
cleanup = onCleanup(@()fclose(file));
written = fprintf(file, "%s\n", jsonencode(value, PrettyPrint=true));
if written <= 0
    error("S12:EngineSoundV11:Publication", "Cannot write JSON output: %s", path);
end
clear cleanup
[moved, message] = movefile(temporary, path, "f");
if ~moved
    error("S12:EngineSoundV11:Publication", "Cannot publish JSON output: %s", message);
end
end

function writeSha256(outputDirectory)
names = ["full_drive_cycle.wav", "idle.wav", "acceleration.wav", ...
    "upshift.wav", "downshift.wav", "deceleration.wav", "afterfire.wav", ...
    "vehicle_trace.csv", "profile_snapshot.json", "sound_analysis.json", "manifest.json"];
names = sort(names);
file = fopen(fullfile(outputDirectory, "SHA256.txt"), "w", "n", "UTF-8");
if file < 0
    error("S12:EngineSoundV11:Publication", "Cannot write SHA256.txt.");
end
cleanup = onCleanup(@()fclose(file));
for name = names
    fprintf(file, "%s  %s\n", s12_v11_sha256_file(fullfile(outputDirectory, name)), name);
end
end

function hash = s12_v11_sha256_file(path)
file = fopen(path, "r", "ieee-le");
if file < 0
    error("S12:EngineSoundV11:Hash", "Cannot read file for SHA-256: %s", path);
end
cleanup = onCleanup(@()fclose(file));
digest = java.security.MessageDigest.getInstance("SHA-256");
while true
    bytes = fread(file, 1024 * 1024, "*uint8");
    if isempty(bytes)
        break;
    end
    digest.update(bytes);
end
hash = lower(join(compose("%02x", typecast(digest.digest(), "uint8")), ""));
end
